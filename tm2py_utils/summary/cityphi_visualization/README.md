# CityPhi Visualization for MTC Travel Model

Interactive 3D visualization of MTC travel model outputs using CityPhi.

## Overview

This package provides a Jupyter notebook tutorial for visualizing MTC travel model data (MAZ zones, individual trips) using CityPhi from Bentley Systems.

## Features

- 3D visualization of MAZ zone centroids
- Individual trip visualization with stacking
- Time-based animation
- Color-coding by trip purpose
- Interactive filtering and querying

## Prerequisites

- Python 3.11+
- CityPhi (from EMME installation)
- Windows OS (CityPhi requirement)

## Installation

### Automated Setup (Recommended)

Run the setup script to automatically create the environment and install packages:

```powershell
cd tm2py_utils/summary/cityphi_visualization
.\setup_env.ps1
```

The script will:
- Create a virtual environment
- Install all Python packages from requirements.txt
- Optionally install CityPhi from your EMME installation
- Provide next steps

### Manual Setup

**Step 1: Create and Activate Virtual Environment**

```powershell
# Navigate to this directory
cd tm2py_utils/summary/cityphi_visualization

# Create virtual environment (can use any name)
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Or activate (Windows Command Prompt)
.\venv\Scripts\activate.bat
```

**Step 2: Install Python Packages**

```powershell
pip install -r requirements.txt
```

**Step 3: Install CityPhi from EMME**

CityPhi cannot be installed from PyPI. Install it from your local EMME installation:

```powershell
# Find your EMME installation path - common locations:
# C:\Program Files\INRO\Emme\Emme 4.6.2\Python312-64\Lib\site-packages\
# C:\Program Files\INRO\Emme\Emme 4.6.1\Python311-64\Lib\site-packages\

# Install all CityPhi packages (adjust path to your EMME version)
pip install "C:\Program Files\INRO\Emme\Emme 4.6.2\Python312-64\Lib\site-packages\cityphi_emme-"*.whl
pip install "C:\Program Files\INRO\Emme\Emme 4.6.2\Python312-64\Lib\site-packages\cityphi_engine-"*.whl
pip install "C:\Program Files\INRO\Emme\Emme 4.6.2\Python312-64\Lib\site-packages\cityphi_studio-"*.whl

# Or install all at once with wildcard:
pip install "C:\Program Files\INRO\Emme\Emme 4.6.2\Python312-64\Lib\site-packages\cityphi_"*.whl
```

**Step 4: Verify Installation**

Open the notebook and run the first code cell to verify all packages are installed correctly.

### Alternative: Use Existing Environment

If you already have an environment with CityPhi installed:
1. Activate that environment
2. Install any missing packages: `pip install -r requirements.txt`
3. Select that kernel when running the notebook

## Data Requirements

The notebook supports flexible data path configuration. See `data/README.md` for details.

### Quick Setup (Recommended)

Place your data files in the `data/` directory:

```
data/
├── maz_shapes/             # MAZ zone boundaries (.shp, .dbf, etc.)
└── trips/
    └── indiv_trip.csv      # Individual trip records from CTRAMP
```

### Alternative Setup

**Option 1: Environment Variables** (best for teams)
```powershell
$env:CITYPHI_MAZ_DATA = "C:\your\path\to\maz_shapefiles"
$env:CITYPHI_TRIP_DATA = "C:\your\path\to\trip_data"
jupyter notebook
```

**Option 2: Edit Notebook**
Uncomment and modify the absolute path configuration in the second code cell.

### Data Details

### Data Details

### MAZ Shapefile
- Should contain MAZ zone geometries
- Coordinate system will be reprojected to Web Mercator (EPSG:3857)

### Individual Trip Data
Expected columns:
- `dest_mgra`: Destination MAZ ID
- `stop_period`: Time period (1-48, 30-minute periods starting at 3:00 AM)
- `dest_purpose`: Trip purpose (string)

## Usage

### Quick Start

1. **Set up Python environment** (see Installation above)

2. **Set up your data** (see Data Requirements section)

3. **Launch Jupyter:**
   ```powershell
   # Make sure your virtual environment is activated
   jupyter notebook notebooks/MTC_CityPhi_Tutorial.ipynb
   ```

4. **Select your kernel:**
   - In Jupyter: Kernel → Change kernel → Select your environment
   - In VS Code: Click kernel selector (top right) → Select your Python environment

5. **Run the verification cell** to check that all packages are installed

6. **Run cells sequentially** through the tutorial

### Portable Setup

The notebook now uses relative paths by default, making it work across different machines without modification. Simply:
- Clone the repository
- Set up the virtual environment
- Place data in `data/maz_shapes/` and `data/trips/`
- Run the notebook

For team projects where data is in different locations, use environment variables.

## Notes

- CityPhi window may open behind other windows when launched
- Large datasets may take time to load and render
- Sections requiring network/trajectory data are marked to skip

## Troubleshooting

### Environment Issues

**"CityPhi not found" error:**
- CityPhi must be installed manually from your EMME installation (see Installation Step 3)
- Verify EMME is installed and locate the cityphi wheel files
- Make sure you're using the correct Python version (match EMME's Python version)

**"Module not found" errors:**
- Ensure your virtual environment is activated
- Run: `pip install -r requirements.txt`
- Check the verification cell output in the notebook

**Wrong Python version:**
- CityPhi requires Python 3.11 or 3.12 (depending on EMME version)
- Create a new environment with the correct Python version:
  ```powershell
  py -3.12 -m venv venv  # Use Python 3.12
  ```

**Kernel not showing in Jupyter/VS Code:**
- Install ipykernel in your environment: `pip install ipykernel`
- Register the kernel: `python -m ipykernel install --user --name=cityphi_env`
- Restart Jupyter/VS Code

### Data Issues

**"No such file or directory" for data paths:**
- Check that data is in the `data/` folder (see data/README.md)
- Or set environment variables before launching Jupyter
- Or edit the configuration cell with absolute paths

**Shapefile coordinate system errors:**
- Ensure your shapefile has a `.prj` file
- CityPhi will reproject to Web Mercator automatically

**Data Loading Errors:**
- Verify shapefile paths
- Check column names in your data match expected format
- Ensure MAZ IDs in trips match those in shapefile

## License

[License TBD]

## Contact

MTC - Metropolitan Transportation Commission
