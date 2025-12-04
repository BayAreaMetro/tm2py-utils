
import logging
import requests
import pandas as pd

## Config Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('census_ctpp.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__) 


def pull_ctpp_data(
        year = 2021, 
        table_id=None, 
        geography_level = "county",
        ):
    """Pull CTPP Data at a given geography_level and returns a dataframe
    
    Args:
        year (int, optional): Year for CTPP table to query. Defaults to 2021
        table_id (str):  CTPP Table ID
        geography_level (str, optional): Census Geography ("county", "place", "tract", "PUMA"). Defaults to "county"
        
    Returns:
        pd.DataFrame: DataFrame of CTPP data
    """

    df = _pull_ctpp_data(
        year,
        table_id,
        geography_level
    )

    return df

def _pull_ctpp_data(
        year = 2021, 
        table_id=None, 
        geography_level = "county", 
):
    """Helper function to pull CTPP data at the given geography level
    
    """
    base_url = _get_base_ctpp_url(year,'data')
    query_params = _get_query_params(table_id, geography_level)

    #api_key = census.get_census_creds()

    header = {
        'x-api-key': api_key,
        'accept': 'application/json'
    }
    

    try:
        logger.info("Requesting CTPP data from CTPP API")
        response = requests.get(base_url, params = query_params, headers = header)
        response.raise_for_status()
        data = response.json()
        data = data['data']
        df = pd.DataFrame(data, columns = data[0])
        logger.info(f"Retrieved {len(data)} records from CTPP API")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to retrieve CTPP data: {str(e)}", exc_info=True)
        raise

    return df
    

def get_ctpp_table_list(
    year = 2021      
):
    """PUll CTPP table IDs at a given year.

    Args: 
        year (int, optional): Year to query for table ID (2010, 2016, 2021). Defaults to 2021.
    """

    base_url = _get_base_ctpp_url('group')


def _get_query_params(
        table_id,
        geography_level
):
    """Helper function to format CTPP API query arguments
    
    Args:
        table_id
        geography_level
    
    Returns:
        dict: Dictionary of query_params for the CTPP API call
    
    """

    var = table_id
    state = "06"
    counties = "001,013,041,055,075,081,085,095,097"

    query_params = {
        "get":f'group({var})',
        "for":f'county:{counties}',
        "in":f'state:{state}',
        "d-for":f'county:{counties}',
        "d-in":f'state:{state}'
    }

    return query_params

def _get_base_ctpp_url(
        year,
        type = 'data'       
):
    """Helper function to generate url for API

    Args:
        type (str, optional): Query type ('data' or 'group'). Defaults to 'data'

    Returns:
        str: The applicable CTPP API url to query
    
    """
    base_url = f'https://ctppdata.transportation.org/api/{type}/{year}'
    
    return base_url

def get_variable_list(
        year,
        table_id
):
    """Pull variable lists for the selected Table ID
    
    Args:
        year (int, optional): Year to pull the variable list
        table_id (str): Table ID to pull the assoicate variable list
    Returns:
        dict: dictionary with name and label
    
    """
    base_url = f"https://ctppdata.transportation.org/api/groups/{table_id}/variables"
    params = {
        'year': year
    }

    header = {
        'x-api-key': api_key,
        'accept': 'application/json'
    }

    try:
        logger.info("Requesting CTPP variable data from CTPP API")        
        rq = requests.get(base_url, params, headers = header)
        rq.raise_for_status()
        variable = rq.json()
        variable = variable['data']
        variable_df = pd.DataFrame(variable, columns = variable[0])
        variable_df.loc[variable_df['name'].str.contains('_m'), 'label'] = variable_df['label'] + "_MOE"
        variable_dict = dict(zip(variable_df['name'].str.lower(), variable_df['label']))
        logger.info(f"Retrieved {len(variable)} records from CTPP API")


    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to retrieve CTPP data: {str(e)}", exc_info=True)
        raise

    return variable_dict
    

## SET API KEY
api_key = ''

table_dict = {
    'B302100':'HomeToWork', 
    'B302103':'HomeToWork_Mode', 
    'B302202': 'HomeToWork_TravelTimeMode',
    'B302102': 'HomeToWork_Industry',
    'B306302': 'HomeToWork_DepartureTime',
    'B306201': 'HomeToWork_MeanTravelTime'
}
year = 2021

for table_id, table_name in table_dict.items():
    logging.info(f"Pulling CTPP data for {table_id}")
    variable_dict = get_variable_list(year, table_id)
    df = pull_ctpp_data(year, table_id, 'county')
    df = df.sort_index(axis = 1)
    df = df[['origin_name', 'destination_name'] + [col for col in df.columns if col not in ['origin_name', 'destination_name']]]
    df.rename(columns = variable_dict, inplace = True)
    df.to_csv(f"E:/GitHub/tm2/tm2py-utils/tm2py_utils/summary/data/{year}_CTPP_{table_name}.csv", index= False)

# %%
