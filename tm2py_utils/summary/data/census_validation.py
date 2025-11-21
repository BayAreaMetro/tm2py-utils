# %%
from mtcpy import census
from mtcpy import credentials
from mtcpy import constants
import pandas as pd
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

# %%
table_ids = {
    'HouseholdSizeByVehicle': 'B08201',
    'CommuteMode': 'B08101',
    'CommuteModeByIncome': 'B08119',
    'CommuteModeByOccupation': 'B08124',
    'CommuteModeByVehicle': 'B08141'
}
year = 2023

variables = census.pull_acs_variables_dict(year = 2023, acs_type='acs1')

#%%

for table_name, table_id in table_ids.items():
    table = census.pull_acs_data(
        year = 2023,
        acs_type = 'acs1',
        table_id = table_id,
        geography_level = "county"
    )
    ## Rename column names from label to concept

    # print(table.columns)
    # print(table.head())
    table.T
    table.to_csv(f'2023_{table_name}_acs1.csv', index = False)
