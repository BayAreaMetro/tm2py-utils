"""
Configuration-Driven Summary Generator

Generates validation summaries from YAML configuration without requiring Python code.
Analysts can define summaries declaratively in validation_config.yaml.

Example configuration:
    custom_summaries:
      - name: "trips_by_purpose"
        data_source: "individual_trips"
        group_by: "dest_purpose"
        weight_field: "sample_rate"
        count_name: "trips"
      
      - name: "auto_ownership_by_income"
        data_source: "households"
        group_by: ["income_category", "num_vehicles"]
        weight_field: "sample_rate"
        count_name: "households"
        share_within: "income_category"
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Union, Any
from pathlib import Path
import yaml

from .summary_utils import calculate_weighted_summary

logger = logging.getLogger(__name__)


# Load value mappings from data model
def load_value_mappings() -> Dict[str, Dict]:
    """Load value mappings from ctramp_data_model.yaml"""
    config_path = Path(__file__).parent.parent / 'data_model' / 'ctramp_data_model.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config.get('value_mappings', {})


class SummaryConfig:
    """Configuration for a single summary."""
    
    def __init__(self, config: Dict[str, Any]):
        self.name = config['name']
        self.data_source = config['data_source']
        self.group_by = config['group_by']
        self.weight_field = config.get('weight_field', None)
        self.count_name = config.get('count_name', 'count')
        self.share_within = config.get('share_within', None)
        self.filter = config.get('filter', None)
        self.bins = config.get('bins', None)
        self.description = config.get('description', '')
        
    def __repr__(self):
        return f"SummaryConfig(name={self.name}, data_source={self.data_source})"


def apply_binning(df: pd.DataFrame, bin_configs: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    """
    Apply binning to continuous variables based on configuration.
    
    Args:
        df: Input dataframe
        bin_configs: Dictionary mapping column names to binning specs
            Example: {
                'tour_distance': {
                    'breaks': [0, 5, 10, 20, 50, 999],
                    'labels': ['0-5mi', '5-10mi', '10-20mi', '20-50mi', '50+mi']
                }
            }
    
    Returns:
        DataFrame with new binned columns (original_column_name + '_bin')
    """
    df = df.copy()
    
    for col_name, bin_spec in bin_configs.items():
        if col_name not in df.columns:
            logger.warning(f"  ⚠ Column '{col_name}' not found for binning, skipping")
            continue
        
        breaks = bin_spec['breaks']
        labels = bin_spec.get('labels', None)
        
        # Create binned column
        binned_col_name = f"{col_name}_bin"
        
        try:
            df[binned_col_name] = pd.cut(
                df[col_name], 
                bins=breaks, 
                labels=labels, 
                include_lowest=True,
                right=False
            )
            logger.info(f"  ✓ Binned '{col_name}' → '{binned_col_name}' with {len(breaks)-1} bins")
        except Exception as e:
            logger.error(f"  ✗ Failed to bin '{col_name}': {e}")
    
    return df


def apply_filter(df: pd.DataFrame, filter_expr: str) -> pd.DataFrame:
    """
    Apply a filter expression to the dataframe.
    
    Args:
        df: Input dataframe
        filter_expr: Python expression to evaluate (e.g., "tour_purpose == 1")
    
    Returns:
        Filtered dataframe
    """
    try:
        filtered_df = df.query(filter_expr)
        logger.info(f"  ✓ Applied filter: '{filter_expr}' ({len(df)} → {len(filtered_df)} rows)")
        return filtered_df
    except Exception as e:
        logger.error(f"  ✗ Failed to apply filter '{filter_expr}': {e}")
        return df


def apply_value_labels(df: pd.DataFrame, value_mappings: Dict[str, Dict]) -> pd.DataFrame:
    """
    Apply human-readable labels to categorical columns based on value mappings.
    
    For columns with numeric codes (like tour_mode, trip_mode), creates a new
    column with '_name' suffix containing the human-readable labels.
    
    Args:
        df: Input dataframe
        value_mappings: Dictionary of value mappings from data model
    
    Returns:
        DataFrame with additional label columns
    """
    df = df.copy()
    
    for col in df.columns:
        # Check if this column has a mapping
        mapping_key = col
        
        # Handle both 'tour_mode' and 'trip_mode' using 'transportation_mode' mapping
        if col in ['tour_mode', 'trip_mode']:
            mapping_key = 'transportation_mode'
        
        if mapping_key not in value_mappings:
            continue
        
        mapping_spec = value_mappings[mapping_key]
        
        # Only apply if column contains numeric codes
        if 'values' not in mapping_spec:
            continue
        
        values_map = mapping_spec['values']
        
        # Convert keys to integers for mapping
        values_map = {int(k): v for k, v in values_map.items()}
        
        # Create labeled column
        label_col = f"{col}_name"
        df[label_col] = df[col].map(values_map)
        
        # Fill any unmapped values with original
        df[label_col] = df[label_col].fillna(df[col].astype(str))
        
        logger.info(f"  ✓ Applied labels to '{col}' → '{label_col}'")
    
    return df


def generate_summary_from_config(
    config: SummaryConfig,
    data: pd.DataFrame,
    dataset_name: str,
    value_mappings: Optional[Dict[str, Dict]] = None
) -> Optional[pd.DataFrame]:
    """
    Generate a summary from a configuration specification.
    
    Args:
        config: SummaryConfig object with summary specification
        data: Input dataframe (should match config.data_source)
        dataset_name: Name of the dataset for labeling
        value_mappings: Optional value mappings for applying labels
    
    Returns:
        Summary DataFrame or None if generation fails
    """
    logger.info(f"  Generating config-driven summary: {config.name}")
    
    if data is None or len(data) == 0:
        logger.warning(f"  ⚠ No data provided for {config.name}")
        return None
    
    # Make a copy to avoid modifying original
    df = data.copy()
    
    # Apply value labels first (before any transformations)
    if value_mappings is None:
        value_mappings = load_value_mappings()
    df = apply_value_labels(df, value_mappings)
    
    # Apply binning if specified
    if config.bins:
        df = apply_binning(df, config.bins)
        # Update group_by to use binned columns
        if isinstance(config.group_by, str) and config.group_by in config.bins:
            config.group_by = f"{config.group_by}_bin"
        elif isinstance(config.group_by, list):
            config.group_by = [
                f"{col}_bin" if col in config.bins else col 
                for col in config.group_by
            ]
    
    # Apply filter if specified
    if config.filter:
        df = apply_filter(df, config.filter)
        if len(df) == 0:
            logger.warning(f"  ⚠ Filter resulted in empty dataset for {config.name}")
            return None
    
    # Check if we should use labeled columns for grouping
    # If a column like 'trip_mode' exists and 'trip_mode_name' was created, use the name
    group_cols = [config.group_by] if isinstance(config.group_by, str) else config.group_by
    group_cols_with_labels = []
    for col in group_cols:
        label_col = f"{col}_name"
        if label_col in df.columns:
            group_cols_with_labels.append(label_col)
        else:
            group_cols_with_labels.append(col)
    
    # Validate group columns exist
    missing_cols = [col for col in group_cols_with_labels if col not in df.columns]
    if missing_cols:
        logger.error(f"  ✗ Missing columns in {config.data_source}: {missing_cols}")
        return None
    
    # Generate summary using existing utility (use labeled columns)
    try:
        # Also update share_within if it uses a labeled column
        share_within = config.share_within
        if share_within:
            share_cols = [share_within] if isinstance(share_within, str) else share_within
            share_cols_with_labels = []
            for col in share_cols:
                label_col = f"{col}_name"
                if label_col in df.columns:
                    share_cols_with_labels.append(label_col)
                else:
                    share_cols_with_labels.append(col)
            share_within = share_cols_with_labels if len(share_cols_with_labels) > 1 else share_cols_with_labels[0] if share_cols_with_labels else None
        
        summary = calculate_weighted_summary(
            df,
            group_cols=group_cols_with_labels,
            weight_col=config.weight_field,
            count_col_name=config.count_name,
            calculate_share=True,
            share_group_cols=share_within,
            additional_cols={'dataset': dataset_name}
        )
        
        # Rename labeled columns back to original names (trip_mode_name -> trip_mode)
        rename_dict = {}
        for col in summary.columns:
            if col.endswith('_name'):
                original = col.replace('_name', '')
                rename_dict[col] = original
        if rename_dict:
            summary = summary.rename(columns=rename_dict)
            logger.info(f"  ✓ Renamed label columns: {list(rename_dict.keys())}")
        
        logger.info(f"  ✓ Generated {config.name}: {len(summary)} rows")
        return summary
        
    except Exception as e:
        logger.error(f"  ✗ Failed to generate {config.name}: {e}")
        return None


def generate_all_config_driven_summaries(
    configs: List[Dict[str, Any]],
    data_dict: Dict[str, pd.DataFrame],
    dataset_name: str
) -> Dict[str, pd.DataFrame]:
    """
    Generate all summaries defined in configuration.
    
    Args:
        configs: List of summary configuration dictionaries from YAML
        data_dict: Dictionary mapping data source names to dataframes
            Example: {
                'households': households_df,
                'individual_tours': tours_df,
                'individual_trips': trips_df
            }
        dataset_name: Name of the dataset for labeling
    
    Returns:
        Dictionary mapping summary names to DataFrames
    """
    summaries = {}
    
    if not configs:
        logger.info(f"  No custom summaries configured for {dataset_name}")
        return summaries
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Generating {len(configs)} config-driven summaries for {dataset_name}")
    logger.info(f"{'='*80}")
    
    for config_dict in configs:
        try:
            config = SummaryConfig(config_dict)
            
            # Get data for this summary
            data = data_dict.get(config.data_source)
            if data is None:
                logger.warning(f"  ⚠ Data source '{config.data_source}' not available, skipping {config.name}")
                continue
            
            # Generate summary
            summary = generate_summary_from_config(config, data, dataset_name)
            
            if summary is not None:
                summary_key = f"{config.name}_{dataset_name}"
                summaries[summary_key] = summary
                
        except Exception as e:
            logger.error(f"  ✗ Error processing config for {config_dict.get('name', 'unknown')}: {e}")
            continue
    
    logger.info(f"\n✓ Generated {len(summaries)} config-driven summaries")
    return summaries


def create_dashboard_config_from_summary(
    config: SummaryConfig,
    csv_filename: str
) -> Dict[str, Any]:
    """
    Auto-generate dashboard chart configuration from summary config.
    
    Args:
        config: SummaryConfig object
        csv_filename: Name of the CSV file containing the summary data
    
    Returns:
        Dictionary with dashboard chart configuration
    """
    # Determine chart type based on grouping
    group_cols = [config.group_by] if isinstance(config.group_by, str) else config.group_by
    
    # Single dimension = simple bar chart
    if len(group_cols) == 1:
        chart_config = {
            'type': 'bar',
            'title': config.description or config.name.replace('_', ' ').title(),
            'props': {
                'dataset': csv_filename,
                'x': group_cols[0],
                'y': config.count_name,
                'groupBy': 'dataset',
                'stacked': False
            },
            'description': config.description or f'Distribution by {group_cols[0]}'
        }
    
    # Two dimensions = stacked/grouped bar chart
    else:
        chart_config = {
            'type': 'bar',
            'title': config.description or config.name.replace('_', ' ').title(),
            'props': {
                'dataset': csv_filename,
                'x': group_cols[0],
                'y': config.count_name,
                'groupBy': group_cols[1],
                'facetBy': 'dataset',
                'stacked': bool(config.share_within)  # Stack if calculating within-group shares
            },
            'description': config.description or f'Distribution by {" and ".join(group_cols)}'
        }
    
    return chart_config
