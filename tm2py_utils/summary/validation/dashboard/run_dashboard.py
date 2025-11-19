"""
Simple script to launch the Streamlit dashboard.

Usage:
    python run_dashboard.py
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Launch the Streamlit dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard_app.py"
    
    print("=" * 60)
    print("Launching TM2.2 Validation Dashboard")
    print("=" * 60)
    print(f"Dashboard location: {dashboard_path}")
    print("\nPress Ctrl+C to stop the dashboard")
    print("=" * 60)
    
    subprocess.run([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard_path),
        "--theme.base=light",
        "--theme.primaryColor=#00A19A",  # MTC Teal
        "--theme.backgroundColor=#FFFFFF",
        "--theme.secondaryBackgroundColor=#F0F2F6",
        "--theme.textColor=#262730"
    ])

if __name__ == "__main__":
    main()
