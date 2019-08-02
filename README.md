# mapper-ofac

## Overview

The [ofac2json.py](ofac2json.py) python script converts the Office of Foreign Asset Control (OFAC)
sdn.xml file available from https://www.treasury.gov/ofac/downloads to a json file ready to load into 
senzing. 

Loading watch lists requires some special features and configurations of Senzing. These are contained in the 
[ofac-config-updates.json](ofac-config-updates.json) file and are applied with the [G2ConfigTool.py](G2ConfigTool.py) contained in this project.

**IMPORTANT NOTE:** For good watch list matching, your other data sources should also map as many these same features as are available!

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
                        output filename. defaults to input file name with a
                        .json extension.
  -c ISOCOUNTRYSIZE, --isoCountrySize ISOCOUNTRYSIZE
                        ISO country code size. Either 2 or 3, default = 3.
  -a, --includeAll      convert all entity types including vessels and
                        aircraft.
  -s STATISTICSFILE, --statisticsFile STATISTICSFILE
                        optional statistics filename in json format.
```

## Contents

1. [Prerequisites](#Prerequisites)
2. [Installation](#Installation)
3. [Configuring Senzing](#Configuring-Senzing)
4. [Running the ofac2json mapper](#Running-the-ofac2json-mapper)
5. [Loading into Senzing](#Loading-into-Senzing)
6. [Mapping other data sources](#Mapping-other-data-sources)
7. [Optional ini file parameter](#Optional-ini-file-parameter)

### Prerequisites
- python 3.6 or higher

### Installation

Place the the following files on a directory of your choice ...
- [ofac2json.py](ofac2json.py) 
- [isoCountries.json](isoCountries.json)
- [ofac-config-updates.json](ofac-config-updates.json)

*Note:* The isoCountries.json file is extensible.   It currently contains a mapping from a raw country name into a 2 digit iso country code. Additional entries can be added as desired.

### Configuring Senzing

*Note:* This only needs to be performed one time! In fact you may want to add these configuration updates to a master configuration file for all your data sources.

Update the G2ConfigTool.py program file on the /opt/senzing/g2/python directory with this one ... [G2ConfigTool.py](G2ConfigTool.py)

Then from the /opt/senzing/g2/python directory ...
```console
python G2ConfigTool.py <path-to-file>/ofac-config-updates.json
```
This will step you through the process of adding the data sources, entity types, features, attributes and other settings needed to load OFAC data into Senzing. After each command you will see a status message saying "success" or "already exists".  For instance, if you run the script twice, the second time through they will all say "already exists" which is OK.

Configuration updates include:
- addDataSource **OFAC**
- addEntityType **PERSON**
- addEntityType **ORGANIZATION**
- add features and attributes for ...
    - **RECORD_TYPE** This helps keep persons and organizations from resolving together.
    - **COUNTRY_CODE** This is a 3 character country code used to improve matching of nationality, citizenship and place of birth.
    - **PLACE_OF_BIRTH** This is a feature missing from the default configuration of early version of Senzing
    - **OFAC_ID** This is used to help prevent watch list entries from resolving to each other and so that you can search on it.
    - **DUNS_NUMBER** This is great for matching companies.

*WARNING:* the following settings are commented out as they affect performance and quality. Only use them if you understand and are OK with the effects.
- sets **NAME** and **ADDRESS** to be used for candidates. Normally just their hashes are used to find candidates.  The effect is performance is slightly degraded.
- set **distinct** off.  Normally this is on to prevent lower strength AKAs to cause matches as only the most distinct names are considered. The effect is more potential false positives.

Finally, the additional entity types and features needed to load aircraft and vessels are also commented out.  Leave them commented out unless you are trying to match aircraft and vessels as well.

### Running the ofac2json mapper

First, download the latest sdn.xml file from https://www.treasury.gov/ofac/downloads. This is the only file needed. It would be a good practice to rename it based on the publish date such as sdn-yyyy-mm-dd.xml and place it on a directory where you will store other source data files loaded into Senzing. 

Second, run the mapper.  Typical usage:
```console
python ofac2json.py -i /<path-to-file>/sdn-yyyy-mm-dd.xml
```
The output file defaults to the same name and location as the input file except the extension is changed to .json.

- Use the -o parameter if you want a supply a different output file name or location
- Use the -a parameter to include the aircraft and vessel OFAC records.
- Use the -c parameter to change from 3 character to 2 character ISO country codes.
- Use the -s parameter to log the mapping statistics to a file.

*Note* The mapping satistics should be reviewed occasionally to determine if there are other values that can be mapped to new features.  Check the UNKNOWN_ID section for values that you may get from other data sources that you would like to make into their own features.  Most of these values were not mapped because there just aren't enough of them to matter and/or you are not likely to get them from any other data sources. However, DUNS_NUMBER, GENDER, and WEBSITE_ADDRESS were found by reviewing these statistics!

### Loading into Senzing

If you use the G2Loader program to load your data, from the /opt/senzing/g2/python directory ...
```console
python G2Loader.py -f /<path-to-file>/ofac-yyyy-mm-dd.json
```
The OFAC currently only contains around 7,000 records and loads in a matter of minutes.

If you use the API directly, then you just need to perform an addRecord for each line of the file.

### Mapping other data sources

Watch lists are harder to match simply because often the only data they contain that matches your other data sources are name, partial date of birth, and citizenship or nationality.  Complete address or identifier matches are possible but more rare. For this reason, the following special attributes should be mapped from your internal data sources or search request messages ... 
- **RECORD_TYPE** (valid values are PERSON or ORGANIZATION, only supply if known.)
- **COUNTRY_CODE** (standardized with [isoCountries.json](isoCountries.json)) Simply find any country you can that qualifies as a nationality, citizenship or place of birth, find it in the isCountries file and map the iso3 value as COUNTRY_CODE. 

### Optional ini file parameter

There is also an ini file change that can benefit watch list matching.  In the pipeline section of the main g2 ini file you use, such as the /opt/senzing/g2/python/G2Module.ini, place the following entry in the pipeline section as show below.

```console
[pipeline]
 NAME_EFEAT_WATCHLIST_MODE=Y
```

This effectively doubles the number of name hashes created which improves the chances of finding a match at the cost of performance.  Consider creating a separate g2 ini file used just for searching and include this parameter.  If you include it during the loading of data, only have it on while loading the watch list as the load time will actually more than double! 

