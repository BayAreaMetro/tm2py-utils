"""
Streamlit dashboard for comparing Model vs Survey outputs
Simplified version for BATS survey vs TM1 model comparison
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import yaml
from typing import Dict, List, Optional, Any

# MTC Brand Colors
MTC_COLORS = {
    'primary_blue': '#003D7A',
    'teal': '#00A19A',
    'orange': '#ED8B00',
    'survey': '#ED8B00',  # Orange for survey
    'model': '#00A19A',   # Teal for model
}

# Color mapping for datasets
DATASET_COLORS = {
    'BATS Survey': MTC_COLORS['survey'],
    'TM1 Model': MTC_COLORS['model'],
}


def load_csv(data_dir: Path, filename: str, dataset_name: str) -> pd.DataFrame:
    """Load a CSV file and add dataset column."""
    csv_path = data_dir / filename
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    df['dataset'] = dataset_name
    return df


def create_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    color_col: str = 'dataset',
) -> go.Figure:
    """Create a bar chart comparing datasets."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", showarrow=False)
        return fig
    
    # Create figure
    fig = px.bar(
        df, 
        x=x, 
        y=y, 
        color=color_col,
        barmode='group',
        title=title,
        color_discrete_map=DATASET_COLORS,
    )
    
    # Update layout with MTC styling
    fig.update_layout(
        font={'family': 'Inter, Arial, sans-serif', 'size': 13},
        plot_bgcolor='rgba(248, 249, 250, 0.3)',
        paper_bgcolor='white',
        margin={'l': 60, 'r': 20, 't': 50, 'b': 70},
        hovermode='closest',
        height=400,
    )
    
    # Add % suffix if it's a share
    if 'share' in y.lower():
        fig.update_yaxes(ticksuffix='%')
    
    return fig


def load_dashboard_config(config_path: Path) -> Dict[str, Any]:
    """Load dashboard configuration from YAML file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Model vs Survey Comparison",
        page_icon="📊",
        layout="wide",
    )
    
    # Custom CSS
    st.markdown(f"""
        <style>
        .main-header {{
            background: linear-gradient(135deg, {MTC_COLORS['primary_blue']} 0%, {MTC_COLORS['teal']} 100%);
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            color: white;
        }}
        .main-header h1 {{
            color: white !important;
            margin: 0;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown(f"""
    <div class="main-header">
        <h1>Model vs Survey Comparison</h1>
        <p>Compare TM1 Model outputs with BATS Survey data</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar for data directories
    st.sidebar.title("📂 Data Sources")
    
    # Get current directory
    current_dir = Path(__file__).parent
    
    # Data directory inputs
    survey_dir = st.sidebar.text_input(
        "Survey Summaries Directory",
        value=r"E:\processed_bats_tm1\summaries_test"
    )
    model_dir = st.sidebar.text_input(
        "Model Summaries Directory",
        value=r"M:\Application\Model One\RTP2025\IncrementalProgress\2023_TM161_IPA_35\OUTPUT\summaries_test"
    )
    
    survey_path = Path(survey_dir)
    model_path = Path(model_dir)
    
    # Check if directories exist
    if not survey_path.exists():
        st.error(f"⚠️ Survey directory not found: {survey_dir}")
        return
    if not model_path.exists():
        st.error(f"⚠️ Model directory not found: {model_dir}")
        return
    
    st.sidebar.success("✅ Both directories found")
    
    # Load dashboard config
    config_path = current_dir / "dashboard-model-survey-comparison.yaml"
    if not config_path.exists():
        st.error(f"Dashboard config not found: {config_path}")
        return
    
    config = load_dashboard_config(config_path)
    layout = config.get('layout', {})
    
    # Render sections
    for section_name, charts in layout.items():
        if not charts:
            continue
        
        section_title = section_name.replace('_', ' ').title()
        st.header(section_title)
        
        # Create columns for charts
        if len(charts) >= 2:
            col1, col2 = st.columns(2)
            cols = [col1, col2]
        else:
            cols = [st.container()]
        
        for i, chart_config in enumerate(charts):
            with cols[i % len(cols)]:
                try:
                    props = chart_config.get('props', {})
                    filename = props.get('dataset', '')
                    x = props.get('x', '')
                    y = props.get('y', '')
                    title = chart_config.get('title', '')
                    
                    # Load data from both sources
                    survey_df = load_csv(survey_path, filename, 'BATS Survey')
                    model_df = load_csv(model_path, filename, 'TM1 Model')
                    
                    # Combine dataframes
                    combined_df = pd.concat([survey_df, model_df], ignore_index=True)
                    
                    if not combined_df.empty:
                        fig = create_bar_chart(combined_df, x, y, title)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning(f"No data found for {filename}")
                
                except Exception as e:
                    st.error(f"Error rendering chart: {str(e)}")
        
        st.divider()


if __name__ == "__main__":
    main()
