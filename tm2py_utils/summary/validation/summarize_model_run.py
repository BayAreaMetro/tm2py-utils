"""
Simple CTRAMP Model Run Summarizer

Generates validation summaries for a SINGLE model run directory.
Designed to be transparent, easy to understand, and junior analyst-friendly.

Usage:
    python summarize_model_run.py <ctramp_dir> [--output <output_dir>]
    
Example:
    python summarize_model_run.py "C:/model_runs/2015_base/ctramp_output" --output "C:/summaries/2015_base"
    
The tool will:
    1. Load CTRAMP output files (households, persons, tours, trips)
    2. Apply data model schema and value mappings from YAML config
    3. Generate summaries defined in ctramp_data_model.yaml
    4. Save individual CSV files for each summary
    
All processing steps are logged clearly so you can see exactly what's happening.
"""

import pandas as pd
import yaml
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import sys

# Configure logging for transparent output
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # Simple format - just the message
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ASCII-safe symbols for Windows compatibility
CHECK = '[OK]'
WARN = '[WARN]'
ERROR = '[ERROR]'
INFO = '[INFO]'
INFO = '[INFO]'


def load_data_model(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load the CTRAMP data model configuration from YAML.
    This defines file patterns, column mappings, value labels, and summaries.
    
    Args:
        config_path: Path to config file. If None, uses default ctramp_data_model.yaml
    
    Returns:
        Dictionary containing complete data model configuration
    """
    logger.info("=" * 80)
    logger.info("STEP 1: Loading Data Model Configuration")
    logger.info("=" * 80)
    
    # Use provided path or default
    if config_path is None:
        config_path = Path(__file__).parent / 'data_model' / 'ctramp_data_model.yaml'
    
    logger.info(f"Config File: {config_path}")
    
    if not config_path.exists():
        logger.error(f"{ERROR} Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Extract and display metadata
    metadata = config.get('metadata', {})
    data_model_type = metadata.get('data_model_type', 'unknown')
    version = metadata.get('version', 'unknown')
    description = metadata.get('description', '')
    
    logger.info(f"Data Model Type: {data_model_type}")
    logger.info(f"Version: {version}")
    if description:
        logger.info(f"Description: {description}")
    
    logger.info(f"{CHECK} Loaded configuration with {len(config.get('summaries', {}))} summary definitions")  
    logger.info("")
    return config


def find_latest_iteration_file(ctramp_dir: Path, pattern: str) -> Optional[Path]:
    """
    Find the file matching the pattern with the highest iteration number.
    Supports both model format (personData_{iteration}.csv) and survey format (PersonData.csv).
    
    Args:
        ctramp_dir: Directory containing CTRAMP output files
        pattern: File pattern like "personData_{iteration}.csv"
    
    Returns:
        Path to the file with highest iteration number, or None if not found
    """
    # If no {iteration} placeholder, just look for exact match
    if '{iteration}' not in pattern:
        file_path = ctramp_dir / pattern
        return file_path if file_path.exists() else None
    
    # Extract base pattern (e.g., "personData_" and ".csv")
    base = pattern.split('{iteration}')[0]
    ext = pattern.split('{iteration}')[1]
    
    # Find all matching files with iteration numbers (model format)
    matches = list(ctramp_dir.glob(f"{base}*{ext}"))
    
    # If no matches with iteration, try survey format (CamelCase, no iteration)
    if not matches:
        # Try converting to CamelCase survey format
        # e.g., "personData_" -> "PersonData"
        survey_patterns = [
            base.rstrip('_'),  # Remove trailing underscore
            base.rstrip('_').title().replace('Data', 'Data'),  # Title case
            base.rstrip('_')[0].upper() + base.rstrip('_')[1:],  # Capitalize first letter
        ]
        
        for survey_base in survey_patterns:
            survey_file = ctramp_dir / f"{survey_base}{ext}"
            if survey_file.exists():
                return survey_file
        
        return None
    
    # If there's only one match, return it
    if len(matches) == 1:
        return matches[0]
    
    # Extract iteration numbers and find max
    iterations = []
    for match in matches:
        try:
            # Extract the number between base and extension
            iter_str = match.name.replace(base, '').replace(ext, '')
            iterations.append((int(iter_str), match))
        except ValueError:
            continue
    
    if iterations:
        return max(iterations, key=lambda x: x[0])[1]
    
    return matches[0]  # Fallback to first match


def load_ctramp_data(ctramp_dir: Path, data_model: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """
    Load CTRAMP output files into dataframes with proper column names.
    
    Args:
        ctramp_dir: Directory containing CTRAMP output CSV files
        data_model: Data model configuration with input schema
    
    Returns:
        Dictionary mapping table names to dataframes
    """
    logger.info("=" * 80)
    logger.info("STEP 2: Loading CTRAMP Output Files")
    logger.info("=" * 80)
    logger.info(f"Source directory: {ctramp_dir}")
    logger.info("")
    
    data = {}
    input_schema = data_model['input_schema']
    
    for table_name, schema in input_schema.items():
        logger.info(f"Loading {table_name}...")
        
        # Skip geography_lookup - it's a static reference file, not CTRAMP output
        if table_name == 'geography_lookup':
            logger.info(f"  {INFO} Skipping {table_name} (static reference file, not CTRAMP output)")
            logger.info("")
            continue
        
        # Find the file
        file_pattern = schema['file_pattern']
        file_path = find_latest_iteration_file(ctramp_dir, file_pattern)
        
        if file_path is None:
            logger.warning(f"  {WARN} File not found matching pattern: {file_pattern}")
            continue
        
        logger.info(f"  File: {file_path.name}")
        
        # Load the CSV
        df = pd.read_csv(file_path)
        logger.info(f"  Rows: {len(df):,}")
        
        # Rename columns to canonical names
        required_cols = schema['columns']['required']
        optional_cols = schema['columns'].get('optional', {})
        all_col_mappings = {**required_cols, **optional_cols}
        
        # Check for missing required columns
        missing_required = []
        for canonical_name, file_col_name in required_cols.items():
            if file_col_name not in df.columns:
                missing_required.append(f"{canonical_name} (expected '{file_col_name}')")
        
        if missing_required:
            logger.warning(f"  {WARN} Missing required columns: {', '.join(missing_required)}")
            logger.warning(f"  {WARN} Available columns: {', '.join(sorted(df.columns.tolist()))}")
        
        # Only rename columns that exist in the file
        rename_map = {v: k for k, v in all_col_mappings.items() if v in df.columns}
        df = df.rename(columns=rename_map)
        
        logger.info(f"  Columns: {len(df.columns)}")
        logger.info(f"  {CHECK} Loaded and standardized")
        logger.info("")
        
        data[table_name] = df
    
    return data

def load_enriched_output(enriched_output_dir: Path, data_model):
    """
    Load enriched output files into dataframe with proper name

    Args: 
        enriched_output_dir: Directory containing enriched output parquet files

    """
    logger.info("=" * 80)
    logger.info("STEP 2: Loading Enriched Output Files")
    logger.info("=" * 80)
    logger.info(f"Source directory: {enriched_output_dir}")
    logger.info("")    

    data = {}
    input_schema = data_model['enriched_input_schema']
    
    for table_name, schema in input_schema.items():
        logger.info(f"Loading {table_name}...")
        
        # Skip geography_lookup - it's a static reference file, not CTRAMP output
        if table_name == 'geography_lookup':
            logger.info(f"  {INFO} Skipping {table_name} (static reference file, not CTRAMP output)")
            logger.info("")
            continue
        
        # Find the file
        file_pattern = schema['file_pattern']
        file_path = enriched_output_dir / file_pattern
        
        if file_path is None:
            logger.warning(f"  {WARN} File not found matching pattern: {file_pattern}")
            continue
        
        logger.info(f"  File: {file_path.name}")
        
        # Load the CSV
        df = pd.read_parquet(file_path)
        logger.info(f"  Rows: {len(df):,}")
        
        # TODO: Determine if we need to standardized the columns
        # Rename columns to canonical names
        required_cols = schema['columns']['required']
        optional_cols = schema['columns'].get('optional', {})
        all_col_mappings = {**required_cols, **optional_cols}
        
        # Check for missing required columns
        missing_required = []
        for canonical_name, file_col_name in required_cols.items():
            if file_col_name not in df.columns:
                missing_required.append(f"{canonical_name} (expected '{file_col_name}')")
        
        if missing_required:
            logger.warning(f"  {WARN} Missing required columns: {', '.join(missing_required)}")
            logger.warning(f"  {WARN} Available columns: {', '.join(sorted(df.columns.tolist()))}")
        
        # Only rename columns that exist in the file
        rename_map = {v: k for k, v in all_col_mappings.items() if v in df.columns}
        df = df.rename(columns=rename_map)
        
        logger.info(f"  Columns: {len(df.columns)}")
        logger.info(f"  {CHECK} Loaded and standardized")
        logger.info("")

        data[table_name] = df

    return data


def apply_value_labels(data: Dict[str, pd.DataFrame], value_mappings: Dict[str, Dict]) -> Dict[str, pd.DataFrame]:
    """
    Apply human-readable labels to coded values (e.g., mode 1 → "drive alone").
    Creates new columns with "_name" suffix for labeled versions.
    
    Args:
        data: Dictionary of dataframes
        value_mappings: Value mapping configuration
    
    Returns:
        Updated dictionary with label columns added
    """
    logger.info("=" * 80)
    logger.info("STEP 3: Applying Value Labels")
    logger.info("=" * 80)
    
    for table_name, df in data.items():
        logger.info(f"{table_name}:")
        
        for col in df.columns:
            # Determine mapping key (handle special cases like tour_mode → transportation_mode)
            mapping_key = col
            if col in ['tour_mode', 'trip_mode']:
                mapping_key = 'transportation_mode'
            
            if mapping_key in value_mappings:
                mapping_dict = value_mappings[mapping_key]
                
                # Check if column is numeric or text
                is_numeric = pd.api.types.is_numeric_dtype(df[col])
                
                # Extract the actual mapping (could be under 'values' key or direct text_values)
                if is_numeric and isinstance(mapping_dict, dict) and 'values' in mapping_dict:
                    # Numeric column with numeric-to-text mapping
                    mapping = mapping_dict['values']
                    label_col = f"{col}_name"
                    df[label_col] = df[col].map(mapping)
                    logger.info(f"  [OK] Labeled '{col}' -> '{label_col}' ({len(mapping)} values)")
                elif not is_numeric and isinstance(mapping_dict, dict) and 'text_values' in mapping_dict:
                    # Text column - just copy it to _name column
                    label_col = f"{col}_name"
                    df[label_col] = df[col]
                    logger.info(f"  [OK] Copied '{col}' -> '{label_col}' (already text values)")
                else:
                    # Column exists but mapping doesn't match data type
                    continue
        
        logger.info("")
    
    return data


def apply_aggregations(data: Dict[str, pd.DataFrame], aggregation_specs: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """
    Apply aggregation mappings to create simplified categorical columns.
    Creates new columns with "_agg" suffix (e.g., tour_mode_agg).
    
    Args:
        data: Dictionary of dataframes
        aggregation_specs: Aggregation specification
    
    Returns:
        Updated dictionary with aggregated columns added
    """
    logger.info("=" * 80)
    logger.info("STEP 4: Creating Aggregated Categories")
    logger.info("=" * 80)
    
    for table_name, df in data.items():
        logger.info(f"{table_name}:")
        
        for agg_name, agg_spec in aggregation_specs.items():
            if 'apply_to' not in agg_spec or 'mapping' not in agg_spec:
                continue
            
            apply_to_cols = agg_spec['apply_to']
            mapping = agg_spec['mapping']
            
            for col in apply_to_cols:
                if col not in df.columns:
                    continue
                
                agg_col = f"{col}_agg"
                df[agg_col] = df[col].map(mapping)
                logger.info(f"  {CHECK} Aggregated '{col}' -> '{agg_col}' ({len(set(mapping.values()))} categories)")
        
        logger.info("")
    
    return data


def apply_bins(data: Dict[str, pd.DataFrame], bin_configs: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """
    Bin continuous variables (e.g., age → age groups, distance → distance bands).
    Creates new columns with "_bin" suffix.
    
    Args:
        data: Dictionary of dataframes
        bin_configs: Binning configuration
    
    Returns:
        Updated dictionary with binned columns added
    """
    logger.info("=" * 80)
    logger.info("STEP 5: Creating Binned Variables")
    logger.info("=" * 80)
    
    for table_name, df in data.items():
        logger.info(f"{table_name}:")
        
        for col, bin_spec in bin_configs.items():
            if col not in df.columns:
                continue
            
            breaks = bin_spec['breaks']
            labels = bin_spec.get('labels', None)
            bin_col = f"{col}_bin"
            
            df[bin_col] = pd.cut(
                df[col],
                bins=breaks,
                labels=labels,
                include_lowest=True,
                right=False
            )
            logger.info(f"  {CHECK} Binned '{col}' -> '{bin_col}' ({len(breaks)-1} bins)")
        
        logger.info("")
    
    return data


def expand_time_periods_summary(df: pd.DataFrame, summary_config: Dict[str, Any]) -> pd.DataFrame:
    """
    Special handler for 'persons touring by time' summary.
    
    For each tour, expand from start_period to end_period to show which time
    periods the person is touring. This answers: "How many tours are actively
    happening during time period X?"
    
    Args:
        df: Tours dataframe with start_period, end_period
        summary_config: Summary configuration
    
    Returns:
        Summary with one row per time_period × group_by combination
    """
    group_cols = summary_config.get('group_by', [])
    if isinstance(group_cols, str):
        group_cols = [group_cols]
    
    weight_field = summary_config.get('weight_field', 'sample_rate')
    count_name = summary_config.get('count_name', 'tours_active')
    time_range = summary_config.get('time_range', [1, 40])
    
    # Prepare result container
    results = []
    
    # For each time period, find tours active during that period
    for time_period in range(time_range[0], time_range[1] + 1):
        # Filter tours active during this time period
        mask = (df['start_period'] <= time_period) & (df['end_period'] >= time_period)
        active_tours = df[mask].copy()
        
        if len(active_tours) == 0:
            continue
        
        # Group by purpose and sum weighted tours
        if group_cols:
            if weight_field in active_tours.columns:
                period_summary = active_tours.groupby(group_cols)[weight_field].sum().reset_index()
                period_summary = period_summary.rename(columns={weight_field: count_name})
            else:
                period_summary = active_tours.groupby(group_cols).size().reset_index(name=count_name)
        else:
            if weight_field in active_tours.columns:
                period_summary = pd.DataFrame({
                    count_name: [active_tours[weight_field].sum()]
                })
            else:
                period_summary = pd.DataFrame({
                    count_name: [len(active_tours)]
                })
        
        period_summary['time_period'] = time_period
        results.append(period_summary)
    
    if not results:
        # Return empty dataframe with correct schema
        cols = group_cols + ['time_period', count_name]
        return pd.DataFrame(columns=cols)
    
    # Combine all time periods
    summary = pd.concat(results, ignore_index=True)
    
    return summary


def generate_summary(df: pd.DataFrame, summary_config: Dict[str, Any], summary_name: str) -> pd.DataFrame:
    """
    Generate a single summary based on configuration.
    
    Args:
        df: Source dataframe
        summary_config: Summary specification from YAML
        summary_name: Name of the summary
    
    Returns:
        Summary dataframe
    """
    # Apply filter if specified
    if 'filter' in summary_config:
        filter_expr = summary_config['filter']
        df = df.query(filter_expr)
    
    # Get grouping columns
    group_cols = summary_config['group_by']
    if isinstance(group_cols, str):
        group_cols = [group_cols]
    
    # Get weight field
    weight_field = summary_config.get('weight_field', None)
    count_name = summary_config.get('count_name', 'count')
    
    # Build aggregation dictionary
    agg_dict = {}
    
    # Add count/weighted count
    if weight_field and weight_field in df.columns:
        agg_dict[weight_field] = 'sum'
    else:
        # For unweighted counts, we'll add after groupby
        pass
    
    # Add custom aggregations if specified
    if 'aggregations' in summary_config:
        for agg_name, source_col in summary_config['aggregations'].items():
            if source_col in df.columns:
                # Check if it's a total or mean
                if agg_name.startswith('total_') or agg_name.startswith('sum_'):
                    agg_dict[source_col] = 'sum'
                elif agg_name.startswith('mean_') or agg_name.startswith('avg_'):
                    agg_dict[source_col] = 'mean'
                else:
                    # Default to mean
                    agg_dict[source_col] = 'mean'
    
    # Generate summary
    if agg_dict:
        summary = df.groupby(group_cols).agg(agg_dict).reset_index()
        
        # Rename weight field to count name
        if weight_field and weight_field in summary.columns:
            summary = summary.rename(columns={weight_field: count_name})
        
        # Rename custom aggregations
        if 'aggregations' in summary_config:
            rename_map = {}
            for agg_name, source_col in summary_config['aggregations'].items():
                if source_col in summary.columns:
                    rename_map[source_col] = agg_name
            summary = summary.rename(columns=rename_map)
    else:
        # Simple count
        summary = df.groupby(group_cols).size().reset_index(name=count_name)
    
    # Calculate shares
    # Don't calculate shares if we have aggregations (mean/sum calculations)
    # because shares of counts don't make sense when showing averages
    has_aggregations = 'aggregations' in summary_config and summary_config['aggregations']
    
    if 'share_within' in summary_config:
        # Calculate shares within groups
        share_within = summary_config['share_within']
        if isinstance(share_within, str):
            share_within = [share_within]
        
        totals = summary.groupby(share_within)[count_name].transform('sum')
        summary['share'] = summary[count_name] / totals
    elif not has_aggregations and summary_config.get('calculate_share', True):
        # Calculate overall shares (for distribution summaries without aggregations)
        total = summary[count_name].sum()
        if total > 0:
            summary['share'] = summary[count_name] / total
    
    return summary


def generate_all_summaries(data: Dict[str, pd.DataFrame], summaries_config: Dict[str, Any], output_dir: Path):
    """
    Generate all summaries defined in the data model and save to CSV files.
    
    Args:
        data: Dictionary of loaded dataframes
        summaries_config: Summaries configuration from data model
        output_dir: Directory to save summary CSV files
    """
    logger.info("=" * 80)
    logger.info("STEP 6: Generating Summaries")
    logger.info("=" * 80)
    logger.info(f"Output directory: {output_dir}")
    logger.info("")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    summary_count = 0
    
    for summary_name, summary_config in summaries_config.items():
        logger.info(f"[{summary_count + 1}] {summary_name}")
        
        # Get source data
        data_source = summary_config['data_source']
        if isinstance(data_source, list):
            # Use the first available data source
            for src in data_source:
                if src in data:
                    df = data[src]
                    break
            else:
                logger.warning(f"  {WARN} None of the data sources {data_source} found, skipping")
                continue
        else:
            if data_source not in data:
                logger.warning(f"  {WARN} Data source '{data_source}' not found, skipping")
                continue
        
            df = data[data_source]
        logger.info(f"  Source: {data_source} ({len(df):,} rows)")
        
        # Generate summary
        try:
            # Check for special handler
            special_handler = summary_config.get('special_handler', None)
            
            if special_handler == 'expand_time_periods':
                summary_df = expand_time_periods_summary(df, summary_config)
            else:
                summary_df = generate_summary(df, summary_config, summary_name)
            
            logger.info(f"  Result: {len(summary_df):,} rows × {len(summary_df.columns)} columns")
            
            # Save to CSV
            output_path = output_dir / f"{summary_name}.csv"
            summary_df.to_csv(output_path, index=False)
            logger.info(f"  {CHECK} Saved: {output_path.name}")
            
            summary_count += 1
        except Exception as e:
            logger.error(f"  {ERROR} Failed: {e}")
        
        logger.info("")
    
    logger.info(f"Generated {summary_count} summaries")
    logger.info("")
    
    # Run validation on generated summaries
    logger.info("=" * 80)
    logger.info("STEP 7: Validating Summaries")
    logger.info("=" * 80)
    
    try:
        from validate_summaries import SummaryValidator
        validator = SummaryValidator(output_dir)
        issues, warnings = validator.validate_all()
        
        if issues:
            logger.warning(f"{WARN} Validation found {len(issues)} issues - review outputs carefully")
        elif warnings:
            logger.info(f"{CHECK} Validation passed with {len(warnings)} warnings")
        else:
            logger.info(f"{CHECK} All validation checks passed")
    except ImportError:
        logger.info(f"{INFO} Validation skipped (validate_summaries.py not found)")
    except Exception as e:
        logger.warning(f"{WARN} Validation failed: {e}")
    
    logger.info("")


def main():
    """Main execution function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Generate validation summaries for a CTRAMP model run',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('ctramp_dir', type=str, help='Path to CTRAMP output directory')
    parser.add_argument('--output', type=str, help='Output directory for summaries (default: ./summaries)')
    parser.add_argument('--config', type=str, 
                        help='Path to data model config YAML file (default: ctramp_data_model.yaml)')
    parser.add_argument('--enriched', action = 'store_true', help = 'Use enriched output mode')

    args = parser.parse_args()
    
    # Convert paths
    ctramp_dir = Path(args.ctramp_dir)
    output_dir = Path(args.output) if args.output else Path('./summaries')
    config_path = Path(args.config) if args.config else None
    
    # Validate input directory
    if not ctramp_dir.exists():
        logger.error(f"ERROR: Directory not found: {ctramp_dir}")
        sys.exit(1)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(" CTRAMP Model Run Summarizer ".center(80))
    logger.info("=" * 80)
    logger.info("")
    
    # Execute processing pipeline
    try:
        # 1. Load data model configuration
        data_model = load_data_model(config_path)
        
        # 2. Load CTRAMP files

        if args.enriched:
            data = load_enriched_output(ctramp_dir, data_model) 

            if not data:
                logger.error("ERROR: No data files loaded. Check file patterns and directory.")
                sys.exit(1)
            
            logger.info("=" * 80)
            logger.info("Skipping Steps 3 to 5")
            logger.info("=" * 80)

        else:
            data = load_ctramp_data(ctramp_dir, data_model)
            
            if not data:
                logger.error("ERROR: No data files loaded. Check file patterns and directory.")
                sys.exit(1)
            
            # 3. Apply value labels
            data = apply_value_labels(data, data_model.get('value_mappings', {}))
            
            # 4. Apply aggregations
            data = apply_aggregations(data, data_model.get('aggregation_specs', {}))
            
            # 5. Apply bins
            data = apply_bins(data, data_model.get('binning_specs', {}))
        
            
        # 6. Generate summaries
        generate_all_summaries(data, data_model.get('summaries', {}), output_dir)
        
        logger.info("=" * 80)
        logger.info("COMPLETE")
        logger.info("=" * 80)
        logger.info(f"{CHECK} All summaries saved to: {output_dir.absolute()}")
        logger.info("")
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("ERROR")
        logger.error("=" * 80)
        logger.error(f"{type(e).__name__}: {e}")
        logger.error("")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
