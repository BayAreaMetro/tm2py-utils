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

### 1. Create Virtual Environment

```powershell
# Create environment
python -m venv cityphi_work

# Activate
.\cityphi_work\Scripts\Activate.ps1

# Install packages
pip install -r requirements.txt
```

### 2. Install CityPhi

CityPhi must be installed from your EMME installation:

```powershell
# Adjust path to your EMME installation
pip install "C:\Program Files\INRO\Emme\Emme 4.6.2\Python312-64\Lib\site-packages\cityphi_*"
```

## Data Requirements

The notebook expects the following data structure:

```
data/
├── maz_shapefile/          # MAZ zone boundaries (.shp, .dbf, etc.)
└── ctramp_output/
    └── indiv_trip.csv      # Individual trip records from CTRAMP
```

### MAZ Shapefile
- Should contain MAZ zone geometries
- Coordinate system will be reprojected to Web Mercator (EPSG:3857)

### Individual Trip Data
Expected columns:
- `dest_mgra`: Destination MAZ ID
- `stop_period`: Time period (1-48, 30-minute periods starting at 3:00 AM)
- `dest_purpose`: Trip purpose (string)

## Usage

1. Update data paths in the notebook:
   ```python
   maz_shapefile_path = "path/to/your/maz/shapefile"
   trip_data_path = "path/to/your/ctramp_output"
   ```

2. Launch Jupyter:
   ```powershell
   jupyter notebook notebooks/MTC_CityPhi_Tutorial.ipynb
   ```

3. Select the `cityphi_work` kernel

4. Run cells sequentially

## Notes

- CityPhi window may open behind other windows when launched
- Large datasets may take time to load and render
- Sections requiring network/trajectory data are marked to skip

## Troubleshooting

**Kernel Selection Issues:**
- Ensure you're using the Python interpreter from `cityphi_work` environment
- In VS Code: Click kernel selector → Python Environments → Choose cityphi_work

**CityPhi Not Found:**
- Verify CityPhi is installed from EMME
- Check that cityphi packages are in your environment

**Data Loading Errors:**
- Verify shapefile paths
- Check column names in your data match expected format
- Ensure MAZ IDs in trips match those in shapefile

## License

[License TBD]

## Contact

MTC - Metropolitan Transportation Commission
