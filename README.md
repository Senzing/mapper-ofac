# mapper-ofac

## Overview

The [ofac_mapper.py](ofac_mapper.py) python script converts the Office of Foreign Asset Control (OFAC)
sdn.xml file available from
[https://www.treasury.gov/ofac/downloads](https://www.treasury.gov/ofac/downloads)
to a json file ready to load into Senzing.

Loading watch lists requires some special features and configurations of Senzing. These are contained in the
[ofac_config_updates.g2c](ofac_config_updates.g2c) file.

Usage:

```console
usage: ofac_mapper.py [-h] [-i INPUTFILE] [-o OUTPUTFILE] [-a]
                    [-s STATISTICSFILE]

optional arguments:
  -h, --help            show this help message and exit
  -i INPUTFILE, --inputFile INPUTFILE
                        an sdn.xml file downloaded from
                        https://www.treasury.gov/ofac/downloads.
  -o OUTPUTFILE, --outputFile OUTPUTFILE
                        output filename, defaults to input file name with a
                        .json extension.
  -a, --includeAll      convert all entity types including vessels and
                        aircraft.
  -s STATISTICSFILE, --statisticsFile STATISTICSFILE
                        optional statistics filename in json format.
```

## Contents

1. [Prerequisites](#prerequisites)
1. [Installation](#installation)
1. [Configuring Senzing](#configuring-senzing)
1. [Running the ofac_mapper mapper](#running-the-ofac_mapper-mapper)
1. [Loading into Senzing](#loading-into-senzing)
1. [Mapping other data sources](#mapping-other-data-sources)
1. [Optional ini file parameter](#optional-ini-file-parameter)

### Prerequisites

- python 3.6 or higher
- Senzing version 2.0 or higher

### Installation

Place the the following files on a directory of your choice ...

- [ofac_mapper.py](ofac_mapper.py)
- [ofac_config_updates.g2c](ofac_config_updates.g2c)
- [iso_countries.json](iso_countries.json)
- [iso_states.json](iso_states.json)

*Note:* The iso\*.json file are extensible. They currently only contain the most common country and state name variations. Additional entries can be added as desired. This conversion program extracts and standardizes country codes from the fields: nationality, citizenship, place of birth, addresses, passports and other national identifiers.

### Configuring Senzing

*Note:* This only needs to be performed one time! In fact you may want to add these configuration updates to a master configuration file for all your data sources.

From your /<project directory>/g2/python directory ...

```console
python3 G2ConfigTool.py <path-to-file>/ofac_config_updates.g2c
```

This will step you through the process of adding the data sources, entity types, features, attributes and other settings needed to load this watch list data into Senzing. After each command you will see a status message saying "success" or "already exists".  For instance, if you run the script twice, the second time through they will all say "already exists" which is OK.

*WARNING:* The are a few commented out optional settings described in the configuration file as they affect performance and quality. Only use them if you understand and are OK with the effects.

The additional entity types and features needed to load aircraft and vessels are also commented out.  You should only uncomment them if you are trying to match aircraft and vessels as well.

### Running the ofac_mapper mapper

First, download the latest sdn.xml file from
[https://www.treasury.gov/ofac/downloads](https://www.treasury.gov/ofac/downloads).
This is the only file needed. It is a good practice to rename it based on the publish date such as sdn-yyyy-mm-dd.xml and place it on a directory where you will store other source data files loaded into Senzing.

Second, run the mapper.  Typical usage:

```console
python ofac_mapper.py -i /<path-to-file>/sdn-yyyy-mm-dd.xml
```

The output file defaults to the same name and location as the input file except the extension is changed to .json.

- Use the -o parameter if you want a supply a different output file name or location
- Use the -a parameter to include the aircraft and vessel OFAC records.
- Use the -s parameter to log the mapping statistics to a file.

*Note* The mapping satistics should be reviewed occasionally to determine if there are other values that can be mapped to new features.  Check the UNKNOWN_ID section for values that you may get from other data sources that you would like to make into their own features.  Most of these values were not mapped because there just aren't enough of them to matter and/or you are not likely to get them from any other data sources. However, DUNS_NUMBER, GENDER, and WEBSITE_ADDRESS were found by reviewing these statistics!

### Loading into Senzing

If you use the G2Loader program to load your data, from the /opt/senzing/g2/python directory ...

```console
python G2Loader.py -f /<path-to-file>/ofac-yyyy-mm-dd.json
```

The OFAC currently only contains around 7,000 records and loads in a matter of minutes.

If you use the API directly, then you just need to perform an addRecord for each line of the file.

### Optional ini file parameter

There is also an ini file change that can benefit watch list matching.  In the pipeline section of the main g2 ini file you use, such as the /opt/senzing/g2/python/G2Module.ini, place the following entry in the pipeline section as show below.

```console
[pipeline]
 NAME_EFEAT_WATCHLIST_MODE=Y
```

This effectively doubles the number of name hashes created which improves the chances of finding a match at the cost of performance.  Consider creating a separate g2 ini file used just for searching and include this parameter.  If you include it during the loading of data, only have it on while loading the watch list as the load time will actually more than double!
