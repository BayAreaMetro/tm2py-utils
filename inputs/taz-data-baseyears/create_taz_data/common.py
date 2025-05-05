import logging
import pandas as pd
import numpy as np
import os
import yaml
from typing import List, Dict, Tuple, Union, Optional

# Load configuration from config.yaml
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')
with open(CONFIG_PATH, 'r') as cfg_file:
    cfg = yaml.safe_load(cfg_file)
# Constants loaded from config
CONSTANTS = cfg.get('constants', {})
ACS_PUMS_5YEAR_LATEST = CONSTANTS.get('ACS_PUMS_5YEAR_LATEST')
ACS_PUMS_1YEAR_LATEST = CONSTANTS.get('ACS_PUMS_1YEAR_LATEST')
ACS_5YEAR_LATEST = CONSTANTS.get('ACS_5YEAR_LATEST')
LODES_YEAR_LATEST = CONSTANTS.get('LODES_YEAR_LATEST')
EMPRES_LODES_WEIGHT = CONSTANTS.get('EMPRES_LODES_WEIGHT')
DOLLARS_2000_to_202X = CONSTANTS.get('DOLLARS_2000_to_202X', {})
NAICS2_EMPSIX = CONSTANTS.get('NAICS2_EMPSIX', {})

# Geo constants
GEO_CONSTANTS = cfg.get('geo_constants', {})
BA_COUNTY_FIPS_CODES = GEO_CONSTANTS.get('BA_COUNTY_FIPS_CODES')
BAY_AREA_COUNTIES = GEO_CONSTANTS.get('BAY_AREA_COUNTIES')
STATE_CODE = GEO_CONSTANTS.get('STATE_CODE')

def retrieve_census_variables(
    c, year, dataset, variables,
    for_geo='block', in_geo=None,
    for_geo_id=None, state=None, county=None
):
    """
    Retrieve data from Census API, logging the exact URL.
    """
    # Build geo dict
    geo = {}
    if for_geo:
        geo['for'] = f"{for_geo}:*"
    if for_geo_id:
        geo['for'] = f"{for_geo}:{for_geo_id}"
    if in_geo:
        geo['in'] = f"{in_geo}:*"
    if state:
        geo['in'] = f"state:{state}"
    if county:
        geo['in'] = geo.get('in', '') + f"+county:{county}"

    try:
        # Map dataset name to valid attribute (e.g. 'dec/pl' -> 'dec_pl')
        ds_attr = dataset.split('/')[-1]
        api = getattr(c, ds_attr)
        
        # Build and log the full URL + query string
        base = f"https://api.census.gov/data/{year}/{dataset}"
        params = {
            'get': ','.join(variables),
            'for': geo.get('for', ''),
            'in': geo.get('in', '')
        }
        param_str = '&'.join(f"{k}={v}" for k, v in params.items() if v)
        logging.info(f"CALLING URL: {base}?{param_str}")

        # Execute the request
        response = api.get(variables, geo=geo, year=year)
        logging.info(f"Retrieved {len(response)} records")
        return response

    except Exception as e:
        # Log the error with URL and parameters
        logging.error(f"Error retrieving Census data: {e}")
        logging.error(f"URL: {base}?{param_str}")
        logging.error(f"Parameters: {params}")
        if 'bad request' in str(e).lower():
            logging.error(f"Variables: {variables}")
            logging.error(f"Geo: {geo}")
        return []


def census_to_df(response, geo_col='GEOID'):
    """
    Convert Census API response to pandas DataFrame and create GEOID.

    Parameters:
        response: list of dicts or pandas.DataFrame returned from Census API
        geo_col: name for generated geography ID column
    Returns:
        pandas.DataFrame with data and a GEOID column
    """
    # Handle empty response
    if response is None or len(response) == 0:
        return pd.DataFrame()

    # If already a DataFrame, ensure GEOID exists
    if isinstance(response, pd.DataFrame):
        df = response.copy()
    else:
        df = pd.DataFrame(response)

    # Create GEOID for block-level
    if {'state','county','block'}.issubset(df.columns):
        df[geo_col] = (
            df['state'].astype(str) +
            df['county'].astype(str) +
            df['block'].astype(str)
        )
    # Otherwise, for tract-level
    elif {'state','county','tract'}.issubset(df.columns):
        df[geo_col] = (
            df['state'].astype(str) +
            df['county'].astype(str) +
            df['tract'].astype(str)
        )
    # If GEOID already present, leave it

    # Remove 'E' suffix from estimate columns
    rename_cols = {col: col[:-1] for col in df.columns if col.endswith('E')}
    df = df.rename(columns=rename_cols)

    # Convert numeric columns except geography
    geo_fields = {'NAME','state','county','tract','block','block group', geo_col}
    for col in df.columns:
        if col not in geo_fields:
            df[col] = pd.to_numeric(df[col], errors='ignore')

    return df



def download_acs_blocks(
    c,
    year: int,
    dataset: str,
    states: Optional[List[str]] = None,
    counties: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Download block‐level population data.
    
    If dataset == 'dec/pl', this uses the 2020 PL data (only available for 2020).
    Otherwise it uses the passed-in year for ACS calls.
    """
    # Decennial PL is only available for 2020
    call_year = 2020 if dataset.lower() == 'dec/pl' else year

    # Default to all Bay Area counties
    if states is None:
        states = list(set(BA_COUNTY_FIPS_CODES.values()))

    all_blocks = []

    for st in states:
        if counties is not None:
            state_counties = counties
        else:
            state_counties = [
                cnty
                for cnty, s in BA_COUNTY_FIPS_CODES.items()
                if s == st
            ]

        for cnty in state_counties:
            blocks = retrieve_census_variables(
                c,
                call_year,
                dataset,
                ['P1_001N'],      # total population
                for_geo='block',
                state=st,
                county=cnty
            )
            all_blocks.extend(blocks)

    df = pd.DataFrame(all_blocks)
    if df.empty:
        logging.warning("No block data retrieved")
        return pd.DataFrame()

    return df


def fix_rounding_artifacts(df, id_var, sum_var, partial_vars, logging_on=True):
    """
    Fix rounding artifacts by adjusting partial variable values to match the sum variable.
    """
    df_copy = df.copy()
    for idx, row in df_copy.iterrows():
        partial_sum = sum(row[var] for var in partial_vars)
        target_sum = row[sum_var]
        discrepancy = target_sum - partial_sum
        if discrepancy != 0:
            if logging_on:
                logging.info(f"Fixing rounding artifact for {id_var}={row[id_var]}: {sum_var}={target_sum} but partial sum={partial_sum} (discrepancy={discrepancy})")
            # Small discrepancy
            if abs(discrepancy) <= len(partial_vars):
                if discrepancy > 0:
                    sorted_vars = sorted(partial_vars, key=lambda x: row[x], reverse=True)
                    for var in sorted_vars[:discrepancy]:
                        df_copy.at[idx, var] += 1
                else:
                    sorted_vars = [var for var in sorted(partial_vars, key=lambda x: row[x]) if row[var] > 0]
                    for var in sorted_vars[:abs(discrepancy)]:
                        df_copy.at[idx, var] -= 1
            else:
                proportions = {var: (row[var] / partial_sum) if partial_sum > 0 else (1.0 / len(partial_vars)) for var in partial_vars}
                remaining = discrepancy
                for var in partial_vars[:-1]:
                    adjustment = int(discrepancy * proportions[var])
                    df_copy.at[idx, var] += adjustment
                    remaining -= adjustment
                df_copy.at[idx, partial_vars[-1]] += remaining
    return df_copy


def scale_data_to_targets(source_df, target_df, id_var, sum_var, partial_vars, logging_on=False):
    """
    Scale data in source_df to match targets in target_df.
    """
    result_df = source_df.copy()
    target_col = f"{sum_var}_target"
    merged = pd.merge(source_df[[id_var] + partial_vars + [sum_var]], target_df[[id_var, target_col]], on=id_var)
    for _, row in merged.iterrows():
        idx = result_df[result_df[id_var] == row[id_var]].index[0]
        source_sum = row[sum_var]
        target_sum = row[target_col]
        if source_sum <= 0:
            continue
        scale_factor = target_sum / source_sum
        if logging_on:
            logging.info(f"Scaling {id_var}={row[id_var]}: {sum_var}={source_sum} to {target_col}={target_sum} (factor={scale_factor:.4f})")
        result_df.at[idx, sum_var] = target_sum
        for var in partial_vars:
            result_df.at[idx, var] = round(row[var] * scale_factor)
    result_df = fix_rounding_artifacts(result_df, id_var, sum_var, partial_vars, logging_on)
    return result_df


def update_disaggregate_data_to_aggregate_targets(source_df, target_df, disagg_id_var, agg_id_var, col_name):
    """
    Update disaggregate data to match aggregate targets.
    """
    result_df = source_df.copy()
    current_totals = source_df.groupby(agg_id_var)[col_name].sum().reset_index()
    diff_df = pd.merge(current_totals, target_df[[agg_id_var, f"{col_name}_target"]], on=agg_id_var)
    diff_df['diff'] = diff_df[f"{col_name}_target"] - diff_df[col_name]
    for _, row in diff_df[diff_df['diff'] != 0].iterrows():
        agg_id = row[agg_id_var]
        difference = row['diff']
        disagg_units = source_df[source_df[agg_id_var] == agg_id]
        if disagg_units.empty:
            continue
        total = row[col_name]
        if total > 0:
            for idx, unit in disagg_units.iterrows():
                prop = unit[col_name] / total
                result_df.at[idx, col_name] += round(difference * prop)
        else:
            equal_adj = difference / len(disagg_units)
            for idx in disagg_units.index:
                result_df.at[idx, col_name] += equal_adj
    return result_df


def map_acs5year_household_income_to_tm1_categories(acs_year):
    """
    Map ACS 5-year household income ranges to TM1 income quartiles.
    """
    logging.info(f"Mapping ACS {acs_year} household income to TM1 categories")
    income_mapping = [
        ("B19001_002", 1, 1.0),
        ("B19001_003", 1, 1.0),
        ("B19001_004", 1, 1.0),
        ("B19001_005", 1, 1.0),
        ("B19001_006", 1, 0.7),
        ("B19001_007", 1, 0.3),
        ("B19001_007", 2, 0.7),
        ("B19001_008", 2, 1.0),
        ("B19001_009", 2, 1.0),
        ("B19001_010", 2, 1.0),
        ("B19001_011", 2, 0.8),
        ("B19001_011", 3, 0.2),
        ("B19001_012", 3, 1.0),
        ("B19001_013", 3, 1.0),
        ("B19001_014", 3, 0.2),
        ("B19001_014", 4, 0.8),
        ("B19001_015", 4, 1.0),
        ("B19001_016", 4, 1.0),
        ("B19001_017", 4, 1.0)
    ]
    return pd.DataFrame(income_mapping, columns=['incrange', 'HHINCQ', 'share'])

def update_tazdata_to_county_target(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    sum_var: str,
    partial_vars: list,
) -> pd.DataFrame:
    """
    Scale TAZ data so county-level totals match targets.

    Parameters
    ----------
    source_df : DataFrame
        TAZ-level data, must include 'County_Name', the `sum_var`, and any `partial_vars`.
    target_df : DataFrame
        County-level targets, must include 'County_Name' and a column named f'{sum_var}_target'.
    sum_var : str
        The column in source_df to match to the county total (e.g. 'TOTHH' or 'sum_age').
    partial_vars : list of str
        Columns in source_df whose totals should be scaled in the same proportion as sum_var.

    Returns
    -------
    DataFrame
        A new DataFrame in which for each county, sum_var and each partial_var
        have been multiplied by the factor = county_target / county_current.
        Rounding artifacts are corrected via fix_rounding_artifacts.
    """
    # 1) Compute current county sums of sum_var
    current = (
        source_df
        .groupby('County_Name')[sum_var]
        .sum()
        .reset_index()
    )

    # 2) Bring in the county targets
    target_col = f'{sum_var}_target'
    merged = pd.merge(
        current,
        target_df[['County_Name', target_col]],
        on='County_Name',
    )

    # 3) Calculate the scale factor for each county
    merged['scale'] = merged[target_col] / merged[sum_var]

    # 4) Apply scaling to each TAZ in the county
    result = source_df.copy()
    for _, row in merged.iterrows():
        scale = row['scale']
        # If scale is essentially 1, skip
        if abs(scale - 1) < 1e-4:
            continue

        mask = result['County_Name'] == row['County_Name']
        # Scale the sum_var and each partial_var
        result.loc[mask, sum_var] *= scale
        for var in partial_vars:
            result.loc[mask, var] *= scale

        # Round them to integers
        cols = [sum_var] + partial_vars
        result.loc[mask, cols] = result.loc[mask, cols].round(0)

        # Fix any rounding artifacts so components sum exactly
        result = fix_rounding_artifacts(
            result,
            id_var='TAZ1454',
            sum_var=sum_var,
            partial_vars=partial_vars,
        )

    return result


def update_gqpop_to_county_totals(source_df, target_df, acs1year):
    """
    Adjust group quarters population and employment to match county-level targets.
    Uses decennial DHC-based estimates and scales TAZ group quarters categories.

    Parameters
    ----------
    source_df : pd.DataFrame
        TAZ-level data, must include 'County_Name', the 'gqpop' column, and the
        detailed gq-type and age breakdown variables.
    target_df : pd.DataFrame
        County-level targets, must include 'County_Name', 'GQPOP_target', and we'll
        compute 'GQEMP_target' here.
    acs1year : int
        ACS 1-year vintage (unused directly in this function, but kept for signature
        consistency).

    Returns
    -------
    pd.DataFrame
        A new DataFrame where:
          1. The total group-quarters pop ('gqpop') is scaled so that
             sum(gqpop) by county = GQPOP_target.
          2. The age-breakdown within gqpop (AGE0004, AGE0519, AGE2044, AGE4564, AGE65P)
             is similarly scaled to match the new gqpop by county.
          3. The employed portion of gqpop ('EMPRES' across the pers_occ_* fields)
             is scaled to a new target GQEMP_target derived from decennial estimates.

    Notes
    -----
    - Uses a hard-coded set of “estimates” for each Bay Area county’s total GQ population
      and employment, purely as a reference to split GQ pop vs. employment.
    - Invokes `update_tazdata_to_county_target` three times in sequence:
        a) to scale overall gqpop by county,
        b) to scale age groups within gqpop,
        c) to scale the employed residents within gqpop.
    """
    # 1) Reference estimates of GQ pop and employment by county
    estimates = pd.DataFrame({
        'County_Name': BAY_AREA_COUNTIES,
        'gq_pop_estimate':   [8000,  4000,  1000,  800,  7000, 3000, 10000, 2000, 2000],
        'gq_emp_estimate':   [4000,  2000,   500,  400,  3500, 1500,  5000, 1000, 1000],
    })
    # Derive the share of GQ pop that is employed
    estimates['worker_share'] = estimates['gq_emp_estimate'] / estimates['gq_pop_estimate']

    # 2) Merge county targets with our reference estimates
    det = pd.merge(target_df, estimates, on='County_Name')
    # Compute a new employment target within GQ pop
    det['GQEMP_target'] = det['GQPOP_target'] * det['worker_share']

    # 3) Scale total GQ population
    df1 = update_tazdata_to_county_target(
        source_df,
        det,
        sum_var='gqpop',
        partial_vars=['gq_type_univ', 'gq_type_mil', 'gq_type_othnon']
    )

    # 4) Scale the age breakdown within GQ
    df2 = update_tazdata_to_county_target(
        df1,
        det.rename(columns={'GQPOP_target': 'gq_age_target'}),
        sum_var='gqpop',
        partial_vars=['AGE0004', 'AGE0519', 'AGE2044', 'AGE4564', 'AGE65P']
    )

    # 5) Scale the employed-residents component within GQ
    df3 = update_tazdata_to_county_target(
        df2,
        det.rename(columns={'GQEMP_target': 'gq_emp_target'}),
        sum_var='EMPRES',
        partial_vars=[
            'pers_occ_management',
            'pers_occ_professional',
            'pers_occ_services',
            'pers_occ_retail',
            'pers_occ_manual',
            'pers_occ_military'
        ]
    )

    return df3


def make_hhsizes_consistent_with_population(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    size_or_workers: str,
    popsyn_ACS_PUMS_5year: int
) -> pd.DataFrame:
    """
    Ensure that household size or worker distributions sum to the same as total households.

    Parameters
    ----------
    source_df : DataFrame
        TAZ-level data containing 'TAZ1454', 'County_Name', and the household size/worker buckets.
    target_df : DataFrame
        County-level targets, must include 'County_Name' and a column
        named 'TOTHH_target' (total households target).
    size_or_workers : str
        Either 'hh_size' for household size buckets or 'hh_wrks' for households by workers.
    popsyn_ACS_PUMS_5year : int
        Year of ACS PUMS five-year dataset, for compatibility (unused here).

    Returns
    -------
    DataFrame
        Adjusted TAZ-level DataFrame with either 'sum_size' or 'sum_hhworkers'
        scaled to match the county-level 'TOTHH_target'.
    """
    # Determine which partial variables to adjust
    if size_or_workers == 'hh_size':
        sum_var = 'sum_size'
        partial_vars = ['hh_size_1', 'hh_size_2', 'hh_size_3', 'hh_size_4_plus']
    elif size_or_workers == 'hh_wrks':
        sum_var = 'sum_hhworkers'
        partial_vars = ['hh_wrks_0', 'hh_wrks_1', 'hh_wrks_2', 'hh_wrks_3_plus']
    else:
        raise ValueError(f"size_or_workers must be 'hh_size' or 'hh_wrks', got {size_or_workers}")

    # Rename TOTHH_target in target_df to match sum_var_target
    targets = target_df.copy()
    targets = targets.rename(columns={'TOTHH_target': f'{sum_var}_target'})

    # Use the generic scaling function
    from common import update_tazdata_to_county_target
    adjusted = update_tazdata_to_county_target(
        source_df,
        targets,
        sum_var,
        partial_vars
    )
    return adjusted

def update_gqpop_to_county_totals(source_df, target_df, acs1year):
    """
    Adjust group quarters population and employment to match county-level targets.
    Uses decennial DHC-based estimates and scales TAZ group quarters categories.

    Parameters
    ----------
    source_df : pd.DataFrame
        TAZ-level data, must include 'County_Name', the 'gqpop' column, and the
        detailed gq-type and age breakdown variables.
    target_df : pd.DataFrame
        County-level targets, must include 'County_Name' and a column 'GQPOP_target'.
    acs1year : int
        ACS 1-year vintage (unused directly in this function).

    Returns
    -------
    pd.DataFrame
        A new DataFrame where:
          1) Total gqpop is scaled so sum(gqpop) by county = GQPOP_target.
          2) The age breakdown within gqpop (AGE0004, AGE0519, AGE2044, AGE4564, AGE65P)
             is similarly scaled to that same county target.
          3) The employed portion of gqpop (EMPRES broken into pers_occ_* fields)
             is scaled to a new target GQEMP_target derived from decennial estimates.
    """
    # 1) Reference estimates for each Bay Area county
    estimates = pd.DataFrame({
        'County_Name': BAY_AREA_COUNTIES,
        'gq_pop_estimate': [8000, 4000, 1000, 800, 7000, 3000, 10000, 2000, 2000],
        'gq_emp_estimate': [4000, 2000, 500, 400, 3500, 1500, 5000, 1000, 1000],
    })
    # Derive share of GQ pop that is employed
    estimates['worker_share'] = estimates['gq_emp_estimate'] / estimates['gq_pop_estimate']

    # 2) Merge county targets with the reference estimates
    det = pd.merge(target_df, estimates, on='County_Name')
    # Compute GQ employment target within each county
    det['GQEMP_target'] = det['GQPOP_target'] * det['worker_share']

    # 3) Scale total group‐quarters population by county
    df1 = update_tazdata_to_county_target(
        source_df,
        det,
        sum_var='gqpop',
        partial_vars=['gq_type_univ', 'gq_type_mil', 'gq_type_othnon']
    )

    # 4) Scale the age breakdown within GQ population by county
    df2 = update_tazdata_to_county_target(
        df1,
        det.rename(columns={'GQPOP_target': 'gq_age_target'}),
        sum_var='gqpop',
        partial_vars=['AGE0004', 'AGE0519', 'AGE2044', 'AGE4564', 'AGE65P']
    )

    # 5) Scale the employed‐resident component within GQ by county
    df3 = update_tazdata_to_county_target(
        df2,
        det.rename(columns={'GQEMP_target': 'gq_emp_target'}),
        sum_var='EMPRES',
        partial_vars=[
            'pers_occ_management',
            'pers_occ_professional',
            'pers_occ_services',
            'pers_occ_retail',
            'pers_occ_manual',
            'pers_occ_military'
        ]
    )

    return df3

def apply_county_targets_to_taz(
    taz_df: pd.DataFrame,
    county_targets: pd.DataFrame,
    sum_var: str,
    partial_vars: List[str]
) -> pd.DataFrame:
    """
    Scale TAZ‐level variables to match county‐level control totals.

    Args:
        taz_df: DataFrame with one row per TAZ. Must include:
            - 'taz' (or already a 'county_fips' column)
            - sum_var (e.g. 'EMPRES')
            - all names in partial_vars
        county_targets: DataFrame with county rows. Must include:
            - 'county_fips' (string of length 5)
            - sum_var column (the target total for each county)
        sum_var: name of the aggregate variable (in both taz_df and county_targets)
        partial_vars: list of disaggregate column names in taz_df to scale similarly

    Returns:
        A copy of taz_df with sum_var and each partial_var multiplied by the county scale factor.

    Raises:
        KeyError: if any required columns are missing.
    """
    df = taz_df.copy()

    # 1) Ensure we have a 'county_fips' column
    if 'county_fips' not in df.columns:
        # assume TAZ codes are strings where first 5 chars = county FIPS
        df['county_fips'] = df['taz'].astype(str).str[:5]

    # 2) Validate input columns
    needed = {sum_var, *partial_vars, 'county_fips'}
    missing = needed - set(df.columns)
    if missing:
        raise KeyError(f"apply_county_targets: missing in taz_df → {missing}")

    tgt_needed = {'county_fips', sum_var}
    missing_tgt = tgt_needed - set(county_targets.columns)
    if missing_tgt:
        raise KeyError(f"apply_county_targets: missing in county_targets → {missing_tgt}")

    # 3) Compute actual county totals
    actual = (
        df
        .groupby('county_fips')[sum_var]
        .sum()
        .reset_index()
        .rename(columns={sum_var: f"{sum_var}_actual"})
    )

    # 4) Merge targets + actuals, compute scale factor
    merged = (
        county_targets[['county_fips', sum_var]]
        .merge(actual, on='county_fips', how='left')
    )
    merged['scale_factor'] = merged[sum_var] / merged[f"{sum_var}_actual"]

    # 5) Bring scale factor back to TAZ rows
    df = df.merge(
        merged[['county_fips', 'scale_factor']],
        on='county_fips',
        how='left'
    )

    # 6) Apply scaling
    df[sum_var] = df[sum_var] * df['scale_factor']
    for var in partial_vars:
        df[var] = df[var] * df['scale_factor']

    # 7) Clean up
    df.drop(columns=['scale_factor'], inplace=True)

    return df


def sanity_check_df(df: pd.DataFrame, step_name: str) -> pd.DataFrame:
    # 1) Empty?
    if df.empty:
        raise RuntimeError(f"[SANITY] {step_name} returned an empty DataFrame")

    # 2) Numeric columns
    num = df.select_dtypes(include=[np.number])
    if num.shape[1] == 0:
        raise RuntimeError(f"[SANITY] {step_name} has no numeric columns")

    # 3) Column sums & overall sum
    col_sums = num.sum()
    total    = col_sums.sum()

    # Convert to full strings
    sums_str = col_sums.to_string()
    logging.info(f"[SANITY] {step_name} column sums:\n{sums_str}")
    logging.info(f"[SANITY] {step_name} overall numeric sum: {total}")

    if total == 0:
        raise RuntimeError(f"[SANITY] {step_name} numeric sum is zero — aborting")

    # 4) Descriptive stats
    desc = num.describe().T
    desc_str = desc.to_string()  
    logging.info(f"[SANITY] {step_name} descriptive stats:\n{desc_str}")

    return df

    def with_sanity(step_fn):
        def wrapper(*args, **kwargs):
            df = step_fn(*args, **kwargs)
            return sanity_check_df(df, step_fn.__name__)
        return wrapper
