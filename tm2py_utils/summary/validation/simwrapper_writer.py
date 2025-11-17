"""
SimWrapper Output Writer

Generates SimWrapper-compatible dashboard YAML files and CSV data
for validation summaries.
"""

import pandas as pd
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class SimWrapperWriter:
    """Helper class to write SimWrapper dashboard configs and data files."""
    
    def __init__(self, output_dir: Path):
        """
        Initialize SimWrapper writer.
        
        Args:
            output_dir: Directory where dashboard YAML and CSV files will be written
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def write_csv(self, df: pd.DataFrame, filename: str) -> str:
        """
        Write dataframe to CSV in output directory.
        
        Args:
            df: DataFrame to write
            filename: Name of CSV file
            
        Returns:
            Relative path to CSV file
        """
        csv_path = self.output_dir / filename
        df.to_csv(csv_path, index=False)
        logger.info(f"  ✓ Wrote SimWrapper CSV: {filename}")
        return filename  # Return relative path for YAML
    
    def create_dashboard(
        self,
        tab_name: str,
        title: str,
        description: str,
        layout: Dict[str, List[Dict[str, Any]]],
        dashboard_number: int = 1
    ) -> str:
        """
        Create a SimWrapper dashboard YAML file.
        
        Args:
            tab_name: Name of the dashboard tab
            title: Dashboard title
            description: Dashboard description
            layout: Dictionary of row names to list of panel configs
            dashboard_number: Dashboard file number for ordering tabs
            
        Returns:
            Path to created YAML file
        """
        dashboard_config = {
            'header': {
                'tab': tab_name,
                'title': title,
                'description': description
            },
            'layout': layout
        }
        
        yaml_filename = f"dashboard-{dashboard_number}-{tab_name.lower().replace(' ', '-')}.yaml"
        yaml_path = self.output_dir / yaml_filename
        
        with open(yaml_path, 'w') as f:
            yaml.dump(dashboard_config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"  ✓ Created SimWrapper dashboard: {yaml_filename}")
        return str(yaml_path)
    
    def create_panel(
        self,
        chart_type: str,
        title: str,
        dataset: str,
        x: Optional[str] = None,
        y: Optional[str] = None,
        columns: Optional[List[str]] = None,
        description: Optional[str] = None,
        stacked: bool = False,
        height: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a panel configuration for dashboard layout.
        
        Args:
            chart_type: Type of chart ('pie', 'bar', 'line', 'table')
            title: Panel title
            dataset: CSV filename or glob pattern
            x: X-axis column name
            y: Y-axis column name (optional)
            columns: Specific columns to plot
            description: Panel description
            stacked: Whether to stack bars/areas
            height: Panel height (default varies by type)
            **kwargs: Additional props
            
        Returns:
            Panel configuration dictionary
        """
        panel = {
            'type': chart_type,
            'title': title,
            'props': {
                'dataset': dataset
            }
        }
        
        if description:
            panel['description'] = description
            
        if height:
            panel['height'] = height
        
        # Add chart-specific props
        if x:
            panel['props']['x'] = x
        if y:
            panel['props']['y'] = y
        if columns:
            panel['props']['columns'] = columns
        if stacked:
            panel['props']['stacked'] = stacked
            
        # Add any additional props
        panel['props'].update(kwargs)
        
        return panel


def create_household_dashboard(
    output_dir: Path,
    summaries: Dict[str, pd.DataFrame]
) -> str:
    """
    Create SimWrapper dashboard for household summaries.
    
    Args:
        output_dir: Directory for output files
        summaries: Dictionary of summary DataFrames
        
    Returns:
        Path to created dashboard YAML
    """
    writer = SimWrapperWriter(output_dir)
    
    # Write CSV files
    csv_files = {}
    for name, df in summaries.items():
        filename = f"{name}.csv"
        writer.write_csv(df, filename)
        csv_files[name] = filename
    
    # Create dashboard layout
    layout = {
        'auto_ownership': [],
        'household_characteristics': []
    }
    
    # Auto ownership charts
    for name, csv_file in csv_files.items():
        if 'auto_ownership_regional' in name:
            layout['auto_ownership'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Auto Ownership - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='num_vehicles',
                    y='households',
                    description='Household vehicle ownership distribution'
                )
            )
        elif 'auto_ownership_by_income' in name:
            layout['auto_ownership'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Auto Ownership by Income - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='income_category',
                    y='households',
                    description='Vehicle ownership by income category',
                    stacked=True
                )
            )
    
    # Household size and income charts
    for name, csv_file in csv_files.items():
        if 'household_size' in name:
            layout['household_characteristics'].append(
                writer.create_panel(
                    chart_type='pie',
                    title=f'Household Size - {name.split("_")[-1]}',
                    dataset=csv_file,
                    description='Distribution of household sizes'
                )
            )
        elif 'income_distribution' in name:
            layout['household_characteristics'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Income Distribution - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='income_category',
                    y='households',
                    description='Household income distribution'
                )
            )
    
    # Create dashboard
    dashboard_path = writer.create_dashboard(
        tab_name='Households',
        title='Household Summary Statistics',
        description='Household demographics and auto ownership patterns',
        layout=layout,
        dashboard_number=1
    )
    
    return dashboard_path


def create_worker_dashboard(
    output_dir: Path,
    summaries: Dict[str, pd.DataFrame]
) -> str:
    """
    Create SimWrapper dashboard for worker summaries.
    
    Args:
        output_dir: Directory for output files
        summaries: Dictionary of summary DataFrames
        
    Returns:
        Path to created dashboard YAML
    """
    writer = SimWrapperWriter(output_dir)
    
    # Write CSV files
    csv_files = {}
    for name, df in summaries.items():
        filename = f"{name}.csv"
        writer.write_csv(df, filename)
        csv_files[name] = filename
    
    # Create dashboard layout
    layout = {
        'worker_overview': [],
        'demographics': []
    }
    
    # Worker type and location charts
    for name, csv_file in csv_files.items():
        if 'worker_type' in name:
            layout['worker_overview'].append(
                writer.create_panel(
                    chart_type='pie',
                    title=f'Worker Types - {name.split("_")[-1]}',
                    dataset=csv_file,
                    description='Full-time vs part-time workers'
                )
            )
        elif 'work_from_home' in name or 'telecommute' in name:
            layout['worker_overview'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Telecommute Frequency - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='telecommute_frequency',
                    y='workers',
                    description='Work from home patterns'
                )
            )
    
    # Demographics charts
    for name, csv_file in csv_files.items():
        if 'worker_age' in name:
            layout['demographics'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Worker Age Distribution - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='age_group',
                    y='workers'
                )
            )
        elif 'worker_gender' in name:
            layout['demographics'].append(
                writer.create_panel(
                    chart_type='pie',
                    title=f'Worker Gender - {name.split("_")[-1]}',
                    dataset=csv_file
                )
            )
        elif 'worker_income' in name:
            layout['demographics'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Worker Income - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='income_category',
                    y='workers'
                )
            )
    
    # Create dashboard
    dashboard_path = writer.create_dashboard(
        tab_name='Workers',
        title='Worker and Employment Statistics',
        description='Worker demographics and commute patterns',
        layout=layout,
        dashboard_number=2
    )
    
    return dashboard_path


def create_tour_dashboard(
    output_dir: Path,
    summaries: Dict[str, pd.DataFrame]
) -> str:
    """
    Create SimWrapper dashboard for tour summaries.
    
    Args:
        output_dir: Directory for output files
        summaries: Dictionary of summary DataFrames
        
    Returns:
        Path to created dashboard YAML
    """
    writer = SimWrapperWriter(output_dir)
    
    # Write CSV files
    csv_files = {}
    for name, df in summaries.items():
        filename = f"{name}.csv"
        writer.write_csv(df, filename)
        csv_files[name] = filename
    
    # Create dashboard layout
    layout = {
        'tour_patterns': [],
        'mode_choice': []
    }
    
    # Tour frequency and mode charts
    for name, csv_file in csv_files.items():
        if 'tour_frequency_by_purpose' in name:
            layout['tour_patterns'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Tour Frequency by Purpose - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='tour_purpose',
                    y='tours'
                )
            )
        elif 'tour_mode_choice' in name:
            layout['mode_choice'].append(
                writer.create_panel(
                    chart_type='pie',
                    title=f'Tour Mode Share - {name.split("_")[-1]}',
                    dataset=csv_file,
                    description='Distribution of tour modes'
                )
            )
        elif 'tour_mode_by_purpose' in name:
            layout['mode_choice'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Mode by Purpose - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='tour_purpose',
                    y='tours',
                    stacked=True,
                    description='Mode choice by tour purpose'
                )
            )
    
    # Create dashboard
    dashboard_path = writer.create_dashboard(
        tab_name='Tours',
        title='Tour Pattern Statistics',
        description='Tour frequency, mode choice, and timing',
        layout=layout,
        dashboard_number=3
    )
    
    return dashboard_path


def create_trip_dashboard(
    output_dir: Path,
    summaries: Dict[str, pd.DataFrame]
) -> str:
    """
    Create SimWrapper dashboard for trip summaries.
    
    Args:
        output_dir: Directory for output files
        summaries: Dictionary of summary DataFrames
        
    Returns:
        Path to created dashboard YAML
    """
    writer = SimWrapperWriter(output_dir)
    
    # Write CSV files
    csv_files = {}
    for name, df in summaries.items():
        filename = f"{name}.csv"
        writer.write_csv(df, filename)
        csv_files[name] = filename
    
    # Create dashboard layout
    layout = {
        'trip_patterns': [],
        'mode_purpose': []
    }
    
    # Trip mode and purpose charts
    for name, csv_file in csv_files.items():
        if 'trip_mode_choice' in name:
            layout['trip_patterns'].append(
                writer.create_panel(
                    chart_type='pie',
                    title=f'Trip Mode Share - {name.split("_")[-1]}',
                    dataset=csv_file,
                    description='Distribution of trip modes'
                )
            )
        elif 'trip_purpose' in name and 'by' not in name:
            layout['trip_patterns'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Trip Purpose - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='destination_purpose',
                    y='trips'
                )
            )
        elif 'trip_mode_by_purpose' in name:
            layout['mode_purpose'].append(
                writer.create_panel(
                    chart_type='bar',
                    title=f'Mode by Purpose - {name.split("_")[-1]}',
                    dataset=csv_file,
                    x='destination_purpose',
                    y='trips',
                    stacked=True
                )
            )
    
    # Create dashboard
    dashboard_path = writer.create_dashboard(
        tab_name='Trips',
        title='Trip Pattern Statistics',
        description='Trip mode choice, purpose, and timing',
        layout=layout,
        dashboard_number=4
    )
    
    return dashboard_path
