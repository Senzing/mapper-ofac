# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python mapper that converts US Treasury OFAC SDN (Specially Designated Nationals) XML files into JSON format ready to load into Senzing entity resolution software.

## Development Commands

### Setup virtual environment and install dependencies

```bash
python -m venv ./venv
source ./venv/bin/activate
pip install --group all .
```

### Run the mapper

```bash
python src/ofac_mapper.py -i <input.xml> -o <output.json> -l <stats.json>
```

Note: The `ofac_codes.csv` file must be in the current working directory when running the mapper.

### Linting

```bash
pylint $(git ls-files '*.py' ':!:docs/source/*')
```

### Run tests

```bash
pytest
```

## Architecture

### Key Files

- **src/ofac_mapper.py** - Main conversion script that parses OFAC SDN XML and outputs Senzing-compatible JSON
- **src/ofac_codes.csv** - Mapping file that translates OFAC ID types and countries to Senzing attributes (e.g., idType -> PASSPORT_NUMBER, idCountry -> ISO country code)
- **src/ofac_config_updates.g2c** - Senzing configuration commands to add required data sources, features, and attributes

### Data Flow

1. XML file downloaded from treasury.gov is parsed using `xml.etree.ElementTree`
2. Each `sdnEntry` is converted to a JSON record with:
   - Entity type mapping (Entity→ORGANIZATION, Individual→PERSON)
   - Name extraction (primary + AKAs)
   - Attributes (DOB, POB, nationality, citizenship)
   - Addresses
   - ID numbers (mapped via ofac_codes.csv to Senzing attribute types)
3. Output JSON written line-by-line for Senzing G2Loader consumption

### Code Mapping System

The `ofac_codes.csv` file tracks code mappings and is updated each time the mapper runs:

- `REVIEWED=Y` indicates a code has been mapped to a Senzing attribute
- `REVIEWED=N` indicates new/unmapped codes that need attention
- Running the mapper updates statistics columns (counts, examples) for code review
