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
import numpy as np


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

def summarize_census_to_taz(working_df: pd.DataFrame, weights_block_df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize BG-adjusted block-level census attributes to TAZ by computing
    weights from BG-adjusted households, ensuring full recovery of totals.

    - Calculates each block's weight_hh as block_BG_hh / TAZ_BG_hh.
    - Applies weights to all numeric attributes in working_df.
    - Aggregates by TAZ1454.
    - Performs a sanity check on 'tothh'.
    - Computes derived 'sum_age' and 'gqpop'.

    Returns DataFrame keyed by TAZ1454 with aggregated variables.
    """
    import numpy as np
    import pandas as pd
    import logging

    # Ensure block_geoid and weights GEOID are same string format for merge
    working_df['block_geoid']    = working_df['block_geoid'].astype(str).str.zfill(15)
    weights_block_df['GEOID']    = weights_block_df['GEOID'].astype(str).str.zfill(15)

    # Bring in TAZ identifier
    df = working_df.merge(
        weights_block_df[['GEOID','TAZ1454']],
        left_on='block_geoid', right_on='GEOID', how='left'
    )

    # Compute BG-adjusted households per block
    df['bg_tothh'] = df['tothh'].fillna(0)

    # Sum to TAZ: total BG-adjusted households
    df['taz_hh'] = df.groupby('TAZ1454')['bg_tothh'].transform('sum')

    # Weight by household share within TAZ
    df['weight_hh'] = np.where(df['taz_hh']>0, df['bg_tothh']/df['taz_hh'], 0)

    # Identify attribute columns (exclude IDs, shares, and bg/taz helper cols)
    exclude = {
        'block_geoid','blockgroup','tract','GEOID','TAZ1454',
        'pop','bg_pop','pop_share','tract_pop','tract_share','bg_tothh','taz_hh','weight_hh'
    }
    attr_cols = [c for c in df.columns if c not in exclude]
    df[attr_cols] = df[attr_cols].apply(pd.to_numeric, errors='coerce')

    # Apply household-based weight
    for col in attr_cols:
        df[col] = df[col].fillna(0) * df['weight_hh']

    # Aggregate to TAZ
    taz = df.groupby('TAZ1454', as_index=False)[attr_cols].sum()

    # Sanity: check tothh
    raw = working_df['tothh'].sum()
    agg = taz['tothh'].sum()
    if abs(raw-agg) > 1e-6:
        logging.warning(f"tothh mismatch: raw {raw} vs agg {agg}")

    # Derived age and gq
    age_bins = [c for c in ['age0004','age0519','age2044','age4564','age65p'] if c in taz]
    if age_bins:
        taz['sum_age'] = taz[age_bins].sum(axis=1)
    gq_cols = [c for c in taz.columns if c.startswith('gq_')]
    if gq_cols:
        taz['gqpop'] = taz[gq_cols].sum(axis=1)

    return taz



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
def step10_integrate_employment(
    taz_base: pd.DataFrame,
    taz_census: pd.DataFrame,
    year: int
) -> pd.DataFrame:
    """
    Step 10: Merge your census‐derived TAZ summary and employment
    into the base TAZ DataFrame, avoiding any _x/_y collisions.

    Parameters
    ----------
    taz_base : pd.DataFrame
      Output of Step 9 (must include a 'taz' column).
    taz_census : pd.DataFrame
      Output of summarize_census_to_taz(...), keyed on 'taz'.
    year : int
      Processing year (for naming any output file).

    Returns
    -------
    pd.DataFrame
      A DataFrame with:
        - all original taz_base columns (plus every census field, merged & coalesced),
        - EMPRES (wage & salary) and TOTEMP (total) employment columns.
    """


    logger = logging.getLogger(__name__)

    # --- 1) Merge in all census fields, give them "_cns" suffix to avoid collisions ---
    merged = taz_base.merge(
        taz_census,
        on="taz",
        how="left",
        suffixes=("", "_cns")
    ).fillna(0)

    # --- 2) Auto-coalesce every "_cns" column back into its base name ---
    cns_cols = [c for c in merged.columns if c.endswith("_cns")]
    for cns in cns_cols:
        base = cns[:-4]  # strip off "_cns"
        # cast to int after filling
        merged[base] = (
            merged[base]
                  .fillna( merged[cns] )
                  .astype(int)
        )
    merged.drop(columns=cns_cols, inplace=True)
    logger.info("Census fields merged & coalesced")

    # --- 3) Load & prep LODES wage-salary data ---
    path_lodes = os.path.expandvars(PATHS['wage_salary_csv'])
    df_lodes = pd.read_csv(path_lodes, dtype=str)
    logger.info(f"Loaded LODES data from {path_lodes}, columns: {df_lodes.columns.tolist()}")

    # Ensure TAZ key
    df_lodes['taz'] = df_lodes['TAZ1454'].astype(str)
    df_lodes['EMPRES'] = (
        pd.to_numeric(df_lodes['TOTEMP'], errors='coerce')
          .fillna(0).astype(int)
    )

    # --- 4) Load & prep self-employment data ---
    path_self = os.path.expandvars(PATHS['self_employment_csv'])
    df_self = pd.read_csv(path_self, dtype=str)
    df_self = df_self.rename(columns={'zone_id':'taz', 'value':'emp_self'})
    df_self['emp_self'] = (
        pd.to_numeric(df_self['emp_self'], errors='coerce')
          .fillna(0).astype(int)
    )
    self_emp = df_self.groupby('taz', as_index=False)['emp_self'].sum()

    # --- 5) Combine into a single employment table ---
    df_emp = (
        df_lodes[['taz','EMPRES']]
          .merge(self_emp, on='taz', how='outer')
          .fillna(0)
    )
    df_emp['TOTEMP'] = (df_emp['EMPRES'] + df_emp['emp_self']).astype(int)

    # optional: write for inspection
    out_emppath = os.path.join(
        os.getcwd(),
        f"step10_employment_combined_{year}.csv"
    )
    #df_emp.to_csv(out_emppath, index=False)
    logger.info(f"Wrote combined employment data to {out_emppath}")

    # --- 6) Merge EMPRES & TOTEMP into the now census-enhanced TAZ base ---
    final = merged.merge(
        df_emp[['taz','EMPRES','TOTEMP']],
        on='taz',
        how='left'
    ).fillna(0)
    final['EMPRES'] = final['EMPRES'].astype(int)
    final['TOTEMP'] = final['TOTEMP'].astype(int)

    logger.info("Employment integrated into TAZ base")
    return final

def step11_compute_scale_factors(
    taz_df: pd.DataFrame,
    taz_targeted: pd.DataFrame,
    base_col: str,
    target_col: str
) -> pd.DataFrame:
    """
    For each county, compute a scale factor = (sum target_col) / (sum base_col),
    then assign that factor to every TAZ in the county.

    Returns a DataFrame with columns ['taz','scale_factor'].
    """
    logger = logging.getLogger(__name__)

    # 1) Sum up the base & target by county
    current = (
        taz_df
          .groupby('county_fips', as_index=False)[base_col]
          .sum()
          .rename(columns={base_col: 'current_total'})
    )
    target = (
        taz_targeted
          .groupby('county_fips', as_index=False)[target_col]
          .sum()
          .rename(columns={target_col: 'target_total'})
    )

    df_cnty = current.merge(target, on='county_fips', how='left').fillna(0)

    # 2) Compute ratio, guarding against zero division
    df_cnty['scale_factor'] = np.where(
        df_cnty['current_total'] > 0,
        df_cnty['target_total'] / df_cnty['current_total'],
        1.0
    )

    # Log a quick sanity check
    total_sf = df_cnty['scale_factor'].sum()
    logger.info(
        "[SANITY] step11_compute_scale_factors: "
        "sum of scale_factors = %.3f", total_sf
    )

    # 3) Map the county-level factor back to each TAZ
    scale_df = (
        taz_df[['taz','county_fips']]
          .merge(
              df_cnty[['county_fips','scale_factor']],
              on='county_fips',
              how='left'
          )
    )

    # Final sanity check: no nulls, all positive
    if scale_df['scale_factor'].isnull().any():
        raise RuntimeError("[SANITY] Missing scale_factor for some TAZs")
    if (scale_df['scale_factor'] <= 0).any():
        raise RuntimeError("[SANITY] Non-positive scale_factor found")

    return scale_df

def apply_county_targets_to_taz(
    taz_df: pd.DataFrame,
    county_targets: pd.DataFrame,
    popsyn_acs_pums_5year: int
) -> pd.DataFrame:
    """
    Push county-level target totals back down to each TAZ across multiple metrics,
    mirroring the R update_tazdata_to_county_target calls in sequence,
    and use the ACS PUMS 5-year vintage for household-size consistency.

    Args:
        taz_df: DataFrame of TAZ-level data, must include 'county_fips' and all source columns.
        county_targets: DataFrame with 'county_fips' and *_target columns for each metric.
        popsyn_acs_pums_5year: ACS PUMS 5-year vintage used for household-size and worker-consistency.

    Returns:
        DataFrame: Updated TAZ-level DataFrame with county targets applied.
    """
    import logging
    from common import update_tazdata_to_county_target, make_hhsizes_consistent_with_population

    logger = logging.getLogger(__name__)
    df = taz_df.copy()

    # 1) Scale employment
    logger.info("Applying county EMPRES targets to TAZ")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets,
        sum_var      = 'EMPRES',
        partial_vars = [
            'pers_occ_management', 'pers_occ_professional',
            'pers_occ_services',   'pers_occ_retail',
            'pers_occ_manual',     'pers_occ_military'
        ]
    )

    # 2) Scale total population & households
    logger.info("Applying county household and population targets to TAZ")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'TOTPOP_target':'sum_age_target'}),
        sum_var      = 'sum_age',
        partial_vars = ['AGE0004','AGE0519','AGE2044','AGE4564','AGE65P']
    )
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'TOTPOP_target':'sum_ethnicity_target'}),
        sum_var      = 'sum_ethnicity',
        partial_vars = ['white_nonh','black_nonh','asian_nonh','other_nonh','hispanic']
    )

    # 3) Scale housing units & tenure
    logger.info("Applying county housing-unit and tenure targets to TAZ")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'TOTHH_target':'sum_DU_target'}),
        sum_var      = 'sum_DU',
        partial_vars = ['SFDU','MFDU']
    )
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'TOTHH_target':'sum_tenure_target'}),
        sum_var      = 'sum_tenure',
        partial_vars = ['hh_own','hh_rent']
    )

    # 4) Scale households with kids
    logger.info("Applying county household-with-kids targets to TAZ")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'TOTHH_target':'sum_kids_target'}),
        sum_var      = 'sum_kids',
        partial_vars = ['hh_kids_yes','hh_kids_no']
    )

    # 5) Scale income quartiles
    logger.info("Applying county income-quartile targets to TAZ")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'TOTHH_target':'sum_income_target'}),
        sum_var      = 'sum_income',
        partial_vars = ['HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4']
    )

    # 6) Scale household size & enforce PUMS distribution
    logger.info("Applying county household-size targets to TAZ")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'TOTHH_target':'sum_size_target'}),
        sum_var      = 'sum_size',
        partial_vars = ['hh_size_1','hh_size_2','hh_size_3','hh_size_4_plus']
    )
    df = make_hhsizes_consistent_with_population(
        source_df             = df,
        target_df             = county_targets,
        size_or_workers       = 'hh_size',
        popsyn_acs_pums_5year = popsyn_acs_pums_5year
    )

    # 7) Scale household workers & enforce PUMS distribution
    logger.info("Applying county household-worker targets to TAZ")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'TOTHH_target':'sum_hhworkers_target'}),
        sum_var      = 'sum_hhworkers',
        partial_vars = ['hh_wrks_0','hh_wrks_1','hh_wrks_2','hh_wrks_3_plus']
    )
    df = make_hhsizes_consistent_with_population(
        source_df             = df,
        target_df             = county_targets,
        size_or_workers       = 'hh_wrks',
        popsyn_acs_pums_5year = popsyn_acs_pums_5year
    )

    # 8) Final adjustments: overwrite TOTHH and TOTPOP
    df['TOTHH']  = df['sum_size']
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