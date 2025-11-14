#!/usr/bin/env python3
"""
SimWrapper Integration Demo for tm2py-utils Summary System
Shows how to create CSV summaries and configure SimWrapper dashboards.
"""

import pandas as pd
import numpy as np
import yaml
import json
from pathlib import Path
import os


def create_sample_summary_data():
    """Create sample summary data that SimWrapper can visualize."""
    print("Creating sample summary data for SimWrapper...")
    
    # Create sample household data
    households = pd.DataFrame({
        'household_id': range(1, 1001),
        'income_quartile': np.random.choice(['Q1', 'Q2', 'Q3', 'Q4'], 1000),
        'vehicles': np.random.choice([0, 1, 2, 3], 1000, p=[0.2, 0.4, 0.3, 0.1]),
        'size': np.random.choice([1, 2, 3, 4, 5], 1000, p=[0.3, 0.3, 0.2, 0.15, 0.05]),
        'county': np.random.choice(['Alameda', 'Contra Costa', 'Marin', 'San Francisco', 
                                   'San Mateo', 'Santa Clara', 'Solano', 'Sonoma', 'Napa'], 1000)
    })
    
    # Create sample trip data
    trips = pd.DataFrame({
        'trip_id': range(1, 5001),
        'household_id': np.random.choice(range(1, 1001), 5000),
        'mode': np.random.choice(['SOV', 'HOV', 'Transit', 'Non-Motorized'], 5000, p=[0.6, 0.2, 0.15, 0.05]),
        'purpose': np.random.choice(['Work', 'Shop', 'School', 'Other'], 5000, p=[0.4, 0.25, 0.15, 0.2]),
        'distance_miles': np.random.exponential(5.0, 5000),
        'duration_minutes': np.random.exponential(20.0, 5000),
        'time_period': np.random.choice(['AM Peak', 'Midday', 'PM Peak', 'Evening'], 5000, p=[0.25, 0.3, 0.25, 0.2])
    })
    
    return households, trips


def create_summary_tables(households, trips, output_dir):
    """Create summary tables that SimWrapper can use for visualization."""
    
    # Ensure output directory exists
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print(f"Creating summary tables in {output_dir}...")
    
    # 1. Mode Share Summary
    mode_share = trips.groupby('mode').size().reset_index(name='trips')
    mode_share['share'] = (mode_share['trips'] / mode_share['trips'].sum() * 100).round(1)
    mode_share.to_csv(output_dir / 'mode_share.csv', index=False)
    print("✓ Created mode_share.csv")
    
    # 2. Trips by Income and Mode
    trip_hh = trips.merge(households, on='household_id')
    trips_by_income_mode = (trip_hh.groupby(['income_quartile', 'mode'])
                           .size().reset_index(name='trips'))
    trips_by_income_mode.to_csv(output_dir / 'trips_by_income_mode.csv', index=False)
    print("✓ Created trips_by_income_mode.csv")
    
    # 3. Daily Activity Summary
    daily_summary = (trip_hh.groupby(['household_id', 'income_quartile'])
                    .agg({
                        'trip_id': 'count',
                        'distance_miles': 'sum',
                        'duration_minutes': 'sum'
                    })
                    .rename(columns={
                        'trip_id': 'total_trips',
                        'distance_miles': 'total_distance',
                        'duration_minutes': 'total_duration'
                    })
                    .reset_index())
    
    daily_activity = (daily_summary.groupby('income_quartile')
                     .agg({
                         'total_trips': 'mean',
                         'total_distance': 'mean', 
                         'total_duration': 'mean'
                     })
                     .round(2)
                     .reset_index())
    daily_activity.to_csv(output_dir / 'daily_activity_by_income.csv', index=False)
    print("✓ Created daily_activity_by_income.csv")
    
    # 4. Time of Day Analysis
    time_analysis = (trip_hh.groupby(['time_period', 'purpose'])
                    .agg({
                        'trip_id': 'count',
                        'distance_miles': 'mean'
                    })
                    .rename(columns={
                        'trip_id': 'trips',
                        'distance_miles': 'avg_distance'
                    })
                    .round(2)
                    .reset_index())
    time_analysis.to_csv(output_dir / 'trips_by_time_purpose.csv', index=False)
    print("✓ Created trips_by_time_purpose.csv")
    
    return {
        'mode_share': mode_share,
        'trips_by_income_mode': trips_by_income_mode,
        'daily_activity': daily_activity,
        'time_analysis': time_analysis
    }


def create_simwrapper_config(output_dir):
    """Create SimWrapper dashboard configuration files."""
    
    output_dir = Path(output_dir)
    
    # Create dashboard configuration
    dashboard_config = {
        'header': {
            'tab': 'Summary Dashboard',
            'title': 'TM2py-Utils Transportation Summary',
            'description': 'Summary visualization of transportation model outputs'
        },
        'layout': {
            'row1': [
                {
                    'type': 'bar',
                    'title': 'Mode Share',
                    'dataset': './mode_share.csv',
                    'x': 'mode',
                    'y': 'share',
                    'color': '#4e79a7'
                },
                {
                    'type': 'table',
                    'title': 'Daily Activity by Income',
                    'dataset': './daily_activity_by_income.csv'
                }
            ],
            'row2': [
                {
                    'type': 'bar',
                    'title': 'Trips by Income Quartile and Mode',
                    'dataset': './trips_by_income_mode.csv',
                    'x': 'income_quartile',
                    'y': 'trips',
                    'groupBy': 'mode'
                }
            ],
            'row3': [
                {
                    'type': 'heatmap',
                    'title': 'Trips by Time Period and Purpose',
                    'dataset': './trips_by_time_purpose.csv',
                    'x': 'time_period',
                    'y': 'purpose',
                    'fill': 'trips'
                }
            ]
        }
    }
    
    # Save dashboard config
    with open(output_dir / 'dashboard-1-summary.yaml', 'w') as f:
        yaml.dump(dashboard_config, f, default_flow_style=False)
    print("✓ Created dashboard-1-summary.yaml")
    
    # Create topsheet config for key statistics
    topsheet_config = {
        'topsheet': [
            {
                'title': 'Total Households',
                'value': 1000,
                'subtext': 'Sample households'
            },
            {
                'title': 'Total Trips',
                'value': 5000,
                'subtext': 'Daily trips'
            },
            {
                'title': 'Avg Trips/HH',
                'value': 5.0,
                'subtext': 'Per household'
            },
            {
                'title': 'Mode Share - SOV',
                'value': '60%',
                'subtext': 'Single occupancy vehicle'
            }
        ]
    }
    
    with open(output_dir / 'topsheet.yaml', 'w') as f:
        yaml.dump(topsheet_config, f, default_flow_style=False)
    print("✓ Created topsheet.yaml")
    
    return dashboard_config, topsheet_config


def create_demo_outputs():
    """Create a complete demo showing SimWrapper integration."""
    
    # Create output directory
    output_dir = Path('simwrapper_demo')
    output_dir.mkdir(exist_ok=True)
    
    print("SimWrapper Integration Demo")
    print("=" * 40)
    
    # Generate sample data
    households, trips = create_sample_summary_data()
    
    # Create summary tables
    summaries = create_summary_tables(households, trips, output_dir)
    
    # Create SimWrapper configuration
    dashboard_config, topsheet_config = create_simwrapper_config(output_dir)
    
    # Create a simple README for the demo
    readme_content = """# SimWrapper Demo

This directory contains sample data and configurations for SimWrapper visualization.

## Files:
- `mode_share.csv` - Mode share summary data
- `trips_by_income_mode.csv` - Trip patterns by income and mode
- `daily_activity_by_income.csv` - Daily activity summaries
- `trips_by_time_purpose.csv` - Trip timing analysis
- `dashboard-1-summary.yaml` - Dashboard configuration
- `topsheet.yaml` - Key statistics configuration

## To view with SimWrapper:

1. Navigate to this directory:
   ```
   cd simwrapper_demo
   ```

2. Start SimWrapper:
   ```
   simwrapper open .
   ```

This will open SimWrapper in your browser showing the configured dashboard.
"""
    
    with open(output_dir / 'README.md', 'w') as f:
        f.write(readme_content)
    print("✓ Created README.md")
    
    print(f"\n✅ Demo created in {output_dir.absolute()}")
    print(f"\nTo view the dashboard:")
    print(f"1. cd {output_dir}")
    print(f"2. simwrapper open .")
    
    return output_dir


if __name__ == "__main__":
    # Create the complete demo
    output_path = create_demo_outputs()
    
    print(f"\n🎯 SimWrapper demo ready!")
    print(f"The demo shows how to create summary CSV files and configure")
    print(f"interactive dashboards for transportation model visualization.")