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
from common import sanity_check_df, apply_county_targets_to_taz, update_tazdata_to_county_target


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
ACS_5YR = CONSTANTS['ACS_5YEAR_LATEST']
PUMS_1YR = CONSTANTS['ACS_PUMS_1YEAR_LATEST']

# Ensure project modules on path
sys.path.insert(0, str(Path(__file__).parent))

# Import individual step functions
from fetch_census_1 import (
    step1_fetch_block_data,
    step2_fetch_acs_bg,
    step2b_compute_bg_vars,
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
    _add_institutional_gq,
    _apply_acs_adjustment,
    build_county_targets,
    step10_integrate_employment,
    integrate_lehd_targets,
    add_taz_summaries,
    apply_county_targets_to_taz,
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
    """
    # Steps 1–4: fetch data
    logging.info('Step 1: fetch block data')
    blocks = step1_fetch_block_data(c)
    sanity_check_df(blocks, "step1_download_blocks")
    logging.info('Step 2: fetch ACS BG data')
    acs_bg = step2_fetch_acs_bg(c, ACS_5YR)
    acs_bg = step2b_compute_bg_vars(acs_bg)
    sanity_check_df(acs_bg, "step2b_compute_bg_vars")
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
    taz_hhinc['taz'] = taz_hhinc['TAZ1454'].astype(str)
    taz_base = taz_hhinc  # now contains HHINCQ1–4 plus all the other TAZ‐level fields
    sanity_check_df(taz_base, 'taz_base')
  

    # Raw census counts to TAZ
    logging.info('Summarize raw census to TAZ')
    taz_census = summarize_census_to_taz(working, weights_block)
    sanity_check_df(taz_census, "summarize_census_to_taz")

    # Step 10: integrate employment
    # Step 10: merge census & employment into taz_base
    logging.info('Step 10: integrate census & employment')
    taz_base['taz'] = taz_base['TAZ1454'].astype(str)
    taz_census['taz'] =taz_census['TAZ1454'].astype(str)
    taz_base = step10_integrate_employment(taz_base, taz_census, YEAR)
    #sanity_check_df(taz_base, "step10_integrate_employment")


    # write out unscaled TAZ data
    out_root = os.path.expandvars(PATHS['output_root'])
    year_dir = os.path.join(out_root, str(YEAR))
    os.makedirs(year_dir, exist_ok=True)
    taz_base.to_csv(os.path.join(year_dir, "taz_unscaled_to_cnty.csv"), index=False)
    taz_census.to_csv(os.path.join(year_dir, "taz_census.csv"), index=False)
    dhc_tr.to_csv(os.path.join(year_dir, "dhc_tract.csv"), index=False)

    """
    out_root = os.path.expandvars(PATHS['output_root'])
    year_dir = os.path.join(out_root, str(YEAR))
    taz_base= pd.read_csv(os.path.join(year_dir, "taz_unscaled_to_cnty.csv"))
    dhc_tr= pd.read_csv(os.path.join(year_dir, "dhc_tract.csv"))
    taz_census= pd.read_csv(os.path.join(year_dir, "taz_census.csv"))

    # Build and merge county targets
    logging.info('Building county targets')
    county_targets = build_county_targets(
        tazdata_census = taz_census,     
        dhc_gqpop = dhc_tr,
        acs_5year = ACS_5YR,
        acs_pums_1year = PUMS_1YR,
        census_client = c
    )
    sanity_check_df(county_targets, "county_targets")
    
  

    county_targets_all = integrate_lehd_targets(
    county_targets=county_targets,
    emp_lodes_weight=CONSTANTS["EMPRES_LODES_WEIGHT"]
    )



    # Step 11: apply all county‐level controls (pop+hh+gq, then employment)
    logging.info("Step 11: apply county targets to TAZ")
    county_targets['county_fips'] = county_targets['county_fips'].astype(str).str.zfill(5)
    # create the County_Name column the scaler expects
 
    taz_base = add_taz_summaries(taz_base)


    taz_base['TAZ1454'] = taz_base['TAZ1454'].astype(str)

    taz_map = pd.read_csv(
        os.path.expandvars(PATHS['taz_sd_county_csv']),
        dtype={'ZONE': str, 'COUNTY_NAME': str}
    )
    taz_map['ZONE'] = taz_map['ZONE'].astype(str)

    # Now merge
    taz_base = (
        taz_base
        .merge(
            taz_map[['ZONE','COUNTY_NAME']],
            left_on='TAZ1454',
            right_on='ZONE',
            how='left'
        )
        .rename(columns={'COUNTY_NAME':'County_Name'})
        .drop(columns=['ZONE'])
    )


    taz_scaled = apply_county_targets_to_taz(
    taz_base,
    county_targets_all,
    ACS_PUMS_5YEAR_LATEST
        )
    
    taz_scaled.to_csv(os.path.join(year_dir, "taz_scaled_to_cnty.csv"), index=False)

    # Step 12: join PBA2015 and write outputs
    logging.info("Step 12: join PBA2015 and write outputs")
    taz_joined = step13_join_pba2015(taz_scaled)
    sanity_check_df(taz_joined, "step13_join_pba2015")
    step14_write_outputs(taz_joined, YEAR)
    logging.info("Pipeline complete")
    """
if __name__ == '__main__':
    main()
