# Generalized SimWrapper Analysis Framework

This framework provides a flexible, configuration-driven approach to creating SimWrapper dashboards for various types of transportation analysis.

## What Was Generalized

The original script was hardcoded for free parking analysis with two specific scenarios. It has been generalized to support:

1. **Configurable Analysis Types**: Any analysis module can be plugged in
2. **Flexible Scenarios**: Any number of scenarios with custom parameters
3. **Adaptive Data Generation**: Person data generation adapts to scenario parameters
4. **Dynamic Dashboard Creation**: Charts and visualizations are configured per analysis type
5. **Modular Analysis Functions**: Analysis functions are loaded dynamically

## How to Use

### 1. Basic Usage (uses default free parking config)
```bash
python test_simwrapper_free_parking_fixed.py
```

### 2. With Custom Configuration
```bash
python test_simwrapper_free_parking_fixed.py --config example_analysis_config.yaml
```

### 3. With Different Parameters
```bash
python test_simwrapper_free_parking_fixed.py \
    --config example_mode_choice_config.yaml \
    --output-dir mode_choice_output \
    --n-persons 5000 \
    --launch
```

## Configuration File Structure

Configuration files can be YAML or TOML format and contain three main sections:

### Analysis Configuration
```yaml
analysis:
  type: "analysis_name"              # Used for file naming
  module: "analysis_module"          # Python module to import
  load_function: "load_data_func"    # Function to load data
  analysis_function: "analyze_func"  # Function to run analysis  
  save_function: "save_func"         # Function to save results
  title: "Display Title"             # For dashboards
  description: "Analysis description"
```

### Scenarios Configuration
```yaml
scenarios:
  - name: "scenario_id"              # Internal identifier
    display_name: "Scenario Name"   # Display name
    parameters:                     # Passed to data generation
      param1: value1
      param2: value2
```

### SimWrapper Configuration
```yaml
simwrapper:
  charts:
    - title: "Chart Title"
      type: "bar|line|histogram|etc"
      file: "data_file.csv"
      x: "x_column"
      y: "y_column"
      groupBy: "group_column"       # Optional
      style:                        # Optional
        height: "400"
```

## Analysis Module Requirements

Your analysis module should provide three functions:

1. **Load Function**: `load_function(file_path) -> DataFrame`
   - Loads person/trip data from CSV
   
2. **Analysis Function**: `analysis_function(data, scenario_name) -> Dict[str, DataFrame]`
   - Analyzes the data and returns summary tables
   - Should return dict with keys like 'regional_summary', 'person_type_summary', etc.
   
3. **Save Function**: `save_function(summaries, output_dir)`
   - Saves analysis results to files

## Example Analysis Modules

### Free Parking Analysis
- Module: `free_parking_analysis.py`
- Analyzes workplace free parking availability
- Returns summaries by choice, person type, etc.

### Mode Choice Analysis  
- Module: `mode_choice_analysis.py`
- Analyzes transportation mode selection
- Returns summaries by mode, income level, etc.

## Data Generation

The framework generates synthetic person data with these base attributes:
- `hh_id`, `person_id`, `person_num`
- `person_type`, `age`, `income_cat`
- `home_taz`, `work_taz`
- `scenario` (metadata)

Additional fields are added based on scenario parameters:
- Any parameter in the config becomes a column if it's a scalar value
- Arrays of length n_persons become columns directly

## SimWrapper Output

The framework creates several standard files:
- `{analysis_type}_comparison.csv`: Main comparison data
- `{analysis_type}_by_category.csv`: Breakdown by categories  
- `scenario_metadata.csv`: Scenario information
- `dashboard.yaml`: SimWrapper dashboard configuration
- `topsheet.yaml`: Summary statistics configuration
- `launch_simwrapper.py`: Launch script for local viewing

## Extending the Framework

To add a new analysis type:

1. Create an analysis module with the three required functions
2. Create a configuration file specifying your module and parameters
3. Run with `--config your_config.yaml`

The framework will handle:
- Data generation with your custom parameters
- Loading your analysis functions
- Creating appropriate SimWrapper visualizations
- Generating dashboards

## Benefits

- **Reusable**: One codebase supports multiple analysis types
- **Configurable**: No code changes needed for new scenarios
- **Maintainable**: Clear separation of concerns
- **Extensible**: Easy to add new analysis types
- **Consistent**: Same output format and dashboard structure

## Requirements

- pandas, numpy, yaml, pathlib
- Your analysis module (e.g., `free_parking_analysis.py`)
- SimWrapper installed for viewing dashboards

## Files

- `test_simwrapper_free_parking_fixed.py`: Main generalized framework
- `example_analysis_config.yaml`: Free parking configuration example
- `example_mode_choice_config.yaml`: Mode choice configuration example
- This README explaining usage