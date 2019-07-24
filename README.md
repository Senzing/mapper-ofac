# mapper-ofac

## Overview

The [ofac2json.py](ofac2json.py) python script converts the Office of Foreign Asset Control (OFAC)
sdn.xml file available from https://www.treasury.gov/ofac/downloads to a json file ready to load into 
senzing. 

The additional configuration needed to load this data is contained in the ofac-config-updates.json](ofac-config-updates.json) file.


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

Typical usage:
```console
python ofac2json.py -i /<filepath>/sdn.xml
```
This will create an ofac-yyyy-mm-dd.json file on the same directory as the sdn.xml file that contains only the 
individuals and entities in the sdn.xml.

### Contents

1. [Installation](#installation)

2. [Senzing Configuration](#senzing-configuration)

### Install

Place the the following files on a directory of your choice ...
    ofac2json.py
    isoCountries.json
    ofac-config-updates.json

### Senzing Configuration

Update the G2ConfigTool.py program file on the /opt/senzing/g2/python directory with this one. 

from the /opt/senzing/g2/python directory
```console
python G2ConfigTool.py <filepath>/ofac-config-updates.json
```
This will step you through the process of adding the data sources, entity types and features needed to load OFAC data intoi Senzing.

