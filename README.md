# mapper-ofac

## Overview

The [ofac2json.py](ofac2json.py) python script converts the Office of Foreign Asset Control (OFAC)
sdn.xml file available from https://www.treasury.gov/ofac/downloads to a json file ready to load into 
senzing. 

Loading watch lists requires some special features and configurations of Senzing. These are contained in the 
[ofac-config-updates.json](ofac-config-updates.json) file and are applied with the [G2ConfigTool.py](G2ConfigTool.py) contained in this project.

**IMPORTANT NOTE: For good watch list matching, your other data sources should also map as many these same features as are available!**

Usage:
```console
$ python ofac2json.py --help
usage: ofac2json.py [-h] [-i INPUTFILE] [-o OUTPUTFILE] [-a]

optional arguments:
  -h, --help            show this help message and exit
  -i INPUTFILE, --inputFile INPUTFILE
                        an sdn.xml file downloaded from
                        https://www.treasury.gov/ofac/downloads.
  -o OUTPUTFILE, --outputFile OUTPUTFILE
                        output filename. default is ofac-yyyy-mm-dd.json based
                        on the publish date
  -a, --includeAll      convert all entity types including vessels and
                        aircraft
```

## Contents

1. [Installation](#installation)

1. [Configuring Senzing](#configuring_senzing)

1. [Running ofac2json](#running-ofac2json)

1. [Loading Senzing](#loading-senzing)

### Installation

Place the the following files on a directory of your choice ...
- [ofac2json.py](ofac2json.py) 
- [isoCountries.json](isoCountries.json)
- [ofac-config-updates.json](ofac-config-updates.json)

### Configuring Senzing

*Note: This only needs to be performed one time! In fact you may want to add these configuration updates to a master configuration file for all your data sources.*

Update the G2ConfigTool.py program file on the /opt/senzing/g2/python directory with this one ... [G2ConfigTool.py](G2ConfigTool.py)

from the /opt/senzing/g2/python directory ...
```console
python G2ConfigTool.py <path-to-file>/ofac-config-updates.json
```
This will step you through the process of adding the data sources, entity types, features and attributes needed to load OFAC data into Senzing. After each command you will see a status message saying "success" or "already exists".  For instance, if you run the script twice, the second time through they will all say "already exists" which is OK.

Configuration updates include:
- addDataSource **OFAC**
- addEntityType **PERSON**
- addEntityType **ORGANIZATION**
- adds features and attributes for ...
    - **RECORD_TYPE** this helps keep persons and organizations from resolving together.
    - **YEAR_OF_BIRTH** this is the year portion of the date of birth
    - **COUNTRY_CODE** this is the ISO country code used to improve matching of nationality, citizenship and place of birth.
    - **OFAC_ID** this is used to help prevent watch list entries from resolving to each other.
    - **PLACE_OF_BIRTH** this is a just a good feature to add 

*WARNING:* the following settings are commented out as they affect performance and quality. Only use them if you understand and are OK with the effects.
- sets NAME and ADDRESS to be used for candidates. Normally just their hashes are used to find candidates.  Affect is performance is slightly degraded.
- set distinct off.  Normally this is on to prevent lower strength AKAs to cause matches as only the most distinct names are considered.


*Note:* the most important features to add to your other data sources are ...
- RECORD_TYPE
- YEAR_OF_BIRTH
- COUNTRY_CODE (standardized with [isoCountries.json](isoCountries.json))



### Running ofac2json.py

First download the latest sdn.xml file from https://www.treasury.gov/ofac/downloads. This is the only file needed. Place it on a directory where you will store other source data files loaded into Senzing.

Typical usage:
```console
python ofac2json.py -i /<filepath>/sdn.xml
```
This will create an ofac-yyyy-mm-dd.json file on the same directory as the sdn.xml file that contains only the 
individuals and entities in the sdn.xml.




