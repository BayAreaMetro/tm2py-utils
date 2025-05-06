import logging
import os
import sys
import yaml
import requests
from pathlib import Path
import pandas as pd
from census import Census
from common import (
    retrieve_census_variables,
    census_to_df,
    download_acs_blocks,
    fix_rounding_artifacts,
    map_acs5year_household_income_to_tm1_categories,
    update_gqpop_to_county_totals,
    update_tazdata_to_county_target,
    make_hhsizes_consistent_with_population,
)
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)

CONSTANTS = cfg['constants']
GEO = cfg['geo_constants']
PATHS = cfg['paths']
VARIABLES = cfg['variables']

# Census API Key
with open(PATHS['census_api_key_file'], 'r') as f:
    CENSUS_API_KEY = f.read().strip()

# Default processing years and geographic constants
YEAR = CONSTANTS['years'][0]
DECENNIAL_YEAR = CONSTANTS['DECENNIAL_YEAR']
ACS_5YR_LATEST = CONSTANTS['ACS_5YEAR_LATEST']
STATE_CODE = GEO['STATE_CODE']
BAYCOUNTIES = GEO['BAYCOUNTIES']

# Initialize Census API client
census_client = Census(CENSUS_API_KEY)

def step1_fetch_block_data(census_client):
    """Fetch block-level total population from decennial census."""
    records = []
    for county in BAYCOUNTIES:
        try:
            recs = retrieve_census_variables(
                census_client, DECENNIAL_YEAR, 'dec/pl', ['P1_001N'],
                for_geo='block', state=STATE_CODE, county=county
            )
            records.extend(recs)
        except Exception as e:
            logger.error(f"Error fetching data for county {county}: {e}")

    df = pd.DataFrame(records)

    df['state'] = df['state'].str.zfill(2)
    df['county'] = df['county'].str.zfill(3)
    df['tract'] = df['tract'].str.zfill(6)
    df['block'] = df['block'].str.zfill(4)

    df['block_geoid'] = df['state'] + df['county'] + df['tract'] + df['block']
    df['blockgroup'] = df['block_geoid'].str[:12]
    df['tract'] = df['block_geoid'].str[:11]

    df['pop'] = pd.to_numeric(df.get('P1_001N', 0), errors='coerce').fillna(0).astype(int)

    return df[['state', 'county', 'block_geoid', 'blockgroup', 'tract', 'pop']]

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

def step2b_compute_bg_vars(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute block-group-level demographic and employment variables:
      1. Build age bins by summing male+female cohorts
      2. Aggregate occupation columns into summary fields
    Expects raw ACS block-group columns (no trailing underscores), e.g.:
      'male0_4', 'female0_4', …, 'pers_occ_management', etc.
    Returns a DataFrame with new bg-level aggregates.
    """
    df = df.copy()
    
    # 1) Age bins
    df['age0004'] = df['male0_4'] + df['female0_4']
    df['age0519'] = (
        df[['male5_9', 'male10_14', 'male15_17', 'male18_19']].sum(axis=1) +
        df[['female5_9', 'female10_14', 'female15_17', 'female18_19']].sum(axis=1)
    )
    df['age2044'] = (
        df[['male20', 'male21', 'male22_24', 'male25_29', 'male30_34', 'male35_39', 'male40_44']].sum(axis=1) +
        df[['female20', 'female21', 'female22_24', 'female25_29', 'female30_34', 'female35_39', 'female40_44']].sum(axis=1)
    )
    df['age4564'] = (
        df[['male45_49', 'male50_54', 'male55_59', 'male60_61', 'male62_64']].sum(axis=1) +
        df[['female45_49', 'female50_54', 'female55_59', 'female60_61', 'female62_64']].sum(axis=1)
    )
    df['age65p'] = (
        df[['male65_66', 'male67_69', 'male70_74', 'male75_79', 'male80_84', 'male85p']].sum(axis=1) +
        df[['female65_66', 'female67_69', 'female70_74', 'female75_79', 'female80_84', 'female85p']].sum(axis=1)
    )

    cats = [
      'manage','prof_biz','prof_comp','svc_comm','prof_leg','prof_edu',
      'svc_ent','prof_heal','svc_heal','svc_fire','svc_law','ret_eat',
      'man_build','svc_pers','ret_sales','svc_off','man_nat','man_prod'
    ]
    for cat in cats:
        df[f'occ_{cat}'] = df[f'occ_m_{cat}'] + df[f'occ_f_{cat}']
    
    # 2) Total employment (sum of all occ_* cols)
    occ_cols = [f'occ_{cat}' for cat in cats]
    df['emp_occ_total'] = df[occ_cols].sum(axis=1)
    
    # 3) Service + retail
    service_cats = ['svc_comm','svc_ent','svc_heal','svc_fire','svc_law','svc_pers','svc_off']
    df['emp_service_retail'] = df[[f'occ_{c}' for c in service_cats] + ['occ_ret_sales']].sum(axis=1)
    
    # 4) Manual + production (natural resources + building + production)
    df['emp_manual_military'] = (
        df['occ_man_nat'] +
        df['occ_man_build'] +
        df['occ_man_prod']
    )

    df['sfdu'] = df['unit1d'] + df['unit1a'] + df['mobile'] + df['boat_RV_Van']
    df['mfdu'] = (
        df['unit2'] + df['unit3_4'] + df['unit5_9']
    + df['unit10_19'] + df['unit20_49'] + df['unit50p']
    )
    # Tenure
    df['hh_own']  = df[['own1','own2','own3','own4','own5','own6','own7p']].sum(axis=1)
    df['hh_rent'] = df[['rent1','rent2','rent3','rent4','rent5','rent6','rent7p']].sum(axis=1)
    # Household sizes
    df['hh_size_1']      = df['own1']  + df['rent1']
    df['hh_size_2']      = df['own2']  + df['rent2']
    df['hh_size_3']      = df['own3']  + df['rent3']
    df['hh_size_4_plus'] = df[['own4','own5','own6','own7p','rent4','rent5','rent6','rent7p']].sum(axis=1)
    return df
# ------------------------------
# STEP 3: Fetch ACS tract variables
# ------------------------------
def step3_fetch_acs_tract(c, year=YEAR, max_retries=3, backoff=5):
    var_map  = VARIABLES.get('ACS_TRACT_VARIABLES', {})
    if not var_map:
        raise ValueError('CONFIG ERROR: ACS_TRACT_VARIABLES empty')

    # 1) Build the list of E-suffixed codes to fetch
    fetch_vars = [f"{code}E" for code in var_map.values()]
    state_code = GEO['STATE_CODE']
    counties   = list(GEO['BA_COUNTY_FIPS_CODES'].keys())

    # 2) Fetch with retries
    records = []
    for county in counties:
        for attempt in range(1, max_retries+1):
            try:
                logging.info(f"[STEP3] attempt {attempt} → fetching {fetch_vars} for tract in {state_code}/{county}")
                recs = retrieve_census_variables(
                    c, year, 'acs5', fetch_vars,
                    for_geo='tract', state=state_code, county=county
                )
                if not recs:
                    raise RuntimeError("empty response")
                records.extend(recs)
                break
            except Exception as e:
                logging.warning(f"[STEP3] county {county}, attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    raise RuntimeError(f"Failed after {max_retries} tries for {state_code}/{county}")
                time.sleep(backoff)

    # 3) Assemble DataFrame
    df = census_to_df(records)
    logging.info(f"[STEP3] raw df columns: {df.columns.tolist()}")

    # 4) Build the 11-digit tract code
    df['tract'] = (
        df['state'].astype(str).str.zfill(2)
      + df['county'].astype(str).str.zfill(3)
      + df['tract'].astype(str).str.zfill(6)
    )

    # 5) Pivot into your clean output
    out = pd.DataFrame({'tract': df['tract']})
    for out_name, code in var_map.items():
        colE = f"{code}E"
        if colE in df.columns:
            series = df[colE]
        elif code in df.columns:
            series = df[code]
        else:
            series = pd.Series(0, index=df.index)

        out[out_name] = (
            pd.to_numeric(series, errors='coerce')
              .fillna(0)
              .astype(int)
        )

    # DEBUG
    logging.info(f"[STEP3 DEBUG] var_map: {var_map}")
    logging.info(f"[STEP3 DEBUG] out columns: {out.columns.tolist()}")
    logging.info(f"[STEP3 DEBUG] out sample:\n{out.head(5)}")

    # 6) Crash if everything is zero
    if out.drop(columns='tract').values.sum() == 0:
        logging.error(f"[STEP3] ALL-ZEROS for year={year}, vars={list(var_map.keys())}")
        raise RuntimeError(f"ACS tract fetch for {year} returned all zeros — aborting")

    return out


def step4_fetch_dhc_tract(census_client):
    """Fetch DHC tract variables."""
    var_map = VARIABLES['DHC_TRACT_VARIABLES']
    rows = []

    for cnt in BAYCOUNTIES:
        resp = requests.get(
            f"https://api.census.gov/data/{DECENNIAL_YEAR}/dec/dhc",
            params={
                'get': ",".join(var_map.values()),
                'for': 'tract:*',
                'in': f"state:{STATE_CODE}+county:{cnt}",
                'key': CENSUS_API_KEY
            }
        )
        if resp.status_code == 200:
            data = resp.json()
            cols = data[0]
            rows.extend([dict(zip(cols, vals)) for vals in data[1:]])
        else:
            logger.error(f"Failed to fetch DHC for county {cnt}: {resp.status_code}")

    df = pd.DataFrame(rows)
    df['tract'] = df['state'].str.zfill(2) + df['county'].str.zfill(3) + df['tract'].str.zfill(6)
    for clean_name, api_code in var_map.items():
        df[clean_name] = pd.to_numeric(df[api_code], errors='coerce').fillna(0).astype(int)

    df['county_fips'] = df['county'].str.zfill(3)
    df['County_Name'] = df['county_fips'].map(GEO['BA_COUNTY_FIPS_CODES'])

    return df[['tract'] + list(var_map.keys()) + ['county_fips', 'County_Name']]
