# %%
# from mtcpy import census
# from mtcpy import credentials
# from mtcpy import constants
# import pandas as pd
# import requests
# import logging
#from ipumspy import IpumsApiClient, MicrodataExtract, save_extract_as_json

# Pull ACS 1-year 2023 Census Data
# Include the following variables:
# Auto Ownership Totals/Shares by Region and County
# Auto Ownership:
# - By Region and County
# - By Region and Income Quartile - do this with iPUMS 
# - By Household Size
# Commute Mode to Work (with and without working at home)
# - By Region and County
# - By Household Income
# - By Auto Ownership
# - By Worker Industry


# logging.basicConfig(
#     level = logging.INFO,
#     format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler('census_validation.log'),
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger(__name__)

# table_ids = {
#     'HouseholdSizeByVehicle': 'B08201',
#     'CommuteMode': ['B08006_001E', 'B08006_002E', 'B08006_003E', 'B08006_004E','B08006_005E', 'B08006_006E', 'B08006_007E', 'B08006_008E', 
#                      'B08006_009E', 'B08006_010E', 'B08006_011E', 'B08006_012E','B08006_013E', 'B08006_014E', 'B08006_015E', 'B08006_016E','B08006_017E'],
#     'CommuteModewoWFH' : ['B08006_001E', 'B08006_002E', 'B08006_003E', 'B08006_004E','B08006_005E', 'B08006_006E', 'B08006_007E', 'B08006_008E', 
#                      'B08006_009E', 'B08006_010E', 'B08006_011E', 'B08006_012E','B08006_013E', 'B08006_014E', 'B08006_015E', 'B08006_016E'],
#     'CommuteModeByIncome': 'B08119',
#     'CommuteModeByOccupation': 'B08124',
#     'CommuteModeByVehicle': 'B08141'
# }
# year = 2023

# variables = census.pull_acs_variables_dict(year = 2023, acs_type='acs1')
# variables_df = pd.DataFrame.from_dict(variables['variables'],orient= 'index')
# variables_df['label'] = variables_df['label'].str.replace("Estimate!!", "")
# variables_df['label'] = variables_df['label'].str.replace("!!", " ")


# #%%
# logger.info(f"Starting 1-Year ACS Data Pull for year {year}")
# logger.info(f"Processing {len(table_ids)} tables: {list(table_ids.key())}")

# for table_name, table_id in table_ids.items():
#     logger.info(f"Processing table: {table_name}")
#     if type(table_id) is list:
#         logger.debug(f"Using variables list with {len(table_id)} variables")
#         table = census.pull_acs_data(
#             year = 2023,
#             acs_type = 'acs1',
#             variable_list= table_id,
#             geography_level='county'
#         )
#         table_variables = variables_df.loc[table_id]
#     else:
#         logger.debug(f"Using table ID: {table_id}")
#         table = census.pull_acs_data(
#             year = 2023,
#             acs_type = 'acs1',
#             table_id = table_id,
#             geography_level = "county"
#         )
#         table_variables = variables_df[variables_df['group'] == table_id]
    
#     logger.info(f"Retrieved {len(table)} rows for {table_name}")
#     variable_dict = table_variables['label'].to_dict()
#     variable_share = dict(zip(table_variables['label'],map(lambda x: "share_" + x, table_variables['label'])))
   
#     ## Rename column names from label to concept
#     table = table.rename(columns = variable_dict)
#     table = table.set_index('county').T
#     table['Bay Area'] = table.sum(axis = 1)

#     table = table.unstack().reset_index()
#     table = table.rename(columns = {'level_1': 'grouping', 0:'universe'})
    
#     table = table[table['grouping'] != 'Total:']
    
#     table['share'] = table.groupby('county')['universe'].transform(lambda x: (x/x.sum())*100)
#     table['dataset'] = '2023 ACS 1 Year'
#     table.to_csv(f'2023_{table_name}_acs1.csv', index = True)

# logger.info(f"Completed ACS data pull")
# #%%
# # Pulling Household and Vehicle information from PUMS
# logger.info("Starting PUMS data pull")
# url = "https://api.census.gov/data/2023/acs/acs1/pums"
# api_key = census.get_census_creds

# county_to_puma = {
#         'Alameda': ['00101','00111', '00112', '00113', '00114', '00115', '00116', '00117', '00118', '00119'],
#         'Contra Costa': ['01301', '01305', '01308', '01309', '01310', '01311', '01312', '01313', '01314'],
#         'Marin': ['04103', '04104'],
#         'Napa': ['05500'],
#         'San Francisco': ['07507', '07508', '07509', '07510', '07511', '07512', '07513', '07514'],
#         'San Mateo': ['08101','08102', '08103', '08104', '08105', '08106'],
#         'Santa Clara': ['08505','08506','08507','08508', '08510', '08511', '08512', '08515', '08516', '08517', '08518', '08519', '08520', '08521','08522'],
#         'Solano':['09501', '09502', '09503'],
#         'Sonoma':['09702', '09704', '09705', '09706']
# }

# puma_to_county = {puma: county for county, pumas in county_to_puma.items() for puma in pumas}

# bay_area_puma = set(puma_to_county.keys())
# logger.info(f"Bay Area PUMAs : {len(bay_area_puma)} area across {len(county_to_puma)} counties")

# #%%
# params = {
#     "get": "SERIALNO,HINCP,VEH,WGTP,ADJINC,PUMA",
#     "for": f"public use microdata area:*",
#     "in": 'state:06',
#     "ucgid": 'H'
# }
# logger.info("Requesting PUMS data from Census API")
# response = requests.get(url, params)
# response.raise_for_status()
# data = response.json()
# logger.info(f"Retreived {len(data)} records from PUMS API")
# # %%

# puma_table = pd.DataFrame(data[1:], columns = data[0])
# logger.info(f"Created DataFrame with {len(puma_table)} total records")

# puma_table = puma_table[puma_table['PUMA'].isin(bay_area_puma)]
# logger.info(f"Filtered to {len(puma_table)} Bay Area records")
    
# puma_table['county'] = puma_table['PUMA'].map(puma_to_county )

# # Convert to numeric
# logger.info("Converting columns to numeric types")
# puma_table['HINCP'] = pd.to_numeric(puma_table['HINCP'], errors='coerce')
# puma_table['WGTP'] = pd.to_numeric(puma_table['WGTP'], errors='coerce')
# puma_table['ADJINC'] = pd.to_numeric(puma_table['HINCP'], errors='coerce')

# puma_table['adjusted_income'] = ( puma_table['HINCP'] * puma_table['ADJINC'] / 1000000).round(0)
# logger.info("Calculated adjusted income")

# # %%
# ## Aggregate PUMA up
# # Create income bins
# logger.info("Aggregating vehicles by income")
# income_bins = [0, 30000, 60000, 100000, 150000, float('inf')]
# income_labels = ['0 to 30k', '30-60k', '60-100k', '100-150k', '150k+']
# puma_table['income_bin'] = pd.cut(puma_table['adjusted_income'], 
#                          bins = income_bins,
#                          labels = income_labels,
#                          right = False)
# logger.info(f"Created income bins: {income_labels}")

# ## Number of vehicles by income
# veh_by_income = puma_table[puma_table['income_bin'].notna() & puma_table['VEH'].notna()]

# pivot =veh_by_income.pivot_table(
#     values = 'WGTP',
#     index = 'income_bin',
#     columns = 'VEH',
#     aggfunc = 'sum',
#     fill_value=0
# )

# pivot = pivot.unstack().reset_index().rename(columns = {0:'household'})
# pivot.to_csv("2023_VehiclesByIncome_pums_acs1.csv", index= False)

import logging
from pathlib import Path
from mtcpy import census
from mtcpy import credentials
from mtcpy import constants
import pandas as pd
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('census_validation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# %%
def pull_acs_tables(table_ids: dict, year: int = 2023) -> dict:
    """Pull ACS data for specified table IDs and process into summaries."""
    logger.info(f"Starting ACS data pull for year {year}")
    logger.info(f"Processing {len(table_ids)} tables: {list(table_ids.keys())}")
    
    results = {}
    variables = census.pull_acs_variables_dict(year=year, acs_type='acs1')
    logger.info(f"Retrieved {len(variables.get('variables', {}))} variables from ACS")
    
    variables_df = pd.DataFrame.from_dict(variables['variables'], orient='index')
    variables_df['label'] = variables_df['label'].str.replace("Estimate!!", "")
    variables_df['label'] = variables_df['label'].str.replace("!!", " ")
    logger.debug(f"Variables DataFrame shape: {variables_df.shape}")

    for table_name, table_id in table_ids.items():
        try:
            logger.info(f"Processing table: {table_name} (ID: {table_id})")
            
            if isinstance(table_id, list):
                logger.debug(f"  Using variable list with {len(table_id)} variables")
                table = census.pull_acs_data(
                    year=year,
                    acs_type='acs1',
                    variable_list=table_id,
                    geography_level='county'
                )
                table_variables = variables_df.loc[table_id]
            else:
                logger.debug(f"  Using table ID: {table_id}")
                table = census.pull_acs_data(
                    year=year,
                    acs_type='acs1',
                    table_id=table_id,
                    geography_level="county"
                )
                table_variables = variables_df[variables_df['group'] == table_id]
            
            logger.info(f"  Retrieved {len(table)} rows for {table_name}")
            
            variable_dict = table_variables['label'].to_dict()
            
            # Rename and reshape
            table = table.rename(columns=variable_dict)
            table = table.set_index('county').T
            table['Bay Area'] = table.sum(axis=1)
            table = table.unstack().reset_index()
            table = table.rename(columns={'level_1': 'grouping', 0: 'universe'})
            
            table = table[table['grouping'] != 'Total:']
            table['share'] = table.groupby('county')['universe'].transform(lambda x: (x / x.sum()) * 100)
            table['dataset'] = '2023 ACS 1 Year'
            
            output_file = f'2023_{table_name}_acs1.csv'
            table.to_csv(output_file, index=True)
            logger.info(f"  Saved to {output_file}")
            
            results[table_name] = table
            
        except Exception as e:
            logger.error(f"Error processing {table_name}: {str(e)}", exc_info=True)
            continue
    
    logger.info(f"Completed ACS data pull. Processed {len(results)}/{len(table_ids)} tables")
    return results

# %%
def pull_pums_data(year: int = 2023) -> pd.DataFrame:
    """Pull PUMS household and vehicle data from Census API."""
    logger.info("Starting PUMS data pull")
    
    county_to_puma = {
        'Alameda': ['00101', '00111', '00112', '00113', '00114', '00115', '00116', '00117', '00118', '00119'],
        'Contra Costa': ['01301', '01305', '01308', '01309', '01310', '01311', '01312', '01313', '01314'],
        'Marin': ['04103', '04104'],
        'Napa': ['05500'],
        'San Francisco': ['07507', '07508', '07509', '07510', '07511', '07512', '07513', '07514'],
        'San Mateo': ['08101', '08102', '08103', '08104', '08105', '08106'],
        'Santa Clara': ['08505', '08506', '08507', '08508', '08510', '08511', '08512', '08515', '08516', '08517', '08518', '08519', '08520', '08521', '08522'],
        'Solano': ['09501', '09502', '09503'],
        'Sonoma': ['09702', '09704', '09705', '09706']
    }
    
    puma_to_county = {puma: county for county, pumas in county_to_puma.items() for puma in pumas}
    bay_area_puma = set(puma_to_county.keys())
    logger.info(f"Bay Area PUMAs: {len(bay_area_puma)} areas across {len(county_to_puma)} counties")
    
    url = "https://api.census.gov/data/2023/acs/acs1/pums"
    api_key = census.get_census_creds
    logger.debug("Retrieved Census API credentials")
    
    params = {
        "get": "SERIALNO,HINCP,VEH,WGTP,ADJINC,PUMA",
        "for": "public use microdata area:*",
        "in": 'state:06',
        "ucgid": 'H'
    }
    
    try:
        logger.info("Requesting PUMS data from Census API")
        response = requests.get(url, params)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Retrieved {len(data)} records from PUMS API")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to retrieve PUMS data: {str(e)}", exc_info=True)
        raise
    
    # Process data
    puma_table = pd.DataFrame(data[1:], columns=data[0])
    logger.info(f"Created DataFrame with {len(puma_table)} total records")
    
    puma_table = puma_table[puma_table['PUMA'].isin(bay_area_puma)]
    logger.info(f"Filtered to {len(puma_table)} Bay Area records")
    
    puma_table['county'] = puma_table['PUMA'].map(puma_to_county)
    
    # Convert to numeric
    logger.info("Converting columns to numeric types")
    puma_table['HINCP'] = pd.to_numeric(puma_table['HINCP'], errors='coerce')
    puma_table['VEH'] = pd.to_numeric(puma_table['VEH'], errors='coerce')
    puma_table['WGTP'] = pd.to_numeric(puma_table['WGTP'], errors='coerce')
    puma_table['ADJINC'] = pd.to_numeric(puma_table['ADJINC'], errors='coerce')
    
    null_counts = puma_table[['HINCP', 'VEH', 'WGTP', 'ADJINC']].isnull().sum()
    logger.info(f"Null values after conversion: {null_counts.to_dict()}")
    
    puma_table['adjusted_income'] = (puma_table['HINCP'] * puma_table['ADJINC'] / 1000000).round(0)
    logger.info("Calculated adjusted income")
    
    return puma_table

# %%
def aggregate_vehicles_by_income(puma_table: pd.DataFrame, output_file: str = None) -> pd.DataFrame:
    """Aggregate vehicle ownership by income bin."""
    logger.info("Aggregating vehicles by income")
    
    # Create income bins
    income_bins = [0, 30000, 60000, 100000, 150000, float('inf')]
    income_labels = ['0 to 30k', '30-60k', '60-100k', '100-150k', '150k+']
    
    puma_table['income_bin'] = pd.cut(
        puma_table['adjusted_income'],
        bins=income_bins,
        labels=income_labels,
        right=False
    )
    logger.info(f"Created income bins: {income_labels}")
    
    # Filter valid records
    veh_by_income = puma_table[
        puma_table['income_bin'].notna() & puma_table['VEH'].notna()
    ]
    logger.info(f"Valid records for aggregation: {len(veh_by_income)}")
    
    # Create pivot table
    pivot = veh_by_income.pivot_table(
        values='WGTP',
        index='income_bin',
        columns='VEH',
        aggfunc='sum',
        fill_value=0
    )
    logger.info(f"Pivot table shape: {pivot.shape}")
    logger.debug(f"\nVehicles by Income:\n{pivot}")
    
    pivot = pivot.unstack().reset_index().rename(columns={0: 'household'})
    
    # Save to file
    if output_file is None:
        output_file = "2023_VehiclesByIncome_pums_acs1.csv"
    
    try:
        pivot.to_csv(output_file, index=False)
        logger.info(f"Saved vehicle aggregation to {output_file}")
    except Exception as e:
        logger.error(f"Failed to save output file {output_file}: {str(e)}", exc_info=True)
        raise
    
    return pivot

# %%
def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("Starting Census Validation Script")
    logger.info("=" * 60)
    
    try:
        # Define ACS tables to pull
        table_ids = {
            'HouseholdSizeByVehicle': 'B08201',
            'CommuteMode': ['B08006_001E', 'B08006_002E', 'B08006_003E', 'B08006_004E',
                           'B08006_005E', 'B08006_006E', 'B08006_007E', 'B08006_008E',
                           'B08006_009E', 'B08006_010E', 'B08006_011E', 'B08006_012E',
                           'B08006_013E', 'B08006_014E', 'B08006_015E', 'B08006_016E',
                           'B08006_017E'],
            'CommuteModeByIncome': 'B08119',
            'CommuteModeByOccupation': 'B08124',
            'CommuteModeByVehicle': 'B08141'
        }
        
        # Pull ACS data
        logger.info("Phase 1: Pulling ACS tabular data")
        acs_results = pull_acs_tables(table_ids, year=2023)
        
        # Pull PUMS data
        logger.info("Phase 2: Pulling PUMS microdata")
        puma_table = pull_pums_data(year=2023)
        
        # Aggregate and save
        logger.info("Phase 3: Aggregating and saving results")
        vehicles_by_income = aggregate_vehicles_by_income(puma_table)
        
        logger.info("=" * 60)
        logger.info("Census Validation Script Completed Successfully")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error("Fatal error in main execution", exc_info=True)
        raise

if __name__ == "__main__":
    main()

# %%
