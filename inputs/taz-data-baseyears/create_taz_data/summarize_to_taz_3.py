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

GEO  = cfg['geo_constants']

# ------------------------------
# STEP 8: Weighted summarize block-group ACS -> TAZ
# ------------------------------
def compute_block_weights(paths):
    cw_path = Path(paths['block2020_to_taz1454_csv'])
    df = pd.read_csv(cw_path, dtype={'blockgroup': str})

    # ensure numeric
    df['block_POP'] = pd.to_numeric(df['block_POPULATION'], errors='coerce').fillna(0)

    # 1) (Optional) block‐group share (for allocating BG vars to blocks)
    df['BG_pop']     = df.groupby('blockgroup')['block_POP'].transform('sum').replace({0:1})
    df['share_bg']   = df['block_POP'] / df['BG_pop']

    # 2) TAZ‐level share (so sums to 1 per TAZ)
    df['TAZ_pop']    = df.groupby('TAZ1454')['block_POP'].transform('sum').replace({0:1})
    df['weight']  = df['block_POP'] / df['TAZ_pop']

    return df[['GEOID','blockgroup','TAZ1454','share_bg','weight']]


def step8_summarize_to_taz(hhinc: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate HHINCQ1–4 from block-groups to TAZ using share_bg weights.
    Assumes weights DataFrame contains 'share_bg' column.
    Returns DataFrame indexed by TAZ1454 with columns HHINCQ1–HHINCQ4.
    """
    # Validate inputs
    for col in ['blockgroup','HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4']:
        if col not in hhinc.columns:
            raise KeyError(f"step8: missing '{col}' in hhinc DataFrame")
    for col in ['blockgroup','TAZ1454','share_bg']:
        if col not in weights.columns:
            raise KeyError(f"step8: missing '{col}' in weights DataFrame")

    # Merge on blockgroup, retaining all hhinc rows
    merged = hhinc.merge(
        weights[['blockgroup','TAZ1454','share_bg']],
        on='blockgroup', how='left', indicator=True
    )
    logging.info(f"step8: merged hhinc ({len(hhinc)}) with share_bg ({len(weights)}) -> {len(merged)} rows")
    missing = merged['_merge'].value_counts().get('left_only', 0)
    if missing:
        logging.warning(f"step8: {missing} blockgroups had no share_bg and will contribute zero")
    merged.drop(columns=['_merge'], inplace=True)

    # Apply share_bg to allocate household quartiles
    for q in range(1,5):
        merged[f'HHINCQ{q}_w'] = merged[f'HHINCQ{q}'] * merged['share_bg']

        # Group by TAZ and sum weighted quartiles
    taz = merged.groupby('TAZ1454')[[f'HHINCQ{q}_w' for q in range(1,5)]].sum().reset_index()
    taz.columns = ['TAZ1454'] + [f'HHINCQ{q}' for q in range(1,5)]

    # Final rounding
    for q in range(1,5):
        taz[f'HHINCQ{q}'] = taz[f'HHINCQ{q}'].round().astype(int)

    # Sanity-check totals
    block_total = hhinc[[f'HHINCQ{q}' for q in range(1,5)]].sum().sum()
    taz_total   = taz.sum().sum()
    diff = block_total - taz_total
    logging.info(f"step8: total HH at blockgroup={block_total}, at TAZ={taz_total}, diff={diff}")

    return taz

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


def step9_summarize_tract_to_taz(acs_df, weights_df):
    """
    Summarize tract-level ACS data into TAZ, writing intermediate CSVs.

    Expects:
      - acs_df    : DataFrame with columns ['tract', 'hhwrks0_', 'hhwrks1_', 'hhwrks2_', 'hhwrks3p_', 
                     'ownkidsyes_', 'rentkidsyes_', 'ownkidsno_', 'rentkidsno_']
      - weights_df: DataFrame with columns ['tract', 'taz', 'weight']

    Returns:
      - DataFrame with columns ['taz', **'county_fips'**, 'TAZ1454',
        'weighted_hhwrks0_', …, 'weighted_rentkidsno_']
    """
    import os
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)

    # 1) Log incoming schemas
    logger.info(f"acs_df columns: {acs_df.columns.tolist()}")
    logger.info(f"weights_df columns: {weights_df.columns.tolist()}")

    # 1a) Derive county_fips from tract
    acs_df = acs_df.copy()
    acs_df['county_fips'] = acs_df['tract'].str[:5]

    # 2) Merge on tract
    merged = acs_df.merge(
        weights_df[['tract', 'taz', 'weight']],
        on='tract',
        how='left'
    )
    missing = merged['weight'].isna().sum()
    if missing > 0:
        logger.warning(f"{missing} records missing tract-to-TAZ weight")

    # 3) Write merged for inspection
    merged_path = os.path.join(os.getcwd(), 'step9_merged.csv')
    #merged.to_csv(merged_path, index=False)
    logger.info(f"Wrote merged tract-to-TAZ to {merged_path}")

    # 4) Compute weighted ACS variables
    acs_vars = ['hhwrks0', 'hhwrks1', 'hhwrks2', 'hhwrks3p',
                'ownkidsyes', 'rentkidsyes', 'ownkidsno', 'rentkidsno']
    for var in acs_vars:
        merged[f'weighted_{var}'] = merged[var] * merged['weight']

    # 5) Aggregate to TAZ **and preserve county_fips**
    agg_dict = {f'weighted_{var}': 'sum' for var in acs_vars}
    # keep one county_fips per TAZ (assumes each TAZ is in a single county)
    agg_dict.update({
        'taz': 'first',
        'county_fips': 'first'      # ← add this line
    })
    taz_df = merged.groupby('taz', as_index=False).agg(agg_dict)

    # 6) Preserve original TAZ identifier
    taz_df['TAZ1454'] = taz_df['taz']

    # 7) Write summary for inspection
    summary_path = os.path.join(os.getcwd(), 'step9_taz_summary.csv')
    #taz_df.to_csv(summary_path, index=False)
    logger.info(f"Wrote TAZ ACS summary to {summary_path}")

    return taz_df

