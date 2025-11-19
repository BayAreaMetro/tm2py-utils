"""
Streamlit Cloud entry point for TM2.2 Validation Dashboard.

This file serves as the entry point for Streamlit Cloud deployment.
It simply imports and runs the main dashboard app.
"""

# Import the main dashboard app
from dashboard.dashboard_app import main

if __name__ == "__main__":
    main()
