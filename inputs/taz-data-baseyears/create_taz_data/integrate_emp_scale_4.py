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

    Returns DataFrame keyed by ['taz','county_fips'] with aggregated variables.
    """
    import numpy as np
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting summarize_census_to_taz: %d blocks, %d weight rows", 
                len(working_df), len(weights_block_df))

    # Standardize block GEOID formats
    working_df['block_geoid'] = working_df['block_geoid'].astype(str).str.zfill(15)
    weights_block_df['GEOID'] = weights_block_df['GEOID'].astype(str).str.zfill(15)
    logger.debug("After zero-fill: working_df.block_geoid sample: %s", 
                 working_df['block_geoid'].head().tolist())

    # Merge weights to working records
    weights_block_df = weights_block_df.rename(columns={'GEOID':'block_geoid'})
    df = working_df.merge(
        weights_block_df[['block_geoid','TAZ1454']],
        on='block_geoid', how='left', validate='many_to_one'
    )
    logger.info("After merge: %d rows, %d missing TAZ1454", 
                len(df), df['TAZ1454'].isna().sum())

    # Derive county_fips directly from block_geoid
    df['county_fips'] = df['block_geoid'].str[:5]

    # Compute BG-adjusted totals
    df['bg_tothh'] = df['tothh'].fillna(0)
    df['bg_hhpop'] = df['hhpop'].fillna(0)
    logger.debug("BG sums sample: %s", df[['bg_tothh','bg_hhpop']].head().to_string(index=False))

    # TAZ-level sums of BG-adjusted households and pop
    df['taz_bg_hh'] = df.groupby('TAZ1454')['bg_tothh'].transform('sum')
    df['taz_bg_pop'] = df.groupby('TAZ1454')['bg_hhpop'].transform('sum')
    logger.debug("TAZ BG totals sample: %s", 
                 df.groupby('TAZ1454')[['taz_bg_hh','taz_bg_pop']].first().head().to_string())

    # Compute block weights
    df['weight_hh'] = np.where(df['taz_bg_hh']>0, df['bg_tothh']/df['taz_bg_hh'], 0)
    logger.debug("Weight_hh stats: %s", df['weight_hh'].describe().to_string())

    # Identify attribute columns to weight
    numeric_cols = [c for c in df.columns if np.issubdtype(df[c].dtype, np.number)]
    no_weight = {'bg_tothh','bg_hhpop','tothh','hhpop','taz_bg_hh','taz_bg_pop','weight_hh','TAZ1454','taz'}
    attr_cols = [c for c in numeric_cols if c not in no_weight]
    logger.info("Attributes to be weighted: %s", attr_cols)

    # Apply household-based weight to attributes
    for col in attr_cols:
        df[col] = df[col].fillna(0) * df['weight_hh']
    logger.debug("After weighting sample: %s", df[attr_cols].head().to_string(index=False))

    # Aggregate weighted attributes to TAZ and county
    taz = df.groupby(['TAZ1454','county_fips'], as_index=False)[attr_cols].sum()
    logger.info("After aggregate: %d TAZ-county rows", len(taz))

    # Restore true totals
    restore = df.groupby(['TAZ1454','county_fips'])[['bg_tothh','bg_hhpop']].sum()
    restore = restore.rename(columns={'bg_tothh':'tothh','bg_hhpop':'hhpop'}).reset_index()
    taz = taz.merge(restore, on=['TAZ1454','county_fips'], how='left')
    logger.info("Restored true tothh and hhpop: sample %s", 
                taz[['tothh','hhpop']].head().to_string(index=False))
        # Compute gqpop as totpop - hhpop if not present
    if 'gqpop' not in taz.columns:
        taz['gqpop'] = taz.get('totpop', taz['hhpop']) - taz['hhpop']

    # Ensure taz key
    if 'taz' not in taz.columns:
        taz['taz'] = taz['TAZ1454'].astype(str).str.zfill(4)
    logger.info("Final TAZ columns: %s", taz.columns.tolist())
    return taz





def _apply_acs_adjustment(county_targets: pd.DataFrame,
                          census_client,
                          acs_year: int,
                          pums_year: int) -> pd.DataFrame:
    import logging, time
    logger = logging.getLogger(__name__)
    logger.info(f"Applying ACS1 adjustment for pums_year={pums_year}")
    # Use canonical ACS1 codes
    var_map = {
        'TOTHH_target':  'B11016_001E',
        'TOTPOP_target': 'B01003_001E',
        'HHPOP_target':  'B09019_001E',
        'employed':      'B23025_004E',
        'armedforces':   'B23025_005E'
    }

    # Ensure county_fips are strings and zero-padded 5-digit FIPS
    county_targets['county_fips'] = (
        county_targets['county_fips']
        .astype(int).astype(str)
        .str.zfill(5)
    ).str.extract(r'(\d{1,5})$')[0].str.zfill(5)

    records = []
    for cnt in county_targets['county_fips']:
        # Debug: log county before call
        logger.info(f"About to call ACS1 for county_fips={cnt}")
        # Extract 3-digit county code for API
        county_arg = cnt[-3:]
        logger.info(f"Fetching ACS1 for county {county_arg}")

        recs = []
        for attempt in range(1, 4):
            try:
                logger.debug(
                    f"ACS1 call: vars={list(var_map.values())}, state={GEO['STATE_CODE']},"
                    f" county={county_arg}, year={pums_year}"
                )
                recs = census_client.acs1.state_county(
                    list(var_map.values()),
                    GEO['STATE_CODE'],
                    county_arg,
                    year=pums_year
                )
                logger.debug(f"ACS1 response for {cnt} (arg {county_arg}): {recs}")
                break
            except Exception as e:
                logger.error(f"ACS1 failure for {county_arg} attempt {attempt}: {e}")
                time.sleep(2 ** (attempt - 1))
        if not recs:
            logger.error(f"No ACS1 data for county {county_arg} after retries, skipping ACS adjustment")
            continue

        # Normalize header/value or dict format
        if isinstance(recs[0], list):
            header, values = recs[0], (recs[1] if len(recs) > 1 else [])
            recs_to_process = [dict(zip(header, values))]
        else:
            recs_to_process = recs

        for r in recs_to_process:
            row = {'county_fips': cnt}
            for out_col, code in var_map.items():
                row[out_col] = int(float(r.get(code, 0)))
            records.append(row)

    logger.info(f"Total ACS records: {len(records)}")
    df_acs = pd.DataFrame(records)
    if df_acs.empty:
        logger.warning("No ACS1 records collected; returning original county_targets")
        return county_targets

    # Merge ACS targets
    merged = county_targets.merge(
        df_acs, on='county_fips', how='left', suffixes=('', '_acs')
    )
    # Overwrite with ACS where available
    for col in [c for c in df_acs.columns if c != 'county_fips']:
        merged[col] = merged[f"{col}_acs"].fillna(merged[col])
        merged.drop(columns=[f"{col}_acs"], inplace=True)

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
    tazdata_census: pd.DataFrame,
    dhc_gqpop: pd.DataFrame,
    acs_5year: int,
    acs_pums_1year: int,
    census_client
) -> pd.DataFrame:
    """
    Compute county targets from TAZ-level census data in one pass.

    Parameters
    ----------
    tazdata_census : DataFrame
        Must include at least ['county_fips','tothh','hhpop','empres','gqpop']
        (and optionally 'totpop','totemp' if already computed).
    dhc_gqpop : DataFrame
        Group-quarters totals for each county.
    acs_5year : int
        ACS 5-year vintage (e.g. 2023).
    acs_pums_1year : int
        PUMS 1-year vintage (e.g. 2023).
    census_client :
        Your Census API client instance.


    Returns
    -------
    county_targets : DataFrame
        One row per county_fips, with columns:
          - tothh, hhpop, empres, gqpop, totpop, totemp  
          - their *_target counterparts  
          - *_diff diagnostics  
        All numeric columns cast to int and filtered to valid_counties.
    """
    logger = logging.getLogger(__name__)
    tazdata_census.columns = tazdata_census.columns.str.lower()
    # ---- Normalize county_fips and drop invalid ----


    # ---- Step 1: current totals ----
    # ensure totpop/totemp exist
    if 'totpop' not in tazdata_census:
        tazdata_census['totpop'] = tazdata_census['hhpop'] + tazdata_census.get('gqpop', 0)


    current = (
        tazdata_census.groupby('county_fips')[[
            'tothh','hhpop','empres','gqpop','totpop','totemp'
        ]].sum()
        .reset_index()
    )

    # ---- Step 2: initialize targets ----
    # Compute current totals per county and set up target columns
    targets = current.rename(columns={
        'tothh':  'tothh_target',
        'hhpop':  'hhpop_target',
        'empres': 'empres_target',
        'gqpop':  'gqpop_target',
        'totpop': 'totpop_target',
        'totemp': 'totemp_target'
    })
    # Merge original current values back so we keep both actual and target
    county_targets = targets.merge(
        current,
        on='county_fips'
    )
    # Now county_targets has columns: county_fips, *_target, tothh, hhpop, empres, gqpop, totpop, totemp
    # above: keeps both current and *_target columns

    # ---- Step 3: ACS adjustment ----
    county_targets = _apply_acs_adjustment(
        county_targets, census_client, acs_5year, acs_pums_1year
    )

    # ---- Step 4: institutional GQ adjustment ----
    county_targets = _add_institutional_gq(county_targets, dhc_gqpop)

    # ---- Step 5: compute diffs ----
    for metric in ['tothh','hhpop','gqpop','totpop','empres','totemp']:
        county_targets[f'{metric}_diff'] = (
            county_targets[f'{metric}_target'] - county_targets[metric]
        )

    # ---- Step 6: cast all numeric columns to int ----
    num_cols = county_targets.select_dtypes(include='number').columns
    county_targets[num_cols] = county_targets[num_cols].round().astype(int)


    logger.info("Final county_targets columns: %s", county_targets.columns.tolist())
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
    if 'taz1454' in taz_census.columns:
        taz_census['taz'] = (
            pd.to_numeric(taz_census['taz1454'], errors='coerce')
            .fillna(0).astype(int)
            .astype(str).str.zfill(4)
        )
    # Ensure taz_base.taz is zero‑padded string
    taz_base['taz'] = taz_base['taz'].astype(str).str.zfill(4)

    logger = logging.getLogger(__name__)

    # --- 1) Merge in all census fields, give them "_cns" suffix to avoid collisions ---
    merged = taz_base.merge(
        taz_census,
        on="taz",
        how="left",
        suffixes=("", "_cns")
    )

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