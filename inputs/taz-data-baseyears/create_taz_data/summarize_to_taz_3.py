#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
summarize_to_taz.py

Module for summarizing ACS data to TAZ geographies.
Executes:
  STEP 8: Weighted summary of block-group ACS to TAZ
  STEP 9: Weighted summary of tract ACS to TAZ
"""
import os
import logging
import pandas as pd
from pathlib import Path
import yaml

# Load configuration
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)
PATHS = cfg['paths']

# ------------------------------
# STEP 8: Weighted summarize block-group ACS -> TAZ
# ------------------------------
def compute_block_weights(paths: dict) -> pd.DataFrame:
    """
    Load block-to-TAZ crosswalk and compute weights by blockgroup.
    Returns DataFrame with ['GEOID','blockgroup','TAZ1454','weight'].
    """
    cw_path = Path(paths['block2020_to_taz1454_csv'])
    df = pd.read_csv(cw_path, dtype={'blockgroup': str})
    df['block_POPULATION'] = pd.to_numeric(df['block_POPULATION'], errors='coerce').fillna(0)
    df['group_pop'] = df.groupby('blockgroup')['block_POPULATION'].transform('sum').replace({0:1})
    df['weight'] = df['block_POPULATION'] / df['group_pop']
    return df[['GEOID','blockgroup','TAZ1454','weight']]


def step8_summarize_to_taz(df_bg: pd.DataFrame, df_weights: pd.DataFrame) -> pd.DataFrame:
    """
    Apply blockgroup weights to block-group ACS data and aggregate to TAZ1454.
    df_bg: has columns ['blockgroup', ... ACS vars ...]
    df_weights: output of compute_block_weights

    Returns DataFrame with ['TAZ1454', ACS vars...]
    """
    acs_vars = [c for c in df_bg.columns if c != 'blockgroup']
    df = df_weights.merge(df_bg, on='blockgroup', how='left')
    for var in acs_vars:
        df[var] = df[var].fillna(0) * df['weight']
    return df.groupby('TAZ1454', as_index=False)[acs_vars].sum()

# ------------------------------
# STEP 9: Tract -> TAZ summarize
# ------------------------------
def compute_tract_weights(paths: dict) -> pd.DataFrame:
    """
    Load tract-to-TAZ crosswalk and compute normalized weights per tract.
    Returns DataFrame with ['tract','taz','weight'].
    """
    cw_path = Path(os.path.expandvars(paths['taz_crosswalk']))
    df = pd.read_csv(cw_path, dtype=str)
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    tract_col = next(col for col in df.columns if 'tract' in col)
    taz_col = next(col for col in df.columns if 'taz' in col)
    weight_col = next(col for col in df.columns if any(k in col for k in ('weight','pop_share','share')))
    df[weight_col] = pd.to_numeric(df[weight_col], errors='coerce').fillna(0)
    df['weight'] = df.groupby(tract_col)[weight_col].transform(lambda x: x / (x.sum() if x.sum() else 1))
    return df.rename(columns={tract_col: 'tract', taz_col: 'taz'})[['tract','taz','weight']]


def step9_summarize_tract_to_taz(df_acs_tr: pd.DataFrame, df_weights_tract: pd.DataFrame) -> pd.DataFrame:
    """
    Weight and aggregate tract-level ACS data to TAZ.
    df_acs_tr: has 'tract' + ACS tract vars
    df_weights_tract: output of compute_tract_weights

    Returns DataFrame with ['taz', ACS vars...]
    """
    df = df_weights_tract.merge(df_acs_tr, on='tract', how='left')
    aggs = [col for col in df.columns if col not in ['tract','taz','weight']]
    df[aggs] = df[aggs].apply(pd.to_numeric, errors='coerce').fillna(0)
    for var in aggs:
        df[var] = df[var] * df['weight']
    return df.groupby('taz', as_index=False)[aggs].sum()
""" 
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # For demonstration, users must supply df_bg and df_acs_tr + crosswalks
    # Example usage - assume hhinc, acs_tr provided
    weights_block = compute_block_weights(PATHS)
    taz_hhinc = step8_summarize_to_taz(hhinc, weights_block)
    weights_tract = compute_tract_weights(PATHS)
    taz_acs = step9_summarize_tract_to_taz(acs_tr, weights_tract)
    print("Module summarize_to_taz loaded") """