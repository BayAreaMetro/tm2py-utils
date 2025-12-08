"""
Example usage of the aggregated_analysis.py script

This script demonstrates how to:
1. Create sample aggregated data files
2. Set up a configuration file
3. Run the analysis script
4. View the results

Run this script to generate sample data and test the analysis workflow.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import tempfile
import sys
import subprocess

def create_sample_data():
    """Create sample aggregated data files for testing."""
    
    # Create temporary directory for sample data
    temp_dir = Path(tempfile.mkdtemp(prefix="tm2py_sample_"))
    print(f"Creating sample data in: {temp_dir}")
    
    # Sample trip data
    np.random.seed(42)
    n_trips = 10000
    
    trip_data = pd.DataFrame({
        'origin_taz': np.random.randint(1, 101, n_trips),
        'dest_taz': np.random.randint(1, 101, n_trips),
        'mode': np.random.choice(['drive_alone', 'carpool', 'transit', 'bike', 'walk'], n_trips, p=[0.4, 0.2, 0.2, 0.1, 0.1]),
        'purpose': np.random.choice(['work', 'school', 'shop', 'other'], n_trips, p=[0.3, 0.1, 0.3, 0.3]),
        'time_period': np.random.choice(['am', 'md', 'pm', 'nt'], n_trips, p=[0.25, 0.3, 0.25, 0.2]),
        'distance': np.random.exponential(5, n_trips),
        'travel_time': np.random.exponential(20, n_trips),
        'income_category': np.random.choice(['low', 'medium', 'high'], n_trips, p=[0.3, 0.5, 0.2])
    })
    trip_data.to_csv(temp_dir / 'trip_summary.csv', index=False)
    
    # Sample household data
    n_households = 5000
    hh_data = pd.DataFrame({
        'hh_id': range(1, n_households + 1),
        'taz': np.random.randint(1, 101, n_households),
        'hh_size': np.random.choice([1, 2, 3, 4, 5], n_households, p=[0.25, 0.35, 0.2, 0.15, 0.05]),
        'workers': np.random.randint(0, 4, n_households),
        'income': np.random.lognormal(10.5, 0.8, n_households),
        'vehicles': np.random.poisson(1.5, n_households),
        'county': np.random.choice(['Alameda', 'Contra Costa', 'Marin', 'Napa', 'San Francisco', 
                                  'San Mateo', 'Santa Clara', 'Solano', 'Sonoma'], n_households),
        'dwelling_type': np.random.choice(['single_family', 'multi_family', 'condo', 'other'], 
                                        n_households, p=[0.6, 0.2, 0.15, 0.05])
    })
    hh_data.to_csv(temp_dir / 'hh_characteristics.csv', index=False)
    
    # Sample person data
    n_persons = 12000
    person_data = pd.DataFrame({
        'person_id': range(1, n_persons + 1),
        'hh_id': np.random.randint(1, n_households + 1, n_persons),
        'age': np.random.randint(5, 85, n_persons),
        'gender': np.random.choice(['male', 'female'], n_persons),
        'employment': np.random.choice(['full_time', 'part_time', 'unemployed', 'student', 'retired'], 
                                     n_persons, p=[0.4, 0.15, 0.1, 0.15, 0.2]),
        'education': np.random.choice(['less_than_hs', 'high_school', 'some_college', 'bachelors', 'graduate'], 
                                    n_persons, p=[0.1, 0.25, 0.3, 0.25, 0.1]),
        'license': np.random.choice([True, False], n_persons, p=[0.85, 0.15])
    })
    person_data.to_csv(temp_dir / 'person_demographics.csv', index=False)
    
    # Sample employment data  
    n_emp = 2000
    emp_data = pd.DataFrame({
        'taz': np.random.randint(1, 101, n_emp),
        'sector': np.random.choice(['retail', 'office', 'manufacturing', 'service', 'other'], 
                                 n_emp, p=[0.2, 0.3, 0.15, 0.25, 0.1]),
        'total_emp': np.random.randint(10, 1000, n_emp),
        'retail_emp': np.random.randint(0, 200, n_emp),
        'office_emp': np.random.randint(0, 500, n_emp),
        'service_emp': np.random.randint(0, 300, n_emp)
    })
    emp_data.to_csv(temp_dir / 'emp_by_sector.csv', index=False)
    
    print("Sample data files created:")
    for file in temp_dir.glob("*.csv"):
        print(f"  {file.name}: {len(pd.read_csv(file))} rows")
    
    return temp_dir

def create_sample_config(input_dir, output_dir):
    """Create a sample configuration file."""
    
    config_content = f"""# Sample configuration for aggregated analysis
[paths]
input_directory = "{str(input_dir).replace(chr(92), '/')}"
output_directory = "{str(output_dir).replace(chr(92), '/')}"

[file_patterns]
trips = "*trip*"
households = "*hh*"
persons = "*person*"
employment = "*emp*"
land_use = "*landuse*"

[analysis_categories]
geography = ["taz", "county"]
demographics = ["income", "age", "hh_size", "workers"]
trip_purpose = ["work", "school", "shop", "other"]
mode = ["drive_alone", "carpool", "transit", "bike", "walk"]
time_period = ["am", "md", "pm", "nt"]

[output_options]
create_excel = true
create_html_charts = true
create_png_charts = true
create_summary_dashboard = true

[chart_options]
max_categories_in_pie = 10
chart_width = 1000
chart_height = 600
dashboard_width = 1200
dashboard_height = 800
"""
    
    config_file = input_dir.parent / 'sample_config.toml'
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    return config_file

def run_analysis_example():
    """Run a complete example of the aggregated analysis."""
    
    print("=" * 70)
    print("AGGREGATED ANALYSIS EXAMPLE")
    print("=" * 70)
    
    try:
        # Create sample data
        input_dir = create_sample_data()
        output_dir = input_dir.parent / 'analysis_output'
        output_dir.mkdir(exist_ok=True)
        
        # Create sample configuration
        config_file = create_sample_config(input_dir, output_dir)
        print(f"Configuration file created: {config_file}")
        
        # Get the analysis script path
        script_dir = Path(__file__).parent
        analysis_script = script_dir / 'aggregated_analysis.py'
        
        if not analysis_script.exists():
            print(f"Analysis script not found at: {analysis_script}")
            print("Make sure aggregated_analysis.py is in the same directory as this example.")
            return
        
        print(f"\nRunning analysis script...")
        print(f"Input directory: {input_dir}")
        print(f"Output directory: {output_dir}")
        print(f"Config file: {config_file}")
        
        # Run the analysis script
        try:
            result = subprocess.run([
                sys.executable, str(analysis_script), str(config_file)
            ], capture_output=True, text=True, timeout=300)
            
            print("\nScript output:")
            print(result.stdout)
            
            if result.stderr:
                print("Script errors:")
                print(result.stderr)
            
            if result.returncode == 0:
                print("\n" + "=" * 70)
                print("EXAMPLE COMPLETED SUCCESSFULLY!")
                print("=" * 70)
                print(f"Sample data: {input_dir}")
                print(f"Analysis results: {output_dir}")
                print(f"Configuration: {config_file}")
                print("\nYou can now examine the generated files:")
                
                # List generated files
                excel_files = list(output_dir.glob("**/*.xlsx"))
                html_files = list(output_dir.glob("**/*.html"))
                png_files = list(output_dir.glob("**/*.png"))
                
                if excel_files:
                    print(f"  Excel files: {[f.name for f in excel_files]}")
                if html_files:
                    print(f"  HTML files: {[f.name for f in html_files]}")
                if png_files:
                    print(f"  PNG files: {[f.name for f in png_files]}")
                    
            else:
                print(f"Script failed with return code: {result.returncode}")
                
        except subprocess.TimeoutExpired:
            print("Script execution timed out after 5 minutes")
        except FileNotFoundError:
            print("Python interpreter not found. Make sure Python is in your PATH.")
            
    except Exception as e:
        print(f"Error running example: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_analysis_example()