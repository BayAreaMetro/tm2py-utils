"""
Dashboard Output Writer

Generates dashboard YAML files and CSV data for validation summaries.
"""

import pandas as pd
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


def _check_multiple_runs(summaries: Dict[str, pd.DataFrame]) -> bool:
    """Check if summaries contain multiple dataset runs."""
    if not summaries:
        return False
    first_df = next(iter(summaries.values()))
    if 'dataset' in first_df.columns:
        return first_df['dataset'].nunique() > 1
    return False


def _create_chart_pair(writer, csv_file: str, x_col: str, count_col: str, 
                       title_base: str, has_multiple_runs: bool,
                       description: str = "", stacked: bool = False,
                       stack_col: Optional[str] = None) -> List[Dict]:
    """
    Create standardized share + total chart pair.
    
    Args:
        stack_col: Column to use for stacking (e.g., 'income_category_bin', 'tour_mode')
    
    Returns list of two panel configs: [share_chart, total_chart]
    """
    charts = []
    
    # Share chart
    panel_config = {
        'chart_type': 'bar',
        'title': f'{title_base} - Share',
        'dataset': csv_file,
        'x': x_col,
        'y': 'share',
        'description': f'Share: {description}'
    }
    if stacked and stack_col:
        panel_config['columns'] = stack_col
    if has_multiple_runs:
        panel_config['groupBy'] = 'dataset'
    charts.append(writer.create_panel(**panel_config))
    
    # Total chart
    panel_config = {
        'chart_type': 'bar',
        'title': f'{title_base} - Total',
        'dataset': csv_file,
        'x': x_col,
        'y': count_col,
        'description': f'Total: {description}'
    }
    if stacked and stack_col:
        panel_config['columns'] = stack_col
    if has_multiple_runs:
        panel_config['groupBy'] = 'dataset'
    charts.append(writer.create_panel(**panel_config))
    
    return charts


class DashboardWriter:
    """Helper class to write dashboard configs and data files."""
    
    def __init__(self, output_dir: Path):
        """
        Initialize dashboard writer.
        
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
        logger.info(f"  ✓ Wrote dashboard CSV: {filename}")
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
        Create a dashboard YAML file.
        
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
        
        logger.info(f"  ✓ Created dashboard: {yaml_filename}")
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
    Create dashboard for household summaries.
    
    Follows standardized pattern:
    - 1D: Share + Total charts, dataset as groupBy (for comparing runs)
    - 2D: Share + Total charts, secondary var stacked, dataset as groupBy
    
    Args:
        output_dir: Directory for output files
        summaries: Dictionary of combined summary DataFrames (dataset column identifies runs)
        
    Returns:
        Path to created dashboard YAML
    """
    writer = DashboardWriter(output_dir)
    
    # Write CSV files
    csv_files = {}
    for name, df in summaries.items():
        filename = f"{name}.csv"
        writer.write_csv(df, filename)
        csv_files[name] = filename
    
    # Check if we have multiple datasets
    has_multiple_runs = _check_multiple_runs(summaries)
    
    # Create dashboard layout
    layout = {
        'auto_ownership': [],
        'household_characteristics': []
    }
    
    # === AUTO OWNERSHIP CHARTS ===
    # 1D: Regional auto ownership (share + total)
    if 'auto_ownership_regional' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['auto_ownership_regional'],
            x_col='num_vehicles', count_col='households',
            title_base='Households by Vehicle Ownership',
            has_multiple_runs=has_multiple_runs,
            description='households by number of vehicles owned'
        )
        layout['auto_ownership'].extend(charts)
    
    # 2D: Auto ownership by income (share + total, stacked)
    if 'auto_ownership_by_income' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['auto_ownership_by_income'],
            x_col='num_vehicles', count_col='households',
            title_base='Auto Ownership by Income',
            has_multiple_runs=has_multiple_runs,
            description='households by vehicle ownership and income category',
            stacked=True,
            stack_col='income_category_bin'
        )
        layout['auto_ownership'].extend(charts)
    
    # === HOUSEHOLD CHARACTERISTICS ===
    # 1D: Household size (share + total)
    if 'household_size_regional' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['household_size_regional'],
            x_col='household_size', count_col='households',
            title_base='Households by Size',
            has_multiple_runs=has_multiple_runs,
            description='households by size'
        )
        layout['household_characteristics'].extend(charts)
    
    # 1D: Income distribution (share + total)
    if 'income_distribution' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['income_distribution'],
            x_col='income_category_bin', count_col='households',
            title_base='Households by Income',
            has_multiple_runs=has_multiple_runs,
            description='households by income category'
        )
        layout['household_characteristics'].extend(charts)
    
    # Create dashboard
    dashboard_path = writer.create_dashboard(
        tab_name='Households',
        title='Household Summary Statistics',
        description='Household demographics and auto ownership patterns (multi-run comparison)',
        layout=layout,
        dashboard_number=1
    )
    
    return dashboard_path


def create_worker_dashboard(
    output_dir: Path,
    summaries: Dict[str, pd.DataFrame]
) -> str:
    """
    Create dashboard for worker summaries.
    
    Follows standardized pattern:
    - 1D: Share + Total charts for each variable
    - 2D: Share + Total charts with stacking
    
    Args:
        output_dir: Directory for output files
        summaries: Dictionary of combined summary DataFrames
        
    Returns:
        Path to created dashboard YAML
    """
    writer = DashboardWriter(output_dir)
    
    # Write CSV files
    csv_files = {}
    for name, df in summaries.items():
        filename = f"{name}.csv"
        writer.write_csv(df, filename)
        csv_files[name] = filename
    
    has_multiple_runs = _check_multiple_runs(summaries)
    
    # Create dashboard layout
    layout = {
        'worker_overview': [],
        'demographics': []
    }
    
    # === WORKER OVERVIEW ===
    # 1D: Worker type (full-time vs part-time)
    if 'worker_type' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['worker_type'],
            x_col='worker_type', count_col='workers',
            title_base='Workers by Type',
            has_multiple_runs=has_multiple_runs,
            description='full-time vs part-time workers'
        )
        layout['worker_overview'].extend(charts)
    
    # 1D: Work from home / telecommute
    if 'work_from_home' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['work_from_home'],
            x_col='telecommute_frequency', count_col='workers',
            title_base='Telecommute Frequency',
            has_multiple_runs=has_multiple_runs,
            description='work from home patterns'
        )
        layout['worker_overview'].extend(charts)
    
    # === DEMOGRAPHICS ===
    # 1D: Worker age
    if 'worker_age' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['worker_age'],
            x_col='age_group', count_col='workers',
            title_base='Workers by Age',
            has_multiple_runs=has_multiple_runs,
            description='worker age distribution'
        )
        layout['demographics'].extend(charts)
    
    # 1D: Worker gender
    if 'worker_gender' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['worker_gender'],
            x_col='gender', count_col='workers',
            title_base='Workers by Gender',
            has_multiple_runs=has_multiple_runs,
            description='worker gender distribution'
        )
        layout['demographics'].extend(charts)
    
    # 1D: Worker income
    if 'worker_income' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['worker_income'],
            x_col='income_category', count_col='workers',
            title_base='Workers by Income',
            has_multiple_runs=has_multiple_runs,
            description='worker income distribution'
        )
        layout['demographics'].extend(charts)
    
    # Create dashboard
    dashboard_path = writer.create_dashboard(
        tab_name='Workers',
        title='Worker and Employment Statistics',
        description='Worker demographics and employment patterns (multi-run comparison)',
        layout=layout,
        dashboard_number=2
    )
    
    return dashboard_path


def create_tour_dashboard(
    output_dir: Path,
    summaries: Dict[str, pd.DataFrame]
) -> str:
    """
    Create dashboard for tour summaries.
    
    Follows standardized pattern:
    - 1D: Share + Total charts for each variable
    - 2D: Share + Total charts with stacking
    
    Args:
        output_dir: Directory for output files
        summaries: Dictionary of combined summary DataFrames
        
    Returns:
        Path to created dashboard YAML
    """
    writer = DashboardWriter(output_dir)
    
    # Write CSV files
    csv_files = {}
    for name, df in summaries.items():
        filename = f"{name}.csv"
        writer.write_csv(df, filename)
        csv_files[name] = filename
    
    has_multiple_runs = _check_multiple_runs(summaries)
    
    # Create dashboard layout
    layout = {
        'tour_patterns': [],
        'mode_choice': []
    }
    
    # === TOUR PATTERNS ===
    # 1D: Tour frequency by purpose
    if 'tour_frequency_by_purpose' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['tour_frequency_by_purpose'],
            x_col='tour_purpose', count_col='tours',
            title_base='Tours by Purpose',
            has_multiple_runs=has_multiple_runs,
            description='tours by purpose'
        )
        layout['tour_patterns'].extend(charts)
    
    # 1D: Tour mode choice
    if 'tour_mode_choice' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['tour_mode_choice'],
            x_col='tour_mode', count_col='tours',
            title_base='Tours by Mode',
            has_multiple_runs=has_multiple_runs,
            description='tour mode distribution'
        )
        layout['mode_choice'].extend(charts)
    
    # 2D: Mode by purpose
    if 'tour_mode_by_purpose' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['tour_mode_by_purpose'],
            x_col='tour_purpose', count_col='tours',
            title_base='Tour Mode by Purpose',
            has_multiple_runs=has_multiple_runs,
            description='mode choice by tour purpose',
            stacked=True,
            stack_col='tour_mode'
        )
        layout['mode_choice'].extend(charts)
    
    # 1D: Tour distance (binned)
    if 'tour_distance' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['tour_distance'],
            x_col='tour_distance_bin', count_col='tours',
            title_base='Tours by Distance',
            has_multiple_runs=has_multiple_runs,
            description='tour distance distribution'
        )
        layout['tour_patterns'].extend(charts)
    
    # 1D: Tour duration (binned)
    if 'tour_duration' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['tour_duration'],
            x_col='tour_duration_bin', count_col='tours',
            title_base='Tours by Duration',
            has_multiple_runs=has_multiple_runs,
            description='tour duration distribution'
        )
        layout['tour_patterns'].extend(charts)
    
    # Create dashboard
    dashboard_path = writer.create_dashboard(
        tab_name='Tours',
        title='Tour Pattern Statistics',
        description='Tour frequency, mode choice, distance, and duration (multi-run comparison)',
        layout=layout,
        dashboard_number=3
    )
    
    return dashboard_path


def create_trip_dashboard(
    output_dir: Path,
    summaries: Dict[str, pd.DataFrame]
) -> str:
    """
    Create dashboard for trip summaries.
    
    Follows standardized pattern:
    - 1D: Share + Total charts for each variable
    - 2D: Share + Total charts with stacking
    
    Args:
        output_dir: Directory for output files
        summaries: Dictionary of combined summary DataFrames
        
    Returns:
        Path to created dashboard YAML
    """
    writer = DashboardWriter(output_dir)
    
    # Write CSV files
    csv_files = {}
    for name, df in summaries.items():
        filename = f"{name}.csv"
        writer.write_csv(df, filename)
        csv_files[name] = filename
    
    has_multiple_runs = _check_multiple_runs(summaries)
    
    # Create dashboard layout
    layout = {
        'trip_patterns': [],
        'mode_purpose': []
    }
    
    # === TRIP PATTERNS ===
    # 1D: Trip mode choice
    if 'trip_mode_choice' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['trip_mode_choice'],
            x_col='trip_mode', count_col='trips',
            title_base='Trips by Mode',
            has_multiple_runs=has_multiple_runs,
            description='trip mode distribution'
        )
        layout['trip_patterns'].extend(charts)
    
    # 1D: Trip purpose
    if 'trip_purpose' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['trip_purpose'],
            x_col='destination_purpose', count_col='trips',
            title_base='Trips by Purpose',
            has_multiple_runs=has_multiple_runs,
            description='trip purpose distribution'
        )
        layout['trip_patterns'].extend(charts)
    
    # 2D: Mode by purpose
    if 'trip_mode_by_purpose' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['trip_mode_by_purpose'],
            x_col='destination_purpose', count_col='trips',
            title_base='Trip Mode by Purpose',
            has_multiple_runs=has_multiple_runs,
            description='mode choice by trip purpose',
            stacked=True,
            stack_col='trip_mode'
        )
        layout['mode_purpose'].extend(charts)
    
    # 1D: Trip distance (binned)
    if 'trip_distance' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['trip_distance'],
            x_col='trip_distance_bin', count_col='trips',
            title_base='Trips by Distance',
            has_multiple_runs=has_multiple_runs,
            description='trip distance distribution'
        )
        layout['trip_patterns'].extend(charts)
    
    # 1D: Trip duration (binned)
    if 'trip_duration' in csv_files:
        charts = _create_chart_pair(
            writer, csv_files['trip_duration'],
            x_col='trip_duration_bin', count_col='trips',
            title_base='Trips by Duration',
            has_multiple_runs=has_multiple_runs,
            description='trip duration distribution'
        )
        layout['trip_patterns'].extend(charts)
    
    # Create dashboard
    dashboard_path = writer.create_dashboard(
        tab_name='Trips',
        title='Trip Pattern Statistics',
        description='Trip mode choice, purpose, distance, and duration (multi-run comparison)',
        layout=layout,
        dashboard_number=4
    )
    
    return dashboard_path
