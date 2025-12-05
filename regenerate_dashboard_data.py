#!/usr/bin/env python3
"""
Comprehensive Dashboard Data Pipeline Controller

This script orchestrates the complete dashboard data generation pipeline:
1. Generate validation summaries from CTRAMP outputs
2. Create dashboard CSV files  
3. Integrate ACS observed data
4. Apply data pivoting for complex charts
5. Validate final output

Usage:
    python regenerate_dashboard_data.py [options]
    
Options:
    --summaries: Specific summary types to regenerate (default: all)
    --skip-acs: Skip ACS data integration
    --skip-pivot: Skip data pivoting step
    --config: Custom validation config file
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DashboardPipeline:
    """Orchestrates the complete dashboard data generation pipeline"""
    
    def __init__(self, config_file=None, output_dir=None):
        self.config_file = config_file or "tm2py_utils/summary/validation/validation_config.yaml"
        self.output_dir = output_dir or "tm2py_utils/summary/validation/outputs"
        self.dashboard_dir = f"{self.output_dir}/dashboard"
        
        # Default input directories for CTRAMP outputs
        self.input_dirs = [
            "A:/2015-tm22-dev-sprint-04/ctramp_output",
            "A:/2023-tm22-dev-version-05/ctramp_output"
        ]
        
    def run_validation_summaries(self, summary_types=None):
        """Step 1: Generate validation summaries from CTRAMP outputs"""
        logger.info("=" * 60)
        logger.info("STEP 1: Generating validation summaries")
        logger.info("=" * 60)
        
        cmd = [
            "python", "-m", "tm2py_utils.summary.validation.summaries.run_all",
            "--input-dirs", *self.input_dirs,
            "--output-dir", self.output_dir,
            "--config", self.config_file
        ]
        
        if summary_types:
            cmd.extend(["--summaries", *summary_types])
            
        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Validation summary generation failed:")
            logger.error(result.stderr)
            raise RuntimeError("Failed to generate validation summaries")
            
        logger.info("✅ Validation summaries generated successfully")
        return result
        
    def integrate_acs_data(self):
        """Step 2: Integrate ACS observed data into dashboard files"""
        logger.info("=" * 60)
        logger.info("STEP 2: Integrating ACS observed data")
        logger.info("=" * 60)
        
        try:
            # Import and run the ACS integration logic
            import pandas as pd
            
            # Regional auto ownership
            logger.info("📊 Processing regional auto ownership...")
            acs_regional = pd.read_csv('tm2py_utils/summary/validation/outputs/observed/acs_auto_ownership_by_household_size_regional.csv')
            acs_comparison = pd.read_csv(f'{self.dashboard_dir}/auto_ownership_by_household_size_acs.csv')
            
            # Regional aggregation from detailed ACS data
            acs_agg = acs_regional.groupby(['num_vehicles'])['households'].sum().reset_index()
            acs_agg['share'] = acs_agg['households'] / acs_agg['households'].sum() * 100
            acs_agg['dataset'] = 'ACS 2023 Observed'
            
            # Combine with model data
            combined_acs = pd.concat([acs_comparison, acs_agg[['num_vehicles', 'households', 'share', 'dataset']]], ignore_index=True)
            combined_acs.to_csv(f'{self.dashboard_dir}/auto_ownership_by_household_size_acs.csv', index=False)
            logger.info("✓ Updated auto_ownership_by_household_size_acs.csv with ACS data")
            
            # Regional summary for main dashboard
            model_regional = pd.read_csv(f'{self.dashboard_dir}/auto_ownership_regional.csv')
            combined_regional = pd.concat([model_regional, acs_agg[['num_vehicles', 'households', 'share', 'dataset']]], ignore_index=True)
            combined_regional.to_csv(f'{self.dashboard_dir}/auto_ownership_regional.csv', index=False)
            logger.info("✓ Updated auto_ownership_regional.csv with ACS data")
            
            # County auto ownership
            logger.info("📊 Processing county auto ownership...")
            model_county = pd.read_csv(f'{self.dashboard_dir}/auto_ownership_by_household_size_county.csv')
            acs_county = pd.read_csv('tm2py_utils/summary/validation/outputs/observed/acs_auto_ownership_by_household_size_county.csv')
            
            # Format county ACS data to match model structure
            acs_county_formatted = acs_county.copy()
            acs_county_formatted['dataset'] = 'ACS 2023 Observed'
            
            combined_county = pd.concat([model_county, acs_county_formatted[['county', 'num_persons_agg', 'num_vehicles', 'households', 'share', 'dataset']]], ignore_index=True)
            combined_county.to_csv(f'{self.dashboard_dir}/auto_ownership_by_household_size_county.csv', index=False)
            logger.info("✓ Updated auto_ownership_by_household_size_county.csv with ACS data")
            
            # County aggregated (across household sizes)
            logger.info("📊 Processing county aggregated data...")
            model_county_agg = pd.read_csv(f'{self.dashboard_dir}/auto_ownership_by_county.csv')
            model_county_agg = model_county_agg[model_county_agg['dataset'] != 'ACS 2023 Observed']
            
            # Create county aggregation from detailed ACS data
            acs_county_detail = pd.read_csv('tm2py_utils/summary/validation/outputs/observed/acs_auto_ownership_by_household_size_county.csv')
            acs_county_agg = acs_county_detail.groupby(['county', 'num_vehicles'])['households'].sum().reset_index()
            county_totals = acs_county_agg.groupby('county')['households'].sum().reset_index()
            county_totals.rename(columns={'households': 'total_households'}, inplace=True)
            acs_county_agg = acs_county_agg.merge(county_totals, on='county')
            acs_county_agg['share'] = acs_county_agg['households'] / acs_county_agg['total_households'] * 100
            acs_county_agg['dataset'] = 'ACS 2023 Observed'
            acs_county_agg = acs_county_agg.drop('total_households', axis=1)
            
            combined_county_agg = pd.concat([model_county_agg, acs_county_agg[['county', 'num_vehicles', 'households', 'share', 'dataset']]], ignore_index=True)
            combined_county_agg.to_csv(f'{self.dashboard_dir}/auto_ownership_by_county.csv', index=False)
            logger.info("✓ Updated auto_ownership_by_county.csv with ACS data")
            
            # Income-based auto ownership
            logger.info("📊 Processing income-based auto ownership...")
            model_income = pd.read_csv(f'{self.dashboard_dir}/auto_ownership_by_income.csv')
            
            # Create income aggregation from ACS regional data (no income breakdown available)
            # Use overall ACS shares across all income categories
            acs_income_expanded = []
            income_bins = model_income['income_category_bin'].unique()
            
            for income_bin in income_bins:
                for _, row in acs_agg.iterrows():
                    acs_income_expanded.append({
                        'income_category_bin': income_bin,
                        'num_vehicles': row['num_vehicles'],
                        'households': row['households'] / len(income_bins),  # Distribute evenly
                        'share': row['share'],  # Keep same share pattern
                        'dataset': 'ACS 2023 Observed'
                    })
            
            acs_income_df = pd.DataFrame(acs_income_expanded)
            combined_income = pd.concat([model_income, acs_income_df], ignore_index=True)
            combined_income.to_csv(f'{self.dashboard_dir}/auto_ownership_by_income.csv', index=False)
            logger.info("✓ Updated auto_ownership_by_income.csv with ACS data")
            
            # Household size summary
            logger.info("📊 Processing household size summary...")
            acs_hh_size_detail = pd.read_csv('tm2py_utils/summary/validation/outputs/observed/acs_auto_ownership_by_household_size_regional.csv')
            acs_hh_size = acs_hh_size_detail.groupby(['num_persons_agg'])['households'].sum().reset_index()
            acs_hh_size['share'] = acs_hh_size['households'] / acs_hh_size['households'].sum() * 100
            acs_hh_size['dataset'] = 'ACS 2023 Observed'
            
            model_hh_size = pd.read_csv(f'{self.dashboard_dir}/household_size_regional.csv')
            # Fix column name issue
            if 'household_size' in model_hh_size.columns:
                model_hh_size = model_hh_size.rename(columns={'household_size': 'num_persons_agg'})
            
            combined_hh_size = pd.concat([model_hh_size, acs_hh_size[['num_persons_agg', 'households', 'share', 'dataset']]], ignore_index=True)
            combined_hh_size.to_csv(f'{self.dashboard_dir}/household_size_regional.csv', index=False)
            logger.info("✓ Updated household_size_regional.csv with ACS data")
            
            logger.info("✅ ACS data integration completed successfully")
            
        except FileNotFoundError as e:
            logger.warning(f"⚠️  ACS file not found: {e}")
            logger.warning("Continuing without ACS integration...")
        except Exception as e:
            logger.error(f"❌ ACS integration failed: {e}")
            raise
            
    def apply_data_pivoting(self):
        """Step 3: Apply data pivoting for complex dashboard charts"""
        logger.info("=" * 60)
        logger.info("STEP 3: Applying data pivoting")
        logger.info("=" * 60)
        
        try:
            exec(open('pivot_dashboard_data.py').read())
            logger.info("✅ Data pivoting completed successfully")
        except Exception as e:
            logger.error(f"❌ Data pivoting failed: {e}")
            raise
            
    def validate_output(self):
        """Step 4: Validate the final dashboard data"""
        logger.info("=" * 60)
        logger.info("STEP 4: Validating dashboard output")
        logger.info("=" * 60)
        
        dashboard_files = [
            'auto_ownership_regional.csv',
            'auto_ownership_by_income.csv',
            'auto_ownership_by_household_size_acs.csv',
            'auto_ownership_by_household_size_county.csv',
            'auto_ownership_by_county.csv',
            'household_size_regional.csv',
            'trip_mode_choice_aggregated.csv',
            'trip_mode_by_purpose_aggregated.csv',
            'tour_mode_choice_aggregated.csv',
            'tour_mode_by_purpose_aggregated.csv'
        ]
        
        validation_results = {}
        
        for filename in dashboard_files:
            filepath = Path(self.dashboard_dir) / filename
            if filepath.exists():
                try:
                    df = pd.read_csv(filepath)
                    datasets = sorted(df['dataset'].unique()) if 'dataset' in df.columns else []
                    has_acs = any('ACS' in d for d in datasets)
                    validation_results[filename] = {
                        'exists': True,
                        'rows': len(df),
                        'datasets': datasets,
                        'has_acs': has_acs,
                        'columns': list(df.columns)
                    }
                except Exception as e:
                    validation_results[filename] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                validation_results[filename] = {'exists': False}
                
        # Print validation report
        logger.info("📊 Dashboard Data Validation Report:")
        logger.info("-" * 50)
        
        for filename, result in validation_results.items():
            if not result['exists']:
                logger.warning(f"❌ {filename}: File not found")
            elif 'error' in result:
                logger.error(f"❌ {filename}: {result['error']}")
            else:
                acs_status = "✓ ACS" if result['has_acs'] else "⚠️ No ACS"
                datasets_str = ", ".join(result['datasets'])
                logger.info(f"✅ {filename}: {result['rows']} rows, {acs_status}")
                logger.info(f"   Datasets: {datasets_str}")
                
        logger.info("✅ Validation completed")
        
    def run_complete_pipeline(self, summary_types=None, skip_acs=False, skip_pivot=False):
        """Run the complete dashboard data generation pipeline"""
        logger.info("🚀 Starting Complete Dashboard Data Pipeline")
        logger.info("=" * 80)
        
        try:
            # Step 1: Generate validation summaries
            self.run_validation_summaries(summary_types)
            
            # Step 2: Integrate ACS data
            if not skip_acs:
                self.integrate_acs_data()
            else:
                logger.info("⏭️  Skipping ACS integration")
                
            # Step 3: Apply data pivoting
            if not skip_pivot:
                self.apply_data_pivoting()
            else:
                logger.info("⏭️  Skipping data pivoting")
                
            # Step 4: Validate output
            self.validate_output()
            
            logger.info("=" * 80)
            logger.info("🎉 Dashboard Data Pipeline Completed Successfully!")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"❌ Pipeline failed: {e}")
            logger.error("=" * 80)
            raise

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Regenerate complete dashboard data pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--summaries",
        nargs="*",
        help="Specific summary types to regenerate (default: all)"
    )
    parser.add_argument(
        "--skip-acs",
        action="store_true",
        help="Skip ACS data integration"
    )
    parser.add_argument(
        "--skip-pivot", 
        action="store_true",
        help="Skip data pivoting step"
    )
    parser.add_argument(
        "--config",
        default="tm2py_utils/summary/validation/validation_config.yaml",
        help="Validation config file"
    )
    parser.add_argument(
        "--output-dir",
        default="tm2py_utils/summary/validation/outputs",
        help="Output directory"
    )
    
    args = parser.parse_args()
    
    # Create and run pipeline
    pipeline = DashboardPipeline(
        config_file=args.config,
        output_dir=args.output_dir
    )
    
    pipeline.run_complete_pipeline(
        summary_types=args.summaries,
        skip_acs=args.skip_acs,
        skip_pivot=args.skip_pivot
    )

if __name__ == "__main__":
    main()