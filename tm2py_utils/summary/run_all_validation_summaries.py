#!/usr/bin/env python3
"""
CTRAMP Validation Summary Generator - run_all_validation_summaries.py

This script processes multiple CTRAMP model output directories and generates
standardized validation summary CSV files for comparison analysis. It supports both
survey data validation and scenario comparison workflows.

Usage:
    python run_all_validation_summaries.py --input-dirs dir1 dir2 dir3 --output-dir results/
    python run_all_validation_summaries.py --config validation_config.yaml
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator
import yaml
import logging
from dataclasses import dataclass
from enum import Enum
import sys
import os

# ActivitySim imports
import activitysim
import activitysim.core.config as asim_config

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Data source types for comparison analysis."""
    MODEL = "model"
    SURVEY = "survey"
    ACS = "acs"
    BATS = "bats"
    CTPP = "ctpp"


class SummaryType(str, Enum):
    """Types of summaries to generate."""
    AUTO_OWNERSHIP = "auto_ownership"
    WORK_LOCATION = "work_location"
    CDAP = "cdap"
    TOUR_FREQUENCY = "tour_frequency"
    TOUR_MODE = "tour_mode"
    TOUR_TIME = "tour_time"
    TRIP_MODE = "trip_mode"


@dataclass
class FileSpec:
    """Specification for expected input files."""
    filename: str
    required: bool = True
    description: str = ""


class CTRAMPFileSpecs(BaseModel):
    """Expected CTRAMP output file specifications based on tm2py documentation."""
    
    # Core files
    households: FileSpec = FileSpec("householdData_1.csv", True, "Household demographics and characteristics")
    persons: FileSpec = FileSpec("personData_1.csv", True, "Person-level attributes and patterns")
    
    # Location choice results
    workplace_school: FileSpec = FileSpec("wsLocResults_1.csv", True, "Workplace and school location results")
    
    # Tour and trip data
    individual_tours: FileSpec = FileSpec("indivTourData_1.csv", True, "Individual tour patterns")
    individual_trips: FileSpec = FileSpec("indivTripData_1.csv", True, "Individual trip segments")
    joint_tours: FileSpec = FileSpec("jointTourData_1.csv", False, "Joint household tours")
    joint_trips: FileSpec = FileSpec("jointTripData_1.csv", False, "Joint household trips")
    
    @validator('*', pre=True)
    def validate_file_spec(cls, v):
        if isinstance(v, dict):
            return FileSpec(**v)
        return v


class InputDirectory(BaseModel):
    """Configuration for a single input directory."""
    path: Path
    name: str
    source_type: DataSource = DataSource.MODEL
    description: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    @validator('path')
    def path_must_exist(cls, v):
        if not v.exists():
            raise ValueError(f"Directory does not exist: {v}")
        return v


class SummaryConfig(BaseModel):
    """Configuration for summary generation."""
    enabled_summaries: List[SummaryType] = Field(default_factory=lambda: list(SummaryType))
    geographic_levels: List[str] = Field(default=["regional", "county", "taz"])
    income_categories: List[str] = Field(default=["Q1", "Q2", "Q3", "Q4"])
    comparison_mode: str = Field(default="survey_vs_model")  # or "scenario_vs_scenario"


class RunConfig(BaseModel):
    """Main configuration for the summary run."""
    input_directories: List[InputDirectory]
    output_directory: Path
    summary_config: SummaryConfig = Field(default_factory=SummaryConfig)
    file_specs: CTRAMPFileSpecs = Field(default_factory=CTRAMPFileSpecs)
    
    class Config:
        arbitrary_types_allowed = True


class DataLoader:
    """Handles loading and validation of CTRAMP output files."""
    
    def __init__(self, file_specs: CTRAMPFileSpecs):
        self.file_specs = file_specs
        self.data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}
    
    def load_directory(self, input_dir: InputDirectory) -> Dict[str, pd.DataFrame]:
        """Load all available files from a directory."""
        logger.info(f"Loading data from {input_dir.name}: {input_dir.path}")
        
        if input_dir.name in self.data_cache:
            return self.data_cache[input_dir.name]
        
        loaded_data = {}
        
        # Load each file type
        for file_type, file_spec in self.file_specs.dict().items():
            file_path = input_dir.path / file_spec.filename
            
            if file_path.exists():
                try:
                    df = pd.read_csv(file_path)
                    loaded_data[file_type] = df
                    logger.info(f"  ✓ Loaded {file_type}: {len(df):,} records")
                except Exception as e:
                    logger.error(f"  ✗ Error loading {file_type}: {e}")
                    if file_spec.required:
                        raise
            elif file_spec.required:
                raise FileNotFoundError(f"Required file not found: {file_path}")
            else:
                logger.warning(f"  ⚠ Optional file not found: {file_path}")
        
        # Cache the loaded data
        self.data_cache[input_dir.name] = loaded_data
        return loaded_data
    
    def validate_data_consistency(self, data: Dict[str, pd.DataFrame]) -> bool:
        """Validate relationships between loaded data tables."""
        logger.info("Validating data consistency...")
        
        issues = []
        
        # Check household-person relationships
        if 'households' in data and 'persons' in data:
            hh_ids_hh = set(data['households']['hh_id'].unique())
            hh_ids_person = set(data['persons']['hh_id'].unique())
            
            if not hh_ids_person.issubset(hh_ids_hh):
                missing = hh_ids_person - hh_ids_hh
                issues.append(f"Person records reference {len(missing)} non-existent households")
        
        # Check tour-trip relationships
        if 'individual_tours' in data and 'individual_trips' in data:
            tour_ids_tours = set(data['individual_tours']['tour_id'].unique())
            tour_ids_trips = set(data['individual_trips']['tour_id'].unique())
            
            if not tour_ids_trips.issubset(tour_ids_tours):
                missing = tour_ids_trips - tour_ids_tours
                issues.append(f"Trip records reference {len(missing)} non-existent tours")
        
        if issues:
            for issue in issues:
                logger.warning(f"  ⚠ {issue}")
            return False
        
        logger.info("  ✓ Data consistency validated")
        return True


class SummaryGenerator:
    """Generates standardized summaries from CTRAMP output data."""
    
    def __init__(self, config: SummaryConfig):
        self.config = config
    
    def generate_auto_ownership_summaries(self, datasets: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
        """Generate auto ownership summary tables."""
        logger.info("Generating auto ownership summaries...")
        
        summaries = {}
        
        for dataset_name, data in datasets.items():
            if 'households' not in data:
                logger.warning(f"  ⚠ Skipping {dataset_name}: missing household data")
                continue
            
            hh_data = data['households'].copy()
            
            # Regional auto ownership share
            regional_summary = (hh_data.groupby('vehicles')
                              .size()
                              .reset_index(name='households'))
            regional_summary['share'] = regional_summary['households'] / regional_summary['households'].sum() * 100
            regional_summary['dataset'] = dataset_name
            regional_summary['geography'] = 'Regional'
            
            summaries[f'auto_ownership_regional_{dataset_name}'] = regional_summary
            
            # Auto ownership by income (if available)
            if 'income' in hh_data.columns:
                income_summary = (hh_data.groupby(['income', 'vehicles'])
                                .size()
                                .reset_index(name='households'))
                income_summary['dataset'] = dataset_name
                summaries[f'auto_ownership_by_income_{dataset_name}'] = income_summary
        
        return summaries
    
    def generate_work_location_summaries(self, datasets: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
        """Generate work location and telecommuting summaries."""
        logger.info("Generating work location summaries...")
        
        summaries = {}
        
        for dataset_name, data in datasets.items():
            if 'persons' not in data:
                logger.warning(f"  ⚠ Skipping {dataset_name}: missing person data")
                continue
            
            person_data = data['persons'].copy()
            
            # Filter to workers only
            if 'person_type' in person_data.columns:
                workers = person_data[person_data['person_type'].isin([1, 2])]  # Full-time, part-time workers
            else:
                logger.warning(f"  ⚠ No person_type field found in {dataset_name}")
                continue
            
            if len(workers) == 0:
                logger.warning(f"  ⚠ No workers found in {dataset_name}")
                continue
            
            # Work from home analysis (if telecommute field available)
            if 'telecommute_frequency' in workers.columns:
                wfh_summary = (workers.groupby('telecommute_frequency')
                             .size()
                             .reset_index(name='workers'))
                wfh_summary['share'] = wfh_summary['workers'] / wfh_summary['workers'].sum() * 100
                wfh_summary['dataset'] = dataset_name
                summaries[f'work_from_home_{dataset_name}'] = wfh_summary
        
        return summaries
    
    def generate_tour_summaries(self, datasets: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
        """Generate tour frequency, mode, and timing summaries."""
        logger.info("Generating tour summaries...")
        
        summaries = {}
        
        for dataset_name, data in datasets.items():
            if 'individual_tours' not in data:
                logger.warning(f"  ⚠ Skipping {dataset_name}: missing tour data")
                continue
            
            tour_data = data['individual_tours'].copy()
            
            # Tour frequency by purpose
            if 'tour_purpose' in tour_data.columns:
                purpose_summary = (tour_data.groupby('tour_purpose')
                                 .size()
                                 .reset_index(name='tours'))
                purpose_summary['dataset'] = dataset_name
                summaries[f'tour_frequency_by_purpose_{dataset_name}'] = purpose_summary
            
            # Tour mode choice
            if 'tour_mode' in tour_data.columns:
                mode_summary = (tour_data.groupby('tour_mode')
                              .size()
                              .reset_index(name='tours'))
                mode_summary['share'] = mode_summary['tours'] / mode_summary['tours'].sum() * 100
                mode_summary['dataset'] = dataset_name
                summaries[f'tour_mode_choice_{dataset_name}'] = mode_summary
            
            # Tour time of day (if available)
            if 'start_period' in tour_data.columns and 'end_period' in tour_data.columns:
                tod_summary = (tour_data.groupby(['start_period', 'end_period'])
                             .size()
                             .reset_index(name='tours'))
                tod_summary['dataset'] = dataset_name
                summaries[f'tour_time_of_day_{dataset_name}'] = tod_summary
        
        return summaries
    
    def generate_all_summaries(self, datasets: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
        """Generate all enabled summaries."""
        all_summaries = {}
        
        if SummaryType.AUTO_OWNERSHIP in self.config.enabled_summaries:
            all_summaries.update(self.generate_auto_ownership_summaries(datasets))
        
        if SummaryType.WORK_LOCATION in self.config.enabled_summaries:
            all_summaries.update(self.generate_work_location_summaries(datasets))
        
        if SummaryType.TOUR_FREQUENCY in self.config.enabled_summaries or \
           SummaryType.TOUR_MODE in self.config.enabled_summaries or \
           SummaryType.TOUR_TIME in self.config.enabled_summaries:
            all_summaries.update(self.generate_tour_summaries(datasets))
        
        return all_summaries


def save_summaries(summaries: Dict[str, pd.DataFrame], output_dir: Path):
    """Save all summary tables to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Saving {len(summaries)} summary tables to {output_dir}")
    
    for summary_name, summary_df in summaries.items():
        output_path = output_dir / f"{summary_name}.csv"
        summary_df.to_csv(output_path, index=False)
        logger.info(f"  ✓ Saved {summary_name}: {len(summary_df)} rows")
    
    # Create a summary index
    index_data = []
    for summary_name, summary_df in summaries.items():
        index_data.append({
            'summary_name': summary_name,
            'filename': f"{summary_name}.csv",
            'rows': len(summary_df),
            'columns': len(summary_df.columns),
            'description': f"Summary table: {summary_name}"
        })
    
    index_df = pd.DataFrame(index_data)
    index_df.to_csv(output_dir / "summary_index.csv", index=False)
    logger.info(f"  ✓ Created summary index with {len(index_data)} tables")


def create_default_config(input_dirs: List[Path], output_dir: Path) -> RunConfig:
    """Create default configuration from command line arguments."""
    input_directories = []
    
    for i, path in enumerate(input_dirs):
        input_directories.append(InputDirectory(
            path=path,
            name=f"scenario_{i+1}",
            source_type=DataSource.MODEL,
            description=f"Model run: {path.name}"
        ))
    
    return RunConfig(
        input_directories=input_directories,
        output_directory=output_dir
    )


def load_config_file(config_path: Path) -> RunConfig:
    """Load configuration from YAML file."""
    with open(config_path) as f:
        config_data = yaml.safe_load(f)
    
    return RunConfig(**config_data)


def main():
    """Main execution function for validation summary generation."""
    parser = argparse.ArgumentParser(
        description="Generate standardized validation summaries from CTRAMP model outputs"
    )
    parser.add_argument(
        "--input-dirs", 
        nargs="+", 
        type=Path,
        help="Input directories containing CTRAMP outputs"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for validation summary files"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Configuration file (YAML format)"
    )
    parser.add_argument(
        "--summaries",
        nargs="+",
        choices=[s.value for s in SummaryType],
        help="Specific summaries to generate (default: all)"
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        if args.config:
            config = load_config_file(args.config)
        else:
            if not args.input_dirs:
                parser.error("Either --config or --input-dirs must be provided")
            config = create_default_config(args.input_dirs, args.output_dir)
        
        # Override summaries if specified
        if args.summaries:
            config.summary_config.enabled_summaries = [SummaryType(s) for s in args.summaries]
        
        logger.info(f"Starting CTRAMP validation summary generation")
        logger.info(f"Input directories: {len(config.input_directories)}")
        logger.info(f"Output directory: {config.output_directory}")
        logger.info(f"Enabled summaries: {[s.value for s in config.summary_config.enabled_summaries]}")
        
        # Initialize components
        data_loader = DataLoader(config.file_specs)
        summary_generator = SummaryGenerator(config.summary_config)
        
        # Load all datasets
        all_datasets = {}
        for input_dir in config.input_directories:
            try:
                data = data_loader.load_directory(input_dir)
                data_loader.validate_data_consistency(data)
                all_datasets[input_dir.name] = data
            except Exception as e:
                logger.error(f"Failed to load {input_dir.name}: {e}")
                continue
        
        if not all_datasets:
            logger.error("No datasets successfully loaded. Exiting.")
            sys.exit(1)
        
        # Generate summaries
        summaries = summary_generator.generate_all_summaries(all_datasets)
        
        if not summaries:
            logger.warning("No summaries generated")
            sys.exit(1)
        
        # Save results
        save_summaries(summaries, config.output_directory)
        
        logger.info("✅ Validation summary generation completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error during execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()