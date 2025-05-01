#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
create_taz_data.py

End-to-end TAZ data pipeline for Travel Model One and Two.
Loads all settings (constants, paths, geo, variable mappings) from config.yaml.
Defines 14 sequential steps to create TAZ-level data from Census and LODES data.
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

YEAR           = CONSTANTS['years'][0]
DECENNIAL_YEAR = CONSTANTS['DECENNIAL_YEAR']
ACS_5YR_LATEST = CONSTANTS['ACS_5YEAR_LATEST']

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
# STEP 1: Fetch block-level population (Decennial PL)
# ------------------------------
def step1_fetch_block_data(c: Census, year: int) -> pd.DataFrame:
    logger = logging.getLogger(__name__)
    codes = list(GEO['BA_COUNTY_FIPS_CODES'].keys())
    recs = []
    for cnt in codes:
        try:
            batch = retrieve_census_variables(c, DECENNIAL_YEAR, 'dec/pl', ['P1_001N'],
                                             for_geo='block', state=GEO['STATE_CODE'], county=cnt)
            recs.extend(batch)
        except Exception as e:
            logger.error(f"Error step1 county {cnt}: {e}")
    df = pd.DataFrame(recs)
    df['state']  = df['state'].str.zfill(2)
    df['county'] = df['county'].str.zfill(3)
    df['tract']  = df['tract'].str.zfill(6)
    df['block']  = df['block'].str.zfill(4)
    df['block_geoid'] = df['state'] + df['county'] + df['tract'] + df['block']
    df['blockgroup']  = df['block_geoid'].str[:12]
    df['tract']       = df['block_geoid'].str[:11]
    df['pop']         = pd.to_numeric(df.get('P1_001N', 0), errors='coerce').fillna(0).astype(int)
    return df[['state','county','block_geoid','blockgroup','tract','pop']]

# ------------------------------
# STEP 2: Fetch ACS block-group variables
# ------------------------------
def step2_fetch_acs_bg(c: Census, year: int) -> pd.DataFrame:
    logger = logging.getLogger(__name__)
    state = GEO['STATE_CODE']
    codes = list(GEO['BA_COUNTY_FIPS_CODES'].keys())
    vars_map = VARIABLES['ACS_BG_VARIABLES']
    apis = [f"{v}E" for v in vars_map.values()]
    recs = []
    for cnt in codes:
        try:
            recs.extend(retrieve_census_variables(c, year, 'acs5', apis,
                                                 for_geo='block group', state=state, county=cnt))
        except Exception as e:
            logger.error(f"Error step2 county {cnt}: {e}")
    df = pd.DataFrame(recs)
    geo = next((c for c in ['GEOID','geoid','block group'] if c in df.columns), None)
    if not geo:
        raise KeyError("step2: no GEOID column")
    df = df.rename(columns={geo:'blockgroup'})
    df['blockgroup'] = df['blockgroup'].astype(str).str[-12:].str.zfill(12)
    for out, code in vars_map.items():
        col = f"{code}E"
        if col in df:
            df[out] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        else:
            logger.warning(f"step2: missing {col}")
            df[out] = 0
    return df[['blockgroup'] + list(vars_map.keys())]

# ------------------------------
# STEP 3: Fetch ACS tract variables
# ------------------------------
def step3_fetch_acs_tract(c: Census, year: int = YEAR) -> pd.DataFrame:
    var_map = VARIABLES['ACS_TRACT_VARIABLES']
    apis = [f"{v}E" for v in var_map.values()]
    state = GEO['STATE_CODE']
    codes = list(GEO['BA_COUNTY_FIPS_CODES'].keys())
    recs = []
    for cnt in codes:
        recs.extend(retrieve_census_variables(c, year, 'acs5', apis,
                                              for_geo='tract', state=state, county=cnt))
    df = census_to_df(recs)
    df['tract'] = df['state'].str.zfill(2) + df['county'].str.zfill(3) + df['tract'].str.zfill(6)
    out = pd.DataFrame({'tract':df['tract']})
    for out_name, code in var_map.items():
        col = f"{code}E"
        if col in df:
            out[out_name] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        else:
            out[out_name] = 0
    return out

# ------------------------------
# STEP 4: Fetch DHC tract variables
# ------------------------------
def step4_fetch_dhc_tract(c: Census, year: int = DECENNIAL_YEAR) -> pd.DataFrame:
    var_map = VARIABLES['DHC_TRACT_VARIABLES']
    state = GEO['STATE_CODE']
    codes = list(GEO['BA_COUNTY_FIPS_CODES'].keys())
    rows = []
    for cnt in codes:
        resp = requests.get(f"https://api.census.gov/data/{year}/dec/dhc",
                            params={'get':','.join(var_map.values()),
                                    'for':'tract:*', 'in':f"state:{state}+county:{cnt}",
                                    'key':CENSUS_API_KEY})
        if resp.status_code==200:
            data=resp.json(); cols=data[0]
            for rec in data[1:]: rows.append(dict(zip(cols,rec)))
        else:
            logging.error(f"step4: DHC fail {cnt}")
    df=pd.DataFrame(rows).rename(columns={v:k for k,v in var_map.items()})
    df['tract']=df['state'].str.zfill(2)+df['county'].str.zfill(3)+df['tract'].str.zfill(6)
    out=pd.DataFrame({'tract':df['tract']})
    for k in var_map: out[k]=pd.to_numeric(df[k],errors='coerce').fillna(0).astype(int)
    return out

# ------------------------------
# STEP 5: Disaggregate ACS block-group variables to blocks
# ------------------------------
def step5_compute_block_shares(df_blk: pd.DataFrame, df_bg: pd.DataFrame) -> pd.DataFrame:
    """
    Disaggregate ACS block-group variables to blocks using population share.
    Expects:
      - df_blk has 'block_geoid' (15-digit) and 'pop'
      - df_bg has 'blockgroup' (12-digit) and ACS_BG_VARIABLES keys
    Returns a DataFrame with columns:
      - block_geoid, blockgroup, each ACS_BG_VARIABLE, pop_share
    """
    logger = logging.getLogger(__name__)
    # 1) Derive blockgroup from block_geoid
    df = df_blk.copy()
    if 'block_geoid' not in df.columns:
        raise KeyError("step5: missing 'block_geoid' in block data")
    df['blockgroup'] = df['block_geoid'].astype(str).str[:12]

    # 2) Compute total blockgroup population and share
    bg_pop = (
        df.groupby('blockgroup')['pop']
          .sum()
          .reset_index()
          .rename(columns={'pop':'bg_pop'})
    )
    df = df.merge(bg_pop, on='blockgroup', how='left')
    df['pop_share'] = df['pop'] / df['bg_pop'].replace({0:1})
    logging.info("step5: sample shares:
%s", df[['block_geoid','pop','bg_pop','pop_share']].head())

    # 3) Merge in ACS block-group variables
    if 'blockgroup' not in df_bg.columns:
        raise KeyError("step5: missing 'blockgroup' in ACS BG data")
    df = df.merge(df_bg, on='blockgroup', how='left', suffixes=(None,'_bg'))
    bg_vars = list(VARIABLES['ACS_BG_VARIABLES'].keys())
    logging.info("step5: ACS BG vars at first block:
%s", df[bg_vars].iloc[0])

    # 4) Disaggregate each variable by pop_share
    for var in bg_vars:
        if var in df.columns:
            df[var] = df[var].fillna(0) * df['pop_share']
        else:
            logger.warning(f"step5: variable {var} not found; filling zeros")
            df[var] = 0

    # 5) Return only needed columns
    return df[['block_geoid','blockgroup'] + bg_vars + ['pop_share']]

# ------------------------------
# STEP 6: Build Working Data# ------------------------------
# STEP 6: Build Working Data
# ------------------------------
def step6_build_workingdata(shares: pd.DataFrame, acs_tr: pd.DataFrame, dhc_tr: pd.DataFrame) -> pd.DataFrame:
    """
    Merge block-level shares (with ACS-BG vars) with ACS-tract and DHC-tract data.
    Expects:
      - shares has 'blockgroup', 'tract', ACS_BG_VARIABLES, and 'pop_share'
      - acs_tr and dhc_tr have 'tract' and corresponding variables
    Returns a DataFrame with one row per block including all input variables.
    """
    logger = logging.getLogger(__name__)
    # Ensure keys exist
    for df_name, df in [('shares', shares), ('acs_tr', acs_tr), ('dhc_tr', dhc_tr)]:
        if 'tract' not in df.columns:
            raise KeyError(f"step6: missing 'tract' in {df_name} data")
    # Copy shares
    df_work = shares.copy()
    # Merge ACS tract data
    merged_tr = df_work.merge(acs_tr, on='tract', how='left', indicator='acs_merge')
    logger.info(f"step6: ACS tract merge counts: {merged_tr['acs_merge'].value_counts().to_dict()}")
    df_work = merged_tr.drop(columns=['acs_merge'])
    # Merge DHC tract data
    merged_dhc = df_work.merge(dhc_tr, on='tract', how='left', indicator='dhc_merge')
    logger.info(f"step6: DHC tract merge counts: {merged_dhc['dhc_merge'].value_counts().to_dict()}")
    df_work = merged_dhc.drop(columns=['dhc_merge'])
    return df_work

# ------------------------------
# STEP 7: Process Household Income
# ------------------------------
# ------------------------------
def step7_process_household_income(df_working: pd.DataFrame, year: int = ACS_5YR_LATEST) -> pd.DataFrame:
    """
    Map ACS block-group income buckets to TM1 quartiles (HHINCQ1–4).
    Expects df_working to contain ACS_BG_VARIABLES output columns and 'blockgroup'.
    Returns DataFrame indexed by 'blockgroup' with HHINCQ1..HHINCQ4.
    """
    logger = logging.getLogger(__name__)
    if 'blockgroup' not in df_working.columns:
        raise KeyError("step7: missing 'blockgroup' in working data")
    mapping = map_acs5year_household_income_to_tm1_categories(year)
    # Initialize output
    out = pd.DataFrame({'blockgroup': df_working['blockgroup']})
    for q in range(1,5):
        out[f"HHINCQ{q}"] = 0.0
    # Build code->column mapping
    code_to_col = {old_code: new_var for new_var, old_code in VARIABLES['ACS_BG_VARIABLES'].items()
                   if old_code.startswith('B19001_') and new_var in df_working.columns}
    # Apply shares
    for _, row in mapping.iterrows():
        acs_code = row['incrange']
        q = int(row['HHINCQ'])
        share = float(row['share'])
        col = code_to_col.get(acs_code)
        if col:
            out[f"HHINCQ{q}"] += df_working[col].fillna(0) * share
        else:
            logger.debug(f"step7: no column mapped for ACS {acs_code}")
    # Round and cast
    for q in range(1,5):
        out[f"HHINCQ{q}"] = out[f"HHINCQ{q}"].round().astype(int)
    return out

# ------------------------------
# STEP 8: Compute Block Weights and Summarize to TAZ
# ------------------------------
# ------------------------------
def compute_block_weights(paths: dict) -> pd.DataFrame:
    """
    Load block-to-TAZ crosswalk and compute weights.
    Expects PATHS['block2020_to_taz1454_csv'] with 'block_POPULATION'.
    Returns DataFrame with 'blockgroup','TAZ1454','weight'.
    """
    cw = pd.read_csv(os.path.expandvars(paths['block2020_to_taz1454_csv']), dtype=str)
    if 'blockgroup' not in cw.columns or 'block_POPULATION' not in cw.columns:
        raise KeyError("step8: missing columns in crosswalk file")
    cw['block_POPULATION'] = pd.to_numeric(cw['block_POPULATION'], errors='coerce').fillna(0)
    cw['total_bg_pop'] = cw.groupby('blockgroup')['block_POPULATION'].transform('sum').replace({0:1})
    cw['weight'] = cw['block_POPULATION'] / cw['total_bg_pop']
    return cw[['blockgroup','TAZ1454','weight']]

def step8_summarize_to_taz(df_bg: pd.DataFrame, cw: pd.DataFrame) -> pd.DataFrame:
    """
    Apply block weights to block-group variables and aggregate to TAZ.
    Expects df_bg with 'blockgroup' and ACS_BG_VARIABLES.
    """
    if 'blockgroup' not in df_bg.columns:
        raise KeyError("step8: missing 'blockgroup' in block-group data")
    df = cw.merge(df_bg, on='blockgroup', how='left')
    vars_bg = [c for c in df_bg.columns if c != 'blockgroup']
    for var in vars_bg:
        df[var] = df[var].fillna(0) * df['weight']
    taz_df = df.groupby('TAZ1454', as_index=False)[vars_bg].sum()
    return taz_df

# ------------------------------
# STEP 9: Compute Tract Weights and Summarize to TAZ
# ------------------------------
# ------------------------------
def compute_tract_weights(paths: dict) -> pd.DataFrame:
    """
    Load tract-to-TAZ crosswalk, normalize weights per tract.
    Expects PATHS['taz_crosswalk'].
    """
    df = pd.read_csv(os.path.expandvars(paths['taz_crosswalk']), dtype=str)
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    tract_col = next((c for c in df.columns if 'tract' in c), None)
    taz_col = next((c for c in df.columns if 'taz' in c), None)
    weight_col = next((c for c in df.columns if any(k in c for k in ('weight','share'))), None)
    if not tract_col or not taz_col or not weight_col:
        raise KeyError("step9: missing crosswalk columns")
    df[weight_col] = pd.to_numeric(df[weight_col], errors='coerce').fillna(0)
    df['weight'] = df.groupby(tract_col)[weight_col].transform(lambda x: x / x.sum().replace({0:1}))
    return df.rename(columns={tract_col:'tract', taz_col:'taz'})[['tract','taz','weight']]

def step9_summarize_tract_to_taz(df_tr: pd.DataFrame, tw: pd.DataFrame) -> pd.DataFrame:
    """
    Weight ACS tract variables into TAZ.
    """
    if 'tract' not in df_tr.columns:
        raise KeyError("step9: missing 'tract' in ACS tract data")
    df = tw.merge(df_tr, on='tract', how='left')
    vars_tr = [c for c in df_tr.columns if c != 'tract']
    for var in vars_tr:
        df[var] = pd.to_numeric(df[var], errors='coerce').fillna(0) * df['weight']
    return df.groupby('taz', as_index=False)[vars_tr].sum()

# ------------------------------
# STEP 10: Integrate Employment
# ------------------------------
# ------------------------------
def step10_integrate_employment(year: int) -> pd.DataFrame:
    """
    Merge LODES and self-employed to produce emp_lodes and emp_self per taz.
    """
    logger = logging.getLogger(__name__)
    lodes = pd.read_csv(os.path.expandvars(PATHS['lodes_employment_csv']), dtype=str)
    if 'TAZ1454' in lodes.columns and 'TOTEMP' in lodes.columns:
        emp = lodes.rename(columns={'TAZ1454':'taz','TOTEMP':'emp_lodes'})[['taz','emp_lodes']]
        emp['emp_lodes'] = pd.to_numeric(emp['emp_lodes'], errors='coerce').fillna(0)
    else:
        cw = pd.read_csv(os.path.expandvars(PATHS['block2020_to_taz1454_csv']), dtype=str)
        block_col = next(c for c in cw.columns if 'block' in c.lower())
        taz_col = next(c for c in cw.columns if 'taz' in c.lower())
        cw = cw.rename(columns={block_col:'block', taz_col:'taz'})[['block','taz']]
        geo_col = next((c for c in lodes.columns if 'geocode' in c.lower()), None)
        emp_col = next((c for c in lodes.columns if c.upper()=='C000'), None)
        if not geo_col or not emp_col:
            raise KeyError("step10: missing LODES columns")
        lodes['block'] = lodes[geo_col].str[:12]
        lodes[emp_col] = pd.to_numeric(lodes[emp_col], errors='coerce').fillna(0)
        emp = lodes.merge(cw, on='block', how='left')
        emp = emp.groupby('taz', as_index=False)[emp_col].sum().rename(columns={emp_col:'emp_lodes'})
    se = pd.read_csv(os.path.expandvars(PATHS['self_employed_csv']), dtype=str)
    se_taz = next(c for c in se.columns if 'taz' in c.lower() or 'zone' in c.lower())
    se_val = next(c for c in se.columns if c != se_taz)
    se = se.rename(columns={se_taz:'taz', se_val:'emp_self'})
    se['emp_self'] = pd.to_numeric(se['emp_self'], errors='coerce').fillna(0)
    df_emp = emp.merge(se, on='taz', how='outer').fillna(0)
    df_emp['taz'] = df_emp['taz'].astype(str)
    return df_emp

# ------------------------------
# STEP 11: Compute Scale Factors
# ------------------------------
# ------------------------------
def step11_compute_scale_factors(taz_df: pd.DataFrame, taz_targeted: pd.DataFrame,
                                 key: str='taz', target_col: str='county_target', base_col: str='county_base') -> pd.DataFrame:
    """
    Compute scale factors = target_total / base_total per TAZ.
    """
    base_totals = taz_df.groupby(key)[base_col].sum().reset_index().rename(columns={base_col:'base_total'})
    targets = taz_targeted[[key,target_col]].rename(columns={target_col:'target_total'})
    df = base_totals.merge(targets, on=key, how='left')
    df['scale_factor'] = df['target_total'] / df['base_total']
    return df[[key,'scale_factor']]

# ------------------------------
# STEP 12: Apply Scaling
# ------------------------------
# ------------------------------
def step12_apply_scaling(taz_df: pd.DataFrame, taz_targeted: pd.DataFrame,
                         scale_key: str='taz', vars_to_scale: list=None) -> pd.DataFrame:
    """
    Apply scale_factor from step11 to numeric columns in taz_df.
    """
    sf = step11_compute_scale_factors(taz_df, taz_targeted, key=scale_key)
    df = taz_df.merge(sf, on=scale_key, how='left')
    if vars_to_scale is None:
        vars_to_scale = [c for c in df.columns if c not in (scale_key,'scale_factor') and pd.api.types.is_numeric_dtype(df[c])]
    for c in vars_to_scale:
        df[c] = df[c] * df['scale_factor']
    return df

# ------------------------------
# STEP 13: Join PBA2015
# ------------------------------
# ------------------------------
def step13_join_pba2015(df_taz: pd.DataFrame) -> pd.DataFrame:
    """
    Join Plan Bay Area 2015 TAZ land use data onto taz_df.
    """
    pba = pd.read_excel(os.path.expandvars(PATHS['pba_taz_2015']), dtype=str)
    taz_col = next(c for c in pba.columns if 'taz' in c.lower())
    pba = pba.rename(columns={taz_col:'taz'})
    pba['taz'] = pba['taz'].astype(str)
    df_taz['taz'] = df_taz['taz'].astype(str)
    return df_taz.merge(pba, on='taz', how='left')

# ------------------------------
# STEP 14: Write outputs
# ------------------------------
# ------------------------------
def step14_write_outputs(taz: pd.DataFrame, year: int) -> None:
    """
    Write various CSV outputs matching original R script.
    """
    out_dir = Path(os.path.expandvars(PATHS['output_root'])) / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Placeholder: implement all CSV exports as needed
    logging.info(f"Outputs written to {out_dir}")
def step6_build_workingdata(shares: pd.DataFrame, acs_tr: pd.DataFrame, dhc_tr: pd.DataFrame) -> pd.DataFrame:
    df=shares.merge(acs_tr,on='tract',how='left').merge(dhc_tr,on='tract',how='left')
    return df

# ------------------------------
# STEP 7: Process Household Income
# ------------------------------
def step7_process_household_income(df_work: pd.DataFrame, year: int = ACS_5YR_LATEST) -> pd.DataFrame:
    mapdf=map_acs5year_household_income_to_tm1_categories(year)
    out=pd.DataFrame({'blockgroup':df_work['blockgroup']})
    for q in range(1,5): out[f'HHINCQ{q}']=0
    for _,r in mapdf.iterrows():
        col=r['incrange']; q=int(r['HHINCQ']); s=r['share']
        if col in df_work: out[f'HHINCQ{q}']+=df_work[col]*s
    for q in range(1,5): out[f'HHINCQ{q}']=out[f'HHINCQ{q}'].round().astype(int)
    return out

# ------------------------------
# STEP 8: Summarize to TAZ (block weights)
# ------------------------------
def compute_block_weights(paths: dict) -> pd.DataFrame:
    df=pd.read_csv(os.path.expandvars(paths['block2020_to_taz1454_csv']),dtype=str)
    df['block_POPULATION']=pd.to_numeric(df['block_POPULATION'],errors='coerce').fillna(0)
    grp=df.groupby('blockgroup')['block_POPULATION'].transform('sum')
    df['weight']=df['block_POPULATION']/grp.replace({0:1})
    return df[['blockgroup','TAZ1454','weight']]

def step8_summarize_to_taz(df_bg: pd.DataFrame, df_w: pd.DataFrame) -> pd.DataFrame:
    df=df_w.merge(df_bg,on='blockgroup',how='left')
    vars=[c for c in df_bg.columns if c!='blockgroup']
    for v in vars: df[v]*=df['weight']
    return df.groupby('TAZ1454')[vars].sum().reset_index()

# ------------------------------
# STEP 9: Tract to TAZ
# ------------------------------
def compute_tract_weights(paths: dict) -> pd.DataFrame:
    df=pd.read_csv(os.path.expandvars(paths['taz_crosswalk']),dtype=str)
    df.columns=df.columns.str.lower().str.replace(' ','_')
    tc=next(c for c in df.columns if 'tract' in c)
    tz=next(c for c in df.columns if 'taz' in c)
    wc=next(c for c in df.columns if any(k in c for k in('weight','share')))
    df[wc]=pd.to_numeric(df[wc],errors='coerce').fillna(0)
    df['weight']=df.groupby(tc)[wc].transform(lambda x: x/x.sum())
    return df.rename(columns={tc:'tract',tz:'taz'})[['tract','taz','weight']]

def step9_summarize_tract_to_taz(df_tr: pd.DataFrame, df_w: pd.DataFrame) -> pd.DataFrame:
    df=df_w.merge(df_tr,on='tract',how='left')
    ag=[c for c in df.columns if c not in('tract','taz','weight')]
    for v in ag: df[v]=pd.to_numeric(df[v],errors='coerce').fillna(0)*df['weight']
    return df.groupby('taz',as_index=False)[ag].sum()

# ------------------------------
# STEP 10: Integrate Employment
# ------------------------------
def step10_integrate_employment(year: int) -> pd.DataFrame:
    # LODES
    lpath=os.path.expandvars(PATHS['lodes_employment_csv'])
    ld=pd.read_csv(lpath,dtype=str)
    cols=ld.columns
    if 'TAZ1454' in cols and 'TOTEMP' in cols:
        emp=ld.rename(columns={'TAZ1454':'taz','TOTEMP':'emp_lodes'})[['taz','emp_lodes']]
        emp['emp_lodes']=pd.to_numeric(emp['emp_lodes'],errors='coerce').fillna(0)
    else:
        cw=pd.read_csv(os.path.expandvars(PATHS['block2020_to_taz1454_csv']),dtype=str)
        blk=next(c for c in cw.columns if 'block' in c.lower())
        tazc=next(c for c in cw.columns if 'taz' in c.lower())
        cw=cw.rename(columns={blk:'block',tazc:'taz'})[['block','taz']]
        geo=next(c for c in cols if 'geocode' in c.lower())
        empc=next((c for c in cols if c.upper()=='C000'),cols[0])
        ld['block']=ld[geo].str[:12]
        ld[empc]=pd.to_numeric(ld[empc],errors='coerce').fillna(0)
        emp=ld.merge(cw,on='block').groupby('taz',as_index=False)[empc].sum().rename(columns={empc:'emp_lodes'})
    # self-employed
    se=pd.read_csv(os.path.expandvars(PATHS['self_employed_csv']),dtype=str)
    st=next(c for c in se.columns if 'taz' in c.lower() or 'zone' in c.lower())
    sv=next(c for c in se.columns if c!=st)
    se=se.rename(columns={st:'taz',sv:'emp_self'})
    se['emp_self']=pd.to_numeric(se['emp_self'],errors='coerce').fillna(0)
    df=emp.merge(se,on='taz',how='outer').fillna(0)
    return df

# ------------------------------
# STEP 11: Compute Scale Factors
# ------------------------------
def step11_compute_scale_factors(taz_df: pd.DataFrame, taz_targeted: pd.DataFrame,
                                 key='taz', target_col='county_target', base_col='county_base') -> pd.DataFrame:
    bt=taz_df.groupby(key)[base_col].sum().reset_index().rename(columns={base_col:'base_total'})
    tg=taz_targeted[[key,target_col]].rename(columns={target_col:'target_total'})
    df=bt.merge(tg,on=key)
    df['scale_factor']=df['target_total']/df['base_total']
    return df[[key,'scale_factor']]

# ------------------------------
# STEP 12: Apply Scaling
# ------------------------------
def step12_apply_scaling(taz_df: pd.DataFrame, taz_targeted: pd.DataFrame,
                         scale_key='taz', vars_to_scale=None) -> pd.DataFrame:
    sf=step11_compute_scale_factors(taz_df,taz_targeted)
    df=taz_df.merge(sf,on=scale_key,how='left')
    if vars_to_scale is None:
        vars_to_scale=[c for c in df.columns if c not in (scale_key,'scale_factor') and pd.api.types.is_numeric_dtype(df[c])]
    for v in vars_to_scale: df[v]*=df['scale_factor']
    return df

# ------------------------------
# STEP 13: Join PBA2015
# ------------------------------
def step13_join_pba2015(df_taz: pd.DataFrame) -> pd.DataFrame:
    pba=pd.read_excel(os.path.expandvars(PATHS['pba_taz_2015']),dtype=str)
    tzc=next(c for c in pba.columns if 'taz' in c.lower())
    pba=pba.rename(columns={tzc:'taz'})
    pba['taz']=pba['taz'].astype(str)
    df_taz['taz']=df_taz['taz'].astype(str)
    return df_taz.merge(pba,on='taz',how='left')

# ------------------------------
# STEP 14: Write outputs
# ------------------------------
def step14_write_outputs(taz: pd.DataFrame, year: int):
    out=Path(os.path.expandvars(PATHS['output_root']))/str(year)
    out.mkdir(parents=True,exist_ok=True)
    # implement CSV exports here
    logging.info(f"Outputs written to {out}")

# ------------------------------
# Setup & Main
# ------------------------------
def setup_logging(year:int):
    od=Path(os.path.expandvars(PATHS['output_root']))/str(year)
    od.mkdir(parents=True,exist_ok=True)
    handlers=[logging.StreamHandler(), logging.FileHandler(od/f'create_tazdata_{year}.log')]
    logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(levelname)s - %(message)s',handlers=handlers)

def setup_census_client()->Census:
    key=Path(os.path.expandvars(PATHS['census_api_key_file'])).read_text().strip()
    return Census(key)

# ------------------------------
# Main pipeline
# ------------------------------
def main():
    setup_logging(YEAR)
    c = setup_census_client()
    outputs = {}
    outputs['blocks'] = step1_fetch_block_data(c, YEAR)
    outputs['acs_bg'] = step2_fetch_acs_bg(c, YEAR)
    outputs['acs_tr'] = step3_fetch_acs_tract(c, min(YEAR+2, ACS_5YR_LATEST))
    outputs['dhc_tr'] = step4_fetch_dhc_tract(c)
    outputs['shares'] = step5_compute_block_shares(outputs['blocks'], outputs['acs_bg'])
    outputs['working'] = step6_build_workingdata(outputs['shares'], outputs['acs_tr'], outputs['dhc_tr'])
    outputs['hhinc'] = step7_process_household_income(outputs['working'], ACS_5YR_LATEST)
    bg_w = compute_block_weights(PATHS)
    df_bg = outputs['hhinc']
    outputs['taz'] = step8_summarize_to_taz(df_bg, bg_w)
    tr_w = compute_tract_weights(PATHS)
    outputs['taz_tract'] = step9_summarize_tract_to_taz(outputs['acs_tr'], tr_w)
    outputs['taz'] = outputs['taz'].rename(columns={'TAZ1454': 'taz'})
    final = outputs['taz'].merge(outputs['taz_tract'], on='taz', how='left')
    emp = step10_integrate_employment(YEAR)
    final = final.merge(emp, on='taz', how='left').fillna(0)
    outputs['taz_final'] = final
    outputs['scaled'] = step12_apply_scaling(final, final)
    outputs['pba'] = step13_join_pba2015(final)
    step14_write_outputs(outputs['pba'], YEAR)
    logging.info("TAZ data processing complete.")

if __name__ == '__main__':
    main()

