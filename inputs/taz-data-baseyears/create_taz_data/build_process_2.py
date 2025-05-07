
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
def step5_compute_block_shares(
    df_blk: pd.DataFrame,
    df_bg: pd.DataFrame
) -> pd.DataFrame:
    """
    Disaggregate BG-level aggregates to blocks by block-population share,
    then compute block-to-tract share, carrying through only BG-level ACS variables.

    Ensures pop_share is normalized to sum to 1 within each blockgroup.

    Returns columns:
      ['block_geoid','blockgroup','tract','pop', <numeric BG vars>, 'pop_share','tract_share']
    """
    logger = logging.getLogger(__name__)

    # Copy BG input and validate key
    df_bg2 = df_bg.copy()
    if 'blockgroup' not in df_bg2:
        raise KeyError("step5: missing 'blockgroup' in ACS BG data")

    # Rename BG key and drop unintended tract column
    df_bg2 = df_bg2.rename(columns={'blockgroup': 'BG_GEOID'})
    df_bg2 = df_bg2.drop(columns=['tract'], errors='ignore')
    df_bg2['blockgroup'] = df_bg2['BG_GEOID']

    # Exclude geo/string columns
    geo_ids = {'BG_GEOID', 'blockgroup', 'state', 'county', 'County_Name', 'block group'}
    carry_cols = [c for c in df_bg2.columns if c not in geo_ids]

    # Coerce BG vars to numeric
    df_bg2[carry_cols] = df_bg2[carry_cols].apply(pd.to_numeric, errors='coerce')

    # Start from blocks
    df = df_blk.copy()
    if 'block_geoid' not in df or 'pop' not in df:
        raise KeyError("step5: block data must include 'block_geoid' and 'pop'")

    # Derive blockgroup & tract
    df['blockgroup'] = df['block_geoid'].astype(str).str.slice(0, 12).str.zfill(12)
    df['tract'] = df['blockgroup'].str.slice(0, 11)

    # Compute raw BG pop and initial pop_share
    df['bg_pop'] = df.groupby('blockgroup')['pop'].transform('sum')
    df['pop_share'] = np.where(df['bg_pop']>0, df['pop']/df['bg_pop'], 0)

    # Normalize pop_share within each blockgroup
    sum_shares = df.groupby('blockgroup')['pop_share'].transform('sum')
    df['pop_share'] = np.where(sum_shares>0, df['pop_share']/sum_shares, 0)

    # Compute tract totals and tract_share
    df['tract_pop'] = df.groupby('tract')['pop'].transform('sum')
    df['tract_share'] = np.where(df['tract_pop']>0, df['pop']/df['tract_pop'], 0)

    # Merge BG variables into block-level DF
    df = df.merge(
        df_bg2[['blockgroup'] + carry_cols],
        on='blockgroup', how='left', indicator='bg_merge'
    )
    logger.info("[step5] bg_merge counts -> %s", df['bg_merge'].value_counts().to_dict())
    df = df.drop(columns=['bg_merge'])

    # After merge, select numeric carries
    numeric_cols = [c for c in carry_cols if np.issubdtype(df[c].dtype, np.number)]

    # Weight numeric BG vars by pop_share
    for col in numeric_cols:
        df[col] = df['pop_share'] * df[col].fillna(0)

    # Final selection: include original block pop for downstream use
    final_cols = ['block_geoid','blockgroup','tract','pop'] + numeric_cols + ['pop_share','tract_share']
    out = df[final_cols]
    logger.info("[step5] output columns: %s", out.columns.tolist())
    return out


    return df[['block_geoid','blockgroup','tract'] + bg_vars + ['pop_share','sharetract']]
def step6_build_workingdata(
    shares: pd.DataFrame,
    acs_tr: pd.DataFrame,
    dhc_tr: pd.DataFrame
) -> pd.DataFrame:
    """
    Step 6: Build the working block-level DataFrame by merging in:
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

    logger.info(f"step6 inputs ▶ shares={df.shape}, acs_tr={acs_tr.shape}, dhc_tr={dhc_tr.shape}")

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

    logger.info(f"step6 output shape ▶ {df_final.shape}")
    return df_final




# ------------------------------
# STEP 7: Map ACS income bins to TM1 quartiles
# ------------------------------
def step7_process_household_income(df_working, year=ACS_5YR_LATEST):
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