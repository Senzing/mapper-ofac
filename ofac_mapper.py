#! /usr/bin/env python3

import os
import sys
import argparse
import xml.etree.ElementTree as etree
from datetime import datetime
import csv
import json
import random


#----------------------------------------
def getValue (segment, tagName):
    """ get an xml element text value """
    try: 
        value = segment.find(tagName).text.strip()
    except: 
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
def load_codes_file(codes_filename):
    code_conversion_data = {}
    unmapped_code_count = 0
    with open(codes_filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['RAW_TYPE'] = row['RAW_TYPE']
            row['RAW_CODE'] = row['RAW_CODE']
            if row['RAW_TYPE'] not in code_conversion_data:
                code_conversion_data[row['RAW_TYPE']] = {}
            row['COUNT'] = 0
            row['EXAMPLES'] = {}
            code_conversion_data[row['RAW_TYPE']][row['RAW_CODE']] = row
            if row['REVIEWED'].upper() != 'Y':
                unmapped_code_count += 1
    return code_conversion_data, unmapped_code_count

#----------------------------------------
def save_codes_file(codes_filename):
    headers = ['REVIEWED', 'RAW_TYPE', 'RAW_CODE', 'RAW_MODIFIER', 'SENZING_ATTR', 'SENZING_DEFAULT', 'RECORD_COUNT',
               'UNIQUE_COUNT', 'UNIQUE_PERCENT', 'TOP1', 'TOP2', 'TOP3', 'TOP4', 'TOP5', 'TOP6', 'TOP7', 'TOP8', 'TOP9', 'TOP10']

    with open(codes_filename, 'w', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for raw_type in sorted(code_conversion_data.keys()):
            for raw_code in sorted(code_conversion_data[raw_type].keys()):
                code_data = code_conversion_data[raw_type][raw_code]
                uniq_record_count = 0
                uniq_value_count = len(code_data['EXAMPLES'])
                topValues = []
                for value in sorted(code_data['EXAMPLES'].items(), key=lambda x: x[1], reverse=True):
                    if value[0] != 'null':
                        uniq_record_count += value[1]
                        if len(topValues) < 10:
                            topValues.append(f'{value[0]} ({value[1]})')
                while len(topValues) < 10:
                    topValues.append('')

                code_record = [code_data['REVIEWED'],
                               code_data['RAW_TYPE'],
                               code_data['RAW_CODE'],
                               code_data['RAW_MODIFIER'],
                               code_data['SENZING_ATTR'],
                               code_data['SENZING_DEFAULT'],
                               uniq_record_count,
                               uniq_value_count,
                               round(float(uniq_value_count)/uniq_record_count*100,2) if uniq_record_count else 0,
                               topValues[0],
                               topValues[1],
                               topValues[2],
                               topValues[3],
                               topValues[4],
                               topValues[5],
                               topValues[6],
                               topValues[7],
                               topValues[8],
                               topValues[9]]
                writer.writerow(code_record)

#----------------------------------------
def update_code_stats(raw_type, raw_code, example_value=None, **kwargs):
    if raw_type not in code_conversion_data:
        code_conversion_data[raw_type] = {}
    if raw_code not in code_conversion_data[raw_type]:
        code_conversion_data[raw_type][raw_code] = {'REVIEWED': 'N',
                                                    'RAW_TYPE': raw_type,
                                                    'RAW_CODE': raw_code,
                                                    'RAW_MODIFIER': '',
                                                    'SENZING_ATTR': kwargs.get('senzing_attr', ''),
                                                    'SENZING_DEFAULT': kwargs.get('senzing_default', ''),
                                                    'COUNT': 0,
                                                    'EXAMPLES': {}}

    code_conversion_data[raw_type][raw_code]['COUNT'] += 1
    if example_value:
        if example_value in code_conversion_data[raw_type][raw_code]['EXAMPLES']:
            code_conversion_data[raw_type][raw_code]['EXAMPLES'][example_value] += 1
        elif len(code_conversion_data[raw_type][raw_code]['EXAMPLES']) < 1000000:
            code_conversion_data[raw_type][raw_code]['EXAMPLES'][example_value] = 1

#----------------------------------------
def capture_mapped_stats(json_data):
    record_type = json_data.get('RECORD_TYPE', 'UNKNOWN_RECORD_TYPE')
    for key1 in json_data:
        if type(json_data[key1]) != list:
            updateStat(record_type, key1, json_data[key1])
        else:
            for subrecord in json_data[key1]:
                for key2 in subrecord:
                    updateStat(record_type, key2, subrecord[key2])


#----------------------------------------
def remove_empty_tags(d):
    if isinstance(d, dict):
        for  k, v in list(d.items()):
            if v is None or len(str(v).strip()) == 0:
                del d[k]
            else:
                remove_empty_tags(v)
    if isinstance(d, list):
        for v in d:
            remove_empty_tags(v)
    return d


#----------------------------------------
def processFile():
    """ convert the ofac sdn xml file to json for senzing  """

    print(f'\nReading from: {inputFile} ...')

    #--read the file into memory
    try: f = open(inputFile)
    except IOError as err:
        print(f'\ncould not open {inputFile}: {err}\n')
        return -1

    xmlDoc = f.read()
    f.close()
    if type(xmlDoc) != str:
        xmlDoc = xmlDoc.decode('utf-8')
    
    #--name spaces not needed and can mess up etree if not accessible
    startPos = xmlDoc.find(' xmlns:')
    while startPos > 0:
        xmlDoc = xmlDoc[0:startPos] + xmlDoc[xmlDoc.find('>',startPos):]
        startPos = xmlDoc.find(' xmlns:')

    #--try to parse
    try: xmlRoot = etree.fromstring(xmlDoc)
    except etree.ParseError as err:
        print(f'\nXML Error: {err}\n')
        return -1
    except:
        print(f'\n{inputFile} is not a valid XML file!\n')
        return -1
    publishDate = getValue(xmlRoot, 'publshInformation/Publish_Date')
    
    #--open output file
    print(f'\nwriting to {outputFile} ...')
    try: outputHandle = open(outputFile, "w", encoding='utf-8', newline='')
    except IOError as err:
        print(f'\ncould not open {outputFile}, {err}\n')
        return -1

    #--for each sdn entry record
    rowCnt = 0
    for sdnEntry in xmlRoot.findall('sdnEntry'):

        #--filter for only entities and individuals unless they want to include all
        g2RecordType = None
        if getValue(sdnEntry, 'sdnType') in ('Entity', 'Individual'):
            if getValue(sdnEntry, 'sdnType') == 'Entity':
                g2RecordType = 'ORGANIZATION'
            elif getValue(sdnEntry, 'sdnType') == 'Individual':
                g2RecordType = 'PERSON'
            elif getValue(sdnEntry, 'sdnType') == 'Vessel':
                g2RecordType = 'VESSEL'
            elif getValue(sdnEntry, 'sdnType') == 'Aircraft':
                g2RecordType = 'AIRCRAFT'
            else:
                updateStat('!UNKNOWN_RECORD_TYPE', getValue(sdnEntry, 'sdnType'))

        if g2RecordType:
            updateStat('!RECORD_TYPE', g2RecordType)
            rowCnt += 1 
        
            jsonData = {}
            jsonData['DATA_SOURCE'] = 'OFAC'
            jsonData['RECORD_TYPE'] = g2RecordType
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

            #--add any attributes (note: sublists must be dictionaries even if only a single field)
            attrList = []
            for subRecord in sdnEntry.findall('dateOfBirthList/dateOfBirthItem'):
                if getValue(subRecord, 'dateOfBirth'):
                    if formatDate(getValue(subRecord, 'dateOfBirth')):
                        attrList.append({'DATE_OF_BIRTH': formatDate(getValue(subRecord, 'dateOfBirth'))})

            for subRecord in sdnEntry.findall('placeOfBirthList/placeOfBirthItem'):
                if getValue(subRecord, 'placeOfBirth'):
                    countryName = getValue(subRecord, 'placeOfBirth')
                    attrList.append({'PLACE_OF_BIRTH': countryName})

            for subRecord in sdnEntry.findall('nationalityList/nationality'):
                if getValue(subRecord, 'country'):
                    attrList.append({'NATIONALITY': getValue(subRecord, 'country')})

            for subRecord in sdnEntry.findall('citizenshipList/citizenship'):
                if getValue(subRecord, 'country'):
                    attrList.append({'CITIZENSHIP': getValue(subRecord, 'country')})

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
                        updateStat('!ADDRESS', 'country only')
                    else:
                        updateStat('!ADDRESS', 'UNTYPED')
            if addrList:
                jsonData['ADDR_LIST'] = addrList

            #--add any ID numbers
            itemNum = 0
            idList = []
            for subRecord in sdnEntry.findall('idList/id'):
                if getValue(subRecord, 'idNumber'):

                    idData = {}
                    idType = getValue(subRecord, 'idType')
                    idNumber = getValue(subRecord, 'idNumber')
                    idCountry = getValue(subRecord, 'idCountry')

                    update_code_stats('idType', idType, idNumber)
                    senzingAttr = code_conversion_data['idType'][idType]['SENZING_ATTR']
                    if idCountry:
                        update_code_stats('idCountry', idCountry, idType)
                        senzingCountry = code_conversion_data['idCountry'][idCountry]['SENZING_DEFAULT']
                    else:
                        senzingCountry = ''

                    if senzingAttr:
                        if senzingAttr == 'IMO_NUMBER':
                            idNumber.replace('IMO ','')
                        idData[senzingAttr] = idNumber
                        if senzingAttr in ('OTHER_ID_NUMBER', 'NATIONAL_ID_NUMBER'):
                            idData[senzingAttr.replace('_NUMBER', '_TYPE')] = idType
                        if senzingCountry:
                            idData[senzingAttr.replace('_NUMBER', '_COUNTRY')] = senzingCountry
                        idList.append(idData)

                    else:
                        senzingAttr = 'UNKNOWN'
                        if idType not in jsonData:
                            jsonData[idType] = idNumber + (f" ({idCountry})" if idCountry else '')
                        else: 
                            jsonData[idType] += ' | ' + idNumber + (f" ({idCountry})" if idCountry else '')

                    #updateStat(f'!{senzingAttr}', f"{idType}", f"{idNumber}|{senzingCountry}")

            if idList:
                jsonData['ID_LIST'] = idList

            #--still some vessel info in this structure
            if g2RecordType == 'VESSEL':
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
                    
            capture_mapped_stats(jsonData)

        jsonStr = json.dumps(jsonData)
        try: outputHandle.write(jsonStr + '\n')
        except IOError as err:
            print(f'\ncould not write to output file: {err}\n')
            appError = 1
            break
            
    outputHandle.close()
    print(f'\n{rowCnt} records written, done!\n')

    return 0

#----------------------------------------
if __name__ == "__main__":
    appPath = os.path.dirname(os.path.abspath(sys.argv[0]))

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-i', '--inputFile', dest='inputFile', type=str, default=None, help='an sdn.xml file downloaded from https://www.treasury.gov/ofac/downloads.')
    argparser.add_argument('-o', '--outputFile', dest='outputFile', type=str, help='output filename, defaults to input file name with a .json extension.')
    argparser.add_argument('-l', '--logFile', dest='logFile', type=str, help='optional statistics filename in json format.')
    args = argparser.parse_args()
    inputFile = args.inputFile
    outputFile = args.outputFile
    logFile = args.logFile

    if not (inputFile):
        print('\nPlease supply an input file name with the -i parameter\n')
        sys.exit(1)

    #--default the output file if not supplied
    if not (outputFile):
        outputFile = inputFile.replace('.xml', '.json')
    
    codes_filename = 'ofac_codes.csv' #--os.path.dirname(__file__) + os.sep + 'ofac_codes.csv'
    if not os.path.exists(codes_filename):
        print(f'\nFile {codes_filename} missing!\n')
        sys.exit(1)

    code_conversion_data, unmapped_code_count = load_codes_file(codes_filename)
    statPack = {}

    result = processFile()

    save_codes_file(codes_filename)
    if logFile: 
        with open(logFile, 'w') as outfile:
            json.dump(statPack, outfile, indent=4, sort_keys = True)    
        print(f'Mapping stats written to {logFile}\n')

    sys.exit(result)
   
