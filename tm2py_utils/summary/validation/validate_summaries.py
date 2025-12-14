"""
Summary Validation Checker

Validates summary outputs for common issues:
- Shares that don't sum to 1.0
- Negative values where they shouldn't exist
- Missing data or zero totals
- Outlier detection
- Logical consistency checks

Usage:
    python validate_summaries.py <output_dir>
    
Example:
    python validate_summaries.py "outputs/test_2015_sprint04"
"""

import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import logging
import sys
from typing import Dict, List, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ASCII-safe symbols for Windows compatibility
CHECK = '[OK]'
WARN = '[WARN]'
ERROR = '[ERROR]'


class SummaryValidator:
    """Validates summary files for data quality issues."""
    
    def __init__(self, summary_dir: Path):
        self.summary_dir = Path(summary_dir)
        self.issues = []
        self.warnings = []
        
    def validate_all(self) -> Tuple[List[str], List[str]]:
        """
        Run all validation checks on summary files.
        
        Returns:
            Tuple of (issues, warnings) lists
        """
        logger.info("=" * 80)
        logger.info("SUMMARY VALIDATION REPORT")
        logger.info("=" * 80)
        logger.info(f"Directory: {self.summary_dir}")
        logger.info("")
        
        # Find all CSV files
        csv_files = list(self.summary_dir.glob("*.csv"))
        logger.info(f"Found {len(csv_files)} summary files to validate")
        logger.info("")
        
        for csv_file in sorted(csv_files):
            self._validate_file(csv_file)
        
        # Print summary
        logger.info("=" * 80)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 80)
        
        if not self.issues and not self.warnings:
            logger.info(f"{CHECK} ALL CHECKS PASSED - No issues found!")
        else:
            if self.issues:
                logger.info(f"{ERROR} ISSUES: {len(self.issues)}")
                for issue in self.issues:
                    logger.info(f"  - {issue}")
                logger.info("")
            
            if self.warnings:
                logger.info(f"{WARN} WARNINGS: {len(self.warnings)}")
                for warning in self.warnings:
                    logger.info(f"  - {warning}")
        
        logger.info("")
        return self.issues, self.warnings
    
    def _validate_file(self, file_path: Path):
        """Validate a single summary file."""
        logger.info(f"Checking: {file_path.name}")
        
        try:
            df = pd.read_csv(file_path)
            
            # Check for empty file
            if len(df) == 0:
                self.warnings.append(f"{file_path.name}: Empty summary (0 rows)")
                logger.info(f"  {WARN} Empty file")
                return
            
            # Run all checks
            self._check_negative_values(df, file_path.name)
            self._check_shares(df, file_path.name)
            self._check_totals(df, file_path.name)
            self._check_outliers(df, file_path.name)
            self._check_logical_consistency(df, file_path.name)
            
            logger.info(f"  {CHECK} Passed all checks")
            
        except Exception as e:
            self.issues.append(f"{file_path.name}: Failed to read - {e}")
            logger.info(f"  {ERROR} Error reading file: {e}")
    
    def _check_negative_values(self, df: pd.DataFrame, filename: str):
        """Check for negative values in count/share columns."""
        # Identify numeric columns that should be non-negative
        count_cols = [col for col in df.columns if any(x in col.lower() for x in 
                      ['count', 'trips', 'tours', 'persons', 'households', 'workers', 'share'])]
        
        for col in count_cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                if (df[col] < 0).any():
                    neg_count = (df[col] < 0).sum()
                    self.issues.append(
                        f"{filename}: {col} has {neg_count} negative values"
                    )
    
    def _check_shares(self, df: pd.DataFrame, filename: str):
        """Check if shares sum to approximately 1.0."""
        if 'share' not in df.columns:
            return
        
        # Check for shares > 1.0
        if (df['share'] > 1.0).any():
            max_share = df['share'].max()
            self.issues.append(
                f"{filename}: share column has values > 1.0 (max: {max_share:.4f})"
            )
        
        # Check for negative shares
        if (df['share'] < 0).any():
            self.issues.append(f"{filename}: share column has negative values")
        
        # Determine grouping columns (everything except share and count columns)
        count_cols = [col for col in df.columns if any(x in col.lower() for x in 
                      ['count', 'trips', 'tours', 'persons', 'households', 'workers', 'share'])]
        group_cols = [col for col in df.columns if col not in count_cols]
        
        # If we have grouping columns, check shares sum to 1.0 within each group
        if group_cols:
            share_sums = df.groupby(group_cols)['share'].sum()
            
            # Allow 0.5% tolerance for rounding errors
            tolerance = 0.005
            bad_sums = share_sums[(share_sums < 1.0 - tolerance) | (share_sums > 1.0 + tolerance)]
            
            if len(bad_sums) > 0:
                self.warnings.append(
                    f"{filename}: {len(bad_sums)} groups have shares not summing to 1.0 "
                    f"(range: {bad_sums.min():.4f} to {bad_sums.max():.4f})"
                )
        else:
            # No grouping, shares should sum to 1.0 for entire table
            total_share = df['share'].sum()
            if not (0.995 <= total_share <= 1.005):
                self.warnings.append(
                    f"{filename}: shares sum to {total_share:.4f}, expected ~1.0"
                )
    
    def _check_totals(self, df: pd.DataFrame, filename: str):
        """Check for unreasonably small or zero totals."""
        # Find count columns
        count_cols = [col for col in df.columns if any(x in col.lower() for x in 
                      ['trips', 'tours', 'persons', 'households', 'workers'])]
        
        for col in count_cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                total = df[col].sum()
                
                # Check for zero total
                if total == 0:
                    self.warnings.append(f"{filename}: {col} sums to 0")
                
                # Check for suspiciously small total (< 100 for most summaries)
                elif total < 100:
                    self.warnings.append(
                        f"{filename}: {col} has very small total ({total:.1f})"
                    )
    
    def _check_outliers(self, df: pd.DataFrame, filename: str):
        """Detect statistical outliers in numeric columns."""
        # Find numeric columns (excluding shares which are bounded 0-1)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        count_cols = [col for col in numeric_cols if 'share' not in col.lower()]
        
        for col in count_cols:
            if len(df[col].dropna()) < 4:  # Need at least 4 values for outlier detection
                continue
            
            # Use IQR method for outlier detection
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            # Define outliers as values > Q3 + 3*IQR (very conservative threshold)
            outlier_threshold = Q3 + 3 * IQR
            outliers = df[df[col] > outlier_threshold]
            
            if len(outliers) > 0 and len(outliers) < len(df) * 0.1:  # Flag if < 10% are outliers
                max_value = df[col].max()
                median_value = df[col].median()
                
                # Only flag if max is more than 10x the median
                if max_value > 10 * median_value:
                    self.warnings.append(
                        f"{filename}: {col} has potential outliers "
                        f"(max: {max_value:,.0f}, median: {median_value:,.0f})"
                    )
    
    def _check_logical_consistency(self, df: pd.DataFrame, filename: str):
        """Check for logical inconsistencies based on filename/content."""
        
        # Auto ownership checks
        if 'auto_ownership' in filename:
            if 'num_vehicles' in df.columns:
                max_autos = df['num_vehicles'].max()
                if max_autos > 10:
                    self.warnings.append(
                        f"{filename}: Maximum vehicles is {max_autos}, seems high"
                    )
        
        # Age distribution checks
        if 'age' in filename and 'age_bin' in df.columns:
            # Check if we have all expected age bins (from ctramp_data_model.yaml)
            expected_bins = ['0-4', '5-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+']
            missing_bins = [b for b in expected_bins if b not in df['age_bin'].values]
            if missing_bins:
                self.warnings.append(
                    f"{filename}: Missing age bins: {', '.join(missing_bins)}"
                )
        
        # Mode distribution checks
        if 'mode' in filename and 'mode_name' in df.columns:
            # Check for transit modes without any trips
            transit_modes = df[df.apply(lambda row: 'TRN' in str(row.get('tour_mode_name', '')) or 
                                                     'TRN' in str(row.get('trip_mode_name', '')), axis=1)]
            if len(transit_modes) > 0:
                count_col = [c for c in df.columns if c in ['trips', 'tours']]
                if count_col:
                    transit_total = transit_modes[count_col[0]].sum()
                    overall_total = df[count_col[0]].sum()
                    transit_share = transit_total / overall_total if overall_total > 0 else 0
                    
                    # Flag if transit is < 0.1% or > 50% (both unusual)
                    if transit_share < 0.001:
                        self.warnings.append(
                            f"{filename}: Transit share is very low ({transit_share*100:.2f}%)"
                        )
                    elif transit_share > 0.5:
                        self.warnings.append(
                            f"{filename}: Transit share is very high ({transit_share*100:.2f}%)"
                        )
        
        # Time period checks
        if 'time' in filename or 'period' in df.columns:
            period_cols = [c for c in df.columns if 'period' in c.lower()]
            for col in period_cols:
                if pd.api.types.is_numeric_dtype(df[col]):
                    min_period = df[col].min()
                    max_period = df[col].max()
                    
                    # Time periods should be 1-40 or 1-48
                    if min_period < 1:
                        self.issues.append(f"{filename}: {col} has values < 1")
                    if max_period > 48:
                        self.issues.append(f"{filename}: {col} has values > 48")
        
        # Household size checks
        if 'household_size' in filename or 'num_persons' in df.columns:
            if 'num_persons' in df.columns:
                max_size = df['num_persons'].max()
                if max_size > 15:
                    self.warnings.append(
                        f"{filename}: Maximum household size is {max_size}"
                    )
                if (df['num_persons'] == 0).any():
                    self.issues.append(f"{filename}: Contains households with 0 persons")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Validate CTRAMP summary outputs for data quality issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('output_dir', type=str, help='Directory containing summary CSV files')
    parser.add_argument('--strict', action='store_true', 
                       help='Treat warnings as errors (return non-zero exit code)')
    
    args = parser.parse_args()
    
    # Validate directory exists
    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        logger.error(f"Error: Directory not found: {output_dir}")
        sys.exit(1)
    
    # Run validation
    validator = SummaryValidator(output_dir)
    issues, warnings = validator.validate_all()
    
    # Exit with appropriate code
    if issues:
        sys.exit(2)  # Issues found
    elif warnings and args.strict:
        sys.exit(1)  # Warnings in strict mode
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
