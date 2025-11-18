"""
Trip Summary Module

Generates trip-level validation summaries including trip mode choice,
trip purpose patterns, and trip distance/timing distributions.
"""

import pandas as pd
import logging
from typing import Dict, Optional

from .summary_utils import calculate_weighted_summary, calculate_binned_summary

logger = logging.getLogger(__name__)


def generate_trip_mode_summary(trip_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate trip mode choice summaries.
    
    Args:
        trip_data: Trip dataframe with mode information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if trip_data is None or len(trip_data) == 0:
        logger.warning(f"  ⚠ No trip data for {dataset_name}")
        return summaries
    
    # Trip mode choice
    if 'trip_mode' not in trip_data.columns:
        logger.warning(f"  ⚠ No trip_mode column in trip data for {dataset_name}")
        return summaries
    
    # Map mode codes to names
    MODE_NAMES = {
        1: "SOV (GP)",
        2: "SOV (Toll)",
        3: "Carpool 2 (GP)",
        4: "Carpool 2 (HOV)",
        5: "Carpool 2 (Toll)",
        6: "Carpool 3+ (GP)",
        7: "Carpool 3+ (HOV)",
        8: "Carpool 3+ (Toll)",
        9: "Walk",
        10: "Bike",
        11: "Walk to Transit",
        12: "Park & Ride",
        13: "Kiss & Ride (Private)",
        14: "Kiss & Ride (TNC)",
        15: "Taxi",
        16: "TNC",
        17: "School Bus"
    }
    
    # Create a copy to avoid modifying original data
    trip_data = trip_data.copy()
    trip_data['trip_mode'] = trip_data['trip_mode'].map(MODE_NAMES).fillna(trip_data['trip_mode'].astype(str))
    
    mode_summary = calculate_weighted_summary(
        trip_data,
        group_cols='trip_mode',
        weight_col=weight_col,
        count_col_name='trips',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'trip_mode_choice_{dataset_name}'] = mode_summary
    logger.info(f"  ✓ Generated trip mode choice summary for {dataset_name}: {len(trip_data)} trips")
    
    return summaries


def generate_trip_purpose_summary(trip_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate trip purpose summaries.
    
    Args:
        trip_data: Trip dataframe with purpose information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if trip_data is None or len(trip_data) == 0:
        logger.warning(f"  ⚠ No trip data for {dataset_name}")
        return summaries
    
    # Trip purpose distribution - use destination_purpose from data model
    if 'destination_purpose' not in trip_data.columns:
        logger.debug(f"  ⓘ No destination_purpose column for {dataset_name}")
        return summaries
    
    purpose_col = 'destination_purpose'
    
    purpose_summary = calculate_weighted_summary(
        trip_data,
        group_cols=purpose_col,
        weight_col=weight_col,
        count_col_name='trips',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'trip_purpose_{dataset_name}'] = purpose_summary
    logger.info(f"  ✓ Generated trip purpose summary for {dataset_name}")
    
    # Mode by purpose cross-tab
    if 'trip_mode' in trip_data.columns:
        mode_purpose_summary = calculate_weighted_summary(
            trip_data,
            group_cols=[purpose_col, 'trip_mode'],
            weight_col=weight_col,
            count_col_name='trips',
            share_group_cols=purpose_col,  # Share of each mode within each purpose
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'trip_mode_by_purpose_{dataset_name}'] = mode_purpose_summary
        logger.info(f"  ✓ Generated trip mode by purpose cross-tab for {dataset_name}")
    
    return summaries


def generate_trip_timing_summary(trip_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate trip time-of-day summaries.
    
    Args:
        trip_data: Trip dataframe with timing information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if trip_data is None or len(trip_data) == 0:
        logger.warning(f"  ⚠ No trip data for {dataset_name}")
        return summaries
    
    # Trip departure time distribution
    time_col = None
    if 'depart_period' in trip_data.columns:
        time_col = 'depart_period'
    elif 'stop_period' in trip_data.columns:
        time_col = 'stop_period'
    elif 'time_period' in trip_data.columns:
        time_col = 'time_period'
    
    if time_col is None:
        logger.debug(f"  ⓘ No time period column for {dataset_name}")
        return summaries
    
    time_summary = calculate_weighted_summary(
        trip_data,
        group_cols=time_col,
        weight_col=weight_col,
        count_col_name='trips',
        additional_cols={'dataset': dataset_name}
    )
    
    summaries[f'trip_time_of_day_{dataset_name}'] = time_summary
    logger.info(f"  ✓ Generated trip time-of-day summary for {dataset_name}")
    
    return summaries


def generate_trip_length_summary(trip_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate trip distance and duration summaries.
    
    Args:
        trip_data: Trip dataframe with distance/time information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if trip_data is None or len(trip_data) == 0:
        logger.warning(f"  ⚠ No trip data for {dataset_name}")
        return summaries
    
    # Trip distance distribution
    if 'distance' in trip_data.columns:
        distance_summary = calculate_binned_summary(
            trip_data,
            value_col='distance',
            bins=[0, 1, 3, 5, 10, 20, 1000],
            labels=['0-1 mile', '1-3 miles', '3-5 miles', '5-10 miles', '10-20 miles', '20+ miles'],
            weight_col=weight_col,
            count_col_name='trips',
            bin_col_name='distance_bin',
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'trip_distance_{dataset_name}'] = distance_summary
        logger.info(f"  ✓ Generated trip distance distribution for {dataset_name}")
    
    # Trip duration/time distribution
    if 'time' in trip_data.columns or 'duration' in trip_data.columns:
        time_col = 'duration' if 'duration' in trip_data.columns else 'time'
        
        duration_summary = calculate_binned_summary(
            trip_data,
            value_col=time_col,
            bins=[0, 5, 10, 15, 30, 60, 10000],
            labels=['0-5 min', '5-10 min', '10-15 min', '15-30 min', '30-60 min', '60+ min'],
            weight_col=weight_col,
            count_col_name='trips',
            bin_col_name='duration_bin',
            additional_cols={'dataset': dataset_name}
        )
        
        summaries[f'trip_duration_{dataset_name}'] = duration_summary
        logger.info(f"  ✓ Generated trip duration distribution for {dataset_name}")
    
    return summaries


def generate_trip_count_by_household_summary(trip_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate trip generation by household summaries.
    
    Args:
        trip_data: Trip dataframe with household information
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of summary name to DataFrame
    """
    summaries = {}
    
    if trip_data is None or len(trip_data) == 0:
        logger.warning(f"  ⚠ No trip data for {dataset_name}")
        return summaries
    
    # Trips per household
    hh_id_col = None
    if 'hh_id' in trip_data.columns:
        hh_id_col = 'hh_id'
    elif 'household_id' in trip_data.columns:
        hh_id_col = 'household_id'
    
    if hh_id_col is None:
        logger.debug(f"  ⓘ No household ID column for {dataset_name}")
        return summaries
    
    trips_per_hh = (trip_data.groupby(hh_id_col)
                   .size()
                   .reset_index(name='trip_count'))
    
    trip_gen_summary = (trips_per_hh.groupby('trip_count')
                       .size()
                       .reset_index(name='households'))
    trip_gen_summary['share'] = trip_gen_summary['households'] / trip_gen_summary['households'].sum() * 100
    trip_gen_summary['dataset'] = dataset_name
    
    summaries[f'trip_generation_{dataset_name}'] = trip_gen_summary
    logger.info(f"  ✓ Generated trip generation summary for {dataset_name}")
    
    return summaries


def generate_all_trip_summaries(trip_data: pd.DataFrame, dataset_name: str, weight_col: Optional[str] = None) -> Dict[str, pd.DataFrame]:
    """
    Generate all trip-level summaries.
    
    Args:
        trip_data: Trip dataframe
        dataset_name: Name identifier for this dataset
        weight_col: Name of weight column for weighted calculations
        
    Returns:
        Dictionary of all trip summary tables
    """
    logger.info(f"Generating trip summaries for {dataset_name}...")
    
    all_summaries = {}
    
    # Trip mode choice
    all_summaries.update(generate_trip_mode_summary(trip_data, dataset_name, weight_col))
    
    # Trip purpose
    all_summaries.update(generate_trip_purpose_summary(trip_data, dataset_name, weight_col))
    
    # Trip timing
    all_summaries.update(generate_trip_timing_summary(trip_data, dataset_name, weight_col))
    
    # Trip distance/duration
    all_summaries.update(generate_trip_length_summary(trip_data, dataset_name, weight_col))
    
    # Trip generation
    all_summaries.update(generate_trip_count_by_household_summary(trip_data, dataset_name, weight_col))
    
    logger.info(f"  ✓ Generated {len(all_summaries)} trip summary tables")
    
    return all_summaries
