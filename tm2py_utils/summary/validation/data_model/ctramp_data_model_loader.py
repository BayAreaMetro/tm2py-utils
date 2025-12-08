"""
Data Model Loader - Separates data schema from analysis code

This module loads the data model configuration from YAML and provides
a clean interface for the analysis code to access schema definitions,
mappings, and validations without hardcoding any column names.
"""

import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)


class ColumnSchema(BaseModel):
    """Schema definition for a single data table."""
    file_pattern: str
    required_columns: Dict[str, str]  # internal_name -> actual_csv_name
    optional_columns: Dict[str, str]  # internal_name -> actual_csv_name
    
    @property
    def all_columns(self) -> Dict[str, str]:
        """Get all columns (required + optional)."""
        return {**self.required_columns, **self.optional_columns}
    
    @property
    def internal_names(self) -> Set[str]:
        """Get all internal column names."""
        return set(self.required_columns.keys()) | set(self.optional_columns.keys())
    
    @property
    def csv_names(self) -> Set[str]:
        """Get all CSV column names."""
        return set(self.required_columns.values()) | set(self.optional_columns.values())
    
    def get_csv_name(self, internal_name: str) -> Optional[str]:
        """Get CSV column name for an internal name."""
        return self.all_columns.get(internal_name)
    
    def get_internal_name(self, csv_name: str) -> Optional[str]:
        """Get internal name for a CSV column name."""
        reverse_map = {v: k for k, v in self.all_columns.items()}
        return reverse_map.get(csv_name)
    
    def get_mapping_dict(self) -> Dict[str, str]:
        """Get mapping dict for pandas rename (csv_name -> internal_name)."""
        return {v: k for k, v in self.all_columns.items()}


class SummaryDefinition(BaseModel):
    """Definition of a summary analysis."""
    description: str
    input_tables: List[str]
    required_columns: Dict[str, List[str]]  # table_name -> [internal_column_names]
    optional_columns: Dict[str, List[str]] = Field(default_factory=dict)
    geographic_levels: List[str]
    output_columns: List[str]
    
    def get_all_required_columns(self, table_name: str) -> List[str]:
        """Get all required columns for a table."""
        return self.required_columns.get(table_name, [])
    
    def get_all_optional_columns(self, table_name: str) -> List[str]:
        """Get all optional columns for a table."""
        return self.optional_columns.get(table_name, [])


class ValueMapping(BaseModel):
    """Mapping for categorical values."""
    type: str  # categorical, numeric, text
    values: Dict[Any, str] = Field(default_factory=dict)  # code -> label
    text_values: List[str] = Field(default_factory=list)  # Valid text values
    
    def get_label(self, code: Any) -> str:
        """Get label for a code."""
        if code in self.values:
            return self.values[code]
        if str(code) in self.text_values:
            return str(code)
        return f"Unknown ({code})"
    
    def get_all_labels(self) -> List[str]:
        """Get all valid labels."""
        return list(self.values.values()) + self.text_values


class DataModel:
    """Complete data model loaded from YAML configuration."""
    
    def __init__(self, config_path: Path):
        """Load data model from YAML file."""
        self.config_path = config_path
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Load schemas
        self._load_input_schema()
        self._load_geography_lookup_config()
        self._load_summary_definitions()
        self._load_value_mappings()
        self._load_aggregation_specs()
        self._load_weight_fields()
        self._load_output_configuration()
        
        logger.info(f"✓ Loaded data model from {config_path}")
    
    def _load_input_schema(self):
        """Load input schema definitions."""
        input_schema = self.config.get('input_schema', {})
        self.schemas = {}
        
        for table_name, table_config in input_schema.items():
            columns_config = table_config.get('columns', {})
            required = columns_config.get('required', {})
            optional = columns_config.get('optional', {})
            
            self.schemas[table_name] = ColumnSchema(
                file_pattern=table_config.get('file_pattern', f"{table_name}.csv"),
                required_columns=required,
                optional_columns=optional
            )
            
            logger.debug(f"  Loaded schema for {table_name}: "
                        f"{len(required)} required, {len(optional)} optional columns")
    
    def _load_geography_lookup_config(self):
        """Load geography lookup table configuration."""
        input_schema = self.config.get('input_schema', {})
        geo_config = input_schema.get('geography_lookup', {})
        
        self.geography_lookup_config = {
            'file_path': geo_config.get('file_path'),
            'columns': geo_config.get('columns', {})
        }
        
        # Cache for loaded geography data
        self._geography_df = None
        
        if self.geography_lookup_config['file_path']:
            logger.debug(f"  Configured geography lookup: {self.geography_lookup_config['file_path']}")
    
    def _load_summary_definitions(self):
        """Load summary definitions."""
        summary_defs = self.config.get('summary_definitions', {})
        self.summaries = {}
        
        for summary_name, summary_config in summary_defs.items():
            self.summaries[summary_name] = SummaryDefinition(**summary_config)
            logger.debug(f"  Loaded summary definition: {summary_name}")
    
    def _load_value_mappings(self):
        """Load value mappings for categorical variables."""
        value_mappings = self.config.get('value_mappings', {})
        self.value_mappings = {}
        
        for field_name, mapping_config in value_mappings.items():
            self.value_mappings[field_name] = ValueMapping(**mapping_config)
            logger.debug(f"  Loaded value mapping: {field_name}")
    
    def _load_aggregation_specs(self):
        """Load aggregation specifications for grouping categorical variables."""
        aggregation_specs = self.config.get('aggregation_specs', {})
        self.aggregation_specs = {}
        
        for spec_name, spec_config in aggregation_specs.items():
            # Convert to format expected by run_all.py AggregationSpec
            self.aggregation_specs[spec_name] = {
                'mapping': spec_config.get('mapping', {}),
                'apply_to': spec_config.get('apply_to', [])
            }
            logger.debug(f"  Loaded aggregation spec: {spec_name} "
                        f"(applies to {len(spec_config.get('apply_to', []))} columns)")
    
    def _load_weight_fields(self):
        """Load weight field definitions for each table."""
        weight_config = self.config.get('weight_fields', {})
        self.weight_fields = {}
        
        for table_name, weight_info in weight_config.items():
            self.weight_fields[table_name] = {
                'field': weight_info.get('field'),
                'description': weight_info.get('description', ''),
                'calculate_weighted': weight_info.get('calculate_weighted', True),
                'default_value': weight_info.get('default_value', 1.0),
                'invert': weight_info.get('invert', False)  # True if expansion = 1/value
            }
            invert_str = " (inverted)" if weight_info.get('invert') else ""
            logger.debug(f"  Loaded weight field for {table_name}: {weight_info.get('field')}{invert_str}")
    
    def _load_output_configuration(self):
        """Load output configuration."""
        output_config = self.config.get('output_configuration', {})
        self.output_filenames = output_config.get('filenames', {})
        self.output_column_renames = output_config.get('column_renames', {})
    
    # Schema access methods
    def get_schema(self, table_name: str) -> Optional[ColumnSchema]:
        """Get schema for a table."""
        return self.schemas.get(table_name)
    
    def get_file_pattern(self, table_name: str) -> str:
        """Get file pattern for a table."""
        schema = self.get_schema(table_name)
        return schema.file_pattern if schema else f"{table_name}.csv"
    
    def get_column_mapping(self, table_name: str) -> Dict[str, str]:
        """Get column mapping for a table (csv_name -> internal_name)."""
        schema = self.get_schema(table_name)
        return schema.get_mapping_dict() if schema else {}
    
    def get_required_columns(self, table_name: str) -> Set[str]:
        """Get required internal column names for a table."""
        schema = self.get_schema(table_name)
        if not schema:
            return set()
        return set(schema.required_columns.keys())
    
    # Summary access methods
    def get_summary(self, summary_name: str) -> Optional[SummaryDefinition]:
        """Get summary definition."""
        return self.summaries.get(summary_name)
    
    def get_summary_required_columns(self, summary_name: str, table_name: str) -> List[str]:
        """Get required columns for a summary on a specific table."""
        summary = self.get_summary(summary_name)
        if not summary:
            return []
        return summary.get_all_required_columns(table_name)
    
    def list_summaries(self) -> List[str]:
        """List all available summaries."""
        return list(self.summaries.keys())
    
    # Value mapping methods
    def get_value_mapping(self, field_name: str) -> Optional[ValueMapping]:
        """Get value mapping for a field."""
        return self.value_mappings.get(field_name)
    
    def map_value(self, field_name: str, code: Any) -> str:
        """Map a code to its label."""
        mapping = self.get_value_mapping(field_name)
        if not mapping:
            return str(code)
        return mapping.get_label(code)
    
    # Weight field methods
    def get_weight_field(self, table_name: str) -> Optional[str]:
        """
        Get weight field name for a table.
        
        Args:
            table_name: Name of the table (households, persons, tours, trips)
        
        Returns:
            Weight field name or None if not configured
        """
        weight_info = self.weight_fields.get(table_name, {})
        return weight_info.get('field')
    
    def has_weights(self, table_name: str) -> bool:
        """Check if table has weight field configured."""
        return self.get_weight_field(table_name) is not None
    
    # Geography methods
    def load_geography_lookup(self, workspace_root: Optional[Path] = None) -> Optional[pd.DataFrame]:
        """
        Load geography lookup table (MAZ to county, district, etc.).
        
        Args:
            workspace_root: Root directory for relative paths. If None, uses config_path parent.
        
        Returns:
            DataFrame with geography lookup data, or None if not configured
        """
        if self._geography_df is not None:
            return self._geography_df
        
        file_path = self.geography_lookup_config.get('file_path')
        if not file_path:
            logger.debug("No geography lookup configured")
            return None
        
        # Resolve path relative to workspace root
        if workspace_root is None:
            # Try to find workspace root by going up from config file
            workspace_root = self.config_path.parent.parent.parent.parent.parent
        
        full_path = workspace_root / file_path
        
        if not full_path.exists():
            logger.warning(f"Geography lookup file not found: {full_path}")
            return None
        
        try:
            # Load only needed columns for efficiency
            columns_config = self.geography_lookup_config.get('columns', {})
            usecols = list(columns_config.values()) if columns_config else None
            
            self._geography_df = pd.read_csv(full_path, usecols=usecols)
            
            # Rename to internal names
            if columns_config:
                rename_map = {v: k for k, v in columns_config.items()}
                self._geography_df = self._geography_df.rename(columns=rename_map)
            
            logger.info(f"  ✓ Loaded geography lookup: {len(self._geography_df)} MAZs")
            return self._geography_df
            
        except Exception as e:
            logger.error(f"Error loading geography lookup: {e}")
            return None
    
    def join_geography(self, df: pd.DataFrame, join_col: str = 'home_mgra', 
                       geography_cols: Optional[List[str]] = None,
                       workspace_root: Optional[Path] = None) -> pd.DataFrame:
        """
        Join geography lookup data to a DataFrame.
        
        Args:
            df: DataFrame to join geography to
            join_col: Column in df to join on (default: 'home_mgra')
            geography_cols: List of geography columns to add (default: ['county_name', 'district_name'])
            workspace_root: Root directory for relative paths
            
        Returns:
            DataFrame with geography columns added
        """
        geo_df = self.load_geography_lookup(workspace_root)
        
        if geo_df is None:
            logger.warning("Cannot join geography - lookup table not available")
            return df
        
        if join_col not in df.columns:
            logger.warning(f"Cannot join geography - column '{join_col}' not in DataFrame")
            return df
        
        # Default geography columns to add
        if geography_cols is None:
            geography_cols = ['county_name', 'district_name']
        
        # Filter to columns that exist in geo_df
        available_cols = [c for c in geography_cols if c in geo_df.columns]
        if not available_cols:
            logger.warning(f"No requested geography columns found in lookup: {geography_cols}")
            return df
        
        # Prepare join DataFrame (maz_node + requested geography columns)
        if 'maz_node' not in geo_df.columns:
            logger.warning("Geography lookup missing 'maz_node' column")
            return df
        
        join_df = geo_df[['maz_node'] + available_cols].drop_duplicates()
        
        # Perform left join
        result = df.merge(join_df, left_on=join_col, right_on='maz_node', how='left')
        
        # Drop the duplicate maz_node column if it was added
        if 'maz_node' in result.columns and 'maz_node' != join_col:
            result = result.drop(columns=['maz_node'])
        
        # Log join stats
        matched = result[available_cols[0]].notna().sum()
        total = len(result)
        logger.info(f"  ✓ Joined geography: {matched}/{total} records matched ({matched/total*100:.1f}%)")
        
        return result
    
    def should_calculate_weighted(self, table_name: str) -> bool:
        """Check if weighted calculations should be performed for this table."""
        weight_info = self.weight_fields.get(table_name, {})
        return weight_info.get('calculate_weighted', True)
    
    def get_weight_default(self, table_name: str) -> float:
        """Get default weight value if weight field is missing."""
        weight_info = self.weight_fields.get(table_name, {})
        return weight_info.get('default_value', 1.0)
    
    def ensure_weight_column(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """
        Ensure dataframe has a weight column, adding default if missing.
        
        Args:
            df: DataFrame to check
            table_name: Name of the table
        
        Returns:
            DataFrame with weight column
        """
        weight_field = self.get_weight_field(table_name)
        
        if weight_field is None:
            # No weight configured - add default weight column
            df = df.copy()
            df['_weight'] = self.get_weight_default(table_name)
            logger.debug(f"No weight field for {table_name}, using default weight=1.0")
            return df
        
        if weight_field not in df.columns:
            # Weight field configured but missing - add default
            df = df.copy()
            default = self.get_weight_default(table_name)
            df[weight_field] = default
            logger.warning(f"Weight field '{weight_field}' missing in {table_name}, using default={default}")
        
        return df
    
    # Output configuration methods
    def get_output_filename(self, summary_name: str, default: str) -> str:
        """Get output filename for a summary."""
        return self.output_filenames.get(summary_name, default)
    
    def rename_output_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns in output dataframe."""
        if not self.output_column_renames:
            return df
        
        # Only rename columns that exist
        rename_map = {k: v for k, v in self.output_column_renames.items() 
                     if k in df.columns}
        
        if rename_map:
            logger.debug(f"Renaming output columns: {rename_map}")
            return df.rename(columns=rename_map)
        
        return df
    
    # Validation methods
    def validate_dataframe(self, df: pd.DataFrame, table_name: str) -> Tuple[bool, List[str]]:
        """
        Validate that a dataframe has required columns.
        
        Returns:
            (is_valid, missing_columns)
        """
        schema = self.get_schema(table_name)
        if not schema:
            logger.warning(f"No schema defined for table: {table_name}")
            return True, []
        
        required_internal = set(schema.required_columns.keys())
        present_columns = set(df.columns)
        missing = required_internal - present_columns
        
        if missing:
            return False, list(missing)
        
        return True, []
    
    def apply_column_mapping(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """
        Apply column mapping to convert CSV columns to internal names.
        Also applies weight transformations if configured (e.g., inversion).
        
        This should be called immediately after loading CSV data.
        """
        mapping = self.get_column_mapping(table_name)
        if not mapping:
            logger.debug(f"No column mapping for {table_name}")
            return df
        
        # Only rename columns that exist in the dataframe
        rename_map = {k: v for k, v in mapping.items() if k in df.columns}
        
        if rename_map:
            logger.info(f"Applying column mapping for {table_name}: {len(rename_map)} columns")
            logger.debug(f"  Mapping: {rename_map}")
            df = df.rename(columns=rename_map)
        
        # Apply weight field transformation if configured
        weight_info = self.weight_fields.get(table_name, {})
        weight_field = weight_info.get('field')
        should_invert = weight_info.get('invert', False)
        
        if should_invert and weight_field and weight_field in df.columns:
            # Invert the weight field (expansion factor = 1 / sample_rate)
            logger.info(f"Inverting {weight_field} for {table_name} (expansion = 1/sample_rate)")
            df[weight_field] = 1.0 / df[weight_field]
            # Handle division by zero or invalid values
            df[weight_field] = df[weight_field].replace([float('inf'), -float('inf')], 1.0)
            df[weight_field] = df[weight_field].fillna(1.0)
        
        return df
    
    def get_internal_column_name(self, table_name: str, csv_column: str) -> str:
        """
        Get internal column name for a CSV column.
        Returns original name if no mapping exists.
        """
        mapping = self.get_column_mapping(table_name)
        return mapping.get(csv_column, csv_column)


def load_data_model(config_path: Optional[Path] = None) -> DataModel:
    """
    Load data model from configuration file.
    
    Args:
        config_path: Path to ctramp_data_model.yaml. If None, looks in default locations.
    
    Returns:
        DataModel instance
    """
    if config_path is None:
        # Try default locations
        search_paths = [
            Path(__file__).parent / 'ctramp_data_model.yaml',
            Path.cwd() / 'ctramp_data_model.yaml',
            Path.cwd() / 'config' / 'ctramp_data_model.yaml',
        ]
        
        for path in search_paths:
            if path.exists():
                config_path = path
                break
        
        if config_path is None:
            raise FileNotFoundError(
                f"Could not find ctramp_data_model.yaml in any of: {search_paths}"
            )
    
    return DataModel(config_path)
