"""
Summary Utilities - Helper functions for weighted calculations

Provides utility functions to support weighted summaries across all
validation summary modules.
"""

import pandas as pd
import logging
from typing import Optional, List, Union, Dict, Tuple

logger = logging.getLogger(__name__)


def calculate_weighted_summary(
    df: pd.DataFrame,
    group_cols: Union[str, List[str]],
    weight_col: Optional[str] = None,
    count_col_name: str = 'count',
    calculate_share: bool = True,
    share_col_name: str = 'share',
    share_group_cols: Optional[Union[str, List[str]]] = None,
    additional_cols: Optional[Dict[str, any]] = None
) -> pd.DataFrame:
    """
    Calculate weighted or unweighted counts and shares grouped by one or more dimensions.
    
    This is the core reusable function for generating summary tables. It handles:
    - Single or multiple grouping columns
    - Weighted (expansion factor) or unweighted counts
    - Optional share/percentage calculation (overall or within groups)
    - Additional constant columns (e.g., dataset name, geography)
    
    Args:
        df: Input dataframe
        group_cols: Column name(s) to group by (string or list of strings)
        weight_col: Name of weight column for weighted calculations. If None, uses unweighted counts.
        count_col_name: Name for the output count column (default: 'count')
        calculate_share: Whether to calculate share/percentage (default: True)
        share_col_name: Name for the output share column (default: 'share')
        share_group_cols: Column(s) to group by when calculating shares for within-group percentages.
                         If None, calculates overall share. Useful for crosstabs where you want
                         shares within each row/column group.
        additional_cols: Dictionary of additional columns to add (e.g., {'dataset': 'model_run_1', 'geography': 'Regional'})
    
    Returns:
        DataFrame with grouped counts and optional shares
        
    Examples:
        # Simple unweighted count by one dimension with overall share
        >>> calculate_weighted_summary(df, 'income_category', count_col_name='households')
        
        # Weighted count by two dimensions with overall share
        >>> calculate_weighted_summary(
        ...     df, 
        ...     ['income_category', 'num_vehicles'],
        ...     weight_col='sample_rate',
        ...     count_col_name='households'
        ... )
        
        # Crosstab with within-group shares (% of each income category with 0,1,2+ cars)
        >>> calculate_weighted_summary(
        ...     df,
        ...     ['income_category', 'num_vehicles'],
        ...     weight_col='sample_rate',
        ...     count_col_name='households',
        ...     share_group_cols='income_category'  # Share within each income group
        ... )
        
        # Multiple dimensions with metadata
        >>> calculate_weighted_summary(
        ...     df,
        ...     ['purpose', 'mode'],
        ...     weight_col='sample_rate',
        ...     count_col_name='trips',
        ...     share_group_cols='purpose',  # Share of modes within each purpose
        ...     additional_cols={'dataset': '2023_v05', 'geography': 'Regional'}
        ... )
    """
    # Ensure group_cols is a list
    if isinstance(group_cols, str):
        group_cols = [group_cols]
    
    # Validate that grouping columns exist
    missing_cols = [col for col in group_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Grouping columns not found in dataframe: {missing_cols}")
    
    # Check if we should use weights
    use_weights = weight_col is not None and weight_col in df.columns
    
    if use_weights:
        # Weighted count: sum of weight column
        summary = (df.groupby(group_cols, observed=True)[weight_col]
                   .sum()
                   .reset_index(name=count_col_name))
    else:
        # Unweighted count: size of groups
        summary = (df.groupby(group_cols, observed=True)
                   .size()
                   .reset_index(name=count_col_name))
    
    # Calculate share/percentage if requested
    if calculate_share:
        if share_group_cols is not None:
            # Within-group shares (e.g., % within each income category)
            if isinstance(share_group_cols, str):
                share_group_cols = [share_group_cols]
            
            # Validate share grouping columns
            missing_share_cols = [col for col in share_group_cols if col not in summary.columns]
            if missing_share_cols:
                raise ValueError(f"Share grouping columns not found in summary: {missing_share_cols}")
            
            # Calculate total within each group
            group_totals = summary.groupby(share_group_cols, observed=True)[count_col_name].transform('sum')
            summary[share_col_name] = (summary[count_col_name] / group_totals * 100).fillna(0.0)
        else:
            # Overall share
            total = summary[count_col_name].sum()
            if total > 0:
                summary[share_col_name] = summary[count_col_name] / total * 100
            else:
                summary[share_col_name] = 0.0
    
    # Add additional constant columns
    if additional_cols:
        for col_name, col_value in additional_cols.items():
            summary[col_name] = col_value
    
    return summary


def calculate_binned_summary(
    df: pd.DataFrame,
    value_col: str,
    bins: List[float],
    labels: List[str],
    weight_col: Optional[str] = None,
    count_col_name: str = 'count',
    calculate_share: bool = True,
    share_col_name: str = 'share',
    bin_col_name: str = 'bin',
    additional_cols: Optional[Dict[str, any]] = None
) -> pd.DataFrame:
    """
    Calculate weighted summary for continuous variables using binning.
    
    Useful for distance, duration, age, etc. distributions.
    
    Args:
        df: Input dataframe
        value_col: Column containing continuous values to bin
        bins: List of bin edges (e.g., [0, 5, 10, 20, 100])
        labels: List of bin labels (e.g., ['0-5', '5-10', '10-20', '20+'])
        weight_col: Name of weight column for weighted calculations
        count_col_name: Name for the output count column
        calculate_share: Whether to calculate share/percentage
        share_col_name: Name for the output share column
        bin_col_name: Name for the bin column in output
        additional_cols: Dictionary of additional columns to add
    
    Returns:
        DataFrame with binned counts and optional shares
        
    Example:
        >>> calculate_binned_summary(
        ...     df,
        ...     value_col='distance',
        ...     bins=[0, 5, 10, 20, 50, 1000],
        ...     labels=['0-5 miles', '5-10 miles', '10-20 miles', '20-50 miles', '50+ miles'],
        ...     weight_col='sample_rate',
        ...     count_col_name='trips'
        ... )
    """
    # Validate inputs
    if value_col not in df.columns:
        raise ValueError(f"Value column '{value_col}' not found in dataframe")
    
    if len(labels) != len(bins) - 1:
        raise ValueError(f"Number of labels ({len(labels)}) must be one less than bins ({len(bins)})")
    
    # Create binned column
    df_binned = df.copy()
    df_binned[bin_col_name] = pd.cut(
        df_binned[value_col],
        bins=bins,
        labels=labels,
        right=False
    )
    
    # Use the standard weighted summary function
    summary = calculate_weighted_summary(
        df_binned,
        group_cols=bin_col_name,
        weight_col=weight_col,
        count_col_name=count_col_name,
        calculate_share=calculate_share,
        share_col_name=share_col_name,
        additional_cols=additional_cols
    )
    
    return summary


def weighted_groupby_count(df: pd.DataFrame, 
                          groupby_cols: List[str], 
                          weight_col: Optional[str] = None,
                          count_name: str = 'count') -> pd.DataFrame:
    """
    Perform weighted or unweighted groupby count.
    
    Args:
        df: Input dataframe
        groupby_cols: Column(s) to group by
        weight_col: Weight column name (if None, uses unweighted count)
        count_name: Name for the count column in result
        
    Returns:
        DataFrame with groupby results
    """
    if weight_col is not None and weight_col in df.columns:
        # Weighted count - sum the weights
        result = (df.groupby(groupby_cols)[weight_col]
                   .sum()
                   .reset_index(name=count_name))
    else:
        # Unweighted count - just count rows
        result = (df.groupby(groupby_cols)
                   .size()
                   .reset_index(name=count_name))
    
    return result


def add_share_column(df: pd.DataFrame, 
                    count_col: str = 'count',
                    share_col: str = 'share',
                    percentage: bool = True) -> pd.DataFrame:
    """
    Add share/percentage column based on counts.
    
    Args:
        df: DataFrame with count column
        count_col: Name of count column
        share_col: Name for new share column
        percentage: If True, multiply by 100 for percentage
        
    Returns:
        DataFrame with added share column
    """
    total = df[count_col].sum()
    
    if total > 0:
        df[share_col] = df[count_col] / total
        if percentage:
            df[share_col] = df[share_col] * 100
    else:
        df[share_col] = 0.0
    
    return df


def weighted_mean(df: pd.DataFrame,
                 value_col: str,
                 weight_col: Optional[str] = None) -> float:
    """
    Calculate weighted or unweighted mean.
    
    Args:
        df: Input dataframe
        value_col: Column to average
        weight_col: Weight column (if None, uses unweighted mean)
        
    Returns:
        Weighted or unweighted mean
    """
    if weight_col is not None and weight_col in df.columns:
        # Weighted mean: sum(value * weight) / sum(weight)
        weighted_sum = (df[value_col] * df[weight_col]).sum()
        weight_sum = df[weight_col].sum()
        
        if weight_sum > 0:
            return weighted_sum / weight_sum
        else:
            return 0.0
    else:
        # Unweighted mean
        return df[value_col].mean()


def get_weight_column(df: pd.DataFrame, 
                     weight_col: Optional[str] = None,
                     default_weight: float = 1.0) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Ensure dataframe has a weight column, adding default if needed.
    
    Args:
        df: Input dataframe
        weight_col: Requested weight column name
        default_weight: Default weight value if column missing
        
    Returns:
        (dataframe with weight column, actual weight column name)
    """
    # If no weight column requested, return as-is
    if weight_col is None:
        return df, None
    
    # If weight column exists, use it
    if weight_col in df.columns:
        return df, weight_col
    
    # Weight column requested but missing - add default
    logger.warning(f"Weight column '{weight_col}' not found, using default weight={default_weight}")
    df = df.copy()
    df[weight_col] = default_weight
    
    return df, weight_col


def bin_continuous_variable(
    df: pd.DataFrame,
    value_col: str,
    bins: Union[List[float], int],
    labels: Optional[List[str]] = None,
    bin_col_name: Optional[str] = None
) -> pd.DataFrame:
    """
    Bin a continuous variable into categories.
    
    This is a generalized binning function that can be used for income, distance, duration,
    age, or any other continuous variable that needs to be grouped for summary tables.
    
    Args:
        df: Input dataframe
        value_col: Name of the column containing continuous values to bin
        bins: Either:
            - List of bin edges (e.g., [0, 25000, 50000, 100000, 1000000])
            - Integer for number of equal-width bins
        labels: Optional list of labels for the bins. If None, uses default range labels.
                Length must be len(bins)-1
        bin_col_name: Name for the output binned column. If None, uses f'{value_col}_bin'
    
    Returns:
        DataFrame with added binned column
        
    Examples:
        # Income bins with custom labels
        df = bin_continuous_variable(
            df, 'income', 
            bins=[0, 30000, 60000, 100000, 150000, 1000000],
            labels=['<30K', '30-60K', '60-100K', '100-150K', '150K+'],
            bin_col_name='income_category'
        )
        
        # Distance bins with automatic labels
        df = bin_continuous_variable(
            df, 'distance',
            bins=[0, 1, 3, 5, 10, 20, 1000],
            bin_col_name='distance_bin'
        )
        
        # Age bins into equal-width categories
        df = bin_continuous_variable(df, 'age', bins=10)
    """
    df = df.copy()
    
    if bin_col_name is None:
        bin_col_name = f'{value_col}_bin'
    
    # Handle missing values
    if value_col not in df.columns:
        logger.error(f"Column '{value_col}' not found in dataframe")
        return df
    
    try:
        # Use pandas cut for binning
        df[bin_col_name] = pd.cut(
            df[value_col],
            bins=bins,
            labels=labels,
            include_lowest=True,
            duplicates='drop'
        )
        
        # Convert to string for consistent handling
        df[bin_col_name] = df[bin_col_name].astype(str)
        
        logger.debug(f"  → Binned '{value_col}' into {df[bin_col_name].nunique()} categories")
        
    except Exception as e:
        logger.error(f"  ✗ Error binning column '{value_col}': {e}")
        # Create a fallback bin with the original values
        df[bin_col_name] = df[value_col].astype(str)
    
    return df


def log_weight_info(dataset_name: str, 
                   weight_col: Optional[str],
                   df: pd.DataFrame):
    """
    Log information about weight usage.
    
    Args:
        dataset_name: Name of dataset
        weight_col: Weight column name or None
        df: DataFrame to check
    """
    if weight_col is None:
        logger.info(f"  ℹ Using unweighted counts for {dataset_name}")
    elif weight_col in df.columns:
        total_weight = df[weight_col].sum()
        logger.info(f"  ℹ Using weighted counts for {dataset_name} (total weight={total_weight:,.0f})")
    else:
        logger.warning(f"  ⚠ Weight column '{weight_col}' not found in {dataset_name}")
