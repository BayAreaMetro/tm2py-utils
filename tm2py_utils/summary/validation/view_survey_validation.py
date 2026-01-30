"""
Quick launcher for viewing survey validation results in Streamlit dashboard.

Usage:
    streamlit run view_survey_validation.py
"""
import sys
from pathlib import Path

# Add the dashboard directory to path
dashboard_dir = Path(__file__).parent / "archived_validation_system" / "dashboard"
sys.path.insert(0, str(dashboard_dir))

# Import the dashboard app
from dashboard_app import main

# Set default paths for survey data
SURVEY_VALIDATION_DIR = Path(r"C:\GitHub\travel-diary-survey-tools\projects\bats_2023\output\ctramp\validation")

if __name__ == "__main__":
    import streamlit as st
    
    st.set_page_config(
        page_title="Survey Validation Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    # Override validation directory
    st.session_state['validation_dir'] = str(SURVEY_VALIDATION_DIR)
    
    main()
