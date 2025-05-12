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

def summarize_census_to_taz(
    working_df: pd.DataFrame,
    weights_block_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Summarize block-level census attributes to TAZ by applying
    population-based block→TAZ weights, then aggregating up to TAZ & county.
    Logs raw vs. aggregated totals and issues warnings if any key total < 1M.
    """
    import numpy as np
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        "Starting summarize_census_to_taz: %d blocks, %d weight rows",
        len(working_df), len(weights_block_df)
    )

    # --- 0) Diagnostic: raw sums in working_df
    raw_totals = {
        'tothh': working_df.get('tothh', pd.Series(0)).sum(),
        'hhpop': working_df.get('hhpop', pd.Series(0)).sum(),
        'employed': working_df.get('employed', pd.Series(0)).sum(),
        'armedforces': working_df.get('armedforces', pd.Series(0)).sum(),
    }
    logger.info("Raw working_df sums: %s", raw_totals)

    # --- 1) Standardize GEOIDs and merge weight
    df = working_df.copy()
    df['block_geoid'] = df['block_geoid'].astype(str).str.zfill(15)

    w = weights_block_df.copy()
    w['GEOID'] = w['GEOID'].astype(str).str.zfill(15)
    w = w.rename(columns={'GEOID': 'block_geoid'})

    df = df.merge(
        w[['block_geoid','TAZ1454','weight']],
        on='block_geoid', how='left', validate='many_to_one'
    )
    missing = df['weight'].isna().sum()
    logger.info("After merge: %d rows, %d missing weight", len(df), missing)
    if missing:
        logger.warning("Some blocks have no TAZ weight – check your crosswalk")

    # --- 2) Check weight sums by TAZ
    ws = df.groupby('TAZ1454')['weight'].sum()
    desc = ws.describe().to_dict()
    logger.info("TAZ weight sums: min=%0.3f mean=%0.3f max=%0.3f",
                desc['min'], desc['mean'], desc['max'])

    # --- 3) Derive county_fips
    df['county_fips'] = df['block_geoid'].str[:5]

    # --- 4) Identify numeric block-level attrs
    numeric = [c for c in df.columns if np.issubdtype(df[c].dtype, np.number)]
    skip = {'weight','TAZ1454','share_bg','tract_share'}
    attr_cols = [c for c in numeric if c not in skip]
    logger.debug("Will weight these columns: %s", attr_cols)

    # --- 5) Aggregate to TAZ & county
    # Here, DO NOT apply the weight again
    taz = df.groupby(['TAZ1454','county_fips'], as_index=False)[attr_cols].sum()
    logger.info("Aggregated to %d TAZ‐county rows", len(taz))

    # --- 6) Add string TAZ key
    taz['taz'] = taz['TAZ1454'].astype(int).astype(str).str.zfill(4)

    # --- 7) Derive R-style totals
    taz['totpop'] = taz['hhpop'] + taz.get('gqpop', 0)
    taz['empres'] = taz.get('employed', 0)
    taz['totemp'] = taz['empres'] + taz.get('armedforces', 0)

    # --- 8) Diagnostic: compare raw vs. aggregated sums
    agg_totals = {
        'tothh': taz.get('tothh', pd.Series(0)).sum(),
        'hhpop': taz['hhpop'].sum(),
        'pop': taz['totpop'].sum(),
        'emp': taz['totemp'].sum()
    }
    logger.info("TAZ aggregated sums: %s", agg_totals)

    # --- 9) Warnings if anything < 1M
    if agg_totals['tothh'] < 1_000_000:
        logger.warning("Total households (%.0f) < 1,000,000", agg_totals['tothh'])
    if agg_totals['pop'] < 1_000_000:
        logger.warning("Total population (%.0f) < 1,000,000", agg_totals['pop'])
    if agg_totals['emp'] < 1_000_000:
        logger.warning("Total employment (%.0f) < 1,000,000", agg_totals['emp'])

    logger.info(
        "Finished summarize_census_to_taz: columns = %s",
        taz.columns.tolist()
    )
    return taz






def _apply_acs_adjustment(county_targets: pd.DataFrame,
                          census_client,
                          acs_year: int,
                          pums_year: int) -> pd.DataFrame:
    import logging, time
    logger = logging.getLogger(__name__)
    logger.info(f"applying acs1 adjustment for pums_year={pums_year}")

    # use canonical acs1 variable codes (all lowercase keys)
    var_map = {
        'tothh_target':  'B11016_001E',
        'totpop_target': 'B01003_001E',
        'hhpop_target':  'B28005_001E',
        'employed':      'B23025_004E',
        'armedforces':   'B23025_005E'
    }

    # ensure county_fips are strings and zero-padded 5-digit
    county_targets['county_fips'] = (
        county_targets['county_fips']
        .astype(str)
        .str.extract(r"(\d{1,5})$")[0]
        .astype(int)
        .astype(str)
        .str.zfill(5)
    )

    records = []
    for cnt in county_targets['county_fips']:
        logger.info(f"about to call acs1 for county_fips={cnt}")
        county_arg = cnt[-3:]
        logger.info(f"fetching acs1 for county {county_arg}")

        recs = []
        for attempt in range(1, 4):
            try:
                logger.debug(
                    f"acs1 call: vars={list(var_map.values())}, state={GEO['STATE_CODE']},"
                    f" county={county_arg}, year={pums_year}"
                )
                recs = census_client.acs1.state_county(
                    list(var_map.values()),
                    GEO['STATE_CODE'],
                    county_arg,
                    year=pums_year
                )
                logger.debug(f"acs1 response for {cnt} (arg {county_arg}): {recs}")
                break
            except Exception as e:
                logger.error(f"acs1 failure for {county_arg} attempt {attempt}: {e}")
                time.sleep(2 ** (attempt - 1))

        if not recs:
            logger.error(f"no acs1 data for county {county_arg} after retries, skipping adjustment")
            continue

        # normalize header/value or dict format
        if isinstance(recs[0], list):
            header, values = recs[0], (recs[1] if len(recs) > 1 else [])
            recs_to_process = [dict(zip(header, values))]
        else:
            recs_to_process = recs

        for r in recs_to_process:
            row = {'county_fips': cnt}
            for out_col, code in var_map.items():
                try:
                    row[out_col] = int(float(r.get(code, 0)))
                except (ValueError, TypeError):
                    logger.warning(f"invalid value for {code} in county {cnt}: {r.get(code)}; default 0")
                    row[out_col] = 0
            records.append(row)

    logger.info(f"total acs records: {len(records)}")
    df_acs = pd.DataFrame(records)
    if df_acs.empty:
        logger.warning("no acs1 records collected; returning original county_targets")
        return county_targets

    # debug: inspect acs dataframe before merging
    logger.info("acs1 dataframe columns: %s", df_acs.columns.tolist())
    logger.info("acs1 dataframe sample:\n%s", df_acs.head().to_string(index=False))

    # compute 'empres' as sum of employed + armedforces, then drop raw columns
    if 'employed' in df_acs.columns and 'armedforces' in df_acs.columns:
        df_acs['empres'] = df_acs['employed'] + df_acs['armedforces']
        df_acs.drop(columns=['employed','armedforces'], inplace=True)
        logger.info("computed 'empres' and dropped 'employed','armedforces'; columns now: %s", df_acs.columns.tolist())

    # merge acs targets
    merged = county_targets.merge(
        df_acs,
        on='county_fips',
        how='left',
        suffixes=('', '_acs')
    )

    merged = merged.loc[:, ~merged.columns.duplicated()]
    logger.info("deduped merged columns: %s", merged.columns.tolist())

    # overwrite with acs where available
    for col in [c for c in df_acs.columns if c != 'county_fips']:
        acs_col = f"{col}_acs"
        if acs_col in merged.columns:
            merged[col] = merged[acs_col].fillna(merged[col])
            merged.drop(columns=[acs_col], inplace=True)
        else:
            logger.debug(f"no acs override column {acs_col} in merged; skipping")

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

    # ---- Normalize county_fips and drop invalid ----


    # ---- Step 1: current totals ----
    # ensure totpop/totemp exist
    if 'totpop' not in tazdata_census.columns:
        tazdata_census['totpop'] = (
            tazdata_census['hhpop']
            + tazdata_census.get('gqpop', 0)
        )
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
    county_targets: pd.DataFrame
) -> pd.DataFrame:
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting integrate_employment")

    # --- 1) Ensure keys are the same format
    taz_base = taz_base.copy()
    taz_census = taz_census.copy()
    county_targets = county_targets.copy()

    # zero-pad county_fips and taz
    taz_base['county_fips'] = taz_base['county_fips'].astype(str).str.zfill(5)
    taz_base['taz']         = taz_base['taz'].astype(str).str.zfill(4)
    taz_census['county_fips'] = taz_census['county_fips'].astype(str).str.zfill(5)
    taz_census['taz']         = taz_census['taz'].astype(str).str.zfill(4)
    county_targets['county_fips'] = county_targets['county_fips'].astype(str).str.zfill(5)

    # --- 2) Merge in TAZ‐level census employment
    merged = taz_base.merge(
        taz_census[['taz','empres','totemp']],
        on='taz', how='left', indicator='merge_census_emp'
    )
    logger.info("Census employment merge counts: %s",
                merged['merge_census_emp'].value_counts().to_dict())
    missing_taz = merged.loc[merged['empres'].isna(), 'taz'].unique().tolist()
    if missing_taz:
        logger.warning("These TAZs are missing census employment: %s", missing_taz)

    # rename for clarity
    merged = merged.rename(columns={
        'empres': 'empres_census',
        'totemp': 'totemp_census'
    })

    # fill zeros so we can scale
    merged['empres_census'] = merged['empres_census'].fillna(0)
    merged['totemp_census'] = merged['totemp_census'].fillna(0)

    # --- 3) Merge in county‐level employment targets
    merged_ct = merged.merge(
        county_targets[['county_fips','EMPRES_target','TOTEMP_target']],
        on='county_fips', how='left', indicator='merge_county_emp'
    )
    logger.info("County employment merge counts: %s",
                merged_ct['merge_county_emp'].value_counts().to_dict())
    missing_ct = merged_ct.loc[merged_ct['EMPRES_target'].isna(), 'county_fips'].unique().tolist()
    if missing_ct:
        logger.warning("These counties are missing employment targets: %s", missing_ct)

    # fill zeros to avoid NaNs in scaling
    merged_ct['EMPRES_target'] = merged_ct['EMPRES_target'].fillna(0)
    merged_ct['TOTEMP_target'] = merged_ct['TOTEMP_target'].fillna(0)

    # --- 4) Compute scaling factors
    # Avoid division by zero
    merged_ct['empres_scale'] = merged_ct.apply(
        lambda row: (row['EMPRES_target'] / row['empres_census'])
        if row['empres_census'] > 0 else 1.0,
        axis=1
    )
    merged_ct['totemp_scale'] = merged_ct.apply(
        lambda row: (row['TOTEMP_target'] / row['totemp_census'])
        if row['totemp_census'] > 0 else 1.0,
        axis=1
    )

    # --- 5) Apply scaling to all employment‐related columns
    # here you could scale individual employment categories if you have them
    merged_ct['empres'] = merged_ct['empres_census'] * merged_ct['empres_scale']
    merged_ct['totemp'] = merged_ct['totemp_census'] * merged_ct['totemp_scale']

    logger.info("Finished integrate_employment")
    return merged_ct


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