# Contributing to tm2py-utils

Thank you for contributing to tm2py-utils! This guide helps you add summaries, validation checks, and other features.

## Development Setup

### Prerequisites

- Python 3.9+
- Conda or virtualenv
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/BayAreaMetro/tm2py-utils.git
cd tm2py-utils

# Create environment
conda env create -f environment.yml
conda activate tm2py_utils

# Install in development mode
pip install -e .

# Install development dependencies
pip install pytest black flake8 mypy
```

## Project Structure

```
tm2py_utils/
├── summary/
│   ├── validation/                        # NEW: Simple validation toolkit
│   │   ├── summarize_model_run.py        # Main tool
│   │   ├── validate_summaries.py         # Quality checker
│   │   ├── data_model/                   # Configuration
│   │   │   ├── ctramp_data_model.yaml   # Edit this to add summaries!
│   │   │   ├── variable_labels.yaml      # Display labels
│   │   │   └── ctramp_data_model_loader.py
│   │   ├── outputs/                      # Generated summaries
│   │   ├── HOW_TO_SUMMARIZE.md          # User guide
│   │   ├── README.md                     # Toolkit overview
│   │   └── archived_validation_system/   # Old multi-dataset system
│   └── core_summaries/                   # DEPRECATED
├── inputs/                                # Input data processing
├── misc/                                  # Utilities
└── docs/                                  # Documentation
```

## Adding a New Summary

### 1. Define in ctramp_data_model.yaml

Edit `tm2py_utils/summary/validation/data_model/ctramp_data_model.yaml`:

```yaml
summaries:
  # ... existing summaries ...
  
  trip_distance_by_mode_purpose:
    description: "Trip distance distribution by mode and purpose"
    data_source: "individual_trips"
    group_by:
      - "trip_mode_name"
      - "tour_purpose_name"
    aggregations:
      trips:
        column: "trip_id"
        agg: "count"
      mean_distance:
        column: "trip_distance_miles"
        agg: "mean"
```

### 2. Test Generation

```bash
cd tm2py_utils/summary/validation

# Generate summaries for a test run
python summarize_model_run.py "A:/path/to/ctramp_output" --output "test_output"
```

### 3. Verify Output

Check the generated file:

```bash
cat test_output/trip_distance_by_mode_purpose.csv
```

Expected format:
```csv
trip_mode_name,tour_purpose_name,trips,mean_distance,share
Drive Alone,Work,1234567,12.5,0.452
Carpool 2,Work,234567,10.3,0.086
Walk-Transit-Walk,Work,156789,8.7,0.057
...
```
...
```

### 4. Update Documentation

Add to appropriate section in `docs/summaries.md`.

## Adding a Dashboard Tab

### 1. Create YAML Configuration

Create `dashboard/dashboard-N-mytab.yaml`:

```yaml
title: "My New Analysis"
description: "Description of what this tab shows"

sections:
  - title: "Overview"
    layout: "two_column"
    charts:
      - type: "bar"
        title: "My Metric by Category"
        data_file: "my_summary.csv"
        x: "category"
        y: "value"
        color: "dataset"
        orientation: "h"
        facet_col: null
      
      - type: "line"
        title: "Trend Over Time"
        data_file: "my_trend.csv"
        x: "year"
        y: "value"
        color: "category"
```

### 2. Generate Required Data

Ensure summaries in YAML exist in `validation_config.yaml`:

```yaml
custom_summaries:
  - name: "my_summary"
    # ... configuration
  
  - name: "my_trend"
    # ... configuration
```

### 3. Test Dashboard

```bash
cd tm2py_utils/summary/validation

# Generate summaries
python run_and_deploy_dashboard.py --config validation_config.yaml

# Launch dashboard
streamlit run dashboard/dashboard_app.py --server.port 8501
```

Visit http://localhost:8501 and check new tab appears.

### 4. Dashboard YAML Reference

**Chart Types:**
- `bar` - Bar chart (vertical or horizontal)
- `line` - Line chart
- `scatter` - Scatter plot
- `box` - Box plot
- `histogram` - Histogram

**Layout Options:**
- `single_column` - One chart per row
- `two_column` - Two charts per row
- `three_column` - Three charts per row

**Chart Properties:**
```yaml
- type: "bar"
  title: "Chart Title"
  data_file: "summary.csv"        # CSV filename (must exist in outputs/dashboard/)
  x: "category_column"            # X-axis column
  y: "value_column"               # Y-axis column
  color: "dataset"                # Color by column
  orientation: "h"                # "h" or "v"
  facet_col: "another_category"   # Create subplots by column
  facet_col_wrap: 3               # Number of facet columns
  barmode: "group"                # "group", "stack", or "relative"
  category_orders:                # Custom ordering
    category_column: ["A", "B", "C"]
  labels:                         # Custom axis labels
    category_column: "Category"
    value_column: "Count"
```

## Adding a Column Mapping

If using new CTRAMP output columns:

### 1. Update Data Model

Edit `data_model/ctramp_data_model.yaml`:

```yaml
individual_trips:
  file_pattern: "indivTripData_{iteration}.csv"
  columns:
    trip_mode: "trip_mode"
    my_new_column: "my_new_column"  # Add mapping
```

### 2. Add Variable Label

Edit `variable_labels.yaml`:

```yaml
my_new_column: "My New Column Label"
```

### 3. Use in Summary

```yaml
custom_summaries:
  - name: "summary_with_new_column"
    group_by: ["my_new_column"]
    # ...
```

## Code Style

### Python

Follow PEP 8:

```bash
# Format code
black tm2py_utils/

# Check style
flake8 tm2py_utils/

# Type checking
mypy tm2py_utils/
```

### YAML

- Use 2-space indentation
- Quote strings with special characters
- Comment complex sections

```yaml
# Good
custom_summaries:
  - name: "my_summary"
    description: "Clear description"
    group_by: ["column1", "column2"]

# Avoid
custom_summaries:
    - name: my_summary  # Missing quotes, 4-space indent
      group_by: [column1]
```

## Testing

### Run Existing Tests

```bash
# All tests
pytest

# Specific test
pytest tm2py_utils/summary/validation/test_summaries.py

# With coverage
pytest --cov=tm2py_utils
```

### Write New Tests

Create `test_my_feature.py`:

```python
import pytest
from tm2py_utils.summary.validation import run_all

def test_my_summary_generation():
    """Test that my_summary generates expected output."""
    # Setup
    config_path = "test_config.yaml"
    
    # Run
    run_all.main(config_path)
    
    # Assert
    output_file = "outputs/my_summary.csv"
    assert output_file.exists()
    # ... more assertions
```

## Documentation

### Update Docs

When adding features, update relevant documentation:

- `docs/summaries.md` - For new summaries or configuration options
- `docs/dashboard.md` - For new dashboard tabs or features
- `docs/configuration.md` - For new config parameters
- `README.md` - For major features

### Build Docs Locally

```bash
# Install mkdocs
pip install mkdocs mkdocs-material

# Serve locally
cd tm2py_utils
mkdocs serve

# Visit http://localhost:8000
```

## Submitting Changes

### 1. Create Branch

```bash
git checkout -b feature/my-new-feature
```

### 2. Make Changes

- Add summaries to `validation_config.yaml`
- Create dashboard YAML files
- Update documentation

### 3. Test Changes

```bash
# Run tests
pytest

# Generate summaries
python run_and_deploy_dashboard.py --config validation_config.yaml

# Test dashboard
streamlit run dashboard/dashboard_app.py
```

### 4. Commit

```bash
git add .
git commit -m "Add trip length analysis dashboard

- Add trip_length_by_mode_purpose summary
- Create dashboard-8-trip-length.yaml
- Update summaries.md documentation"
```

### 5. Push and Create PR

```bash
git push origin feature/my-new-feature
```

Then create Pull Request on GitHub.

## Common Patterns

### Binning Continuous Variables

```yaml
custom_summaries:
  - name: "trips_by_distance_bin"
    group_by: ["distance_bin", "trip_mode"]
    bins:
      distance:
        breaks: [0, 5, 10, 20, 50, 1000]
        labels: ['<5mi', '5-10mi', '10-20mi', '20-50mi', '50+mi']
```

### Multiple Aggregations

```yaml
custom_summaries:
  - name: "trip_stats_by_mode"
    group_by: ["trip_mode"]
    aggregations:
      trips: "count"
      avg_distance: {"column": "trip_distance_miles", "agg": "mean"}
      total_time: {"column": "trip_time_minutes", "agg": "sum"}
      max_distance: {"column": "trip_distance_miles", "agg": "max"}
```

### Conditional Filters

```yaml
custom_summaries:
  - name: "work_tours_only"
    data_source: "individual_tours"
    filters:
      tour_purpose: ["Work"]
    group_by: ["tour_mode"]
```

### Comparison to Observed Data

Add to `observed_data_sources` in config:

```yaml
observed_data_sources:
  - name: "ACS 2019"
    directory: "/path/to/acs/data"
    files:
      auto_ownership: "acs_auto_ownership.csv"
```

Then reference in summary:

```yaml
custom_summaries:
  - name: "auto_ownership_regional"
    observed_data: "ACS 2019"
    observed_file: "auto_ownership"
```

## Getting Help

- **Documentation**: Check [docs/](../docs/)
- **Examples**: See `examples/` directory
- **Issues**: Open on [GitHub](https://github.com/BayAreaMetro/tm2py-utils/issues)
- **Email**: modeling@bayareametro.gov

## Related Resources

- [Consolidation Proposal](../summary/CONSOLIDATION_PROPOSAL.md) - System architecture
- [Dashboard Deployment Guide](../summary/DASHBOARD_DEPLOYMENT.md) - Deployment workflow
- [validation_config.yaml](../summary/validation/validation_config.yaml) - Live configuration example
