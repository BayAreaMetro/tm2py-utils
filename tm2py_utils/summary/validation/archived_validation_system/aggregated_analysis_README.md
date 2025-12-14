# Aggregated Analysis Script

This script (`aggregated_analysis.py`) is designed to analyze pre-aggregated output files from transportation models, create comprehensive summaries, and generate data visualizations.

## Features

- **Automated File Loading**: Discovers and loads CSV/Excel files based on configurable patterns
- **Statistical Analysis**: Calculates summary statistics, shares, distributions, and cross-tabulations  
- **Excel Output**: Creates multi-sheet Excel workbook with organized results
- **Data Visualizations**: Generates HTML and PNG charts using Plotly
- **Summary Dashboard**: Creates comprehensive overview dashboard
- **Configurable**: Supports TOML configuration files for customization

## Installation

Install required packages:

```bash
pip install pandas numpy matplotlib seaborn openpyxl plotly kaleido toml
```

Or if you're in the tm2py-utils environment:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage (Interactive)
```bash
python aggregated_analysis.py
```
The script will prompt for input and output directories.

### Using Configuration File
```bash
python aggregated_analysis.py analysis_config.toml
```

### Configuration File Example

Create a `analysis_config.toml` file:

```toml
[paths]
input_directory = "C:/data/model_outputs/aggregated"
output_directory = "C:/results/analysis"

[file_patterns]
trips = "*trip*"
households = "*hh*"  
persons = "*person*"
employment = "*emp*"

[analysis_categories]
geography = ["taz", "maz", "district", "county"]
demographics = ["income", "age", "hh_size", "workers"]
```

## Input File Requirements

The script expects CSV or Excel files in the input directory matching the specified patterns:

- **File naming**: Files should follow patterns like `*trip*.csv`, `*hh*.xlsx`, etc.
- **Data format**: Standard tabular data with columns and rows
- **File types**: Supports `.csv` and `.xlsx` formats

## Output Structure

```
output_directory/
├── excel/
│   └── aggregated_analysis_results.xlsx  # Multi-sheet summary workbook
├── html/
│   ├── summary_dashboard.html           # Interactive overview dashboard
│   ├── *_distributions.html             # Distribution charts for datasets
│   └── *_pie.html                       # Share/proportion charts
└── png/
    ├── summary_dashboard.png             # Static overview charts
    ├── *_distributions.png               # Static distribution charts
    └── *_pie.png                         # Static share charts
```

## Excel Output Sheets

- **Summary**: Overview of all datasets (record counts, column types, etc.)
- **[Dataset]_stats**: Detailed statistics for each dataset
- **[Dataset]_shares**: Shares and distributions for categorical variables  
- **[Dataset]_crosstab**: Cross-tabulations between key variables

## Customization

### File Patterns
Modify the `FILE_PATTERNS` dictionary in the script or config file:

```python
FILE_PATTERNS = {
    'trips': '*trip*',
    'households': '*hh*',
    'custom_data': '*my_pattern*'
}
```

### Analysis Categories
Configure analysis groupings:

```python
ANALYSIS_CATEGORIES = {
    'geography': ['taz', 'maz', 'district'],
    'demographics': ['income', 'age', 'hh_size'],
    'custom_category': ['field1', 'field2']
}
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Install missing packages with pip
2. **File Not Found**: Check input directory path and file patterns
3. **Empty Results**: Verify file naming matches expected patterns
4. **Memory Issues**: For large datasets, consider processing subsets

### Debug Mode

Add print statements or modify the logging level in the script for more detailed output.

## Dependencies

- `pandas`: Data manipulation and analysis
- `numpy`: Numerical computing
- `matplotlib`: Basic plotting
- `seaborn`: Statistical visualizations  
- `openpyxl`: Excel file handling
- `plotly`: Interactive charts
- `kaleido`: Static image export for Plotly
- `toml`: Configuration file parsing (optional)

## Examples

### Analyzing Travel Model Outputs

For TM2 model outputs, you might have files like:
- `trip_summary_am.csv`
- `hh_characteristics.xlsx`  
- `person_demographics.csv`

The script will automatically:
1. Load and summarize each dataset
2. Calculate mode shares, purpose distributions
3. Create cross-tabs between geography and demographics  
4. Generate visualizations showing patterns and trends

### Custom Analysis

Modify the analysis functions to add:
- Custom aggregation logic
- Specific validation checks
- Domain-specific calculations
- Additional chart types

## Contributing

To extend the script:
1. Add new analysis functions following existing patterns
2. Update configuration options as needed
3. Add corresponding visualization functions
4. Test with representative datasets