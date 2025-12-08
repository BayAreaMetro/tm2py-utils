"""
TM2 Mode Share Analysis Tool

This script analyzes Travel Model Two (TM2) core summaries with proper transportation planning focus.
Generates treemap visualizations for mode share patterns using TM2-specific labels and codes.

Focus: Mode share analysis with proper TM2 mode labels and meaningful breakdowns
"""

import pandas as pd
import numpy as np
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import argparse
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# TM2-SPECIFIC CONFIGURATION
# ============================================================================

# TM2 Mode Labels (from CTRAMP documentation)
TM2_MODE_LABELS = {
    1: "Drive Alone (Free)",
    2: "Drive Alone (Toll)", 
    3: "HOV2 (GP Lanes)",
    4: "HOV2 (HOV Lanes)",
    5: "HOV2 (Toll)",
    6: "HOV3+ (GP Lanes)", 
    7: "HOV3+ (HOV Lanes)",
    8: "HOV3+ (Toll)",
    9: "Walk",
    10: "Bike", 
    11: "Walk to Transit",
    12: "Park & Ride Transit",
    13: "Kiss & Ride (Personal)",
    14: "Kiss & Ride (TNC)",
    15: "Taxi",
    16: "TNC (Uber/Lyft)"
}

# Mode Categories for Analysis
MODE_CATEGORIES = {
    "Auto - Solo": [1, 2],  # Drive Alone
    "Auto - Shared": [3, 4, 5, 6, 7, 8],  # All HOV modes
    "Transit": [11, 12, 13, 14],  # All transit access modes
    "Active": [9, 10],  # Walk, Bike
    "TNC/Taxi": [15, 16],  # Commercial modes
    "School Bus": [17]  # School bus
}

# TM2 Time Periods (5-period aggregation from documentation)
TIME_PERIODS = {
    "EA": "Early AM (3-6 AM)",
    "AM": "AM Peak (6-9 AM)", 
    "MD": "Midday (9 AM-3 PM)",
    "PM": "PM Peak (3-6:30 PM)",
    "EV": "Evening (6:30 PM-3 AM)"
}

# Trip Purposes (from CTRAMP documentation)
TRIP_PURPOSES = [
    "Home", "Work", "School", "University", "Shop", "Maintenance", 
    "Escort", "Eating Out", "Visiting", "Discretionary", "Work-Based"
]

# Income Categories
INCOME_LABELS = {
    1: "Less than $30k",
    2: "$30k to $60k", 
    3: "$60k to $100k",
    4: "$100k+"
}

# ============================================================================
# DATA LOADING AND PROCESSING
# ============================================================================

def load_tm2_data(data_dir):
    """Load TM2 core summary files with proper error handling."""
    data_dir = Path(data_dir)
    
    print(f"Loading TM2 data from: {data_dir}")
    
    files_loaded = {}
    
    # Trip Summary files (main focus for mode share)
    trip_files = [
        "TripSummaryByMode.csv",
        "TripSummaryByModePurpose.csv", 
        "TripSummaryByModeTimePeriod.csv",
        "TripSummaryByPurpose.csv",
        "TripSummarySimpleModePurpose.csv"
    ]
    
    for filename in trip_files:
        file_path = data_dir / filename
        if file_path.exists():
            try:
                df = pd.read_csv(file_path)
                files_loaded[filename] = df
                print(f"✓ Loaded {filename}: {len(df)} records")
            except Exception as e:
                print(f"✗ Error loading {filename}: {e}")
        else:
            print(f"⚠ File not found: {filename}")
    
    # Auto ownership for demographic breakdowns
    auto_files = ["AutomobileOwnership.csv"]
    for filename in auto_files:
        file_path = data_dir / filename
        if file_path.exists():
            try:
                df = pd.read_csv(file_path)
                files_loaded[filename] = df
                print(f"✓ Loaded {filename}: {len(df)} records")
            except Exception as e:
                print(f"✗ Error loading {filename}: {e}")
    
    return files_loaded

def apply_tm2_labels(df, mode_column='trip_mode'):
    """Apply proper TM2 mode labels and categories to dataframe."""
    if mode_column in df.columns:
        # Use existing labels if available, otherwise map from codes
        if 'trip_mode_label' in df.columns:
            df['mode_label'] = df['trip_mode_label']
        else:
            df['mode_label'] = df[mode_column].map(TM2_MODE_LABELS)
        df['mode_category'] = df[mode_column].apply(categorize_mode)
    return df

def categorize_mode(mode_code):
    """Categorize mode codes into broader categories."""
    for category, codes in MODE_CATEGORIES.items():
        if mode_code in codes:
            return category
    return "Other"

def categorize_mode_by_label(mode_label):
    """Categorize mode labels (from TM2 files) into broader categories."""
    mode_label = str(mode_label).lower()
    
    # Auto - Solo
    if any(x in mode_label for x in ['sov', 'drive_alone', 'da']):
        return "Auto - Solo"
    
    # Auto - Shared  
    if any(x in mode_label for x in ['sr2', 'sr3', 'hov', 'shared']):
        return "Auto - Shared"
    
    # Transit
    if any(x in mode_label for x in ['pnr', 'knr', 'wlk_trn', 'drv_trn', 'transit', 'bus', 'rail']):
        return "Transit"
    
    # Active
    if any(x in mode_label for x in ['walk', 'bike', 'wlk']):
        return "Active"
    
    # TNC/Taxi
    if any(x in mode_label for x in ['taxi', 'tnc', 'uber', 'lyft']):
        return "TNC/Taxi"
    
    # School bus
    if 'schlbus' in mode_label:
        return "School Bus"
    
    return "Other"

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def analyze_mode_shares(files_data):
    """Analyze mode shares from TM2 trip summary files."""
    results = {}
    
    # Overall mode share from TripSummaryByMode
    if "TripSummaryByMode.csv" in files_data:
        df = files_data["TripSummaryByMode.csv"].copy()
        df = apply_tm2_labels(df)
        
        if 'freq' in df.columns:
            # Preserve original share data if available
            if 'share' in df.columns:
                mode_totals = df.groupby(['mode_label', 'mode_category']).agg({
                    'freq': 'sum',
                    'share': 'sum'
                }).reset_index()
                mode_totals['share_pct'] = mode_totals['share'].round(2)
            else:
                mode_totals = df.groupby(['mode_label', 'mode_category'])['freq'].sum().reset_index()
                total_trips = mode_totals['freq'].sum()
                mode_totals['share_pct'] = (mode_totals['freq'] / total_trips * 100).round(2)
            
            results['overall_mode_share'] = mode_totals
            total_trips = mode_totals['freq'].sum()
            print(f"Overall mode share calculated: {total_trips:,.0f} total trips")
    
    # Mode by Purpose from TripSummaryByModePurpose  
    if "TripSummaryByModePurpose.csv" in files_data:
        df = files_data["TripSummaryByModePurpose.csv"].copy()
        df = apply_tm2_labels(df)
        
        if 'freq' in df.columns and 'tour_purpose' in df.columns:
            mode_purpose = df.groupby(['tour_purpose', 'mode_category', 'mode_label'])['freq'].sum().reset_index()
            
            # Calculate shares within each purpose
            purpose_totals = mode_purpose.groupby('tour_purpose')['freq'].sum().reset_index()
            purpose_totals.columns = ['tour_purpose', 'purpose_total']
            mode_purpose = mode_purpose.merge(purpose_totals, on='tour_purpose')
            mode_purpose['share_pct'] = (mode_purpose['freq'] / mode_purpose['purpose_total'] * 100).round(2)
            
            results['mode_by_purpose'] = mode_purpose
            print(f"Mode by purpose calculated: {len(mode_purpose)} purpose-mode combinations")
    
    # Mode by Time Period
    if "TripSummaryByModeTimePeriod.csv" in files_data:
        df = files_data["TripSummaryByModeTimePeriod.csv"].copy()
        
        # This file only has mode labels, not codes, so handle differently
        if 'freq' in df.columns and 'timePeriod' in df.columns and 'trip_mode_label' in df.columns:
            # Create mode categories based on mode labels
            df['mode_category'] = df['trip_mode_label'].apply(categorize_mode_by_label)
            df['mode_label'] = df['trip_mode_label']
            
            mode_time = df.groupby(['timePeriod', 'mode_category', 'mode_label'])['freq'].sum().reset_index()
            
            # Calculate shares within each time period
            time_totals = mode_time.groupby('timePeriod')['freq'].sum().reset_index()  
            time_totals.columns = ['timePeriod', 'time_total']
            mode_time = mode_time.merge(time_totals, on='timePeriod')
            mode_time['share_pct'] = (mode_time['freq'] / mode_time['time_total'] * 100).round(2)
            
            results['mode_by_time'] = mode_time
            print(f"Mode by time period calculated: {len(mode_time)} time-mode combinations")
    
    # Trip Purpose Summary from TripSummaryByPurpose
    if "TripSummaryByPurpose.csv" in files_data:
        df = files_data["TripSummaryByPurpose.csv"].copy()
        
        if 'freq' in df.columns and 'tour_purpose' in df.columns:
            purpose_totals = df.groupby('tour_purpose')['freq'].sum().reset_index()
            total_trips = purpose_totals['freq'].sum()
            purpose_totals['share_pct'] = (purpose_totals['freq'] / total_trips * 100).round(2)
            purpose_totals = purpose_totals.sort_values('freq', ascending=False)
            
            results['trip_purpose_summary'] = purpose_totals
            print(f"Trip purpose summary calculated: {total_trips:,.0f} total trips across {len(purpose_totals)} purposes")
    
    # Trip Time Period Summary - extract from mode by time data
    if "TripSummaryByModeTimePeriod.csv" in files_data:
        df = files_data["TripSummaryByModeTimePeriod.csv"].copy()
        
        if 'freq' in df.columns and 'timePeriod' in df.columns:
            time_totals = df.groupby('timePeriod')['freq'].sum().reset_index()
            total_trips = time_totals['freq'].sum()
            time_totals['share_pct'] = (time_totals['freq'] / total_trips * 100).round(2)
            
            # Sort by time period logically (assuming standard naming)
            time_order = ['EA', 'AM', 'MD', 'PM', 'EV']  # Standard TM2 time periods
            time_totals['time_sort'] = time_totals['timePeriod'].map(
                {period: i for i, period in enumerate(time_order)}
            ).fillna(99)  # Put unknown periods at the end
            time_totals = time_totals.sort_values('time_sort').drop('time_sort', axis=1)
            
            results['trip_time_summary'] = time_totals
            print(f"Trip time period summary calculated: {total_trips:,.0f} total trips across {len(time_totals)} time periods")
    
    return results

def analyze_demographics(files_data):
    """Analyze mode shares by demographic characteristics."""
    results = {}
    
    if "AutomobileOwnership.csv" in files_data:
        df = files_data["AutomobileOwnership.csv"].copy()
        
        if 'incQ_label' in df.columns and 'autos' in df.columns and 'freq' in df.columns:
            # Auto ownership by income
            auto_income = df.groupby(['incQ_label', 'autos'])['freq'].sum().reset_index()
            
            # Calculate shares within income groups
            income_totals = auto_income.groupby('incQ_label')['freq'].sum().reset_index()
            income_totals.columns = ['incQ_label', 'income_total']  
            auto_income = auto_income.merge(income_totals, on='incQ_label')
            auto_income['share_pct'] = (auto_income['freq'] / auto_income['income_total'] * 100).round(2)
            
            results['auto_by_income'] = auto_income
            print(f"Auto ownership by income calculated: {len(auto_income)} combinations")
    
    return results

# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def create_mode_share_barchart(mode_data, title, output_path):
    """Create bar chart visualization for mode shares."""
    
    if mode_data.empty:
        print(f"No data available for {title}")
        return
    
    # Sort by frequency for better visualization
    mode_data = mode_data.sort_values('freq', ascending=True)  # ascending for horizontal bar
    
    # Calculate percentages
    if 'share_pct' in mode_data.columns:
        percentages = mode_data['share_pct']
    elif 'share' in mode_data.columns:
        percentages = mode_data['share']
    else:
        total_trips = mode_data['freq'].sum()
        percentages = (mode_data['freq'] / total_trips * 100)
    
    # Create horizontal bar chart
    fig = go.Figure(go.Bar(
        x=mode_data['freq'],
        y=mode_data['mode_label'],
        orientation='h',
        text=[f"{freq:,.0f} trips ({pct:.1f}%)" 
              for freq, pct in zip(mode_data['freq'], percentages)],
        textposition='outside',
        customdata=percentages,
        hovertemplate="<b>%{y}</b><br>" +
                      "Trips: %{x:,.0f}<br>" + 
                      "Share: %{customdata:.1f}%<br>" +
                      "<extra></extra>",
        marker=dict(color='steelblue')
    ))
    
    fig.update_layout(
        title=f"<b>{title}</b><br><sup>TM2 Mode Share Analysis</sup>",
        xaxis_title="Number of Trips",
        yaxis_title="Travel Mode",
        font_size=12,
        width=1200,
        height=max(600, len(mode_data) * 40),  # Dynamic height based on number of modes
        margin=dict(l=150, r=150, t=100, b=50)
    )
    
    # Save as HTML and PNG
    html_path = output_path.with_suffix('.html')
    png_path = output_path.with_suffix('.png')
    
    fig.write_html(html_path)
    fig.write_image(png_path, width=1200, height=max(600, len(mode_data) * 40))
    
    print(f"Bar chart saved: {html_path}")
    return fig

def create_purpose_mode_barchart(purpose_mode_data, title, output_path):
    """Create bar chart for mode share by trip purpose with proper within-purpose percentages."""
    
    if purpose_mode_data.empty:
        print(f"No data available for {title}")
        return
    
    purpose_col = 'tour_purpose' if 'tour_purpose' in purpose_mode_data.columns else 'purpose'
    
    # Calculate percentages WITHIN each purpose (so each purpose sums to 100%)
    # Use transform to calculate percentage within each purpose group
    purpose_mode_data['within_purpose_pct'] = (
        purpose_mode_data['freq'] / 
        purpose_mode_data.groupby(purpose_col)['freq'].transform('sum') * 100
    )
    
    # Create subplot for each purpose
    purposes = sorted(purpose_mode_data[purpose_col].unique())
    
    rows = len(purposes)
    fig = make_subplots(
        rows=rows, cols=1,
        subplot_titles=[f"{purpose} Trip Purpose" for purpose in purposes],
        vertical_spacing=0.02
    )
    
    for i, purpose in enumerate(purposes, 1):
        purpose_data = purpose_mode_data[purpose_mode_data[purpose_col] == purpose].copy()
        purpose_data = purpose_data.sort_values('within_purpose_pct', ascending=True)
        
        fig.add_trace(
            go.Bar(
                x=purpose_data['within_purpose_pct'],
                y=purpose_data['mode_label'],
                orientation='h',
                text=[f"{pct:.1f}% ({freq:,.0f} trips)" 
                      for pct, freq in zip(purpose_data['within_purpose_pct'], purpose_data['freq'])],
                textposition='outside',
                name=purpose,
                showlegend=False,
                customdata=purpose_data['freq'],
                hovertemplate="<b>%{y}</b><br>" +
                              "Share within " + purpose + ": %{x:.1f}%<br>" +
                              "Trips: %{customdata:,.0f}<br>" +
                              "<extra></extra>",
                marker=dict(color=f'hsl({i*30}, 70%, 50%)')  # Different color for each purpose
            ),
            row=i, col=1
        )
        
        # Update x-axis for this subplot
        fig.update_xaxes(title_text="Percentage (%)" if i == len(purposes) else "", 
                        range=[0, max(100, purpose_data['within_purpose_pct'].max() * 1.1)],
                        row=i, col=1)
        fig.update_yaxes(title_text="", row=i, col=1)
    
    fig.update_layout(
        title=f"<b>{title}</b><br><sup>Mode Share within Each Trip Purpose (each purpose sums to 100%)</sup>",
        height=max(800, rows * 250),
        width=1200,
        font_size=10,
        margin=dict(l=100, r=100, t=100, b=50)
    )
    
    # Save files
    html_path = output_path.with_suffix('.html') 
    png_path = output_path.with_suffix('.png')
    
    fig.write_html(html_path)
    fig.write_image(png_path, width=1200, height=max(800, rows * 250))
    
    print(f"Purpose-mode bar chart saved: {html_path}")
    return fig

def create_trip_purpose_barchart(purpose_data, title, output_path):
    """Create bar chart showing trips by purpose."""
    
    if purpose_data.empty:
        print(f"No data available for {title}")
        return
    
    # Sort by frequency for better visualization
    purpose_data = purpose_data.sort_values('freq', ascending=True)
    
    # Create horizontal bar chart
    fig = go.Figure(go.Bar(
        x=purpose_data['freq'],
        y=purpose_data['tour_purpose'],
        orientation='h',
        text=[f"{freq:,.0f} trips ({pct:.1f}%)" 
              for freq, pct in zip(purpose_data['freq'], purpose_data['share_pct'])],
        textposition='outside',
        customdata=purpose_data['share_pct'],
        hovertemplate="<b>%{y}</b><br>" +
                      "Trips: %{x:,.0f}<br>" + 
                      "Share: %{customdata:.1f}%<br>" +
                      "<extra></extra>",
        marker=dict(color='darkgreen')
    ))
    
    fig.update_layout(
        title=f"<b>{title}</b><br><sup>TM2 Trip Purpose Distribution</sup>",
        xaxis_title="Number of Trips",
        yaxis_title="Trip Purpose",
        font_size=12,
        width=1200,
        height=max(600, len(purpose_data) * 50),  # Dynamic height based on number of purposes
        margin=dict(l=200, r=150, t=100, b=50)
    )
    
    # Save as HTML and PNG
    html_path = output_path.with_suffix('.html')
    png_path = output_path.with_suffix('.png')
    
    fig.write_html(html_path)
    fig.write_image(png_path, width=1200, height=max(600, len(purpose_data) * 50))
    
    print(f"Trip purpose bar chart saved: {html_path}")
    return fig

def create_trip_time_barchart(time_data, title, output_path):
    """Create bar chart showing trips by time period."""
    
    if time_data.empty:
        print(f"No data available for {title}")
        return
    
    # Create horizontal bar chart
    fig = go.Figure(go.Bar(
        x=time_data['freq'],
        y=time_data['timePeriod'],
        orientation='h',
        text=[f"{freq:,.0f} trips ({pct:.1f}%)" 
              for freq, pct in zip(time_data['freq'], time_data['share_pct'])],
        textposition='outside',
        customdata=time_data['share_pct'],
        hovertemplate="<b>%{y}</b><br>" +
                      "Trips: %{x:,.0f}<br>" + 
                      "Share: %{customdata:.1f}%<br>" +
                      "<extra></extra>",
        marker=dict(color='darkorange')
    ))
    
    fig.update_layout(
        title=f"<b>{title}</b><br><sup>TM2 Trip Distribution by Time Period</sup>",
        xaxis_title="Number of Trips",
        yaxis_title="Time Period",
        font_size=12,
        width=1200,
        height=max(400, len(time_data) * 60),  # Dynamic height based on number of periods
        margin=dict(l=150, r=150, t=100, b=50)
    )
    
    # Save as HTML and PNG
    html_path = output_path.with_suffix('.html')
    png_path = output_path.with_suffix('.png')
    
    fig.write_html(html_path)
    fig.write_image(png_path, width=1200, height=max(400, len(time_data) * 60))
    
    print(f"Trip time period bar chart saved: {html_path}")
    return fig

def create_quarto_report(output_dir):
    """Create a Quarto report template in the output directory."""
    
    quarto_content = '''---
title: "TM2 Travel Pattern Analysis Report"
subtitle: "Mode Share and Trip Distribution Summary"
author: "Bay Area Metro - Transportation Planning"
date: "`r Sys.Date()`"
format:
  html:
    toc: true
    toc-depth: 3
    code-fold: true
    theme: cosmo
    fig-width: 12
    fig-height: 8
  pdf:
    toc: true
    fig-width: 10
    fig-height: 6
execute:
  echo: false
  warning: false
  message: false
---

# Executive Summary

This report presents a comprehensive analysis of travel patterns from the Travel Model Two (TM2) transportation demand model. The analysis covers mode share distributions, trip purposes, and temporal travel patterns across the Bay Area region.

## Key Findings

```{python}
#| label: setup
#| include: false

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

# Load analysis results from current directory
excel_file = "tm2_mode_analysis_summary.xlsx"

# Load all analysis results
overall_mode = pd.read_excel(excel_file, sheet_name="Overall Mode Share")
mode_by_purpose = pd.read_excel(excel_file, sheet_name="Mode By Purpose") 
trip_purpose = pd.read_excel(excel_file, sheet_name="Trip Purpose Summary")
trip_time = pd.read_excel(excel_file, sheet_name="Trip Time Summary")

# Calculate key metrics
total_trips = overall_mode['freq'].sum()
top_mode = overall_mode.loc[overall_mode['share_pct'].idxmax(), 'mode_label']
top_mode_share = overall_mode['share_pct'].max()
```

```{python}
#| label: key-metrics

print(f"📊 **Total Daily Trips Analyzed**: {total_trips:,.0f}")
print(f"🚗 **Dominant Travel Mode**: {top_mode} ({top_mode_share:.1f}%)")
print(f"🎯 **Trip Purposes Analyzed**: {len(trip_purpose)} categories")
print(f"⏰ **Time Periods Covered**: {len(trip_time)} periods")
```

# Mode Share Analysis

## Overall Mode Share Distribution

```{python}
#| label: fig-overall-mode
#| fig-cap: "Overall Mode Share Distribution - All Trip Purposes Combined"

# Create overall mode share chart
fig = go.Figure(go.Bar(
    x=overall_mode['freq'],
    y=overall_mode['mode_label'],
    orientation='h',
    text=[f"{freq:,.0f}<br>({pct:.1f}%)" 
          for freq, pct in zip(overall_mode['freq'], overall_mode['share_pct'])],
    textposition='outside',
    marker=dict(color='steelblue')
))

fig.update_layout(
    title="TM2 Overall Mode Share Distribution",
    xaxis_title="Number of Daily Trips",
    yaxis_title="Transportation Mode",
    font_size=12,
    height=600,
    margin=dict(l=200, r=100, t=80, b=50)
)

fig.show()
```

### Mode Share Summary Table

```{python}
#| label: tbl-mode-summary
#| tbl-cap: "Mode Share Summary Statistics"

# Create summary table
mode_summary = overall_mode[['mode_label', 'freq', 'share_pct']].copy()
mode_summary.columns = ['Transportation Mode', 'Daily Trips', 'Share (%)']
mode_summary['Daily Trips'] = mode_summary['Daily Trips'].apply(lambda x: f"{x:,.0f}")
mode_summary['Share (%)'] = mode_summary['Share (%)'].apply(lambda x: f"{x:.1f}%")

print(mode_summary.to_string(index=False))
```

# Trip Purpose Analysis

```{python}
#| label: fig-trip-purpose
#| fig-cap: "Trip Distribution by Purpose"

# Sort by frequency for better visualization
purpose_sorted = trip_purpose.sort_values('freq', ascending=True)

fig = go.Figure(go.Bar(
    x=purpose_sorted['freq'],
    y=purpose_sorted['tour_purpose'],
    orientation='h',
    text=[f"{freq:,.0f}<br>({pct:.1f}%)" 
          for freq, pct in zip(purpose_sorted['freq'], purpose_sorted['share_pct'])],
    textposition='outside',
    marker=dict(color='darkgreen')
))

fig.update_layout(
    title="Daily Trips by Trip Purpose",
    xaxis_title="Number of Daily Trips",
    yaxis_title="Trip Purpose",
    font_size=12,
    height=500,
    margin=dict(l=200, r=150, t=80, b=50)
)

fig.show()
```

# Temporal Travel Patterns

```{python}
#| label: fig-time-periods
#| fig-cap: "Trip Distribution by Time Period"

# Time period labels for better presentation
time_labels = {
    'EA': 'Early AM (3-6 AM)',
    'AM': 'AM Peak (6-10 AM)', 
    'MD': 'Midday (10 AM-3 PM)',
    'PM': 'PM Peak (3-7 PM)',
    'EV': 'Evening (7 PM-3 AM)'
}

trip_time_labeled = trip_time.copy()
trip_time_labeled['time_label'] = trip_time_labeled['timePeriod'].map(time_labels).fillna(trip_time_labeled['timePeriod'])

fig = go.Figure(go.Bar(
    x=trip_time_labeled['freq'],
    y=trip_time_labeled['time_label'],
    orientation='h',
    text=[f"{freq:,.0f}<br>({pct:.1f}%)" 
          for freq, pct in zip(trip_time_labeled['freq'], trip_time_labeled['share_pct'])],
    textposition='outside',
    marker=dict(color='darkorange')
))

fig.update_layout(
    title="Daily Trips by Time Period",
    xaxis_title="Number of Daily Trips",
    yaxis_title="Time Period",
    font_size=12,
    height=400,
    margin=dict(l=250, r=150, t=80, b=50)
)

fig.show()
```

---

*Report generated using the tm2py-utils analysis toolkit*

*To render this report: `quarto render tm2_analysis_report.qmd`*
'''
    
    qmd_path = output_dir / "tm2_analysis_report.qmd"
    with open(qmd_path, 'w') as f:
        f.write(quarto_content)
    
    print(f"Quarto report template created: {qmd_path}")
    return qmd_path

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='TM2 Mode Share Analysis')
    parser.add_argument('--data-dir', required=True, help='Path to TM2 core summaries directory')
    parser.add_argument('--output-dir', required=False, help='Output directory for results (default: creates "agg" subdirectory in data-dir)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("TM2 MODE SHARE ANALYSIS")
    print("=" * 70)
    
    # Create output directory - default to 'agg' subdirectory in data directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        data_dir_path = Path(args.data_dir)
        output_dir = data_dir_path / "agg"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    
    # Load data
    files_data = load_tm2_data(args.data_dir)
    
    if not files_data:
        print("No TM2 data files found. Check the data directory path.")
        return
    
    # Analyze mode shares
    print("\n" + "=" * 50)
    print("ANALYZING MODE SHARES")  
    print("=" * 50)
    
    mode_results = analyze_mode_shares(files_data)
    demo_results = analyze_demographics(files_data)
    
    # Create visualizations
    print("\n" + "=" * 50)
    print("CREATING VISUALIZATIONS")
    print("=" * 50)
    
    # Overall mode share bar chart
    if 'overall_mode_share' in mode_results:
        create_mode_share_barchart(
            mode_results['overall_mode_share'],
            "Overall Mode Share",
            output_dir / "mode_share_overall"
        )
    
    # Mode by purpose bar chart
    if 'mode_by_purpose' in mode_results:
        create_purpose_mode_barchart(
            mode_results['mode_by_purpose'],
            "Mode Share by Trip Purpose", 
            output_dir / "mode_share_by_purpose"
        )
    
    # Trip purpose summary bar chart
    if 'trip_purpose_summary' in mode_results:
        create_trip_purpose_barchart(
            mode_results['trip_purpose_summary'],
            "Trips by Purpose",
            output_dir / "trips_by_purpose"
        )
    
    # Trip time period summary bar chart
    if 'trip_time_summary' in mode_results:
        create_trip_time_barchart(
            mode_results['trip_time_summary'],
            "Trips by Time Period",
            output_dir / "trips_by_time_period"
        )
    
    # Create summary Excel file
    excel_path = output_dir / "tm2_mode_analysis_summary.xlsx"
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        
        for name, df in mode_results.items():
            sheet_name = name.replace('_', ' ').title()[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        for name, df in demo_results.items():
            sheet_name = name.replace('_', ' ').title()[:31] 
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print(f"\nExcel summary saved: {excel_path}")
    
    # Generate Quarto report template
    create_quarto_report(output_dir)
    
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE!")
    print("=" * 70)
    print(f"Results saved to: {output_dir}")
    print("Generated files:")
    print("  - mode_share_overall.html/png")
    print("  - mode_share_by_purpose.html/png") 
    print("  - trips_by_purpose.html/png")
    print("  - trips_by_time_period.html/png")
    print("  - tm2_mode_analysis_summary.xlsx")
    print("  - tm2_analysis_report.qmd (Quarto report template)")

if __name__ == "__main__":
    main()