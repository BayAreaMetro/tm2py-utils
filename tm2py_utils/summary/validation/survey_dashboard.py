"""
Streamlit dashboard for viewing survey validation summaries.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from typing import Dict, List

# Survey validation directory
SURVEY_DIR = Path(r"C:\GitHub\travel-diary-survey-tools\projects\bats_2023\output\ctramp\validation")

# MTC Brand Colors
MTC_COLORS = {
    'primary_blue': '#003D7A',
    'teal': '#00A19A',
    'orange': '#ED8B00',
    'purple': '#7A3F93',
    'green': '#8CC63F',
    'red': '#E31937',
}

def load_summary_csv(filename: str) -> pd.DataFrame:
    """Load a validation summary CSV."""
    csv_path = SURVEY_DIR / filename
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return None

def create_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> go.Figure:
    """Create a simple bar chart."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[x_col],
        y=df[y_col],
        marker_color=MTC_COLORS['teal']
    ))
    fig.update_layout(
        title=title,
        xaxis_title=x_col.replace('_', ' ').title(),
        yaxis_title=y_col.replace('_', ' ').title(),
        plot_bgcolor='rgba(248, 249, 250, 0.3)',
        paper_bgcolor='white',
        font={'family': 'Inter, Arial, sans-serif', 'size': 12, 'color': '#6B6B6B'},
    )
    return fig

def main():
    st.set_page_config(
        page_title="Survey Validation Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 BATS 2023 Survey Validation Dashboard")
    st.markdown("---")
    
    # Check if validation directory exists
    if not SURVEY_DIR.exists():
        st.error(f"Validation directory not found: {SURVEY_DIR}")
        return
    
    # Get all CSV files
    csv_files = sorted(SURVEY_DIR.glob("*.csv"))
    
    if not csv_files:
        st.warning(f"No CSV files found in {SURVEY_DIR}")
        return
    
    st.sidebar.title("Select Summary")
    selected_file = st.sidebar.selectbox(
        "Choose a summary to view:",
        options=[f.name for f in csv_files],
        format_func=lambda x: x.replace('_', ' ').replace('.csv', '').title()
    )
    
    # Display summary info
    st.sidebar.markdown("---")
    st.sidebar.info(f"**Total summaries:** {len(csv_files)}")
    
    # Load and display selected CSV
    df = load_summary_csv(selected_file)
    
    if df is not None:
        st.subheader(f"Summary: {selected_file.replace('_', ' ').replace('.csv', '').title()}")
        
        # Show dataframe
        st.dataframe(df, use_container_width=True, height=400)
        
        # Show basic stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Rows", len(df))
        with col2:
            st.metric("Total Columns", len(df.columns))
        with col3:
            if df.select_dtypes(include=['number']).shape[1] > 0:
                numeric_col = df.select_dtypes(include=['number']).columns[0]
                st.metric(f"Total {numeric_col}", f"{df[numeric_col].sum():,.0f}")
        
        # Try to create a visualization if appropriate columns exist
        st.markdown("---")
        st.subheader("Visualization")
        
        # Simple heuristic: if there's a 'count' or 'value' column, visualize it
        if len(df) > 0 and len(df.columns) >= 2:
            x_col = df.columns[0]
            numeric_cols = df.select_dtypes(include=['number']).columns
            
            if len(numeric_cols) > 0:
                y_col = numeric_cols[0]
                
                # Limit to top 20 categories if too many
                df_plot = df.nlargest(20, y_col) if len(df) > 20 else df
                
                fig = create_bar_chart(df_plot, x_col, y_col, selected_file.replace('.csv', '').replace('_', ' ').title())
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No numeric columns available for visualization")
        
        # Download button
        st.markdown("---")
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=selected_file,
            mime="text/csv"
        )
    else:
        st.error(f"Could not load {selected_file}")

if __name__ == "__main__":
    main()
