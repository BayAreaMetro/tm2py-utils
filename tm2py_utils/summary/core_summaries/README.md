# Core Summaries Analysis Tools

This directory contains analysis tools for processing TM2 core summaries output files.

## Directory Structure

```
core_summaries/
└── basic/                          # Basic analysis tools
    ├── aggregated_analysis.py      # Main analysis script
    ├── analysis_config.toml        # Configuration file for TM2 data
    ├── discover_files.py           # File discovery utility
    ├── example_usage.py            # Example/test script
    ├── requirements.txt            # Python dependencies
    └── README.md                   # Detailed documentation
```

## Quick Start

1. **Install dependencies:**
   ```bash
   cd core_summaries/basic
   pip install -r requirements.txt
   ```

2. **Discover your files:**
   ```bash
   python discover_files.py
   ```

3. **Run analysis:**
   ```bash
   python aggregated_analysis.py analysis_config.toml
   ```

## What's Included

### `aggregated_analysis.py`
- **Main analysis script** for TM2 core summaries
- Automatically loads and categorizes files by type (trips, tours, etc.)
- Generates comprehensive Excel workbook with multiple analysis sheets
- Creates interactive HTML and static PNG visualizations
- Configurable through TOML files or interactive prompts

### `analysis_config.toml`
- **Pre-configured for TM2 data** with correct file patterns
- Points to your actual data location: `E:\Box\...\core_summaries`
- Includes TM2-specific analysis categories and field names
- Ready to use with your 15 core summary files

### `discover_files.py`
- **File discovery utility** to explore your data directory
- Shows what files are available and their structure
- Samples the first few rows to understand data format
- Helps verify file patterns before running full analysis

### Current Data Files (Auto-Detected)
Based on your directory, the script will analyze:
- ActivityPattern.csv
- AutomobileOwnership.csv/.xlsx
- JourneyToWork.csv
- TimeOfDay.csv (multiple variants)
- TourSummary*.csv (by mode, purpose, etc.)
- TripSummary*.csv (by mode, purpose, time period, etc.)

## Analysis Outputs

The script generates:

### Excel Workbook (`aggregated_analysis_results.xlsx`)
- **Summary sheet**: Overview of all datasets
- **Statistics sheets**: Detailed stats for each file
- **Shares sheets**: Mode shares, purpose distributions, etc.
- **Cross-tabulation sheets**: Geographic vs demographic breakdowns

### Interactive Visualizations (`html/`)
- **Dashboard**: Overview of all datasets with charts
- **Distribution plots**: Histograms for numeric variables
- **Pie charts**: Shares for categorical variables

### Static Images (`png/`)
- All charts as PNG files for reports and presentations

## Configuration

The analysis is pre-configured for TM2 with:

**File Patterns:**
- Trip summaries: `*TripSummary*`
- Tour summaries: `*TourSummary*`
- Activity patterns: `*ActivityPattern*`
- Auto ownership: `*AutomobileOwnership*`
- Journey to work: `*JourneyToWork*`
- Time of day: `*TimeOfDay*`

**Analysis Categories:**
- Geography: DistID, CountyID
- Demographics: Income quartiles, workers, auto ownership
- Travel behavior: Mode choice, trip purposes, time periods
- Activity patterns: CDAP types, model choices

## Next Steps

This is the "basic" analysis toolkit. Future expansions could include:
- `advanced/` - More sophisticated statistical analysis
- `validation/` - Model validation and comparison tools  
- `visualization/` - Specialized charts and dashboards
- `reporting/` - Automated report generation

## Support

For questions or issues:
1. Check the README.md for detailed documentation
2. Run `discover_files.py` to verify your data structure
3. Review the configuration file settings
4. Check that all required packages are installed