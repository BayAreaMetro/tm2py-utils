#!/usr/bin/env python3
"""
Example script showing how to use ActivitySim for summary system development.
This demonstrates basic ActivitySim integration for analyzing model outputs.
"""

import pandas as pd
import numpy as np
import activitysim.core.config as asim_config
import activitysim.core.pipeline as asim_pipeline
from pathlib import Path


def demo_activitysim_config():
    """Demonstrate ActivitySim configuration capabilities."""
    print("ActivitySim Configuration Example")
    print("=" * 40)
    
    # Example of how ActivitySim handles configuration
    try:
        # This would normally load from a settings file
        # For demo, we'll just show the structure
        print("ActivitySim can load and validate model configurations from YAML/TOML files")
        print("Key configuration areas:")
        print("- Model settings (households, persons, trips)")
        print("- Data input specifications")
        print("- Output table definitions") 
        print("- Pipeline step configurations")
        
        return True
        
    except Exception as e:
        print(f"Configuration demo error: {e}")
        return False


def demo_data_analysis():
    """Demonstrate data analysis capabilities for summary system."""
    print("\nData Analysis Example")
    print("=" * 30)
    
    # Create sample data similar to what ActivitySim would produce
    households = pd.DataFrame({
        'household_id': range(1, 1001),
        'income': np.random.normal(75000, 25000, 1000),
        'size': np.random.choice([1, 2, 3, 4, 5], 1000, p=[0.3, 0.3, 0.2, 0.15, 0.05]),
        'vehicles': np.random.choice([0, 1, 2, 3], 1000, p=[0.2, 0.4, 0.3, 0.1])
    })
    
    trips = pd.DataFrame({
        'trip_id': range(1, 5001),
        'household_id': np.random.choice(range(1, 1001), 5000),
        'mode': np.random.choice(['drive', 'transit', 'walk', 'bike'], 5000, p=[0.6, 0.2, 0.15, 0.05]),
        'distance': np.random.exponential(5.0, 5000),
        'purpose': np.random.choice(['work', 'shop', 'other'], 5000, p=[0.4, 0.3, 0.3])
    })
    
    print(f"Sample data created:")
    print(f"- {len(households)} households")
    print(f"- {len(trips)} trips")
    
    # Basic summary statistics
    print(f"\nHousehold Summary:")
    print(f"- Average income: ${households['income'].mean():,.0f}")
    print(f"- Average size: {households['size'].mean():.1f}")
    print(f"- Average vehicles: {households['vehicles'].mean():.1f}")
    
    print(f"\nTrip Summary:")
    print(f"- Trips per household: {len(trips) / len(households):.1f}")
    print(f"- Average distance: {trips['distance'].mean():.1f} miles")
    
    # Mode share analysis
    mode_share = trips['mode'].value_counts(normalize=True) * 100
    print(f"\nMode Share:")
    for mode, share in mode_share.items():
        print(f"- {mode.capitalize()}: {share:.1f}%")
    
    return households, trips


def demo_summary_outputs():
    """Show how to create summary outputs for the system."""
    print("\nSummary Output Example")
    print("=" * 25)
    
    households, trips = demo_data_analysis()
    
    # Join data for analysis
    trip_hh = trips.merge(households, on='household_id')
    
    # Summary by income quartile
    trip_hh['income_quartile'] = pd.qcut(trip_hh['income'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'])
    
    summary_by_income = (trip_hh.groupby('income_quartile')
                        .agg({
                            'trip_id': 'count',
                            'distance': 'mean',
                            'household_id': 'nunique'
                        })
                        .rename(columns={
                            'trip_id': 'total_trips',
                            'distance': 'avg_distance',
                            'household_id': 'households'
                        }))
    
    summary_by_income['trips_per_hh'] = (summary_by_income['total_trips'] / 
                                        summary_by_income['households'])
    
    print("Trip Analysis by Income Quartile:")
    print(summary_by_income.round(2))
    
    return summary_by_income


if __name__ == "__main__":
    print("ActivitySim Summary System Development Demo")
    print("=" * 50)
    
    # Test basic functionality
    config_ok = demo_activitysim_config()
    
    if config_ok:
        # Run data analysis demo
        summary_data = demo_summary_outputs()
        
        print(f"\n✓ Demo completed successfully!")
        print(f"This shows the foundation for building a comprehensive summary system")
        print(f"that can process ActivitySim model outputs and generate insights.")
    else:
        print("⚠ Some issues detected, but core functionality available.")