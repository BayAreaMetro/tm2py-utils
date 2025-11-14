# Validation Scripts Directory

This directory contains focused validation analysis scripts for specific CTRAMP model validation tasks. Each script follows a standardized Load/Analyze/Save pattern for consistency and maintainability.

## Current Scripts

### `free_parking_analysis.py`
**Purpose**: Analyzes free parking choice model outputs and compares choice patterns across scenarios.

**Key Features**:
- Loads person-level CTRAMP data with free parking choices
- Generates aggregated choice summaries by demographics
- Supports both test data generation and real data analysis
- Outputs standardized CSV results for comparison

**Associated Directories**:
- `test_free_parking/` - Test data and sample results
- `free_parking_results/` - Production analysis outputs

**Usage**:
```bash
python validation/free_parking_analysis.py --input-dir path/to/model/output --output-dir results/
```

### `analyze_real_data.py`
**Purpose**: Processes and compares real model output data across multiple scenarios.

**Key Features**:
- Configured for MTC 2015 vs 2023 model comparison
- Handles large-scale production model outputs
- Supports multiple analysis types within single script
- Real data path integration

**Usage**:
```bash
python validation/analyze_real_data.py --config ../analysis_config.toml
```

## Data and Results Directories

### `test_free_parking/`
Contains test data and sample results for free parking validation:
- Sample CTRAMP person data files
- Test configuration files
- Expected output examples

### `free_parking_results/`
Contains production results from free parking choice analysis:
- Scenario comparison outputs
- Summary statistics and aggregations
- SimWrapper-ready dashboard data

### `simwrapper_demo/`
Contains SimWrapper dashboard examples and configurations for validation:
- Interactive dashboard configurations
- Sample data visualizations
- Chart and plot examples for validation analysis

### `simwrapper_demo.py`
Utility script for SimWrapper integration:
- Dashboard creation helpers
- Data formatting for visualization
- Integration patterns for validation workflows

## Script Architecture

### Standard Pattern
All validation scripts follow this pattern:

```python
def load_data(input_dir: Path) -> CTRAMPPerson:
    """Load and validate CTRAMP data using Pydantic models."""
    
def analyze_data(data: CTRAMPPerson, config: Dict) -> pd.DataFrame:
    """Apply analysis-specific logic and generate summaries."""
    
def save_results(results: pd.DataFrame, output_path: Path):
    """Save results in standardized format."""
```

### Shared Utilities
Common functionality across scripts:
- Pydantic data models from `../ctramp_models.py`
- Configuration handling (YAML/TOML)
- Logging and error handling
- Standardized output formats

## Adding New Validation Scripts

When creating a new validation script in this directory:

1. **Load Function** - Standardized data loading with validation
2. **Analysis Function** - Generate summaries at multiple aggregation levels
3. **Comparison Function** - Cross-scenario comparison tables
4. **Save Function** - Consistent CSV output format
5. **Test Data** - Built-in test data generation

## Common Patterns

### Data Loading
```python
def load_person_file(file_path: Path) -> pd.DataFrame:
    # Validation, error handling, field checking
```

### Summary Generation  
```python
def analyze_[topic](df: pd.DataFrame, scenario_name: str) -> Dict[str, pd.DataFrame]:
    # Multiple aggregation levels
    # Descriptive labels
    # Scenario tagging
```

### Comparison Creation
```python
def create_comparison_summaries(summaries1, summaries2) -> Dict[str, pd.DataFrame]:
    # Cross-scenario comparison tables
```

This structure makes each analysis:
- **Independent** - Can be run separately
- **Testable** - Built-in test data and validation
- **Extensible** - Easy to add new summary types
- **Consistent** - Standardized output format