#!/usr/bin/env python3
"""
Generate CTRAMP validation summaries and prepare them for the dashboard.

This script:
1. Runs the validation summary system to generate CSV summaries
2. Copies the generated summaries to the dashboard folder
3. Optionally launches the Streamlit dashboard

Usage:
    # Generate all summaries
    python run_and_deploy_dashboard.py --config validation_config.yaml
    
    # Generate only core summaries
    python run_and_deploy_dashboard.py --config validation_config.yaml --summaries core
    
    # Generate and launch dashboard
    python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def run_summaries(config_path: Path, summary_type: str = None):
    """Run the validation summary generation system."""
    logger.info("=" * 80)
    logger.info("STEP 1: Generating Validation Summaries")
    logger.info("=" * 80)
    
    # Run as module using -m flag with proper path setup
    # Add the tm2py-utils root to Python path
    repo_root = Path(__file__).parent.parent.parent.parent
    
    cmd = [
        sys.executable, '-m',
        'tm2py_utils.summary.validation.summaries.run_all',
        '--config', str(config_path)
    ]
    
    # Set PYTHONPATH environment variable to include repo root
    env = os.environ.copy()
    env['PYTHONPATH'] = str(repo_root) + os.pathsep + env.get('PYTHONPATH', '')
    
    if summary_type:
        logger.info(f"Generating {summary_type} summaries only")
    else:
        logger.info("Generating all summaries")
    
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info(f"PYTHONPATH: {env.get('PYTHONPATH')}")
    
    try:
        result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        logger.info("✓ Summary generation completed successfully")
        if result.stdout:
            logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("✗ Summary generation failed")
        if e.stderr:
            logger.error(e.stderr)
        if e.stdout:
            logger.error(e.stdout)
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        return False


def copy_summaries_to_dashboard(output_dir: Path, dashboard_dir: Path):
    """Copy generated summary CSVs to the dashboard folder."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 2: Copying Summaries to Dashboard Folder")
    logger.info("=" * 80)
    
    # Ensure dashboard directory exists
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all CSV files in the output directory
    csv_files = list(output_dir.glob("*.csv"))
    
    if not csv_files:
        logger.warning(f"⚠ No CSV files found in {output_dir}")
        return False
    
    logger.info(f"Found {len(csv_files)} CSV files to copy")
    
    copied = 0
    for csv_file in csv_files:
        dest = dashboard_dir / csv_file.name
        try:
            shutil.copy2(csv_file, dest)
            logger.info(f"  ✓ {csv_file.name}")
            copied += 1
        except Exception as e:
            logger.error(f"  ✗ Failed to copy {csv_file.name}: {e}")
    
    logger.info(f"Successfully copied {copied}/{len(csv_files)} files")
    return copied > 0


def launch_dashboard(dashboard_script: Path, port: int = 8501):
    """Launch the Streamlit dashboard."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("STEP 3: Launching Streamlit Dashboard")
    logger.info("=" * 80)
    
    cmd = [
        'streamlit', 'run',
        str(dashboard_script),
        '--server.port', str(port)
    ]
    
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info(f"Dashboard will be available at: http://localhost:{port}")
    logger.info("Press Ctrl+C to stop the dashboard")
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        logger.info("\nDashboard stopped by user")
    except Exception as e:
        logger.error(f"Failed to launch dashboard: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate summaries and deploy to dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all summaries and copy to dashboard
  python run_and_deploy_dashboard.py --config validation_config.yaml
  
  # Generate only core summaries
  python run_and_deploy_dashboard.py --config validation_config.yaml --summaries core
  
  # Generate and launch dashboard
  python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard
  
  # Use custom port for dashboard
  python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard --port 8503
        """
    )
    
    parser.add_argument(
        '--config',
        type=Path,
        required=True,
        help='Path to validation_config.yaml'
    )
    
    parser.add_argument(
        '--summaries',
        choices=['all', 'core', 'validation'],
        default=None,
        help='Which summaries to generate (uses config file setting if not specified)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Output directory for summaries (default: from config file)'
    )
    
    parser.add_argument(
        '--dashboard-dir',
        type=Path,
        default=None,
        help='Dashboard directory (default: output-dir/dashboard)'
    )
    
    parser.add_argument(
        '--launch-dashboard',
        action='store_true',
        help='Launch Streamlit dashboard after generating summaries'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=8501,
        help='Port for Streamlit dashboard (default: 8501)'
    )
    
    parser.add_argument(
        '--skip-generation',
        action='store_true',
        help='Skip summary generation, only copy existing files'
    )
    
    args = parser.parse_args()
    
    # Validate config file exists
    if not args.config.exists():
        logger.error(f"Configuration file not found: {args.config}")
        return 1
    
    # Determine directories
    if args.output_dir is None:
        # Default to validation/outputs
        args.output_dir = args.config.parent / 'outputs'
    
    if args.dashboard_dir is None:
        args.dashboard_dir = args.output_dir / 'dashboard'
    
    dashboard_script = args.config.parent / 'dashboard' / 'dashboard_app.py'
    
    # Step 1: Generate summaries (unless skipped)
    if not args.skip_generation:
        if not run_summaries(args.config, args.summaries):
            logger.error("Summary generation failed. Aborting.")
            return 1
    else:
        logger.info("Skipping summary generation (--skip-generation flag)")
    
    # Step 2: Copy summaries to dashboard folder
    if not copy_summaries_to_dashboard(args.output_dir, args.dashboard_dir):
        logger.warning("No summaries were copied. Dashboard may not have data.")
    
    # Step 3: Launch dashboard (if requested)
    if args.launch_dashboard:
        if not dashboard_script.exists():
            logger.error(f"Dashboard script not found: {dashboard_script}")
            return 1
        launch_dashboard(dashboard_script, args.port)
    else:
        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Summaries are ready in: {args.dashboard_dir}")
        logger.info("")
        logger.info("To launch the dashboard, run:")
        logger.info(f"  streamlit run {dashboard_script} --server.port {args.port}")
        logger.info("=" * 80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
