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
def step1_fetch_block_data(c, year):
    df_raw = download_acs_blocks(c, year, 'dec/pl')
    if df_raw.empty:
        logging.error('No block data retrieved; exiting.')
        sys.exit(1)
    df = census_to_df(df_raw)
    # rename population field
    if 'P1_001N' in df.columns:
        df = df.rename(columns={'P1_001N': 'pop'})
    else:
        logging.error('Expected P1_001N not found in block data')
        sys.exit(1)
    df['pop'] = pd.to_numeric(df['pop'], errors='coerce').fillna(0).astype(int)
    return df[['GEOID', 'pop']]

# ------------------------------
# STEP 2: Fetch ACS block-group variables
# ------------------------------
def step2_fetch_acs_bg(c, year):
    var_map    = VARIABLES['ACS_BG_VARIABLES']
    state_code = GEO['STATE_CODE']
    counties   = GEO['BA_COUNTY_FIPS_CODES']
    # batch into <=45 per request
    items      = list(var_map.items())
    batches    = [items[i:i+45] for i in range(0, len(items), 45)]
    df_chunks = []
    for batch in batches:
        fetch_vars = [f"{code}E" for (_, code) in batch]
        rename_map = {f"{code}E": name for (name, code) in batch}
        records = []
        for county in counties:
            try:
                recs = retrieve_census_variables(
                    c, year, 'acs5', fetch_vars,
                    for_geo='block group', state=state_code, county=county
                )
            except Exception as e:
                logging.warning(f"County {county} failed: {e}")
                continue
            records.extend(recs)
        if not records:
            continue
        df_batch = census_to_df(records).rename(columns=rename_map)
        df_chunks.append(df_batch)
    if not df_chunks:
        logging.error('No ACS block-group data fetched.')
        return pd.DataFrame()
    # merge all batches on geo cols
    geo_cols = ['state','county','tract','block group']
    df = df_chunks[0]
    for df_next in df_chunks[1:]:
        df = df.merge(df_next, on=geo_cols, how='outer')
    # coerce each var to int
    for out in var_map.keys():
        if out in df.columns:
            df[out] = pd.to_numeric(df[out], errors='coerce').fillna(0).astype(int)
        else:
            df[out] = 0
    return df

# ------------------------------
# STEP 3: Fetch ACS tract variables
# ------------------------------
def step3_fetch_acs_tract(c, year=YEAR):
    var_map      = VARIABLES.get('ACS_TRACT_VARIABLES', {})
    if not var_map:
        raise ValueError('CONFIG ERROR: ACS_TRACT_VARIABLES empty')
    fetch_vars   = [f"{code}E" for code in var_map.values()]
    state_code   = GEO['STATE_CODE']
    counties     = list(GEO['BA_COUNTY_FIPS_CODES'].keys())
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
    # ensure all cols exist and numeric
    for out in var_map.keys():
        if out not in df.columns:
            df[out] = 0
        df[out] = pd.to_numeric(df[out], errors='coerce').fillna(0).astype(int)
    return df

# Step 4: Fetch DHC tract variables (Detailed Housing Characteristics)
# ------------------------------
def step4_fetch_dhc_tract(c, year=DECENNIAL_YEAR):
    """
    Download decennial DHC variables for tracts. Raises if no data.
    Returns DataFrame with columns ['GEOID', <DHC vars>].
    """
    # choose valid decennial year
    dec_year = year if year in (2000, 2010, 2020) else DECENNIAL_YEAR
    var_map = VARIABLES.get('DHC_TRACT_VARIABLES', {})
    if not var_map:
        raise ValueError("CONFIG ERROR: DHC_TRACT_VARIABLES is empty in config.yaml")
    fetch_vars = list(var_map.values())
    state = GEO['STATE_CODE']
    counties = list(GEO['BA_COUNTY_FIPS_CODES'].keys())

    records = []
    for cnt in counties:
        try:
            recs = retrieve_census_variables(
                c, dec_year, 'dec/dhc', fetch_vars,
                for_geo='tract', state=state, county=cnt
            )
            records.extend(recs)
        except Exception as e:
            logging.error(f"DHC fetch failed for county {cnt}: {e}")
    if not records:
        raise RuntimeError(f"No DHC records fetched for decennial year {dec_year}; aborting.")

    df = census_to_df(records)
    # rename according to var_map
    df = df.rename(columns={code: name for name, code in var_map.items()})
    # ensure GEOID column exists
    if 'GEOID' not in df.columns:
        if all(k in df.columns for k in ['state','county','tract']):
            df['GEOID'] = df['state'] + df['county'] + df['tract']
        else:
            raise KeyError("Cannot build GEOID: missing components and no GEOID field in DHC output.")
    return df


# ------------------------------
# STEP 5: Disaggregate ACS BG vars to block level
# ------------------------------
def step5_compute_block_shares(df_blk, df_bg):
    # Ensure block-group GEOID exists in df_bg
    df_bg = df_bg.copy()
    if 'GEOID' in df_bg.columns:
        df_bg = df_bg.rename(columns={'GEOID': 'BG_GEOID'})
    else:
        # build BG_GEOID from components
        df_bg['BG_GEOID'] = (
            df_bg['state'] + df_bg['county'] +
            df_bg['tract'] + df_bg['block group']
        )
    # Prepare the block-level DataFrame
    df = df_blk.copy()
    df['BG_GEOID'] = df['GEOID'].str[:12]
    # Compute total population per block group
    bg_pop = df.groupby('BG_GEOID')['pop'].sum().reset_index().rename(columns={'pop': 'bg_pop'})
    df = df.merge(bg_pop, on='BG_GEOID', how='left')
    # Compute share and handle zero-pop block groups
    df['pop_share'] = (df['pop'] / df['bg_pop'].replace({0: 1})).fillna(0)
    # Merge in block-group ACS estimates
    df = df.merge(df_bg, on='BG_GEOID', how='left')
    bg_vars = list(VARIABLES['ACS_BG_VARIABLES'].keys())
    # Disaggregate each ACS variable
    for var in bg_vars:
        df[var] = (df['pop_share'] * df[var].fillna(0)).round().astype(int)
    return df[['GEOID'] + bg_vars]
# ------------------------------
# STEP 6: Build working dataset at block geography
# ------------------------------
def step6_build_workingdata(df_shares, df_bg, df_tr, df_dhc):
    """
    Combine block-level shares with tract and DHC data.
    Diagnostic prints added to inspect df_dhc structure.
    """
    df = df_shares.copy()
    # extract block geographies
    df['state'] = df['GEOID'].str[:2]
    df['county'] = df['GEOID'].str[2:5]
    df['tract'] = df['GEOID'].str[5:11]
    df['block_group'] = df['GEOID'].str[11:12]
    df['block'] = df['GEOID'].str[12:]

    # DEBUG: inspect df_tr and df_dhc columns
    print("DF_TR columns:", df_tr.columns.tolist())
    print("DF_DHC columns:", df_dhc.columns.tolist())

    # Ensure tract table has 'GEOID' or state/county/tract
    df_tr2 = df_tr.copy()
    if 'GEOID' in df_tr2.columns:
        df_tr2['state'] = df_tr2['GEOID'].str[:2]
        df_tr2['county'] = df_tr2['GEOID'].str[2:5]
        df_tr2['tract'] = df_tr2['GEOID'].str[5:11]
    # merge tract ACS
    df = df.merge(df_tr2, on=['state','county','tract'], how='left', suffixes=('','_tr'))

    # Ensure DHC table has 'GEOID' or state/county/tract
    df_dhc2 = df_dhc.copy()
    if 'GEOID' in df_dhc2.columns:
        df_dhc2['state'] = df_dhc2['GEOID'].str[:2]
        df_dhc2['county'] = df_dhc2['GEOID'].str[2:5]
        df_dhc2['tract'] = df_dhc2['GEOID'].str[5:11]
    else:
        # if no GEOID, assume it already has state/county/tract
        missing = [c for c in ['state','county','tract'] if c not in df_dhc2.columns]
        if missing:
            raise KeyError(f"DHC missing columns: {missing}. Columns present: {df_dhc2.columns.tolist()}")
    # merge DHC
    df = df.merge(df_dhc2, on=['state','county','tract'], how='left', suffixes=('','_dhc'))

    # drop any duplicate GEOID columns
    for col in ['GEOID_tr','GEOID_dhc']:
        if col in df.columns:
            df = df.drop(columns=[col])

    # fill numeric NAs
    num_cols = df.select_dtypes(include='number').columns
    df[num_cols] = df[num_cols].fillna(0)

    return df



# ------------------------------
# STEP 7: Map ACS income bins to TM1 quartiles
# ------------------------------
def step7_process_household_income(working, year=ACS_5YR_LATEST):
    geoid_col = next((c for c in working.columns if 'geoid' in c.lower()), None)
    if geoid_col is None:
        raise KeyError('No GEOID column in working DF')
    map_df = map_acs5year_household_income_to_tm1_categories(year)
    code_to_var = {code: name for name, code in VARIABLES['ACS_BG_VARIABLES'].items()}
    out = pd.DataFrame({'GEOID': working[geoid_col]})
    for q in sorted(map_df['HHINCQ'].unique()):
        out[f'hhincq{q}'] = 0
    for _, row in map_df.iterrows():
        code, quart, share = row['incrange'], row['HHINCQ'], row['share']
        col = code_to_var.get(code)
        if col in working.columns:
            out[f'hhincq{quart}'] += working[col].fillna(0) * share
    for col in out.columns:
        if col.startswith('hhincq'):
            out[col] = out[col].round().astype(int)
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
    cw_path = Path(__file__).parent / Path(paths['taz_crosswalk'])
    df = pd.read_csv(cw_path, dtype={'tract':str})
    if 'weight' not in df.columns:
        df['weight'] = 1 / df.groupby('TAZ1454')['tract'].transform('count')
    return df[['tract','TAZ1454','weight']]

def step9_summarize_tract_to_taz(df_tr, df_wt):
    df = df_wt.merge(df_tr.rename(columns={'GEOID':'tract'}), on='tract', how='left')
    vars_tr = [c for c in df_tr.columns if c!='GEOID']
    for var in vars_tr:
        df[var] = df[var] * df['weight']
    return df.groupby('TAZ1454')[vars_tr].sum().reset_index()

def step9_integrate_employment(year):
    # stub: integrate LODES/self-employed
    raise NotImplementedError

# ------------------------------
# Steps 10-13: stubs
# ------------------------------
def step10_build_county_targets(taz, emp): raise NotImplementedError

def step11_apply_scaling(taz, targets): raise NotImplementedError

def step12_join_pba2015(taz): raise NotImplementedError

def step13_write_outputs(taz, year): raise NotImplementedError

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
        outputs['shares'], outputs['acs_bg'], outputs['acs_tr'], outputs['dhc_tr']
    )
    outputs['hhinc']     = step7_process_household_income(outputs['working'], ACS_5YR_LATEST)
    outputs['weights']   = compute_block_weights(PATHS)
    df_bg = outputs['hhinc'].rename(columns={'GEOID':'blockgroup'})
    outputs['taz']       = step8_summarize_to_taz(df_bg, outputs['weights'])
    outputs['weights_tract'] = compute_tract_weights(PATHS)
    outputs['taz_tract']    = step9_summarize_tract_to_taz(
        outputs['acs_tr'], outputs['weights_tract']
    )
    outputs['taz_final']  = outputs['taz'].merge(outputs['taz_tract'], on='TAZ1454', how='left')
    outputs['emp']       = step9_integrate_employment(YEAR)
    outputs['targets']   = step10_build_county_targets(outputs['taz'], outputs['emp'])
    outputs['scaled']    = step11_apply_scaling(outputs['taz'], outputs['targets'])
    outputs['final']     = step12_join_pba2015(outputs['scaled'])
    step13_write_outputs(outputs['final'], YEAR)

    logging.info("TAZ data processing complete.")

if __name__ == '__main__':
    main()