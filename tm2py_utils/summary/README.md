# CTRAMP Summary and Validation System

This directory contains a comprehensive system for analyzing and validating transportation model outputs, with a focus on CTRAMP (Cube Transportation Resource Allocation Model Platform) data processing and ActivitySim integration.

## Directory Structure

### Core System Files
- `run_all_validation_summaries.py` - Main orchestrator for comprehensive validation analysis
- `ctramp_models.py` - Pydantic data models for CTRAMP file validation and type safety
- `validation_config.yaml` - Configuration template for validation analysis parameters
- `test_summary_system.py` - Test suite for validation system components

### Validation Directory (`validation/`)
Focused analysis scripts and results for specific validation tasks:
- `free_parking_analysis.py` - Analyzes free parking choice model outputs
- `analyze_real_data.py` - Processes and compares real model output data
- `test_free_parking/` - Test data and sample results for free parking validation
- `free_parking_results/` - Production results from free parking choice analysis
- `simwrapper_demo/` - SimWrapper dashboard examples and configurations for validation
- `simwrapper_demo.py` - SimWrapper integration utilities for validation visualizations
- Additional focused validation scripts can be added here following the same patterns

### Legacy and Examples
- `acceptance_example.py` - Example acceptance testing workflows
- `example_usage.py` - Basic usage examples for the summary system
- `compare_skims.py` - Skim matrix comparison utilities
- `compile_model_runs.py` - Model run compilation tools

### ActivitySim Integration
- `activitysim_demo.py` - ActivitySim integration demonstrations
- `test_environment.py` - Environment testing for ActivitySim setup
- `quick_demo.py` - Quick demonstration scripts

### Legacy Scripts and Utilities
- Various legacy analysis and utility scripts

### Analysis Results
- `core_summaries/` - Core summary output files
- `notebooks/` - Jupyter notebooks for exploratory analysis

## Quick Start

### 1. Environment Setup
Ensure you have the tm2py-utils conda environment activated with ActivitySim and required dependencies:

```bash
conda activate tm2py-utils
pip install -r requirements.txt
```

### 2. Individual Validation Analysis
For focused validation tasks, use scripts in the `validation/` directory:

```bash
# Analyze free parking choice patterns
python validation/free_parking_analysis.py --input-dir path/to/model/output --output-dir results/

# Compare real model data across scenarios
python validation/analyze_real_data.py --config analysis_config.toml
```

### 3. Comprehensive Validation Suite
For complete validation across multiple scenarios:

```bash
# Copy and customize the configuration template
cp validation_config.yaml my_validation_config.yaml

# Run comprehensive validation
python run_all_validation_summaries.py --config my_validation_config.yaml
```

### 4. Quick Testing
Test the system with sample data:

```bash
python test_summary_system.py
python quick_demo.py
```

## Architecture

### Data Models
The system uses Pydantic models (`ctramp_models.py`) for type-safe data validation:
- `CTRAMPPerson` - Person-level data including demographics and choices
- `CTRAMPHousehold` - Household-level data and characteristics  
- `CTRAMPTour` - Tour-level data and attributes
- `CTRAMPTrip` - Trip-level data and patterns

### Validation Patterns
Each validation script follows consistent patterns:
1. **Load**: Read and validate CTRAMP data using Pydantic models
2. **Analyze**: Apply analysis-specific logic (aggregations, comparisons, etc.)
3. **Save**: Output results in standardized CSV format for comparison

### Configuration-Driven
Analysis parameters are externalized in YAML/TOML configuration files:
- Input/output directory specifications
- Analysis parameters and thresholds
- Comparison scenarios and data sources

## Key Features

### 🔍 **Focused Validation Scripts**
Individual scripts in `validation/` directory for specific analysis tasks, making it easy to:
- Run targeted validation checks
- Customize analysis parameters
- Debug specific model components

### 🎯 **Comprehensive Orchestration**  
The main `run_all_validation_summaries.py` script coordinates multiple validation analyses:
- Multi-scenario comparison
- Standardized output formats
- Configurable analysis workflows

### 📊 **Interactive Dashboards**
SimWrapper integration for interactive visualization:
- Dynamic charts and plots
- Comparative analysis views
- Web-based exploration tools

### 🔧 **ActivitySim Integration**
Full integration with ActivitySim framework:
- Native data handling
- Model configuration reading
- Standard analysis workflows

## Data Sources

The system supports multiple data source types:
- **Model Output**: CTRAMP/ActivitySim model results
- **Survey Data**: Travel survey data for validation
- **ACS Data**: American Community Survey data for demographic validation

## Real Data Integration

The system includes configurations for real MTC model data:
- 2015 TM2 baseline model outputs
- 2023 development scenario outputs  
- Survey data validation datasets

See `analyze_real_data.py` for examples of real data processing workflows.

## Adding New Validation Scripts

To add a new validation analysis:

1. Create a new script in the `validation/` directory
2. Follow the Load/Analyze/Save pattern
3. Use Pydantic models for data validation
4. Add configuration parameters to YAML/TOML files
5. Update the main orchestrator if needed for comprehensive analysis

## Dependencies

Core dependencies (see `requirements.txt` for full list):
- ActivitySim 1.1.0+ - Activity-based modeling framework
- SimWrapper 1.8.5+ - Interactive dashboard creation  
- Pydantic 1.10+ - Data validation and modeling
- pandas, numpy - Data manipulation
- geopandas - Spatial data processing
- pyyaml, tomli - Configuration file handling

## Testing

Run the test suite to validate system functionality:

```bash
python test_summary_system.py
```

This includes:
- Data model validation tests
- File I/O operation tests  
- Analysis workflow tests
- Integration tests with sample data

## Contributing

When adding new functionality:
1. Follow the established patterns for validation scripts
2. Add comprehensive docstrings and type hints
3. Update configuration templates as needed
4. Add tests for new functionality
5. Update this README with new features