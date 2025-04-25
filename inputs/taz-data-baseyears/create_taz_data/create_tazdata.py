#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Create TAZ data for 2020 and beyond.

This script generates Transportation Analysis Zone (TAZ) data for Travel Model One.
It downloads and processes Census data for the specified year, combining block, block
group, and tract level data into a comprehensive TAZ dataset for modeling.

Usage:
    python create_tazdata_2020_and_after.py

Notes:
- Household and population variables use ACS5-year data centered on the year
  (ACS_5YR_LATEST).
- Block group variables fallback to tract level if suppressed at block group level.
- Group quarter data uses 2020 Decennial Census where ACS is unavailable.
- Wage/salary employment uses LODES (LODES_YEAR_LATEST).
- Self-employed workers added from taz_self_employed_workers_[YEAR].csv.
- ACS1-year data (if newer) scales county totals.
- Employed residents blend ACS and LODES via EMPRES_LODES_WEIGHT.

Author: Metropolitan Transportation Commission (MTC)
Date:   March 2024
"""

import logging
import os
from pathlib import Path
from string import Template

import pandas as pd
import yaml
from census import Census


from common import (
    census_to_df,
    download_acs_blocks,
    fix_rounding_artifacts,
    map_acs5year_household_income_to_tm1_categories,
    retrieve_census_variables,
    scale_data_to_targets,
    update_disaggregate_data_to_aggregate_targets,
)


# Load configuration
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open('r') as cfg_file:
    _cfg = yaml.safe_load(cfg_file)


# Constants (ALL_CAPS)
YEAR_DEFAULT = _cfg['constants']['years'][0]
ACS_PUMS_5YR_LATEST = _cfg['constants']['ACS_PUMS_5YEAR_LATEST']
ACS_PUMS_1YR_LATEST = _cfg['constants']['ACS_PUMS_1YEAR_LATEST']
ACS_5YR_LATEST = _cfg['constants']['ACS_5YEAR_LATEST']
LODES_YEAR_LATEST = _cfg['constants']['LODES_YEAR_LATEST']
EMPRES_LODES_WEIGHT = _cfg['constants']['EMPRES_LODES_WEIGHT']
DOLLARS_TO_202X = _cfg['constants']['DOLLARS_2000_to_202X']
NAICS2_EMPSIX = _cfg['constants']['NAICS2_EMPSIX']

# Geo constants
BA_COUNTY_FIPS_CODES = _cfg['geo_constants']['BA_COUNTY_FIPS_CODES']
BAY_AREA_COUNTIES = _cfg['geo_constants']['BAY_AREA_COUNTIES']
STATE_CODE = _cfg['geo_constants']['STATE_CODE']

# Template environment for path resolution
_ENV = {
    'USERPROFILE': os.environ.get('USERPROFILE', ''),
    'BOX_TM': _cfg['paths']['box_tm_default'],
    'TM1': _cfg['paths']['tm1_root'],
    'YEAR': None,
    'LODES_YEAR': None,
}


def resolve(path: str) -> str:
    """Substitute template variables into a path string."""
    return Template(path).substitute(_ENV)


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


# Helper functions

def update_tazdata_to_county_target(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    sum_var: str,
    partial_vars: list,
) -> pd.DataFrame:
    """Scale TAZ data so county-level totals match targets."""
    current = (
        source_df.groupby('County_Name')[sum_var]
        .sum()
        .reset_index()
    )
    target_col = f'{sum_var}_target'
    merged = pd.merge(
        current,
        target_df[['County_Name', target_col]],
        on='County_Name',
    )
    merged['scale'] = merged[target_col] / merged[sum_var]

    result = source_df.copy()
    for _, row in merged.iterrows():
        scale = row['scale']
        if abs(scale - 1) < 1e-4:
            continue
        mask = result['County_Name'] == row['County_Name']
        result.loc[mask, sum_var] *= scale
        for var in partial_vars:
            result.loc[mask, var] *= scale
        cols = [sum_var] + partial_vars
        result.loc[mask, cols] = result.loc[mask, cols].round(0)
        result = fix_rounding_artifacts(
            result,
            'TAZ1454',
            sum_var,
            partial_vars,
        )
    return result


def update_gqpop_to_county_totals(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    acs1year: int,
) -> pd.DataFrame:
    """Adjust group quarters population and employment."""
    estimates = pd.DataFrame(
        {
            'County_Name': BAY_AREA_COUNTIES,
            'gq_pop_estimate': [
                8000, 4000, 1000, 800, 7000,
                3000, 10000, 2000, 2000,
            ],
            'gq_emp_estimate': [
                4000, 2000, 500, 400, 3500,
                1500, 5000, 1000, 1000,
            ],
        }
    )
    estimates['worker_share'] = (
        estimates['gq_emp_estimate']
        / estimates['gq_pop_estimate']
    )
    detailed = pd.merge(target_df, estimates, on='County_Name')
    detailed['GQEMP_target'] = (
        detailed['GQPOP_target']
        * detailed['worker_share']
    )
    df = update_tazdata_to_county_target(
        source_df,
        detailed,
        'gqpop',
        [
            'gq_type_univ',
            'gq_type_mil',
            'gq_type_othnon',
        ],
    )
    df = update_tazdata_to_county_target(
        df,
        detailed.rename(
            columns={'GQPOP_target': 'gq_age_target'},
        ),
        'gqpop',
        [
            'AGE0004',
            'AGE0519',
            'AGE2044',
            'AGE4564',
            'AGE65P',
        ],
    )
    df = update_tazdata_to_county_target(
        df,
        detailed.rename(
            columns={'GQEMP_target': 'gq_emp_target'},
        ),
        'EMPRES',
        [
            'pers_occ_management',
            'pers_occ_professional',
            'pers_occ_services',
            'pers_occ_retail',
            'pers_occ_manual',
            'pers_occ_military',
        ],
    )
    return df


# Main routine


def main() -> None:
    # Settings
    YEAR = _cfg['constants']['years'][0]
    LODES_YEAR = min(YEAR, _cfg['constants']['LODES_YEAR_LATEST'])
    _ENV['YEAR'] = YEAR
    _ENV['LODES_YEAR'] = LODES_YEAR

    # Initialize Census client
    key_file = resolve(_cfg['paths']['census_api_key_file'])
    api_key = Path(key_file).read_text().strip()
    c = Census(api_key)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.info(f"Running for YEAR={YEAR}, LODES_YEAR={LODES_YEAR}")

    # Paths
    PBA_TAZ_2015 = resolve(_cfg['paths']['pba_taz_2015'])

    # 1) Fetch block-level population from Decennial PL
    blocks = download_acs_blocks(c, YEAR, 'dec/pl')
    if blocks.empty:
        logging.error('No block data retrieved')
        return
    df_blocks = census_to_df(blocks)

        # 2) Fetch ACS5 block-group income buckets for each county
        # Define fetch variables with ACS estimate suffix (E)
    fetch_vars = [f'B19001_{i:03d}E' for i in range(2, 18)]
    # Define income_vars without suffix for downstream processing
    income_vars = [var[:-1] for var in fetch_vars]
    geo_cfg = _cfg['geo_constants']
    state_code = geo_cfg['STATE_CODE']
    bg_income_records = []
    county_codes = list(geo_cfg['BA_COUNTY_FIPS_CODES'].keys())
    for county_code in county_codes:
        recs = retrieve_census_variables(
            c,
            YEAR,
            'acs5',
            fetch_vars,
            for_geo='block group',
            state=state_code,
            county=county_code
        )
        bg_income_records.extend(recs)
        recs = retrieve_census_variables(
            c,
            YEAR,
            'acs5',
            income_vars,
            for_geo='block group',
            state=state_code,
            county=county_code
        )
        bg_income_records.extend(recs)
        df_bg_inc = census_to_df(bg_income_records)

    # Build block-group GEOID
    df_bg_inc['GEOID_BG'] = (
        df_bg_inc['state'].str.zfill(2)
        + df_bg_inc['county'].str.zfill(3)
        + df_bg_inc['tract']
        + df_bg_inc['block group']
    )

    # Load block→block group crosswalk
    cw_path = resolve(_cfg['paths']['block_to_blockgroup_csv'])
    cw = pd.read_csv(cw_path)
    # cw must have columns ['BLOCKID', 'GEOID_BG']

    # Merge crosswalk onto blocks
    df_blocks = df_blocks.merge(
        cw[['BLOCKID', 'GEOID_BG']],
        left_on='GEOID',
        right_on='BLOCKID',
        how='left'
    )

    # Merge income variables using the computed GEOID_BG
    df_blocks = df_blocks.merge(
        df_bg_inc.set_index('GEOID_BG')[income_vars],
        left_on='GEOID_BG',
        right_index=True,
        how='left'
    )(
        cw[['BLOCKID', 'GEOID_BG']],
        left_on='GEOID',
        right_on='BLOCKID',
        how='left'
    )

    # Merge income variables using the computed GEOID_BG
    df_blocks = df_blocks.merge(
        df_bg_inc.set_index('GEOID_BG')[income_vars],
        left_on='GEOID_BG',
        right_index=True,
        how='left'
    )

    df_blocks = df_blocks.merge(
        df_bg_inc.set_index('GEOID_BG')[income_vars],
        left_on='GEOID_BG',
        right_index=True,
        how='left'
    )

    # 4) Prepare hhinc_map targets (county-level PUMS quartiles)
    hhinc_map = map_acs5year_household_income_to_tm1_categories(YEAR)

    # 5) Scale block-level income buckets to match targets
    scaled = scale_data_to_targets(
        df_blocks,
        hhinc_map,
        'GEOID',
        'P1_001N',
        income_vars
    )
    disagg = update_disaggregate_data_to_aggregate_targets(
        scaled,
        hhinc_map,
        'GEOID', 'GEOID', 'P1_001N'
    )

    # 6) Continue existing workflow for county scaling, GQ, outputs...
    county_df = update_tazdata_to_county_target(
        disagg, hhinc_map, 'P1_001N', income_vars
    )
    gq_df = update_gqpop_to_county_totals(
        county_df, hhinc_map, ACS_PUMS_1YR_LATEST 
    )

    # [output routines unchanged]
    logging.info('Processing complete.')


if __name__ == '__main__':
    main()
