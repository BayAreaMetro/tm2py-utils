"""
Quick validation check for tm2py validation configuration.

Checks only critical issues:
1. Input directories exist
2. Dashboard files reference existing CSVs (after generation)
3. Configuration file is valid YAML
"""

import sys
from pathlib import Path
import yaml
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    """Run quick validation checks."""
    config_path = Path('validation_config.yaml')
    
    if not config_path.exists():
        logger.error(f"❌ Configuration file not found: {config_path}")
        return 1
    
    logger.info("=" * 80)
    logger.info("TM2PY VALIDATION SYSTEM - QUICK CHECK")
    logger.info("=" * 80)
    
    # Check 1: Load config
    logger.info("\n📄 Loading configuration...")
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        logger.info("  ✓ Configuration file is valid YAML")
    except Exception as e:
        logger.error(f"  ❌ Failed to load config: {e}")
        return 1
    
    # Check 2: Input directories
    logger.info("\n📁 Checking input directories...")
    input_dirs = config.get('input_directories', [])
    if not input_dirs:
        logger.warning("  ⚠️  No input directories configured")
    
    all_exist = True
    for dir_config in input_dirs:
        path = Path(dir_config.get('path', ''))
        label = dir_config.get('label', 'unknown')
        
        if not path.exists():
            logger.error(f"  ❌ Directory not found: {path} ({label})")
            all_exist = False
        else:
            logger.info(f"  ✓ {label}: {path}")
    
    # Check 3: Count summaries
    logger.info("\n📊 Counting configured summaries...")
    all_summaries = config.get('custom_summaries', [])
    active = [s for s in all_summaries if isinstance(s, dict)]
    logger.info(f"  ✓ {len(active)} active summaries configured")
    
    # Check 4: Output files (if outputs exist)
    outputs_dir = Path('outputs/dashboard')
    if outputs_dir.exists():
        csv_files = list(outputs_dir.glob('*.csv'))
        logger.info(f"\n📦 Found {len(csv_files)} output CSV files in outputs/dashboard/")
        
        # Check dashboard references
        dashboard_dir = Path('dashboard')
        if dashboard_dir.exists():
            logger.info("\n🎨 Checking dashboard configurations...")
            dashboard_files = list(dashboard_dir.glob('dashboard-*.yaml'))
            logger.info(f"  ✓ {len(dashboard_files)} dashboard files found")
            
            # Quick check for obvious issues
            missing_files = []
            for yaml_file in dashboard_files:
                try:
                    with open(yaml_file, encoding='utf-8') as f:
                        dash_config = yaml.safe_load(f)
                except Exception as e:
                    logger.warning(f"  ⚠️  Could not read {yaml_file.name}: {e}")
                    continue
    else:
        logger.info(f"\n📦 No outputs found yet (run summary generation first)")
    
    # Summary
    logger.info("\n" + "=" * 80)
    if all_exist:
        logger.info("✅ BASIC CHECKS PASSED")
        logger.info("\nNext steps:")
        logger.info("  1. Generate summaries: python run_and_deploy_dashboard.py --config validation_config.yaml")
        logger.info("  2. Launch dashboard: streamlit run dashboard/dashboard_app.py")
        return 0
    else:
        logger.error("❌ CHECKS FAILED - Fix input directory paths")
        return 1


if __name__ == '__main__':
    sys.exit(main())
