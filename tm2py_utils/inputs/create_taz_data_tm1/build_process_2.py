
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
import requests
from census import Census
import numpy as np


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
    map_acs5year_household_income_to_tm1_categories
)



# ------------------------------
# STEP 5: Disaggregate ACS BG vars to block level
# ------------------------------
def compute_block_shares(
    df_blk: pd.DataFrame,
    df_bg: pd.DataFrame
) -> pd.DataFrame:
    """
    Disaggregate BG-level ACS variables to blocks by block-population share,
    then compute block-to-tract share.  Returns one row per block:
      ['block_geoid','blockgroup','tract','pop',
       <all numeric BG vars allocated to the block>,
       'share_bg','tract_share']
    """
    import numpy as np
    import logging

    logger = logging.getLogger(__name__)

    # 1) Prepare BG data
    df_bg2 = df_bg.copy()
    if 'blockgroup' not in df_bg2.columns:
        raise KeyError("step5: missing 'blockgroup' in ACS BG data")

    # rename for clarity, then re-create blockgroup key
    df_bg2 = df_bg2.rename(columns={'blockgroup':'BG_GEOID'})
    df_bg2['blockgroup'] = df_bg2['BG_GEOID']
    # drop any accidental 'tract' column
    df_bg2 = df_bg2.drop(columns=['tract'], errors='ignore')

    # identify exactly the ACS_BG_VARIABLES you want to allocate
    geo_cols = {'BG_GEOID','blockgroup','state','county','County_Name'}
    bg_vars = [c for c in df_bg2.columns if c not in geo_cols]

    # coerce them to numeric (fill NAs with zero)
    df_bg2[bg_vars] = df_bg2[bg_vars].apply(pd.to_numeric, errors='coerce').fillna(0)

    # 2) Start from your block-level frame
    df = df_blk.copy()
    if 'block_geoid' not in df.columns or 'pop' not in df.columns:
        raise KeyError("step5: block data must include 'block_geoid' and 'pop'")

    # derive blockgroup & tract
    df['blockgroup'] = df['block_geoid'].astype(str).str[:12].str.zfill(12)
    df['tract']      = df['blockgroup'].str[:11]

    # 3) compute block-to-BG share (share_bg)
    df['bg_pop']     = df.groupby('blockgroup')['pop'].transform('sum')
    df['share_bg']   = np.where(df['bg_pop']>0, df['pop']/df['bg_pop'], 0)
    # normalize so shares sum to 1 in each BG
    df['share_bg']   = df['share_bg'] / df.groupby('blockgroup')['share_bg'].transform('sum')

    # 4) compute block-to-tract share (if you still need it)
    df['tract_pop']  = df.groupby('tract')['pop'].transform('sum')
    df['tract_share']= np.where(df['tract_pop']>0, df['pop']/df['tract_pop'], 0)

    # 5) bring in the BG vars and allocate
    df = df.merge(
        df_bg2[['blockgroup'] + bg_vars],
        on='blockgroup', how='left', validate='many_to_one', indicator='bg_merge'
    )
    logger.info("[step5] bg_merge counts -> %s", df['bg_merge'].value_counts().to_dict())
    df = df.drop(columns=['bg_merge'])

    for var in bg_vars:
        df[var] = df[var] * df['share_bg']

    # 6) select and return
    final_cols = (
      ['block_geoid','blockgroup','tract','pop']
      + bg_vars
      + ['share_bg','tract_share']
    )
    out = df[final_cols]
    logger.info("[step5] output columns: %s", out.columns.tolist())
    return out

    return df[['block_geoid','blockgroup','tract'] + bg_vars + ['pop_share','sharetract']]
def build_workingdata(
    shares: pd.DataFrame,
    acs_tr: pd.DataFrame,
    dhc_tr: pd.DataFrame
) -> pd.DataFrame:
    """
     Build the working block-level DataFrame by merging in:
      - weighted tract-level ACS variables
      - weighted tract-level DHC variables

    Assumes `shares` includes:
      - 'blockgroup','pop_share','sharetract'
      - all BG aggregates already weighted
    """
    logger = logging.getLogger(__name__)

    df = shares.copy()
    df['blockgroup'] = df['blockgroup'].astype(str).str.zfill(12)
    df['tract'] = df['blockgroup'].str[:11]

    logger.info(f"inputs ▶ shares={df.shape}, acs_tr={acs_tr.shape}, dhc_tr={dhc_tr.shape}")

    acs_tr = acs_tr.copy()
    acs_tr['tract'] = acs_tr['tract'].astype(str)
    tr_cols = [c for c in acs_tr.columns if c != 'tract']
    m1 = df.merge(
        acs_tr[['tract'] + tr_cols],
        on='tract', how='left', indicator='tr_merge'
    )
    logger.info(f"tr_merge → {m1['tr_merge'].value_counts().to_dict()}")
    df = m1.drop(columns=['tr_merge'])

    dhc_tr = dhc_tr.copy()
    dhc_tr['tract'] = dhc_tr['tract'].astype(str)
    gq_cols = [c for c in dhc_tr.columns if c != 'tract']
    m2 = df.merge(
        dhc_tr[['tract'] + gq_cols],
        on='tract', how='left', indicator='dhc_merge'
    )
    logger.info(f"dhc_merge → {m2['dhc_merge'].value_counts().to_dict()}")
    df_final = m2.drop(columns=['dhc_merge'])

    logger.info(f"output shape ▶ {df_final.shape}")
    return df_final




# ------------------------------
# STEP 7: Map ACS income bins to TM1 quartiles
# ------------------------------
def process_household_income(df_working, year=ACS_5YR_LATEST):
    """
    Allocate ACS block‑group income bins into TM1 HHINCQ1–4 by share.
    Accepts df_working columns named either “tothh”, “hhinc000_010”, … 
    or “tothh_”, “hhinc000_010_”, … and produces:
      - blockgroup : 12‑digit FIPS
      - HHINCQ1..HHINCQ4 : int
    """
    mapping = map_acs5year_household_income_to_tm1_categories(year)

    # 1) Build raw‐code → working‐col map, matching either suffix or no‑suffix
    code_to_col = {}
    for new_var, old_code in VARIABLES['ACS_BG_VARIABLES'].items():
        if not old_code.startswith("B19001_"):
            continue
        # prefer bare name, else trailing‑underscore name
        if new_var in df_working.columns:
            col = new_var
        elif new_var + "_" in df_working.columns:
            col = new_var + "_"
        else:
            logging.warning(f"step7: ACS_BG_VARIABLES defines '{new_var}' but working DF lacks both '{new_var}' and '{new_var}_'")
            continue
        code_to_col[old_code] = col

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
            logging.warning(f"step7: no working‑column mapped for ACS code {acs_code}")
            continue
        out[f"HHINCQ{q}"] += df_working[col].fillna(0) * share

    # 4) Round and cast
    for q in (1,2,3,4):
        out[f"HHINCQ{q}"] = out[f"HHINCQ{q}"].round().astype(int)

    return out

