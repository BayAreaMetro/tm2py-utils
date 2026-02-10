
from pathlib import Path
import os
import pandas as pd
import geopandas as gpd

# Import configuration from setup module
from setup import (
    MAZ_TAZ_DIR, 
    ANALYSIS_CRS,
    M_DRIVE_BASE,
    MAZ_VERSION
)

# Loaders
def load_maz_shp(use_maz_orig=False):
    """
    Loads the MAZ shapefile. Uses the original MAZ file if use_maz_orig is True, 
    otherwise loads the default version 2.5 shapefile.
    
    Args:
        use_maz_orig (bool): If True, loads MAZ v2.2 shapefile. Otherwise loads version from setup.MAZ_VERSION.
    
    Returns:
        GeoDataFrame: MAZ polygons with MAZ_NODE, TAZ_NODE, and geometry columns.
    """
    print(f"Loading MAZ shapefile...")
    if use_maz_orig:
        maz_path = M_DRIVE_BASE / "GIS layers" / "TM2_maz_taz_v2.2" / "mazs_TM2_v2_2.shp"
        maz = gpd.read_file(maz_path).to_crs(ANALYSIS_CRS)
        maz = maz.rename(columns={"maz": "MAZ_NODE", "taz": "TAZ_NODE"})
        print(f"  Loaded MAZ v2.2 from: {maz_path}")
    else:
        maz_shp = os.path.join(MAZ_TAZ_DIR, f"mazs_TM2_{MAZ_VERSION}.shp")
        maz = gpd.read_file(maz_shp).to_crs(ANALYSIS_CRS)
        print(f"  Loaded MAZ v{MAZ_VERSION} from: {maz_shp}")

    maz = maz[["MAZ_NODE", "TAZ_NODE", "geometry"]]
    print(f"  MAZ count: {len(maz)}")
    print(f"  MAZ dtypes:\n{maz.dtypes}")

    return maz


def spatial_join_to_maz(points_gdf, maz_gdf):
    """
    Spatially joins point features to MAZ polygons using a two-step approach:
    1. Join points within MAZ polygons (fast, catches majority)
    2. Join remaining points to nearest MAZ (catches edge cases)
    
    This ensures every point gets assigned to a MAZ, even if slightly outside polygon boundaries
    due to geocoding errors or topology issues.
    
    Args:
        points_gdf (GeoDataFrame): Point features to join to MAZ (e.g., firms, schools).
        maz_gdf (GeoDataFrame): MAZ polygons with MAZ_NODE and TAZ_NODE columns.
    
    Returns:
        DataFrame: Input points with added MAZ_NODE and TAZ_NODE columns (geometry dropped).
    """
    print(f"Spatially joining {len(points_gdf)} points to MAZ...")
    
    # Step 1: Spatial join using 'within' predicate (points inside MAZ polygons)
    joined = gpd.sjoin(points_gdf, maz_gdf, how="left", predicate="within")
    joined = joined.drop(columns=['index_right'], errors='ignore')
    
    matched_count = joined["MAZ_NODE"].notnull().sum()
    print(f"  Step 1 (within): {matched_count:,} / {len(points_gdf):,} points matched to MAZ")
    
    # Step 2: Nearest neighbor join for unmatched points
    unmatched = joined[joined["MAZ_NODE"].isnull()]
    if len(unmatched) > 0:
        print(f"  Step 2 (nearest): Assigning {len(unmatched):,} unmatched points to nearest MAZ...")
        
        # Prepare unmatched subset as GeoDataFrame, drop null MAZ/TAZ columns
        unmatched_gdf = gpd.GeoDataFrame(
            unmatched, 
            geometry="geometry", 
            crs=points_gdf.crs
        ).drop(columns=["MAZ_NODE", "TAZ_NODE"], errors='ignore')
        
        # Nearest neighbor spatial join
        nearest_joined = gpd.sjoin_nearest(unmatched_gdf, maz_gdf, how="left")
        nearest_joined = nearest_joined.drop(columns=['index_right'], errors='ignore')
        
        # Convert to DataFrame and concatenate with successfully matched points
        nearest_joined = pd.DataFrame(nearest_joined)
        matched = pd.DataFrame(joined[joined["MAZ_NODE"].notnull()])
        joined = pd.concat([matched, nearest_joined], ignore_index=True)
        
        still_unmatched = joined["MAZ_NODE"].isnull().sum()
        if still_unmatched > 0:
            print(f"  WARNING: {still_unmatched} points still unmatched after nearest join!")
        else:
            print(f"  Step 2 complete: All points now assigned to MAZ")
    
    total_matched = joined["MAZ_NODE"].notnull().sum()
    print(f"  Final: {total_matched:,} / {len(points_gdf):,} points assigned to MAZ")
    
    return joined