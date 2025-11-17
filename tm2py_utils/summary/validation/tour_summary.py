"""
Tour Summary Module

Generates tour-level validation summaries including tour frequency by purpose,
mode choice patterns, and tour timing (time-of-day) distributions.
"""

import pandas as pd
import logging
from typing import Dict, Optional

from .summary_utils import calculate_weighted_summary, calculate_binned_summary

logger = logging.getLogger(__name__)


def generate_tour_frequency_summary(tour_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate tour frequency by purpose summaries.
    
    Args:
        tour_data: Tour dataframe with tour purpose information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if tour_data is None or len(tour_data) == 0:
        logger.warning(f"  ⚠ No tour data for {dataset_name}")
        return summaries
    
    # Tour frequency by purpose
    if 'tour_purpose' not in tour_data.columns:
        logger.warning(f"  ⚠ No tour_purpose column in tour data for {dataset_name}")
        return summaries
    
    purpose_summary = calculate_weighted_summary(
        tour_data,
        group_cols='tour_purpose',
        weight_col=weight_col,
        count_col_name='tours',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'tour_frequency_by_purpose_{dataset_name}'] = purpose_summary
    logger.info(f"  ✓ Generated tour frequency by purpose for {dataset_name}: {len(tour_data)} tours")
    
    return summaries


def generate_tour_mode_summary(tour_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate tour mode choice summaries.
    
    Args:
        tour_data: Tour dataframe with tour mode information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if tour_data is None or len(tour_data) == 0:
        logger.warning(f"  ⚠ No tour data for {dataset_name}")
        return summaries
    
    # Tour mode choice
    if 'tour_mode' not in tour_data.columns:
        logger.warning(f"  ⚠ No tour_mode column in tour data for {dataset_name}")
        return summaries
    
    mode_summary = calculate_weighted_summary(
        tour_data,
        group_cols='tour_mode',
        weight_col=weight_col,
        count_col_name='tours',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'tour_mode_choice_{dataset_name}'] = mode_summary
    logger.info(f"  ✓ Generated tour mode choice summary for {dataset_name}")
    
    # Mode by purpose (cross-tabulation)
    if 'tour_purpose' in tour_data.columns:
        mode_purpose_summary = calculate_weighted_summary(
            tour_data,
            group_cols=['tour_purpose', 'tour_mode'],
            weight_col=weight_col,
            count_col_name='tours',
            share_group_cols='tour_purpose',  # Share of each mode within each purpose
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'tour_mode_by_purpose_{dataset_name}'] = mode_purpose_summary
        logger.info(f"  ✓ Generated tour mode by purpose cross-tab for {dataset_name}")
    
    return summaries


def generate_tour_timing_summary(tour_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate tour time-of-day (timing) summaries.
    
    Args:
        tour_data: Tour dataframe with timing information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if tour_data is None or len(tour_data) == 0:
        logger.warning(f"  ⚠ No tour data for {dataset_name}")
        return summaries
    
    # Tour time of day (if available)
    if 'start_period' not in tour_data.columns or 'end_period' not in tour_data.columns:
        logger.debug(f"  ⓘ No start_period/end_period columns for {dataset_name}")
        return summaries
    
    tod_summary = calculate_weighted_summary(
        tour_data,
        group_cols=['start_period', 'end_period'],
        weight_col=weight_col,
        count_col_name='tours',
        calculate_share=False,
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'tour_time_of_day_{dataset_name}'] = tod_summary
    logger.info(f"  ✓ Generated tour time-of-day summary for {dataset_name}")
    
    # Start time distribution
    start_summary = calculate_weighted_summary(
        tour_data,
        group_cols='start_period',
        weight_col=weight_col,
        count_col_name='tours',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'tour_start_time_{dataset_name}'] = start_summary
    logger.info(f"  ✓ Generated tour start time distribution for {dataset_name}")
    
    return summaries


def generate_tour_length_summary(tour_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate tour distance/duration summaries.
    
    Args:
        tour_data: Tour dataframe with distance/time information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if tour_data is None or len(tour_data) == 0:
        logger.warning(f"  ⚠ No tour data for {dataset_name}")
        return summaries
    
    # Tour distance distribution (if available)
    if 'distance' in tour_data.columns:
        distance_summary = calculate_binned_summary(
            tour_data,
            value_col='distance',
            bins=[0, 5, 10, 20, 50, 1000],
            labels=['0-5 miles', '5-10 miles', '10-20 miles', '20-50 miles', '50+ miles'],
            weight_col=weight_col,
            count_col_name='tours',
            bin_col_name='distance_bin',
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'tour_distance_{dataset_name}'] = distance_summary
        logger.info(f"  ✓ Generated tour distance distribution for {dataset_name}")
    
    # Tour duration distribution (if available)
    if 'duration' in tour_data.columns or 'time' in tour_data.columns:
        time_col = 'duration' if 'duration' in tour_data.columns else 'time'
        
        duration_summary = calculate_binned_summary(
            tour_data,
            value_col=time_col,
            bins=[0, 30, 60, 120, 240, 10000],
            labels=['0-30 min', '30-60 min', '1-2 hours', '2-4 hours', '4+ hours'],
            weight_col=weight_col,
            count_col_name='tours',
            bin_col_name='duration_bin',
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'tour_duration_{dataset_name}'] = duration_summary
        logger.info(f"  ✓ Generated tour duration distribution for {dataset_name}")
    
    return summaries


def generate_all_tour_summaries(tour_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate all tour-level summaries.
    
    Args:
        tour_data: Tour dataframe
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of all tour summary tables
    """
    logger.info(f"Generating tour summaries for {dataset_name}...")
    
    all_summaries = {}
    
    # Tour frequency
    all_summaries.update(generate_tour_frequency_summary(tour_data, dataset_name, weight_col))
    
    # Tour mode choice
    all_summaries.update(generate_tour_mode_summary(tour_data, dataset_name, weight_col))
    
    # Tour timing
    all_summaries.update(generate_tour_timing_summary(tour_data, dataset_name, weight_col))
    
    # Tour distance/duration
    all_summaries.update(generate_tour_length_summary(tour_data, dataset_name, weight_col))
    
    logger.info(f"  ✓ Generated {len(all_summaries)} tour summary tables")
    
    return all_summaries
