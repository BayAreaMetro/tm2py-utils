#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
create_taz_data.py

End-to-end TAZ data pipeline for Travel Model One and Two.
Loads all settings (constants, paths, geo, variable mappings) from config.yaml.
Defines 14 sequential steps to create TAZ-level data from Census and LODES data.


 - Household- and population-based variables are based on the ACS5-year dataset which centers around the
   given year, or the latest ACS5-year dataset that is available (see variable, ACS_5year). 
   The script fetches this data using tidycensus.

 - ACS block group variables used in all instances where not suppressed. If suppressed at the block group 
   level, tract-level data used instead. Suppressed variables may change if ACS_5year is changed. This 
   should be checked, as this change could cause the script not to work.

 - Group quarter data is not available below state level from ACS, so 2020 Decennial census numbers
   are used instead, and then scaled (if applicable)

 - Wage/Salary Employment data is sourced from LODES for the given year, or the latest LODES dataset that is available.
   (See variable, LODES_YEAR)
 - Self-employed persons are also added from taz_self_employed_workers_[year].csv
 
 - If ACS1-year data is available that is more recent than that used above, these totals are used to scale
   the above at a county-level.

 - Employed Residents, which includes people who live *and* work in the Bay Area are quite different
   between ACS and LODES, with ACS regional totals being much higher than LODES regional totals.
   This script includes a parameter, EMPRES_LODES_WEIGHT, which can be used to specify a blended target
   between the two.

"""
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
import requests
from census import Census



CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)

CONSTANTS = cfg['constants']
GEO       = cfg['geo_constants']
PATHS     = cfg['paths']
VARIABLES = cfg['variables']

KEY_FILE = PATHS['census_api_key_file']
with open(KEY_FILE, 'r') as f:
    CENSUS_API_KEY = f.read().strip()

# Default processing year from config
YEAR = CONSTANTS['years'][0]
DECENNIAL_YEAR  = CONSTANTS['DECENNIAL_YEAR']
ACS_5YR_LATEST  = CONSTANTS['ACS_5YEAR_LATEST']

# ------------------------------
# Import helper functions from common.py
# ------------------------------
sys.path.insert(0, str(Path(__file__).parent))
from common import (
    census_to_df,
    download_acs_blocks,
    retrieve_census_variables,
    fix_rounding_artifacts,
    map_acs5year_household_income_to_tm1_categories,
    update_gqpop_to_county_totals,
    update_tazdata_to_county_target,
    make_hhsizes_consistent_with_population,
)

# ------------------------------
# STEP 1: Fetch block-level population (Decennial PL)
# ------------------------------
import logging
import pandas as pd

def step1_fetch_block_data(c, year):
    """
    Fetch 2020 dec/pl block‐level total population (P1_001N),
    construct the 15‐digit block GEOID from state/county/tract/block,
    derive blockgroup & tract, and keep state & county.
    Returns columns:
      - state        : 2-digit state FIPS
      - county       : 3-digit county FIPS
      - block_geoid  : full 15-digit block GEOID
      - blockgroup   : 12-digit block-group FIPS
      - tract        : 11-digit tract FIPS
      - pop          : block population (int)
    """
    logger = logging.getLogger(__name__)

    # Config
    dec_year     = CONSTANTS['DECENNIAL_YEAR']              # e.g. 2020
    state_code   = GEO['STATE_CODE']                        # e.g. "06"
    county_codes = list(GEO['BA_COUNTY_FIPS_CODES'].keys()) # e.g. ["001","013",…]
    
    # 1) Retrieve P1_001N from dec/pl
    records = []
    for county in county_codes:
        try:
            recs = retrieve_census_variables(
                c, dec_year, 'dec/pl',
                ['P1_001N'],      # total population
                for_geo='block',
                state=state_code,
                county=county
            )
            records.extend(recs)
        except Exception as e:
            logger.error(f"Error fetching {dec_year} PL for county {county}: {e}")
    df = pd.DataFrame(records)
    logger.info(f"step1 fetched columns: {df.columns.tolist()}")

    # 2) Pad and keep state & county
    df['state']  = df['state'].astype(str).str.zfill(2)
    df['county'] = df['county'].astype(str).str.zfill(3)

    # 3) Pad tract (6) and block (4) then build full block_geoid
    df['tract'] = df['tract'].astype(str).str.zfill(6)
    df['block'] = df['block'].astype(str).str.zfill(4)
    df['block_geoid'] = df['state'] + df['county'] + df['tract'] + df['block']

    # 4) Derive blockgroup & tract keys
    df['blockgroup'] = df['block_geoid'].str[:12]
    df['tract']      = df['block_geoid'].str[:11]

    # 5) Coerce population
    df['pop'] = (
        pd.to_numeric(df.get('P1_001N', 0), errors='coerce')
          .fillna(0)
          .astype(int)
    )

    # 6) Return the columns step5 needs
    return df[['state','county','block_geoid','blockgroup','tract','pop']]


# ------------------------------
# STEP 2: Fetch ACS block-group variables
# ------------------------------
def step2_fetch_acs_bg(c, year):
    """
    Fetch ACS 5-year block-group vars and return a DataFrame
    with:
      - a 12-char padded 'blockgroup' string (no "1500000US" prefix)
      - one column per VARIABLES['ACS_BG_VARIABLES'] key
    """
    # 1) FIPS codes from config
    state_code   = GEO['STATE_CODE']                        # e.g. "06"
    county_codes = list(GEO['BA_COUNTY_FIPS_CODES'].keys()) # e.g. ["001","013",…]
    
    # 2) Build the list of API vars with the "E" suffix
    fetch_vars = [f"{code}E" for code in VARIABLES['ACS_BG_VARIABLES'].values()]

    # 3) Retrieve records
    records = []
    for county in county_codes:
        try:
            recs = retrieve_census_variables(
                c, year, 'acs5',
                fetch_vars,
                for_geo='block group',
                state=state_code,
                county=county
            )
            records.extend(recs)
        except Exception as e:
            logger.error(f"Error retrieving ACS BG for county {county}: {e}")
            continue

    df = pd.DataFrame(records)

    # 4) Rename the geo-ID field → 'blockgroup'
    for col in ('GEOID', 'GEO_ID', 'geoid', 'block group'):
        if col in df.columns:
            df.rename(columns={col: 'blockgroup'}, inplace=True)
            break
    else:
        raise KeyError("ACS BG fetch: no GEOID or 'block group' column found")

    # 5) Strip any prefix and keep only the last 12 characters
    df['blockgroup'] = (
        df['blockgroup']
          .astype(str)
          .str[-12:]        # take rightmost 12 characters
          .str.zfill(12)    # ensure 12 digits
    )

    # 7) Rename your ACS variables and coerce
    for new_var, old_code in VARIABLES['ACS_BG_VARIABLES'].items():
        api_var = f"{old_code}E"
        if api_var in df.columns:
            df.rename(columns={api_var: new_var}, inplace=True)
            df[new_var] = (
                pd.to_numeric(df[new_var], errors='coerce')
                  .fillna(0)
                  .astype(int)
            )
        else:
            logger.warning(f"ACS BG: expected {api_var!r} not in results, filling zeros for {new_var}")
            df[new_var] = 0

    return df
# ------------------------------
# STEP 3: Fetch ACS tract variables
# ------------------------------
def step3_fetch_acs_tract(c, year=YEAR):
    var_map    = VARIABLES.get('ACS_TRACT_VARIABLES', {})
    if not var_map:
        raise ValueError('CONFIG ERROR: ACS_TRACT_VARIABLES empty')

    # 1) fetch the raw Census vars with E-suffix
    fetch_vars = [f"{code}E" for code in var_map.values()]
    state_code = GEO['STATE_CODE']
    counties   = list(GEO['BA_COUNTY_FIPS_CODES'].keys())

    records = []
    for county in counties:
        recs = retrieve_census_variables(
            c, year, 'acs5', fetch_vars,
            for_geo='tract', state=state_code, county=county
        )
        records.extend(recs)

    if not records:
        logging.warning(f"No tract ACS for {year}")
        return pd.DataFrame()

    df = census_to_df(records)

    # 2) build the full 11-digit tract code
    df['tract'] = (
        df['state'].astype(str).str.zfill(2)
      + df['county'].astype(str).str.zfill(3)
      + df['tract'].astype(str).str.zfill(6)
    )

    # 3) start your output with tract
    out = pd.DataFrame({'tract': df['tract']})

    # 4) for each (output_name, census_code), grab the E-column or zeros
    for output_name, code in var_map.items():
        colE = f"{code}E"
        # if missing, produce a zero Series of correct length
        series = df.get(colE, pd.Series(0, index=df.index))
        out[output_name] = (
            pd.to_numeric(series, errors='coerce')
              .fillna(0)
              .astype(int)
        )

    return out


# Step 4: Fetch DHC tract variables (Detailed Housing Characteristics)
# ------------------------------
def step4_fetch_dhc_tract(c, year=DECENNIAL_YEAR):
    """
    Download decennial DHC variables for tracts using the Census API.
    Returns a DataFrame with columns:
      - tract       : 11-digit GEOID (state+county+tract)
      - one column per VARIABLES['DHC_TRACT_VARIABLES'] key
      - county_fips : 3-digit county FIPS (from the raw API response)
      - County_Name : full county name (matches GEO['BA_COUNTY_FIPS_CODES'])
    """
    import requests

    # 1) pick a valid decennial year
    dec_year = year if year in (2000, 2010, 2020) else DECENNIAL_YEAR

    # 2) pull your mapping of clean names → API codes
    var_map = VARIABLES.get('DHC_TRACT_VARIABLES', {})
    if not var_map:
        raise ValueError("CONFIG ERROR: DHC_TRACT_VARIABLES is empty")

    fetch_vars = list(var_map.values())
    state      = GEO['STATE_CODE']
    counties   = list(GEO['BA_COUNTY_FIPS_CODES'].keys())

    # 3) fetch JSON for each county
    rows = []
    for cnt in counties:
        resp = requests.get(
            f"https://api.census.gov/data/{dec_year}/dec/dhc",
            params={
                'get': ",".join(fetch_vars),
                'for': 'tract:*',
                'in':  f"state:{state}+county:{cnt}",
                'key': CENSUS_API_KEY
            }
        )
        if resp.status_code != 200:
            logging.error(f"DHC fetch failed ({cnt}): {resp.status_code}")
            continue
        data = resp.json()
        cols = data[0]
        for vals in data[1:]:
            rows.append(dict(zip(cols, vals)))

    if not rows:
        raise RuntimeError(f"No DHC data for decennial year {dec_year}")

    df = pd.DataFrame(rows)

    # 4) build the full 11-digit tract GEOID
    df['tract'] = (
        df['state'].str.zfill(2) +
        df['county'].str.zfill(3) +
        df['tract'].str.zfill(6)
    )

    # 5) pull out each API field into its clean name
    out = pd.DataFrame({'tract': df['tract']})
    for clean_name, api_code in var_map.items():
        out[clean_name] = (
            pd.to_numeric(df[api_code], errors='coerce')
              .fillna(0)
              .astype(int)
        )

    # 6) retain the raw county FIPS from df
    out['county_fips'] = df['county'].astype(str).str.zfill(3)
    # 7) map to full county name
    out['County_Name'] = out['county_fips'].map(GEO['BA_COUNTY_FIPS_CODES'])

    return out
""" 
if __name__ == '__main__':
    # Initialize Census client
    from census import Census
    c = Census(CENSUS_API_KEY)

    # Fetch Census-based data layers
    outputs = {}
    outputs['blocks'] = step1_fetch_block_data(c, YEAR)
    outputs['acs_bg'] = step2_fetch_acs_bg(c, YEAR)
    outputs['acs_tr'] = step3_fetch_acs_tract(c, min(YEAR+2, ACS_5YR_LATEST))
    outputs['dhc_tr'] = step4_fetch_dhc_tract(c)

    # Summary of fetched layers
    print('Fetched data layers:', list(outputs.keys())) """