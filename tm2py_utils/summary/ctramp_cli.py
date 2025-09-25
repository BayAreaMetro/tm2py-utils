"""
CTRAMP Schema Analysis CLI - Command line interface for analyzing CTRAMP model outputs
"""

import argparse
import sys
from pathlib import Path

from .ctramp_schema_analyzer import CTRAMPSchemaAnalyzer
from .ctramp_validator import CTRAMPValidator
from .ctramp_analysis_templates import show_analysis_recommendations


def main():
    """
    Main CLI function for CTRAMP schema analysis
    """
    parser = argparse.ArgumentParser(
        description="Analyze CTRAMP model output file schemas and validate against documentation"
    )
    
    parser.add_argument(
        "data_directory", 
        help="Path to directory containing CTRAMP output files"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        default=".",
        help="Directory to save output files (default: current directory)"
    )
    
    parser.add_argument(
        "--schema-output", 
        default="ctramp_schema_analysis.csv",
        help="Filename for schema analysis output (default: ctramp_schema_analysis.csv)"
    )
    
    parser.add_argument(
        "--validation-output",
        default="ctramp_validation_results.csv", 
        help="Filename for validation results output (default: ctramp_validation_results.csv)"
    )
    
    parser.add_argument(
        "--show-recommendations", "-r",
        action="store_true",
        help="Show analysis recommendations for each file"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    data_dir = Path(args.data_directory)
    if not data_dir.exists():
        print(f"Error: Directory '{data_dir}' does not exist")
        sys.exit(1)
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize analyzer and validator
    analyzer = CTRAMPSchemaAnalyzer(str(data_dir))
    validator = CTRAMPValidator()
    
    print(f"🔍 Analyzing CTRAMP files in: {data_dir}")
    print("="*80)
    
    # Run schema analysis
    schema_results = analyzer.analyze_directory_schema()
    
    if 'error' in schema_results:
        print(f"Error: {schema_results['error']}")
        sys.exit(1)
    
    # Print summary if verbose
    if args.verbose:
        analyzer.print_schema_summary()
    
    # Run validation
    print(f"\n🔍 Validating files against CTRAMP documentation...")
    validation_results = validator.validate_multiple_files(schema_results['file_schemas'])
    
    # Print validation summary
    print(f"\n📊 VALIDATION SUMMARY")
    print(f"Total files analyzed: {len(validation_results)}")
    
    analysis_ready = sum(1 for v in validation_results if v.get('analysis_ready', False))
    print(f"CTRAMP files identified: {analysis_ready}")
    
    # Export results
    schema_output_path = output_dir / args.schema_output
    analyzer.export_schema_csv(str(schema_output_path))
    
    validation_output_path = output_dir / args.validation_output
    validation_df = validator.create_validation_dataframe(validation_results)
    validation_df.to_csv(validation_output_path, index=False)
    print(f"✅ Validation results exported to: {validation_output_path}")
    
    # Show analysis recommendations if requested
    if args.show_recommendations:
        print(f"\n🎯 ANALYSIS RECOMMENDATIONS")
        print("="*80)
        
        for file_info in schema_results['file_schemas']:
            if not file_info.get('error'):
                show_analysis_recommendations(
                    file_info['filename'], 
                    file_info.get('columns', [])
                )
    
    # Data quality analysis
    print(f"\n🔍 Running data quality checks...")
    quality_issues = validator.analyze_data_quality_with_ctramp_context(
        schema_results, validation_results
    )
    
    if quality_issues:
        print(f"\n⚠️  Found potential issues in {len(quality_issues)} files:")
        for issue_info in quality_issues:
            print(f"\n📄 {issue_info['filename']} ({issue_info['file_type']})")
            for issue in issue_info['issues']:
                print(f"   • {issue}")
    else:
        print("✅ No major data quality issues detected!")
    
    print(f"\n✅ Analysis complete! Output files saved to: {output_dir}")


if __name__ == "__main__":
    main()