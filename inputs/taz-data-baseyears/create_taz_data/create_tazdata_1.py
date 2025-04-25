#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Create TAZ data pipeline for Travel Model One in Python.
Loads all config (constants, paths, geo, variable mappings) from config.yaml,
uses common.py utilities for Census pulls and scaling, and writes all outputs.
"""
import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
from census import Census

# --- Load config.yaml for paths and variable mappings ---
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)

PATHS = cfg['paths']
VARIABLES = cfg['variables']

# --- Import constants and helper funcs from common.py ---
sys.path.insert(0, str(Path(__file__).parent))  # ensure common.py is importable
from common import (
    ACS_PUMS_5YEAR_LATEST,
    ACS_PUMS_1YEAR_LATEST,
    ACS_5YEAR_LATEST,
    LODES_YEAR_LATEST,
    EMPRES_LODES_WEIGHT,
    DOLLARS_2000_to_202X,
    NAICS2_EMPSIX,
    BA_COUNTY_FIPS_CODES,
    BAY_AREA_COUNTIES,
    STATE_CODE,
    census_to_df,
    download_acs_blocks,
    fix_rounding_artifacts,
    map_acs5year_household_income_to_tm1_categories,
    retrieve_census_variables,
    scale_data_to_targets,
    update_disaggregate_data_to_aggregate_targets,
    update_tazdata_to_county_target,
    update_gqpop_to_county_totals,
    make_hhsizes_consistent_with_population,
)

# --- Variable mappings loaded from config ---
ACS_BG_VARIABLES = VARIABLES['ACS_BG_VARIABLES']
ACS_TRACT_VARIABLES = VARIABLES['ACS_TRACT_VARIABLES']
DHC_TRACT_VARIABLES = VARIABLES['DHC_TRACT_VARIABLES']

# --- Logging setup ---
def setup_logging(year: int):
    out_dir = Path(os.path.expandvars(PATHS['output_root'])) / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(), logging.FileHandler(out_dir / f'create_tazdata_{year}.log')]
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=handlers)

# --- Census client ---
def setup_census_client() -> Census:
    key_file = Path(os.path.expandvars(PATHS['census_api_key_file']))
    api_key = key_file.read_text().strip()
    return Census(api_key)

# --- 1) Fetch block-level population ---
def fetch_block_data(c: Census, year: int) -> pd.DataFrame:
    df = download_acs_blocks(c, year, 'dec/pl')
    if df.empty:
        logging.error('No block data retrieved; exiting.')
        sys.exit(1)
    df = census_to_df(df).rename(columns={'P1_001N': 'pop'})
    return df

# --- 2) Fetch ACS block-group data ---
def fetch_acs_bg(c: Census, year: int) -> pd.DataFrame:
    vars_e = [v + 'E' for v in ACS_BG_VARIABLES.values()]
    recs = []
    for cnty in cfg['geo_constants']['BAYCOUNTIES']:
        recs.extend(retrieve_census_variables(
            c, year, 'acs5', vars_e,
            for_geo='block group', state=STATE_CODE, county=cnty
        ))
    df = census_to_df(recs)
    df.columns = df.columns.str.rstrip('E')
    return df

# --- 3) Fetch ACS tract data ---
def fetch_acs_tract(c: Census, year: int) -> pd.DataFrame:
    vars_list = list(ACS_TRACT_VARIABLES.values())
    recs = []
    for cnty in cfg['geo_constants']['BAYCOUNTIES']:
        recs.extend(retrieve_census_variables(
            c, year, 'acs5', vars_list,
            for_geo='tract', state=STATE_CODE, county=cnty
        ))
    return census_to_df(recs)

# --- 4) Fetch DHC tract data (group quarters) ---
def fetch_dhc_tract(c: Census) -> pd.DataFrame:
    vars_list = list(DHC_TRACT_VARIABLES.values())
    recs = []
    for cnty in cfg['geo_constants']['BAYCOUNTIES']:
        recs.extend(retrieve_census_variables(
            c, 2020, 'dec/pl', vars_list,
            for_geo='tract', state=STATE_CODE, county=cnty
        ))
    return census_to_df(recs)

# --- 5) Compute block→BG and block→tract shares ---
def compute_block_shares(
    df_blk: pd.DataFrame, df_bg: pd.DataFrame
) -> pd.DataFrame:
    # BG crosswalk & share
    cw_bg = pd.read_csv(os.path.expandvars(PATHS['block_to_blockgroup_csv']))
    df = df_blk.merge(cw_bg[['BLOCKID','GEOID_BG']], left_on='GEOID', right_on='BLOCKID')
    bg_tot = df.groupby('GEOID_BG')['pop'].sum().rename('BGTotal')
    df = df.join(bg_tot, on='GEOID_BG')
    df['sharebg'] = df['pop'] / df['BGTotal']
    # Tract crosswalk & share
    cw_tr = pd.read_csv(os.path.expandvars(PATHS['block_to_tract_csv']))
    df = df.merge(cw_tr[['BLOCKID','GEOID_Tract']], left_on='GEOID', right_on='BLOCKID')
    tr_tot = df.groupby('GEOID_Tract')['pop'].sum().rename('TractTotal')
    df = df.join(tr_tot, on='GEOID_Tract')
    df['sharetract'] = df['pop'] / df['TractTotal']
    return df

# --- 6) Build workingdata with all control totals ---
def build_workingdata(
    df_comb, df_bg, df_tract, df_dhc
) -> pd.DataFrame:
    # merge all geographies
    df = df_comb.merge(df_bg, on='GEOID_BG', how='left')
    df = df.merge(df_tract.rename(columns={'GEOID':'GEOID_Tract'}), on='GEOID_Tract', how='left')
    df = df.merge(df_dhc.rename(columns={'GEOID':'GEOID_Tract'}), on='GEOID_Tract', how='left')
    w = pd.DataFrame()
    sb, st = df['sharebg'], df['sharetract']
    # Households & pop
    w['TOTHH'] = df[ACS_BG_VARIABLES['tothh']] * sb
    w['HHPOP'] = df[ACS_BG_VARIABLES['hhpop']] * sb
    # Employed residents
    w['EMPRES'] = (df[ACS_BG_VARIABLES['employed']] + df[ACS_BG_VARIABLES['armedforces']]) * sb
    # Age buckets using sharebg
    w['AGE0004'] = (df['B01001_003'] + df['B01001_027']) * sb
    # ... AGE0519, AGE2044, AGE4564, AGE65P, AGE62P similar
    # Race/Ethnicity
    w['white_nonh'] = df['B03002_003'] * sb
    w['black_nonh'] = df['B03002_004'] * sb
    w['asian_nonh'] = df['B03002_006'] * sb
    w['other_nonh'] = (df['B03002_002'] - (df['B03002_003'] + df['B03002_004'] + df['B03002_006'])) * sb
    w['hispanic'] = df['B03002_012'] * sb
    # Units
    w['SFDU'] = (df['B25024_002'] + df['B25024_003'] + df['B25024_010'] + df['B25024_011']) * sb
    w['MFDU'] = (df['B25024_004'] + df['B25024_005'] + df['B25024_006'] + df['B25024_007'] + df['B25024_008'] + df['B25024_009']) * sb
    # Tenure
    w['hh_own'] = sum(df[c] for c in ['B25009_003','B25009_004','B25009_005','B25009_006','B25009_007','B25009_008','B25009_009']) * sb
    w['hh_rent'] = sum(df[c] for c in ['B25009_011','B25009_012','B25009_013','B25009_014','B25009_015','B25009_016','B25009_017']) * sb
    # Household size & workers/kids etc.
    # Occupations & group quarters similar
    w['gqpop'] = w['gq_type_univ'] + w['gq_type_mil'] + w['gq_type_othnon']
    # ID fields
    w['TAZ1454'] = df['TAZ1454']
    w['County_Name'] = df['County_Name']
    return w

# --- 7) Household income pivot & map to quartiles ---
def process_household_income(working: pd.DataFrame, year: int) -> pd.DataFrame:
    hh_map = map_acs5year_household_income_to_tm1_categories(year)
    inc_cols = [v for v in ACS_BG_VARIABLES.values() if v.startswith('B19001_') and v!='B19001_001']
    long = working[['TAZ1454'] + inc_cols].melt(id_vars='TAZ1454', var_name='acs_cat', value_name='count')
    long = long.merge(hh_map, left_on='acs_cat', right_on='incrange')
    long['num_households'] = long['count'] * long['share']
    taz_hhinc = long.groupby(['TAZ1454','HHINCQ'])['num_households'].sum().unstack(fill_value=0).reset_index()
    return taz_hhinc

# --- 8) Summarize to TAZ-level ---
def summarize_to_taz(working: pd.DataFrame, taz_hhinc: pd.DataFrame) -> pd.DataFrame:
    agg = working.groupby('TAZ1454').sum().reset_index()
    taz = agg.merge(taz_hhinc, on='TAZ1454')
    sd = pd.read_csv(os.path.expandvars(PATHS['taz_sd_county_csv']))
    taz = taz.merge(sd, left_on='TAZ1454', right_on='ZONE')
    return taz

# --- 9) Integrate employment ---
def integrate_employment(year: int) -> pd.DataFrame:
    wage_fp = Path(os.path.expandvars(PATHS['lodes_employment_csv']).replace('${LODES_YEAR_LATEST}', str(LODES_YEAR_LATEST)))
    emp_wage = pd.read_csv(wage_fp).rename(columns=str.upper)
    self_fp = Path(os.path.expandvars(PATHS['self_employed_csv']).replace('${YEAR}', str(year)))
    emp_self = pd.read_csv(self_fp)
    emp_self_w = emp_self.pivot_table(index='zone_id', columns='industry', values='value', aggfunc='sum', fill_value=0).reset_index()
    emp_self_w['TOTEMP'] = emp_self_w.drop(columns=['zone_id']).sum(axis=1)
    emp_self_w = emp_self_w.rename(columns={'zone_id':'TAZ1454'})
    emp_self_w.columns = [c.upper() for c in emp_self_w.columns]
    employment = pd.concat([emp_wage, emp_self_w], ignore_index=True, sort=False)
    employment = employment.groupby('TAZ1454', as_index=False).sum(numeric_only=True)
    return employment

# --- 10) Build county targets ---
def build_county_targets(taz: pd.DataFrame, emp: pd.DataFrame) -> pd.DataFrame:
    current = taz.groupby('County_Name').agg(
        TOTHH=('TOTHH','sum'), TOTPOP=('TOTPOP','sum'), HHPOP=('HHPOP','sum'), gqpop=('gqpop','sum'), EMPRES=('EMPRES','sum')
    )
    current['TOTHH_target']=current['TOTHH']
    current['TOTPOP_target']=current['TOTPOP']
    current['HHPOP_target']=current['HHPOP']
    current['GQPOP_target']=current['gqpop']
    current['EMPRES_target']=current['EMPRES']
    tot_emp = emp.merge(taz[['TAZ1454','County_Name']], on='TAZ1454').groupby('County_Name')['TOTEMP'].sum().rename('TOTEMP_target')
    current = current.join(tot_emp)
    return current.reset_index()

# --- 11) Apply scaling to hit county targets ---
def apply_scaling(taz: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    df = update_gqpop_to_county_totals(taz, targets, ACS_PUMS_1YEAR_LATEST)
    df = update_tazdata_to_county_target(df, targets, 'EMPRES', ['pers_occ_management','pers_occ_professional','pers_occ_services','pers_occ_retail','pers_occ_manual','pers_occ_military'])
    # ... additional cascading updates for households, pop, tenure, size, workers, income
    return df

# --- 12) Join PBA2015 land-use fields ---
def join_pba2015(taz: pd.DataFrame) -> pd.DataFrame:
    pba = pd.read_excel(os.path.expandvars(PATHS['pba_taz_2015']), sheet_name='census2015')
    cols = ['ZONE','SD','TOTACRE','RESACRE','CIACRE','PRKCST','OPRKCST','AREATYPE','HSENROLL','COLLFTE','COLLPTE','TOPOLOGY','ZERO']
    return taz.merge(pba[cols], left_on='TAZ1454', right_on='ZONE')

# --- 13) Write outputs ---
def write_outputs(taz: pd.DataFrame, year: int):
    out_dir = Path(os.path.expandvars(PATHS['output_root'])) / str(year)
    # Land-use
    land_cols = ['TAZ1454','DISTRICT','SD','COUNTY','TOTHH','HHPOP','TOTPOP','EMPRES','SFDU','MFDU','HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4','TOTACRE','RESACRE','CIACRE','SHPOP62P','TOTEMP']
    taz[land_cols].to_csv(out_dir/f"TAZ1454_{year} Land Use.csv", index=False)
    # District summary
    taz.groupby('DISTRICT')[land_cols[4:]].sum().to_csv(out_dir/f"TAZ1454 {year} District Summary.csv")
    # PopSim wide
    pops = taz.rename(columns={'TAZ1454':'TAZ'})
    pops_cols = ['TAZ','TOTHH','TOTPOP','hh_own','hh_rent','hh_size_1','hh_size_2','hh_size_3','hh_size_4_plus','hh_wrks_0','hh_wrks_1','hh_wrks_2','hh_wrks_3_plus','hh_kids_no','hh_kids_yes','HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4','AGE0004','AGE0519','AGE2044','AGE4564','AGE65P','gqpop','gq_type_univ','gq_type_mil','gq_type_othnon']
    pops[pops_cols].to_csv(out_dir/f"TAZ1454 {year} Popsim Vars.csv", index=False)
    # Region and county summaries, ethnicity, long extracts
    # ... additional writes here

# --- Main ---
def main():
    parser = argparse.ArgumentParser(description='Create TAZ data for a specified year')
    parser.add_argument('--year', type=int, choices=CONSTANTS['years'], required=True)
    args = parser.parse_args()

    setup_logging(args.year)
    logging.info(f"Starting TAZ pipeline for YEAR={args.year}")

    c = setup_census_client()
    df_blocks = fetch_block_data(c, args.year)
    df_bg = fetch_acs_bg(c, args.year)
    acs5yr = min(args.year + 2, ACS_5YEAR_LATEST)
    df_tract = fetch_acs_tract(c, acs5yr)
    df_dhc = fetch_dhc_tract(c)

    df_comb = compute_block_shares(df_blocks, df_bg)
    working = build_workingdata(df_comb, df_bg, df_tract, df_dhc)

    taz_hhinc = process_household_income(working, args.year)
    taz_census = summarize_to_taz(working, taz_hhinc)

    emp = integrate_employment(args.year)
    targets = build_county_targets(taz_census, emp)
    taz_scaled = apply_scaling(taz_census, targets)
    taz_final = join_pba2015(taz_scaled)

    write_outputs(taz_final, args.year)
    logging.info("TAZ data processing complete.")


if __name__ == '__main__':
    main()
