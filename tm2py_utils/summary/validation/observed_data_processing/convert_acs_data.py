"""
Convert pre-parsed ACS household size by vehicle data to model validation format.

This script takes the already-parsed ACS data from the summary/data directory
and converts it to match the model output format for validation comparisons.
"""
import pandas as pd
import logging
from pathlib import Path
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def parse_grouping_label(label: str) -> tuple:
    """
    Parse ACS grouping label to extract household size and vehicle count.
    
    Examples:
        "Total: 1-person household: No vehicle available" -> (1, 0)
        "Total: 2-person household: 3 vehicles available" -> (2, 3)
        "Total: 4-or-more-person household: 4 or more vehicles available" -> (4, 4)
    
    Returns:
        (num_persons, num_vehicles) or (None, None) if not a detail row
    """
    # Skip total rows (no household size specified)
    if not re.search(r'\d+-person household:|4-or-more-person household:', label):
        return None, None
    
    # Extract household size
    if '1-person household:' in label:
        num_persons = 1
    elif '2-person household:' in label:
        num_persons = 2
    elif '3-person household:' in label:
        num_persons = 3
    elif '4-or-more-person household:' in label:
        num_persons = 4
    else:
        return None, None
    
    # Extract vehicle count
    if 'No vehicle available' in label:
        num_vehicles = 0
    elif '1 vehicle available' in label:
        num_vehicles = 1
    elif '2 vehicles available' in label:
        num_vehicles = 2
    elif '3 vehicles available' in label:
        num_vehicles = 3
    elif '4 or more vehicles available' in label:
        num_vehicles = 4
    else:
        return None, None
    
    return num_persons, num_vehicles


def convert_acs_data(input_path: Path, output_dir: Path, dataset_name: str = "ACS 2023"):
    """
    Convert ACS data to model validation format.
    
    Args:
        input_path: Path to the preprocessed ACS CSV file
        output_dir: Directory to save converted outputs
        dataset_name: Name for the dataset column
    """
    logger.info("=" * 60)
    logger.info("ACS Data Converter for Model Validation")
    logger.info("=" * 60)
    
    # Load the data
    logger.info(f"Loading ACS data from {input_path}")
    df = pd.read_csv(input_path)
    logger.info(f"  ✓ Loaded {len(df)} rows")
    
    # Parse grouping labels
    logger.info("\nParsing grouping labels...")
    records = []
    
    for _, row in df.iterrows():
        num_persons, num_vehicles = parse_grouping_label(row['grouping'])
        
        if num_persons is not None and num_vehicles is not None:
            records.append({
                'county': row['county'],
                'num_persons': num_persons,
                'num_vehicles': num_vehicles,
                'households': row['universe'],
                'share': row['share']
            })
    
    result = pd.DataFrame(records)
    logger.info(f"  ✓ Parsed {len(result)} detail records")
    
    # Calculate shares within household size (for regional/county data)
    # The input shares are % of total, we need % within household size
    def recalc_shares(group_df):
        total = group_df['households'].sum()
        group_df = group_df.copy()
        group_df['share'] = (group_df['households'] / total * 100)
        return group_df
    
    # Create regional summary
    logger.info("\nCreating regional summary...")
    regional = result[result['county'] == 'Bay Area'].copy()
    regional = regional.groupby(['num_persons', 'num_vehicles'], as_index=False).apply(
        lambda x: x
    ).reset_index(drop=True)
    regional = regional.groupby('num_persons', group_keys=False).apply(recalc_shares).reset_index(drop=True)
    regional = regional[['num_persons', 'num_vehicles', 'households', 'share']].copy()
    
    # Convert num_persons to match model format: 1, 2, 3, '4+' (string for 4+)
    regional['num_persons'] = regional['num_persons'].apply(lambda x: str(x) if x < 4 else '4+')
    
    regional['dataset'] = dataset_name
    logger.info(f"  ✓ Created regional summary: {len(regional)} rows")
    
    # Create county summaries
    logger.info("\nCreating county summaries...")
    counties = ['Alameda', 'Contra Costa', 'Marin', 'Napa', 'San Francisco', 
                'San Mateo', 'Santa Clara', 'Solano', 'Sonoma']
    
    county_data = result[result['county'].isin(counties)].copy()
    county_data = county_data.groupby(['county', 'num_persons'], group_keys=False).apply(recalc_shares).reset_index(drop=True)
    county_data = county_data[['county', 'num_persons', 'num_vehicles', 'households', 'share']].copy()
    
    # Convert num_persons to match model format: 1, 2, 3, '4+' (string for 4+)
    county_data['num_persons'] = county_data['num_persons'].apply(lambda x: str(x) if x < 4 else '4+')
    
    county_data['dataset'] = dataset_name
    logger.info(f"  ✓ Created county summaries: {len(county_data)} rows across {len(counties)} counties")
    
    # Save outputs
    logger.info("\nSaving outputs...")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    regional_path = output_dir / "acs_auto_ownership_by_household_size_regional.csv"
    regional.to_csv(regional_path, index=False)
    logger.info(f"  ✓ Saved {regional_path}")
    
    county_path = output_dir / "acs_auto_ownership_by_household_size_county.csv"
    county_data.to_csv(county_path, index=False)
    logger.info(f"  ✓ Saved {county_path}")
    
    # Print summary statistics
    logger.info("\n" + "=" * 60)
    logger.info("Summary Statistics")
    logger.info("=" * 60)
    
    total_hh = regional['households'].sum()
    logger.info(f"Total Bay Area households: {total_hh:,.0f}")
    
    logger.info("\nHouseholds by size (regional):")
    size_summary = regional.groupby('num_persons')['households'].sum()
    for size, count in size_summary.items():
        pct = count / total_hh * 100
        size_label = f"{size}+" if size == 4 else str(size)
        logger.info(f"  {size_label}-person: {count:>12,.0f} ({pct:>5.1f}%)")
    
    logger.info("\nHouseholds by vehicles (regional):")
    veh_summary = regional.groupby('num_vehicles')['households'].sum()
    for veh, count in veh_summary.items():
        pct = count / total_hh * 100
        veh_label = f"{veh}+" if veh == 4 else str(veh)
        logger.info(f"  {veh_label} vehicles: {count:>12,.0f} ({pct:>5.1f}%)")
    
    logger.info("\n✅ ACS data conversion completed successfully!")
    
    return regional, county_data


if __name__ == "__main__":
    # Paths
    validation_dir = Path(__file__).parent
    input_file = validation_dir.parent / "data" / "2023_HouseholdSizeByVehicle_acs1.csv"
    output_dir = validation_dir / "outputs" / "observed"
    
    # Convert
    regional, county = convert_acs_data(input_file, output_dir, dataset_name="ACS 2023")
