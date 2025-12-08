# TM2 PopSim Crosswalk Creator

A unified script to create complete geographic crosswalk files for TM2 PopulationSim without dependencies on the populationsim repository configuration.

## Overview

This script combines the functionality of the previous `create_tm2_crosswalk.py` and `build_complete_crosswalk.py` scripts into a single standalone tool that:

1. **Creates basic crosswalk**: MAZ-TAZ-PUMA-COUNTY spatial mappings using area-based PUMA assignment
2. **Enhances with block data**: Adds census block and block group mappings for demographic data integration
3. **Validates results**: Provides summary statistics and validation reports

## Pipeline Integration

### Automatic Pipeline Integration

The script now automatically detects and writes to the PopulationSim pipeline directory when available.

**Simple usage (recommended):**
```bash
python popsim_tm2_crosswalk_creator.py \
  --maz-shapefile /path/to/maz_shapefile.shp \
  --puma-shapefile /path/to/puma_shapefile.shp \
  --county-shapefile /path/to/county_shapefile.shp \
  --blocks-file /path/to/blocks.csv \
  --verbose
```

**What happens automatically:**
- ✅ If you're in a populationsim repository → writes directly to `output_2023/populationsim_working_dir/data/`
- ✅ If not in a populationsim repo → falls back to `./crosswalk_outputs/`
- ✅ Creates the correct filenames expected by the pipeline
- ✅ No manual copying needed!

### Manual Directory Override

If you want to specify a custom output directory:
```bash
python popsim_tm2_crosswalk_creator.py \
  --maz-shapefile /path/to/maz_shapefile.shp \
  --puma-shapefile /path/to/puma_shapefile.shp \
  --county-shapefile /path/to/county_shapefile.shp \
  --blocks-file /path/to/blocks.csv \
  --output-dir /my/custom/directory \
  --verbose
```

### File Requirements

The pipeline expects exactly these filenames:
- ✅ `geo_cross_walk_tm2_maz.csv` (basic crosswalk)
- ✅ `geo_cross_walk_tm2_block10.csv` (enhanced crosswalk)

## Usage

```bash
python popsim_tm2_crosswalk_creator.py \
  --maz-shapefile /path/to/maz_shapefile.shp \
  --puma-shapefile /path/to/puma_shapefile.shp \
  --county-shapefile /path/to/county_shapefile.shp \
  --blocks-file /path/to/blocks.csv \
  --output-dir /path/to/output/directory \
  --verbose
```

## Required Inputs

1. **MAZ Shapefile**: Contains MAZ geometries with TAZ relationships and county information
2. **PUMA Shapefile**: US Census TIGER/Line PUMA boundaries (2020 vintage recommended)
3. **County Shapefile**: California counties from CA Open Data Portal
4. **Blocks File**: CSV with block GEOIDs and MAZ assignments

## Outputs

- `geo_cross_walk_tm2_maz.csv`: Basic crosswalk (MAZ-TAZ-PUMA-COUNTY)
- `geo_cross_walk_tm2_block10.csv`: Enhanced crosswalk with block/block group mappings
- `*_bg_summary.csv`: Block group validation summary

## Features

- **Standalone**: No external configuration dependencies
- **Area-based PUMA assignment**: Uses spatial intersection areas for accurate TAZ-PUMA mapping
- **Robust geography handling**: Automatically detects column names and handles different shapefile formats
- **Data validation**: Built-in checks for missing mappings and spatial consistency
- **Bay Area specific**: Includes 1-9 county coding system for Bay Area counties

## Example with Typical Paths

```bash
python popsim_tm2_crosswalk_creator.py \
  --maz-shapefile "C:/GitHub/tm2py-utils/tm2py_utils/inputs/maz_taz/TM2_MAZ_TAZ_Bounds/TM2_MAZ_TAZ_Bounds.shp" \
  --puma-shapefile "C:/GitHub/tm2py-utils/tm2py_utils/inputs/maz_taz/shapefiles/tl_2020_06_puma10.shp" \
  --county-shapefile "C:/GitHub/tm2py-utils/tm2py_utils/inputs/maz_taz/shapefiles/california_counties.shp" \
  --blocks-file "C:/GitHub/tm2py-utils/tm2py_utils/inputs/maz_taz/tm2py_mazs_blocks_23.csv" \
  --output-dir "output_2023/populationsim_working_dir/data" \
  --verbose
```

## Dependencies

- Python 3.8+
- geopandas
- pandas
- numpy

## Migration from Previous Scripts

This script replaces:

- `create_tm2_crosswalk.py` (basic crosswalk creation)
- `build_complete_crosswalk.py` (enhanced crosswalk with blocks)

The unified approach provides the same functionality with improved portability and easier maintenance.

