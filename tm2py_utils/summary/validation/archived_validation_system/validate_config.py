"""
Validation script to check configuration before generating summaries.

NOTE: This script checks against RAW data columns from CSV files.
Many summaries use DERIVED columns created during data processing,
so some warnings are expected. Focus on summaries that are commented out
or obviously incorrect.

Checks:
- All configured summaries have required data columns (basic check)
- All dashboard files reference existing CSV outputs
- All data source files exist
"""

import sys
from pathlib import Path
import yaml
import pandas as pd
from typing import Dict, List, Set
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Column mappings for each data source (based on actual files)
KNOWN_COLUMNS = {
    'persons': [
        'hh_id', 'person_id', 'person_num', 'age', 'gender', 'type',
        'value_of_time', 'transitSubsidy_choice', 'transitSubsidy_percent',
        'transitPass_choice', 'naicsCode', 'preTelecommuteCdap', 'telecommute',
        'cdap', 'imf_choice', 'inmf_choice', 'fp_choice', 'reimb_pct',
        'sampleRate', 'workDCLogsum', 'schoolDCLogsum',
        # Derived in processing:
        'sample_rate', 'person_type'
    ],
    'households': [
        'hh_id', 'home_zone_id', 'income', 'auto_ownership', 'household_size',
        'num_workers', 'sample_rate'
    ],
    'individual_tours': [
        'tour_id', 'person_id', 'tour_purpose', 'tour_mode', 'start_period',
        'end_period', 'tour_distance_miles', 'sample_rate'
    ],
    'individual_trips': [
        'trip_id', 'tour_id', 'person_id', 'trip_mode', 'trip_purpose',
        'trip_distance_miles', 'depart_period', 'sample_rate'
    ],
    'workplace_school': [
        'person_id', 'home_county', 'work_county', 'distance_miles',
        'time_minutes', 'tour_mode', 'sample_rate'
    ]
}


def load_config(config_path: Path) -> Dict:
    """Load validation configuration YAML."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def check_summary_columns(summaries: List[Dict]) -> List[str]:
    """
    Check if all configured summaries reference valid columns.
    
    Returns list of error messages.
    """
    errors = []
    
    for summary in summaries:
        name = summary.get('name', 'unknown')
        data_source = summary.get('data_source')
        
        if not data_source:
            continue
            
        # Get available columns for this data source
        available_cols = set(KNOWN_COLUMNS.get(data_source, []))
        
        # Check group_by columns
        group_by = summary.get('group_by', [])
        if isinstance(group_by, str):
            group_by = [group_by]
            
        for col in group_by:
            if col not in available_cols:
                errors.append(
                    f"Summary '{name}': Column '{col}' not found in {data_source}. "
                    f"Available: {sorted(available_cols)}"
                )
        
        # Check aggregation columns
        aggregations = summary.get('aggregations', {})
        for agg_name, agg_def in aggregations.items():
            if isinstance(agg_def, dict):
                col = agg_def.get('column')
                if col and col not in available_cols:
                    errors.append(
                        f"Summary '{name}': Aggregation column '{col}' not found in {data_source}"
                    )
        
        # Check weight field
        weight_field = summary.get('weight_field')
        if weight_field and weight_field not in available_cols:
            errors.append(
                f"Summary '{name}': Weight field '{weight_field}' not found in {data_source}"
            )
    
    return errors


def check_dashboard_files(dashboard_dir: Path, outputs_dir: Path) -> List[str]:
    """
    Check if dashboard YAML files reference existing CSV outputs.
    
    Returns list of warning messages.
    """
    warnings = []
    
    if not dashboard_dir.exists():
        return [f"Dashboard directory not found: {dashboard_dir}"]
    
    # Get all dashboard YAML files
    dashboard_files = list(dashboard_dir.glob('dashboard-*.yaml'))
    
    for yaml_file in dashboard_files:
        try:
            with open(yaml_file) as f:
                config = yaml.safe_load(f)
            
            # Extract all CSV file references
            csv_files = extract_csv_references(config)
            
            # Check if files exist
            for csv_file in csv_files:
                csv_path = outputs_dir / csv_file
                if not csv_path.exists():
                    warnings.append(
                        f"Dashboard '{yaml_file.name}' references missing file: {csv_file}"
                    )
        
        except Exception as e:
            warnings.append(f"Error reading {yaml_file.name}: {e}")
    
    return warnings


def extract_csv_references(config: Dict) -> Set[str]:
    """Recursively extract all CSV file references from dashboard config."""
    csv_files = set()
    
    def recurse(obj):
        if isinstance(obj, dict):
            if 'dataset' in obj and isinstance(obj['dataset'], str):
                if obj['dataset'].endswith('.csv'):
                    csv_files.add(obj['dataset'])
            for value in obj.values():
                recurse(value)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item)
    
    recurse(config)
    return csv_files


def check_input_directories(config: Dict) -> List[str]:
    """Check if configured input directories exist."""
    errors = []
    
    input_dirs = config.get('input_directories', [])
    for dir_config in input_dirs:
        path = Path(dir_config.get('path', ''))
        label = dir_config.get('label', 'unknown')
        
        if not path.exists():
            errors.append(f"Input directory not found: {path} (label: {label})")
        else:
            # Check for required files
            required_files = [
                'personData_1.csv',
                'householdData_1.csv',
                'indivTourData_1.csv',
                'indivTripData_1.csv'
            ]
            
            ctramp_output = path / 'ctramp_output'
            if ctramp_output.exists():
                check_dir = ctramp_output
            else:
                check_dir = path
            
            for filename in required_files:
                if not (check_dir / filename).exists():
                    errors.append(
                        f"Missing required file in {label}: {filename}"
                    )
    
    return errors


def main():
    """Run all validation checks."""
    config_path = Path('validation_config.yaml')
    
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        return 1
    
    logger.info("Loading configuration...")
    config = load_config(config_path)
    
    has_errors = False
    has_warnings = False
    
    # Check input directories
    logger.info("\n" + "="*80)
    logger.info("Checking input directories...")
    logger.info("="*80)
    errors = check_input_directories(config)
    if errors:
        has_errors = True
        for error in errors:
            logger.error(f"  ❌ {error}")
    else:
        logger.info("  ✓ All input directories found")
    
    # Check summary configurations
    logger.info("\n" + "="*80)
    logger.info("Checking summary configurations...")
    logger.info("="*80)
    
    all_summaries = config.get('custom_summaries', [])
    
    # Count active vs commented summaries
    active_summaries = [s for s in all_summaries if isinstance(s, dict)]
    logger.info(f"  Found {len(active_summaries)} active summaries")
    
    errors = check_summary_columns(active_summaries)
    if errors:
        has_errors = True
        for error in errors:
            logger.error(f"  ❌ {error}")
    else:
        logger.info("  ✓ All summaries have valid column references")
    
    # Check dashboard files
    logger.info("\n" + "="*80)
    logger.info("Checking dashboard configurations...")
    logger.info("="*80)
    
    dashboard_dir = Path('dashboard')
    outputs_dir = Path('outputs/dashboard')
    
    if outputs_dir.exists():
        warnings = check_dashboard_files(dashboard_dir, outputs_dir)
        if warnings:
            has_warnings = True
            for warning in warnings:
                logger.warning(f"  ⚠️  {warning}")
        else:
            logger.info("  ✓ All dashboard files reference existing CSVs")
    else:
        logger.warning(f"  ⚠️  Outputs directory not found: {outputs_dir}")
        logger.warning("     Run summary generation first to create output files")
        has_warnings = True
    
    # Summary
    logger.info("\n" + "="*80)
    if has_errors:
        logger.error("❌ VALIDATION FAILED - Fix errors before running summaries")
        return 1
    elif has_warnings:
        logger.warning("⚠️  VALIDATION PASSED WITH WARNINGS - Review warnings above")
        return 0
    else:
        logger.info("✅ VALIDATION PASSED - Configuration looks good!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
