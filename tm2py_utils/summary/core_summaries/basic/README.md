# TM2 Mode Share Analysis

Transportation-focused analysis tool for Travel Model Two (TM2) core summaries, with emphasis on mode share patterns using treemap visualizations and proper TM2 mode labels.

## Overview

This tool analyzes TM2 trip data to understand:
- **Overall mode share** across all trips
- **Mode share by trip purpose** (work, school, shopping, etc.)
- **Mode share by time period** (AM peak, midday, PM peak, etc.)
- **Auto ownership patterns** by income and demographics

## Key Features

### TM2-Specific Design
- Uses proper TM2 mode codes and labels from CTRAMP documentation
- Understands transportation planning concepts (HOV lanes, park & ride, etc.)
- Categorizes modes meaningfully for transportation analysis
- Handles TM2 time periods and trip purposes correctly

### Visualizations
- **Bar charts** for clear, reliable data display
- Interactive HTML outputs with hover details
- High-quality PNG exports for reports
- Proper within-purpose percentages (each purpose sums to 100%)

### Mode Categories
- **Auto - Solo**: Drive Alone (Free/Toll)
- **Auto - Shared**: HOV2/3+ (GP/HOV/Toll lanes)  
- **Transit**: Walk/Park & Ride/Kiss & Ride to transit
- **Active**: Walk and Bike
- **TNC/Taxi**: Commercial ride services

## Usage

### Basic Usage (Default Output Location)
```bash
python tm2_mode_analysis.py --data-dir "path/to/core_summaries"
# Results automatically saved to: path/to/core_summaries/agg/
```

### With TM2 Default Path
```bash
python tm2_mode_analysis.py --data-dir "E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Outputs\2015-tm22-dev-sprint-04\core_summaries"
# Results saved to: E:\Box\...\core_summaries\agg\
```

### Custom Output Location
```bash
python tm2_mode_analysis.py --data-dir "path/to/core_summaries" --output-dir "custom/results/path"
```

### Run Example
```bash
python run_example.py
```

## Expected Input Files

The tool looks for these TM2 core summary files:
- `TripSummaryByMode.csv` - Overall mode share (main analysis)
- `TripSummaryByModePurpose.csv` - Mode by trip purpose
- `TripSummaryByModeTimePeriod.csv` - Mode by time of day
- `AutomobileOwnership.csv` - Demographic analysis
- `TripSummaryByPurpose.csv` - Purpose totals
- `TripSummarySimpleModePurpose.csv` - Simplified breakdowns

**Note**: The analysis runs with whatever files are available. Missing files are skipped gracefully.

### Outputs

### Bar Chart Visualizations
- `mode_share_overall.html/png` - Overall mode share bar chart
- `mode_share_by_purpose.html/png` - Mode share by trip purpose (each purpose sums to 100%)

### Data Summary
- `tm2_mode_analysis_summary.xlsx` - All analysis results in Excel format

### Example Output Structure
```
results/
├── mode_share_overall.html          # Interactive overall mode share
├── mode_share_overall.png           # Static image for reports
├── mode_share_by_purpose.html       # Interactive purpose breakdown
├── mode_share_by_purpose.png        # Static purpose image
└── tm2_mode_analysis_summary.xlsx   # Complete data tables
```

## Configuration

Edit `config.toml` to customize:
- Default data paths
- Which analyses to run
- Visualization settings
- Mode filtering options

## TM2 Mode Codes Reference

| Code | Mode Label | Category |
|------|------------|----------|
| 1 | Drive Alone (Free) | Auto - Solo |
| 2 | Drive Alone (Toll) | Auto - Solo |
| 3-8 | HOV2/3+ variants | Auto - Shared |
| 9 | Walk | Active |
| 10 | Bike | Active |
| 11-14 | Transit access modes | Transit |
| 15-16 | Taxi/TNC | TNC/Taxi |

## Requirements

- Python 3.7+
- pandas
- plotly 
- kaleido (for PNG export)
- openpyxl (for Excel output)

Install in tm2py-utils environment:
```bash
conda activate tm2py-utils
pip install plotly kaleido openpyxl
```

## Transportation Planning Context

This tool is designed for transportation planners working with TM2 outputs. It:
- Uses transportation industry standard terminology
- Focuses on policy-relevant mode categories
- Provides hierarchical analysis suitable for different planning levels
- Generates publication-ready visualizations

## Future Enhancements

- Geographic analysis (TAZ/county level)
- Income-based mode choice analysis  
- Temporal trend analysis across model runs
- Integration with other TM2 summary tools