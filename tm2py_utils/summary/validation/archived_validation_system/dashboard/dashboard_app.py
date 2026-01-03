"""
Streamlit dashboard for TM2.2 validation summaries.

Loads validation CSVs and displays interactive comparison charts
for multiple datasets using YAML-based configuration.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import yaml
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Load variable display names and categorical ordering
VARIABLE_LABELS = {}
CATEGORICAL_ORDER = {}
DATASET_ORDER = []

try:
    variable_labels_path = Path(__file__).parent.parent.parent / "data_model" / "variable_labels.yaml"
    if variable_labels_path.exists():
        with open(variable_labels_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
            # Extract labels (all non-dict values)
            VARIABLE_LABELS = {k: v for k, v in config.items() if not isinstance(v, dict)}
            # Extract categorical ordering
            CATEGORICAL_ORDER = config.get('categorical_order', {})
except Exception as e:
    logger.warning(f"Could not load variable labels: {e}")

try:
    # Load dataset order from validation config
    validation_config_path = Path(__file__).parent.parent / "validation_config.yaml"
    if validation_config_path.exists():
        with open(validation_config_path, 'r', encoding='utf-8') as f:
            validation_config = yaml.safe_load(f) or {}
            DATASET_ORDER = validation_config.get('dataset_order', [])
except Exception as e:
    logger.warning(f"Could not load validation config: {e}")

# MTC Brand Colors
MTC_COLORS = {
    'primary_blue': '#003D7A',      # MTC Primary Blue
    'teal': '#00A19A',              # MTC Teal
    'orange': '#ED8B00',            # MTC Orange
    'purple': '#7A3F93',            # MTC Purple
    'green': '#8CC63F',             # MTC Green
    'red': '#E31937',               # MTC Red
    'dark_blue': '#002D56',         # Darker blue
    'light_blue': '#4A90E2',        # Light blue
    'gray': '#6B6B6B',              # MTC Gray
}

# Color palettes for different use cases
MTC_PALETTE_SEQUENTIAL = [
    MTC_COLORS['primary_blue'],
    MTC_COLORS['teal'],
    MTC_COLORS['light_blue'],
    MTC_COLORS['orange'],
    MTC_COLORS['purple'],
    MTC_COLORS['green'],
]

# Extended categorical palette for mode charts (17 modes)
MTC_PALETTE_CATEGORICAL = [
    MTC_COLORS['teal'],          # 1
    MTC_COLORS['orange'],        # 2
    MTC_COLORS['purple'],        # 3
    MTC_COLORS['green'],         # 4
    MTC_COLORS['primary_blue'],  # 5
    MTC_COLORS['red'],           # 6
    '#FFB6C1',  # Light Pink     # 7
    '#87CEEB',  # Sky Blue       # 8
    '#DDA0DD',  # Plum           # 9
    '#F0E68C',  # Khaki          # 10
    '#98FB98',  # Pale Green     # 11
    '#FFE4B5',  # Moccasin       # 12
    '#B0C4DE',  # Light Steel    # 13
    '#FFDAB9',  # Peach          # 14
    '#E6E6FA',  # Lavender       # 15
    '#FAFAD2',  # Light Goldenrod# 16
    '#D3D3D3',  # Light Gray     # 17
]

# Default layout for all charts
PLOTLY_LAYOUT = {
    'font': {'family': 'Inter, Arial, sans-serif', 'size': 13, 'color': MTC_COLORS['gray']},
    'plot_bgcolor': 'rgba(248, 249, 250, 0.3)',
    'paper_bgcolor': 'white',
    'margin': {'l': 60, 'r': 20, 't': 50, 'b': 70},
    'hovermode': 'closest',
    'hoverlabel': {
        'font': {'size': 13, 'family': 'Inter, Arial, sans-serif'},
        'bgcolor': 'white',
        'bordercolor': MTC_COLORS['teal'],
        'align': 'left'
    },
}


def load_csv(data_dir: Path, filename: str) -> pd.DataFrame:
    """Load a CSV file from the data directory."""
    csv_path = data_dir / filename
    if not csv_path.exists():
        st.error(f"CSV file not found: {filename}")
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def create_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    color_col: Optional[str] = None,
    stacked: bool = False,
    color_palette: Optional[List[str]] = None,
    facet_col: Optional[str] = None,
    **kwargs
) -> go.Figure:
    """
    Create a bar chart with MTC styling.
    
    Args:
        df: DataFrame with data
        x: Column for x-axis
        y: Column for y-axis
        title: Chart title
        color_col: Column to use for coloring/grouping bars
        stacked: Whether to stack bars
        color_palette: Custom color palette (defaults to MTC categorical)
        facet_col: Column to use for faceting (creates subplots)
        **kwargs: Additional Plotly Express bar() arguments
    
    Returns:
        Plotly Figure object
    """
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", showarrow=False)
        return fig
    
    # Validate required columns exist and show helpful error with st.error
    import streamlit as st
    if x not in df.columns:
        error_msg = f"❌ Column '{x}' not found in DataFrame. Available columns: {list(df.columns)}"
        st.error(error_msg)
        raise ValueError(error_msg)
    if y not in df.columns:
        error_msg = f"❌ Column '{y}' not found in DataFrame. Available columns: {list(df.columns)}"
        st.error(error_msg)
        raise ValueError(error_msg)
    if color_col and color_col not in df.columns:
        error_msg = f"❌ Color column '{color_col}' not found in DataFrame. Available columns: {list(df.columns)}"
        st.error(error_msg)
        raise ValueError(error_msg)
    if facet_col and facet_col not in df.columns:
        error_msg = f"❌ Facet column '{facet_col}' not found in DataFrame. Available columns: {list(df.columns)}"
        st.error(error_msg)
        raise ValueError(error_msg)
    
    # Use MTC categorical palette by default
    if color_palette is None:
        color_palette = MTC_PALETTE_CATEGORICAL
    
    # Get readable labels for axes
    x_label = VARIABLE_LABELS.get(x, x.replace('_', ' ').title())
    y_label = VARIABLE_LABELS.get(y, y.replace('_', ' ').title())
    color_label = VARIABLE_LABELS.get(color_col, color_col.replace('_', ' ').title()) if color_col else None
    
    # Build category_orders dict for Plotly
    category_orders = {}
    if x in CATEGORICAL_ORDER:
        # Convert to strings to match CSV data
        category_orders[x] = [str(cat) for cat in CATEGORICAL_ORDER[x]]
    if color_col and color_col in CATEGORICAL_ORDER:
        category_orders[color_col] = [str(cat) for cat in CATEGORICAL_ORDER[color_col]]
    if facet_col and facet_col in CATEGORICAL_ORDER:
        category_orders[facet_col] = [str(cat) for cat in CATEGORICAL_ORDER[facet_col]]
    
    # Apply dataset ordering if dataset is used as a dimension
    if DATASET_ORDER:
        if x == 'dataset':
            category_orders['dataset'] = DATASET_ORDER
        if color_col == 'dataset':
            category_orders['dataset'] = DATASET_ORDER
        if facet_col == 'dataset':
            category_orders['dataset'] = DATASET_ORDER
    
    # Create the bar chart
    if color_col:
        fig = px.bar(
            df, 
            x=x, 
            y=y, 
            color=color_col,
            facet_col=facet_col,
            title=title,
            barmode='stack' if stacked else 'group',
            color_discrete_sequence=color_palette,
            category_orders=category_orders if category_orders else None,
            labels={x: x_label, y: y_label, color_col: color_label},
            **kwargs
        )
    else:
        fig = px.bar(
            df, 
            x=x, 
            y=y, 
            facet_col=facet_col,
            title=title,
            color_discrete_sequence=[MTC_COLORS['primary_blue']],
            category_orders=category_orders if category_orders else None,
            labels={x: x_label, y: y_label},
            **kwargs
        )
    
    # Apply MTC styling
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_layout(
        title={
            'font': {'size': 18, 'color': MTC_COLORS['dark_blue'], 'family': 'Inter, Arial, sans-serif'},
            'x': 0.02,
            'xanchor': 'left'
        },
        margin={'l': 70, 'r': 30, 't': 60, 'b': 110}  # Extra bottom margin for axis labels
    )
    
    # Format axes with modern styling
    fig.update_xaxes(
        showgrid=False,
        showline=True,
        linewidth=2,
        linecolor='#E5E5E5',
        title_font={'size': 13, 'color': MTC_COLORS['gray'], 'family': 'Inter, Arial, sans-serif'},
        tickfont={'size': 12},
        tickangle=-45,  # Angle labels to prevent overlap
        automargin=True  # Auto-adjust margins for labels
    )
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1.5,
        gridcolor='rgba(0,0,0,0.05)',
        showline=True,
        linewidth=2,
        linecolor='#E5E5E5',
        title_font={'size': 13, 'color': MTC_COLORS['gray'], 'family': 'Inter, Arial, sans-serif'},
        tickfont={'size': 12},
        automargin=True,  # Auto-adjust margins for labels
        zeroline=True,
        zerolinewidth=2,
        zerolinecolor='rgba(0,0,0,0.1)'
    )
    
    # Add smooth bar styling
    fig.update_traces(
        marker_line_width=0,
        opacity=0.95
    )
    
    # Add % suffix to y-axis if column contains 'share' (values already in percent form)
    if 'share' in y.lower():
        fig.update_yaxes(ticksuffix='%')
    
    # Style faceted charts
    if facet_col:
        # Clean up facet titles (remove "dataset=" prefix)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        # Adjust spacing between facets
        fig.update_layout(
            margin={'l': 60, 'r': 20, 't': 80, 'b': 60},
            height=400
        )
    
    return fig


def create_chart_from_config(
    chart_config: Dict[str, Any],
    data_dir: Path
) -> Optional[go.Figure]:
    """
    Create a chart based on YAML configuration.
    
    Args:
        chart_config: Chart configuration from YAML
        data_dir: Directory containing CSV files
    
    Returns:
        Plotly Figure or None if error
    """
    chart_type = chart_config.get('type', 'bar')
    props = chart_config.get('props', {})
    title = chart_config.get('title', '')
    
    # Load data
    dataset = props.get('dataset')
    if not dataset:
        st.error(f"Chart '{title}' missing 'dataset' property")
        return None
    
    df = load_csv(data_dir, dataset)
    if df.empty:
        return None
    
    # Extract chart properties
    x = props.get('x')
    y = props.get('y')
    columns = props.get('columns')  # For stacking/coloring
    groupBy = props.get('groupBy')  # For grouping by dataset
    stacked = props.get('stacked', False)
    
    # Determine if we need faceting (3+ dimensions)
    # Count non-null dimensions: x, y is always present, plus columns/groupBy and dataset
    has_columns = columns is not None
    has_dataset = 'dataset' in df.columns and df['dataset'].nunique() > 1
    needs_faceting = has_columns and has_dataset
    
    if chart_type == 'bar':
        if needs_faceting:
            # Use columns for color, facet by dataset
            return create_bar_chart(
                df=df,
                x=x,
                y=y,
                title=title,
                color_col=columns,
                stacked=stacked,
                facet_col='dataset',
                text=y if props.get('show_values') else None
            )
        else:
            # Use groupBy if specified, otherwise fall back to columns
            color_col = groupBy or columns
            return create_bar_chart(
                df=df,
                x=x,
                y=y,
                title=title,
                color_col=color_col,
                stacked=stacked,
                text=y if props.get('show_values') else None
            )
    
    # Add more chart types as needed
    else:
        st.warning(f"Chart type '{chart_type}' not yet implemented")
        return None


def load_dashboard_config(config_path: Path) -> Dict[str, Any]:
    """Load dashboard configuration from YAML file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def render_dashboard(config: Dict[str, Any], data_dir: Path):
    """
    Render the dashboard based on YAML configuration.
    
    Args:
        config: Dashboard configuration dictionary
        data_dir: Directory containing CSV data files
    """
    # Display header with MTC-inspired styling
    st.markdown("""
    <style>
    /* MTC-inspired professional styling */
    .main-header {
        background: linear-gradient(135deg, #003D7A 0%, #00A19A 100%);
        padding: 2.5rem 2rem 2rem 2rem;
        border-radius: 12px;
        margin-bottom: 2.5rem;
        box-shadow: 0 4px 12px rgba(0,61,122,0.15);
        position: relative;
        overflow: hidden;
    }
    .main-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
        border-radius: 50%;
    }
    .main-header h1 {
        color: white !important;
        margin: 0;
        font-weight: 700;
        font-size: 2.75rem;
        letter-spacing: -0.5px;
        position: relative;
    }
    .main-header p {
        color: rgba(255,255,255,0.95);
        margin-top: 0.75rem;
        font-size: 1.15rem;
        font-weight: 300;
        position: relative;
    }
    /* Card-style sections */
    .stApp section[data-testid="stVerticalBlock"] > div {
        background: white;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        transition: box-shadow 0.3s ease;
    }
    .stApp section[data-testid="stVerticalBlock"] > div:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    /* Cleaner dividers */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(to right, transparent, #e5e5e5, transparent);
        margin: 2.5rem 0;
    }
    /* Better section headers */
    h2 {
        font-weight: 600;
        letter-spacing: -0.3px;
        margin-top: 2rem !important;
        margin-bottom: 1.5rem !important;
        padding-bottom: 0.75rem;
        border-bottom: 3px solid #00A19A;
        display: inline-block;
    }
    </style>
    """, unsafe_allow_html=True)
    
    header = config.get('header', {})
    title = header.get('title', 'Travel Model Two Validation')
    description = header.get('description', 'Regional transportation model validation dashboard for the San Francisco Bay Area')
    
    st.markdown(f"""
    <div class="main-header">
        <h1>{title}</h1>
        <p>{description}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Render layout sections
    layout = config.get('layout', {})
    
    for section_name, charts in layout.items():
        if not charts:  # Skip empty sections
            continue
            
        # Section header
        section_title = section_name.replace('_', ' ').title()
        st.subheader(section_title)
        
        # Create columns for side-by-side charts
        if len(charts) == 1:
            # Single chart takes full width
            fig = create_chart_from_config(charts[0], data_dir)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        elif len(charts) == 2:
            # Two charts side by side
            col1, col2 = st.columns(2)
            with col1:
                fig = create_chart_from_config(charts[0], data_dir)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = create_chart_from_config(charts[1], data_dir)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
        else:
            # More than 2 charts: show 2 per row
            for i in range(0, len(charts), 2):
                col1, col2 = st.columns(2)
                with col1:
                    fig = create_chart_from_config(charts[i], data_dir)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                if i + 1 < len(charts):
                    with col2:
                        fig = create_chart_from_config(charts[i + 1], data_dir)
                        if fig:
                            st.plotly_chart(fig, use_container_width=True)
        
        st.divider()


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="TM2.2 Validation Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Banner image
    banner_path = Path(__file__).parent.parent / "outputs" / "dashboard" / "validation-app-banner.PNG"
    if banner_path.exists():
        st.image(str(banner_path), use_container_width=True)
    
    # Custom CSS for MTC branding
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        .stApp {{
            background: linear-gradient(to bottom, #f8f9fa 0%, #ffffff 100%);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}
        h1 {{
            color: {MTC_COLORS['dark_blue']};
            font-family: 'Inter', sans-serif;
            font-weight: 700;
        }}
        h2, h3 {{
            color: {MTC_COLORS['primary_blue']};
            font-family: 'Inter', sans-serif;
            font-weight: 600;
        }}
        .stButton>button {{
            background: linear-gradient(135deg, {MTC_COLORS['teal']} 0%, #008f89 100%);
            color: white;
            border: none;
            padding: 0.5rem 1.5rem;
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.3s ease;
            box-shadow: 0 2px 6px rgba(0,161,154,0.3);
        }}
        .stButton>button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,161,154,0.4);
        }}
        /* Sidebar enhancements */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(to bottom, #f8f9fa 0%, #ffffff 100%);
            border-right: 1px solid #e5e5e5;
        }}
        section[data-testid="stSidebar"] .stMarkdown {{
            padding: 0.25rem 0;
        }}
        /* Selectbox styling */
        .stSelectbox > div > div {{
            border-radius: 8px;
            border-color: #d1d5db;
            transition: all 0.2s ease;
        }}
        .stSelectbox > div > div:hover {{
            border-color: {MTC_COLORS['teal']};
            box-shadow: 0 0 0 1px {MTC_COLORS['teal']};
        }}
        /* Plotly chart containers */
        .js-plotly-plot {{
            border-radius: 8px;
            overflow: hidden;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    # Sidebar for configuration
    st.sidebar.title("📊 Travel Model Two Validation")
    st.sidebar.markdown("---")
    
    # Get validation directory
    validation_dir = Path(__file__).parent.parent
    outputs_dir = validation_dir / "outputs"
    data_dir = outputs_dir / "dashboard"  # CSVs are in outputs/dashboard folder
    dashboard_config_dir = validation_dir / "dashboard"  # YAML configs are in dashboard/ folder
    
    # Check if data directory exists
    if not data_dir.exists():
        st.error("⚠️ Dashboard data directory not found!")
        st.markdown(f"""
        ### Setup Required
        
        The dashboard needs CSV files to display. Expected location:
        ```
        {data_dir}
        ```
        
        **To generate the required CSV files:**
        
        1. Run the validation summaries:
        ```bash
        cd tm2py_utils/summary/validation
        conda activate tm2py-utils
        python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml
        ```
        
        2. For deployment, ensure CSV files are committed to the repository (you may need to update `.gitignore`)
        
        **For local development:** See [Generate Summaries documentation](https://github.com/BayAreaMetro/tm2py-utils/blob/main/tm2py_utils/docs/generate-summaries.md)
        """)
        return
    
    # Find dashboard YAML files
    dashboard_files = sorted(dashboard_config_dir.glob("dashboard-*.yaml"))
    
    if not dashboard_files:
        st.error("No dashboard configuration files found!")
        st.info(f"Looking in: {dashboard_config_dir}")
        return
    
    # Dashboard selector
    dashboard_names = {f.stem: f for f in dashboard_files}
    selected_dashboard = st.sidebar.selectbox(
        "Select Dashboard",
        options=list(dashboard_names.keys()),
        format_func=lambda x: x.replace('dashboard-', '').replace('-', ' ').replace('1', '').replace('3', '').replace('4', '').strip().title()
    )
    
    # Data freshness indicator
    if dashboard_names:
        latest_file = max(dashboard_files, key=lambda f: f.stat().st_mtime)
        st.sidebar.info(f"Last updated: {pd.Timestamp(latest_file.stat().st_mtime, unit='s').strftime('%Y-%m-%d %H:%M')}")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.markdown("Compare multiple TM2.2 datasets across household, worker, tour, and trip summaries.")
    
    # Load and render selected dashboard
    config_path = dashboard_names[selected_dashboard]
    
    try:
        config = load_dashboard_config(config_path)
        render_dashboard(config, data_dir)
    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error("Fatal error starting dashboard")
        st.exception(e)
        import traceback
        st.code(traceback.format_exc())
