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


def step8_summarize_to_taz(data_df, weights_df):
    """
    Summarize blockgroup-level household income data into TAZ.

    Expects:
      - data_df    : DataFrame with columns ['blockgroup', 'HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4']
      - weights_df : DataFrame with columns including a blockgroup identifier, a TAZ identifier, and 'weight'

    Returns:
      - DataFrame with columns ['taz', 'weighted_HHINCQ1', 'weighted_HHINCQ2',
        'weighted_HHINCQ3', 'weighted_HHINCQ4']
    """
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)

    # Debug: show incoming DataFrame schemas
    logger.info(f"data_df columns: {data_df.columns.tolist()}")
    logger.info(f"weights_df columns: {weights_df.columns.tolist()}")

    # Identify the blockgroup key in weights_df
    block_keys = ['blockgroup', 'block', 'GEOID']
    right_block_key = next((col for col in block_keys if col in weights_df.columns), None)
    if right_block_key is None:
        raise KeyError(
            "weights_df must contain a blockgroup identifier column: one of {}".format(block_keys)
        )

    # Identify the TAZ key in weights_df
    taz_keys = ['TAZ1454', 'TAZ', 'taz']
    right_taz_key = next((col for col in taz_keys if col in weights_df.columns), None)
    if right_taz_key is None:
        raise KeyError(
            "weights_df must contain a TAZ identifier column: one of {}".format(taz_keys)
        )

    # Ensure weight column exists
    if 'weight' not in weights_df.columns:
        raise KeyError("weights_df must contain a 'weight' column")

    logger.info(f"Using blockgroup key: {right_block_key}, TAZ key: {right_taz_key}")

    # 1) Merge data_df with weights_df on blockgroup
    df = data_df.merge(
        weights_df[[right_block_key, right_taz_key, 'weight']],
        left_on='blockgroup', right_on=right_block_key,
        how='left'
    )
    missing_w = df['weight'].isna().sum()
    if missing_w > 0:
        logger.warning(f"{missing_w} records missing crosswalk weight")

    # Drop duplicate key column if needed
    if right_block_key != 'blockgroup':
        df = df.drop(columns=[right_block_key])

    # Rename TAZ column to 'taz' for consistency
    if right_taz_key != 'taz':
        df = df.rename(columns={right_taz_key: 'taz'})

    # 2) Compute weighted values for each household income quartile
    quartiles = ['HHINCQ1', 'HHINCQ2', 'HHINCQ3', 'HHINCQ4']
    for q in quartiles:
        df[f'weighted_{q}'] = df[q] * df['weight']

    # 3) Aggregate to TAZ
    agg_dict = {f'weighted_{q}': 'sum' for q in quartiles}
    taz_df = df.groupby('taz', as_index=False).agg(agg_dict)

    return taz_df

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
    merged.to_csv(merged_path, index=False)
    logger.info(f"Wrote merged tract-to-TAZ to {merged_path}")

    # 4) Compute weighted ACS variables
    acs_vars = ['hhwrks0_', 'hhwrks1_', 'hhwrks2_', 'hhwrks3p_',
                'ownkidsyes_', 'rentkidsyes_', 'ownkidsno_', 'rentkidsno_']
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
    taz_df.to_csv(summary_path, index=False)
    logger.info(f"Wrote TAZ ACS summary to {summary_path}")

    return taz_df
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