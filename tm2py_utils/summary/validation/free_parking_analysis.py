#!/usr/bin/env python3
"""
Free Parking Choice Analysis

Focused analysis script to compare free parking choice between two model runs.
This demonstrates the architecture for a single summary type.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import argparse
from typing import Dict, List, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_person_file(file_path: Path) -> pd.DataFrame:
    """Load and validate person data file."""
    logger.info(f"Loading person data from {file_path}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"Person file not found: {file_path}")
    
    # Read the CSV file
    df = pd.read_csv(file_path)
    logger.info(f"  ✓ Loaded {len(df):,} person records")
    
    # Check for required fields
    required_fields = ['hh_id', 'person_id', 'person_num', 'person_type']
    missing_fields = [field for field in required_fields if field not in df.columns]
    
    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")
    
    # Check for fp_choice field
    if 'fp_choice' not in df.columns:
        logger.warning("  ⚠ fp_choice field not found - may not be in this model version")
        df['fp_choice'] = -1  # Mark as missing
    
    logger.info(f"  ✓ Data validation passed")
    return df


def analyze_free_parking_choice(df: pd.DataFrame, scenario_name: str) -> Dict[str, pd.DataFrame]:
    """Generate free parking choice summaries."""
    logger.info(f"Analyzing free parking choice for {scenario_name}")
    
    summaries = {}
    
    # Filter to workers only (person types 1 and 2)
    if 'person_type' in df.columns:
        workers = df[df['person_type'].isin([1, 2])].copy()
        logger.info(f"  ✓ Found {len(workers):,} workers")
    else:
        workers = df.copy()
        logger.warning("  ⚠ No person_type field - analyzing all persons")
    
    if len(workers) == 0:
        logger.error("No workers found for analysis")
        return summaries
    
    # Regional free parking summary
    if workers['fp_choice'].notna().sum() > 0:
        regional_summary = (workers['fp_choice']
                          .value_counts()
                          .reset_index(name='workers'))
        regional_summary.columns = ['fp_choice', 'workers']
        regional_summary['share'] = (regional_summary['workers'] / 
                                   regional_summary['workers'].sum() * 100)
        regional_summary['scenario'] = scenario_name
        regional_summary['geography'] = 'Regional'
        
        # Add descriptive labels
        regional_summary['fp_choice_label'] = regional_summary['fp_choice'].map({
            0: 'No Free Parking',
            1: 'Free Parking Available',
            -1: 'Not Modeled'
        })
        
        summaries['free_parking_regional'] = regional_summary
        logger.info(f"  ✓ Created regional summary: {len(regional_summary)} categories")
    
    # Free parking by person type
    if 'person_type' in workers.columns and workers['fp_choice'].notna().sum() > 0:
        person_type_summary = (workers.groupby(['person_type', 'fp_choice'])
                             .size()
                             .reset_index(name='workers'))
        person_type_summary['scenario'] = scenario_name
        
        # Add person type labels
        person_type_summary['person_type_label'] = person_type_summary['person_type'].map({
            1: 'Full-time Worker',
            2: 'Part-time Worker'
        })
        
        person_type_summary['fp_choice_label'] = person_type_summary['fp_choice'].map({
            0: 'No Free Parking',
            1: 'Free Parking Available',
            -1: 'Not Modeled'
        })
        
        summaries['free_parking_by_person_type'] = person_type_summary
        logger.info(f"  ✓ Created person type summary: {len(person_type_summary)} records")
    
    # Free parking by income (if household data available)
    if 'income' in workers.columns and workers['fp_choice'].notna().sum() > 0:
        income_summary = (workers.groupby(['income', 'fp_choice'])
                        .size()
                        .reset_index(name='workers'))
        income_summary['scenario'] = scenario_name
        
        # Add income labels
        income_summary['income_label'] = income_summary['income'].map({
            1: 'Low Income (Q1)',
            2: 'Medium-Low Income (Q2)', 
            3: 'Medium-High Income (Q3)',
            4: 'High Income (Q4)'
        })
        
        income_summary['fp_choice_label'] = income_summary['fp_choice'].map({
            0: 'No Free Parking',
            1: 'Free Parking Available',
            -1: 'Not Modeled'
        })
        
        summaries['free_parking_by_income'] = income_summary
        logger.info(f"  ✓ Created income summary: {len(income_summary)} records")
    
    return summaries


def create_comparison_summaries(summaries1: Dict[str, pd.DataFrame], 
                              summaries2: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Create comparison summaries between two scenarios."""
    logger.info("Creating comparison summaries...")
    
    comparisons = {}
    
    # Compare regional summaries
    if 'free_parking_regional' in summaries1 and 'free_parking_regional' in summaries2:
        regional_comparison = pd.concat([
            summaries1['free_parking_regional'],
            summaries2['free_parking_regional']
        ], ignore_index=True)
        
        comparisons['free_parking_regional_comparison'] = regional_comparison
        logger.info("  ✓ Created regional comparison")
    
    # Compare person type summaries
    if 'free_parking_by_person_type' in summaries1 and 'free_parking_by_person_type' in summaries2:
        person_type_comparison = pd.concat([
            summaries1['free_parking_by_person_type'],
            summaries2['free_parking_by_person_type']
        ], ignore_index=True)
        
        comparisons['free_parking_by_person_type_comparison'] = person_type_comparison
        logger.info("  ✓ Created person type comparison")
    
    return comparisons


def save_summaries(summaries: Dict[str, pd.DataFrame], output_dir: Path):
    """Save summary tables to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Saving {len(summaries)} summary files to {output_dir}")
    
    for name, df in summaries.items():
        output_path = output_dir / f"{name}.csv"
        df.to_csv(output_path, index=False)
        logger.info(f"  ✓ Saved {name}.csv ({len(df)} rows)")
    
    # Create summary index
    index_data = []
    for name, df in summaries.items():
        index_data.append({
            'summary_name': name,
            'filename': f"{name}.csv",
            'rows': len(df),
            'columns': len(df.columns),
            'summary_type': 'free_parking_analysis'
        })
    
    index_df = pd.DataFrame(index_data)
    index_df.to_csv(output_dir / "free_parking_analysis_index.csv", index=False)
    logger.info(f"  ✓ Created analysis index")


def create_test_data():
    """Create test data with free parking choices for demonstration."""
    logger.info("Creating test data for free parking analysis...")
    
    # Create test directories
    base_dir = Path("test_free_parking")
    scenario1_dir = base_dir / "2015_baseline"
    scenario2_dir = base_dir / "2023_updated"
    
    scenario1_dir.mkdir(parents=True, exist_ok=True)
    scenario2_dir.mkdir(parents=True, exist_ok=True)
    
    # Create scenario 1 data (2015 baseline)
    np.random.seed(42)
    n_persons = 5000
    
    persons1 = pd.DataFrame({
        'hh_id': np.random.randint(1, 2000, n_persons),
        'person_id': range(1, n_persons + 1),
        'person_num': np.random.randint(1, 5, n_persons),
        'person_type': np.random.choice([1, 2, 3, 4, 5], n_persons, p=[0.4, 0.2, 0.1, 0.2, 0.1]),
        'age': np.random.randint(16, 80, n_persons),
        'gender': np.random.choice([1, 2], n_persons),
        'income': np.random.choice([1, 2, 3, 4], n_persons),
        'fp_choice': np.random.choice([0, 1], n_persons, p=[0.7, 0.3])  # 30% have free parking
    })
    
    # Create scenario 2 data (2023 - more free parking)
    np.random.seed(123)
    persons2 = pd.DataFrame({
        'hh_id': np.random.randint(1, 2000, n_persons),
        'person_id': range(1, n_persons + 1),
        'person_num': np.random.randint(1, 5, n_persons),
        'person_type': np.random.choice([1, 2, 3, 4, 5], n_persons, p=[0.4, 0.2, 0.1, 0.2, 0.1]),
        'age': np.random.randint(16, 80, n_persons),
        'gender': np.random.choice([1, 2], n_persons),
        'income': np.random.choice([1, 2, 3, 4], n_persons),
        'fp_choice': np.random.choice([0, 1], n_persons, p=[0.6, 0.4])  # 40% have free parking
    })
    
    # Save test data
    persons1.to_csv(scenario1_dir / "personData_1.csv", index=False)
    persons2.to_csv(scenario2_dir / "personData_1.csv", index=False)
    
    logger.info(f"  ✓ Created test data in {base_dir}")
    logger.info(f"    Scenario 1: {len(persons1)} persons")
    logger.info(f"    Scenario 2: {len(persons2)} persons")
    
    return scenario1_dir, scenario2_dir


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Free Parking Choice Analysis")
    parser.add_argument("--scenario1-dir", type=Path, help="First scenario directory")
    parser.add_argument("--scenario2-dir", type=Path, help="Second scenario directory")
    parser.add_argument("--output-dir", type=Path, default=Path("free_parking_results"), help="Output directory")
    parser.add_argument("--create-test-data", action="store_true", help="Create test data")
    
    args = parser.parse_args()
    
    try:
        if args.create_test_data:
            # Create test data
            scenario1_dir, scenario2_dir = create_test_data()
        else:
            scenario1_dir = args.scenario1_dir
            scenario2_dir = args.scenario2_dir
            
            if not scenario1_dir or not scenario2_dir:
                parser.error("Must specify both scenario directories or use --create-test-data")
        
        logger.info("Free Parking Choice Analysis")
        logger.info("=" * 40)
        
        # Load data from both scenarios
        person1_file = scenario1_dir / "personData_1.csv"
        person2_file = scenario2_dir / "personData_1.csv"
        
        df1 = load_person_file(person1_file)
        df2 = load_person_file(person2_file)
        
        # Generate summaries
        summaries1 = analyze_free_parking_choice(df1, "Scenario_1")
        summaries2 = analyze_free_parking_choice(df2, "Scenario_2")
        
        # Create comparisons
        comparisons = create_comparison_summaries(summaries1, summaries2)
        
        # Combine all summaries
        all_summaries = {**summaries1, **summaries2, **comparisons}
        
        # Save results
        save_summaries(all_summaries, args.output_dir)
        
        logger.info("✅ Free parking analysis completed successfully!")
        logger.info(f"Results saved to: {args.output_dir.absolute()}")
        
        # Show quick results
        if 'free_parking_regional_comparison' in all_summaries:
            print("\n📊 Regional Free Parking Summary:")
            comparison_df = all_summaries['free_parking_regional_comparison']
            pivot_df = comparison_df.pivot(index='fp_choice_label', columns='scenario', values='share')
            print(pivot_df.round(1))
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        raise


if __name__ == "__main__":
    main()