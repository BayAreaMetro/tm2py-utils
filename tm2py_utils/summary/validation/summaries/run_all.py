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
import webbrowser

# Validation summary modules
from . import household_summary, worker_summary, tour_summary, trip_summary
from ..data_model.ctramp_data_model_loader import load_data_model
from ..dashboard.dashboard_writer import (
    create_household_dashboard, 
    create_worker_dashboard,
    create_tour_dashboard,
    create_trip_dashboard
)

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
    """Configuration for an input directory."""
    path: Path
    name: str
    source_type: DataSource = DataSource.MODEL
    description: str = ""
    iteration: Optional[int] = None  # Specific iteration to load (e.g., 1 for _1.csv), None = highest
    display_name: Optional[str] = None  # Human-readable label for dashboards (defaults to name)
    available_tables: Optional[List[str]] = None  # Optional: limit which tables to load (e.g., ["households"] for ACS data)
    
    class Config:
        arbitrary_types_allowed = True
    
    @validator('path')
    def path_must_exist(cls, v):
        if not v.exists():
            raise ValueError(f"Directory does not exist: {v}")
        return v


class OutputConfig(BaseModel):
    """Configuration for output file customization."""
    filename_patterns: Dict[str, str] = Field(default_factory=dict)
    column_renames: Dict[str, str] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


class ColumnMapping(BaseModel):
    """Configuration for input column name mapping."""
    persons: Dict[str, str] = Field(default_factory=dict)
    households: Dict[str, str] = Field(default_factory=dict)
    tours: Dict[str, str] = Field(default_factory=dict)
    trips: Dict[str, str] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


class BinningSpec(BaseModel):
    """Specification for binning a continuous variable."""
    bins: List[float]
    labels: Optional[List[str]] = None
    
    class Config:
        arbitrary_types_allowed = True


class AggregationSpec(BaseModel):
    """Specification for aggregating categorical variables into broader groups."""
    mapping: Dict[Union[int, str], str]  # Original value -> Aggregated category
    apply_to: List[str]  # List of column names to apply this aggregation to
    
    class Config:
        arbitrary_types_allowed = True


class SummaryConfig(BaseModel):
    """Configuration for summary generation."""
    enabled_summaries: List[SummaryType] = Field(default_factory=lambda: list(SummaryType))
    geographic_levels: List[str] = Field(default=["regional", "county", "taz"])
    income_categories: List[str] = Field(default=["Q1", "Q2", "Q3", "Q4"])
    comparison_mode: str = Field(default="survey_vs_model")  # or "scenario_vs_scenario"


class ObservedSummary(BaseModel):
    """Configuration for a pre-aggregated observed/survey summary."""
    name: str
    display_name: str
    summaries: Dict[str, Dict[str, Any]]  # summary_name -> {file, columns}
    
    class Config:
        arbitrary_types_allowed = True


class RunConfig(BaseModel):
    """Main configuration for the summary run."""
    input_directories: List[InputDirectory]
    output_directory: Path
    summary_config: SummaryConfig = Field(default_factory=SummaryConfig)
    file_specs: CTRAMPFileSpecs = Field(default_factory=CTRAMPFileSpecs)
    column_mapping: ColumnMapping = Field(default_factory=ColumnMapping)
    output_config: OutputConfig = Field(default_factory=OutputConfig)
    binning_specs: Dict[str, BinningSpec] = Field(default_factory=dict)
    aggregation_specs: Dict[str, AggregationSpec] = Field(default_factory=dict)
    observed_summaries: List[ObservedSummary] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True


class DataLoader:
    """Handles loading and validation of CTRAMP output files."""
    
    def __init__(self, file_specs: CTRAMPFileSpecs, column_mapping: ColumnMapping = None, data_model_path: Optional[Path] = None, binning_specs: Optional[Dict[str, BinningSpec]] = None, aggregation_specs: Optional[Dict[str, AggregationSpec]] = None):
        self.file_specs = file_specs
        self.column_mapping = column_mapping or ColumnMapping()
        self.data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.binning_specs = binning_specs or {}
        self.aggregation_specs = aggregation_specs or {}
        
        # Load data model for column mapping
        if data_model_path is None:
            # Use default path relative to this file
            data_model_path = Path(__file__).parent.parent / "data_model" / "ctramp_data_model.yaml"
        
        self.data_model = None
        if data_model_path.exists():
            try:
                self.data_model = load_data_model(data_model_path)
                logger.info(f"  ✓ Loaded data model from {data_model_path.name}")
                
                # Use aggregation specs from data model if not provided explicitly
                if not self.aggregation_specs and hasattr(self.data_model, 'aggregation_specs'):
                    self.aggregation_specs = {
                        name: AggregationSpec(**spec) 
                        for name, spec in self.data_model.aggregation_specs.items()
                    }
                    if self.aggregation_specs:
                        logger.info(f"  ✓ Loaded {len(self.aggregation_specs)} aggregation specs from data model")
            except Exception as e:
                logger.warning(f"  ⚠ Could not load data model: {e}")
        else:
            logger.warning(f"  ⚠ Data model not found at {data_model_path}")
    
    def _get_workspace_root(self) -> Path:
        """Get the workspace root directory for finding geography files."""
        # Go up from this file to find tm2py-utils root
        # This file is at: tm2py_utils/summary/validation/summaries/run_all.py
        # Workspace root is at: tm2py-utils/
        return Path(__file__).parent.parent.parent.parent.parent
    
    def _find_iteration_file(self, directory: Path, base_filename: str, iteration: Optional[int] = None) -> Optional[Path]:
        """Find file with specific or highest iteration number.
        
        Args:
            directory: Directory to search in
            base_filename: Base filename pattern (e.g., 'householdData_1.csv')
            iteration: Specific iteration to load, or None for highest
            
        Returns:
            Path to file, or None if not found
        """
        # Extract the base name and extension
        # e.g., 'householdData_1.csv' -> 'householdData', '.csv'
        parts = base_filename.rsplit('_', 1)
        if len(parts) != 2:
            # No underscore pattern, return original
            return directory / base_filename if (directory / base_filename).exists() else None
        
        base_name = parts[0]
        ext_part = parts[1]  # e.g., '1.csv'
        extension = '.' + ext_part.split('.', 1)[1] if '.' in ext_part else ''
        
        # If specific iteration requested, check for that file directly
        if iteration is not None:
            target_file = directory / f"{base_name}_{iteration}{extension}"
            if target_file.exists():
                logger.info(f"  → Found iteration {iteration}: {target_file.name}")
                return target_file
            else:
                logger.warning(f"  ⚠ Iteration {iteration} not found: {target_file.name}")
                return None
        
        # Find all matching files with pattern: baseName_N.ext
        import re
        pattern = re.compile(rf'^{re.escape(base_name)}_(\d+){re.escape(extension)}$')
        
        matching_files = []
        for file_path in directory.iterdir():
            if file_path.is_file():
                match = pattern.match(file_path.name)
                if match:
                    iteration_num = int(match.group(1))
                    matching_files.append((iteration_num, file_path))
        
        if not matching_files:
            return None
        
        # Return file with highest iteration number
        matching_files.sort(key=lambda x: x[0], reverse=True)
        highest_iteration, highest_file = matching_files[0]
        logger.info(f"  → Found highest iteration: {highest_file.name} (iteration {highest_iteration})")
        return highest_file
    
    def _apply_binning_specs(self, df: pd.DataFrame, file_type: str) -> pd.DataFrame:
        """
        Apply binning specifications to continuous variables in the dataframe.
        
        Args:
            df: Input dataframe
            file_type: Type of file (households, persons, tours, trips, etc.)
            
        Returns:
            DataFrame with binned columns added
        """
        from .summary_utils import bin_continuous_variable
        
        if not self.binning_specs:
            return df
        
        for col_name, bin_spec in self.binning_specs.items():
            # Check if this column exists in the dataframe
            if col_name in df.columns:
                try:
                    # Create binned version with '_bin' suffix
                    df = bin_continuous_variable(
                        df,
                        value_col=col_name,
                        bins=bin_spec.bins,
                        labels=bin_spec.labels,
                        bin_col_name=f'{col_name}_bin'
                    )
                    logger.info(f"    → Binned '{col_name}' into {len(bin_spec.bins)-1} categories")
                except Exception as e:
                    logger.warning(f"    ⚠ Could not bin '{col_name}': {e}")
        
        return df
    
    def _apply_aggregation_specs(self, df: pd.DataFrame, file_type: str) -> pd.DataFrame:
        """
        Apply aggregation specifications to categorical variables in the dataframe.
        Groups detailed categories into broader categories for easier analysis.
        
        Args:
            df: Input dataframe
            file_type: Type of file (households, persons, tours, trips, etc.)
            
        Returns:
            DataFrame with aggregated columns added
        """
        if not self.aggregation_specs:
            return df
        
        for spec_name, agg_spec in self.aggregation_specs.items():
            for col_name in agg_spec.apply_to:
                # Check if this column exists in the dataframe
                if col_name in df.columns:
                    try:
                        # Create aggregated version with '_agg' suffix
                        agg_col_name = f'{col_name}_agg'
                        
                        # Convert mapping keys to match column dtype
                        if pd.api.types.is_integer_dtype(df[col_name]):
                            # Ensure mapping keys are integers
                            mapping = {int(k): v for k, v in agg_spec.mapping.items()}
                        else:
                            # Keep as strings
                            mapping = {str(k): v for k, v in agg_spec.mapping.items()}
                        
                        # Apply mapping
                        df[agg_col_name] = df[col_name].map(mapping)
                        
                        # Warn about unmapped values
                        unmapped = df[agg_col_name].isna() & df[col_name].notna()
                        if unmapped.any():
                            unmapped_values = df.loc[unmapped, col_name].unique()
                            logger.warning(f"    ⚠ '{col_name}' has unmapped values: {unmapped_values[:5].tolist()}")
                        
                        logger.info(f"    → Aggregated '{col_name}' into {df[agg_col_name].nunique()} categories ({agg_col_name})")
                    except Exception as e:
                        logger.warning(f"    ⚠ Could not aggregate '{col_name}': {e}")
        
        return df
    
    def load_directory(self, input_dir: InputDirectory) -> Dict[str, pd.DataFrame]:
        """Load all available files from a directory."""
        logger.info(f"Loading data from {input_dir.name}: {input_dir.path}")
        
        if input_dir.name in self.data_cache:
            return self.data_cache[input_dir.name]
        
        loaded_data = {}
        
        # Load each file type
        for file_type, file_spec in self.file_specs.dict().items():
            # Skip if available_tables is specified and this table is not in the list
            if input_dir.available_tables is not None and file_type not in input_dir.available_tables:
                logger.info(f"  ⊘ Skipping {file_type} (not in available_tables for {input_dir.name})")
                continue
            
            # Find the file with specified or highest iteration number
            file_path = self._find_iteration_file(input_dir.path, file_spec.filename, input_dir.iteration)
            
            if file_path and file_path.exists():
                try:
                    df = pd.read_csv(file_path)
                    
                    # Apply data model column mapping (CSV names → internal standard names)
                    if self.data_model:
                        try:
                            df = self.data_model.apply_column_mapping(df, file_type)
                            logger.info(f"    → Applied data model mapping for {file_type}")
                        except Exception as e:
                            logger.warning(f"    ⚠ Could not apply data model mapping: {e}")
                    
                    # Apply legacy column mapping if configured (for backward compatibility)
                    mapping_dict = getattr(self.column_mapping, file_type, {})
                    if isinstance(mapping_dict, dict) and mapping_dict:
                        rename_dict = {v: k for k, v in mapping_dict.items() if v in df.columns}
                        if rename_dict:
                            df = df.rename(columns=rename_dict)
                            logger.info(f"    → Mapped {len(rename_dict)} columns: {', '.join(f'{v}→{k}' for v, k in list(rename_dict.items())[:3])}")
                    
                    # Apply binning specs to continuous variables
                    df = self._apply_binning_specs(df, file_type)
                    
                    # Apply aggregation specs to categorical variables
                    df = self._apply_aggregation_specs(df, file_type)
                    
                    # Join geography for households (adds county_name, district_name)
                    if file_type == 'households' and self.data_model:
                        try:
                            df = self.data_model.join_geography(
                                df, 
                                join_col='home_mgra',
                                geography_cols=['county_name', 'district_name'],
                                workspace_root=self._get_workspace_root()
                            )
                        except Exception as e:
                            logger.warning(f"    ⚠ Could not join geography: {e}")
                    
                    loaded_data[file_type] = df
                    logger.info(f"  ✓ Loaded {file_type}: {len(df):,} records from {file_path.name}")
                except Exception as e:
                    logger.error(f"  ✗ Error loading {file_type}: {e}")
                    if file_spec.required:
                        raise
            elif file_spec.required:
                raise FileNotFoundError(f"Required file not found: {file_spec.filename} in {input_dir.path}")
            else:
                logger.warning(f"  ⚠ Optional file not found: {file_spec.filename}")
        
        # Cache the loaded data
        self.data_cache[input_dir.name] = loaded_data
        return loaded_data
    
    def load_observed_summaries(self, observed_config: ObservedSummary) -> Dict[str, pd.DataFrame]:
        """
        Load pre-aggregated summary data from survey/observed sources.
        
        Args:
            observed_config: Configuration specifying summary files and column mappings
            
        Returns:
            Dictionary mapping summary names to DataFrames with standardized columns
        """
        logger.info(f"Loading pre-aggregated summaries from {observed_config.name}: {observed_config.display_name}")
        
        loaded_summaries = {}
        
        for summary_name, summary_spec in observed_config.summaries.items():
            file_path = Path(summary_spec['file'])
            
            if not file_path.exists():
                logger.warning(f"  ⚠ Summary file not found: {file_path}")
                continue
            
            try:
                # Load the CSV
                df = pd.read_csv(file_path)
                
                # Apply column renaming if specified
                if 'columns' in summary_spec:
                    column_map = summary_spec['columns']
                    # Rename columns: {standard_name: csv_column_name} -> {csv_column_name: standard_name}
                    reverse_map = {v: k for k, v in column_map.items() if v in df.columns}
                    if reverse_map:
                        df = df.rename(columns=reverse_map)
                        logger.info(f"    → Mapped {len(reverse_map)} columns")
                
                # Add dataset identifier
                df['dataset'] = observed_config.display_name
                
                # Store with dataset-specific key
                summary_key = f"{summary_name}_{observed_config.name}"
                loaded_summaries[summary_key] = df
                
                logger.info(f"  ✓ Loaded {summary_name}: {len(df):,} rows from {file_path.name}")
                
            except Exception as e:
                logger.error(f"  ✗ Error loading {summary_name}: {e}")
                continue
        
        return loaded_summaries
    
    def validate_data_consistency(self, data: Dict[str, pd.DataFrame]) -> bool:
        """Validate relationships between loaded data tables."""
        logger.info("Validating data consistency...")
        
        issues = []
        
        # Check household-person relationships (using standard column names after mapping)
        if 'households' in data and 'persons' in data:
            # Use mapped column names
            hh_col = 'household_id' if 'household_id' in data['households'].columns else 'hh_id'
            person_hh_col = 'household_id' if 'household_id' in data['persons'].columns else 'hh_id'
            
            if hh_col in data['households'].columns and person_hh_col in data['persons'].columns:
                hh_ids_hh = set(data['households'][hh_col].unique())
                hh_ids_person = set(data['persons'][person_hh_col].unique())
                
                if not hh_ids_person.issubset(hh_ids_hh):
                    missing = hh_ids_person - hh_ids_hh
                    issues.append(f"Person records reference {len(missing)} non-existent households")
        
        # Check tour-trip relationships (using standard column names after mapping)
        if 'individual_tours' in data and 'individual_trips' in data:
            # Use mapped column names
            tour_col = 'tour_id' if 'tour_id' in data['individual_tours'].columns else 'tour_id'
            trip_tour_col = 'tour_id' if 'tour_id' in data['individual_trips'].columns else 'tour_id'
            
            if tour_col in data['individual_tours'].columns and trip_tour_col in data['individual_trips'].columns:
                tour_ids_tours = set(data['individual_tours'][tour_col].unique())
                tour_ids_trips = set(data['individual_trips'][trip_tour_col].unique())
                
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
    """Orchestrates summary generation using modular validation summary modules."""
    
    def __init__(self, config: SummaryConfig, data_model=None, custom_summary_configs=None):
        self.config = config
        self.data_model = data_model
        self.custom_summary_configs = custom_summary_configs or []
    
    def generate_all_summaries(self, datasets: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
        """Generate all enabled summaries using modular summary functions."""
        all_summaries = {}
        
        for dataset_name, data in datasets.items():
            # Use display name if available, otherwise use dataset_name
            display_name = self.dataset_display_names.get(dataset_name, dataset_name)
            logger.info(f"\nProcessing dataset: {display_name} ({dataset_name})")
            
            # Household summaries
            if SummaryType.AUTO_OWNERSHIP in self.config.enabled_summaries:
                if 'households' in data:
                    # Get weight field from data model
                    weight_col = None
                    if hasattr(self, 'data_model') and self.data_model:
                        weight_col = self.data_model.get_weight_field('households')
                    
                    all_summaries.update(
                        household_summary.generate_all_household_summaries(
                            data['households'], display_name, weight_col
                        )
                    )
                else:
                    logger.warning(f"  ⚠ No household data for {dataset_name}")
            
            # Worker summaries
            if SummaryType.WORK_LOCATION in self.config.enabled_summaries:
                if 'persons' in data:
                    # Get weight field from data model
                    weight_col = None
                    if hasattr(self, 'data_model') and self.data_model:
                        weight_col = self.data_model.get_weight_field('persons')
                    
                    all_summaries.update(
                        worker_summary.generate_all_worker_summaries(
                            data['persons'], display_name, weight_col
                        )
                    )
                else:
                    logger.warning(f"  ⚠ No person data for {dataset_name}")
            
            # Tour summaries
            if (SummaryType.TOUR_FREQUENCY in self.config.enabled_summaries or 
                SummaryType.TOUR_MODE in self.config.enabled_summaries or 
                SummaryType.TOUR_TIME in self.config.enabled_summaries):
                if 'individual_tours' in data:
                    # Get weight field from data model
                    weight_col = None
                    if hasattr(self, 'data_model') and self.data_model:
                        weight_col = self.data_model.get_weight_field('tours')
                    
                    all_summaries.update(
                        tour_summary.generate_all_tour_summaries(
                            data['individual_tours'], display_name, weight_col
                        )
                    )
                else:
                    logger.warning(f"  ⚠ No tour data for {dataset_name}")
            
            # Trip summaries
            if SummaryType.TRIP_MODE in self.config.enabled_summaries:
                if 'individual_trips' in data:
                    # Get weight field from data model
                    weight_col = None
                    if hasattr(self, 'data_model') and self.data_model:
                        weight_col = self.data_model.get_weight_field('trips')
                    
                    all_summaries.update(
                        trip_summary.generate_all_trip_summaries(
                            data['individual_trips'], display_name, weight_col
                        )
                    )
                else:
                    logger.warning(f"  ⚠ No trip data for {dataset_name}")
            
            # Config-driven custom summaries
            if hasattr(self, 'custom_summary_configs') and self.custom_summary_configs:
                from .config_driven_summaries import generate_all_config_driven_summaries
                
                all_summaries.update(
                    generate_all_config_driven_summaries(
                        self.custom_summary_configs,
                        data,
                        display_name
                    )
                )
        
        logger.info(f"\n✓ Generated {len(all_summaries)} total summary tables")
        return all_summaries


def _combine_multi_run_summaries(summaries: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Combine summaries from multiple runs into single DataFrames.
    
    Takes summaries like:
        'auto_ownership_regional_2023_version_05': df1
        'auto_ownership_regional_2024_version_01': df2
    
    Returns:
        'auto_ownership_regional': pd.concat([df1, df2])
    
    The 'dataset' column in each df identifies the run.
    
    Strategy: Extract base name by removing dataset suffix (everything after the last underscore
    that matches a dataset pattern, or the entire suffix after finding a common pattern).
    
    Args:
        summaries: Dictionary mapping summary name to DataFrame
        
    Returns:
        Dictionary of combined summaries by base name
    """
    from collections import defaultdict
    import re
    
    # Group summaries by base name
    grouped = defaultdict(list)
    
    # Extract all unique summary names to find patterns
    all_names = list(summaries.keys())
    
    # Find base names by looking for common prefixes across dataset-suffixed names
    # Strategy: Remove everything after a dataset name pattern
    for name, df in summaries.items():
        # Try to find dataset name in the summary name
        # Dataset names typically appear at the end: "summary_name_DatasetName"
        # Split on underscores and try progressively shorter base names
        parts = name.split('_')
        
        # Start with full name, then try removing parts from the end
        base_name = name
        for i in range(len(parts), 0, -1):
            candidate = '_'.join(parts[:i])
            
            # Check if this candidate appears in multiple summaries with different suffixes
            matches = [n for n in all_names if n.startswith(candidate + '_') or n == candidate]
            
            if len(matches) > 1:
                # Found a base name that has multiple variants
                base_name = candidate
                break
        
        grouped[base_name].append(df)
    
    # Concatenate DataFrames with same base name
    result = {}
    for base_name, dfs in grouped.items():
        if len(dfs) == 1:
            result[base_name] = dfs[0]
        else:
            result[base_name] = pd.concat(dfs, ignore_index=True)
    
    return result


def save_summaries(summaries: Dict[str, pd.DataFrame], output_dir: Path, 
                  output_config: OutputConfig = None, generate_simwrapper: bool = True):
    """Save all summary tables to CSV files and optionally generate SimWrapper dashboards.
    
    Args:
        summaries: Dictionary of summary name to DataFrame
        output_dir: Directory to save output files
        output_config: Optional configuration for custom filenames and column names
        generate_simwrapper: Whether to generate SimWrapper dashboard files (default: True)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if output_config is None:
        output_config = OutputConfig()
    
    logger.info(f"Saving {len(summaries)} summary tables to {output_dir}")
    
    for summary_name, summary_df in summaries.items():
        # Apply column renaming if configured
        df_out = summary_df.copy()
        if output_config.column_renames:
            rename_dict = {old: new for old, new in output_config.column_renames.items() 
                          if old in df_out.columns}
            if rename_dict:
                df_out = df_out.rename(columns=rename_dict)
                logger.info(f"    → Renamed {len(rename_dict)} columns in {summary_name}")
        
        # Determine output filename
        filename = output_config.filename_patterns.get(summary_name, f"{summary_name}.csv")
        if not filename.endswith('.csv'):
            filename = f"{filename}.csv"
        
        output_path = output_dir / filename
        df_out.to_csv(output_path, index=False)
        logger.info(f"  ✓ Saved {filename}: {len(df_out)} rows")
    
    # Create a summary index
    index_data = []
    for summary_name, summary_df in summaries.items():
        filename = output_config.filename_patterns.get(summary_name, f"{summary_name}.csv")
        if not filename.endswith('.csv'):
            filename = f"{filename}.csv"
        
        index_data.append({
            'summary_name': summary_name,
            'filename': filename,
            'rows': len(summary_df),
            'columns': len(summary_df.columns),
            'description': f"Summary table: {summary_name}"
        })
    
    index_df = pd.DataFrame(index_data)
    index_df.to_csv(output_dir / "summary_index.csv", index=False)
    logger.info(f"  ✓ Created summary index with {len(index_data)} tables")
    
    # Generate dashboards if enabled
    if generate_simwrapper:
        logger.info("\nGenerating dashboards...")
        dashboard_dir = output_dir / "dashboard"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        
        # Combine multi-run summaries (merge summaries with same base name)
        combined_summaries = _combine_multi_run_summaries(summaries)
        logger.info(f"  ℹ Combined {len(summaries)} summaries into {len(combined_summaries)} multi-run tables")
        
        # Group combined summaries by type
        household_summaries = {k: v for k, v in combined_summaries.items() if 'household' in k.lower() or 'auto_ownership' in k.lower()}
        worker_summaries = {k: v for k, v in combined_summaries.items() if 'worker' in k.lower() or 'person' in k.lower()}
        tour_summaries = {k: v for k, v in combined_summaries.items() if 'tour' in k.lower()}
        trip_summaries = {k: v for k, v in combined_summaries.items() if 'trip' in k.lower()}
        
        # Create dashboards for each category
        if household_summaries:
            create_household_dashboard(dashboard_dir, household_summaries)
            logger.info(f"  ✓ Created household dashboard with {len(household_summaries)} summaries")
        
        if worker_summaries:
            create_worker_dashboard(dashboard_dir, worker_summaries)
            logger.info(f"  ✓ Created worker dashboard with {len(worker_summaries)} summaries")
        
        if tour_summaries:
            create_tour_dashboard(dashboard_dir, tour_summaries)
            logger.info(f"  ✓ Created tour dashboard with {len(tour_summaries)} summaries")
        
        if trip_summaries:
            create_trip_dashboard(dashboard_dir, trip_summaries)
            logger.info(f"  ✓ Created trip dashboard with {len(trip_summaries)} summaries")
        
        logger.info(f"  ✓ Dashboards saved to {dashboard_dir}")


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


def load_config_file(config_path: Path):
    """Load configuration from YAML file.
    
    Returns:
        Tuple of (RunConfig object, raw config_data dict)
    """
    with open(config_path) as f:
        config_data = yaml.safe_load(f)
    
    return RunConfig(**config_data), config_data


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
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Disable dashboard generation"
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config_data = {}
        if args.config:
            config, config_data = load_config_file(args.config)
            # Override output directory if specified on command line
            if args.output_dir:
                config.output_directory = args.output_dir
        else:
            if not args.input_dirs or not args.output_dir:
                parser.error("Either --config or both --input-dirs and --output-dir must be provided")
            config = create_default_config(args.input_dirs, args.output_dir)
        
        # Override summaries if specified
        if args.summaries:
            config.summary_config.enabled_summaries = [SummaryType(s) for s in args.summaries]
        
        logger.info(f"Starting CTRAMP validation summary generation")
        logger.info(f"Input directories: {len(config.input_directories)}")
        logger.info(f"Output directory: {config.output_directory}")
        logger.info(f"Enabled summaries: {[s.value for s in config.summary_config.enabled_summaries]}")
        
        # Initialize components
        data_loader = DataLoader(
            config.file_specs, 
            config.column_mapping, 
            binning_specs=config.binning_specs,
            aggregation_specs=config.aggregation_specs
        )
        
        # Create display name mapping for dashboards
        dataset_display_names = {
            input_dir.name: input_dir.display_name or input_dir.name
            for input_dir in config.input_directories
        }
        
        # Load custom summary configurations if present
        custom_summary_configs = config_data.get('custom_summaries', [])
        if custom_summary_configs:
            logger.info(f"Loaded {len(custom_summary_configs)} custom summary configurations")
        
        summary_generator = SummaryGenerator(
            config.summary_config, 
            data_loader.data_model,
            custom_summary_configs=custom_summary_configs
        )
        summary_generator.dataset_display_names = dataset_display_names
        
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
        
        # Generate summaries from model outputs
        summaries = summary_generator.generate_all_summaries(all_datasets)
        
        if not summaries:
            logger.warning("No summaries generated from model outputs")
        
        # Load and merge observed summaries (pre-aggregated survey/ACS data)
        if config.observed_summaries:
            logger.info(f"Loading {len(config.observed_summaries)} observed datasets...")
            for observed_config in config.observed_summaries:
                try:
                    observed_sums = data_loader.load_observed_summaries(observed_config)
                    logger.info(f"Loaded {len(observed_sums)} summaries from {observed_config.display_name}")
                    summaries.update(observed_sums)
                    
                    # Add to display name mapping for dashboards
                    dataset_display_names[observed_config.name] = observed_config.display_name
                    
                except Exception as e:
                    logger.error(f"Failed to load observed summaries from {observed_config.name}: {e}")
                    continue
        
        if not summaries:
            logger.error("No summaries available (neither model nor observed). Exiting.")
            sys.exit(1)
        
        # Save results with output configuration
        save_summaries(summaries, config.output_directory, config.output_config, 
                      generate_simwrapper=not args.no_dashboard)
        
        logger.info("✅ Validation summary generation completed successfully!")
        
        # Open SimWrapper in browser if dashboards were generated
        if not args.no_dashboard:
            simwrapper_dir = config.output_directory / "simwrapper"
            if simwrapper_dir.exists():
                logger.info("\n🌐 Opening SimWrapper in browser...")
                # Open SimWrapper with local folder
                webbrowser.open('https://simwrapper.github.io/site/')
                logger.info(f"   → In SimWrapper, click 'Add Local folder' and select:")
                logger.info(f"   → {simwrapper_dir.absolute()}")
        
    except Exception as e:
        logger.error(f"❌ Error during execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()