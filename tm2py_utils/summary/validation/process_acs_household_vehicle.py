#!/usr/bin/env python3
"""
ACS Household Size by Vehicle Data Processor

Transforms ACS household size by vehicle ownership data to match model output format
for validation comparison.

ACS Source Format (wide):
    - Rows: Household size x vehicle ownership combinations (e.g., "Total: 1-person household: No vehicle available")
    - Columns: Counties + Bay Area total
    - Values: Household counts

Model Output Format (long):
    - num_persons: Household size (1, 2, 3, 4+)
    - num_vehicles: Vehicle count (0, 1, 2, 3, 4+)
    - households: Count of households
    - share: Percentage (within household size or of total)
    - dataset: Data source identifier

Usage:
    python process_acs_household_vehicle.py
    python process_acs_household_vehicle.py --input data/2023_HouseholdSizeByVehicle_acs1.csv --output outputs/
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ACS data parsing configuration
# Maps ACS row labels to structured categories
ACS_HH_SIZE_PATTERNS = {
    r'^Total: 1-person household:': 1,
    r'^Total: 2-person household:': 2,
    r'^Total: 3-person household:': 3,
    r'^Total: 4-or-more-person household:': 4,  # 4+ in ACS
}

ACS_VEHICLE_PATTERNS = {
    r'No vehicle available': 0,
    r'1 vehicle available': 1,
    r'2 vehicles available': 2,
    r'3 vehicles available': 3,
    r'4 or more vehicles available': 4,  # 4+ in ACS
}

# Bay Area county names
BAY_AREA_COUNTIES = [
    'Alameda', 'Contra Costa', 'Marin', 'Napa',
    'San Francisco', 'San Mateo', 'Santa Clara', 'Solano', 'Sonoma'
]


def parse_acs_row_label(label: str) -> tuple:
    """
    Parse ACS row label to extract household size and vehicle count.
    
    Args:
        label: ACS row label (e.g., "Total: 1-person household: No vehicle available")
        
    Returns:
        Tuple of (household_size, vehicle_count) or (None, None) if not parseable
    """
    hh_size = None
    vehicles = None
    
    # Check if this is a household size + vehicle row (not a subtotal or total)
    for pattern, size in ACS_HH_SIZE_PATTERNS.items():
        if re.match(pattern, label):
            hh_size = size
            break
    
    if hh_size is None:
        return None, None
    
    # Now check for vehicle count
    for pattern, veh in ACS_VEHICLE_PATTERNS.items():
        if re.search(pattern, label):
            vehicles = veh
            break
    
    return hh_size, vehicles


def load_acs_data(input_path: Path) -> pd.DataFrame:
    """
    Load and parse ACS household size by vehicle data from wide format.
    
    Args:
        input_path: Path to ACS CSV file
        
    Returns:
        DataFrame in long format with columns: num_persons, num_vehicles, households, county
    """
    logger.info(f"Loading ACS data from {input_path}")
    
    # Read CSV - first column is the label
    df = pd.read_csv(input_path, index_col=0)
    
    # Parse row labels to extract household size and vehicle categories
    records = []
    
    for label, row in df.iterrows():
        hh_size, vehicles = parse_acs_row_label(str(label))
        
        if hh_size is not None and vehicles is not None:
            # This is a valid household size x vehicle combination
            for county in df.columns:
                records.append({
                    'num_persons': hh_size,
                    'num_vehicles': vehicles,
                    'households': row[county],
                    'county': county
                })
    
    result = pd.DataFrame(records)
    logger.info(f"  ✓ Parsed {len(result)} records from ACS data")
    
    return result


def calculate_shares(df: pd.DataFrame, within_col: str = None) -> pd.DataFrame:
    """
    Calculate share percentages.
    
    Args:
        df: DataFrame with 'households' column
        within_col: Column to calculate shares within (e.g., 'num_persons' for within-HH-size shares)
                    If None, calculates share of total
        
    Returns:
        DataFrame with 'share' and optionally 'share_of_total' columns added
    """
    df = df.copy()
    
    if within_col:
        # Calculate share within each group
        df['share'] = df.groupby(within_col)['households'].transform(lambda x: x / x.sum() * 100)
        
        # Also calculate share of total
        total = df['households'].sum()
        df['share_of_total'] = df['households'] / total * 100
    else:
        # Calculate share of total only
        total = df['households'].sum()
        df['share'] = df['households'] / total * 100
    
    return df


def process_regional_summary(df: pd.DataFrame, dataset_name: str = "ACS 2023") -> pd.DataFrame:
    """
    Create regional (Bay Area total) summary.
    
    Args:
        df: Long-format DataFrame with parsed ACS data
        dataset_name: Name to identify this dataset
        
    Returns:
        DataFrame matching model output format
    """
    # Filter to Bay Area total
    regional = df[df['county'] == 'Bay Area'].copy()
    
    # Group by household size and vehicles (should already be unique per combination)
    regional = regional.groupby(['num_persons', 'num_vehicles'])['households'].sum().reset_index()
    
    # Calculate shares within household size
    regional = calculate_shares(regional, within_col='num_persons')
    
    # Add dataset identifier
    regional['dataset'] = dataset_name
    
    # Reorder columns to match model output
    regional = regional[['num_persons', 'num_vehicles', 'households', 'share', 'dataset']]
    
    logger.info(f"  ✓ Created regional summary: {len(regional)} rows")
    
    return regional


def process_county_summaries(df: pd.DataFrame, dataset_name: str = "ACS 2023") -> pd.DataFrame:
    """
    Create county-level summaries.
    
    Args:
        df: Long-format DataFrame with parsed ACS data
        dataset_name: Base name for dataset identifier
        
    Returns:
        DataFrame with all counties, matching model output format plus county column
    """
    # Filter to individual counties (not Bay Area total)
    county_df = df[df['county'].isin(BAY_AREA_COUNTIES)].copy()
    
    # Calculate shares within each county and household size
    results = []
    for county in BAY_AREA_COUNTIES:
        county_data = county_df[county_df['county'] == county].copy()
        
        # Calculate shares within household size for this county
        county_data = calculate_shares(county_data, within_col='num_persons')
        
        results.append(county_data)
    
    result = pd.concat(results, ignore_index=True)
    
    # Add dataset identifier
    result['dataset'] = dataset_name
    
    # Reorder columns
    result = result[['county', 'num_persons', 'num_vehicles', 'households', 'share', 'dataset']]
    
    logger.info(f"  ✓ Created county summaries: {len(result)} rows across {len(BAY_AREA_COUNTIES)} counties")
    
    return result


def save_outputs(regional: pd.DataFrame, county: pd.DataFrame, output_dir: Path,
                 regional_filename: str = "acs_auto_ownership_by_household_size_regional.csv",
                 county_filename: str = "acs_auto_ownership_by_household_size_county.csv") -> None:
    """
    Save processed summaries to CSV files.
    
    Args:
        regional: Regional summary DataFrame
        county: County summary DataFrame  
        output_dir: Directory to save outputs
        regional_filename: Filename for regional summary
        county_filename: Filename for county summary
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    regional_path = output_dir / regional_filename
    regional.to_csv(regional_path, index=False)
    logger.info(f"  ✓ Saved regional summary: {regional_path}")
    
    county_path = output_dir / county_filename
    county.to_csv(county_path, index=False)
    logger.info(f"  ✓ Saved county summary: {county_path}")


def create_combined_for_dashboard(regional: pd.DataFrame, county: pd.DataFrame,
                                   output_dir: Path,
                                   filename: str = "acs_auto_ownership_by_household_size.csv") -> pd.DataFrame:
    """
    Create a combined file suitable for dashboard comparison with model data.
    
    This creates a single file with both regional and county data that can be
    concatenated with model summaries for side-by-side comparison.
    
    Args:
        regional: Regional summary DataFrame
        county: County summary DataFrame
        output_dir: Directory to save output
        filename: Output filename
        
    Returns:
        Combined DataFrame
    """
    # Add geography column to regional
    regional_copy = regional.copy()
    regional_copy['geography'] = 'Bay Area'
    
    # Rename county column to geography for consistency
    county_copy = county.copy()
    county_copy = county_copy.rename(columns={'county': 'geography'})
    
    # Combine
    combined = pd.concat([regional_copy, county_copy], ignore_index=True)
    
    # Reorder columns
    combined = combined[['geography', 'num_persons', 'num_vehicles', 'households', 'share', 'dataset']]
    
    # Save
    output_path = output_dir / filename
    combined.to_csv(output_path, index=False)
    logger.info(f"  ✓ Saved combined summary: {output_path}")
    
    return combined


def main():
    """Main entry point for ACS data processing."""
    parser = argparse.ArgumentParser(
        description="Process ACS Household Size by Vehicle data for model validation"
    )
    parser.add_argument(
        '--input', '-i',
        type=Path,
        default=Path(__file__).parent.parent / "data" / "2023_HouseholdSizeByVehicle_acs1.csv",
        help="Path to ACS input CSV file"
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path(__file__).parent / "outputs" / "observed",
        help="Directory to save processed outputs"
    )
    parser.add_argument(
        '--dataset-name', '-n',
        type=str,
        default="ACS 2023",
        help="Name to identify this dataset in outputs"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("ACS Household Size by Vehicle Data Processor")
    logger.info("=" * 60)
    
    # Load and parse ACS data
    acs_data = load_acs_data(args.input)
    
    # Generate regional summary
    logger.info("\nGenerating regional summary...")
    regional = process_regional_summary(acs_data, args.dataset_name)
    
    # Generate county summaries
    logger.info("\nGenerating county summaries...")
    county = process_county_summaries(acs_data, args.dataset_name)
    
    # Save outputs
    logger.info("\nSaving outputs...")
    save_outputs(regional, county, args.output)
    
    # Create combined dashboard file
    logger.info("\nCreating combined dashboard file...")
    combined = create_combined_for_dashboard(regional, county, args.output)
    
    # Print summary statistics
    logger.info("\n" + "=" * 60)
    logger.info("Summary Statistics")
    logger.info("=" * 60)
    
    total_hh = regional['households'].sum()
    logger.info(f"Total Bay Area households: {total_hh:,.0f}")
    
    # Show distribution by household size
    logger.info("\nHouseholds by size (regional):")
    size_summary = regional.groupby('num_persons')['households'].sum()
    for size, count in size_summary.items():
        pct = count / total_hh * 100
        size_label = f"{size}+" if size == 4 else str(size)
        logger.info(f"  {size_label}-person: {count:>12,.0f} ({pct:>5.1f}%)")
    
    # Show distribution by vehicles
    logger.info("\nHouseholds by vehicles (regional):")
    veh_summary = regional.groupby('num_vehicles')['households'].sum()
    for veh, count in veh_summary.items():
        pct = count / total_hh * 100
        veh_label = f"{veh}+" if veh == 4 else str(veh)
        logger.info(f"  {veh_label} vehicles: {count:>12,.0f} ({pct:>5.1f}%)")
    
    logger.info("\n✅ ACS data processing completed successfully!")
    
    return regional, county, combined


if __name__ == "__main__":
    main()
