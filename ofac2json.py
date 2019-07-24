#! /usr/bin/env python3

import os
import sys
import argparse
import urllib.request as urllib
import xml.etree.ElementTree as etree
from datetime import datetime
import json

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
def processFile(inputFile, outputFile, includeAll):
    """ convert the ofac sdn xml file to json for senzing  """

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
    
    #--add the publish date to the file name if they left the default
    defaultPath = os.path.dirname(os.path.abspath(inputFile))
    publishDate = getValue(xmlRoot, 'publshInformation/Publish_Date')
    print('Publish Date: %s' % publishDate)
    if outputFile == 'ofac.json': #--the default
        outputFile = defaultPath + os.path.sep + 'ofac-%s.json' % formatDate(publishDate)
    
    #--open output file
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
            rowCnt += 1 
        
            #--note: attributes used for resolution must be upper case
            
            jsonData = {}
            jsonData['DATA_SOURCE'] = 'OFAC'
            jsonData['ENTITY_TYPE'] = g2EntityType
            jsonData['RECORD_TYPE'] = g2EntityType
            jsonData['RECORD_ID'] = getValue(sdnEntry, 'uid')
            jsonData['OFAC_ID'] = getValue(sdnEntry, 'uid')
            jsonData['PUBLISH_DATE'] = publishDate
            if getValue(sdnEntry, 'title'):
                jsonData['SDN_TITLE'] = getValue(sdnEntry, 'title')
            if getValue(sdnEntry, 'remarks'):
                jsonData['SDN_REMARKS'] = getValue(sdnEntry, 'remarks')
                
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
            if nameList:
                jsonData['NAME_LIST'] = nameList

            #attributes
            attrList = []
            yobList = []
            countryList = []
            #--add any DOBs (note: sublists must be dictionaries even if only a single field)
            for subRecord in sdnEntry.findall('dateOfBirthList/dateOfBirthItem'):
                if getValue(subRecord, 'dateOfBirth'):
                    if formatDate(getValue(subRecord, 'dateOfBirth')):
                        attrList.append({'DATE_OF_BIRTH': formatDate(getValue(subRecord, 'dateOfBirth'))})
                        attrList.append({'YEAR_OF_BIRTH': formatDate(getValue(subRecord, 'dateOfBirth'), '%Y')})
                        yobList.append(formatDate(getValue(subRecord, 'dateOfBirth'), '%Y'))

            for subRecord in sdnEntry.findall('placeOfBirthList/placeOfBirthItem'):
                if getValue(subRecord, 'placeOfBirth'):
                    attrList.append({'PLACE_OF_BIRTH': getValue(subRecord, 'placeOfBirth')})
                    if getValue(subRecord, 'placeOfBirth').upper() in isoCountry: #--also map the code for matching
                        attrList.append({'POB_COUNTRY': isoCountry[getValue(subRecord, 'placeOfBirth').upper()]})
                        countryList.append(isoCountry[getValue(subRecord, 'placeOfBirth').upper()])

            for subRecord in sdnEntry.findall('nationalityList/nationality'):
                if getValue(subRecord, 'country'):
                    attrList.append({'NATIONALITY': getValue(subRecord, 'country')})
                    if getValue(subRecord, 'country').upper() in isoCountry: #--also map the code for matching
                        attrList.append({'NATIONALITY_COUNTRY': isoCountry[getValue(subRecord, 'country').upper()]})
                        countryList.append(isoCountry[getValue(subRecord, 'country').upper()])

            for subRecord in sdnEntry.findall('citizenshipList/citizenship'):
                if getValue(subRecord, 'country'):
                    attrList.append({'CITIZENSHIP': getValue(subRecord, 'country')})
                    if getValue(subRecord, 'country').upper() in isoCountry: #--also map the code for matching
                        attrList.append({'CITIZENSHIP_COUNTRY': isoCountry[getValue(subRecord, 'country').upper()]})
                        countryList.append(isoCountry[getValue(subRecord, 'country').upper()])

            if attrList:
                jsonData['ATTR_LIST'] = attrList

            #--add any addresses
            addrList = []
            for subRecord in sdnEntry.findall('addressList/address'):
                addrDict ={}
                if getValue(subRecord, 'address1'):
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

            if addrList:
                jsonData['ADDR_LIST'] = addrList

            #--add any ID numbers
            otherDict = {}
            idList = []
            for subRecord in sdnEntry.findall('idList/id'):
                if getValue(subRecord, 'idNumber'):
                    idData = {}
                    
                    #--Entities and Individuals
                    if 'SSN' in getValue(subRecord, 'idType').upper():
                        idData['SSN_NUMBER'] = getValue(subRecord, 'idNumber')

                    elif 'DRIVER' in getValue(subRecord, 'idType').upper():
                        idData['DRIVERS_LICENSE_NUMBER'] = getValue(subRecord, 'idNumber')
                        if getValue(subRecord, 'idCountry'):
                            idData['DRIVERS_LICENSE_STATE'] = getValue(subRecord, 'idCountry')

                    elif 'PASSPORT' in getValue(subRecord, 'idType').upper():
                        idData['PASSPORT_NUMBER'] = getValue(subRecord, 'idNumber')
                        if getValue(subRecord, 'idCountry'):
                            idData['PASSPORT_COUNTRY'] = getValue(subRecord, 'idCountry')
                            
                    elif g2EntityType in ('PERSON','ORGANIZATION') and getValue(subRecord, 'idCountry'): #--removes some of the garbage values (if it wasn't issued by a country its just free text or gender
                        #--idData['NATIONAL_ID_TYPE'] = getValue(subRecord, 'idType')
                        idData['NATIONAL_ID_NUMBER'] = getValue(subRecord, 'idNumber')
                        if getValue(subRecord, 'idCountry'):
                            idData['NATIONAL_ID_COUNTRY'] = getValue(subRecord, 'idCountry')

                    #--vessel stuff
                    elif getValue(subRecord, 'idType') == 'Vessel Registration Identification':
                        idData['IMO_NUMBER'] = getValue(subRecord, 'idNumber').replace('IMO ','')
                    elif getValue(subRecord, 'idType') == 'MMSI':
                        idData['MMSI_NUMBER_NUMBER'] = getValue(subRecord, 'idNumber').replace('IMO ','')
                    elif getValue(subRecord, 'idType') == "Other Vessel Call Sign":
                        idData['CALL_SIGN'] = getValue(subRecord, 'idNumber')

                    #--aircraft stuff
                    elif getValue(subRecord, 'idType') == 'Aircraft Construction Number (also called L/N or S/N or F/N)':
                        idData['AIRCRAFT_CONSTRUCTION_NUM'] = getValue(subRecord, 'idNumber')
                    elif getValue(subRecord, 'idType') == "Aircraft Manufacturer's Serial Number (MSN)":
                        idData['AIRCRAFT_MFG_SERIAL_NUM'] = getValue(subRecord, 'idNumber')
                    elif getValue(subRecord, 'idType') == "Aircraft Tail Number":
                        idData['AIRCRAFT_TAIL_NUM'] = getValue(subRecord, 'idNumber')

                    #--everything else from any entity type
                    else:
                        if getValue(subRecord, 'idType') not in otherDict:
                            otherDict[getValue(subRecord, 'idType')] = []
                        otherDict[getValue(subRecord, 'idType')].append(getValue(subRecord, 'idNumber'))
                    
                    if idData:
                        idList.append(idData)
            if idList:
                jsonData['ID_LIST'] = idList
            if otherDict:
                for attr in otherDict:
                    jsonData[attr] = ' | '.join(otherDict[attr])
                
            #--still some vessel info in this structure
            if g2EntityType == 'VESSEL':
                if getValue(sdnEntry, 'vesselInfo/callSign'):
                    jsonData['CALL_SIGN'] = getValue(sdnEntry, 'vesselInfo/callSign')
                if getValue(sdnEntry, 'vesselInfo/vesselType'):
                    jsonData['vesselType'] = getValue(sdnEntry, 'vesselInfo/vesselType')
                if getValue(sdnEntry, 'vesselInfo/vesselFlag'):
                    jsonData['vesselFlag'] = getValue(sdnEntry, 'vesselInfo/vesselFlag')
                if getValue(sdnEntry, 'vesselInfo/vesselOwner'):
                    jsonData['vesselOwner'] = getValue(sdnEntry, 'vesselInfo/vesselOwner')
                if getValue(sdnEntry, 'vesselInfo/tonnage'):
                    jsonData['tonnage'] = getValue(sdnEntry, 'vesselInfo/tonnage')
                if getValue(sdnEntry, 'vesselInfo/grossRegisteredTonnage'):
                    jsonData['grossRegisteredTonnage'] = getValue(sdnEntry, 'vesselInfo/grossRegisteredTonnage')
                    
        jsonStr = json.dumps(jsonData)
        try: outputHandle.write(jsonStr + '\n')
        except IOError as err:
            print('ERROR: could not write to json file')
            print(err)
            appError = 1
            break
            
    outputHandle.close()

    print('%s records written, done!' % rowCnt)
    print('')

    return 0

#----------------------------------------
if __name__ == "__main__":
    appPath = os.path.dirname(os.path.abspath(sys.argv[0]))

    outputFile = 'ofac.json'

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-i', '--inputFile', dest='inputFile', type=str, default=None, help='an sdn.xml file downloaded from https://www.treasury.gov/ofac/downloads.')
    argparser.add_argument('-o', '--outputFile', dest='outputFile', type=str, default=outputFile, help='output filename. default is ofac-yyyy-mm-dd.json based on the publish date')
    argparser.add_argument('-a', '--includeAll', dest='includeAll', action='store_true', default=False, help='convert all entity types including vessels and aircraft')

    args = argparser.parse_args()
    inputFile = args.inputFile
    outputFile = args.outputFile
    includeAll = args.includeAll

    if not (inputFile):
        print('')
        print('Please supply an input file name with the -i parameter.')
        print('')
        sys.exit(1)

    #--need conversion table for country codes
    isoCountriesFile = appPath + os.path.sep + 'isoCountries.json'
    if not os.path.exists(isoCountriesFile):
        print('')
        print('File %s is missing!' % (isoCountriesFile))
        print('')
        sys.exit(1)
    try: isoCountry = json.load(open(isoCountriesFile,'r'))
    except json.decoder.JSONDecodeError as err:
        print('')
        print('JSON error %s in %s' % (err, isoCountriesFile))
        print('')
        sys.exit(1)

    result = processFile(inputFile, outputFile, includeAll)
    
    sys.exit(result)
   
