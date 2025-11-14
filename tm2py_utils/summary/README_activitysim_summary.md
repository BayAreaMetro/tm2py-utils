# CTRAMP Summary System

This directory contains a comprehensive system for generating standardized summaries from CTRAMP (ActivitySim/TM2) model outputs. The system supports both survey data validation and multi-scenario comparison workflows.

## Overview

The system processes multiple model run directories and generates CSV summaries for:
- **Auto Ownership Analysis** - Regional and demographic breakdowns
- **Work Location Patterns** - Telecommuting and workplace accessibility
- **Daily Activity Patterns** - CDAP analysis by demographics
- **Tour Analysis** - Frequency, mode choice, timing, and geography
- **Trip Analysis** - Detailed trip-level summaries

## Environment Setup

A dedicated conda environment `tm2py-utils` includes:

### Core Dependencies
- **Python 3.8** - Base environment
- **ActivitySim 1.1.0** - Activity-based modeling framework
- **pandas 2.0.3** - Data manipulation and analysis
- **geopandas 0.13.2** - Geospatial data processing
- **pydantic 1.10** - Data validation and modeling

### Visualization Tools
- **SimWrapper 1.8.5** - Interactive dashboard creation
- **PyYAML 6.0** - Configuration file management

## Getting Started

1. **Activate the environment:**
   ```bash
   conda activate tm2py-utils
   ```

2. **Test the setup:**
   ```bash
   python test_environment.py
   ```

3. **Run the ActivitySim demo:**
   ```bash
   python activitysim_demo.py
   ```

4. **Create and view SimWrapper demo:**
   ```bash
   python simwrapper_demo.py
   cd simwrapper_demo
   python launch_simwrapper.py
   ```
   
   **Note:** The Python launcher script checks the environment and provides helpful error messages if dependencies are missing.

## Available Examples

ActivitySim includes several prototype examples that can serve as templates:
- `prototype_mtc` - San Francisco Bay Area model
- `prototype_marin` - Marin County model
- `placeholder_psrc` - Puget Sound Regional Council
- `placeholder_sandag` - San Diego Association of Governments

## Files

- `test_environment.py` - Validates the installation and package compatibility
- `activitysim_demo.py` - Demonstrates basic ActivitySim integration for summary analysis
- `simwrapper_demo.py` - Creates sample data and SimWrapper dashboard configuration
- `simwrapper_demo/` - Directory with sample CSV data and dashboard configs for SimWrapper
- `quick_demo.py` - Simple environment test and demonstration script
- `run_all_summaries.py` - Master summary generation engine (comprehensive approach)
- `ctramp_models.py` - Pydantic data models for CTRAMP file validation
- `config_template.yaml` - Configuration template for multi-scenario analysis
- `validation/` - Directory with focused analysis scripts for specific summaries
- `requirements.txt` - Package dependencies for the summary system

## Notes

- Some ActivitySim ABM modules may have numba/numpy version compatibility issues, but core functionality works
- The environment uses ActivitySim's required numpy 1.21.0 version for maximum compatibility
- Focus on using ActivitySim's core configuration and pipeline modules for summary system development

## Next Steps

This foundation provides:
1. **Configuration Management** - Using ActivitySim's robust config system
2. **Data Pipeline** - Leveraging ActivitySim's data processing capabilities  
3. **Analysis Tools** - Building on pandas/geopandas for summary statistics
4. **Integration** - Ready to process ActivitySim model outputs and create insights