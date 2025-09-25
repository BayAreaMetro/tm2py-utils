#!/usr/bin/env python3
"""
Example script showing how to use the CTRAMP schema analysis modules
"""

import pandas as pd
from pathlib import Path

# Import the CTRAMP analysis modules
from tm2py_utils.summary.ctramp_schema_analyzer import CTRAMPSchemaAnalyzer
from tm2py_utils.summary.ctramp_validator import CTRAMPValidator
from tm2py_utils.summary.ctramp_analysis_templates import (
    CTRAMPAnalysisTemplates, 
    show_analysis_recommendations,
    list_applicable_summaries
)


def main():
    """
    Example usage of the CTRAMP analysis suite
    """
    
    # 1. SCHEMA ANALYSIS
    print("🔍 CTRAMP Schema Analysis Example")
    print("="*50)
    
    # Set your data directory
    data_directory = r"C:\Users\schildress\OneDrive - Metropolitan Transportation Commission\Documents\test_outputs"
    
    # Initialize the analyzer
    analyzer = CTRAMPSchemaAnalyzer(data_directory)
    
    # Run the analysis
    print(f"Analyzing files in: {data_directory}")
    schema_results = analyzer.analyze_directory_schema()
    
    # Print summary
    analyzer.print_schema_summary()
    
    # Export to CSV
    schema_file = analyzer.export_schema_csv("example_schema_results.csv")
    
    
    # 2. VALIDATION AGAINST DOCUMENTATION
    print(f"\n🔍 CTRAMP Validation Example")
    print("="*50)
    
    # Initialize validator
    validator = CTRAMPValidator()
    
    # Run validation
    validation_results = validator.validate_multiple_files(schema_results['file_schemas'])
    
    # Export validation results
    validation_df = validator.create_validation_dataframe(validation_results)
    validation_df.to_csv("example_validation_results.csv", index=False)
    
    # Show validation summary
    analysis_ready_files = [v for v in validation_results if v.get('analysis_ready', False)]
    print(f"Found {len(analysis_ready_files)} CTRAMP files ready for analysis")
    
    
    # 3. ANALYSIS RECOMMENDATIONS
    print(f"\n🎯 Analysis Recommendations Example")
    print("="*50)
    
    # Show recommendations for each file
    for file_info in schema_results['file_schemas'][:3]:  # Just show first 3
        if not file_info.get('error'):
            show_analysis_recommendations(
                file_info['filename'],
                file_info.get('columns', [])
            )
    
    
    # 4. PRE-BUILT ANALYSIS EXAMPLES
    print(f"\n📊 Pre-Built Analysis Templates Example")
    print("="*50)
    
    # Example: Load a trip file and run analyses (if it exists)
    trip_files = [f for f in schema_results['file_schemas'] 
                  if 'trip' in f['filename'].lower() and not f.get('error')]
    
    if trip_files:
        trip_file = trip_files[0]
        print(f"Running analysis examples on: {trip_file['filename']}")
        
        # Load the data (first 10000 rows for example)
        try:
            data_path = Path(data_directory) / trip_file['filename'] 
            df = pd.read_csv(data_path, nrows=10000)
            
            print(f"Loaded {len(df):,} rows for analysis")
            
            # Example 1: Mode Share Analysis
            if 'trip_mode' in df.columns:
                print("\n📈 Mode Share Analysis:")
                mode_share = CTRAMPAnalysisTemplates.mode_share_analysis(
                    df, 
                    mode_field='trip_mode'
                )
                print(mode_share.head())
            
            # Example 2: VMT Calculation
            if 'TRIP_DISTANCE' in df.columns and 'trip_mode' in df.columns:
                print("\n🚗 VMT Calculation:")
                vmt = CTRAMPAnalysisTemplates.vmt_calculation(df)
                print(vmt)
            
            # Example 3: Time of Day Analysis
            time_fields = [col for col in df.columns if 'period' in col.lower()]
            if time_fields:
                print(f"\n⏰ Time of Day Analysis ({time_fields[0]}):")
                tod = CTRAMPAnalysisTemplates.time_of_day_analysis(
                    df, 
                    time_field=time_fields[0]
                )
                print(tod.head(10))
            
            # Example 4: Trip Length Distribution
            if 'TRIP_DISTANCE' in df.columns:
                print("\n📏 Trip Length Distribution:")
                trip_lengths = CTRAMPAnalysisTemplates.trip_length_distribution(df)
                print(trip_lengths)
                
        except Exception as e:
            print(f"Could not load data file: {e}")
    
    
    # 5. DATA QUALITY ANALYSIS
    print(f"\n🔍 Data Quality Analysis Example")
    print("="*50)
    
    quality_issues = validator.analyze_data_quality_with_ctramp_context(
        schema_results, validation_results
    )
    
    if quality_issues:
        print(f"Found potential issues in {len(quality_issues)} files:")
        for issue_info in quality_issues[:3]:  # Show first 3
            print(f"\n📄 {issue_info['filename']}:")
            for issue in issue_info['issues']:
                print(f"   • {issue}")
    else:
        print("✅ No data quality issues found!")
    
    
    print(f"\n✅ Example analysis complete!")
    print("Files created:")
    print("   • example_schema_results.csv")
    print("   • example_validation_results.csv")


if __name__ == "__main__":
    main()