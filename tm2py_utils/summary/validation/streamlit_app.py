"""
Streamlit Cloud entry point for TM2.2 Validation Dashboard.

This is a simplified entry point for cloud deployment that uses
relative paths and assumes the dashboard data is in the repository.
"""

import sys
from pathlib import Path
import importlib.util

# Load dashboard_app directly without importing tm2py_utils package
# This avoids triggering heavy dependencies in tm2py_utils.__init__.py
dashboard_path = Path(__file__).parent / "dashboard_app.py"
spec = importlib.util.spec_from_file_location("dashboard_app", dashboard_path)
dashboard_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard_app)

if __name__ == "__main__":
    dashboard_app.main()
