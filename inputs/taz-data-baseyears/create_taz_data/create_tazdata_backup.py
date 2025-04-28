#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
create_taz_data.py

End-to-end TAZ data pipeline for Travel Model One and Two.
Loads all settings (constants, paths, geo, variable mappings) from config.yaml.
Defines 13 sequential steps, each stubbed out for implementation.
"""
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
import requests
from census import Census

# ------------------------------
# Load configuration
# ------------------------------
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
DECENNIAL_YEAR = CONSTANTS['DECENNIAL_YEAR']
ACS_5YR_LATEST = CONSTANTS['ACS_5YEAR_LATEST']

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

# ------------------------------
# STUBS FOR EACH STEP
# ------------------------------
def step1_fetch_block_data(c, year):
    """1) Fetch block-level population (2020 Decennial PL)"""
    df_raw = download_acs_blocks(c, year, 'dec/pl')
    if df_raw.empty:
        logging.error('No block data retrieved; exiting.')
        sys.exit(1)
    df = census_to_df(df_raw)
    if 'P1_001N' in df.columns:
        df = df.rename(columns={'P1_001N': 'pop'})
    else:
        logging.error('Expected P1_001N field not found in block data')
        sys.exit(1)
    result = df[['GEOID', 'pop']].copy()
    result['pop'] = pd.to_numeric(result['pop'], errors='coerce').fillna(0).astype(int)
    return result

def step2_fetch_acs_bg(c, year):
    """
    2) Fetch ACS5 block‐group estimates for all variables listed in config.yaml:
       VARIABLES['ACS_BG_VARIABLES'] maps output_name → ACS code (without the “E”).
    """
    var_map     = VARIABLES['ACS_BG_VARIABLES']   # e.g. {'tothh_': 'B19001_001', …}
    state_code  = GEO['STATE_CODE']
    counties    = GEO['BA_COUNTY_FIPS_CODES']    # e.g. ['001','013',…]
    
    # Turn the var_map into a list of (name, code) pairs
    items       = list(var_map.items())
    batch_size  = 45
    batches     = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    
    df_chunks = []
    
    for batch in batches:
        # build your fetch list and rename map for *this* batch
        fetch_vars   = [f"{code}E" for (_, code) in batch]
        rename_map   = {f"{code}E": name for (name, code) in batch}
        
        # pull each county
        records = []
        for county in counties:
            try:
                recs = retrieve_census_variables(
                    c, year, 'acs5', fetch_vars,
                    for_geo  = 'block group',
                    state    = state_code,
                    county   = county
                )
            except Exception as e:
                logging.warning(f"County {county} failed: {e}")
                continue
            records.extend(recs)
        
        if not records:
            # nothing came back for this batch
            continue
        
        # convert & rename
        df_batch = census_to_df(records).rename(columns=rename_map)
        df_chunks.append(df_batch)
    
    if not df_chunks:
        logging.error("No ACS data was fetched for *any* batch.")
        return pd.DataFrame()
    
    # merge all the batches back together on the geo columns
    geo_cols = ['state', 'county', 'tract', 'block group']
    df = df_chunks[0]
    for df_next in df_chunks[1:]:
        df = df.merge(df_next, on=geo_cols, how='outer')
    
    # now coerce every output_name to int, filling any missing with zero
    for output_name in var_map.keys():
        if output_name in df.columns:
        # existing column: coerce to numeric
            series = (
                pd.to_numeric(df[output_name], errors='coerce')
                .fillna(0)
                .astype(int)
         )
        else:
         # missing column: create a zero Series
            series = pd.Series(0, index=df.index, dtype=int)
        df[output_name] = series
    
    return df

def step3_fetch_acs_tract(c, year=YEAR):
    var_map    = VARIABLES.get('ACS_TRACT_VARIABLES', {})
    if not var_map:
        raise ValueError("CONFIG ERROR: 'ACS_TRACT_VARIABLES' is empty in config.yaml")

    fetch_vars = [f"{code}E" for code in var_map.values()]
    state_code = GEO['STATE_CODE']
    county_codes = list(GEO['BA_COUNTY_FIPS_CODES'].keys())

    tract_records = []
    for county in county_codes:
        recs = retrieve_census_variables(
            c, year, 'acs5', fetch_vars,
            for_geo='tract', state=state_code, county=county
        )
        tract_records.extend(recs)

    if not tract_records:
        logging.warning(f"No ACS tract records fetched for year {year}")
        return pd.DataFrame()

    df = census_to_df(tract_records)

    # --- NEW: ensure every desired column exists as a Series before coercion ---
    for out_col in var_map:
        if out_col not in df.columns:
            # create a Series of zeros matching the DataFrame's index
            df[out_col] = pd.Series(0, index=df.index)

        # now this is guaranteed to be a Series
        df[out_col] = (
            pd.to_numeric(df[out_col], errors='coerce')
              .fillna(0)
              .astype(int)
        )

    return df

def step4_fetch_dhc_tract(c, year=YEAR):
    """
    Fetch full 2020 Demographic & Housing Characteristics (DHC) SF1 tables
    (the PCT19_* series) at the tract level by calling the /data/{year}/dec/dhc 
    endpoint directly with requests.
    """

    # 1) Your age/sex group‐quarters mapping
    var_map = VARIABLES.get('DHC_TRACT_VARIABLES', {})
    if not var_map:
        raise ValueError("CONFIG ERROR: 'DHC_TRACT_VARIABLES' is empty in config.yaml")
    codes = list(var_map.values())

    state = GEO['STATE_CODE']
    counties = list(GEO['BA_COUNTY_FIPS_CODES'].keys())

    records = []
    base_url = f"https://api.census.gov/data/{year}/dec/dhc"

    # 2) Loop each county, fetch tract‐level DHC
    for county in counties:
        params = {
            "get":    ",".join(codes),
            "for":    "tract:*",
            "in":     f"state:{state}+county:{county}",
            "key":    CENSUS_API_KEY   # if your c object has the key attribute
        }
        resp = requests.get(base_url, params=params)
        resp.raise_for_status()

        data = resp.json()
        header, *rows = data
        for row in rows:
            rec = dict(zip(header, row))
            records.append(rec)

    if not records:
        logging.warning(f"No DHC tract records fetched for year {year}")
        return pd.DataFrame()

    # 3) Build DataFrame, rename & coerce
    df = pd.DataFrame(records)
    df = df.rename(columns={code: name for name, code in var_map.items()})

    for name in var_map:
        df[name] = (
            pd.to_numeric(df[name], errors="coerce")
              .fillna(0)
              .astype(int)
        )

    return df


    

def step5_compute_block_shares(df_blk, df_bg):
    """
    5) Compute the share of block‐group ACS estimates at the block level.

    Parameters
    ----------
    df_blk : DataFrame with columns
        - 'GEOID' (block GEOID)
        - 'pop'   (block population)
    df_bg : DataFrame with columns
        - 'GEOID' (block‐group GEOID)
        - one column per VARIABLES['ACS_BG_VARIABLES'] key

    Returns
    -------
    DataFrame with one row per block, containing:
        - 'GEOID' (block GEOID)
        - disaggregated ACS BG variables
    """

    # 1) Start from the block‐level DataFrame
    df = df_blk.copy()

    # 2) Extract the block‐group GEOID (first 12 chars of block GEOID)
    df['BG_GEOID'] = df['GEOID'].str[:12]

    # 3) Compute total population per block‐group
    bg_pop = (
        df
        .groupby('BG_GEOID')['pop']
        .sum()
        .reset_index()
        .rename(columns={'pop': 'bg_pop'})
    )
    df = df.merge(bg_pop, on='BG_GEOID', how='left')

    # 4) Compute each block’s share of its block‐group population,
    #    avoiding divide‐by‐zero by replacing bg_pop=0 with 1
    df['pop_share'] = df['pop'] / df['bg_pop'].replace({0: 1})

    # 5) Merge in the ACS block‐group estimates
    df = df.merge(
        df_bg.rename(columns={'GEOID': 'BG_GEOID'}),
        on='BG_GEOID',
        how='left'
    )

    # 6) Clean up any NaNs before disaggregation
    df['pop_share'] = df['pop_share'].fillna(0)

    bg_vars = list(VARIABLES['ACS_BG_VARIABLES'].keys())
    df[bg_vars] = df[bg_vars].fillna(0)

    # 7) Disaggregate each ACS BG variable to the block
    for var in bg_vars:
        df[var] = (
            df['pop_share'] * df[var]
        ).round().astype(int)

    # 8) Return only block GEOID + the disaggregated vars
    return df[['GEOID'] + bg_vars]

def step5_compute_block_shares(df_blk, df_bg):
    # … all the same up through the merge …
    df['pop_share'] = df['pop'] / df['bg_pop'].where(df['bg_pop']>0, 1)
    df = df.merge(df_bg.rename(columns={'GEOID':'BG_GEOID'}), on='BG_GEOID', how='left')

    # Make sure pop_share has no NaNs (blocks in BGs with zero pop → share=0)
    df['pop_share'] = df['pop_share'].fillna(0)

    bg_vars = list(VARIABLES['ACS_BG_VARIABLES'].keys())

    # And make any missing ACS BG vars zero before disaggregation
    df[bg_vars] = df[bg_vars].fillna(0)

    # Now do the disaggregation and safe cast
    for var in bg_vars:
        df[var] = (
            df['pop_share'] * df[var]
        ).round().astype(int)

    return df[['GEOID'] + bg_vars]

def step6_build_workingdata(df_shares, df_bg, df_tract, df_dhc):
    """
    6) Build the working dataset at block geography by merging:
       - df_shares: block-level disaggregated ACS BG variables (GEOID + bg_vars)
       - df_tract:  tract-level ACS variables (state,county,tract + tract_vars)
       - df_dhc:    tract-level DHC variables (state,county,tract + gq_vars)

    Returns
    -------
    DataFrame, one row per block, with:
      - GEOID, state, county, tract, block_group, block
      - all ACS BG vars at block level
      - all ACS tract vars (repeated for each block in tract)
      - all DHC vars (repeated for each block in tract)
    """
    # 1) Start from the block‐level shares
    df = df_shares.copy()

    # 2) Pull apart the GEOID into its components
    df['state']       = df['GEOID'].str[:2]
    df['county']      = df['GEOID'].str[2:5]
    df['tract']       = df['GEOID'].str[5:11]
    df['block_group'] = df['GEOID'].str[11:12]
    df['block']       = df['GEOID'].str[12:]

    # 3) Merge in tract‐level ACS variables
    df = df.merge(
        df_tract,
        on=['state', 'county', 'tract'],
        how='left',
    )

    # 4) Merge in tract‐level DHC variables
    df = df.merge(
        df_dhc,
        on=['state', 'county', 'tract'],
        how='left',
    )

    return df

def step7_process_household_income(working, year):
    """
    7) Map ACS 5-year household income ranges into TM1 income quartiles
       at the block level, finding any GEOID-like column automatically.
    """
    # 1) Find your GEOID column (case-insensitive substring match)
    geoid_col = None
    for col in working.columns:
        if 'geoid' in col.lower():
            geoid_col = col
            break
    if geoid_col is None:
        raise KeyError(
            f"step7: could not find a GEOID column in working DataFrame. "
            f"Found columns: {list(working.columns)}"
        )

    # 2) Load the ACS→quartile mapping
    map_df = map_acs5year_household_income_to_tm1_categories(year)

    # 3) Invert your ACS_BG_VARIABLES to map codes → working‐DF column names
    code_to_var = {code: name for name, code in VARIABLES['ACS_BG_VARIABLES'].items()}

    # 4) Prepare the output DataFrame, seeding GEOID from whatever column we found
    out = pd.DataFrame({'GEOID': working[geoid_col]})
    for q in sorted(map_df['HHINCQ'].unique()):
        out[f'hhincq{q}'] = 0.0

    # 5) Allocate each ACS income bin into its TM1 quartile
    for _, row in map_df.iterrows():
        code  = row['incrange']  # e.g. "B19001_007"
        quart = row['HHINCQ']     # 1–4
        share = row['share']      # fraction
        col   = code_to_var.get(code)

        if col not in working.columns:
            logging.warning(f"step7: missing ACS column for code {code}, skipping.")
            continue

        out[f'hhincq{quart}'] += working[col].fillna(0) * share

    # 6) Round & cast to int
    for col in out.columns:
        if col.startswith('hhincq'):
            out[col] = out[col].round().astype(int)

    return out

def step9_summarize_tract_to_taz(df_tract, df_weights):
    """
    df_tract: DataFrame of tract‐level vars, with GEOID column
    df_weights: output of compute_tract_weights()
    """
    # 1) rename GEOID → tract for the join
    df = (
        df_weights
          .merge(df_tract.rename(columns={"GEOID": "tract"}),
                 on="tract", how="left")
    )
    
    # 2) identify your tract vars (all except 'tract', 'TAZ1454', 'weight')
    tract_vars = [c for c in df_tract.columns if c != "GEOID"]
    
    # 3) apply the weight
    for var in tract_vars:
        df[var] = df[var] * df["weight"]
    
    # 4) aggregate up to TAZ
    return (
        df
          .groupby("TAZ1454")[tract_vars]
          .sum()
          .reset_index()
    )

def step9_integrate_employment(year): raise NotImplementedError

def step10_build_county_targets(taz, emp): raise NotImplementedError

def step11_apply_scaling(taz, targets): raise NotImplementedError

def step12_join_pba2015(taz): raise NotImplementedError

def step13_write_outputs(taz, year): raise NotImplementedError


def compute_block_weights(paths):
    """
    Read your block-to-TAZ crosswalk, compute each block’s share
    of its blockgroup, and return a DataFrame of weights.
    """
    cw_path = Path(__file__).parent / Path(paths["block2020_to_taz1454_csv"])
    df = pd.read_csv(cw_path, dtype={'blockgroup': str})
    
    # ensure population is numeric
    df['block_POPULATION'] = (
        pd.to_numeric(df['block_POPULATION'], errors='coerce')
          .fillna(0)
    )
    
    # compute total pop per blockgroup
    df['group_pop'] = df.groupby('blockgroup')['block_POPULATION'].transform('sum')
    
    # each block’s weight within its blockgroup
    df['weight'] = df['block_POPULATION'] / df['group_pop']
    
    return df[['GEOID', 'blockgroup', 'TAZ1454', 'weight']]

def compute_tract_weights(paths):
    """
    Read your tract‐to‐TAZ crosswalk, ensure there's a 'weight' column,
    and return only the columns we need.
    """
    cw_path = Path(__file__).parent / paths["taz_crosswalk"]
    df = pd.read_csv(cw_path, dtype={"tract": str})
    
    # if there's no explicit weight, assume equal share across TAZ overlaps
    if "weight" not in df.columns:
        df["weight"] = 1 / df.groupby("TAZ1454")["tract"].transform("count")

    return df[["tract", "TAZ1454", "weight"]]
# ------------------------------
# Logging setup
# ------------------------------
def setup_logging(year):
    out_dir = Path(os.path.expandvars(PATHS['output_root']).replace('${YEAR}', str(year)))
    out_dir.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(), logging.FileHandler(out_dir / f'create_tazdata_{year}.log')]
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=handlers)

# ------------------------------
# Census client
# ------------------------------
def setup_census_client():
    key_file = Path(os.path.expandvars(PATHS['census_api_key_file']))
    api_key = key_file.read_text().strip()
    return Census(api_key)

# ------------------------------
# Main pipeline execution
# ------------------------------
def main():
    # Use configured YEAR instead of CLI args
    setup_logging(YEAR)
    logging.info(f"Starting TAZ pipeline for YEAR={YEAR}")

    c = setup_census_client()

    outputs = {}
    outputs['blocks'] = step1_fetch_block_data(c, YEAR)
    outputs['acs_bg'] = step2_fetch_acs_bg(c, YEAR)
    outputs['acs_tr'] = step3_fetch_acs_tract(c, min(YEAR + 2, ACS_5YR_LATEST))
    outputs['dhc_tr'] = step4_fetch_dhc_tract(c)
    outputs['shares'] = step5_compute_block_shares(outputs['blocks'], outputs['acs_bg'])
    outputs['working'] = step6_build_workingdata(
        outputs['shares'], outputs['acs_bg'], outputs['acs_tr'], outputs['dhc_tr']
    )
    outputs['hhinc'] = step7_process_household_income(outputs['working'], ACS_5YR_LATEST)
    outputs['weights'] = compute_block_weights(PATHS)
    df_bg = outputs['hhinc'].rename(columns={"GEOID":"blockgroup"})
    outputs["taz"] = step8_summarize_to_taz(
        df_bg=df_bg,
        df_weights=outputs["weights"]
    )
    # Step 9a: read tract→TAZ weights
    outputs["weights_tract"] = compute_tract_weights(PATHS)

    # Step 9b: compute tract‐based TAZ summaries
    outputs["taz_tract"] = step9_summarize_tract_to_taz(
    df_tract   = outputs["tract"],
    df_weights = outputs["weights_tract"]
    )

# (Optional) merge block‐group TAZ + tract TAZ into one final table
    outputs["taz_final"] = (
        outputs["taz"]
        .merge(outputs["taz_tract"],
             on="TAZ1454", how="left")
)
    outputs['emp'] = step9_integrate_employment(YEAR)
    outputs['targets'] = step10_build_county_targets(outputs['taz'], outputs['emp'])
    outputs['scaled'] = step11_apply_scaling(outputs['taz'], outputs['targets'])
    outputs['final'] = step12_join_pba2015(outputs['scaled'])
    step13_write_outputs(outputs['final'], YEAR)

    logging.info("TAZ data processing complete.")

if __name__ == '__main__':
    main()

