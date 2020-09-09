#! /usr/bin/env python3

import os
import sys
import argparse
import urllib.request as urllib
import xml.etree.ElementTree as etree
from datetime import datetime
import json
import random

#----------------------------------------
def pause(question='PRESS ENTER TO CONTINUE ...'):
    """ pause for debug purposes """
    if sys.version[0] == '2':
        response = raw_input(question)
    else:
        response = input(question)
    return response

#----------------------------------------
def getValue (segment, tagName):
    """ get an xml element text value """
    try: value = segment.find(tagName).text.strip()
    except: value = ''
    else: 
        if len(value) == 0:
            value = ''
    return value
    
#----------------------------------------
def formatDate(inStr, outputFormat = '%Y-%m-%d'):
    """ format a date as yyyy-mm-dd """
    #--bypass if not complete
    outStr = inStr
    #if len(inStr) >= 6:

    formatList = []
    formatList.append("%Y-%m-%d")
    formatList.append("%m/%d/%Y")
    formatList.append("%m/%d/%y")
    formatList.append("%d %b %Y")
    formatList.append("%d %m %Y")
    #formatList.append("%Y")

    #formatList.append("CIRCA %Y")

    for format in formatList:
        #outStr = datetime.strftime(datetime.strptime(inStr, format), '%Y-%m-%d')
        try: outStr = datetime.strftime(datetime.strptime(inStr, format), outputFormat)
        except: pass
        else: 
            break

    return outStr

#----------------------------------------
def updateStat(cat1, cat2, example = None):
    if cat1 not in statPack:
        statPack[cat1] = {}
    if cat2 not in statPack[cat1]:
        statPack[cat1][cat2] = {}
        statPack[cat1][cat2]['count'] = 1

    statPack[cat1][cat2]['count'] += 1
    if example:
        if 'examples' not in statPack[cat1][cat2]:
            statPack[cat1][cat2]['examples'] = []
        if example not in statPack[cat1][cat2]['examples']:
            if len(statPack[cat1][cat2]['examples']) < 5:
                statPack[cat1][cat2]['examples'].append(example)
            else:
                randomSampleI = random.randint(2,4)
                statPack[cat1][cat2]['examples'][randomSampleI] = example
    return

#----------------------------------------
def processFile(inputFile, outputFile, includeAll):
    """ convert the ofac sdn xml file to json for senzing  """

    print('')
    print('Reading from: %s ...' % inputFile)

    #--read the file into memory
    try: f = open(inputFile)
    except IOError as err:
        print('')
        print(err)
        print('could not open %s!' % inputFile)
        print('')
        return -1

    xmlDoc = f.read()
    f.close()
    if type(xmlDoc) != str: #--urllib returns bytes for python3
        xmlDoc = xmlDoc.decode('utf-8')
    
    #--name spaces not needed and can mess up etree if not accessible
    startPos = xmlDoc.find(' xmlns:')
    while startPos > 0:
        xmlDoc = xmlDoc[0:startPos] + xmlDoc[xmlDoc.find('>',startPos):]
        startPos = xmlDoc.find(' xmlns:')

    #--try to parse
    try: xmlRoot = etree.fromstring(xmlDoc)
    except etree.ParseError as err:
        print('')
        print('XML Error: %s' % err)
        print('')
        return -1
    except:
        print('')
        print('%s is not a valid XML file!' % inputFile)
        print('')
        return -1
    publishDate = getValue(xmlRoot, 'publshInformation/Publish_Date')
    
    #--open output file
    print('')
    print('writing to %s ...' % outputFile)
    try: outputHandle = open(outputFile, "w", encoding='utf-8', newline='')
    except IOError as err:
        print('')
        print(err)
        print('could not open %s!' % outputFile)
        print('')
        return -1

    #--for each sdn entry record
    rowCnt = 0
    for sdnEntry in xmlRoot.findall('sdnEntry'):

        #--filter for only entities and individuals unless they want to include all
        g2EntityType = None
        if getValue(sdnEntry, 'sdnType') in ('Entity', 'Individual') or includeAll:
            if getValue(sdnEntry, 'sdnType') == 'Entity':
                g2EntityType = 'ORGANIZATION'
            if getValue(sdnEntry, 'sdnType') == 'Individual':
                g2EntityType = 'PERSON'
            if getValue(sdnEntry, 'sdnType') == 'Vessel':
                g2EntityType = 'VESSEL'
            if getValue(sdnEntry, 'sdnType') == 'Aircraft':
                g2EntityType = 'AIRCRAFT'
        if g2EntityType:
            updateStat('ENTITY_TYPE', g2EntityType)
            rowCnt += 1 
        
            isoCountryList = []
            
            jsonData = {}
            jsonData['DATA_SOURCE'] = 'OFAC'
            jsonData['ENTITY_TYPE'] = g2EntityType
            jsonData['RECORD_TYPE'] = g2EntityType
            jsonData['RECORD_ID'] = getValue(sdnEntry, 'uid')
            jsonData['OFAC_ID'] = getValue(sdnEntry, 'uid')
            jsonData['PUBLISH_DATE'] = publishDate
            if getValue(sdnEntry, 'title'):
                jsonData['SDN_TITLE'] = getValue(sdnEntry, 'title')
                updateStat('PAYLOAD_DATA', 'SDN_TITLE')
            if getValue(sdnEntry, 'remarks'):
                jsonData['SDN_REMARKS'] = getValue(sdnEntry, 'remarks')
                updateStat('PAYLOAD_DATA', 'SDN_REMARKS')
                
            #--add the SDN programs (usually only one)
            programList = None
            for programRecord in sdnEntry.findall('programList'):
                if getValue(programRecord, 'program'):
                    if not programList:
                        programList = getValue(programRecord, 'program')
                    else:    
                        programList = programList + ', ' + getValue(programRecord, 'program')
            if programList:
                jsonData['SDN_PROGRAM'] = programList
                updateStat('PAYLOAD_DATA', 'SDN_PROGRAM')

            #--get the names 
            nameList = []
            #--get the primary
            if getValue(sdnEntry, 'lastName') or getValue(sdnEntry, 'firstName'):
                nameDict = {}
                nameDict['NAME_TYPE'] = 'PRIMARY'
                if getValue(sdnEntry, 'sdnType') != 'Individual':
                    nameDict['NAME_ORG'] = getValue(sdnEntry, 'lastName')
                else:
                    if getValue(sdnEntry, 'lastName'):
                        nameDict['NAME_LAST'] = getValue(sdnEntry, 'lastName')
                    if getValue(sdnEntry, 'firstName'):
                        nameDict['NAME_FIRST'] = getValue(sdnEntry, 'firstName')
                nameList.append(nameDict)
                updateStat('NAME_TYPE', 'PRIMARY')

            #--add any AKAs
            for subRecord in sdnEntry.findall('akaList/aka'):
                if getValue(subRecord, 'lastName') or getValue(subRecord, 'firstName'):
                    nameDict = {}
                    nameDict['NAME_TYPE'] = getValue(subRecord, 'type').replace('.','').upper()
                    if getValue(sdnEntry, 'sdnType') != 'Individual':
                        nameDict['NAME_ORG'] = getValue(subRecord, 'lastName')
                    else:
                        if getValue(subRecord, 'lastName'):
                            nameDict['NAME_LAST'] = getValue(subRecord, 'lastName')
                        if getValue(subRecord, 'firstName'):
                            nameDict['NAME_FIRST'] = getValue(subRecord, 'firstName')
                    nameList.append(nameDict)
                    updateStat('NAME_TYPE', nameDict['NAME_TYPE'])
            if nameList:
                jsonData['NAME_LIST'] = nameList

            #--add any attributes (note: sublists must be dictionaries even if only a single field)
            attrList = []
            for subRecord in sdnEntry.findall('dateOfBirthList/dateOfBirthItem'):
                if getValue(subRecord, 'dateOfBirth'):
                    if formatDate(getValue(subRecord, 'dateOfBirth')):
                        attrList.append({'DATE_OF_BIRTH': formatDate(getValue(subRecord, 'dateOfBirth'))})
                        updateStat('DATE_OF_BIRTH', len(getValue(subRecord, 'dateOfBirth')), getValue(subRecord, 'dateOfBirth'))

            for subRecord in sdnEntry.findall('placeOfBirthList/placeOfBirthItem'):
                if getValue(subRecord, 'placeOfBirth'):
                    countryName = getValue(subRecord, 'placeOfBirth')
                    attrList.append({'PLACE_OF_BIRTH': countryName})
                    updateStat('ATTRIBUTE', 'PLACE_OF_BIRTH', countryName)
                    if countryName.lower() in isoCountries: #--also map the code for matching
                        isoCountryList.append(isoCountries[countryName.lower()])
                    elif ',' in countryName: #--check after possible city
                        countryName1 = countryName[countryName.find(',')+1:].strip()
                        if countryName1.lower() in isoCountries: #--also map the code for matching
                            isoCountryList.append(isoCountries[countryName1.lower()])
                        else:
                            countryName1 = countryName[countryName.rfind(',')+1:].strip()
                            if countryName1.lower() in isoCountries: #--also map the code for matching
                                isoCountryList.append(isoCountries[countryName1.lower()])

            for subRecord in sdnEntry.findall('nationalityList/nationality'):
                if getValue(subRecord, 'country'):
                    attrList.append({'NATIONALITY': getValue(subRecord, 'country')})
                    updateStat('ATTRIBUTE', 'NATIONALITY', getValue(subRecord, 'country'))
                    if getValue(subRecord, 'country').lower() in isoCountries: #--also map the code for matching
                        isoCountryList.append(isoCountries[getValue(subRecord, 'country').lower()])

            for subRecord in sdnEntry.findall('citizenshipList/citizenship'):
                if getValue(subRecord, 'country'):
                    attrList.append({'CITIZENSHIP': getValue(subRecord, 'country')})
                    updateStat('ATTRIBUTE', 'CITIZENSHIP', getValue(subRecord, 'country'))
                    if getValue(subRecord, 'country').lower() in isoCountries: #--also map the code for matching
                        isoCountryList.append(isoCountries[getValue(subRecord, 'country').lower()])

            if attrList:
                jsonData['ATTR_LIST'] = attrList

            #--add any addresses
            addrList = []
            for subRecord in sdnEntry.findall('addressList/address'):
                addrDict ={}
                if getValue(subRecord, 'address1') and getValue(subRecord, 'address1') != 'Address Unknown':
                    addrDict['ADDR_LINE1'] = getValue(subRecord, 'address1')
                if getValue(subRecord, 'address2'):
                    addrDict['ADDR_LINE2'] = getValue(subRecord, 'address2')
                if getValue(subRecord, 'address3'):
                    addrDict['ADDR_LINE3'] = getValue(subRecord, 'address3')
                if getValue(subRecord, 'city'):
                    addrDict['ADDR_CITY'] = getValue(subRecord, 'city')
                if getValue(subRecord, 'stateOrProvince'):
                    addrDict['ADDR_STATE'] = getValue(subRecord, 'stateOrProvince')
                if getValue(subRecord, 'postalCode'):
                    addrDict['ADDR_POSTAL_CODE'] = getValue(subRecord, 'postalCode')
                if getValue(subRecord, 'country'):
                    addrDict['ADDR_COUNTRY'] = getValue(subRecord, 'country')
                if addrDict:
                    addrList.append(addrDict)
                    if len(addrDict) == 1 and list(addrDict.keys())[0] == 'ADDR_COUNTRY':
                        updateStat('ADDRESS', 'country only')
                    else:
                        updateStat('ADDRESS', 'UNTYPED')
                    if 'ADDR_COUNTRY' in addrDict and addrDict['ADDR_COUNTRY'].lower() in isoCountries: #--also map the code for matching
                        isoCountryList.append(isoCountries[addrDict['ADDR_COUNTRY'].lower()])
            if addrList:
                jsonData['ADDR_LIST'] = addrList

            #nationalIdTypes = 
            #taxidTypes = 
            #leiNumberTypes = 

            #--add any ID numbers
            itemNum = 0
            idList = []
            for subRecord in sdnEntry.findall('idList/id'):
                if getValue(subRecord, 'idNumber'):
                    idData = {}
                    idType = getValue(subRecord, 'idType')
                    idNumber = getValue(subRecord, 'idNumber')
                    idCountry = getValue(subRecord, 'idCountry')
                    if not idCountry:
                        idCountry = ''

                    #--try to standardize the country
                    isoCountry = ''
                    if idCountry and idCountry.lower() in isoCountries: #--also map the code for matching
                        isoCountry = isoCountries[idCountry.lower()]
                        isoCountryList.append(isoCountry)

                    #--check state file if not found and a drivers license
                    if idCountry and (isoCountry in ('US', 'USA') or not isoCountry) and 'DRIVER' in idType.upper() and idCountry.lower() in isoStates:
                        isoCountry = isoStates[idCountry.lower()]

                    #--key word assignments
                    idTypeUpper = idType.upper()
                    if 'SSN' in idTypeUpper:
                        g2idType = 'SSN_NUMBER'
                        idData['SSN_NUMBER'] = idNumber

                    elif 'DRIVER' in idTypeUpper:
                        g2idType = 'DRIVERS_LICENSE_NUMBER'
                        idData['DRIVERS_LICENSE_NUMBER'] = idNumber
                        idData['DRIVERS_LICENSE_STATE'] = isoCountry

                    elif 'PASSPORT' in idTypeUpper:
                        g2idType = 'PASSPORT_NUMBER'
                        idData['PASSPORT_NUMBER'] = idNumber
                        idData['PASSPORT_COUNTRY'] = isoCountry

                    elif any(idTypeUpper.startswith(expression) for expression in ['NATIONAL ID', 'CEDULA', 'IDENTIFICATION NUMBER', 'NATIONAL FOREIGN ID NUMBER', 'D.N.I.', 'KENYAN ID NO.']) or 'PERSONAL ID' in idTypeUpper: 
                        g2idType = 'NATIONAL_ID_NUMBER'
                        idData['NATIONAL_ID_NUMBER'] = idNumber
                        idData['NATIONAL_ID_COUNTRY'] = isoCountry

                    #--entities stuff
                    elif any(idTypeUpper.startswith(expression) for expression in ['TAX ID NO.', 'NIT', 'RUC', 'RIF', 'RFC', 'R.F.C']) or any(expression in idTypeUpper for expression in ['FEIN', ' TAX ']): 
                        g2idType = 'TAX_ID_NUMBER'
                        idData['TAX_ID_NUMBER'] = idNumber
                        idData['TAX_ID_COUNTRY'] = isoCountry

                    elif any(idTypeUpper.startswith(expression) for expression in ['LEGAL ENTITY NUMBER', 'COMMERCIAL REGISTRY NUMBER', 'BUSINESS REGISTRATION', 'COMPANY NUMBER', 'BUSINESS NUMBER', 'PUBLIC REGISTRATION NUMBER', 'REGISTRATION NUMBER', 'REGISTRATION ID', 'TRADE LICENSE']):
                        g2idType = 'LEI_NUMBER'
                        idData['LEI_NUMBER'] = idNumber
                        idData['LEI_COUNTRY'] = isoCountry

                    elif idTypeUpper == 'D-U-N-S NUMBER':
                        g2idType = 'DUNS_NUMBER'
                        idData['DUNS_NUMBER'] = idNumber

                    elif idTypeUpper == 'MSB REGISTRATION NUMBER':
                        g2idType = 'MSB_LICENSE_NUMBER'
                        idData['MSB_LICENSE_NUMBER'] = idNumber
                            
                    #--vessel stuff
                    elif idTypeUpper == 'VESSEL REGISTRATION IDENTIFICATION':
                        g2idType = 'IMO_NUMBER'
                        idData['IMO_NUMBER'] = idNumber.replace('IMO ','')
                    elif idTypeUpper == 'MMSI':
                        g2idType = 'MMSI_NUMBER_NUMBER'
                        idData['MMSI_NUMBER_NUMBER'] = idNumber
                    elif idTypeUpper == 'OTHER VESSEL CALL SIGN':
                        g2idType = 'CALL_SIGN'
                        idData['CALL_SIGN'] = idNumber

                    #--aircraft stuff
                    elif idTypeUpper.startswith('AIRCRAFT CONSTRUCTION NUMBER'):
                        g2idType = 'AIRCRAFT_CONSTRUCTION_NUM'
                        idData['AIRCRAFT_CONSTRUCTION_NUM'] = idNumber
                    elif idTypeUpper.startswith("AIRCRAFT MANUFACTURER'S SERIAL NUMBER"):
                        g2idType = 'AIRCRAFT_MFG_SERIAL_NUM'
                        idData['AIRCRAFT_MFG_SERIAL_NUM'] = idNumber
                    elif any(idTypeUpper.startswith(expression) for expression in ['AIRCRAFT TAIL NUMBER', 'PREVIOUS AIRCRAFT TAIL NUMBER']):
                        g2idType = 'AIRCRAFT_TAIL_NUM'
                        idData['AIRCRAFT_TAIL_NUM'] = idNumber
                    elif idTypeUpper.startswith('AIRCRAFT MODEL'):
                        g2idType = 'AIRCRAFT_TAIL_NUM'
                        #--not an ID, called out here to prevent it becoming an other_id
                    elif idTypeUpper.startswith('AIRCRAFT MANUFACTURE DATE'):
                        g2idType = 'REGISTRATION_DATE'
                        #--note: this is not an id! ()


                    #--other data hidden in ID section
                    elif idTypeUpper == 'WEBSITE':
                        g2idType = 'WEBSITE_ADDRESS'
                        idData['WEBSITE_ADDRESS'] = idNumber
                    elif idTypeUpper == 'EMAIL ADDRESS':
                        g2idType = 'EMAIL_ADDRESS'
                        idData['EMAIL_ADDRESS'] = idNumber
                    elif idTypeUpper == 'PHONE NUMBER':
                        g2idType = 'PHONE_NUMBER'
                        idData['PHONE_NUMBER'] = idNumber
                    elif idTypeUpper == 'GENDER':
                        g2idType = 'GENDER'
                        idData['GENDER'] = idNumber

                    #--everything else from any entity type
                    else:

                        #--its an id number if meets the following criteria
                        if len(idNumber) >= 5 and len(idNumber) <= 20 and any(char.isdigit() for char in idNumber):
                            g2idType = 'OTHER_ID_NUMBER'
                            idData['OTHER_ID_TYPE'] = idType
                            idData['OTHER_ID_NUMBER'] = idNumber
                            idData['OTHER_ID_COUNTRY'] = isoCountry

                        #--some value that probabaly not an ID (does not assign idData!)
                        else:
                            itemNum += 1
                            jsonData['ID%s' % itemNum] = '%s %s %s' % (idType, idNumber, idCountry)
                            g2idType = 'UNKNOWN_ID'

                    updateStat(g2EntityType, g2idType + ': ' + idType + ' (' + isoCountry + ')', idNumber + '  (' + idCountry + ')')
                    if idData:
                        idList.append(idData)


            if idList:
                jsonData['ID_LIST'] = idList

            #--still some vessel info in this structure
            if g2EntityType == 'VESSEL':
                if getValue(sdnEntry, 'vesselInfo/callSign'):
                    jsonData['CALL_SIGN'] = getValue(sdnEntry, 'vesselInfo/callSign')
                    updateStat('VESSEL', 'CALL_SIGN', getValue(sdnEntry, 'vesselInfo/callSign'))
                if getValue(sdnEntry, 'vesselInfo/vesselType'):
                    jsonData['vesselType'] = getValue(sdnEntry, 'vesselInfo/vesselType')
                    updateStat('VESSEL', 'vesselType', getValue(sdnEntry, 'vesselInfo/vesselType'))
                if getValue(sdnEntry, 'vesselInfo/vesselFlag'):
                    jsonData['vesselFlag'] = getValue(sdnEntry, 'vesselInfo/vesselFlag')
                    updateStat('VESSEL', 'vesselFlag', getValue(sdnEntry, 'vesselInfo/vesselFlag'))
                if getValue(sdnEntry, 'vesselInfo/vesselOwner'):
                    jsonData['vesselOwner'] = getValue(sdnEntry, 'vesselInfo/vesselOwner')
                    updateStat('VESSEL', 'vesselOwner', getValue(sdnEntry, 'vesselInfo/vesselOwner'))
                if getValue(sdnEntry, 'vesselInfo/tonnage'):
                    jsonData['tonnage'] = getValue(sdnEntry, 'vesselInfo/tonnage')
                    updateStat('VESSEL', 'tonnage', getValue(sdnEntry, 'vesselInfo/tonnage'))
                if getValue(sdnEntry, 'vesselInfo/grossRegisteredTonnage'):
                    jsonData['grossRegisteredTonnage'] = getValue(sdnEntry, 'vesselInfo/grossRegisteredTonnage')
                    updateStat('VESSEL', 'grossRegisteredTonnage', getValue(sdnEntry, 'vesselInfo/grossRegisteredTonnage'))
                    
            #--as of 2.0 country of association can be cconfigured to be computed automatically for all data sources!
            if False: 
                #--add all the country codes found 
                subList = []
                for cntryCode in set(isoCountryList):
                    subList.append({'COUNTRY_CODE': cntryCode})
                    updateStat('ATTRIBUTE','COUNTRY_OF_ASSOCIATION')
                if subList:
                    jsonData['ISO_COUNTRY_CODES'] = subList

        jsonStr = json.dumps(jsonData)
        try: outputHandle.write(jsonStr + '\n')
        except IOError as err:
            print('')
            print('ERROR: could not write to json file')
            print(err)
            print('')
            appError = 1
            break
            
    outputHandle.close()
    print('')
    print('%s records written, done!' % rowCnt)
    print('')

    if statisticsFile: 
        with open(statisticsFile, 'w') as outfile:
            json.dump(statPack, outfile, indent=4, sort_keys = True)    
        print('Mapping stats written to %s' % statisticsFile)
        print('')

    return 0

#----------------------------------------
if __name__ == "__main__":
    appPath = os.path.dirname(os.path.abspath(sys.argv[0]))

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-i', '--inputFile', dest='inputFile', type=str, default=None, help='an sdn.xml file downloaded from https://www.treasury.gov/ofac/downloads.')
    argparser.add_argument('-o', '--outputFile', dest='outputFile', type=str, help='output filename, defaults to input file name with a .json extension.')
    argparser.add_argument('-a', '--includeAll', dest='includeAll', action='store_true', default=False, help='convert all entity types including vessels and aircraft.')
    #argparser.add_argument('-c', '--isoCountrySize', dest='isoCountrySize', type=int, default=3, help='ISO country code size. Either 2 or 3, default=3.')
    argparser.add_argument('-s', '--statisticsFile', dest='statisticsFile', type=str, help='optional statistics filename in json format.')
    args = argparser.parse_args()
    inputFile = args.inputFile
    outputFile = args.outputFile
    includeAll = args.includeAll
    isoCountrySize = 3 #--args.isoCountrySize #--3 is a better standard for country so as not to be confused with 2 digit state codes 
    statisticsFile = args.statisticsFile

    if not (inputFile):
        print('')
        print('Please supply an input file name with the -i parameter.')
        print('')
        sys.exit(1)

    #--default the output file if not supplied
    if not (outputFile):
        outputFile = inputFile + '.json'
    
    #--need conversion table for country codes
    if isoCountrySize == 3:
        isoCountryFile = 'isoCountries3.json'
    elif isoCountrySize == 2:
        isoCountryFile = 'isoCountries2.json'
    else:
        print('')
        print('The ISO Country size must be 2 or 3.')
        print('')
        sys.exit(1)

    isoCountryFile = appPath + os.path.sep + isoCountryFile
    if not os.path.exists(isoCountryFile):
        print('')
        print('File %s is missing!' % (isoCountryFile))
        print('')
        sys.exit(1)
    try: isoCountries = json.load(open(isoCountryFile,'r'))
    except json.decoder.JSONDecodeError as err:
        print('')
        print('JSON error %s in %s' % (err, isoCountryFile))
        print('')
        sys.exit(1)

    #--need conversion table for country codes
    isoStatesFile = appPath + os.path.sep + 'isoStates.json'
    if not os.path.exists(isoStatesFile):
        print('')
        print('File %s is missing!' % (isoCountriesFile))
        print('')
        sys.exit(1)
    try: isoStates = json.load(open(isoStatesFile,'r'))
    except json.decoder.JSONDecodeError as err:
        print('')
        print('JSON error %s in %s' % (err, isoStatesFile))
        print('')
        sys.exit(1)

    statPack = {}

    result = processFile(inputFile, outputFile, includeAll)

    sys.exit(result)
   
