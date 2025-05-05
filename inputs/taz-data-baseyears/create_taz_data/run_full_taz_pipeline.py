#!/usr/bin/env python 
# -*- coding: utf-8 -*-
"""
run_full_pipeline.py

Master script to execute the entire TAZ data pipeline in sequence by
calling each step function directly.
"""
import os
import sys
import logging
from pathlib import Path
import yaml
from census import Census
import pandas as pd
from common import sanity_check_df, apply_county_targets_to_taz

# Load configuration
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)
CONSTANTS       = cfg['constants']
PATHS           = cfg['paths']
GEO             = cfg.get('geo_constants', {})
ACS_5YR_LATEST  = CONSTANTS['ACS_5YEAR_LATEST']
ACS_PUMS_1YEAR_LATEST  = CONSTANTS['ACS_PUMS_1YEAR_LATEST']
YEAR            = CONSTANTS['years'][0]
VARIABLES = cfg['variables']

# Ensure project modules on path
sys.path.insert(0, str(Path(__file__).parent))

# Import individual step functions
from fetch_census_1 import (
    step1_fetch_block_data,
    step2_fetch_acs_bg,
    step3_fetch_acs_tract,
    step4_fetch_dhc_tract
)
from build_process_2 import (
    step5_compute_block_shares,
    step6_build_workingdata,
    step7_process_household_income
)
from summarize_to_taz_3 import (
    compute_block_weights,
    step8_summarize_to_taz,
    compute_tract_weights,
    step9_summarize_tract_to_taz
)
# Integrate & scale functions, including county targets builder
from integrate_emp_scale_4 import (
    summarize_census_to_taz,
    build_county_targets,
    step10_integrate_employment,
    step11_compute_scale_factors,
    step12_apply_scaling
)
from finalize_pipeline_5 import (
    step13_join_pba2015,
    step14_write_outputs
)

def main():
    logging.basicConfig(level=logging.INFO)
    # Load API key
    import os
    key_path = os.path.expandvars(PATHS['census_api_key_file'])
    with open(key_path) as f:
        api_key = f.read().strip()
    c = Census(api_key, year=None)

    YEAR = CONSTANTS['DECENNIAL_YEAR']
    ACS_5YR = CONSTANTS['ACS_5YEAR_LATEST']
    PUMS_1YR = CONSTANTS['ACS_PUMS_1YEAR_LATEST']

    # Steps 1–4: fetch data
    logging.info('Step 1: fetch block data')
    blocks = step1_fetch_block_data(c, YEAR)
    sanity_check_df(blocks, "step1_download_blocks")
    logging.info('Step 2: fetch ACS BG data')
    acs_bg = step2_fetch_acs_bg(c, YEAR)
    sanity_check_df(acs_bg, "step2_fetch_acs_bg")
    logging.info('Step 3: fetch ACS tract data')
    acs_tr = step3_fetch_acs_tract(c, ACS_5YR)
    sanity_check_df(acs_tr, "step3_fetch_acs_tract")
    logging.info('Step 4: fetch DHC tract data')
    dhc_tr = step4_fetch_dhc_tract(c)
    sanity_check_df(dhc_tr, "step4_fetch_dhc_tract")

    # Steps 5–7: working & household income
    logging.info('Step 5: compute block shares')
    shares = step5_compute_block_shares(blocks, acs_bg)
    sanity_check_df(shares, "step5_compute_block_shares")
    logging.info('Step 6: build working data')
    working = step6_build_workingdata(shares, acs_tr, dhc_tr)
    sanity_check_df(working, "step6_build_workingdata")
    logging.info('Step 7: process household income')
    hhinc = step7_process_household_income(working, ACS_5YR)
    sanity_check_df(working, "step7_process_household_income")

    # Steps 8–9: summarize to TAZ
    logging.info('Step 8: summarize hhinc to TAZ')
    weights_block = compute_block_weights(PATHS)
    sanity_check_df(weights_block, "compute_block_weights")
    taz_hhinc = step8_summarize_to_taz(hhinc, weights_block)
    sanity_check_df(taz_hhinc, "taz_hhinc")
    logging.info('Step 9: summarize ACS tract to TAZ')
    weights_tract = compute_tract_weights(PATHS)
    sanity_check_df(weights_tract, "commute_tract_weights")
    taz_acs = step9_summarize_tract_to_taz(acs_tr, weights_tract)
    sanity_check_df(taz_acs, "step9_summarize_tract_to_taz")

    # Combine TAZ summaries
    logging.info('Combining TAZ summaries')
    taz_hhinc['taz'] = taz_hhinc['taz'].astype(str)
    taz_acs['taz'] = taz_acs['taz'].astype(str)
    taz_base = taz_hhinc.merge(taz_acs, on='taz', how='left')
    sanity_check_df(taz_base, 'taz_base')
  

    # Raw census counts to TAZ
    logging.info('Summarize raw census to TAZ')
    taz_census = summarize_census_to_taz(working, weights_block)
    sanity_check_df(taz_census, "summarize_census_to_taz")

    # Step 10: integrate employment
    logging.info('Step 10: integrate employment')
    df_emp = step10_integrate_employment(taz_base, taz_census, YEAR)
    sanity_check_df(df_emp, "step10_integrate_employment")

    # Build and merge county targets
    logging.info('Building county targets')
    county_targets = build_county_targets(
        tazdata_census = taz_base,
        dhc_gqpop = dhc_tr,
        acs_5year = ACS_5YR,
        acs_pums_1year = PUMS_1YR,
        census_client = c
    )
    merge_ct = (
        county_targets[['county_fips','EMPRES','TOTEMP']]
        .rename(columns={'EMPRES':'county_base','TOTEMP':'county_target'})
    )
    taz_base = taz_base.merge(merge_ct, on='county_fips', how='left')

    # Step 11: compute scale factors
    logging.info('Step 11: compute scale factors')
    scale_df = step11_compute_scale_factors(
        taz_df = taz_base,
        taz_targeted = taz_base,
        base_col = 'county_base',
        target_col = 'county_target'
    )

    # Step 12: apply scaling
    logging.info('Step 12: apply scaling')
    taz_scaled = step12_apply_scaling(
        taz_df = taz_base,
        taz_targeted = taz_base,
        vars_to_scale = ['emp_lodes','emp_self']
    )

    # Step 13: apply county targets back to TAZ
    logging.info('Step 13: apply county targets to TAZ')
    taz_scaled = apply_county_targets_to_taz(
        taz_scaled,
        county_targets,
        popsyn_ACS_PUMS_5YEAR = PUMS_1YR
    )

    # Step 14: join and write outputs
    logging.info('Step 14: join PBA2015 and write outputs')
    taz_joined = step13_join_pba2015(taz_scaled)
    
    step14_write_outputs(taz_joined, YEAR)
    logging.info('Pipeline complete')

if __name__ == '__main__':
    main()
