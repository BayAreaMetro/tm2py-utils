"""
Worker Summary Module

Generates worker-level validation summaries including work location patterns,
telecommuting frequency, and worker demographics.
"""

import pandas as pd
import logging
from typing import Dict, Optional

from .summary_utils import calculate_weighted_summary, calculate_binned_summary

logger = logging.getLogger(__name__)


def generate_work_location_summary(person_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate work location and commute pattern summaries.
    
    Args:
        person_data: Person dataframe with worker information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if person_data is None or len(person_data) == 0:
        logger.warning(f"  ⚠ No person data for {dataset_name}")
        return summaries
    
    # Filter to workers only
    if 'person_type' not in person_data.columns:
        logger.warning(f"  ⚠ No person_type field found in {dataset_name}")
        return summaries
    
    # Full-time and part-time workers (typically codes 1 and 2)
    workers = person_data[person_data['person_type'].isin([1, 2])]
    
    if len(workers) == 0:
        logger.warning(f"  ⚠ No workers found in {dataset_name}")
        return summaries
    
    # Basic worker count by type
    worker_type_summary = calculate_weighted_summary(
        workers,
        group_cols='person_type',
        weight_col=weight_col,
        count_col_name='workers',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'worker_type_{dataset_name}'] = worker_type_summary
    logger.info(f"  ✓ Generated worker type summary for {dataset_name}: {len(workers)} workers")
    
    return summaries


def generate_telecommute_summary(person_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate telecommuting frequency summary.
    
    Args:
        person_data: Person dataframe with telecommute information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if person_data is None or len(person_data) == 0:
        logger.warning(f"  ⚠ No person data for {dataset_name}")
        return summaries
    
    # Filter to workers only
    if 'person_type' not in person_data.columns:
        logger.warning(f"  ⚠ No person_type field found in {dataset_name}")
        return summaries
    
    workers = person_data[person_data['person_type'].isin([1, 2])]
    
    if len(workers) == 0:
        logger.warning(f"  ⚠ No workers found in {dataset_name}")
        return summaries
    
    # Work from home analysis (if telecommute field available)
    if 'telecommute_frequency' not in workers.columns:
        logger.debug(f"  ⓘ No telecommute_frequency column for {dataset_name}")
        return summaries
    
    wfh_summary = calculate_weighted_summary(
        workers,
        group_cols='telecommute_frequency',
        weight_col=weight_col,
        count_col_name='workers',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'work_from_home_{dataset_name}'] = wfh_summary
    logger.info(f"  ✓ Generated work-from-home summary for {dataset_name}")
    
    return summaries


def generate_worker_demographics_summary(person_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate worker demographics summaries (age, gender, income).
    
    Args:
        person_data: Person dataframe with demographic information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if person_data is None or len(person_data) == 0:
        logger.warning(f"  ⚠ No person data for {dataset_name}")
        return summaries
    
    if 'person_type' not in person_data.columns:
        logger.warning(f"  ⚠ No person_type field found in {dataset_name}")
        return summaries
    
    workers = person_data[person_data['person_type'].isin([1, 2])]
    
    if len(workers) == 0:
        logger.warning(f"  ⚠ No workers found in {dataset_name}")
        return summaries
    
    # Age distribution of workers
    if 'age' in workers.columns:
        age_summary = calculate_binned_summary(
            workers,
            value_col='age',
            bins=[0, 25, 35, 45, 55, 65, 120],
            labels=['Under 25', '25-34', '35-44', '45-54', '55-64', '65+'],
            weight_col=weight_col,
            count_col_name='workers',
            bin_col_name='age_group',
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'worker_age_{dataset_name}'] = age_summary
        logger.info(f"  ✓ Generated worker age distribution for {dataset_name}")
    
    # Gender distribution of workers
    if 'gender' in workers.columns:
        gender_summary = calculate_weighted_summary(
            workers,
            group_cols='gender',
            weight_col=weight_col,
            count_col_name='workers',
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'worker_gender_{dataset_name}'] = gender_summary
        logger.info(f"  ✓ Generated worker gender distribution for {dataset_name}")
    
    # Income category of workers (if person-level income available)
    if 'income_category' in workers.columns:
        income_summary = calculate_weighted_summary(
            workers,
            group_cols='income_category',
            weight_col=weight_col,
            count_col_name='workers',
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'worker_income_{dataset_name}'] = income_summary
        logger.info(f"  ✓ Generated worker income distribution for {dataset_name}")
    
    return summaries


def generate_all_worker_summaries(person_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate all worker-level summaries.
    
    Args:
        person_data: Person dataframe
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of all worker summary tables
    """
    logger.info(f"Generating worker summaries for {dataset_name}...")
    
    all_summaries = {}
    
    # Work location
    all_summaries.update(generate_work_location_summary(person_data, dataset_name, weight_col))
    
    # Telecommuting
    all_summaries.update(generate_telecommute_summary(person_data, dataset_name, weight_col))
    
    # Worker demographics
    all_summaries.update(generate_worker_demographics_summary(person_data, dataset_name, weight_col))
    
    logger.info(f"  ✓ Generated {len(all_summaries)} worker summary tables")
    
    return all_summaries
