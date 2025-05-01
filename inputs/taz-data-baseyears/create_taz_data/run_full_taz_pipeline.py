#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_full_pipeline.py

Master script to execute the entire TAZ data pipeline in sequence by
calling each step function directly.
"""
import os
import logging
from pathlib import Path
import yaml
from census import Census
import pandas as pd

# Load configuration
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)
CONSTANTS = cfg['constants']
PATHS     = cfg['paths']
ACS_5YR_LATEST = CONSTANTS['ACS_5YEAR_LATEST']
YEAR           = CONSTANTS['years'][0]


# Add project modules to path
import sys
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
from integrate_emp_scale_4 import (
    step10_integrate_employment,
    step11_compute_scale_factors,
    step12_apply_scaling
)
from finalize_pipeline_5 import (
    step13_join_pba2015,
    step14_write_outputs
)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    c = Census(os.getenv('CENSUS_API_KEY', ''), year=None)

    # Steps 1–4: Fetch Census data
    logging.info('Running Step 1: fetch block data')
    blocks = step1_fetch_block_data(c, YEAR)
    logging.info('Running Step 2: fetch ACS BG data')
    acs_bg = step2_fetch_acs_bg(c, YEAR)
    logging.info('Running Step 3: fetch ACS tract data')
    acs_tr = step3_fetch_acs_tract(c, min(YEAR+2, ACS_5YR_LATEST))
    logging.info('Running Step 4: fetch DHC tract data')
    dhc_tr = step4_fetch_dhc_tract(c)

    # Steps 5–7: Build working and household income
    logging.info('Running Step 5: compute block shares')
    shares = step5_compute_block_shares(blocks, acs_bg)
    logging.info('Running Step 6: build working data')
    working = step6_build_workingdata(shares, acs_tr, dhc_tr)
    logging.info('Running Step 7: process household income')
    hhinc = step7_process_household_income(working, ACS_5YR_LATEST)

    # Steps 8–9: Summarize to TAZ
    logging.info('Running Step 8: compute block weights and summarize hhinc to TAZ')
    weights_block = compute_block_weights(PATHS)
    taz_hhinc = step8_summarize_to_taz(hhinc, weights_block)
    logging.info('Running Step 9: compute tract weights and summarize ACS tr to TAZ')
    weights_tract = compute_tract_weights(PATHS)
    taz_acs = step9_summarize_tract_to_taz(acs_tr, weights_tract)

    # Combine TAZ outputs
    logging.info('Combining TAZ household income and ACS summaries')
    taz_hhinc['taz'] = taz_hhinc['TAZ1454'].astype(str)
    taz_acs['taz'] = taz_acs['taz'].astype(str)
    taz_base = taz_hhinc.merge(taz_acs, on='taz', how='left')

    # Step 10: Integrate employment
    logging.info('Running Step 10: integrate employment')
    df_emp = step10_integrate_employment(YEAR)
    df_emp['taz'] = df_emp['taz'].astype(str)
    taz_base['taz'] = taz_base['taz'].astype(str)
    taz_base = taz_base.merge(df_emp, on='taz', how='left').fillna(0)

    # Step 11: Compute scale factors
    logging.info('Running Step 11: compute scale factors')
    scale_df = step11_compute_scale_factors(
        taz_df=taz_base,
        taz_targeted=taz_base,
        base_col='emp_lodes',
        target_col='emp_lodes'
    )

    # Step 12: Apply scaling
    logging.info('Running Step 12: apply scaling')
    taz_scaled = step12_apply_scaling(
        taz_base,
        taz_base,
        vars_to_scale=['emp_lodes', 'emp_self']
    )

    # Step 13: Join PBA2015
    logging.info('Running Step 13: join PBA2015 attributes')
    taz_joined = step13_join_pba2015(taz_scaled)

    # Step 14: Write outputs
    logging.info('Running Step 14: write outputs')
    step14_write_outputs(taz_joined, YEAR)

    logging.info('Full pipeline executed successfully')
