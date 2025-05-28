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
ACS_PUMS_5YEAR_LATEST  = CONSTANTS['ACS_PUMS_5YEAR_LATEST']
YEAR            = CONSTANTS['years'][0]
VARIABLES = cfg['variables']

YEAR = CONSTANTS['years'][0]
BASELINE_YEAR = CONSTANTS["BASELINE_YEAR"]
ACS_5YR = CONSTANTS['ACS_5YEAR_LATEST']
PUMS_1YR = CONSTANTS['ACS_PUMS_1YEAR_LATEST']

# Ensure project modules on path
sys.path.insert(0, str(Path(__file__).parent))

# Import individual step functions
from fetch_census_1 import (
    fetch_block_data,
    fetch_acs_bg,
    compute_bg_vars,
    fetch_acs_tract,
    fetch_dhc_tract
)
from build_process_2 import (
    compute_block_shares,
    build_workingdata,
    process_household_income
)
from summarize_to_taz_3 import (
    compute_block_weights,
    summarize_to_taz,
    summarize_census_to_taz
)
# Integrate & scale functions, including county targets builder
from integrate_emp_scale_4 import (
    build_county_targets,
    integrate_employment,
    integrate_lehd_targets,
    add_taz_summaries,
    apply_county_targets_to_taz
)
from finalize_pipeline_5 import (
    write_out_all
)

def main():
    
    logging.basicConfig(level=logging.INFO)
    # Load API key
    import os
    key_path = os.path.expandvars(PATHS['census_api_key_file'])
    with open(key_path) as f:
        api_key = f.read().strip()
    c = Census(api_key, year=None)


    # fetch Census data
    logging.info('Fetch block data')
    blocks = fetch_block_data(c)
    logging.info('Fetch: fetch ACS BG data')
    acs_bg = fetch_acs_bg(c, ACS_5YR)
    acs_bg = compute_bg_vars(acs_bg)
    logging.info('Fetch ACS tract data')
    acs_tr = fetch_acs_tract(c, ACS_5YR)
    logging.info('fetch DHC tract data')
    dhc_tr = fetch_dhc_tract(c)

    # working, shares & household income
    logging.info('compute block shares')
    shares = compute_block_shares(blocks, acs_bg)
    logging.info('build working data')
    working = build_workingdata(shares, acs_tr, dhc_tr)
    
    logging.info('process household income')
    hhinc = process_household_income(working, ACS_5YR)
    sanity_check_df(working, "process_household_income")

    # Summarize to TAZ
    logging.info('summarize hhinc to TAZ')
    weights_block = compute_block_weights(PATHS)
    taz_hhinc = summarize_to_taz(hhinc, weights_block)
    taz_base = taz_hhinc  # now contains HHINCQ1–4 plus all the other TAZ‐level fields

    logging.info('Summarize raw census to TAZ')
    taz_census = summarize_census_to_taz(working, weights_block)
    sanity_check_df(taz_census, "summarize_census_to_taz")

    # integrate employment
    #  merge census & employment into taz_base
    logging.info('integrate census & employment')
    taz_base_emp = integrate_employment(taz_base, taz_census, YEAR)


    # Build and merge county targets
    logging.info('Building county targets')
    county_targets = build_county_targets(
        tazdata_census = taz_census,     
        dhc_gqpop = dhc_tr,
        acs_5year = ACS_5YR,
        acs_pums_1year = PUMS_1YR,
        census_client = c
    )

    county_targets_all = integrate_lehd_targets(
    county_targets=county_targets,
    emp_lodes_weight=CONSTANTS["EMPRES_LODES_WEIGHT"]
    )

    # Apply all county‐level controls (pop+hh+gq, then employment)
    logging.info("Apply county targets to TAZ")
    county_targets['county_fips'] = county_targets['county_fips'].astype(str).str.zfill(5)
    taz_base_emp['TAZ1454'] = taz_base_emp['TAZ1454'].astype(str)
    taz_base_emp = add_taz_summaries(taz_base_emp)
    

    taz_scaled = apply_county_targets_to_taz(
    taz_base_emp,
    county_targets_all,
    ACS_PUMS_5YEAR_LATEST
        )

    # join PBA2015 and write outputs
    logging.info("join PBA2015 and write outputs")
    pba_path = os.path.expandvars(PATHS['pba_taz_2015'])
    df_pba  = pd.read_excel(pba_path, sheet_name="census2015", dtype=str)

    write_out_all(taz_scaled, df_pba, baseline_year=BASELINE_YEAR, target_year=YEAR)
    logging.info("Pipeline complete")
 
if __name__ == '__main__':
    main()
