"""
Streamlit Cloud entry point for TM2.2 Validation Dashboard.

This is a simplified entry point for cloud deployment that uses
relative paths and assumes the dashboard data is in the repository.
"""

import sys
from pathlib import Path

# Add the tm2py_utils directory to Python path
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

# Import and run the main dashboard
from tm2py_utils.summary.validation.dashboard_app import main

if __name__ == "__main__":
    main()
