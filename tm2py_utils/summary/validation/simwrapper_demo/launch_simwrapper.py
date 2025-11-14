#!/usr/bin/env python3
"""
Python launcher script for SimWrapper
Handles environment checking and launches SimWrapper properly
"""

import subprocess
import sys
import os
from pathlib import Path


def check_environment():
    """Check if we're in the correct conda environment."""
    try:
        # Check if we can import required packages
        import simwrapper
        import pandas
        print("✓ Required packages available")
        return True
    except ImportError as e:
        print(f"✗ Missing package: {e}")
        print("\nPlease activate the tm2py-utils environment:")
        print("conda activate tm2py-utils")
        return False


def launch_simwrapper():
    """Launch SimWrapper in the current directory."""
    current_dir = Path.cwd()
    
    print(f"Launching SimWrapper from: {current_dir}")
    
    # Check for required files
    required_files = ['dashboard-1-summary.yaml', 'topsheet.yaml']
    missing_files = []
    
    for file in required_files:
        if not (current_dir / file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"⚠ Missing configuration files: {missing_files}")
        print("SimWrapper may not display properly without these files")
    
    # Launch SimWrapper
    try:
        print("Starting SimWrapper...")
        result = subprocess.run(['simwrapper', 'open', '.'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ SimWrapper launched successfully!")
            print("Check your browser - SimWrapper should be opening")
        else:
            print(f"✗ Error launching SimWrapper: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("✗ SimWrapper command not found")
        print("Make sure SimWrapper is installed: pip install simwrapper")
        return False
    except Exception as e:
        print(f"✗ Error launching SimWrapper: {e}")
        return False
    
    return True


def main():
    """Main function."""
    print("SimWrapper Python Launcher")
    print("=" * 30)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Launch SimWrapper
    success = launch_simwrapper()
    
    if success:
        print("\n🎯 SimWrapper should now be running in your browser!")
        print("Press Ctrl+C in this terminal to stop the server when done.")
    else:
        print("\n❌ Failed to launch SimWrapper")
        sys.exit(1)


if __name__ == "__main__":
    main()