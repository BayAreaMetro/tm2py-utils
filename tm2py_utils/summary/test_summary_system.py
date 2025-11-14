#!/usr/bin/env python3
"""
Test script for CTRAMP Summary System

Creates sample data and demonstrates the run_all_summaries functionality.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import shutil
import tempfile
import yaml

# Create sample CTRAMP data that matches the expected format
def create_sample_ctramp_data():
    """Create sample CTRAMP data files for testing."""
    
    np.random.seed(42)  # For reproducible results
    
    # Sample household data
    n_households = 1000
    households = pd.DataFrame({
        'hh_id': range(1, n_households + 1),
        'home_mgra': np.random.randint(1, 2000, n_households),
        'income': np.random.choice([1, 2, 3, 4], n_households, p=[0.25, 0.3, 0.25, 0.2]),
        'vehicles': np.random.choice([0, 1, 2, 3, 4], n_households, p=[0.15, 0.35, 0.35, 0.12, 0.03]),
        'workers': np.random.choice([0, 1, 2, 3], n_households, p=[0.2, 0.4, 0.35, 0.05]),
        'hhsize': np.random.choice([1, 2, 3, 4, 5], n_households, p=[0.3, 0.35, 0.2, 0.12, 0.03]),
        'HHT': np.random.choice([1, 2, 3, 4], n_households),
        'BLD': np.random.choice([1, 2, 3, 4, 5], n_households),
        'TYPE': np.random.choice([1, 2, 3], n_households),
        'sampleRate': np.random.uniform(0.5, 2.0, n_households)
    })
    
    # Sample person data
    persons_per_hh = []
    for hh_id, hh_size in zip(households['hh_id'], households['hhsize']):
        for person_num in range(1, hh_size + 1):
            persons_per_hh.append({
                'hh_id': hh_id,
                'person_num': person_num
            })
    
    person_base = pd.DataFrame(persons_per_hh)
    n_persons = len(person_base)
    
    persons = person_base.copy()
    persons['person_id'] = range(1, n_persons + 1)
    persons['person_type'] = np.random.choice([1, 2, 3, 4, 5, 6, 7, 8], n_persons, 
                                            p=[0.25, 0.15, 0.05, 0.2, 0.15, 0.1, 0.07, 0.03])
    persons['age'] = np.random.randint(0, 85, n_persons)
    persons['gender'] = np.random.choice([1, 2], n_persons)
    persons['work_mgra'] = np.where(
        persons['person_type'].isin([1, 2]), 
        np.random.randint(1, 2000, n_persons), 
        -1
    )
    persons['school_mgra'] = np.where(
        persons['person_type'].isin([3, 6, 7]), 
        np.random.randint(1, 2000, n_persons), 
        -1
    )
    persons['telecommute_frequency'] = np.where(
        persons['person_type'].isin([1, 2]),
        np.random.choice([0, 1, 2, 3], n_persons),
        0
    )
    
    # Sample tour data
    n_tours = int(n_persons * 1.5)  # Average 1.5 tours per person
    tours = pd.DataFrame({
        'tour_id': range(1, n_tours + 1),
        'person_id': np.random.choice(persons['person_id'], n_tours),
        'tour_purpose': np.random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9], n_tours,
                                       p=[0.35, 0.05, 0.15, 0.1, 0.15, 0.1, 0.05, 0.03, 0.02]),
        'tour_mode': np.random.choice(range(1, 18), n_tours),  # 17 modes in standard model
        'dest_mgra': np.random.randint(1, 2000, n_tours),
        'start_period': np.random.randint(1, 49, n_tours),
        'end_period': np.random.randint(1, 49, n_tours),
        'tour_distance': np.random.exponential(10.0, n_tours),
        'valueOfTime': np.random.uniform(5.0, 25.0, n_tours),
        'dcLogsum': np.random.normal(0, 2, n_tours)
    })
    
    # Add household and person info to tours
    tours = tours.merge(persons[['person_id', 'hh_id', 'person_num', 'person_type']], 
                       on='person_id', how='left')
    
    # Sample trip data 
    n_trips = int(n_tours * 2.5)  # Average 2.5 trips per tour
    trips = pd.DataFrame({
        'person_id': np.random.choice(tours['person_id'], n_trips),
        'tour_id': np.random.choice(tours['tour_id'], n_trips),
        'stop_id': np.random.choice([0, 1, 2, 3], n_trips, p=[0.6, 0.25, 0.1, 0.05]),
        'inbound': np.random.choice([True, False], n_trips),
        'orig_mgra': np.random.randint(1, 2000, n_trips),
        'dest_mgra': np.random.randint(1, 2000, n_trips),
        'trip_mode': np.random.choice(range(1, 18), n_trips),
        'trip_purpose': np.random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9], n_trips),
        'trip_period': np.random.randint(1, 49, n_trips),
        'trip_distance': np.random.exponential(5.0, n_trips)
    })
    
    # Add household and person info to trips
    trips = trips.merge(persons[['person_id', 'hh_id', 'person_num']], 
                       on='person_id', how='left')
    
    # Workplace/school location results
    workers_students = persons[persons['person_type'].isin([1, 2, 3, 6, 7])].copy()
    ws_locations = workers_students[['person_id', 'hh_id', 'person_num', 'person_type']].copy()
    
    ws_locations['WorkLocation'] = np.where(
        ws_locations['person_type'].isin([1, 2]),
        ws_locations['person_id'].map(dict(zip(workers_students['person_id'], workers_students['work_mgra']))),
        -1
    )
    ws_locations['WorkLocationDistance'] = np.where(
        ws_locations['WorkLocation'] > 0,
        np.random.exponential(15.0, len(ws_locations)),
        0
    )
    ws_locations['WorkLocationLogsum'] = np.where(
        ws_locations['WorkLocation'] > 0,
        np.random.normal(0, 1.5, len(ws_locations)),
        0
    )
    
    ws_locations['SchoolLocation'] = np.where(
        ws_locations['person_type'].isin([3, 6, 7]),
        ws_locations['person_id'].map(dict(zip(workers_students['person_id'], workers_students['school_mgra']))),
        -1
    )
    ws_locations['SchoolLocationDistance'] = np.where(
        ws_locations['SchoolLocation'] > 0,
        np.random.exponential(8.0, len(ws_locations)),
        0
    )
    ws_locations['SchoolLocationLogsum'] = np.where(
        ws_locations['SchoolLocation'] > 0,
        np.random.normal(0, 1.0, len(ws_locations)),
        0
    )
    
    return {
        'householdData_1.csv': households,
        'personData_1.csv': persons,
        'indivTourData_1.csv': tours,
        'indivTripData_1.csv': trips,
        'wsLocResults_1.csv': ws_locations
    }


def create_test_directories():
    """Create test directories with sample data."""
    
    # Create temporary directories
    base_dir = Path(tempfile.mkdtemp(prefix='ctramp_test_'))
    
    scenario1_dir = base_dir / 'scenario1'
    scenario2_dir = base_dir / 'scenario2'
    output_dir = base_dir / 'summaries'
    
    scenario1_dir.mkdir(parents=True)
    scenario2_dir.mkdir(parents=True)
    
    print(f"Created test directories in: {base_dir}")
    
    # Create sample data for scenario 1
    print("Creating scenario 1 data...")
    data1 = create_sample_ctramp_data()
    for filename, df in data1.items():
        df.to_csv(scenario1_dir / filename, index=False)
        print(f"  ✓ {filename}: {len(df):,} records")
    
    # Create slightly different data for scenario 2
    print("Creating scenario 2 data...")
    np.random.seed(123)  # Different seed for variation
    data2 = create_sample_ctramp_data()
    
    # Modify scenario 2 to have more telecommuting
    data2['personData_1.csv']['telecommute_frequency'] = np.where(
        data2['personData_1.csv']['person_type'].isin([1, 2]),
        np.random.choice([0, 1, 2, 3], len(data2['personData_1.csv']), p=[0.4, 0.3, 0.2, 0.1]),
        0
    )
    
    for filename, df in data2.items():
        df.to_csv(scenario2_dir / filename, index=False)
        print(f"  ✓ {filename}: {len(df):,} records")
    
    return scenario1_dir, scenario2_dir, output_dir


def create_test_config(scenario1_dir, scenario2_dir, output_dir):
    """Create a test configuration file."""
    
    config = {
        'input_directories': [
            {
                'path': str(scenario1_dir),
                'name': 'baseline',
                'source_type': 'model',
                'description': 'Baseline scenario with standard telecommuting'
            },
            {
                'path': str(scenario2_dir),
                'name': 'high_telecommute',
                'source_type': 'model', 
                'description': 'Scenario with increased telecommuting'
            }
        ],
        'output_directory': str(output_dir),
        'summary_config': {
            'enabled_summaries': [
                'auto_ownership',
                'work_location',
                'tour_frequency',
                'tour_mode'
            ],
            'geographic_levels': ['regional'],
            'comparison_mode': 'scenario_vs_scenario'
        }
    }
    
    config_path = output_dir.parent / 'test_config.yaml'
    config_path.parent.mkdir(exist_ok=True)
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"Created test config: {config_path}")
    return config_path


def main():
    """Run the test demonstration."""
    print("CTRAMP Summary System Test")
    print("=" * 40)
    
    try:
        # Create test data
        scenario1_dir, scenario2_dir, output_dir = create_test_directories()
        config_path = create_test_config(scenario1_dir, scenario2_dir, output_dir)
        
        print(f"\n📁 Test setup complete!")
        print(f"Scenario 1: {scenario1_dir}")
        print(f"Scenario 2: {scenario2_dir}")
        print(f"Config file: {config_path}")
        print(f"Output dir: {output_dir}")
        
        print(f"\n🚀 To run the summary system:")
        print(f"cd {Path.cwd()}")
        print(f"python run_all_summaries.py --config {config_path}")
        
        print(f"\n🧹 To clean up test data:")
        print(f"Remove directory: {scenario1_dir.parent}")
        
        return config_path
        
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        return None


if __name__ == "__main__":
    config_path = main()
    
    if config_path:
        print(f"\n✅ Test data created successfully!")
        print(f"Run 'python run_all_summaries.py --config {config_path}' to test the system")
    else:
        print(f"\n❌ Test setup failed")