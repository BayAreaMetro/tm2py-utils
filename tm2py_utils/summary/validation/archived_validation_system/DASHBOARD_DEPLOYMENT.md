# Dashboard Deployment Guide

This guide explains how to generate validation summaries and deploy them to the dashboard.

## Quick Start

### Option 1: Use the Batch Script (Windows)

Double-click `deploy_dashboard.bat` and follow the menu:

1. **Generate ALL summaries** - Generates all 34 summaries (core + validation)
2. **Generate CORE summaries only** - Generates 21 core summaries (essential analysis)
3. **Generate VALIDATION summaries only** - Generates 13 validation summaries (dashboard-focused)
4. **Copy existing summaries** - Just copies already-generated CSVs to dashboard folder
5. **Generate and LAUNCH dashboard** - Generates summaries and opens Streamlit app

### Option 2: Use Python Script Directly

```bash
# Generate all summaries and copy to dashboard
python run_and_deploy_dashboard.py --config validation_config.yaml

# Generate only core summaries
python run_and_deploy_dashboard.py --config validation_config.yaml --summaries core

# Generate and launch dashboard
python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard

# Use custom port
python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard --port 8503
```

### Option 3: Manual Steps

```bash
# Step 1: Generate summaries
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml

# Step 2: Copy to dashboard folder
cp outputs/*.csv outputs/dashboard/

# Step 3: Launch dashboard
streamlit run dashboard/dashboard_app.py --server.port 8503
```

## Understanding Summary Types

The validation system generates two types of summaries:

### Core Summaries (21 summaries)
Essential analysis matching `core_summaries.py` outputs:
- Auto ownership (regional, by income)
- Activity patterns / CDAP (5 breakdowns)
- Tour summaries (frequency, mode, timing)
- Trip summaries (mode, purpose, distance, time)
- Journey to work (distance, time, mode choice)

**Use case:** Quick model runs, essential validation checks

### Validation Summaries (13 summaries)
Extended analysis for detailed validation and dashboard:
- Auto ownership by household size (ACS-comparable)
- Auto ownership by county
- Aggregated mode categories
- Binned distance/duration distributions
- Detailed demographic breakdowns

**Use case:** Comprehensive validation, stakeholder presentations, dashboard visualization

## Controlling Summary Generation

Edit `validation_config.yaml` to set which summaries to generate:

```yaml
# Generate only core summaries (fast)
generate_summaries: "core"

# Generate only validation summaries (dashboard-focused)
generate_summaries: "validation"

# Generate all summaries (default)
generate_summaries: "all"
```

View configured summaries:
```bash
python list_summaries.py
```

## Dashboard Tabs

The dashboard includes these tabs (in order):

0. **Population** - Synthetic population from PopulationSim
1. **Households** - Auto ownership analysis
2. **Activity Patterns** - Daily activity patterns (CDAP)
3. **Tours** - Tour frequency and mode choice
4. **Trips** - Trip mode and purpose
5. **Journey to Work** - Commute patterns
6. **Time of Day** - Temporal distribution
7. **Trip Characteristics** - Distance and travel time

Each tab automatically loads its corresponding CSV files from `outputs/dashboard/`.

## File Locations

```
validation/
├── validation_config.yaml          # Main configuration
├── list_summaries.py                # View configured summaries
├── run_and_deploy_dashboard.py     # Main deployment script
├── deploy_dashboard.bat             # Windows batch wrapper
├── outputs/                         # Generated summary CSVs
│   └── dashboard/                   # CSVs for dashboard (copied here)
└── dashboard/                       # Dashboard YAML configs
    ├── dashboard_app.py             # Streamlit application
    ├── dashboard-0-population.yaml  # Population tab
    ├── dashboard-1-households.yaml  # Households tab
    ├── dashboard-2-activity-patterns.yaml
    ├── dashboard-3-tours.yaml
    ├── dashboard-4-trips.yaml
    ├── dashboard-5-commute.yaml
    ├── dashboard-6-time-of-day.yaml
    └── dashboard-7-trip-characteristics.yaml
```

## Troubleshooting

### No summaries generated
- Check that input directories in `validation_config.yaml` point to valid CTRAMP output folders
- Verify CSV files exist: `indivTripData_1.csv`, `householdData_1.csv`, etc.
- Check log output for specific error messages

### Dashboard shows "No data available"
- Run `python run_and_deploy_dashboard.py --skip-generation` to copy existing CSVs
- Check that CSV files exist in `outputs/dashboard/`
- Verify CSV column names match those in dashboard YAML files

### Wrong summaries generated
- Check `generate_summaries` setting in `validation_config.yaml`
- Run `python list_summaries.py` to see what will be generated
- Edit summary `summary_type` fields to change core vs validation classification

### Port already in use
- Use `--port` flag: `python run_and_deploy_dashboard.py --launch-dashboard --port 8503`
- Or manually kill existing Streamlit process: `Stop-Process -Name streamlit -Force`

## Advanced Configuration

### Add new summaries

Edit `validation_config.yaml` and add to `custom_summaries`:

```yaml
custom_summaries:
  - name: "my_new_summary"
    summary_type: "validation"  # or "core"
    description: "Description of what this summarizes"
    data_source: "individual_trips"  # or households, tours, etc.
    group_by: ["trip_mode", "tour_purpose"]
    weight_field: "sample_rate"
    count_name: "trips"
```

### Add new dashboard tab

Create `dashboard/dashboard-N-mytab.yaml`:

```yaml
dashboard:
  tab: My New Tab
  title: My Analysis
  description: What this tab shows

sections:
  my_section:
    title: "Section Title"
    charts:
      - type: bar
        title: "Chart Title"
        dataset: my_new_summary.csv
        x: trip_mode
        y: trips
        color: dataset
```

The dashboard automatically discovers new YAML files and adds tabs in numeric order.

## Next Steps

After deploying locally:

1. **Validate outputs** - Check that summary numbers make sense
2. **Compare with core_summaries.py** - Verify core summaries match (if migrating)
3. **Push to GitHub** - Dashboard auto-deploys to https://tm2-validation-dashboard.streamlit.app/
4. **Share with team** - Live dashboard accessible to stakeholders

For consolidation planning, see `CONSOLIDATION_PROPOSAL.md`.
