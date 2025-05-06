
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
import requests
from census import Census

CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)

CONSTANTS = cfg['constants']
GEO       = cfg['geo_constants']
PATHS     = cfg['paths']
VARIABLES = cfg['variables']

KEY_FILE = PATHS['census_api_key_file']
with open(KEY_FILE, 'r') as f:
    CENSUS_API_KEY = f.read().strip()

# Default processing year from config
YEAR = CONSTANTS['years'][0]
DECENNIAL_YEAR  = CONSTANTS['DECENNIAL_YEAR']
ACS_5YR_LATEST  = CONSTANTS['ACS_5YEAR_LATEST']

# ------------------------------
# Import helper functions from common.py
# ------------------------------
sys.path.insert(0, str(Path(__file__).parent))
from common import (
    census_to_df,
    download_acs_blocks,
    retrieve_census_variables,
    fix_rounding_artifacts,
    map_acs5year_household_income_to_tm1_categories,
    update_gqpop_to_county_totals,
    update_tazdata_to_county_target,
    make_hhsizes_consistent_with_population,
)

import logging
import pandas as pd

# ------------------------------
# STEP 5: Disaggregate ACS BG vars to block level
# ------------------------------
def step5_compute_block_shares(df_blk, df_bg):
    """
    Disaggregate ACS block-group vars to blocks using block-population share.
    Expects:
      - df_blk has 'block_geoid' (15-digit) and 'pop'
      - df_bg has 'blockgroup' (12-digit) plus ACS_BG_VARIABLES keys
    Returns:
      ['block_geoid','blockgroup'] + ACS_BG_VARIABLES keys + ['pop_share']
    """
    # 1) Copy & promote the BG codes from your ACS table
    df_bg2 = df_bg.copy()
    if 'blockgroup' not in df_bg2.columns:
        raise KeyError("step5: missing 'blockgroup' in ACS BG data")
    df_bg2['BG_GEOID'] = df_bg2['blockgroup']

    # 2) Start from block-level pop
    df = df_blk.copy()
    if 'block_geoid' not in df.columns:
        raise KeyError("step5: missing 'block_geoid' in block data")
    # first 12 digits of block_geoid give blockgroup
    df['BG_GEOID'] = df['block_geoid'].astype(str).str[:12]

    # 3) Compute blockgroup total pop & shares
    bg_pop = (
        df.groupby('BG_GEOID')['pop']
          .sum()
          .reset_index()
          .rename(columns={'pop':'bg_pop'})
    )
    df = df.merge(bg_pop, on='BG_GEOID', how='left')
    df['pop_share'] = df['pop'] / df['bg_pop'].replace({0:1})

    logging.info(
        "Block share sample:\n%s",
        df[['block_geoid','pop','bg_pop','pop_share']].head()
    )

    # 4) Merge in ACS block-group variables
    df = df.merge(df_bg2, on='BG_GEOID', how='left')
    bg_vars = list(VARIABLES['ACS_BG_VARIABLES'].keys())
    logging.info(
        "ACS BG values at first block:\n%s",
        df[bg_vars].iloc[0]
    )

    # 5) Disaggregate each ACS var
    for var in bg_vars:
        df[var] = df['pop_share'] * df[var].fillna(0)

    # 6) Rename BG_GEOID back to blockgroup for step6
    df['blockgroup'] = df['BG_GEOID']

    return df[['block_geoid','blockgroup'] + bg_vars + ['pop_share']]

import pandas as pd
import logging

def step6_build_workingdata(
    shares: pd.DataFrame,
    acs_bg: pd.DataFrame,
    acs_tr: pd.DataFrame,
    dhc_tr: pd.DataFrame
) -> pd.DataFrame:
    """
    Step 6: Build the “working” block‐level DataFrame by:
      a) Copying shares to avoid fragmentation warnings
      b) Ensuring 'blockgroup' is a 12-digit string and deriving 'tract'
      c) Merging BG-level ACS summaries (acs_bg)
      d) Merging tract-level ACS (acs_tr) with merge indicators & logs
      e) Merging tract-level DHC (dhc_tr) with merge indicators & logs

    Parameters
    ----------
    shares : DataFrame
        Block-to-BG weight shares. Must have 'blockgroup' column.
    acs_bg : DataFrame
        BG-level ACS summary from step2b_compute_bg_vars. Must have 'blockgroup'.
    acs_tr : DataFrame
        Tract-level ACS variables. Must have 'tract'.
    dhc_tr : DataFrame
        Tract-level group-quarters (DHC). Must have 'tract'.

    Returns
    -------
    DataFrame
        A block-level “working” table containing:
        - all original shares columns
        - all BG summaries (age bins, emp_occ_*, etc.)
        - all tract ACS variables
        - all tract DHC variables
    """
    # a) Copy to avoid fragmentation warnings
    df = shares.copy()

    # b) Ensure blockgroup (12 digits) and derive tract (first 11)
    df['blockgroup'] = df['blockgroup'].astype(str).str.zfill(12)
    df['tract'] = df['blockgroup'].str[:11]

    logger = logging.getLogger(__name__)
    logger.info(f"step6 inputs ▶ shares={shares.shape}, acs_bg={acs_bg.shape}, acs_tr={acs_tr.shape}, dhc_tr={dhc_tr.shape}")

    # c) Merge BG‐level ACS summaries
    m1 = df.merge(acs_bg, on='blockgroup', how='left', indicator='bg_merge')
    logger.info(f"bg_merge counts → {m1['bg_merge'].value_counts().to_dict()}")
    df = m1.drop(columns=['bg_merge'])

    # d) Merge tract‐level ACS
    m2 = df.merge(acs_tr, on='tract', how='left', indicator='tr_merge')
    logger.info(f"tr_merge counts → {m2['tr_merge'].value_counts().to_dict()}")
    df = m2.drop(columns=['tr_merge'])

    # e) Merge tract‐level DHC (group quarters)
    m3 = df.merge(dhc_tr, on='tract', how='left', indicator='dhc_merge')
    logger.info(f"dhc_merge counts → {m3['dhc_merge'].value_counts().to_dict()}")
    df_final = m3.drop(columns=['dhc_merge'])

    logger.info(f"step6 output shape ▶ {df_final.shape}")
    return df_final




# ------------------------------
# STEP 7: Map ACS income bins to TM1 quartiles
# ------------------------------
def step7_process_household_income(df_working, year=ACS_5YR_LATEST):
    """
    Allocate ACS block-group income bins into TM1 HHINCQ1–4 by share.
    Returns a DataFrame with:
      - blockgroup : 12-digit FIPS
      - HHINCQ1..HHINCQ4 : int
    """
    mapping = map_acs5year_household_income_to_tm1_categories(year)
    # 1) Build raw‐code → working‐col map, but only keep those actually in df_working
    code_to_col = {}
    for new_var, old_code in VARIABLES['ACS_BG_VARIABLES'].items():
        # only pick the B19001 bins
        if not old_code.startswith("B19001_"):
            continue
        if new_var in df_working.columns:
            code_to_col[old_code] = new_var
        else:
            logging.warning(f"step7: ACS_BG_VARIABLES defines '{new_var}' but working DF lacks that column")

    # 2) Kick off output keyed on blockgroup
    if "blockgroup" not in df_working.columns:
        raise KeyError("step7: working DF missing 'blockgroup'")
    out = pd.DataFrame({"blockgroup": df_working["blockgroup"]})
    for q in (1,2,3,4):
        out[f"HHINCQ{q}"] = 0.0

    # 3) Apply shares
    for _, row in mapping.iterrows():
        acs_code = row["incrange"]           # e.g. "B19001_002"
        q        = int(row["HHINCQ"])
        share    = float(row["share"])
        col      = code_to_col.get(acs_code)
        if col is None:
            logging.warning(f"step7: no working‐column mapped for ACS code {acs_code}")
            continue
        out[f"HHINCQ{q}"] += df_working[col].fillna(0) * share

    # 4) Round and cast
    for q in (1,2,3,4):
        out[f"HHINCQ{q}"] = out[f"HHINCQ{q}"].round().astype(int)
    return out

""" if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # The following dataframes must be provided by upstream process:
    # blocks, acs_bg, acs_tr, dhc_tr
    # For example, they could be imported or loaded prior to calling this module.

    # Run STEP 5–7
    shares = step5_compute_block_shares(blocks, acs_bg)
    working = step6_build_workingdata(shares, acs_tr, dhc_tr)
    hhinc = step7_process_household_income(working, ACS_5YR_LATEST)

    logging.info("Completed steps 5–7: share rows=%d, working rows=%d, hhinc rows=%d", 
                 shares.shape[0], working.shape[0], hhinc.shape[0])
 """