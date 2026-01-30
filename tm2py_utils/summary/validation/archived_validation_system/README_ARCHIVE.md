# Archived Validation System

This directory contains the old multi-dataset validation system that was replaced with a simpler, more transparent architecture.

## What's Here

- **summaries/run_all.py** - Old monolithic orchestrator that handled multiple datasets, comparison, and visualization all in one
- **dashboard/** - Streamlit dashboard configuration files for multi-dataset comparison
- **streamlit_app.py** - Streamlit Cloud dashboard application
- **run_and_deploy_dashboard.py** - Script that generated summaries and deployed to dashboard

## Why It Was Archived

The old system tried to do too much in one tool:
1. Load multiple CTRAMP model runs
2. Generate summaries for each run
3. Combine summaries across runs
4. Compare to external data sources
5. Prepare dashboard visualization files
6. Deploy to Streamlit Cloud

This made the code complex with many classes, abstraction layers, and difficult-to-follow execution flow.

## New Approach

The new simplified architecture separates concerns:

- **summarize_model_run.py** - Simple standalone tool that summarizes ONE model run
  - Transparent logging showing each processing step
  - ~300 lines of easy-to-read code
  - Minimal classes, clear data flow
  - Junior analyst friendly

- **Comparison & Visualization** - To be handled separately (future work)
  - Compare summaries from different runs using simple pandas scripts
  - Create visualizations as needed without complex orchestration

## If You Need the Old System

The code is preserved here for reference. It still works but is not actively maintained.

Key files:
- `summaries/run_all.py` - Main entry point
- `summaries/config_driven_summaries.py` - Summary generation logic
- `dashboard/dashboard_app.py` - Streamlit dashboard

To use it, you'll need to restore the imports and file paths that expected these to be in the parent directory.

## Migration Notes

All summary definitions have been moved to:
- `data_model/ctramp_data_model.yaml` - Central configuration for summaries, value mappings, binning specs

The new tool reads from this same configuration, so summary definitions are preserved.
