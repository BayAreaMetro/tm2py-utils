#!/usr/bin/env python3
"""
Real Data Free Parking Analysis

Script to analyze free parking choice between the two real model runs:
- C:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Outputs\2015-tm22-dev-sprint-04\ctramp_output
- A:\2023-tm22-dev-version-05\ctramp_output
"""

import pandas as pd
from pathlib import Path
import sys
import os

# Add the summary directory to path to import our modules
sys.path.append(str(Path(__file__).parent.parent))
from validation.free_parking_analysis import load_person_file, analyze_free_parking_choice, create_comparison_summaries, save_summaries
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Analyze free parking choice between 2015 and 2023 model runs."""
    
    # Define the real data paths
    scenario1_dir = Path(r"C:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Outputs\2015-tm22-dev-sprint-04\ctramp_output")
    scenario2_dir = Path(r"A:\2023-tm22-dev-version-05\ctramp_output")
    output_dir = Path("real_free_parking_results")
    
    logger.info("Real Data Free Parking Choice Analysis")
    logger.info("=" * 50)
    logger.info(f"Scenario 1 (2015): {scenario1_dir}")
    logger.info(f"Scenario 2 (2023): {scenario2_dir}")
    
    try:
        # Check if directories exist
        if not scenario1_dir.exists():
            logger.error(f"Scenario 1 directory not found: {scenario1_dir}")
            return False
            
        if not scenario2_dir.exists():
            logger.error(f"Scenario 2 directory not found: {scenario2_dir}")
            return False
        
        # Load data from both scenarios
        person1_file = scenario1_dir / "personData_1.csv"
        person2_file = scenario2_dir / "personData_1.csv"
        
        logger.info(f"\nLoading data files...")
        df1 = load_person_file(person1_file)
        df2 = load_person_file(person2_file)
        
        # Show data info
        logger.info(f"\nData Summary:")
        logger.info(f"  2015 Model: {len(df1):,} persons")
        logger.info(f"  2023 Model: {len(df2):,} persons")
        
        # Check if fp_choice field exists
        fp1_available = 'fp_choice' in df1.columns and df1['fp_choice'].notna().sum() > 0
        fp2_available = 'fp_choice' in df2.columns and df2['fp_choice'].notna().sum() > 0
        
        logger.info(f"  2015 fp_choice field: {'✓' if fp1_available else '✗'}")
        logger.info(f"  2023 fp_choice field: {'✓' if fp2_available else '✗'}")
        
        if not fp1_available and not fp2_available:
            logger.error("Neither dataset has free parking choice data")
            return False
        
        # Generate summaries
        logger.info(f"\nGenerating summaries...")
        summaries1 = analyze_free_parking_choice(df1, "2015_Baseline")
        summaries2 = analyze_free_parking_choice(df2, "2023_Updated")
        
        # Create comparisons
        comparisons = create_comparison_summaries(summaries1, summaries2)
        
        # Combine all summaries
        all_summaries = {**summaries1, **summaries2, **comparisons}
        
        # Save results
        save_summaries(all_summaries, output_dir)
        
        logger.info("✅ Analysis completed successfully!")
        logger.info(f"Results saved to: {output_dir.absolute()}")
        
        # Show key results if available
        if 'free_parking_regional_comparison' in all_summaries:
            print("\n📊 Regional Free Parking Comparison:")
            comparison_df = all_summaries['free_parking_regional_comparison']
            
            # Filter out missing data
            valid_data = comparison_df[comparison_df['fp_choice'] != -1]
            
            if len(valid_data) > 0:
                pivot_df = valid_data.pivot(index='fp_choice_label', columns='scenario', values='share')
                print(pivot_df.round(1))
                
                # Calculate change
                if len(pivot_df.columns) == 2:
                    for index in pivot_df.index:
                        val_2015 = pivot_df.iloc[pivot_df.index.get_loc(index), 0]
                        val_2023 = pivot_df.iloc[pivot_df.index.get_loc(index), 1]
                        change = val_2023 - val_2015
                        print(f"{index}: {change:+.1f} percentage point change")
            else:
                print("No valid free parking data found in either scenario")
        
        print(f"\n📁 Output files:")
        for file_path in output_dir.glob("*.csv"):
            print(f"  - {file_path.name}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    
    if success:
        print(f"\n🎯 Next steps:")
        print(f"1. Review the CSV files in real_free_parking_results/")
        print(f"2. Use these as templates for other summary types")
        print(f"3. Create SimWrapper dashboards from the CSV outputs")
    else:
        print(f"\n❌ Analysis failed - check logs above")
        sys.exit(1)