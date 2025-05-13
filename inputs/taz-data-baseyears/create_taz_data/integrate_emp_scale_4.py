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
from typing import List, Sequence
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
    tazdata_census['gqpop'] = tazdata_census['pop'] - tazdata_census['hhpop']
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
    year: int
) -> pd.DataFrame:
    import os
    import numpy as np
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)

    usps_per_thousand = CONSTANTS.get("USPS_PER_THOUSAND_JOBS", 1.83)

    # 1) Merge in census…
    merged = taz_base.merge(
        taz_census, on="taz", how="left", suffixes=("", "_cns")
    )
    for cns in [c for c in merged if c.endswith("_cns")]:
        base = cns[:-4]
        if base not in merged:
            merged[base] = np.nan
        merged[base] = merged[base].fillna(merged[cns]).astype(int)
    merged.drop(columns=[c for c in merged if c.endswith("_cns")], inplace=True)
    logger.info("Census fields merged & coalesced")

    # 2) Load LODES (wage & salary)
    path_lodes = os.path.expandvars(PATHS["wage_salary_csv"])
    df_lodes = pd.read_csv(path_lodes, dtype=str)
    logger.info(f"Loaded LODES rows: {len(df_lodes)}; columns: {df_lodes.columns.tolist()}")

    # --- NEW: make a proper 'taz' and group to one row per TAZ ---
    df_lodes["taz"] = df_lodes["TAZ1454"].astype(str)
    df_lodes["TOTEMP"] = (
        pd.to_numeric(df_lodes["TOTEMP"], errors="coerce")
          .fillna(0).astype(int)
    )
    df_lodes = (
        df_lodes
        .groupby("taz", as_index=False)["TOTEMP"]
        .sum()
    )
    logger.info(f"Collapsed LODES to {df_lodes['taz'].nunique()} unique TAZs")

    # inflate by USPS factor
    df_lodes["TOTEMP"] = (
        (df_lodes["TOTEMP"] * (1 + usps_per_thousand / 1_000))
        .round()
        .astype(int)
    )

    # 3) Load self-employment
    path_self = os.path.expandvars(PATHS["self_employment_csv"])
    df_self = pd.read_csv(path_self, dtype=str)
    df_self = df_self.rename(columns={"zone_id": "taz", "value": "emp_self"})
    df_self["emp_self"] = (
        pd.to_numeric(df_self["emp_self"], errors="coerce")
          .fillna(0).astype(int)
    )
    self_emp = df_self.groupby("taz", as_index=False)["emp_self"].sum()
    logger.info(f"Self-emp covers {self_emp['taz'].nunique()} unique TAZs, total jobs: {self_emp['emp_self'].sum():,}")

    # 4) Combine LODES + self-employment
    df_emp = (
        df_lodes
        .merge(self_emp, on="taz", how="outer")
        .fillna(0)
    )
    df_emp["EMPRES"] = df_emp["TOTEMP"]
    df_emp["TOTEMP"] = (df_emp["EMPRES"] + df_emp["emp_self"]).astype(int)
    logger.info(f"After merge: {df_emp['taz'].nunique()} TAZs; EMPRES sum = {df_emp['EMPRES'].sum():,}; TOTEMP sum = {df_emp['TOTEMP'].sum():,}")

    # write out if you like
    out_path = os.path.join(os.getcwd(), f"step10_employment_combined_{year}.csv")
    df_emp.to_csv(out_path, index=False)
    logger.info(f"Wrote combined employment data to {out_path}")

    # 5) Merge back into your TAZ base
    final = merged.merge(
        df_emp[["taz", "EMPRES", "TOTEMP"]],
        on="taz",
        how="left"
    ).fillna(0)
    final["EMPRES"] = final["EMPRES"].astype(int)
    final["TOTEMP"] = final["TOTEMP"].astype(int)
    logger.info(f"[SUM CHECK FINAL] EMPRES={final['EMPRES'].sum():,}; TOTEMP={final['TOTEMP'].sum():,}")

    return final

    logger.info("Employment integrated into TAZ base")
    return final
def integrate_lehd_targets(
    county_targets: pd.DataFrame,
    bay_area_counties: Sequence[str],
    emp_lodes_weight: float
) -> pd.DataFrame:
    """
    1) Load your LODES CSV, inflate by USPS factor from CONSTANTS, and
       collapse to county→county flows.
    2) Log Bay-Area totals (home, work, both).
    3) Sum Bay→Bay flows into EMPRES_LEHD_target by home county.
    4) Merge & blend into county_targets.
    """
    import os
    import logging
    import pandas as pd

    logger = logging.getLogger(__name__)

    # ----------------------------------------------------------------
    # A) Build lehd_cty internally
    # ----------------------------------------------------------------
    path_ws = os.path.expandvars(PATHS["wage_salary_csv"])
    lodes = pd.read_csv(path_ws, dtype=str)

    # Pull USPS factor (as a proportion) from CONSTANTS
    if "USPS_PER_THOUSAND_JOBS" not in CONSTANTS:
        raise KeyError("Missing USPS_PER_THOUSAND_JOBS in CONSTANTS")
    usps_factor = CONSTANTS["USPS_PER_THOUSAND_JOBS"] / 1_000

    # cast & inflate
    lodes["TOTEMP"] = (
        pd.to_numeric(lodes["TOTEMP"], errors="coerce")
          .fillna(0).astype(int)
    )
    lodes["TOTEMP"] = (lodes["TOTEMP"] * (1 + usps_factor)).round().astype(int)

    # collapse to county-to-county
    lehd_cty = (
        lodes
        .drop(columns=["w_state","h_state"], errors="ignore")
        .groupby(["w_county","h_county"], as_index=False)["TOTEMP"]
        .sum()
    )
    logger.info(f"Built lehd_cty ({len(lehd_cty)} rows) with USPS factor={usps_factor:.4f}")

    # ----------------------------------------------------------------
    # B) Bay-Area summaries
    # ----------------------------------------------------------------
    h_ba = lehd_cty.loc[lehd_cty["h_county"].isin(bay_area_counties), "TOTEMP"].sum()
    w_ba = lehd_cty.loc[lehd_cty["w_county"].isin(bay_area_counties), "TOTEMP"].sum()
    both_ba = lehd_cty.loc[
        lehd_cty["h_county"].isin(bay_area_counties) &
        lehd_cty["w_county"].isin(bay_area_counties),
        "TOTEMP"
    ].sum()

    logger.info(f"Workers with h_county in BayArea: {h_ba:,}")
    logger.info(f"Workers with w_county in BayArea: {w_ba:,}")
    logger.info(f"Workers with both h_county AND w_county in BayArea: {both_ba:,}")

    # ----------------------------------------------------------------
    # C) Build EMPRES_LEHD_target by home county
    # ----------------------------------------------------------------
    lehd_h = (
        lehd_cty[
            lehd_cty["w_county"].isin(bay_area_counties) &
            lehd_cty["h_county"].isin(bay_area_counties)
        ]
        .groupby("h_county", as_index=False)["TOTEMP"]
        .sum()
        .rename(columns={
            "h_county": "County_Name",
            "TOTEMP": "EMPRES_LEHD_target"
        })
    )
    logger.info(f"lehd_lodes_h_county:\n{lehd_h}")

    # ----------------------------------------------------------------
    # D) Merge & blend into county_targets
    # ----------------------------------------------------------------
    updated = (
        county_targets
        .merge(lehd_h, on="County_Name", how="left")
        .fillna({"EMPRES_LEHD_target": 0})
    )
    logger.info(f"Before blend (weight={emp_lodes_weight:.2f}):\n{updated}")

    updated["EMPRES_target"] = (
        emp_lodes_weight * updated["EMPRES_LEHD_target"]
        + (1 - emp_lodes_weight) * updated["EMPRES_target"]
    )
    updated = updated.drop(columns=["EMPRES_LEHD_target"])

    logger.info(f"After blend:\n{updated}")
    logger.info("Updated county_targets totals:\n" +
                updated.select_dtypes("number").sum().to_string())

    return updated



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
        county_targets: DataFrame with lowercase *_target columns for each metric.
        popsyn_acs_pums_5year: ACS PUMS 5-year vintage used for household-size and worker-consistency.

    Returns:
        DataFrame: Updated TAZ-level DataFrame with county targets applied.
    """
    import logging
    from common import update_tazdata_to_county_target, make_hhsizes_consistent_with_population

    logger = logging.getLogger(__name__)
    df = taz_df.copy()

    # 1) Scale employment (EMPRES) + occupations
    logger.info("Scaling EMPRES and occupations to county targets")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets,
        sum_var      = 'EMPRES',
        partial_vars = [
            'occ_manage','occ_prof_biz','occ_prof_comp','occ_svc_comm',
            'occ_prof_leg','occ_prof_edu','occ_svc_ent','occ_prof_heal',
            'occ_svc_heal','occ_svc_fire','occ_svc_law','occ_ret_eat',
            'occ_man_build','occ_svc_pers','occ_ret_sales','occ_svc_off',
            'occ_man_nat','occ_man_prod'
        ]
    )

    # 2) total population by age (sum_age)
    logger.info("Scaling age groups to county pop targets")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'totpop_target':'sum_age_target'}),
        sum_var      = 'sum_age',
        partial_vars = ['age0004','age0519','age2044','age4564','age65p']
    )

    # 3) population by ethnicity (sum_ethnicity)
    logger.info("Scaling ethnicity groups to county pop targets")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'totpop_target':'sum_ethnicity_target'}),
        sum_var      = 'sum_ethnicity',
        partial_vars = ['white_nonh','black_nonh','asian_nonh','other_nonh','hispanic']
    )

    # 4) housing units (sum_DU)
    logger.info("Scaling housing-unit counts to county DU targets")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'tothh_target':'sum_DU_target'}),
        sum_var      = 'sum_DU',
        partial_vars = ['sfdu','mfdu']
    )

    # 5) tenure (sum_tenure)
    logger.info("Scaling tenure counts to county tenure targets")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'tothh_target':'sum_tenure_target'}),
        sum_var      = 'sum_tenure',
        partial_vars = ['hh_own','hh_rent']
    )

    # 6) households with kids (sum_kids)
    logger.info("Scaling households-with-kids to county targets")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'tothh_target':'sum_kids_target'}),
        sum_var      = 'sum_kids',
        partial_vars = ['ownkidsyes','ownkidsno']
    )

    # 7) income quartiles (sum_income)
    logger.info("Scaling income quartiles to county targets")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'tothh_target':'sum_income_target'}),
        sum_var      = 'sum_income',
        partial_vars = ['hhinc000_010','hhinc010_015','hhinc015_020','hhinc020_025'] +
                       ['hhinc025_030','hhinc030_035','hhinc035_040','hhinc040_045'] +
                       ['hhinc045_050','hhinc050_060','hhinc060_075','hhinc075_100'] +
                       ['hhinc100_125','hhinc125_150','hhinc150_200','hhinc200p']
    )

    # 8) household size (sum_size)
    logger.info("Scaling household sizes to county targets")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'tothh_target':'sum_size_target'}),
        sum_var      = 'sum_size',
        partial_vars = ['hh_size_1','hh_size_2','hh_size_3','hh_size_4_plus']
    )
    df = make_hhsizes_consistent_with_population(
        source_df             = df,
        target_df             = county_targets,
        size_or_workers       = 'hh_size',
        popsyn_acs_pums_5year = popsyn_acs_pums_5year
    )

    # 9) household workers (sum_hhworkers)
    logger.info("Scaling household workers to county targets")
    df = update_tazdata_to_county_target(
        source_df    = df,
        target_df    = county_targets.rename(columns={'tothh_target':'sum_hhworkers_target'}),
        sum_var      = 'sum_hhworkers',
        partial_vars = ['hhwrks0','hhwrks1','hhwrks2','hhwrks3p']
    )
    df = make_hhsizes_consistent_with_population(
        source_df             = df,
        target_df             = county_targets,
        size_or_workers       = 'hh_wrks',
        popsyn_acs_pums_5year = popsyn_acs_pums_5year
    )

    # 10) Final adjustments
    df['TOTHH']  = df['sum_size']
    df['TOTPOP'] = df['hhpop'] + df['gqpop']

    logger.info("Finished apply_county_targets_to_taz")
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