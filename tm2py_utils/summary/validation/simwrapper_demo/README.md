# SimWrapper Demo

This directory contains sample data and configurations for SimWrapper visualization.

## Files:
- `mode_share.csv` - Mode share summary data
- `trips_by_income_mode.csv` - Trip patterns by income and mode
- `daily_activity_by_income.csv` - Daily activity summaries
- `trips_by_time_purpose.csv` - Trip timing analysis
- `dashboard-1-summary.yaml` - Dashboard configuration
- `topsheet.yaml` - Key statistics configuration

## To view with SimWrapper:

### Option 1: Using the Python launcher
```bash
python launch_simwrapper.py
```

### Option 2: Manual activation
1. Open a new PowerShell/Command Prompt
2. Navigate to this directory:
   ```bash
   cd C:\GitHub\tm2py-utils\tm2py_utils\summary\simwrapper_demo
   ```
3. Activate the conda environment:
   ```bash
   conda activate tm2py-utils
   ```
4. Start SimWrapper:
   ```bash
   simwrapper open .
   ```

This will open SimWrapper in your browser showing the configured dashboard.
