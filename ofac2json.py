import os
import sys
import argparse
try: import urllib.request as urllib #--python3
except: import urllib #--python27
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
def formatDate(inStr):
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
        try: outStr = datetime.strftime(datetime.strptime(inStr, format), '%Y-%m-%d')
        except: pass
        else: 
            break

    return outStr

#----------------------------------------
def processFile(inputFile, outputFile, includeAll):
    """ convert the ofac sdn xml file to json for senzing  """

    print('Reading from: %s ...' % inputFile)

    #--read the file into memory
    if inputFile.upper().startswith('HTTP'):
        try: f = urllib.urlopen(inputFile)
        except:
            print('could not open %s!' % inputFile)
            return -1
    else:
        try: 
            f = open(inputFile)
        except IOError as err:
            print(err)
            print('could not open %s!' % inputFile)
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
        print('XML Error: %s' % err)
        return -1
    except:
        print('%s is not a valid XML file!' % inputFile)
        return -1
    
    #--add the publish date to the file name if they left the default
    publishDate = getValue(xmlRoot, 'publshInformation/Publish_Date')
    print('Publish Date: %s' % publishDate)
    if outputFile == 'ofac.json':
        outputFile = 'ofac-%s.json' % formatDate(publishDate)
    
    #--open output file
    print('writing to %s ...' % outputFile)
    if sys.version[0] == '2':
        outputHandle = open(outputFile, "w")
    else:
        outputHandle = open(outputFile, "w", encoding='utf-8', newline='')

    #--for each sdn entry record
    rowCnt = 0
    for sdnEntry in xmlRoot.findall('sdnEntry'):
        rowCnt += 1 
        
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

            #--note: attributes used for resolution must be upper case
            
            jsonData = {}
            jsonData['DATA_SOURCE'] = 'OFAC'
            jsonData['ENTITY_TYPE'] = g2EntityType
            jsonData['RECORD_ID'] = getValue(sdnEntry, 'uid')
            jsonData['publishDate'] = publishDate
            if getValue(sdnEntry, 'title'):
                jsonData['sdnTitle'] = getValue(sdnEntry, 'title')
            if getValue(sdnEntry, 'remarks'):
                jsonData['sdnRemarks'] = getValue(sdnEntry, 'remarks')
                
            #--add the SDN programs (usually only one)
            programList = None
            for programRecord in sdnEntry.findall('programList'):
                if getValue(programRecord, 'program'):
                    if not programList:
                        programList = getValue(programRecord, 'program')
                    else:    
                        programList = programList + ', ' + getValue(programRecord, 'program')
            if programList:
                jsonData['sdnProgram'] = programList

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
            #--add any DOBs (note: sublists must be dictionaries even if only a single field)
            for subRecord in sdnEntry.findall('dateOfBirthList/dateOfBirthItem'):
                if getValue(subRecord, 'dateOfBirth'):
                    attrList.append({'DATE_OF_BIRTH': formatDate(getValue(subRecord, 'dateOfBirth'))})
            for subRecord in sdnEntry.findall('placeOfBirthList/placeOfBirthItem'):
                if getValue(subRecord, 'placeOfBirth'):
                    attrList.append({'PLACE_OF_BIRTH': formatDate(getValue(subRecord, 'placeOfBirth'))})
            for subRecord in sdnEntry.findall('nationalityList/nationality'):
                if getValue(subRecord, 'country'):
                    attrList.append({'NATIONALITY': formatDate(getValue(subRecord, 'country'))})
            for subRecord in sdnEntry.findall('citizenshipList/citizenship'):
                if getValue(subRecord, 'country'):
                    attrList.append({'CITIZENSHIP': formatDate(getValue(subRecord, 'country'))})
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
            otherList = []
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
                        #rowData['NATIONAL_ID_TYPE'] = getValue(subRecord, 'idType')
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
                        otherList.append({getValue(subRecord, 'idType'): getValue(subRecord, 'idNumber')})
                    
                    if idData:
                        idList.append(idData)
            if idList:
                jsonData['ID_LIST'] = idList
            if otherList:
                jsonData['OTHER_LIST'] = otherList
                
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

    inputFile = 'http://www.treasury.gov/ofac/downloads/sdn.xml'
    outputFile = 'ofac.json'
    includeAll = True #--set to false if you only want entities and individuals. if true will map vessels and aircraft as well    

    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser()
        parser.add_argument('-i', type=str, default=inputFile, help='ofac xml file such as sdn.xml or the url.  default is ' + inputFile)
        parser.add_argument('-o', type=str, default=outputFile, help='output filename. default is ofac-yyyy-mm-dd.json based on the publish date')
        args = parser.parse_args()
        inputFile = args.i
        outputFile = args.o

    result = processFile(inputFile, outputFile, includeAll)
    
    sys.exit(result)
   
