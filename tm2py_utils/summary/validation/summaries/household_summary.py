"""
Household Summary Module

Generates household-level validation summaries including auto ownership patterns,
household size distribution, and income-based analyses.
"""

import pandas as pd
import logging
from typing import Dict, Optional

from .summary_utils import calculate_weighted_summary

logger = logging.getLogger(__name__)


def generate_auto_ownership_summary(hh_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate auto ownership summary tables.
    
    Args:
        hh_data: Household dataframe with 'vehicles' column
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations (e.g., 'sample_rate')
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if hh_data is None or len(hh_data) == 0:
        logger.warning(f"  ⚠ No household data for {dataset_name}")
        return summaries
    
    # Validate required columns
    if 'num_vehicles' not in hh_data.columns:
        logger.error(f"  ✗ Missing 'num_vehicles' column in household data for {dataset_name}")
        return summaries
    
    # Regional auto ownership share
    regional_summary = calculate_weighted_summary(
        hh_data,
        group_cols='num_vehicles',
        weight_col=weight_col,
        count_col_name='households',
        additional_cols={'dataset': dataset_name, 'geography': 'Regional'}
    )
    
    summaries[f'auto_ownership_regional_{dataset_name}'] = regional_summary
    logger.info(f"  ✓ Generated regional auto ownership summary for {dataset_name}")
    
    # Auto ownership by income (if available)
    # Use binned income if available, otherwise try to bin from raw income
    income_col = 'income_category_bin' if 'income_category_bin' in hh_data.columns else 'income_category'
    
    if income_col in hh_data.columns:
        income_summary = calculate_weighted_summary(
            hh_data,
            group_cols=[income_col, 'num_vehicles'],
            weight_col=weight_col,
            count_col_name='households',
            share_group_cols=income_col,  # Share within each income group
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'auto_ownership_by_income_{dataset_name}'] = income_summary
        logger.info(f"  ✓ Generated auto ownership by income summary for {dataset_name}")
    
    return summaries


def generate_household_size_summary(hh_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate household size distribution summary.
    
    Args:
        hh_data: Household dataframe with 'persons' column
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if hh_data is None or len(hh_data) == 0:
        logger.warning(f"  ⚠ No household data for {dataset_name}")
        return summaries
    
    if 'num_persons' not in hh_data.columns:
        logger.warning(f"  ⚠ Missing 'num_persons' column in household data for {dataset_name}")
        return summaries
    
    # Household size distribution
    size_summary = calculate_weighted_summary(
        hh_data,
        group_cols='num_persons',
        weight_col=weight_col,
        count_col_name='households',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'household_size_{dataset_name}'] = size_summary
    logger.info(f"  ✓ Generated household size summary for {dataset_name}")
    
    return summaries


def generate_income_summary(hh_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate income distribution summary with binned income categories.
    
    Args:
        hh_data: Household dataframe with 'income' or 'income_category' column
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if hh_data is None or len(hh_data) == 0:
        logger.warning(f"  ⚠ No household data for {dataset_name}")
        return summaries
    
    # Use binned income if available from config, otherwise check for raw income
    income_col = 'income_category_bin' if 'income_category_bin' in hh_data.columns else 'income_category'
    
    if income_col not in hh_data.columns:
        logger.warning(f"  ⚠ Missing '{income_col}' column in household data for {dataset_name}")
        return summaries
    
    # Income distribution
    income_summary = calculate_weighted_summary(
        hh_data,
        group_cols=income_col,
        weight_col=weight_col,
        count_col_name='households',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'income_distribution_{dataset_name}'] = income_summary
    logger.info(f"  ✓ Generated income distribution summary for {dataset_name}")
    
    return summaries


def generate_all_household_summaries(hh_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate all household-level summaries.
    
    Args:
        hh_data: Household dataframe
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of all household summary tables
    """
    logger.info(f"Generating household summaries for {dataset_name}...")
    
    all_summaries = {}
    
    # Auto ownership
    all_summaries.update(generate_auto_ownership_summary(hh_data, dataset_name, weight_col))
    
    # Household size
    all_summaries.update(generate_household_size_summary(hh_data, dataset_name, weight_col))
    
    # Income distribution
    all_summaries.update(generate_income_summary(hh_data, dataset_name, weight_col))
    
    logger.info(f"  ✓ Generated {len(all_summaries)} household summary tables")
    
    return all_summaries
