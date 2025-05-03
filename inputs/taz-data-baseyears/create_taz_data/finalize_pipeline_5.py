
import os
import logging
from pathlib import Path
import pandas as pd
import yaml

# Load configuration\ nCONFIG_PATH = Path(__file__).parent / 'config.yaml'
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)
PATHS = cfg['paths']


def step13_join_pba2015(df_taz):
    """
    Join your TAZ-level outputs to the Plan Bay Area 2015 TAZ data
    (land-use/blueprint) so you can carry those attributes forward.

    Parameters
    ----------
    df_taz : pandas.DataFrame
        Must contain a 'taz' column (string or numeric).

    Returns
    -------
    pandas.DataFrame
        All columns from df_taz plus all columns from the PBA2015 file,
        merged on the TAZ identifier.
    """
    # 1) load the PBA 2015 TAZ data
    pba_path = os.path.expandvars(PATHS['pba_taz_2015'])
    df_pba  = pd.read_excel(pba_path, dtype=str)
    
    # 2) detect the TAZ column in the PBA file
    pba_cols = df_pba.columns.tolist()
    taz_col = next(c for c in pba_cols if 'taz' in c.lower())
    
    # 3) standardize the name and type
    df_pba = df_pba.rename(columns={taz_col: 'taz'})
    df_pba['taz'] = df_pba['taz'].astype(str)
    
    # 4) ensure df_taz.taz is string
    df_taz = df_taz.copy()
    df_taz['taz'] = df_taz['taz'].astype(str)
    
    # 5) merge
    df_out = df_taz.merge(df_pba, on='taz', how='left')
    
    return df_out

def step14_write_outputs(taz: pd.DataFrame, year: int) -> None:
    """
    Write out the same suite of CSVs that the original R script did,
    using the fully-joined TAZ‐level DataFrame `taz`.
    """
    # 1) Prepare output directory
    out_root = os.path.expandvars(PATHS['output_root'])
    year_dir = os.path.join(out_root, str(year))
    os.makedirs(year_dir, exist_ok=True)

    # 2) --- Ethnicity ---
    ethnic = taz[[
        'TAZ1454',
        'hispanic','white_nonh','black_nonh','asian_nonh','other_nonh',
        'TOTPOP','COUNTY','County_Name'
    ]]
    ethnic_path = os.path.join(year_dir, "TAZ1454_Ethnicity.csv")
    ethnic.to_csv(ethnic_path, index=False)
    logging.info(f"Wrote {ethnic_path}")

    # 3) --- TAZ Land Use file ---
    taz_landuse = taz.copy()
    taz_landuse['hhlds'] = taz_landuse['TOTHH']
    landuse_cols = [
        'TAZ1454','DISTRICT','SD','COUNTY','TOTHH','HHPOP','TOTPOP','EMPRES',
        'SFDU','MFDU','HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4','TOTACRE',
        'RESACRE','CIACRE','SHPOP62P','TOTEMP','AGE0004','AGE0519','AGE2044',
        'AGE4564','AGE65P','RETEMPN','FPSEMPN','HEREMPN','AGREMPN','MWTEMPN',
        'OTHEMPN','PRKCST','OPRKCST','AREATYPE','HSENROLL','COLLFTE','COLLPTE',
        'TERMINAL','TOPOLOGY','ZERO','hhlds','gqpop'
    ]
    landuse = taz_landuse[landuse_cols]
    landuse_path = os.path.join(year_dir, f"TAZ1454_{year}_Land Use.csv")
    landuse.to_csv(landuse_path, index=False, quotechar='"')
    logging.info(f"Wrote {landuse_path}")

    # 4) --- District summary for 2015 (from PBA2015 sheet) ---
    pba = pd.read_excel(
        os.path.expandvars(PATHS['pba_taz_2015']),
        sheet_name="census2015",
        dtype=str
    )
    num_vars = [
        'TOTHH','HHPOP','TOTPOP','EMPRES','SFDU','MFDU',
        'HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4','TOTEMP',
        'AGE0004','AGE0519','AGE2044','AGE4564','AGE65P',
        'RETEMPN','FPSEMPN','HEREMPN','AGREMPN','MWTEMPN',
        'OTHEMPN','HSENROLL','COLLFTE','COLLPTE'
    ]
    for v in num_vars:
        pba[v] = pd.to_numeric(pba[v], errors='coerce').fillna(0)
    pba['gqpop'] = pba['TOTPOP'] - pba['HHPOP']
    summary_2015 = (
        pba
        .groupby('DISTRICT', as_index=False)[ num_vars + ['TOTPOP','gqpop'] ]
        .sum()
    )
    path_2015 = os.path.join(year_dir, f"TAZ1454_2015_District Summary.csv")
    summary_2015.to_csv(path_2015, index=False, quotechar='"')
    logging.info(f"Wrote {path_2015}")

    # 5) --- District summary for target year ---
    # re‐use our taz_landuse table as the “census” base
    df = taz_landuse.copy()
    for v in num_vars + ['gqpop']:
        df[v] = pd.to_numeric(df[v], errors='coerce').fillna(0)
    summary_year = (
        df
        .groupby('DISTRICT', as_index=False)[ num_vars + ['TOTPOP','gqpop'] ]
        .sum()
    )
    path_year = os.path.join(year_dir, f"TAZ1454_{year}_District Summary.csv")
    summary_year.to_csv(path_year, index=False, quotechar='"')
    logging.info(f"Wrote {path_year}")

    # 6) --- Popsim Vars ---
    pops = taz.rename(columns={'TAZ1454':'TAZ','gqpop':'gq_tot_pop'})[[
        'TAZ','TOTHH','TOTPOP','hh_own','hh_rent',
        'hh_size_1','hh_size_2','hh_size_3','hh_size_4_plus',
        'hh_wrks_0','hh_wrks_1','hh_wrks_2','hh_wrks_3_plus',
        'hh_kids_no','hh_kids_yes',
        'HHINCQ1','HHINCQ2','HHINCQ3','HHINCQ4',
        'AGE0004','AGE0519','AGE2044','AGE4564','AGE65P',
        'gq_tot_pop','gq_type_univ','gq_type_mil','gq_type_othnon'
    ]]
    pops_path = os.path.join(year_dir, f"TAZ1454_{year}_Popsim Vars.csv")
    pops.to_csv(pops_path, index=False, quotechar='"')
    logging.info(f"Wrote {pops_path}")

    # 7) --- Region‐level Popsim Vars ---
    region = pops.copy()
    region['REGION'] = 1
    region_sum = region.groupby('REGION', as_index=False)[ 'gq_tot_pop' ].sum()
    region_path = os.path.join(year_dir, f"TAZ1454_{year}_Popsim Vars Region.csv")
    region_sum.rename(columns={'gq_tot_pop':'gq_num_hh_region'}) \
              .to_csv(region_path, index=False, quotechar='"')
    logging.info(f"Wrote {region_path}")

    # 8) --- County‐level Popsim Vars ---
    county_pop = pops.rename(columns={'TAZ':'ignored'}) \
        .groupby('COUNTY', as_index=False).agg({
            'gq_type_univ':'sum','gq_type_mil':'sum','gq_type_othnon':'sum'
        })
    # you can expand with any other pers_occ_... sums here
    county_path = os.path.join(year_dir, f"TAZ1454_{year}_Popsim Vars County.csv")
    county_pop.to_csv(county_path, index=False, quotechar='"')
    logging.info(f"Wrote {county_path}")

    # 9) --- Tableau‐friendly long for 2015 ---
    # we'll need your TAZ→SD→County_Name→DISTRICT_NAME crosswalk
    xw = pd.read_csv(os.path.expandvars(PATHS['taz_sd_county_csv']), dtype=str)
    xw = xw.rename(columns=lambda c: c.strip()).loc[:, ['ZONE','County_Name','DISTRICT_NAME']]
    pba_long = (
        pba
        .assign(gqpop=lambda df: df['TOTPOP'] - df['HHPOP'], Year=2015)
        .merge(xw, on='ZONE', how='left')
        .melt(
            id_vars=['ZONE','DISTRICT','DISTRICT_NAME','COUNTY','County_Name','Year'],
            value_vars=num_vars + ['SHPOP62P','TOTEMP','AGE0004','AGE0519','AGE2044','AGE4564','AGE65P','RETEMPN','FPSEMPN','HEREMPN','AGREMPN','MWTEMPN','OTHEMPN','PRKCST','OPRKCST','HSENROLL','COLLFTE','COLLPTE','gqpop'],
            var_name='Variable',
            value_name='Value'
        )
    )
    long15_path = os.path.join(year_dir, f"TAZ1454_2015_long.csv")
    pba_long.to_csv(long15_path, index=False, quotechar='"')
    logging.info(f"Wrote {long15_path}")

    # 10) --- Tableau‐friendly long for target year ---
    census_long = (
        taz
        .assign(Year=year)
        .melt(
            id_vars=['TAZ1454','DISTRICT','DISTRICT_NAME','COUNTY','County_Name','Year'],
            value_vars=num_vars + ['SHPOP62P','TOTEMP','AGE0004','AGE0519','AGE2044','AGE4564','AGE65P','RETEMPN','FPSEMPN','HEREMPN','AGREMPN','MWTEMPN','OTHEMPN','PRKCST','OPRKCST','HSENROLL','COLLFTE','COLLPTE','gqpop'],
            var_name='Variable',
            value_name='Value'
        )
    )
    longyr_path = os.path.join(year_dir, f"TAZ1454_{year}_long.csv")
    census_long.to_csv(longyr_path, index=False, quotechar='"')
    logging.info(f"Wrote {longyr_path}")

""" 
    if __name__ == '__main__':
        logging.basicConfig(level=logging.INFO)
        # Assume `taz` DataFrame is provided (e.g., from previous pipeline)
        taz = pd.DataFrame()
        year = CONSTANTS['years'][0]
        df = step13_join_pba2015(taz)
        step14_write_outputs(df, year)
        print('Finalize pipeline executed') """
