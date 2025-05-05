#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
integrate_and_scale.py

Module to integrate employment data and apply scaling factors.
Executes:
  STEP 10: Integrate LODES and self-employed data at TAZ level
  STEP 11: Compute scale factors comparing base and targeted totals
  STEP 12: Apply scale factors to TAZ variables
"""
import os
import logging
from pathlib import Path
import pandas as pd
import yaml
from typing import List
from census import Census
import logging
import time
from common import update_tazdata_to_county_target
from common import make_hhsizes_consistent_with_population


# Load configuration
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)
CONSTANTS = cfg['constants']
PATHS = cfg['paths']
VARIABLES = cfg['variables']
GEO= cfg.get('geo_constants', {})   

STATE_CODE           = GEO.get('STATE_CODE')
BAY_COUNTIES         = GEO.get('BAY_COUNTIES', [])
ACS_5YEAR_LATEST     = CONSTANTS.get('ACS_5YEAR_LATEST')
ACS_PUMS_1YEAR_LATEST= CONSTANTS.get('ACS_PUMS_1YEAR_LATEST')
EMPRES_LODES_WEIGHT  = CONSTANTS.get('EMPRES_LODES_WEIGHT', 0.0)

def summarize_census_to_taz(working_df, weights_block_df):
    """
    Summarize raw block-level working data to TAZ with:
      - TOTPOP : total population (hhpop_ + gqpop)
      - TOTHH  : total households (tothh_)
      - HHPOP  : household population (hhpop_)
      - gqpop  : group-quarters population
    
    Expects:
      working_df       : DataFrame with 'block_geoid', 'blockgroup', 'tothh_', 'hhpop_', 'gq_*'
      weights_block_df : DataFrame with ['GEOID','blockgroup','TAZ1454','weight']
    """
    import logging
    logger = logging.getLogger(__name__)
    import pandas as pd

    # 1) Rename TAZ and cast blockgroup → str on both
    wb = weights_block_df.rename(columns={'TAZ1454': 'taz'}).copy()
    wb['blockgroup'] = wb['blockgroup'].astype(str)
    wb['taz']        = wb['taz'].astype(str)

    df = working_df.copy()
    df['blockgroup'] = df['blockgroup'].astype(str)

    # 2) Merge on blockgroup (not block_geoid)
    tmp = df.merge(
        wb[['blockgroup','taz','weight']],
        on='blockgroup',
        how='left'
    )
    missing = tmp['weight'].isna().sum()
    if missing > 0:
        logger.warning(f"{missing} working rows missing a BG→TAZ weight")

    # 3) Build gqpop, then weight all counts
    gq_cols = [c for c in tmp.columns if c.startswith('gq_inst') or c.startswith('gq_noninst')]
    tmp['gqpop']    = tmp[gq_cols].sum(axis=1)
    tmp['TOTHH_taz']  = tmp['tothh_']  * tmp['weight']
    tmp['HHPOP_taz']  = tmp['hhpop_']  * tmp['weight']
    tmp['gqpop_taz']  = tmp['gqpop']   * tmp['weight']
    tmp['TOTPOP_taz'] = (tmp['hhpop_'] + tmp['gqpop']) * tmp['weight']

    # 4) Aggregate to TAZ
    taz_census = tmp.groupby('taz', as_index=False).agg(
        TOTPOP = ('TOTPOP_taz', 'sum'),
        TOTHH  = ('TOTHH_taz',  'sum'),
        HHPOP  = ('HHPOP_taz',  'sum'),
        gqpop  = ('gqpop_taz',  'sum'),
    )
    return taz_census


def _compute_current_totals(df):
    """
    Compute current county-level aggregates for population, households, base employment, and target employment.
    Returns a DataFrame with ['county_fips','County_Name','TOTPOP','TOTHH','HHPOP','gqpop','EMPRES','TOTEMP'].
    """
    logger = logging.getLogger(__name__)
    # Ensure county_fips is just the 3-digit code
    df = df.copy()
    df['county_fips'] = df['county_fips'].astype(str).str[-3:]

    # Aggregate raw population/household counts by county_fips
    pop_agg = df.groupby('county_fips', as_index=False).agg(
        TOTPOP=('TOTPOP', 'sum'),
        TOTHH=('TOTHH', 'sum'),
        HHPOP=('HHPOP', 'sum'),
        gqpop=('gqpop', 'sum')
    )
    # Map 3-digit FIPS to county name
    pop_agg['County_Name'] = pop_agg['county_fips'].map(GEO['BA_COUNTY_FIPS_CODES'])

    # Aggregate base employment by county_fips
    emp_base = df.groupby('county_fips', as_index=False)['EMPRES'].sum()
    emp_base = emp_base.rename(columns={'EMPRES': 'EMPRES'})

    # Aggregate target employment (TOTEMP) by county_fips
    emp_target = df.groupby('county_fips', as_index=False)['TOTEMP'].sum()
    emp_target = emp_target.rename(columns={'TOTEMP': 'TOTEMP'})

    # Merge population, base, and target employment
    current = (
        pop_agg
        .merge(emp_base, on='county_fips', how='left')
        .merge(emp_target, on='county_fips', how='left')
    )
    # Debug: inspect current
    logger.info(f"Current totals columns: {current.columns.tolist()}")
    logger.info("Current totals preview:\n%s", current.head().to_string(index=False))
    return current


def _initialize_targets(current):
    """
    Initialize target columns equal to base values for pop, hh, and target employment for EMPRES.
    """
    logger = logging.getLogger(__name__)
    targets = current.copy()
    for col in ['TOTPOP', 'TOTHH', 'HHPOP', 'gqpop']:
        targets[f'{col}_target'] = targets[col]
    # Use TOTEMP as initial EMPRES_target
    targets['EMPRES_target'] = targets['TOTEMP'].fillna(0).astype(int)
    # Debug: inspect initialized targets
    logger.info(f"Initialized targets columns: {targets.columns.tolist()}")
    logger.info("Initialized targets preview:\n%s", targets.head().to_string(index=False))
    return targets


def _apply_acs_adjustment(county_targets, census_client, acs_year, pums_year):
    """
    Adjust county_targets using ACS 1-year estimates when acs_year < pums_year + 2.
    Returns updated county_targets.
    """
    logger = logging.getLogger(__name__)
    var_map = VARIABLES.get('ACS_1YEAR_TARGET_VARS')
    if not var_map:
        raise ValueError("CONFIG ERROR: 'ACS_1YEAR_TARGET_VARS' missing in VARIABLES.")

    if acs_year >= pums_year + 2:
        return county_targets

    logger.info("Applying ACS 1-year county targets adjustment")
    records = []
    for cnt in county_targets['county_fips']:
        # Retry logic
        recs = []
        for attempt in range(3):
            try:
                recs = census_client.acs5.state_county(
                    list(var_map.values()), GEO['STATE_CODE'], cnt,
                    year=pums_year
                )
                break
            except Exception as e:
                logger.warning(f"ACS API failed for {cnt} (attempt {attempt+1}): {e}")
                time.sleep(2 ** attempt)
        if not recs:
            logger.error(f"No ACS data for county {cnt}, skipping ACS adjustment")
            continue

        for r in recs:
            name = r.get('NAME', '').replace(' County, California', '')
            row = {'county_fips': cnt, 'County_Name': name}
            for out_col, code in var_map.items():
                row[out_col] = int(float(r.get(code, 0)))
            records.append(row)

    df_acs = pd.DataFrame(records)
    if df_acs.empty:
        return county_targets

    # Derive gqpop_target and EMPRES_target
    df_acs['gqpop_target'] = df_acs['TOTPOP_target'] - df_acs['HHPOP_target']
    df_acs['EMPRES_target'] = df_acs['employed_'] + df_acs['armedforces_']

    cols = [
        'county_fips', 'County_Name',
        'TOTHH_target', 'TOTPOP_target', 'HHPOP_target', 'gqpop_target', 'EMPRES_target'
    ]
    df_acs = df_acs[cols]

    # Merge and overwrite
    merged = county_targets.merge(
        df_acs, on=['county_fips', 'County_Name'], how='left', suffixes=('', '_acs')
    )
    for col in [
        'TOTHH_target', 'TOTPOP_target', 'HHPOP_target', 'gqpop_target', 'EMPRES_target'
    ]:
        merged[col] = merged[f'{col}_acs'].fillna(merged[col])
        merged = merged.drop(columns=[f'{col}_acs'])
    return merged


def _add_institutional_gq(county_targets, dhc_gqpop):
    """
    Add institutional group-quarters population (gq_inst) to county_targets.
    """
    if 'gq_inst' not in dhc_gqpop.columns:
        return county_targets
    dhc = dhc_gqpop.groupby('County_Name', as_index=False).gq_inst.sum()
    merged = county_targets.merge(dhc, on='County_Name', how='left')
    merged['gqinst'] = merged['gq_inst'].fillna(0).astype(int)
    return merged


def build_county_targets(
    tazdata_census,
    dhc_gqpop,
    acs_5year,
    acs_pums_1year,
    census_client
):
    """
    Orchestrate county-level target building by sequencing subtasks.
    """
    logger = logging.getLogger(__name__)

    # Debug: inspect input
    logger.info(f"build_county_targets received tazdata_census shape: {tazdata_census.shape}")
    logger.info("tazdata_census preview:\n%s", tazdata_census.head().to_string(index=False))

    # Step 1: current totals
    current = _compute_current_totals(tazdata_census)
    # Step 2: initialize targets
    county_targets = _initialize_targets(current)
    # Step 3: ACS adjustment
    county_targets = _apply_acs_adjustment(
        county_targets, census_client, acs_5year, acs_pums_1year
    )
    # Step 4: institutional GQ
    county_targets = _add_institutional_gq(county_targets, dhc_gqpop)

    # Debug: inspect final before cast
    logger.info(f"County targets before final cast columns: {county_targets.columns.tolist()}")
    logger.info("County targets before final cast preview:\n%s", county_targets.head().to_string(index=False))

    # Final cast - ensure all numeric fields are ints
    for col in [
        'TOTPOP','TOTHH','HHPOP','gqpop','TOTEMP',
        'TOTPOP_target','TOTHH_target','HHPOP_target','gqpop_target',
        'EMPRES','EMPRES_target'
    ]:
        county_targets[col] = county_targets[col].astype(int)

    logger.info(f"Final county_targets columns: {county_targets.columns.tolist()}")
    logger.info("Final county_targets preview:\n%s", county_targets.head().to_string(index=False))
    return county_targets
# ------------------------------
# STEP 10: Integrate employment
# ------------------------------
def step10_integrate_employment(year):
    """
    Integrate LODES wage & salary employment and self-employment into a single TAZ-level DataFrame.

    Reads:
      - PATHS['wage_salary_csv'] : CSV with columns ["COUNTY_NAME", "TAZ1454", "AGREMPN", "FPSEMPN", 
                                      "HEREMPN", "MWTEMPN", "RETEMPN", "OTHEMPN", "TOTEMP"]
      - PATHS['self_employment_csv']: CSV with columns ["zone_id", "industry", "value"]

    Returns:
      - DataFrame with columns:
          - taz       : TAZ ID (string)
          - emp_lodes : total wage & salary employment from TOTEMP
          - emp_self  : sum of self-employment value across industries
    """
    import os
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)

    # 1) Load LODES wage & salary data
    path_lodes = os.path.expandvars(PATHS['wage_salary_csv'])
    df_lodes = pd.read_csv(path_lodes, dtype=str)
    logger.info(f"Loaded LODES data from {path_lodes}, columns: {df_lodes.columns.tolist()}")

    # Ensure TAZ key
    df_lodes['taz'] = df_lodes['TAZ1454'].astype(str)
    # Extract total employment
    df_lodes['emp_lodes'] = pd.to_numeric(df_lodes['TOTEMP'], errors='coerce').fillna(0).astype(int)
    lodes = df_lodes[['taz', 'emp_lodes']]

    # 2) Load self-employment data
    path_self = os.path.expandvars(PATHS['self_employment_csv'])
    df_self = pd.read_csv(path_self, dtype=str)
    logger.info(f"Loaded self-employment data from {path_self}, columns: {df_self.columns.tolist()}")

    # Normalize and aggregate
    df_self = df_self.rename(columns={'zone_id': 'taz', 'value': 'emp_self'})
    df_self['emp_self'] = pd.to_numeric(df_self['emp_self'], errors='coerce').fillna(0).astype(int)
    self_emp = df_self.groupby('taz', as_index=False)['emp_self'].sum()

    # 3) Merge LODES and self-employment
    df_emp = lodes.merge(self_emp, on='taz', how='outer').fillna(0)

    # Convert to appropriate dtypes
    df_emp['emp_lodes'] = df_emp['emp_lodes'].astype(int)
    df_emp['emp_self']  = df_emp['emp_self'].astype(int)

    # 4) Write intermediate files for inspection
    merged_path = os.path.join(os.getcwd(), 'step10_employment_combined.csv')
    df_emp.to_csv(merged_path, index=False)
    logger.info(f"Wrote combined employment data to {merged_path}")

    return df_emp

def step11_compute_scale_factors(taz_df: pd.DataFrame,
                                 taz_targeted: pd.DataFrame,
                                 key: str = 'taz',
                                 target_col: str = 'county_target',
                                 base_col: str = 'county_base') -> pd.DataFrame:
    """
    For each TAZ, compute the ratio of targeted county total to
    the base county total, yielding a scale_factor.
    """
    # 1) Sum up base values by TAZ
    base_totals = (
        taz_df
        .groupby(key)[base_col]
        .sum()
        .reset_index()
        .rename(columns={base_col: 'base_total'})
    )

    # 2) Pull in the targeted totals (already one row per TAZ)
    targets = taz_targeted[[key, target_col]].rename(columns={target_col: 'target_total'})

    # 3) Merge and compute factor
    scale_df = (
        base_totals
        .merge(targets, on=key, how='left')
    )
    scale_df['scale_factor'] = scale_df['target_total'] / scale_df['base_total']

    return scale_df[[key, 'scale_factor']]

def apply_county_targets_to_taz(
    taz_df: pd.DataFrame,
    county_targets: pd.DataFrame,
    popsyn_ACS_PUMS_5YEAR: int
) -> pd.DataFrame:
    """
    Push county-level target totals back down to each TAZ across multiple metrics.

    Args:
        taz_df: DataFrame of TAZ-level data.
        county_targets: DataFrame with county_fips and *_target columns.
        popsyn_ACS_PUMS_5YEAR: ACS PUMS 1-year vintage for size/work consistency.

    Returns:
        DataFrame: Updated TAZ-level DataFrame with county targets applied.
    """
    logger = logging.getLogger(__name__)
    df = taz_df.copy()

    logger.info("Applying county EMPRES targets to TAZ")
    df = update_tazdata_to_county_target(
        source_df=df,
        target_df=county_targets,
        sum_var='EMPRES',
        partial_vars=[
            'pers_occ_management', 'pers_occ_professional',
            'pers_occ_services', 'pers_occ_retail',
            'pers_occ_manual', 'pers_occ_military'
        ]
    )

    logger.info("Applying county household and population targets to TAZ")
    # Total households & population by age
    df = update_tazdata_to_county_target(
        source_df=df,
        target_df=county_targets.rename(columns={'TOTPOP_target':'sum_age_target'}),
        sum_var='sum_age',
        partial_vars=['AGE0004','AGE0519','AGE2044','AGE4564','AGE65P']
    )
    # Population by ethnicity
    df = update_tazdata_to_county_target(
        source_df=df,
        target_df=county_targets.rename(columns={'TOTPOP_target':'sum_ethnicity_target'}),
        sum_var='sum_ethnicity',
        partial_vars=['white_nonh','black_nonh','asian_nonh','other_nonh','hispanic']
    )
    # Housing units
    df = update_tazdata_to_county_target(
        source_df=df,
        target_df=county_targets.rename(columns={'TOTHH_target':'sum_DU_target'}),
        sum_var='sum_DU',
        partial_vars=['SFDU','MFDU']
    )
    # Tenure
    df = update_tazdata_to_county_target(
        source_df=df,
        target_df=county_targets.rename(columns={'TOTHH_target':'sum_tenure_target'}),
        sum_var='sum_tenure',
        partial_vars=['hh_own','hh_rent']
    )
    # Households with kids
    df = update_tazdata_to_county_target(
        source_df=df,
        target_df=county_targets.rename(columns={'TOTHH_target':'sum_kids_target'}),
        sum_var='sum_kids',
        partial_vars=['hh_kids_yes','hh_kids_no']
    )
    # Income quartiles
    df = update_tazdata_to_county_target(
        source_df=df,
        target_df=county_targets.rename(columns={'TOTHH_target':'sum_income_target'}),
        sum_var='sum_income',
        partial_vars=['HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4']
    )
    # Household size
    df = update_tazdata_to_county_target(
        source_df=df,
        target_df=county_targets.rename(columns={'TOTHH_target':'sum_size_target'}),
        sum_var='sum_size',
        partial_vars=['hh_size_1','hh_size_2','hh_size_3','hh_size_4_plus']
    )
    df = make_hhsizes_consistent_with_population(
        source_df=df,
        target_df=county_targets,
        size_or_workers='hh_size',
        popsyn_ACS_PUMS_5YEAR=popsyn_ACS_PUMS_5YEAR
    )
    # Household workers
    df = update_tazdata_to_county_target(
        source_df=df,
        target_df=county_targets.rename(columns={'TOTHH_target':'sum_hhworkers_target'}),
        sum_var='sum_hhworkers',
        partial_vars=['hh_wrks_0','hh_wrks_1','hh_wrks_2','hh_wrks_3_plus']
    )
    df = make_hhsizes_consistent_with_population(
        source_df=df,
        target_df=county_targets,
        size_or_workers='hh_wrks',
        popsyn_ACS_PUMS_5YEAR=popsyn_ACS_PUMS_5YEAR
    )

    # Final household and total population
    df['TOTHH'] = df['sum_size']
    df['TOTPOP'] = df['HHPOP'] + df['gqpop']

    return df
    return result

def step12_apply_scaling(taz_df: pd.DataFrame,
                         taz_targeted: pd.DataFrame,
                         scale_key: str = 'taz',
                         vars_to_scale: List[str] = None) -> pd.DataFrame:
    """
    Merge in scale_factor and multiply each designated variable by it.
    """
    # 1) Compute scale factors
    scale_df = step11_compute_scale_factors(
        taz_df,
        taz_targeted,
        key=scale_key,
        target_col='county_target',
        base_col='county_base'
    )

    # 2) Merge onto TAZ
    df = taz_df.merge(scale_df, on=scale_key, how='left')

    # 3) Apply scaling to each variable
    if vars_to_scale is None:
        # default to all numeric columns except the key
        vars_to_scale = [
            c for c in df.columns
            if c not in (scale_key, 'scale_factor')
               and pd.api.types.is_numeric_dtype(df[c])
        ]

    for col in vars_to_scale:
        df[col] = df[col] * df['scale_factor']

    return df

# ------------------------------
# MAIN: integrate employment and apply scaling
# ------------------------------
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # STEP 10: Integrate employment data
    # Combine household income and ACS summaries into unified TAZ DataFrame
    taz_hh = taz_hhinc.rename(columns={'TAZ1454':'taz'})
    taz_hh['taz'] = taz_hh['taz'].astype(str)
    taz_acs['taz'] = taz_acs['taz'].astype(str)
    taz = taz_hh.merge(taz_acs, on='taz', how='left')

    # Step 10: integrate employment
    df_emp = step10_integrate_employment(YEAR)
    taz = taz.merge(df_emp, on='taz', how='left')

    # Step 11: compute scale factors
    # taz_targeted: DataFrame with county_target and county_base for each TAZ
    # For now, copy taz to serve as both base and target
    taz_targeted = taz.copy()
    scale_df = step11_compute_scale_factors(taz, taz_targeted)
    print('Scale factors computed: rows=', scale_df.shape[0])

    # Step 12: apply scaling
    taz_scaled = step12_apply_scaling(taz, taz_targeted,
                                      vars_to_scale=['emp_lodes','emp_self'])


