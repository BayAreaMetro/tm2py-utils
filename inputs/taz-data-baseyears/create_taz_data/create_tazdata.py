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
    """
    Fetch 2020 dec/pl block‐level total population (P1_001N),
    construct the 15‐digit block GEOID from state/county/tract/block,
    and derive 12‐digit blockgroup & 11‐digit tract codes.
    """
    logger = logging.getLogger(__name__)

    # 1) Config
    dec_year     = CONSTANTS['DECENNIAL_YEAR']                # e.g. 2020
    state_code   = GEO['STATE_CODE']                          # e.g. "06"
    county_codes = list(GEO['BA_COUNTY_FIPS_CODES'].keys())   # ["001","013",…]

    # 2) Pull P1_001N from 2020 PL
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

    # 3) Zero‐pad each piece and build the full 15-digit block GEOID
    df['state']  = df['state'].astype(str).str.zfill(2)
    df['county'] = df['county'].astype(str).str.zfill(3)
    df['tract']  = df['tract'].astype(str).str.zfill(6)
    df['block']  = df['block'].astype(str).str.zfill(4)
    df['block_geoid'] = df['state'] + df['county'] + df['tract'] + df['block']

    # 4) Derive blockgroup (first 12 digits) & tract (first 11 digits)
    df['blockgroup'] = df['block_geoid'].str[:12]
    df['tract']      = df['block_geoid'].str[:11]

    # 5) Coerce pop
    df['pop'] = (
        pd.to_numeric(df.get('P1_001N', 0), errors='coerce')
          .fillna(0).astype(int)
    )

    # 6) Return only the key columns
    return df[['block_geoid', 'blockgroup', 'tract', 'pop']]

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

    # 6) Drop any other geo columns
    df.drop(columns=['state','county','tract','block group'], errors='ignore', inplace=True)

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
    Download decennial DHC variables for tracts using direct API call. Raises if no data.
    Returns DataFrame with columns ['GEOID', <DHC vars>].
    """
    import requests
    # choose valid decennial year
    dec_year = year if year in (2000, 2010, 2020) else DECENNIAL_YEAR
    var_map = VARIABLES.get('DHC_TRACT_VARIABLES', {})
    if not var_map:
        raise ValueError("CONFIG ERROR: DHC_TRACT_VARIABLES is empty in config.yaml")
    fetch_vars = list(var_map.values())
    state = GEO['STATE_CODE']
    counties = list(GEO['BA_COUNTY_FIPS_CODES'].keys())

    all_rows = []
    for cnt in counties:
        url = f"https://api.census.gov/data/{dec_year}/dec/dhc"
        params = {
            'get': ",".join(fetch_vars),
            'for': 'tract:*',
            'in': f"state:{state}+county:{cnt}",
            'key': CENSUS_API_KEY
        }
        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            logging.error(f"DHC request failed (county {cnt}): {resp.status_code} {resp.text}")
            continue
        data = resp.json()
        # first row is header
        cols = data[0]
        for row in data[1:]:
            all_rows.append(dict(zip(cols, row)))
    if not all_rows:
        raise RuntimeError(f"No DHC records fetched for decennial year {dec_year}; aborting.")

    df = pd.DataFrame(all_rows)
    # rename according to var_map
    df = df.rename(columns={code: name for name, code in var_map.items()})
    # build GEOID if not present
    if 'GEOID' not in df.columns:
        df['GEOID'] = df['state'] + df['county'] + df['tract']
    # convert numeric columns
    for name in var_map.keys():
        df[name] = pd.to_numeric(df[name], errors='coerce').fillna(0).astype(int)
    return df


# ------------------------------
# STEP 5: Disaggregate ACS BG vars to block level
# ------------------------------
def step5_compute_block_shares(df_blk, df_bg):
    """
    Disaggregate ACS block-group variables to blocks using 2020 block population share.
    Returns a DataFrame with columns ['GEOID'] + ACS_BG_VARIABLES.keys() + ['pop_share'].
    """
    # Prepare ACS block-group DataFrame: ensure BG_GEOID
    df_bg2 = df_bg.copy()
    if 'GEOID' in df_bg2.columns:
        df_bg2 = df_bg2.rename(columns={'GEOID':'BG_GEOID'})
    else:
        # build BG_GEOID from components
        df_bg2['BG_GEOID'] = df_bg2['state'] + df_bg2['county'] + df_bg2['tract'] + df_bg2['block group']

    # Prepare block-level DataFrame
    df = df_blk.copy()
    df['BG_GEOID'] = df['GEOID'].str.slice(0,12)

    # Compute total pop per block group
    bg_pop = df.groupby('BG_GEOID')['pop'].sum().reset_index().rename(columns={'pop':'bg_pop'})
    df = df.merge(bg_pop, on='BG_GEOID', how='left')
    df['pop_share'] = df['pop'] / df['bg_pop'].replace({0:1})

    # DEBUG: log first few shares
    logging.info("Block share sample:%s", df[['GEOID','pop','bg_pop','pop_share']].head())

    # Merge ACS block-group estimates
    df = df.merge(df_bg2, on='BG_GEOID', how='left')
    bg_vars = list(VARIABLES['ACS_BG_VARIABLES'].keys())
    logging.info("ACS BG values at first block:%s", df[bg_vars].iloc[0])

    # Disaggregate each ACS variable
    for var in bg_vars:
        df[var] = df['pop_share'] * df[var].fillna(0)

    # Return block-level shares (float); rounding happens later
    return df[['GEOID'] + bg_vars + ['pop_share']]

# ------------------------------
# STEP 6: Build working dataset at block geography
# ------------------------------
def step6_build_workingdata(shares, acs_bg, acs_tr, dhc_tr):
    # (0) derive blockgroup+tract from the 15-digit GEOID
    shares['blockgroup'] = (
        shares['block_geoid'].astype(str).str[-12:].str.zfill(12)
    )
    shares['tract'] = shares['blockgroup'].str[:11]
    logger = logging.getLogger(__name__)
    try:
        # 1) Log shapes
        logger.info(f"step6 inputs ▶ shares={shares.shape}, acs_bg={acs_bg.shape}, "
                    f"acs_tr={acs_tr.shape}, dhc_tr={dhc_tr.shape}")

        # 2) Rename/pad/drop as before...
        key_cfg = {
            'shares': dict(expected='blockgroup', alts=['GEOID','block_group','bgid'], length=12,
                           drop_cols=[]),
            'acs_bg':  dict(expected='blockgroup', alts=['GEOID','GEOID_BG','block group'], length=12,
                           drop_cols=['state','county','tract']),
            'acs_tr':  dict(expected='tract',      alts=['GEOID','TRACTCE'],          length=11,
                           drop_cols=[]),
            'dhc_tr':  dict(expected='tract',      alts=['GEOID','TRACTCE'],          length=11,
                           drop_cols=[]),
        }
        for df, name in [(shares,'shares'), (acs_bg,'acs_bg'),
                         (acs_tr,'acs_tr'), (dhc_tr,'dhc_tr')]:
            cfg = key_cfg[name]
            exp = cfg['expected']
            # rename
            if exp not in df.columns:
                for alt in cfg['alts']:
                    if alt in df.columns:
                        df.rename(columns={alt: exp}, inplace=True)
                        logger.warning(f"{name}: renamed {alt!r} → {exp!r}")
                        break
            if exp not in df.columns:
                logger.error(f"{name!r} missing key {exp!r}; cols: {df.columns.tolist()}")
                raise KeyError(f"{name} missing column {exp}")
            # pad
            df[exp] = df[exp].astype(str).str.zfill(cfg['length'])
            logger.debug(f"{name}.{exp} sample: {df[exp].head().tolist()}")
            # drop configured extras
            for drop in cfg['drop_cols']:
                if drop in df.columns:
                    df.drop(columns=[drop], inplace=True)
                    logger.warning(f"{name}: dropped column {drop!r}")
            # drop other geoid‐like collisions
            to_drop_geo = [c for c in df.columns
                           if c.lower().startswith('geoid') and c != exp]
            if to_drop_geo:
                df.drop(columns=to_drop_geo, inplace=True)
                logger.warning(f"{name}: dropped extra geo cols {to_drop_geo}")

        # ──────────────────────────────────────────────────────────────────────────
        # 3) **DIAGNOSTIC: key‐matching summary before merge**
        #
        s_bg = set(shares['blockgroup'])
        b_bg = set(acs_bg['blockgroup'])
        common_bg = s_bg & b_bg
        logger.info(f"Blockgroup keys ▶ shares unique={len(s_bg)}, acs_bg unique={len(b_bg)}, "
                    f"intersection={len(common_bg)}")
        logger.info(f"Sample shares bg (5): {list(s_bg)[:5]}")
        logger.info(f"Sample acs_bg bg  (5): {list(b_bg)[:5]}")

        # ──────────────────────────────────────────────────────────────────────────
        # 4) Merge shares ← acs_bg
        m1 = shares.merge(acs_bg, on='blockgroup', how='left', indicator='bg_merge')
        logger.info(f"bg_merge counts → {m1['bg_merge'].value_counts().to_dict()}")
        df_work = m1.drop(columns=['bg_merge'])

        # ──────────────────────────────────────────────────────────────────────────
        # 5) **DIAGNOSTIC: tract‐matching summary before second merge**
        #
        # shares-derived tract vs. acs_tr
        s_tr = set(df_work['tract'])
        t_tr = set(acs_tr['tract'])
        common_tr = s_tr & t_tr
        logger.info(f"Tract keys ▶ shares/acs_bg-derived unique={len(s_tr)}, acs_tr unique={len(t_tr)}, "
                    f"intersection={len(common_tr)}")
        logger.info(f"Sample shares tract (5): {list(s_tr)[:5]}")
        logger.info(f"Sample acs_tr tract   (5): {list(t_tr)[:5]}")

        # 6) Merge ← acs_tr
        m2 = df_work.merge(acs_tr, on='tract', how='left', indicator='tr_merge')
        logger.info(f"tr_merge counts → {m2['tr_merge'].value_counts().to_dict()}")
        df_work = m2.drop(columns=['tr_merge'])

        # ──────────────────────────────────────────────────────────────────────────
        # 7) Merge ← dhc_tr (auto‐retry on collisions)
        try:
            m3 = df_work.merge(dhc_tr, on='tract', how='left', indicator='dhc_merge')
        except MergeError as me:
            overlap = set(df_work.columns).intersection(dhc_tr.columns) - {'tract'}
            logger.warning(f"dhc_merge collision: dropping {overlap} & retrying")
            dhc_clean = dhc_tr.drop(columns=list(overlap))
            m3 = df_work.merge(dhc_clean, on='tract', how='left', indicator='dhc_merge')

        logger.info(f"dhc_merge counts → {m3['dhc_merge'].value_counts().to_dict()}")
        result = m3.drop(columns=['dhc_merge'])

        logger.info(f"step6 output shape ▶ {result.shape}")
        return result

    except Exception:
        logger.exception("💥 Error in step6_build_workingdata")
        raise

# ------------------------------
# STEP 7: Map ACS income bins to TM1 quartiles
# ------------------------------
def step7_process_household_income(df_working, year=ACS_5YR_LATEST):
    """
    Allocate ACS block-group income categories into TM1 household income quartiles (HHINCQ1–4).
    Returns a DataFrame with columns ['GEOID','HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4'].
    Includes detailed logging of mapping and available columns.
    """
    mapping = map_acs5year_household_income_to_tm1_categories(year)
    # build code->working-col map for income
    code_to_col = {code: name for name, code in VARIABLES['ACS_BG_VARIABLES'].items() if name.startswith('hhinc')}

    # DEBUG: show code_to_col keys & df_working cols
    logging.info(f"code_to_col keys: {list(code_to_col.keys())}")
    logging.info(f"df_working columns: {df_working.columns.tolist()}")

    out = pd.DataFrame({'GEOID': df_working['GEOID']})
    for q in [1,2,3,4]:
        out[f'HHINCQ{q}'] = 0.0

    for _, row in mapping.iterrows():
        acs_code = row['incrange']
        q = int(row['HHINCQ'])
        share = float(row['share'])
        col = code_to_col.get(acs_code)
        if col is None:
            logging.warning(f"No mapping for ACS code {acs_code}")
            continue
        if col not in df_working.columns:
            logging.warning(f"Mapped column {col} not in working DF")
            continue
        out[f'HHINCQ{q}'] += df_working[col].fillna(0) * share

    for q in [1,2,3,4]:
        out[f'HHINCQ{q}'] = out[f'HHINCQ{q}'].round().astype(int)
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