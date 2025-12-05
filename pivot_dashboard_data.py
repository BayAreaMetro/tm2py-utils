#!/usr/bin/env python3
"""
Script to pivot auto ownership dashboard data into the correct format for visualization
"""
import pandas as pd
import os

def pivot_auto_ownership_data():
    """Pivot auto ownership data from long to wide format for dashboard"""
    
    dashboard_dir = "tm2py_utils/summary/validation/outputs/dashboard"
    
    # Dataset configurations: {filename: {index_cols: [], pivot_col: str}}
    datasets = {
        "auto_ownership_by_income.csv": {
            "index_cols": ["income_category_bin", "dataset"],
            "pivot_col": "num_vehicles"
        },
        "auto_ownership_by_household_size_acs.csv": {
            "index_cols": ["num_persons_agg", "dataset"], 
            "pivot_col": "num_vehicles"
        },
        "auto_ownership_by_household_size_county.csv": {
            "index_cols": ["county", "num_persons_agg", "dataset"],
            "pivot_col": "num_vehicles"
        }
    }
    
    for filename, config in datasets.items():
        filepath = os.path.join(dashboard_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"⚠️  File not found: {filepath}")
            continue
            
        print(f"📊 Pivoting {filename}...")
        
        # Read the data
        df = pd.read_csv(filepath)
        
        # Pivot the data - share becomes columns for each vehicle count
        df_pivot = df.pivot_table(
            index=config["index_cols"],
            columns=config["pivot_col"],
            values="share",
            aggfunc="first"
        ).reset_index()
        
        # Clean up column names - add prefix for vehicle counts
        df_pivot.columns = [col if col in config["index_cols"] else f"vehicles_{col}" for col in df_pivot.columns]
        
        # Rename the columns to be cleaner
        if 'vehicles_0' in df_pivot.columns:
            df_pivot = df_pivot.rename(columns={'vehicles_0': 'zero_vehicles'})
        if 'vehicles_1' in df_pivot.columns:
            df_pivot = df_pivot.rename(columns={'vehicles_1': 'one_vehicle'})
        if 'vehicles_2' in df_pivot.columns:
            df_pivot = df_pivot.rename(columns={'vehicles_2': 'two_vehicles'})
        if 'vehicles_3' in df_pivot.columns:
            df_pivot = df_pivot.rename(columns={'vehicles_3': 'three_vehicles'})
        if 'vehicles_4' in df_pivot.columns:
            df_pivot = df_pivot.rename(columns={'vehicles_4': 'four_plus_vehicles'})
            
        print(f"   Original shape: {df.shape}")
        print(f"   Pivoted shape: {df_pivot.shape}")
        print(f"   Columns: {list(df_pivot.columns)}")
        
        # Save the pivoted data
        output_path = filepath.replace(".csv", "_pivoted.csv")
        df_pivot.to_csv(output_path, index=False)
        print(f"   ✅ Saved: {output_path}")
        print()

if __name__ == "__main__":
    pivot_auto_ownership_data()