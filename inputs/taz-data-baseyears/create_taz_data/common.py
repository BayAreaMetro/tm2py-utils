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
