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
    """
    1) Merge taz_base + taz_census, coalesce "_cns" suffix cols.
    2) Rename EMPRES/TOTEMP to EMPRES_CNS/TOTEMP_CNS if present.
    3) Load & collapse LODES WAC, ensuring int taz.
    4) Load & sum self-employment, int taz.
    5) Build df_emp seeded on all_zones (int), compute LDES cols.
    6) Merge side-by-side.
    """
    import os
    import numpy as np
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)

    # 0) Ensure taz_base.taz is int
    taz_base["taz"] = taz_base["taz"].astype(int)

    # 1) Census merge & coalesce
    merged = taz_base.merge(
        taz_census.assign(taz=lambda df: df["taz"].astype(int)),
        on="taz", how="left", suffixes=("", "_cns")
    )
    for cns in [c for c in merged if c.endswith("_cns")]:
        base = cns[:-4]
        if base not in merged:
            merged[base] = np.nan
        merged[base] = merged[base].fillna(merged[cns]).astype(int)
    merged.drop(columns=[c for c in merged if c.endswith("_cns")], inplace=True)

    # 2) Preserve census EMPRES/TOTEMP
    if "EMPRES" in merged: merged.rename(columns={"EMPRES":"EMPRES_CNS"}, inplace=True)
    if "TOTEMP" in merged: merged.rename(columns={"TOTEMP":"TOTEMP_CNS"}, inplace=True)
    logger.info("Columns now: " + ", ".join(merged.columns))

    # 3) Load & collapse LODES
    path_lodes = os.path.expandvars(PATHS["wage_salary_csv"])
    lodes = pd.read_csv(path_lodes, dtype=str)
    # cast
    lodes["taz"] = lodes["TAZ1454"].astype(int)
    lodes["TOTEMP"] = pd.to_numeric(lodes["TOTEMP"], errors="coerce").fillna(0).astype(int)
    df_lodes = lodes.groupby("taz", as_index=False)["TOTEMP"].sum()
    # inflate
    usps_factor = CONSTANTS["USPS_PER_THOUSAND_JOBS"]/1000
    df_lodes["TOTEMP"] = (df_lodes["TOTEMP"] * (1+usps_factor)).round().astype(int)
    logger.info(f"Collapsed LODES to {len(df_lodes)} zones")

    # 4) Load & sum self-employment
    path_self = os.path.expandvars(PATHS["self_employment_csv"])
    df_self = pd.read_csv(path_self, dtype=str)
    df_self["taz"] = df_self["zone_id"].astype(int)
    df_self["emp_self"] = pd.to_numeric(df_self["value"], errors="coerce").fillna(0).astype(int)
    self_emp = df_self.groupby("taz", as_index=False)["emp_self"].sum()
    logger.info(f"Self-emp covers {len(self_emp)} zones")

    # 5) Seed on all zones, then join
    all_zones = merged[["taz"]].drop_duplicates()
    df_emp = (
        all_zones
        .merge(df_lodes,  on="taz", how="left")
        .merge(self_emp,  on="taz", how="left")
        .fillna(0)
    )
    df_emp["EMPRES_LDES"] = df_emp["TOTEMP"].astype(int)
    df_emp["TOTEMP_LDES"] = (df_emp["EMPRES_LDES"] + df_emp["emp_self"].astype(int)).astype(int)
    logger.info(f"Built df_emp for {len(df_emp)} zones; SUM EMPRES_LDES={df_emp['EMPRES_LDES'].sum():,}")

    # 6) Merge into final
    final = merged.merge(
        df_emp[["taz","EMPRES_LDES","TOTEMP_LDES"]],
        on="taz", how="left"
    ).fillna(0)
    for col in ("EMPRES_CNS","TOTEMP_CNS","EMPRES_LDES","TOTEMP_LDES"):
        if col in final: final[col] = final[col].astype(int)

    logger.info("step10 complete")
    return final

    logger.info("Employment integrated into TAZ base")
    return final
def integrate_lehd_targets(
    county_targets: pd.DataFrame,
    emp_lodes_weight: float,
) -> pd.DataFrame:
    """
    1) Load LODES OD CSV, inflate by USPS factor, collapse to county→county flows.
    2) Map Bay-Area FIPS→County_Name from GEO.
    3) Use county names in the LODES data for filtering and grouping.
    4) Build EMPRES_LEHD_target and blend into county_targets.
    5) Pivot self_employment CSV (by TAZ) from industry/value to TOTEMP_self per TAZ,
       map to county and summarize, then add to county TOTEMP.
    """
    logger = logging.getLogger(__name__)

    # A) Bay-Area FIPS→Name mapping
    ba_map = GEO.get("BAY_AREA_COUNTY_FIPS")
    if ba_map is None:
        raise KeyError("Missing BAY_AREA_COUNTY_FIPS in GEO")
    # fips_name_df: county_fips <-> County_Name
    fips_name_df = (
        pd.DataFrame.from_dict(ba_map, orient='index', columns=['County_Name'])
          .reset_index()
          .rename(columns={'index':'county_fips'})
    )
    bay_area_names = fips_name_df['County_Name'].tolist()

    # Ensure county_targets has county_fips & County_Name
    if 'County_Name' not in county_targets.columns:
        if 'county_fips' in county_targets.columns:
            county_targets = county_targets.merge(
                fips_name_df, on='county_fips', how='left'
            )
        else:
            raise KeyError("county_targets missing both 'county_fips' and 'County_Name'")

    # B) Load & inflate LODES data
    lodes = pd.read_csv(
        os.path.expandvars(PATHS['lehd_lodes_csv']), dtype=str
    )
    usps_factor = CONSTANTS['USPS_PER_THOUSAND_JOBS'] / 1_000
    lodes['TOTEMP'] = (
        pd.to_numeric(lodes.get('Total_Workers', 0), errors='coerce')
          .fillna(0).astype(int)
    )
    lodes['TOTEMP'] = (lodes['TOTEMP'] * (1 + usps_factor)).round().astype(int)
    raw_cty = (
        lodes
        .drop(columns=['w_state','h_state'], errors='ignore')
        .groupby(['w_county','h_county'], as_index=False)['TOTEMP']
        .sum()
    )
    logger.info(f"Built raw county flows ({len(raw_cty)} rows) @ USPS factor {usps_factor:.4f}")

    # C) Build EMPRES_LEHD_target by county name
    lehd_h = (
        raw_cty[
            raw_cty['w_county'].isin(bay_area_names) &
            raw_cty['h_county'].isin(bay_area_names)
        ]
        .groupby('h_county', as_index=False)['TOTEMP']
        .sum()
        .rename(columns={
            'h_county':'County_Name',
            'TOTEMP':'EMPRES_LEHD_target'
        })
    )
    logger.info(f"LEHD county summary:\n{lehd_h}")

    # D) Merge & blend into county_targets
    updated = county_targets.merge(
        lehd_h[['County_Name','EMPRES_LEHD_target']],
        on='County_Name', how='left'
    ).fillna({'EMPRES_LEHD_target':0})
    updated['EMPRES_target'] = (
        emp_lodes_weight * updated['EMPRES_LEHD_target'] +
        (1 - emp_lodes_weight) * updated['empres_target']
    )
    updated.drop(columns=['EMPRES_LEHD_target'], inplace=True)

    # E) Process self-employed by TAZ and roll up to county
    self_emp = pd.read_csv(os.path.expandvars(PATHS['self_employment_csv']), dtype=str)
    # Ensure values numeric
    self_emp['value'] = pd.to_numeric(self_emp['value'], errors='coerce').fillna(0)
    # Pivot to wide form: one industry per column
    wide = (
        self_emp
        .pivot_table(index='zone_id', columns='industry', values='value', aggfunc='sum', fill_value=0)
        .reset_index()
        .rename(columns={'zone_id':'ZONE'})
    )
    # Sum across industries to get TOTEMP_self per TAZ
    industry_cols = [c for c in wide.columns if c != 'ZONE']
    wide['TOTEMP_self'] = wide[industry_cols].sum(axis=1)

    # Map TAZ ZONE to county via taz_sd_county_csv
    taz_map = pd.read_csv(
        os.path.expandvars(PATHS['taz_sd_county_csv']),
        dtype={'ZONE':str,'COUNTY_NAME':str}
    )
    # Join and aggregate to county level
    self_by_cty = (
        wide[['ZONE','TOTEMP_self']]
        .merge(taz_map[['ZONE','COUNTY_NAME']], on='ZONE', how='left')
        .groupby('COUNTY_NAME', as_index=False)['TOTEMP_self'].sum()
        .rename(columns={'COUNTY_NAME':'County_Name'})
    )
    # Add to county-level TOTEMP if present
    if 'TOTEMP' in updated.columns:
        updated = updated.merge(self_by_cty, on='County_Name', how='left')
        updated['TOTEMP_self'] = updated['TOTEMP_self'].fillna(0)
        updated['TOTEMP'] = updated['TOTEMP'] + updated['TOTEMP_self']
        updated.drop(columns=['TOTEMP_self'], inplace=True)

    totals = updated.select_dtypes(include='number').sum()
    logger.info("Final county_targets summary:")
    logger.info(f"Households: target {totals['tothh_target']:.0f}, actual {totals['tothh']:.0f}, diff {totals['tothh_diff']:.0f}")
    logger.info(f"Household population: target {totals['hhpop_target']:.0f}, actual {totals['hhpop']:.0f}, diff {totals['hhpop_diff']:.0f}")
    logger.info(f"Group quarters population: {totals['gqpop']:.0f}")
    logger.info(f"Total population: target {totals['totpop_target']:.0f}, actual {totals['totpop']:.0f}, diff {totals['totpop_diff']:.0f}")
    logger.info(f"LODES target blended: {totals['empres_target']:.0f}, actual {totals['empres']:.0f}, diff {totals['empres_diff']:.0f}")
    return updated
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


def add_taz_summaries(taz_df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds summary columns to a TAZ-level DataFrame:
      - sum_age: total population aged 0–4, 5–19, 20–44, 45–64, 65+
      - other_nonh, hispanic, sum_ethnicity: derives ethnic group totals
      - sum_DU: total dwelling units
      - sum_tenure: total households by tenure
      - hh_kids_yes, hh_kids_no, sum_kids: households with/without kids
      - sum_income: total households by income quartile
      - sum_size: total households by size category
      - sum_hhworkers: total households by number of workers
    """
    df = taz_df.copy()

    # 1) Age groups
    age_cols = ['age0004', 'age0519', 'age2044', 'age4564', 'age65p']
    df['sum_age'] = df[age_cols].sum(axis=1).astype(int)

    # 2) Ethnicity groups
    df['other_nonh'] = (
        df['total_nonh']
        - df[['white_nonh', 'black_nonh', 'asian_nonh']].sum(axis=1)
    ).astype(int)
    df['hispanic'] = df['total_hisp'].astype(int)
    eth_cols = ['white_nonh', 'black_nonh', 'asian_nonh', 'other_nonh', 'hispanic']
    df['sum_ethnicity'] = df[eth_cols].sum(axis=1).astype(int)

    # 3) Total dwelling units
    df['sum_DU'] = df[['sfdu', 'mfdu']].sum(axis=1).astype(int)

    # 4) Tenure
    df['sum_tenure'] = df[['hh_own', 'hh_rent']].sum(axis=1).astype(int)

    # 5) Households with kids
    df['hh_kids_yes'] = (df['ownkidsyes'] + df['rentkidsyes']).astype(int)
    df['hh_kids_no']  = (df['ownkidsno']  + df['rentkidsno']).astype(int)
    df['sum_kids']    = (df['hh_kids_yes'] + df['hh_kids_no']).astype(int)

    # 6) Income quartiles
    incq = ['HHINCQ1', 'HHINCQ2', 'HHINCQ3', 'HHINCQ4']
    df['sum_income'] = df[incq].sum(axis=1).astype(int)

    # 7) Household size
    size_cols = ['hh_size_1', 'hh_size_2', 'hh_size_3', 'hh_size_4_plus']
    df['sum_size'] = df[size_cols].sum(axis=1).astype(int)

    # 8) Household workers
    wrk_cols = ['hhwrks0', 'hhwrks1', 'hhwrks2', 'hhwrks3p']
    df['sum_hhworkers'] = df[wrk_cols].sum(axis=1).astype(int)

    return df

def apply_county_targets_to_taz(
    taz_df: pd.DataFrame,
    county_targets: pd.DataFrame,
    popsyn_acs_pums_5year: int
) -> pd.DataFrame:
    logger = logging.getLogger(__name__)
    logger.info("Starting apply_county_targets_to_taz()")

    # 0) Sanity-check and clean inputs
    logger.debug("Original taz_df shape: %s", taz_df.shape)
    taz_df = taz_df.loc[:, ~taz_df.columns.duplicated()]
    logger.debug("Dropped duplicate columns, new taz_df shape: %s", taz_df.shape)
    if taz_df['TAZ1454'].duplicated().any():
        dup = taz_df.loc[taz_df['TAZ1454'].duplicated(), 'TAZ1454'].unique()
        logger.warning("Found duplicate TAZ1454 IDs: %s (will collapse)", dup)

    logger.debug("Original county_targets shape: %s", county_targets.shape)
    if county_targets['County_Name'].duplicated().any():
        dup_ct = county_targets.loc[county_targets['County_Name'].duplicated(), 'County_Name'].unique()
        logger.warning("Dropping duplicate County_Name rows: %s", dup_ct)
        county_targets = county_targets.drop_duplicates(subset='County_Name', keep='first')
    logger.debug("Cleaned county_targets shape: %s", county_targets.shape)

    # 1) Uppercase key columns in TAZ
    lower_to_upper = {
        'tothh':  'TOTHH',
        'hhpop':  'HHPOP',
        'gqpop':  'GQPOP',
        'totpop': 'TOTPOP',
        'empres': 'EMPRES',
        'totemp': 'TOTEMP',
    }
    taz = taz_df.rename(columns=lower_to_upper)
    logger.debug("Renamed TAZ columns: %s", list(lower_to_upper.values()))

    # 2) Collapse across all rows by TAZ1454
    before = len(taz)
    agg_dict = {}
    for col in taz.columns:
        if col == 'TAZ1454':
            continue
        if col == 'County_Name':
            agg_dict[col] = 'first'
        elif pd.api.types.is_numeric_dtype(taz[col]):
            agg_dict[col] = 'sum'
        else:
            agg_dict[col] = 'first'
    taz = taz.groupby('TAZ1454', as_index=False).agg(agg_dict)
    after = len(taz)
    logger.info("Collapsed from %d rows to %d unique TAZ1454 rows", before, after)

    # 3) Prepare county_targets (keep County_Name column)
    rename_tg = {
        f"{lc}_target": f"{uc}_target"
        for lc, uc in lower_to_upper.items()
    }
    ct = county_targets.rename(columns=rename_tg)
    logger.debug("Renamed target columns: %s", list(rename_tg.values()))
    target_cols = [c for c in ct.columns if c.endswith('_target')]
    ct = ct[['County_Name'] + target_cols]
    logger.debug("Final county_targets columns: %s", ct.columns.tolist())

    # 4) Build derived sum_*_target fields
    ct['sum_age_target']       = ct['TOTPOP_target']
    ct['sum_ethnicity_target'] = ct['TOTPOP_target']
    ct['sum_DU_target']        = ct['TOTHH_target']
    ct['sum_tenure_target']    = ct['TOTHH_target']
    ct['sum_kids_target']      = ct['TOTHH_target']
    ct['sum_income_target']    = ct['TOTHH_target']
    ct['sum_size_target']      = ct['TOTHH_target']
    ct['sum_hhworkers_target'] = ct['TOTHH_target']
    logger.debug("Built derived sum_*_target fields")

    # 5) Scaling steps
    steps = [
        ('EMPRES & occupations', 'EMPRES', [
            'occ_manage','occ_prof_biz','occ_prof_comp','occ_svc_comm',
            'occ_prof_leg','occ_prof_edu','occ_svc_ent','occ_prof_heal',
            'occ_svc_heal','occ_svc_fire','occ_svc_law','occ_ret_eat',
            'occ_man_build','occ_svc_pers','occ_ret_sales','occ_svc_off',
            'occ_man_nat','occ_man_prod'
        ]),
        ('age groups',       'sum_age',       ['age0004','age0519','age2044','age4564','age65p']),
        ('ethnicity groups', 'sum_ethnicity', ['white_nonh','black_nonh','asian_nonh','other_nonh','hispanic']),
        ('dwelling units',   'sum_DU',        ['sfdu','mfdu']),
        ('tenure',           'sum_tenure',    ['hh_own','hh_rent']),
        ('households with kids','sum_kids',   ['hh_kids_yes','hh_kids_no']),
        ('income quartiles', 'sum_income',    ['HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4']),
        ('household size',   'sum_size',      ['hh_size_1','hh_size_2','hh_size_3','hh_size_4_plus']),
        ('household workers','sum_hhworkers', ['hhwrks0','hhwrks1','hhwrks2','hhwrks3p'])
    ]

    for name, sum_var, parts in steps:
        logger.info("Scaling %s …", name)
        taz = update_tazdata_to_county_target(
            source_df    = taz,
            target_df    = ct,
            sum_var      = sum_var,
            partial_vars = parts
        )
        logger.debug(
            "After %s scaling — head of %s and partials:\n%s",
            name, sum_var, taz[['TAZ1454', sum_var] + parts].head(3)
        )

        if sum_var in ('sum_size', 'sum_hhworkers'):
            kind = 'hh_size' if sum_var == 'sum_size' else 'hh_wrks'
            taz = make_hhsizes_consistent_with_population(
                source_df             = taz,
                target_df             = ct,
                size_or_workers       = kind,
                popsyn_ACS_PUMS_5year = popsyn_acs_pums_5year
            )
            logger.debug("Applied consistency for %s", kind)

    # 6) Final housekeeping
    taz['TOTHH']  = taz['sum_size']
    taz['TOTPOP'] = taz['HHPOP'] + taz['GQPOP']
    logger.info("Finished apply_county_targets_to_taz(); final shape: %s", taz.shape)

    return taz





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