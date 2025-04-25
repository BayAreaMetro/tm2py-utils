#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
create_taz_data.py

End-to-end TAZ data pipeline for Travel Model One and Two.
Loads all settings (constants, paths, geo, variable mappings) from config.yaml.
Defines 13 sequential steps, each stubbed out for implementation.
"""
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
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

# Default processing year from config
YEAR = CONSTANTS['years'][0]
ACS_5YR_LATEST = CONSTANTS['ACS_5YEAR_LATEST']

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
# STUBS FOR EACH STEP
# ------------------------------
def step1_fetch_block_data(c, year):
    """1) Fetch block-level population (2020 Decennial PL)"""
    df_raw = download_acs_blocks(c, year, 'dec/pl')
    if df_raw.empty:
        logging.error('No block data retrieved; exiting.')
        sys.exit(1)
    df = census_to_df(df_raw)
    if 'P1_001N' in df.columns:
        df = df.rename(columns={'P1_001N': 'pop'})
    else:
        logging.error('Expected P1_001N field not found in block data')
        sys.exit(1)
    result = df[['GEOID', 'pop']].copy()
    result['pop'] = pd.to_numeric(result['pop'], errors='coerce').fillna(0).astype(int)
    return result

def step2_fetch_acs_bg(c, year):
    """
    2) Fetch ACS5 block‐group estimates for all variables listed in config.yaml:
       VARIABLES['ACS_BG_VARIABLES'] maps output_name → ACS code (without the “E”).
    """
    var_map     = VARIABLES['ACS_BG_VARIABLES']   # e.g. {'tothh_': 'B19001_001', …}
    state_code  = GEO['STATE_CODE']
    counties    = GEO['BA_COUNTY_FIPS_CODES']    # e.g. ['001','013',…]
    
    # Turn the var_map into a list of (name, code) pairs
    items       = list(var_map.items())
    batch_size  = 45
    batches     = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    
    df_chunks = []
    
    for batch in batches:
        # build your fetch list and rename map for *this* batch
        fetch_vars   = [f"{code}E" for (_, code) in batch]
        rename_map   = {f"{code}E": name for (name, code) in batch}
        
        # pull each county
        records = []
        for county in counties:
            try:
                recs = retrieve_census_variables(
                    c, year, 'acs5', fetch_vars,
                    for_geo  = 'block group',
                    state    = state_code,
                    county   = county
                )
            except Exception as e:
                logging.warning(f"County {county} failed: {e}")
                continue
            records.extend(recs)
        
        if not records:
            # nothing came back for this batch
            continue
        
        # convert & rename
        df_batch = census_to_df(records).rename(columns=rename_map)
        df_chunks.append(df_batch)
    
    if not df_chunks:
        logging.error("No ACS data was fetched for *any* batch.")
        return pd.DataFrame()
    
    # merge all the batches back together on the geo columns
    geo_cols = ['state', 'county', 'tract', 'block group']
    df = df_chunks[0]
    for df_next in df_chunks[1:]:
        df = df.merge(df_next, on=geo_cols, how='outer')
    
    # now coerce every output_name to int, filling any missing with zero
    for output_name in var_map.keys():
        if output_name in df.columns:
        # existing column: coerce to numeric
            series = (
                pd.to_numeric(df[output_name], errors='coerce')
                .fillna(0)
                .astype(int)
         )
        else:
         # missing column: create a zero Series
            series = pd.Series(0, index=df.index, dtype=int)
        df[output_name] = series
    
    return df

def step3_fetch_acs_tract(c, year): raise NotImplementedError

def step4_fetch_dhc_tract(c): raise NotImplementedError

def step5_compute_block_shares(df_blk, df_bg): raise NotImplementedError

def step6_build_workingdata(df_comb, df_bg, df_tract, df_dhc): raise NotImplementedError

def step7_process_household_income(working, year): raise NotImplementedError

def step8_summarize_to_taz(working, taz_hhinc): raise NotImplementedError

def step9_integrate_employment(year): raise NotImplementedError

def step10_build_county_targets(taz, emp): raise NotImplementedError

def step11_apply_scaling(taz, targets): raise NotImplementedError

def step12_join_pba2015(taz): raise NotImplementedError

def step13_write_outputs(taz, year): raise NotImplementedError

# ------------------------------
# Logging setup
# ------------------------------
def setup_logging(year):
    out_dir = Path(os.path.expandvars(PATHS['output_root']).replace('${YEAR}', str(year)))
    out_dir.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(), logging.FileHandler(out_dir / f'create_tazdata_{year}.log')]
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=handlers)

# ------------------------------
# Census client
# ------------------------------
def setup_census_client():
    key_file = Path(os.path.expandvars(PATHS['census_api_key_file']))
    api_key = key_file.read_text().strip()
    return Census(api_key)

# ------------------------------
# Main pipeline execution
# ------------------------------
def main():
    # Use configured YEAR instead of CLI args
    setup_logging(YEAR)
    logging.info(f"Starting TAZ pipeline for YEAR={YEAR}")

    c = setup_census_client()

    outputs = {}
    outputs['blocks'] = step1_fetch_block_data(c, YEAR)
    outputs['acs_bg'] = step2_fetch_acs_bg(c, YEAR)
    outputs['acs_tr'] = step3_fetch_acs_tract(c, min(YEAR + 2, ACS_5YR_LATEST))
    outputs['dhc_tr'] = step4_fetch_dhc_tract(c)
    outputs['shares'] = step5_compute_block_shares(outputs['blocks'], outputs['acs_bg'])
    outputs['working'] = step6_build_workingdata(
        outputs['shares'], outputs['acs_bg'], outputs['acs_tr'], outputs['dhc_tr']
    )
    outputs['hhinc'] = step7_process_household_income(outputs['working'], YEAR)
    outputs['taz'] = step8_summarize_to_taz(outputs['working'], outputs['hhinc'])
    outputs['emp'] = step9_integrate_employment(YEAR)
    outputs['targets'] = step10_build_county_targets(outputs['taz'], outputs['emp'])
    outputs['scaled'] = step11_apply_scaling(outputs['taz'], outputs['targets'])
    outputs['final'] = step12_join_pba2015(outputs['scaled'])
    step13_write_outputs(outputs['final'], YEAR)

    logging.info("TAZ data processing complete.")

if __name__ == '__main__':
    main()

