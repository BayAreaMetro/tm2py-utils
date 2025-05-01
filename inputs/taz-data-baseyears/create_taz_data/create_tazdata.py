#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
create_taz_data.py

End-to-end TAZ data pipeline for Travel Model One and Two.
Loads all settings (constants, paths, geo, variable mappings) from config.yaml.
Defines 13 sequential steps, each stubbed out for implementation.
"""

# - Household- and population-based variables are based on the ACS5-year dataset which centers around the
#   given year, or the latest ACS5-year dataset that is available (see variable, ACS_5year). 
#   The script fetches this data using tidycensus.
#
# - ACS block group variables used in all instances where not suppressed. If suppressed at the block group 
#   level, tract-level data used instead. Suppressed variables may change if ACS_5year is changed. This 
#   should be checked, as this change could cause the script not to work.
#
# - Group quarter data is not available below state level from ACS, so 2020 Decennial census numbers
#   are used instead, and then scaled (if applicable)
#
# - Wage/Salary Employment data is sourced from LODES for the given year, or the latest LODES dataset that is available.
#   (See variable, LODES_YEAR)
# - Self-employed persons are also added from taz_self_employed_workers_[year].csv
# 
# - If ACS1-year data is available that is more recent than that used above, these totals are used to scale
#   the above at a county-level.
#
# - Employed Residents, which includes people who live *and* work in the Bay Area are quite different
#   between ACS and LODES, with ACS regional totals being much higher than LODES regional totals.
#   This script includes a parameter, EMPRES_LODES_WEIGHT, which can be used to specify a blended target
#   between the two.

import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
import requests
from census import Census


# ------------------------------
# Load configuration
# ------------------------------
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
      - tract : 11-digit GEOID (state+county+tract)
      - one column per VARIABLES['DHC_TRACT_VARIABLES'] key
    """
    import requests

    # 1) pick a valid decennial year
    dec_year = year if year in (2000, 2010, 2020) else DECENNIAL_YEAR

    # 2) map and API vars
    var_map  = VARIABLES.get('DHC_TRACT_VARIABLES', {})
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

    # 4) rename raw codes → clean var names
    df = df.rename(columns={code: name for name, code in var_map.items()})

    # 5) build the full 11-digit tract key
    df['tract'] = (
        df['state'].astype(str).str.zfill(2) +
        df['county'].astype(str).str.zfill(3) +
        df['tract'].astype(str).str.zfill(6)
    )

    # 6) pull out just tract + DHC vars, coercing to int
    out = pd.DataFrame({'tract': df['tract']})
    for name in var_map.keys():
        out[name] = (
            pd.to_numeric(df[name], errors='coerce')
              .fillna(0)
              .astype(int)
        )

    return out


# ------------------------------
# STEP 5: Disaggregate ACS BG vars to block level
# ------------------------------
def step5_compute_block_shares(df_blk, df_bg):
    """
    Disaggregate ACS block-group vars to blocks using block-population share.
    Expects:
      - df_blk has 'block_geoid' (15-digit) and 'pop'
      - df_bg has 'blockgroup' (12-digit) plus ACS_BG_VARIABLES keys
    Returns:
      ['block_geoid','blockgroup'] + ACS_BG_VARIABLES keys + ['pop_share']
    """
    # 1) Copy & promote the BG codes from your ACS table
    df_bg2 = df_bg.copy()
    if 'blockgroup' not in df_bg2.columns:
        raise KeyError("step5: missing 'blockgroup' in ACS BG data")
    df_bg2['BG_GEOID'] = df_bg2['blockgroup']

    # 2) Start from block-level pop
    df = df_blk.copy()
    if 'block_geoid' not in df.columns:
        raise KeyError("step5: missing 'block_geoid' in block data")
    # first 12 digits of block_geoid give blockgroup
    df['BG_GEOID'] = df['block_geoid'].astype(str).str[:12]

    # 3) Compute blockgroup total pop & shares
    bg_pop = (
        df.groupby('BG_GEOID')['pop']
          .sum()
          .reset_index()
          .rename(columns={'pop':'bg_pop'})
    )
    df = df.merge(bg_pop, on='BG_GEOID', how='left')
    df['pop_share'] = df['pop'] / df['bg_pop'].replace({0:1})

    logging.info(
        "Block share sample:\n%s",
        df[['block_geoid','pop','bg_pop','pop_share']].head()
    )

    # 4) Merge in ACS block-group variables
    df = df.merge(df_bg2, on='BG_GEOID', how='left')
    bg_vars = list(VARIABLES['ACS_BG_VARIABLES'].keys())
    logging.info(
        "ACS BG values at first block:\n%s",
        df[bg_vars].iloc[0]
    )

    # 5) Disaggregate each ACS var
    for var in bg_vars:
        df[var] = df['pop_share'] * df[var].fillna(0)

    # 6) Rename BG_GEOID back to blockgroup for step6
    df['blockgroup'] = df['BG_GEOID']

    return df[['block_geoid','blockgroup'] + bg_vars + ['pop_share']]

def step6_build_workingdata(shares, acs_tr, dhc_tr):
    """
    Merge block‐level shares (with ACS‐BG vars) + ACS‐tract + DHC‐tract
    into a “working” block table. Keeps all original shares columns.
    """
    # a) Copy to avoid fragmentation warnings
    df_work = shares.copy()

    # b) Ensure blockgroup (12d) and tract (11d)
    df_work['blockgroup'] = df_work['blockgroup'].astype(str).str.zfill(12)
    df_work['tract']      = df_work['blockgroup'].str[:11]

    logger = logging.getLogger(__name__)
    logger.info(f"step6 inputs ▶ shares={df_work.shape}, acs_tr={acs_tr.shape}, dhc_tr={dhc_tr.shape}")

    # c) Merge ACS‐tract (11d key)
    m2 = df_work.merge(acs_tr, on='tract', how='left', indicator='tr_merge')
    logger.info(f"tr_merge counts → {m2['tr_merge'].value_counts().to_dict()}")
    df_work = m2.drop(columns=['tr_merge'])

    # d) Merge DHC‐tract (11d key)
    m3 = df_work.merge(dhc_tr, on='tract', how='left', indicator='dhc_merge')
    logger.info(f"dhc_merge counts → {m3['dhc_merge'].value_counts().to_dict()}")
    df_final = m3.drop(columns=['dhc_merge'])

    logger.info(f"step6 output shape ▶ {df_final.shape}")
    return df_final



# ------------------------------
# STEP 7: Map ACS income bins to TM1 quartiles
# ------------------------------
def step7_process_household_income(df_working, year=ACS_5YR_LATEST):
    """
    Allocate ACS block-group income bins into TM1 HHINCQ1–4 by share.
    Returns a DataFrame with:
      - blockgroup : 12-digit FIPS
      - HHINCQ1..HHINCQ4 : int
    """
    mapping = map_acs5year_household_income_to_tm1_categories(year)
    # 1) Build raw‐code → working‐col map, but only keep those actually in df_working
    code_to_col = {}
    for new_var, old_code in VARIABLES['ACS_BG_VARIABLES'].items():
        # only pick the B19001 bins
        if not old_code.startswith("B19001_"):
            continue
        if new_var in df_working.columns:
            code_to_col[old_code] = new_var
        else:
            logging.warning(f"step7: ACS_BG_VARIABLES defines '{new_var}' but working DF lacks that column")

    # 2) Kick off output keyed on blockgroup
    if "blockgroup" not in df_working.columns:
        raise KeyError("step7: working DF missing 'blockgroup'")
    out = pd.DataFrame({"blockgroup": df_working["blockgroup"]})
    for q in (1,2,3,4):
        out[f"HHINCQ{q}"] = 0.0

    # 3) Apply shares
    for _, row in mapping.iterrows():
        acs_code = row["incrange"]           # e.g. "B19001_002"
        q        = int(row["HHINCQ"])
        share    = float(row["share"])
        col      = code_to_col.get(acs_code)
        if col is None:
            logging.warning(f"step7: no working‐column mapped for ACS code {acs_code}")
            continue
        out[f"HHINCQ{q}"] += df_working[col].fillna(0) * share

    # 4) Round and cast
    for q in (1,2,3,4):
        out[f"HHINCQ{q}"] = out[f"HHINCQ{q}"].round().astype(int)
    return out




# ------------------------------
# Step 8: Weighted summarize block-group ACS -> TAZ
# ------------------------------
def compute_block_weights(paths):
    cw_path = Path(__file__).parent / Path(paths['block2020_to_taz1454_csv'])
    df = pd.read_csv(cw_path, dtype={'blockgroup':str})
    df['block_POPULATION'] = pd.to_numeric(df['block_POPULATION'],errors='coerce').fillna(0)
    df['group_pop'] = df.groupby('blockgroup')['block_POPULATION'].transform('sum')
    df['weight'] = df['block_POPULATION'] / df['group_pop']
    return df[['GEOID','blockgroup','TAZ1454','weight']]

def step8_summarize_to_taz(df_bg, df_weights):
    acs_vars = [c for c in df_bg.columns if c!='blockgroup']
    df = df_weights.merge(df_bg, left_on='blockgroup', right_on='blockgroup', how='left')
    for var in acs_vars:
        df[var] = df[var] * df['weight']
    return df.groupby('TAZ1454')[acs_vars].sum().reset_index()

# ------------------------------
# Steps 9a/9b: Tract -> TAZ summarize
# ------------------------------
def compute_tract_weights(paths):
    """
    Load the tract-to-TAZ crosswalk and compute normalized weights for each tract.
    Expects:
      paths['taz_crosswalk'] → CSV with at least: tract, TAZ, and a weight/pop_share column.
    Returns a DataFrame with columns ['tract', 'taz', 'weight'], where weights sum to 1 per tract.
    """
    # 1) Locate and read the crosswalk CSV
    cw_path = Path(os.path.expandvars(paths['taz_crosswalk']))
    df = pd.read_csv(cw_path, dtype=str)
    
    # 2) Normalize column names to simplify matching
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    
    # 3) Identify the tract, taz, and weight columns
    tract_col  = next(col for col in df.columns if 'tract' in col)
    taz_col    = next(col for col in df.columns if 'taz'   in col)
    # common weight names: 'weight', 'pop_share', 'share'
    weight_col = next(col for col in df.columns if any(k in col for k in ('weight','pop_share','share')))
    
    # 4) Coerce weight to numeric and normalize so each tract sums to 1
    df[weight_col] = pd.to_numeric(df[weight_col], errors='coerce').fillna(0)
    df['weight']  = df.groupby(tract_col)[weight_col].transform(lambda x: x / x.sum())
    
    # 5) Return only the three standardized columns
    return df[[tract_col, taz_col, 'weight']].rename(
        columns={tract_col: 'tract', taz_col: 'taz'}
    )

def step9_summarize_tract_to_taz(df_acs_tr, df_weights_tract):
    # 1) Merge ACS tract data with tract→TAZ weights
    df = df_weights_tract.merge(df_acs_tr, on='tract', how='left')

    # 2) Identify which columns to aggregate
    aggs = [col for col in df.columns if col not in ['tract', 'taz', 'weight']]

    # 3) Make sure every aggregation column is numeric
    df[aggs] = df[aggs].apply(pd.to_numeric, errors='coerce').fillna(0)

    # 4) Weight each ACS variable by the tract→TAZ fraction
    for var in aggs:
        df[var] = df[var] * df['weight']

    # 5) Group by TAZ and sum up weighted variables
    df_taz = df.groupby('taz', as_index=False)[aggs].sum()

    return df_taz

import os
import pandas as pd

def step10_integrate_employment(year):
    """
    Integrate LODES WAC employment and self‐employed counts at the TAZ level.
    
    Falls back to using TOTEMP if the LODES file is already at TAZ granularity,
    otherwise performs block-to-TAZ crosswalk.
    """
    # --- 1) Read LODES file ---
    lodes_path = os.path.expandvars(PATHS['lodes_employment_csv'])
    df_lodes   = pd.read_csv(lodes_path, dtype=str)
    cols = df_lodes.columns.tolist()

    # --- 2) If already TAZ‐level, shortcut ---
    if 'TAZ1454' in cols and 'TOTEMP' in cols:
        df_emp_lodes = (
            df_lodes
            .rename(columns={'TAZ1454':'taz','TOTEMP':'emp_lodes'})
            [['taz','emp_lodes']]
        )
        df_emp_lodes['emp_lodes'] = pd.to_numeric(
            df_emp_lodes['emp_lodes'], errors='coerce'
        ).fillna(0)
    else:
        # 2a) Block‐to‐TAZ crosswalk
        cw = pd.read_csv(os.path.expandvars(PATHS['block2020_to_taz1454_csv']), dtype=str)
        # detect block & taz columns
        block_col = next(c for c in cw.columns if 'block' in c.lower())
        taz_col   = next(c for c in cw.columns if 'taz'   in c.lower())
        cw = cw[[block_col, taz_col]].rename(columns={block_col:'block', taz_col:'taz'})

        # 2b) Find geocode & employment columns in raw WAC
        geo_col = next((c for c in cols if 'geocode' in c.lower()), None)
        if not geo_col:
            raise KeyError(f"No geocode column in LODES; found {cols!r}")
        emp_col = next((c for c in cols if c.upper()=='C000'), None)
        if emp_col is None:
            emp_col = next((c for c in cols if c.lower().startswith('c')), None)
        if emp_col is None:
            raise KeyError(f"No employment column in LODES; found {cols!r}")

        # 2c) Trim to blocks, coerce, merge, sum to TAZ
        df_lodes['block']      = df_lodes[geo_col].str[:12]
        df_lodes[emp_col]      = pd.to_numeric(df_lodes[emp_col], errors='coerce').fillna(0)
        df_lodes               = df_lodes.merge(cw, on='block', how='left')
        df_emp_lodes = (
            df_lodes
            .groupby('taz', as_index=False)[emp_col]
            .sum()
            .rename(columns={emp_col:'emp_lodes'})
        )

    # --- 3) Read self‐employed file ---
    se = pd.read_csv(os.path.expandvars(PATHS['self_employed_csv']), dtype=str)
    se_cols = se.columns.tolist()
    # detect TAZ column in self‐emp file
    se_taz = next(
        (c for c in se_cols if 'taz' in c.lower() or 'zone' in c.lower()),
        None
    )
    if not se_taz:
        raise KeyError(f"No TAZ/zone column in self‐emp; found {se_cols!r}")
    se_val = next(c for c in se_cols if c != se_taz)

    df_se = (
        se.rename(columns={se_taz:'taz', se_val:'emp_self'})
          .assign(emp_self=lambda df: pd.to_numeric(df['emp_self'], errors='coerce').fillna(0))
          [['taz','emp_self']]
    )

    # --- 4) Merge the two employment sources ---
    df_emp = df_emp_lodes.merge(df_se, on='taz', how='outer').fillna(0)
    df_emp['taz'] = df_emp['taz'].astype(str)

    return df_emp


def step11_build_county_targets(df_taz, paths):
    """
    Scale TAZ‐level outputs so they match county‐level control totals.

    Parameters
    ----------
    df_taz : pandas.DataFrame
        Must have a 'taz' column plus all the variables you want to scale.
    paths : dict
        Must include:
          - 'taz_sd_county_csv': path to a CSV mapping each TAZ to its county
          - 'county_targets_csv': path to a CSV of county‐level control totals,
            with one row per county and the same variable columns as df_taz

    Returns
    -------
    pandas.DataFrame
        Same as df_taz, but with every variable re‐weighted so that if you do
        df.groupby('county')[vars].sum(), you get exactly the county_targets.
    """

    # 1) load the TAZ→county crosswalk and pick out the two key columns
    cw = pd.read_csv(os.path.expandvars(paths['taz_sd_county_csv']), dtype=str)
    # normalize names
    cw.columns = cw.columns.str.lower().str.replace(' ', '_')
    taz_col    = next(c for c in cw.columns if 'taz'    in c)
    county_col = next(c for c in cw.columns if 'county' in c)
    cw = cw[[taz_col, county_col]].rename(
        columns={taz_col: 'taz', county_col: 'county'}
    )

    # 2) attach county onto each TAZ row
    df = df_taz.merge(cw, on='taz', how='left')

    # 3) read in your county‐level targets
    df_ct = pd.read_csv(os.path.expandvars(paths['county_targets_csv']), dtype=str)
    # ensure the county ID column is named 'county' as well
    if 'county' not in df_ct.columns:
        ct_id = next(c for c in df_ct.columns if 'county' in c.lower())
        df_ct = df_ct.rename(columns={ct_id: 'county'})
    # coerce all the control total columns to numeric
    vars_to_scale = [c for c in df_ct.columns if c != 'county']
    df_ct[vars_to_scale] = df_ct[vars_to_scale]\
        .apply(pd.to_numeric, errors='coerce')\
        .fillna(0)

    # 4) call the common helper to do the proportional scaling
    #    (it will group by 'county', compare sums in df vs. df_ct, 
    #     and multiply each TAZ row by the appropriate factor)
    df_scaled = update_tazdata_to_county_target(
        df,          # your merged TAZ+county table
        df_ct,       # the county‐control‐totals table
        id_col='taz',
        county_col='county'
    )

    return df_scaled

def step12_apply_scaling(taz: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """
    Apply county‐level control totals to a TAZ‐level table by computing
    and applying proportional scaling factors.

    Parameters
    ----------
    taz : pandas.DataFrame
        Must contain:
          - a 'county' column
          - one or more numeric variable columns to be scaled.
    targets : pandas.DataFrame
        Must contain:
          - the same 'county' column
          - one column per variable with the target total for that county.

    Returns
    -------
    pandas.DataFrame
        A copy of `taz` where each variable has been multiplied by a county‐
        specific factor so that grouping back to county yields exactly the
        `targets` values.
    """
    # 1) Identify variables to scale (everything except 'county')
    vars_to_scale = [c for c in taz.columns if c != 'county']

    # 2) Compute actual sums by county
    actual = (
        taz
        .groupby('county', as_index=False)[vars_to_scale]
        .sum()
        .rename(columns={v: f"{v}_actual" for v in vars_to_scale})
    )

    # 3) Prepare the targets table
    tgt = targets[['county'] + vars_to_scale]\
          .rename(columns={v: f"{v}_target" for v in vars_to_scale})

    # 4) Merge actuals and targets to get scale factors
    factors = tgt.merge(actual, on='county')
    for v in vars_to_scale:
        # avoid division by zero
        factors[f"{v}_factor"] = (
            factors[f"{v}_target"]
            / factors[f"{v}_actual"].replace({0: np.nan})
        ).fillna(1)
    
    # 5) Attach factors back to each TAZ row
    factor_cols = ['county'] + [f"{v}_factor" for v in vars_to_scale]
    df = taz.merge(factors[factor_cols], on='county', how='left')

    # 6) Apply scaling
    for v in vars_to_scale:
        df[v] = df[v] * df[f"{v}_factor"]

    # 7) Drop the factor columns
    df = df.drop(columns=[f"{v}_factor" for v in vars_to_scale])

    return df

def step13_join_pba2015(df_taz):
    """
    Join your TAZ-level outputs to the Plan Bay Area 2015 TAZ data
    (land-use/blueprint) so you can carry those attributes forward.

    Parameters
    ----------
    df_taz : pandas.DataFrame
        Must contain a 'taz' column (string or numeric).

    Returns
    -------
    pandas.DataFrame
        All columns from df_taz plus all columns from the PBA2015 file,
        merged on the TAZ identifier.
    """
    # 1) load the PBA 2015 TAZ data
    pba_path = os.path.expandvars(PATHS['pba_taz_2015'])
    df_pba  = pd.read_excel(pba_path, dtype=str)
    
    # 2) detect the TAZ column in the PBA file
    pba_cols = df_pba.columns.tolist()
    taz_col = next(c for c in pba_cols if 'taz' in c.lower())
    
    # 3) standardize the name and type
    df_pba = df_pba.rename(columns={taz_col: 'taz'})
    df_pba['taz'] = df_pba['taz'].astype(str)
    
    # 4) ensure df_taz.taz is string
    df_taz = df_taz.copy()
    df_taz['taz'] = df_taz['taz'].astype(str)
    
    # 5) merge
    df_out = df_taz.merge(df_pba, on='taz', how='left')
    
    return df_out

def step14_write_outputs(taz: pd.DataFrame, year: int) -> None:
    """
    Write out the same suite of CSVs that the original R script did,
    using the fully-joined TAZ‐level DataFrame `taz`.
    """
    # 1) Prepare output directory
    out_root = os.path.expandvars(PATHS['output_root'])
    year_dir = os.path.join(out_root, str(year))
    os.makedirs(year_dir, exist_ok=True)

    # 2) --- Ethnicity ---
    ethnic = taz[[
        'TAZ1454',
        'hispanic','white_nonh','black_nonh','asian_nonh','other_nonh',
        'TOTPOP','COUNTY','County_Name'
    ]]
    ethnic_path = os.path.join(year_dir, "TAZ1454_Ethnicity.csv")
    ethnic.to_csv(ethnic_path, index=False)
    logging.info(f"Wrote {ethnic_path}")

    # 3) --- TAZ Land Use file ---
    taz_landuse = taz.copy()
    taz_landuse['hhlds'] = taz_landuse['TOTHH']
    landuse_cols = [
        'TAZ1454','DISTRICT','SD','COUNTY','TOTHH','HHPOP','TOTPOP','EMPRES',
        'SFDU','MFDU','HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4','TOTACRE',
        'RESACRE','CIACRE','SHPOP62P','TOTEMP','AGE0004','AGE0519','AGE2044',
        'AGE4564','AGE65P','RETEMPN','FPSEMPN','HEREMPN','AGREMPN','MWTEMPN',
        'OTHEMPN','PRKCST','OPRKCST','AREATYPE','HSENROLL','COLLFTE','COLLPTE',
        'TERMINAL','TOPOLOGY','ZERO','hhlds','gqpop'
    ]
    landuse = taz_landuse[landuse_cols]
    landuse_path = os.path.join(year_dir, f"TAZ1454_{year}_Land Use.csv")
    landuse.to_csv(landuse_path, index=False, quotechar='"')
    logging.info(f"Wrote {landuse_path}")

    # 4) --- District summary for 2015 (from PBA2015 sheet) ---
    pba = pd.read_excel(
        os.path.expandvars(PATHS['pba_taz_2015']),
        sheet_name="census2015",
        dtype=str
    )
    num_vars = [
        'TOTHH','HHPOP','TOTPOP','EMPRES','SFDU','MFDU',
        'HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4','TOTEMP',
        'AGE0004','AGE0519','AGE2044','AGE4564','AGE65P',
        'RETEMPN','FPSEMPN','HEREMPN','AGREMPN','MWTEMPN',
        'OTHEMPN','HSENROLL','COLLFTE','COLLPTE'
    ]
    for v in num_vars:
        pba[v] = pd.to_numeric(pba[v], errors='coerce').fillna(0)
    pba['gqpop'] = pba['TOTPOP'] - pba['HHPOP']
    summary_2015 = (
        pba
        .groupby('DISTRICT', as_index=False)[ num_vars + ['TOTPOP','gqpop'] ]
        .sum()
    )
    path_2015 = os.path.join(year_dir, f"TAZ1454_2015_District Summary.csv")
    summary_2015.to_csv(path_2015, index=False, quotechar='"')
    logging.info(f"Wrote {path_2015}")

    # 5) --- District summary for target year ---
    # re‐use our taz_landuse table as the “census” base
    df = taz_landuse.copy()
    for v in num_vars + ['gqpop']:
        df[v] = pd.to_numeric(df[v], errors='coerce').fillna(0)
    summary_year = (
        df
        .groupby('DISTRICT', as_index=False)[ num_vars + ['TOTPOP','gqpop'] ]
        .sum()
    )
    path_year = os.path.join(year_dir, f"TAZ1454_{year}_District Summary.csv")
    summary_year.to_csv(path_year, index=False, quotechar='"')
    logging.info(f"Wrote {path_year}")

    # 6) --- Popsim Vars ---
    pops = taz.rename(columns={'TAZ1454':'TAZ','gqpop':'gq_tot_pop'})[[
        'TAZ','TOTHH','TOTPOP','hh_own','hh_rent',
        'hh_size_1','hh_size_2','hh_size_3','hh_size_4_plus',
        'hh_wrks_0','hh_wrks_1','hh_wrks_2','hh_wrks_3_plus',
        'hh_kids_no','hh_kids_yes',
        'HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4',
        'AGE0004','AGE0519','AGE2044','AGE4564','AGE65P',
        'gq_tot_pop','gq_type_univ','gq_type_mil','gq_type_othnon'
    ]]
    pops_path = os.path.join(year_dir, f"TAZ1454_{year}_Popsim Vars.csv")
    pops.to_csv(pops_path, index=False, quotechar='"')
    logging.info(f"Wrote {pops_path}")

    # 7) --- Region‐level Popsim Vars ---
    region = pops.copy()
    region['REGION'] = 1
    region_sum = region.groupby('REGION', as_index=False)[ 'gq_tot_pop' ].sum()
    region_path = os.path.join(year_dir, f"TAZ1454_{year}_Popsim Vars Region.csv")
    region_sum.rename(columns={'gq_tot_pop':'gq_num_hh_region'}) \
              .to_csv(region_path, index=False, quotechar='"')
    logging.info(f"Wrote {region_path}")

    # 8) --- County‐level Popsim Vars ---
    county_pop = pops.rename(columns={'TAZ':'ignored'}) \
        .groupby('COUNTY', as_index=False).agg({
            'gq_type_univ':'sum','gq_type_mil':'sum','gq_type_othnon':'sum'
        })
    # you can expand with any other pers_occ_... sums here
    county_path = os.path.join(year_dir, f"TAZ1454_{year}_Popsim Vars County.csv")
    county_pop.to_csv(county_path, index=False, quotechar='"')
    logging.info(f"Wrote {county_path}")

    # 9) --- Tableau‐friendly long for 2015 ---
    # we'll need your TAZ→SD→County_Name→DISTRICT_NAME crosswalk
    xw = pd.read_csv(os.path.expandvars(PATHS['taz_sd_county_csv']), dtype=str)
    xw = xw.rename(columns=lambda c: c.strip()).loc[:, ['ZONE','County_Name','DISTRICT_NAME']]
    pba_long = (
        pba
        .assign(gqpop=lambda df: df['TOTPOP'] - df['HHPOP'], Year=2015)
        .merge(xw, on='ZONE', how='left')
        .melt(
            id_vars=['ZONE','DISTRICT','DISTRICT_NAME','COUNTY','County_Name','Year'],
            value_vars=num_vars + ['SHPOP62P','TOTEMP','AGE0004','AGE0519','AGE2044','AGE4564','AGE65P','RETEMPN','FPSEMPN','HEREMPN','AGREMPN','MWTEMPN','OTHEMPN','PRKCST','OPRKCST','HSENROLL','COLLFTE','COLLPTE','gqpop'],
            var_name='Variable',
            value_name='Value'
        )
    )
    long15_path = os.path.join(year_dir, f"TAZ1454_2015_long.csv")
    pba_long.to_csv(long15_path, index=False, quotechar='"')
    logging.info(f"Wrote {long15_path}")

    # 10) --- Tableau‐friendly long for target year ---
    census_long = (
        taz
        .assign(Year=year)
        .melt(
            id_vars=['TAZ1454','DISTRICT','DISTRICT_NAME','COUNTY','County_Name','Year'],
            value_vars=num_vars + ['SHPOP62P','TOTEMP','AGE0004','AGE0519','AGE2044','AGE4564','AGE65P','RETEMPN','FPSEMPN','HEREMPN','AGREMPN','MWTEMPN','OTHEMPN','PRKCST','OPRKCST','HSENROLL','COLLFTE','COLLPTE','gqpop'],
            var_name='Variable',
            value_name='Value'
        )
    )
    longyr_path = os.path.join(year_dir, f"TAZ1454_{year}_long.csv")
    census_long.to_csv(longyr_path, index=False, quotechar='"')
    logging.info(f"Wrote {longyr_path}")

# ------------------------------
# Logging and Census client
# ------------------------------

def setup_logging(year):
    out_dir = Path(os.path.expandvars(PATHS['output_root']).replace('${YEAR}', str(year)))
    out_dir.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(), logging.FileHandler(out_dir / f'create_tazdata_{year}.log')]
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=handlers)

def setup_census_client():
    api_key = Path(os.path.expandvars(PATHS['census_api_key_file'])).read_text().strip()
    return Census(api_key)

# ------------------------------
# Main pipeline
# ------------------------------
def main():

    setup_logging(YEAR)
    
    logging.info(f"Starting TAZ pipeline for YEAR={YEAR}")
    
    c = setup_census_client()

    outputs = {}
    outputs['blocks']    = step1_fetch_block_data(c, YEAR)
    outputs['acs_bg']    = step2_fetch_acs_bg(c, YEAR)
    outputs['acs_tr']    = step3_fetch_acs_tract(c, min(YEAR+2, ACS_5YR_LATEST))
    outputs['dhc_tr']    = step4_fetch_dhc_tract(c)
    outputs['shares']    = step5_compute_block_shares(outputs['blocks'], outputs['acs_bg'])
    outputs['working']   = step6_build_workingdata(
        outputs['shares'],  outputs['acs_tr'], outputs['dhc_tr']
    )
    outputs['hhinc']     = step7_process_household_income(outputs['working'], ACS_5YR_LATEST)
    outputs['weights']   = compute_block_weights(PATHS)
    df_bg = outputs['hhinc'].rename(columns={'GEOID':'blockgroup'})
    outputs['taz']       = step8_summarize_to_taz(df_bg, outputs['weights'])
    outputs['weights_tract'] = compute_tract_weights(PATHS)
    outputs['taz_tract']    = step9_summarize_tract_to_taz(
        outputs['acs_tr'], outputs['weights_tract']
    )
    outputs['taz'] = outputs['taz'].rename(columns={'TAZ1454': 'taz'})
    outputs['taz']['taz']       = outputs['taz']['taz'].astype(str)
    outputs['taz_tract']['taz'] = outputs['taz_tract']['taz'].astype(str)
    outputs['taz_final'] = outputs['taz'].merge(outputs['taz_tract'], on ='taz', how='left')

    outputs['emp'] = step10_integrate_employment(YEAR)

    # merge into your TAZ summary table
    # assuming outputs['taz'] has a column 'taz'
    outputs['taz_final'] = outputs['taz'].merge(outputs['emp'], on='taz', how='left')

# fill any missing employment with zero
    outputs['taz_final'][['emp_lodes','emp_self']] = (
    outputs['taz_final'][['emp_lodes','emp_self']].fillna(0))
    outputs['taz_targeted'] = step11_build_county_targets(
    outputs['taz_final'],  # your TAZ‐level table (with 'taz' column)
    PATHS)                  # the dict of file paths)
    outputs['scaled']    = step12_apply_scaling(outputs['taz'], outputs['targets'])
    outputs['taz_with_pba2015'] = step13_join_pba2015(outputs['taz_targeted'])
    step14_write_outputs(outputs['taz_with_pba2015'], YEAR)

    logging.info("TAZ data processing complete.")

if __name__ == '__main__':
    main()