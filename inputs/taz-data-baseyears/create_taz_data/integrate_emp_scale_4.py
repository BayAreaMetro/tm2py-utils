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

# Load configuration
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)
CONSTANTS = cfg['constants']
PATHS = cfg['paths']

# ------------------------------
# LOAD CONFIG
# ------------------------------
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)
CONSTANTS = cfg['constants']
GEO       = cfg.get('geo_constants', {})
PATHS     = cfg['paths']

STATE_CODE           = GEO.get('STATE_CODE')
BAY_COUNTIES         = GEO.get('BAY_COUNTIES', [])
ACS_5YEAR_LATEST     = CONSTANTS.get('ACS_5YEAR_LATEST')
ACS_PUMS_1YEAR_LATEST= CONSTANTS.get('ACS_PUMS_1YEAR_LATEST')
EMPRES_LODES_WEIGHT  = CONSTANTS.get('EMPRES_LODES_WEIGHT', 0.0)

def summarize_census_to_taz(working_df, weights_block_df):
    """
    Summarize raw block-level working data to TAZ with:
      - TOTPOP : total population
      - TOTHH  : total households
      - HHPOP  : household population
      - gqpop  : group-quarters population

    Expects:
      working_df        : DataFrame with 'block_geoid', 'pop', 'hh', 'hhpop', and all 'gq_*' cols
      weights_block_df  : DataFrame with ['GEOID','TAZ1454','weight']

    Returns:
      DataFrame with ['taz','TOTPOP','TOTHH','HHPOP','gqpop']
    """
    # 1) Normalize the weights table
    wb = weights_block_df.rename(columns={
        'GEOID':   'block_geoid',
        'TAZ1454': 'taz'
    })

    # 2) Merge block→TAZ weights onto working
    tmp = working_df.merge(
        wb[['block_geoid','taz','weight']],
        on='block_geoid',
        how='left'
    )
    missing = tmp['weight'].isna().sum()
    if missing > 0:
        logging.warning(f"{missing} working rows missing a block→TAZ weight")

    # 3) Compute weighted block shares
    tmp['pop_taz']   = tmp['pop']    * tmp['weight']
    tmp['hh_taz']    = tmp['hh']     * tmp['weight']
    tmp['hhpop_taz'] = tmp['hhpop']  * tmp['weight']

    # 4) Collapse all gq_inst / gq_noninst into one gqpop, then weight it
    gq_cols = [c for c in tmp.columns if c.startswith('gq_inst') or c.startswith('gq_noninst')]
    tmp['gqpop']     = tmp[gq_cols].sum(axis=1)
    tmp['gqpop_taz'] = tmp['gqpop'] * tmp['weight']

    # 5) Aggregate to TAZ
    taz_census = tmp.groupby('taz', as_index=False).agg(
        TOTPOP = ('pop_taz',   'sum'),
        TOTHH  = ('hh_taz',    'sum'),
        HHPOP  = ('hhpop_taz', 'sum'),
        gqpop  = ('gqpop_taz', 'sum'),
    )

    return taz_census


def build_county_targets(
    tazdata_census: pd.DataFrame,
    lehd_lodes: pd.DataFrame,
    dhc_gqpop: pd.DataFrame,
    state_code: str,
    baycounties: List[str],
    acs_5year: int,
    acs_pums_1year: int,
    census_client: Census,
    empres_lodes_weight: float
) -> pd.DataFrame:
    """
    Build county-level targets for TAZ data based on census and LODES inputs.
    Returns a DataFrame with current totals, target totals, and diffs.
    """

    tazdata_census['County_Name'] = tazdata_census['county_fips'] \
            .map(GEO['BA_COUNTY_FIPS_CODES'])
    # 1) compute current county totals from TAZ data
    current = (
        tazdata_census
        .groupby('County_Name', as_index=False)
        .agg(
            TOTHH=('TOTHH', 'sum'),
            TOTPOP=('TOTPOP', 'sum'),
            GQPOP=('gqpop', 'sum'),
            HHPOP=('HHPOP', 'sum'),
            EMPRES=('EMPRES', 'sum'),
            TOTEMP=('TOTEMP', 'sum')
        )
    )
    county_targets = current.copy()
    # initialize target cols equal to current
    for col in ['TOTHH','TOTPOP','GQPOP','HHPOP','EMPRES','TOTEMP']:
        county_targets[f"{col}_target"] = county_targets[col]

    # 2) optionally scale to ACS 1-year if older
    if acs_5year < acs_pums_1year + 2:
        acs_vars: Dict[str,str] = {
            'TOTHH_target':'B19001_001',
            'TOTPOP_target':'B01001_001',
            'HHPOP_target':'B28005_001',
            'employed':'B23025_004',
            'armedforces':'B23025_006'
        }
        records = []
        for county in baycounties:
            res = census_client.acs.get(
                list(acs_vars.values()),
                geo={'for':'county','in':f'state:{state_code} county:{county}'},
                year=acs_pums_1year
            )[0]
            name = res['NAME'].replace(' County,','')
            row = {'County_Name':name}
            # extract ACS values
            row['TOTHH_target']  = res[f"{acs_vars['TOTHH_target']}E"]
            row['TOTPOP_target'] = res[f"{acs_vars['TOTPOP_target']}E"]
            row['HHPOP_target']  = res[f"{acs_vars['HHPOP_target']}E"]
            empl = res[f"{acs_vars['employed']}E"] + res[f"{acs_vars['armedforces']}E"]
            row['EMPRES_target'] = empl
            row['GQPOP_target']  = row['TOTPOP_target'] - row['HHPOP_target']
            records.append(row)
        acs_df = pd.DataFrame(records)
        # subtract institutionalized GQ from DHC
        acs_df = acs_df.merge(
            dhc_gqpop[['County_Name','gq_inst']],
            on='County_Name', how='left'
        )
        acs_df['TOTPOP_target'] -= acs_df['gq_inst']
        acs_df['GQPOP_target']   -= acs_df['gq_inst']
        # replace targets
        county_targets = (
            county_targets.drop(columns=[
                'TOTHH_target','TOTPOP_target','HHPOP_target','EMPRES_target','GQPOP_target'
            ])
            .merge(acs_df, on='County_Name')
        )

    # 3) blend in LODES employment
    lodes_sum = (
        lehd_lodes
        .query('w_county in @baycounties and h_county in @baycounties')
        .groupby('h_county', as_index=False)['TOTEMP']
        .sum()
        .rename(columns={'h_county':'County_Name','TOTEMP':'EMPRES_LEHD_target'})
    )
    county_targets = county_targets.merge(lodes_sum, on='County_Name', how='left')
    county_targets['EMPRES_target'] = (
        empres_lodes_weight * county_targets['EMPRES_LEHD_target'] +
        (1-empres_lodes_weight) * county_targets['EMPRES_target']
    )
    county_targets.drop(columns=['EMPRES_LEHD_target'], inplace=True)

    # 4) compute diffs
    for col in ['TOTHH','TOTPOP','GQPOP','HHPOP','EMPRES','TOTEMP']:
        county_targets[f"{col}_diff"] = (
            county_targets[f"{col}_target"] - county_targets[col]
        )
    return county_targets


# ------------------------------
# STEP 10: Integrate employment
# ------------------------------
def step10_integrate_employment(year):
    """
    Integrate LODES WAC employment and self‐employed counts at the TAZ level.
    
    Falls back to using TOTEMP if the LODES file is already at TAZ granularity,
    otherwise performs block-to-TAZ crosswalk.
    """
    # --- 1) Read LODES file ---
    lodes_path = os.path.expandvars(PATHS['lodes_employment_csv'])
    df_lodes   = pd.read_csv(lodes_path, dtype=str)
    cols = df_lodes.columns.tolist()

    # --- 2) If already TAZ‐level, shortcut ---
    if 'TAZ1454' in cols and 'TOTEMP' in cols:
        df_emp_lodes = (
            df_lodes
            .rename(columns={'TAZ1454':'taz','TOTEMP':'emp_lodes'})
            [['taz','emp_lodes']]
        )
        df_emp_lodes['emp_lodes'] = pd.to_numeric(
            df_emp_lodes['emp_lodes'], errors='coerce'
        ).fillna(0)
    else:
        # 2a) Block‐to‐TAZ crosswalk
        cw = pd.read_csv(os.path.expandvars(PATHS['block2020_to_taz1454_csv']), dtype=str)
        # detect block & taz columns
        block_col = next(c for c in cw.columns if 'block' in c.lower())
        taz_col   = next(c for c in cw.columns if 'taz'   in c.lower())
        cw = cw[[block_col, taz_col]].rename(columns={block_col:'block', taz_col:'taz'})

        # 2b) Find geocode & employment columns in raw WAC
        geo_col = next((c for c in cols if 'geocode' in c.lower()), None)
        if not geo_col:
            raise KeyError(f"No geocode column in LODES; found {cols!r}")
        emp_col = next((c for c in cols if c.upper()=='C000'), None)
        if emp_col is None:
            emp_col = next((c for c in cols if c.lower().startswith('c')), None)
        if emp_col is None:
            raise KeyError(f"No employment column in LODES; found {cols!r}")

        # 2c) Trim to blocks, coerce, merge, sum to TAZ
        df_lodes['block']      = df_lodes[geo_col].str[:12]
        df_lodes[emp_col]      = pd.to_numeric(df_lodes[emp_col], errors='coerce').fillna(0)
        df_lodes               = df_lodes.merge(cw, on='block', how='left')
        df_emp_lodes = (
            df_lodes
            .groupby('taz', as_index=False)[emp_col]
            .sum()
            .rename(columns={emp_col:'emp_lodes'})
        )

    # --- 3) Read self‐employed file ---
    se = pd.read_csv(os.path.expandvars(PATHS['self_employed_csv']), dtype=str)
    se_cols = se.columns.tolist()
    # detect TAZ column in self‐emp file
    se_taz = next(
        (c for c in se_cols if 'taz' in c.lower() or 'zone' in c.lower()),
        None
    )
    if not se_taz:
        raise KeyError(f"No TAZ/zone column in self‐emp; found {se_cols!r}")
    se_val = next(c for c in se_cols if c != se_taz)

    df_se = (
        se.rename(columns={se_taz:'taz', se_val:'emp_self'})
          .assign(emp_self=lambda df: pd.to_numeric(df['emp_self'], errors='coerce').fillna(0))
          [['taz','emp_self']]
    )

    # --- 4) Merge the two employment sources ---
    df_emp = df_emp_lodes.merge(df_se, on='taz', how='outer').fillna(0)
    df_emp['taz'] = df_emp['taz'].astype(str)

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


