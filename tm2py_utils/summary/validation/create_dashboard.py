#!/usr/bin/env python3
"""
Dashboard Generator

Creates HTML dashboards from analysis results using Plotly.
Reads config files and output CSVs to generate interactive visualizations.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from pathlib import Path
import yaml
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DashboardGenerator:
    """Generate HTML dashboards from analysis results."""
    
    def __init__(self, config_path: Path, results_dir: Path, output_dir: Path):
        self.config_path = config_path
        self.results_dir = results_dir
        self.output_dir = output_dir
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """Load configuration file."""
        logger.info(f"Loading config from {self.config_path}")
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def create_dashboard(self):
        """Generate complete dashboard HTML file."""
        logger.info("Creating dashboard...")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load all analysis results
        data = self._load_results()
        
        if not data:
            logger.error("No data loaded, cannot create dashboard")
            return None
        
        # Create visualizations
        figs = []
        
        # 1. Regional comparison bar chart
        if 'regional' in data:
            fig1 = self._create_regional_comparison(data['regional'])
            if fig1:
                figs.append(fig1)
        
        # 2. Person type breakdown
        if 'by_person_type' in data:
            fig2 = self._create_person_type_breakdown(data['by_person_type'])
            if fig2:
                figs.append(fig2)
        
        # 3. Summary statistics table
        if 'regional' in data:
            fig3 = self._create_summary_table(data['regional'])
            if fig3:
                figs.append(fig3)
        
        # Generate HTML
        html_path = self.output_dir / "dashboard.html"
        self._generate_html(figs, html_path)
        
        logger.info(f"✅ Dashboard created: {html_path}")
        return html_path
    
    def _load_results(self) -> dict:
        """Load all CSV results from analysis directories."""
        data = {}
        
        # Find all analysis result directories
        result_dirs = [d for d in self.results_dir.glob("analysis_results_*") if d.is_dir()]
        
        if not result_dirs:
            logger.error(f"No analysis result directories found in {self.results_dir}")
            return data
        
        logger.info(f"Found {len(result_dirs)} result directories")
        
        # Combine data from all scenarios
        all_regional = []
        all_person_type = []
        
        for result_dir in result_dirs:
            scenario_name = result_dir.name.replace("analysis_results_", "")
            logger.info(f"Loading results from {scenario_name}")
            
            # Load regional data
            regional_file = result_dir / "free_parking_regional.csv"
            if regional_file.exists():
                df = pd.read_csv(regional_file)
                all_regional.append(df)
            
            # Load person type data
            person_type_file = result_dir / "free_parking_by_person_type.csv"
            if person_type_file.exists():
                df = pd.read_csv(person_type_file)
                all_person_type.append(df)
        
        if all_regional:
            data['regional'] = pd.concat(all_regional, ignore_index=True)
            logger.info(f"  ✓ Loaded {len(data['regional'])} regional records")
        
        if all_person_type:
            data['by_person_type'] = pd.concat(all_person_type, ignore_index=True)
            logger.info(f"  ✓ Loaded {len(data['by_person_type'])} person type records")
        
        return data
    
    def _create_regional_comparison(self, df: pd.DataFrame) -> go.Figure:
        """Create regional comparison bar chart."""
        logger.info("Creating regional comparison chart")
        
        # Filter to only modeled choices (exclude -1)
        df_plot = df[df['fp_choice'] != -1].copy()
        
        if len(df_plot) == 0:
            logger.warning("No valid data for regional comparison")
            return None
        
        # Fix empty labels - use fp_choice values
        df_plot['fp_choice_label'] = df_plot['fp_choice_label'].fillna('').replace('', 'Unknown')
        df_plot.loc[df_plot['fp_choice'] == 1, 'fp_choice_label'] = 'Free Parking Available'
        df_plot.loc[df_plot['fp_choice'] == 2, 'fp_choice_label'] = 'Paid Parking'
        df_plot.loc[df_plot['fp_choice'] == 3, 'fp_choice_label'] = 'No Parking'
        
        # Create figure
        fig = px.bar(
            df_plot,
            x='scenario',
            y='share',
            color='fp_choice_label',
            title='Free Parking Choice by Scenario (Workers Only)',
            labels={'share': 'Percentage (%)', 'scenario': 'Scenario'},
            barmode='group',
            color_discrete_sequence=px.colors.qualitative.Set2,
            text='share'
        )
        
        # Format text labels
        fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
        
        fig.update_layout(
            height=500,
            xaxis_title='Scenario',
            yaxis_title='Share of Workers (%)',
            legend_title='Parking Choice',
            hovermode='x unified',
            yaxis_range=[0, max(df_plot['share']) * 1.15]  # Add space for labels
        )
        
        return fig
    
    def _create_person_type_breakdown(self, df: pd.DataFrame) -> go.Figure:
        """Create person type breakdown chart."""
        logger.info("Creating person type breakdown chart")
        
        # Filter to only modeled choices
        df_plot = df[df['fp_choice'] != -1].copy()
        
        if len(df_plot) == 0:
            logger.warning("No valid data for person type breakdown")
            return None
        
        # Fix empty labels
        df_plot['fp_choice_label'] = df_plot['fp_choice_label'].fillna('').replace('', 'Unknown')
        df_plot.loc[df_plot['fp_choice'] == 1, 'fp_choice_label'] = 'Free Parking'
        df_plot.loc[df_plot['fp_choice'] == 2, 'fp_choice_label'] = 'Paid Parking'
        df_plot.loc[df_plot['fp_choice'] == 3, 'fp_choice_label'] = 'No Parking'
        
        # Create grouped bar chart by scenario
        fig = px.bar(
            df_plot,
            x='fp_choice_label',
            y='share',
            color='scenario',
            facet_col='person_type_label',
            title='Free Parking Choice by Person Type',
            labels={'share': 'Percentage (%)', 'fp_choice_label': 'Parking Choice'},
            barmode='group',
            color_discrete_sequence=['#4e79a7', '#e15759'],
            text='share'
        )
        
        # Format text labels
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        
        fig.update_layout(
            height=500,
            yaxis_title='Share (%)',
            hovermode='x unified'
        )
        
        return fig
    
    def _create_summary_table(self, df: pd.DataFrame) -> go.Figure:
        """Create summary statistics table."""
        logger.info("Creating summary table")
        
        # Filter to only modeled choices and fix labels
        df_clean = df[df['fp_choice'] != -1].copy()
        df_clean['fp_choice_label'] = df_clean['fp_choice_label'].fillna('').replace('', 'Unknown')
        df_clean.loc[df_clean['fp_choice'] == 1, 'fp_choice_label'] = 'Free Parking Available'
        df_clean.loc[df_clean['fp_choice'] == 2, 'fp_choice_label'] = 'Paid Parking'
        df_clean.loc[df_clean['fp_choice'] == 3, 'fp_choice_label'] = 'No Parking'
        
        # Pivot data for table
        df_pivot = df_clean.pivot_table(
            index='fp_choice_label',
            columns='scenario',
            values='share',
            aggfunc='sum'
        ).round(2)
        
        # Add worker counts too
        df_workers = df_clean.pivot_table(
            index='fp_choice_label',
            columns='scenario',
            values='workers',
            aggfunc='sum'
        )
        
        # Format workers with commas
        table_values = [df_pivot.index]
        for col in df_pivot.columns:
            table_values.append([f"{df_pivot.loc[idx, col]:.2f}% ({df_workers.loc[idx, col]:,.0f})" 
                               for idx in df_pivot.index])
        
        # Create table
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['Parking Choice'] + list(df_pivot.columns),
                fill_color='paleturquoise',
                align='left',
                font=dict(size=12, color='black')
            ),
            cells=dict(
                values=table_values,
                fill_color='lavender',
                align='left',
                font=dict(size=11)
            )
        )])
        
        fig.update_layout(
            title='Summary Statistics - Share % (Worker Count)',
            height=300
        )
        
        return fig
    
    def _generate_html(self, figs: list, output_path: Path):
        """Generate HTML file with all visualizations."""
        logger.info(f"Generating HTML to {output_path}")
        
        # Get analysis title from config
        analysis_title = self.config.get('analysis', {}).get('title', 'Analysis Dashboard')
        analysis_desc = self.config.get('analysis', {}).get('description', '')
        
        # Build HTML
        html_parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '    <meta charset="utf-8">',
            f'    <title>{analysis_title}</title>',
            '    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>',
            '    <style>',
            '        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }',
            '        .header { background-color: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }',
            '        .header h1 { margin: 0; }',
            '        .header p { margin: 5px 0 0 0; opacity: 0.9; }',
            '        .chart-container { background-color: white; padding: 20px; margin-bottom: 20px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }',
            '        .footer { text-align: center; padding: 20px; color: #7f8c8d; font-size: 0.9em; }',
            '    </style>',
            '</head>',
            '<body>',
            '    <div class="header">',
            f'        <h1>{analysis_title}</h1>',
            f'        <p>{analysis_desc}</p>',
            f'        <p style="font-size: 0.9em;">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>',
            '    </div>',
        ]
        
        # Add each figure
        for i, fig in enumerate(figs):
            div_id = f'chart_{i}'
            html_parts.append(f'    <div class="chart-container">')
            html_parts.append(f'        <div id="{div_id}"></div>')
            html_parts.append('    </div>')
        
        html_parts.extend([
            '    <div class="footer">',
            '        <p>TM2py-Utils Analysis Dashboard</p>',
            '    </div>',
        ])
        
        # Add JavaScript to render plots
        html_parts.append('    <script>')
        for i, fig in enumerate(figs):
            div_id = f'chart_{i}'
            plot_json = fig.to_json()
            html_parts.append(f'        Plotly.newPlot("{div_id}", {plot_json});')
        html_parts.append('    </script>')
        
        html_parts.extend([
            '</body>',
            '</html>'
        ])
        
        # Write file
        with open(output_path, 'w') as f:
            f.write('\n'.join(html_parts))


def main():
    """Main entry point."""
    # Set up paths
    validation_dir = Path(__file__).parent
    config_path = validation_dir / "example_analysis_config.yaml"
    results_dir = validation_dir / "data_final"
    output_dir = validation_dir / "dashboard_output"
    
    logger.info("Dashboard Generation")
    logger.info("=" * 50)
    logger.info(f"Config: {config_path}")
    logger.info(f"Results: {results_dir}")
    logger.info(f"Output: {output_dir}")
    
    # Create dashboard
    generator = DashboardGenerator(config_path, results_dir, output_dir)
    html_path = generator.create_dashboard()
    
    if html_path:
        logger.info(f"\n✅ Success! Open dashboard at: {html_path.absolute()}")
        return True
    else:
        logger.error("\n❌ Dashboard generation failed")
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
