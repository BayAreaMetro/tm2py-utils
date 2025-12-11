# Dashboard Guide

The tm2py-utils validation dashboard is an interactive web application for comparing model runs and validating outputs against observed data.

## Live Dashboard

View the deployed dashboard: **[https://tm2-dashboard.streamlit.app/](https://tm2-dashboard.streamlit.app/)**

## Running Locally

### Quick Start

```bash
cd tm2py_utils/summary/validation
streamlit run dashboard/dashboard_app.py --server.port 8501
```

The dashboard will open at `http://localhost:8501`

### Using the Deployment Script

```bash
# Generate summaries and launch dashboard
python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard

# Use custom port
python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard --port 8503
```

## Dashboard Tabs

### 0. Population
Synthetic population from PopulationSim with ACS validation:
- Household size distribution
- Income distribution
- Geographic distribution by county
- Workers per household
- Age distribution

### 1. Households
Auto ownership analysis from CTRAMP model:
- Regional auto ownership
- By income category
- By household size (with ACS comparison)
- By county

### 2. Activity Patterns
Coordinated daily activity patterns (CDAP):
- Overall distribution
- By person type (worker, student, etc.)
- By age group
- By home county
- By auto ownership

### 3. Tours
Tour frequency and characteristics:
- Tours by purpose
- Tours by mode
- Tour distance distribution
- Tour duration distribution

### 4. Trips
Trip-level analysis:
- Trips by mode
- Trips by purpose
- Mode by purpose cross-tabs
- Trip distance and duration

### 5. Journey to Work
Commute pattern analysis:
- Commute distance by origin-destination
- Commute time by origin-destination
- Mode share for work tours
- Mode by origin-destination

### 6. Time of Day
Temporal distribution of travel:
- Tour departure times
- Tour arrival times
- Tour timing by purpose and mode
- Trip mode by time period

### 7. Trip Characteristics
Detailed distance and time analysis:
- Trip distance distribution
- Average distance by income/mode/purpose
- Trip duration distribution
- Average time by income/mode/purpose

## Dashboard Features

### Interactive Charts
- **Hover**: See exact values
- **Zoom**: Click and drag to zoom in
- **Pan**: Shift+drag to pan
- **Reset**: Double-click to reset view
- **Download**: Camera icon to save as PNG

### Filters
- **Dataset Comparison**: Select which model runs to compare
- **Faceting**: Some charts split data across multiple panels

### Data Export
Click the download icon on any chart to export as PNG for reports.

## Customizing the Dashboard

### Adding New Charts

Edit or create dashboard YAML files in `dashboard/` folder:

```yaml
dashboard:
  tab: My New Tab
  title: Custom Analysis
  description: Description of what this shows

sections:
  my_section:
    title: "Section Title"
    charts:
      - type: bar
        title: "Chart Title"
        dataset: my_data.csv
        x: category
        y: value
        color: dataset
        axis_labels:
          category: "Category Name"
          value: "Value Label"
```

### Chart Types

Supported chart types:
- `bar` - Bar charts (most common)
- `line` - Line charts
- `scatter` - Scatter plots

### Faceting

Split charts across multiple panels:

```yaml
- type: bar
  title: "My Chart"
  dataset: data.csv
  x: category
  y: value
  color: subcategory
  facet: dataset  # Creates separate panel for each dataset
```

## Data Requirements

The dashboard reads CSV files from `outputs/dashboard/` directory. Each CSV must have:

1. **Column for x-axis** (categories, modes, etc.)
2. **Column for y-axis** (counts, shares, averages, etc.)
3. **dataset column** (to distinguish between model runs)

Example CSV structure:

```csv
trip_mode,trips,share,dataset
Drive Alone,1000000,45.2,2023 TM2.2 v05
Carpool,300000,13.6,2023 TM2.2 v05
Transit,200000,9.0,2023 TM2.2 v05
Drive Alone,950000,43.8,2015 TM2.2 Sprint 04
...
```

## Troubleshooting

### "No data available"

Ensure CSV files exist in `outputs/dashboard/` and column names match the YAML configuration.

### Port already in use

Use a different port:
```bash
streamlit run dashboard/dashboard_app.py --server.port 8503
```

### Charts not updating

Streamlit auto-reloads when files change. If not working, refresh the browser (F5).

### Missing tabs

Check that dashboard YAML files are in `dashboard/` directory (not `outputs/dashboard/`).

## Deployment

The dashboard auto-deploys to Streamlit Cloud when changes are pushed to the main branch on GitHub.

**Live URL**: [https://tm2-dashboard.streamlit.app/](https://tm2-dashboard.streamlit.app/)

### Manual Deployment

To deploy your own instance:

1. Create a Streamlit Cloud account
2. Connect your GitHub repository
3. Set main file: `tm2py_utils/summary/validation/streamlit_app.py`
4. Deploy!

## Next Steps

- [Generate Summaries](summaries.md) to populate dashboard data
- [Customize Configuration](configuration.md) to add new analyses
