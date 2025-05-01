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

# Load configuration
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)
CONSTANTS = cfg['constants']
PATHS = cfg['paths']

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


