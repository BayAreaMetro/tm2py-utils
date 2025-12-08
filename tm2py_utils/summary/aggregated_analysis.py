"""
Aggregated Output Analysis Script

This script analyzes pre-aggregated output files, creates summaries, shares, and distributions,
and outputs Excel files with multiple sheets and data visualizations.

Usage:
    python aggregated_analysis.py [config_file]
    
If no config file is provided, the script will prompt for input directory and output location,
or you can modify the configuration section below.

Example:
    python aggregated_analysis.py analysis_config.toml
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import argparse
import warnings
warnings.filterwarnings('ignore')

# Try to import toml for config file support
try:
    import toml
    HAS_TOML = True
except ImportError:
    HAS_TOML = False
    print("Warning: toml package not available. Config file support disabled.")

# ============================================================================
# CONFIGURATION SECTION - Modify these paths as needed
# ============================================================================

# Input directory containing pre-aggregated files
INPUT_DIR = Path(r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Outputs\2015-tm22-dev-sprint-04\core_summaries")

# Output directory for results
OUTPUT_DIR = Path(r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Outputs\2015-tm22-dev-sprint-04\analysis_output")

# File patterns to look for (based on TM2 core summaries files)
FILE_PATTERNS = {
    'trip_summaries': '*TripSummary*',
    'tour_summaries': '*TourSummary*', 
    'activity_patterns': '*ActivityPattern*',
    'automobile_ownership': '*AutomobileOwnership*',
    'journey_to_work': '*JourneyToWork*',
    'time_of_day': '*TimeOfDay*',
    'mode_choice': '*Mode*',
    'purpose_analysis': '*Purpose*',
    'time_period': '*TimePeriod*',
    'all_files': '*'  # Catch-all pattern to find any CSV/Excel files
}

# Analysis categories for grouping and aggregation (TM2 specific)
ANALYSIS_CATEGORIES = {
    'geography': ['DistID', 'CountyID', 'taz', 'district'],
    'demographics': ['incQ', 'incQ_label', 'workers', 'kidsNoDr', 'autos'],
    'trip_purpose': ['work', 'school', 'shop', 'other', 'purpose'],
    'travel_mode': ['mode', 'simple_mode'],
    'time_period': ['time_period', 'tod'],
    'activity_patterns': ['type', 'cdap', 'imf_choice', 'inmf_choice'],
    'household_characteristics': ['autos', 'workers', 'income_quartile']
}

# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def load_config(config_file_path):
    """Load configuration from TOML file."""
    if not HAS_TOML:
        print("TOML package not available. Using default configuration.")
        return None
    
    try:
        with open(config_file_path, 'r') as f:
            config = toml.load(f)
        print(f"Loaded configuration from: {config_file_path}")
        return config
    except Exception as e:
        print(f"Error loading config file {config_file_path}: {e}")
        return None

def apply_config(config):
    """Apply configuration settings to global variables."""
    global INPUT_DIR, OUTPUT_DIR, FILE_PATTERNS, ANALYSIS_CATEGORIES
    
    if config is None:
        return
    
    # Update paths
    if 'paths' in config:
        if 'input_directory' in config['paths']:
            INPUT_DIR = Path(config['paths']['input_directory'])
        if 'output_directory' in config['paths']:
            OUTPUT_DIR = Path(config['paths']['output_directory'])
    
    # Update file patterns
    if 'file_patterns' in config:
        FILE_PATTERNS.update(config['file_patterns'])
    
    # Update analysis categories
    if 'analysis_categories' in config:
        ANALYSIS_CATEGORIES.update(config['analysis_categories'])

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def setup_directories():
    """Create output directories if they don't exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / 'excel').mkdir(exist_ok=True)
    (OUTPUT_DIR / 'visualizations').mkdir(exist_ok=True)
    (OUTPUT_DIR / 'html').mkdir(exist_ok=True)
    (OUTPUT_DIR / 'png').mkdir(exist_ok=True)
    print(f"Output directories created at: {OUTPUT_DIR}")

def get_user_paths():
    """Get input and output paths from user if default paths don't exist."""
    global INPUT_DIR, OUTPUT_DIR
    
    if not INPUT_DIR.exists():
        input_path = input(f"Input directory '{INPUT_DIR}' not found.\nEnter path to directory with aggregated files: ")
        INPUT_DIR = Path(input_path)
        
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"Input directory not found: {INPUT_DIR}")
    
    output_path = input(f"Enter output directory (default: {OUTPUT_DIR}): ").strip()
    if output_path:
        OUTPUT_DIR = Path(output_path)
    
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")

def load_aggregated_files():
    """Load all aggregated files from the input directory."""
    files_data = {}
    all_found_files = []
    
    print(f"\nScanning directory: {INPUT_DIR}")
    
    # First, discover all CSV and Excel files
    all_csv_files = list(INPUT_DIR.glob('*.csv'))
    all_xlsx_files = list(INPUT_DIR.glob('*.xlsx'))
    all_files = all_csv_files + all_xlsx_files
    
    print(f"Found {len(all_files)} data files:")
    for file in all_files:
        print(f"  {file.name}")
    
    if not all_files:
        print("No CSV or Excel files found in the input directory.")
        return files_data
    
    print("\nCategorizing and loading files...")
    
    # Track which files have been categorized
    categorized_files = set()
    
    for category, pattern in FILE_PATTERNS.items():
        if category == 'all_files':  # Skip the catch-all for now
            continue
            
        # Look for files matching the pattern
        matching_files = []
        for file in all_files:
            if pattern.replace('*', '').lower() in file.name.lower():
                matching_files.append(file)
                categorized_files.add(file)
        
        if matching_files:
            print(f"\n{category.upper()} files: {[f.name for f in matching_files]}")
            category_data = {}
            
            for file_path in matching_files:
                try:
                    if file_path.suffix.lower() == '.csv':
                        df = pd.read_csv(file_path)
                    elif file_path.suffix.lower() == '.xlsx':
                        df = pd.read_excel(file_path)
                    else:
                        continue
                    
                    category_data[file_path.stem] = df
                    print(f"  ✓ Loaded {file_path.name}: {df.shape[0]} rows, {df.shape[1]} columns")
                    
                except Exception as e:
                    print(f"  ✗ Error loading {file_path.name}: {e}")
            
            if category_data:
                files_data[category] = category_data
    
    # Handle uncategorized files
    uncategorized_files = [f for f in all_files if f not in categorized_files]
    if uncategorized_files:
        print(f"\nUNCATEGORIZED files: {[f.name for f in uncategorized_files]}")
        other_data = {}
        
        for file_path in uncategorized_files:
            try:
                if file_path.suffix.lower() == '.csv':
                    df = pd.read_csv(file_path)
                elif file_path.suffix.lower() == '.xlsx':
                    df = pd.read_excel(file_path)
                else:
                    continue
                
                other_data[file_path.stem] = df
                print(f"  ✓ Loaded {file_path.name}: {df.shape[0]} rows, {df.shape[1]} columns")
                
            except Exception as e:
                print(f"  ✗ Error loading {file_path.name}: {e}")
        
        if other_data:
            files_data['other'] = other_data
    
    print(f"\nSuccessfully loaded {sum(len(datasets) for datasets in files_data.values())} datasets")
    return files_data

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def calculate_summaries(data_dict):
    """Calculate summary statistics for each dataset."""
    summaries = {}
    
    print("\nCalculating summaries...")
    for category, datasets in data_dict.items():
        category_summaries = {}
        
        for dataset_name, df in datasets.items():
            summary = {
                'total_records': len(df),
                'numeric_columns': df.select_dtypes(include=[np.number]).columns.tolist(),
                'categorical_columns': df.select_dtypes(include=['object']).columns.tolist(),
                'summary_stats': df.describe() if not df.empty else pd.DataFrame(),
                'missing_values': df.isnull().sum().to_dict(),
                'column_totals': df.select_dtypes(include=[np.number]).sum().to_dict() if not df.empty else {}
            }
            category_summaries[dataset_name] = summary
            print(f"  Summarized {category}/{dataset_name}")
        
        summaries[category] = category_summaries
    
    return summaries

def calculate_shares_and_distributions(data_dict):
    """Calculate shares and distributions for categorical variables."""
    shares_distributions = {}
    
    print("\nCalculating shares and distributions...")
    for category, datasets in data_dict.items():
        category_analysis = {}
        
        for dataset_name, df in datasets.items():
            if df.empty:
                continue
                
            analysis = {}
            
            # Calculate shares for categorical columns
            categorical_cols = df.select_dtypes(include=['object']).columns
            for col in categorical_cols:
                if col in df.columns:
                    value_counts = df[col].value_counts()
                    shares = (value_counts / len(df) * 100).round(2)
                    analysis[f'{col}_shares'] = shares.to_dict()
            
            # Calculate distributions for numeric columns
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if col in df.columns and not df[col].isnull().all():
                    # Create bins for distribution
                    try:
                        bins = pd.cut(df[col].dropna(), bins=10, precision=2)
                        distribution = bins.value_counts(sort=False)
                        analysis[f'{col}_distribution'] = distribution.to_dict()
                    except Exception as e:
                        print(f"    Could not create distribution for {col}: {e}")
            
            category_analysis[dataset_name] = analysis
            print(f"  Analyzed {category}/{dataset_name}")
        
        shares_distributions[category] = category_analysis
    
    return shares_distributions

def create_cross_tabulations(data_dict):
    """Create cross-tabulations between key variables."""
    cross_tabs = {}
    
    print("\nCreating cross-tabulations...")
    for category, datasets in data_dict.items():
        category_crosstabs = {}
        
        for dataset_name, df in datasets.items():
            if df.empty or len(df.columns) < 2:
                continue
            
            crosstabs = {}
            categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
            
            # Create cross-tabs between categorical variables
            if len(categorical_cols) >= 2:
                for i, col1 in enumerate(categorical_cols[:3]):  # Limit to first 3 to avoid too many combinations
                    for col2 in categorical_cols[i+1:4]:
                        if col1 != col2:
                            try:
                                crosstab = pd.crosstab(df[col1], df[col2], margins=True)
                                crosstabs[f'{col1}_vs_{col2}'] = crosstab
                            except Exception as e:
                                print(f"    Could not create crosstab for {col1} vs {col2}: {e}")
            
            category_crosstabs[dataset_name] = crosstabs
            if crosstabs:
                print(f"  Created cross-tabs for {category}/{dataset_name}")
        
        cross_tabs[category] = category_crosstabs
    
    return cross_tabs

# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def create_excel_output(summaries, shares_distributions, cross_tabs):
    """Create comprehensive Excel workbook with multiple sheets."""
    print("\nCreating Excel output...")
    
    output_file = OUTPUT_DIR / 'excel' / 'aggregated_analysis_results.xlsx'
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        
        # Summary sheet
        summary_rows = []
        for category, datasets in summaries.items():
            for dataset_name, summary in datasets.items():
                row = {
                    'Category': category,
                    'Dataset': dataset_name,
                    'Total Records': summary['total_records'],
                    'Numeric Columns': len(summary['numeric_columns']),
                    'Categorical Columns': len(summary['categorical_columns']),
                    'Columns with Missing Values': sum(1 for v in summary['missing_values'].values() if v > 0)
                }
                summary_rows.append(row)
        
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Detailed statistics for each dataset
        for category, datasets in summaries.items():
            for dataset_name, summary in datasets.items():
                if not summary['summary_stats'].empty:
                    sheet_name = f"{category}_{dataset_name}_stats"[:31]  # Excel sheet name limit
                    summary['summary_stats'].to_excel(writer, sheet_name=sheet_name)
        
        # Shares and distributions
        for category, datasets in shares_distributions.items():
            for dataset_name, analysis in datasets.items():
                if analysis:
                    sheet_name = f"{category}_{dataset_name}_shares"[:31]
                    
                    # Combine all shares and distributions into one sheet
                    combined_data = []
                    for metric_name, values in analysis.items():
                        for key, value in values.items():
                            combined_data.append({
                                'Metric': metric_name,
                                'Category': str(key),
                                'Value': value
                            })
                    
                    if combined_data:
                        shares_df = pd.DataFrame(combined_data)
                        shares_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Cross-tabulations
        for category, datasets in cross_tabs.items():
            for dataset_name, crosstabs in datasets.items():
                for crosstab_name, crosstab_df in crosstabs.items():
                    sheet_name = f"{category}_{crosstab_name}"[:31]
                    crosstab_df.to_excel(writer, sheet_name=sheet_name)
    
    print(f"Excel file created: {output_file}")
    return output_file

def create_visualizations(data_dict, summaries, shares_distributions):
    """Create HTML and PNG visualizations."""
    print("\nCreating visualizations...")
    
    # Create summary dashboard
    create_summary_dashboard(summaries)
    
    # Create individual charts for each dataset
    for category, datasets in data_dict.items():
        for dataset_name, df in datasets.items():
            if df.empty:
                continue
            
            create_dataset_visualizations(df, category, dataset_name)
    
    # Create distribution charts
    create_distribution_charts(shares_distributions)

def create_summary_dashboard(summaries):
    """Create an HTML dashboard with summary statistics."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Dataset Sizes', 'Column Types', 'Missing Values', 'Data Quality'),
        specs=[[{"type": "bar"}, {"type": "bar"}],
               [{"type": "bar"}, {"type": "scatter"}]]
    )
    
    # Prepare data for charts
    categories, datasets, record_counts, numeric_cols, categorical_cols, missing_counts = [], [], [], [], [], []
    
    for category, datasets_info in summaries.items():
        for dataset_name, summary in datasets_info.items():
            categories.append(category)
            datasets.append(dataset_name)
            record_counts.append(summary['total_records'])
            numeric_cols.append(len(summary['numeric_columns']))
            categorical_cols.append(len(summary['categorical_columns']))
            missing_counts.append(sum(1 for v in summary['missing_values'].values() if v > 0))
    
    # Dataset sizes
    fig.add_trace(
        go.Bar(x=datasets, y=record_counts, name="Record Count"),
        row=1, col=1
    )
    
    # Column types
    fig.add_trace(
        go.Bar(x=datasets, y=numeric_cols, name="Numeric Columns"),
        row=1, col=2
    )
    fig.add_trace(
        go.Bar(x=datasets, y=categorical_cols, name="Categorical Columns"),
        row=1, col=2
    )
    
    # Missing values
    fig.add_trace(
        go.Bar(x=datasets, y=missing_counts, name="Columns with Missing Values"),
        row=2, col=1
    )
    
    # Data quality scatter
    fig.add_trace(
        go.Scatter(x=record_counts, y=missing_counts, mode='markers+text',
                  text=datasets, textposition="top center", name="Quality vs Size"),
        row=2, col=2
    )
    
    fig.update_layout(height=800, title_text="Aggregated Data Analysis Dashboard")
    
    # Save as HTML
    html_file = OUTPUT_DIR / 'html' / 'summary_dashboard.html'
    fig.write_html(html_file)
    
    # Save as PNG
    png_file = OUTPUT_DIR / 'png' / 'summary_dashboard.png'
    fig.write_image(png_file, width=1200, height=800)
    
    print(f"Dashboard created: {html_file}")

def create_dataset_visualizations(df, category, dataset_name):
    """Create visualizations for a specific dataset."""
    if df.empty:
        return
    
    # Create subplots for numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()[:4]  # Limit to 4 columns
    
    if numeric_cols:
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[f'{col} Distribution' for col in numeric_cols[:4]]
        )
        
        positions = [(1,1), (1,2), (2,1), (2,2)]
        
        for i, col in enumerate(numeric_cols[:4]):
            if i < len(positions):
                row, col_pos = positions[i]
                fig.add_trace(
                    go.Histogram(x=df[col].dropna(), name=col, showlegend=False),
                    row=row, col=col_pos
                )
        
        fig.update_layout(height=600, title_text=f"{category} - {dataset_name} Distributions")
        
        # Save files
        safe_name = f"{category}_{dataset_name}".replace(' ', '_').replace('/', '_')
        html_file = OUTPUT_DIR / 'html' / f'{safe_name}_distributions.html'
        png_file = OUTPUT_DIR / 'png' / f'{safe_name}_distributions.png'
        
        fig.write_html(html_file)
        fig.write_image(png_file, width=1000, height=600)

def create_distribution_charts(shares_distributions):
    """Create pie charts and bar charts for shares and distributions."""
    for category, datasets in shares_distributions.items():
        for dataset_name, analysis in datasets.items():
            for metric_name, values in analysis.items():
                if '_shares' in metric_name and values:
                    # Create pie chart for shares
                    labels = list(values.keys())
                    sizes = list(values.values())
                    
                    fig = go.Figure(data=[go.Pie(labels=labels, values=sizes)])
                    fig.update_layout(title=f"{category} - {dataset_name} - {metric_name}")
                    
                    safe_name = f"{category}_{dataset_name}_{metric_name}".replace(' ', '_').replace('/', '_')
                    html_file = OUTPUT_DIR / 'html' / f'{safe_name}_pie.html'
                    png_file = OUTPUT_DIR / 'png' / f'{safe_name}_pie.png'
                    
                    fig.write_html(html_file)
                    fig.write_image(png_file, width=800, height=600)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    print("=" * 70)
    print("AGGREGATED OUTPUT ANALYSIS SCRIPT")
    print("=" * 70)
    
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Analyze aggregated output files')
        parser.add_argument('config', nargs='?', help='Configuration file path (optional)')
        args = parser.parse_args()
        
        # Load configuration if provided
        config = None
        if args.config:
            config_path = Path(args.config)
            if config_path.exists():
                config = load_config(config_path)
                apply_config(config)
            else:
                print(f"Config file not found: {config_path}")
        
        # Setup
        get_user_paths()
        setup_directories()
        
        # Load data
        data_dict = load_aggregated_files()
        
        if not data_dict:
            print("No data files found. Please check your input directory and file patterns.")
            print("Available file patterns:")
            for category, pattern in FILE_PATTERNS.items():
                print(f"  {category}: {pattern}")
            return
        
        # Perform analysis
        summaries = calculate_summaries(data_dict)
        shares_distributions = calculate_shares_and_distributions(data_dict)
        cross_tabs = create_cross_tabulations(data_dict)
        
        # Create outputs
        excel_file = create_excel_output(summaries, shares_distributions, cross_tabs)
        create_visualizations(data_dict, summaries, shares_distributions)
        
        print("\n" + "=" * 70)
        print("ANALYSIS COMPLETE!")
        print("=" * 70)
        print(f"Results saved to: {OUTPUT_DIR}")
        print(f"Excel file: {excel_file}")
        print(f"HTML visualizations: {OUTPUT_DIR / 'html'}")
        print(f"PNG visualizations: {OUTPUT_DIR / 'png'}")
        print("\nOutput structure:")
        print(f"  📁 {OUTPUT_DIR}")
        print(f"    📁 excel/")
        print(f"      📄 aggregated_analysis_results.xlsx")
        print(f"    📁 html/")
        print(f"      📄 summary_dashboard.html")
        print(f"      📄 *_distributions.html")
        print(f"      📄 *_pie.html")
        print(f"    📁 png/")
        print(f"      🖼️  summary_dashboard.png")
        print(f"      🖼️  *_distributions.png")
        print(f"      🖼️  *_pie.png")
        
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()