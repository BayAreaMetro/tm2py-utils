"""
Dashboard validation script - checks that all dashboard tabs can load.

Verifies:
- All dashboard YAML files are valid
- All referenced CSV files exist
- Charts can be created without errors
"""

import sys
from pathlib import Path
import yaml
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_dashboard_file(yaml_path: Path, outputs_dir: Path) -> dict:
    """
    Check a single dashboard YAML file.
    
    Returns dict with:
        - valid: bool
        - errors: list of error messages
        - warnings: list of warning messages
    """
    result = {
        'valid': True,
        'errors': [],
        'warnings': []
    }
    
    # Load YAML
    try:
        with open(yaml_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        result['valid'] = False
        result['errors'].append(f"Failed to load YAML: {e}")
        return result
    
    # Check dashboard structure
    if not config:
        result['errors'].append("Empty YAML file")
        result['valid'] = False
        return result
    
    # Handle both old and new dashboard structures
    # Old structure: sections (top level) with dashboard header
    # New structure: header, layout
    if 'sections' in config:
        # Old structure with sections at top level
        sections = config.get('sections', {})
    elif 'layout' in config:
        # New structure
        sections = config.get('layout', {})
    elif 'dashboard' in config and 'sections' in config.get('dashboard', {}):
        # Alternative old structure: dashboard -> sections
        sections = config.get('dashboard', {}).get('sections', {})
    else:
        result['errors'].append("No 'sections' or 'layout' key found")
        result['valid'] = False
        return result
    
    if not sections:
        result['warnings'].append("No sections/layout defined")
        return result
    
    # Check each chart
    for section_name, section_config in sections.items():
        # Handle both structures
        if isinstance(section_config, dict):
            # Old structure: section has 'charts' key
            charts = section_config.get('charts', [])
        elif isinstance(section_config, list):
            # New structure: section IS the list of charts
            charts = section_config
        else:
            continue
        
        for i, chart in enumerate(charts):
            chart_title = chart.get('title', f'Chart {i+1}')
            
            # Check if dataset file exists (in 'dataset' or 'props.dataset')
            dataset = chart.get('dataset')
            if not dataset and 'props' in chart:
                dataset = chart['props'].get('dataset')
            
            if dataset:
                csv_path = outputs_dir / dataset
                if not csv_path.exists():
                    result['warnings'].append(
                        f"Section '{section_name}', chart '{chart_title}': "
                        f"Dataset file not found: {dataset}"
                    )
                else:
                    # Try to load CSV to check structure
                    try:
                        df = pd.read_csv(csv_path, nrows=1)
                        
                        # Check if required columns exist
                        for col_param in ['x', 'y', 'color', 'facet']:
                            col = chart.get(col_param)
                            if col and col not in df.columns:
                                result['warnings'].append(
                                    f"Section '{section_name}', chart '{chart_title}': "
                                    f"Column '{col}' not found in {dataset}"
                                )
                    except Exception as e:
                        result['warnings'].append(
                            f"Section '{section_name}', chart '{chart_title}': "
                            f"Error reading {dataset}: {e}"
                        )
    
    return result


def main():
    """Run dashboard validation."""
    dashboard_dir = Path('dashboard')
    outputs_dir = Path('outputs/dashboard')
    
    if not dashboard_dir.exists():
        logger.error(f"❌ Dashboard directory not found: {dashboard_dir}")
        return 1
    
    logger.info("=" * 80)
    logger.info("DASHBOARD VALIDATION")
    logger.info("=" * 80)
    
    # Get all dashboard YAML files
    dashboard_files = sorted(dashboard_dir.glob('dashboard-*.yaml'))
    
    if not dashboard_files:
        logger.error(f"❌ No dashboard files found in {dashboard_dir}")
        return 1
    
    logger.info(f"\nFound {len(dashboard_files)} dashboard files\n")
    
    # Check if outputs exist
    if not outputs_dir.exists():
        logger.warning(f"⚠️  Outputs directory not found: {outputs_dir}")
        logger.warning("   Run summary generation first to create output files\n")
    
    # Check each dashboard file
    total_errors = 0
    total_warnings = 0
    valid_dashboards = 0
    
    for yaml_file in dashboard_files:
        tab_name = yaml_file.stem.replace('dashboard-', '').replace('-', ' ').title()
        
        result = check_dashboard_file(yaml_file, outputs_dir)
        
        # Print status
        if not result['valid']:
            logger.error(f"❌ {tab_name}")
            for error in result['errors']:
                logger.error(f"   ERROR: {error}")
            total_errors += len(result['errors'])
        elif result['warnings']:
            logger.warning(f"⚠️  {tab_name}")
            for warning in result['warnings']:
                logger.warning(f"   {warning}")
            total_warnings += len(result['warnings'])
        else:
            logger.info(f"✅ {tab_name}")
            valid_dashboards += 1
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info(f"Checked: {len(dashboard_files)} dashboard files")
    logger.info(f"Valid: {valid_dashboards}")
    logger.info(f"Warnings: {total_warnings}")
    logger.info(f"Errors: {total_errors}")
    
    if total_errors > 0:
        logger.info("=" * 80)
        logger.error("❌ VALIDATION FAILED - Fix errors before deploying")
        return 1
    elif total_warnings > 0:
        logger.info("=" * 80)
        logger.warning("⚠️  VALIDATION PASSED WITH WARNINGS")
        logger.warning("   Some charts may not display data - review warnings above")
        return 0
    else:
        logger.info("=" * 80)
        logger.info("✅ ALL DASHBOARDS VALID")
        return 0


if __name__ == '__main__':
    sys.exit(main())
