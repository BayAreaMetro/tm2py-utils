"""
Configuration module for MAZ land use input pipeline.

This module defines all paths, constants, and configuration variables
used across the land use data preparation scripts.

Example:
    from tm2py_utils.inputs.land_use.setup import *
"""

from pathlib import Path

# ================================
# Data Versioning
# ================================
MAZ_VERSION = "2_6"  # Options: "2_2", "2_5"
DATA_VINTAGE = "2023"  # Year of input data (employment, enrollment, etc.)

# ================================
# Coordinate Reference Systems
# ================================
ANALYSIS_CRS = "EPSG:26910"  # NAD83 / UTM Zone 10N (Bay Area)
WGS84_CRS = "EPSG:4326"

# ================================
# Directories
# ================================
# Box directory - main storage for land use inputs
BOX_LANDUSE_BASE = Path(r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse")

# M: Drive - jobs data
M_DRIVE_BASE = Path(r"M:\Data")

# Local repository directories
REPO_BASE = Path(__file__).parent.parent  # tm2py_utils/inputs/

# ================================
# Input Data Directories
# ================================
# Raw data directories
RAW_DATA_DIR = Path(r"E:\Box\Modeling and Surveys\Development\raw_base_data\2023")
EMPLOYMENT_RAW_DATA_DIR = M_DRIVE_BASE / "BusinessData"
ENROLLMENT_RAW_DATA_DIR = RAW_DATA_DIR / "enrollment"
PARKING_RAW_DATA_DIR = RAW_DATA_DIR / "parking"

# MAZ/TAZ shapefiles
MAZ_TAZ_DIR = REPO_BASE / "maz_taz" / "shapefiles"

# Synthetic population (for parking prep)
SYNTH_POP_FILE = BOX_LANDUSE_BASE / "maz_data_old.csv"

# ================================
# Output Directories
# ================================
# Interim cache for intermediate pipeline outputs
INTERIM_CACHE_DIR = BOX_LANDUSE_BASE / "interim_cache"

# Final output directory
FINAL_OUTPUT_DIR = BOX_LANDUSE_BASE

# ================================
# Common Constants
# ================================
SQUARE_METERS_PER_ACRE = 4046.86

BAY_AREA_COUNTIES = [
    "Alameda",
    "Contra Costa",
    "Marin",
    "Napa",
    "San Francisco",
    "San Mateo",
    "Santa Clara",
    "Solano",
    "Sonoma"
]

# Census API key (for parking prep - pytidycensus)
CENSUS_API_KEY = "a3928abdddafbb9bbd88399816c55c82337c3ca6"

# ================================
# CPI Constants (use annual averages from https://data.bls.gov/pdq/SurveyOutputServlet)
# ================================


CPI_VALUES = {
    2010: 218.056, # TM2 uses 2010 dollars
    2023: 304.702 # We likely have different dollar years for different cost data sources - settle on 2023
}

# ================================
# Initialization
# ================================
def ensure_directories():
    """Create output directories if they don't exist."""
    import os
    os.makedirs(INTERIM_CACHE_DIR, exist_ok=True)
    os.makedirs(FINAL_OUTPUT_DIR, exist_ok=True)
    print(f"Ensured directories exist:")
    print(f"  Interim cache: {INTERIM_CACHE_DIR}")
    print(f"  Final output: {FINAL_OUTPUT_DIR}")
