"""
Geocode parking scrape data using GeoPandas

This script:
1. Reads parking scrape CSV data from interim cache
2. Cleans addresses (removes parenthetical content)
3. Geocodes addresses using Nominatim via GeoPandas
4. Saves results as GeoPackage with geometry column to interim cache
5. Flags failed geocodes while keeping all records

Dependencies:
- geopandas
- pandas
- tqdm
"""

import pandas as pd
import geopandas as gpd
from tqdm import tqdm
import time

# Import configuration
from setup import INTERIM_CACHE_DIR, ensure_directories

# Configuration
INPUT_FILE = 'parking_scrape_location_cost.csv'
OUTPUT_FILE = 'parking_scrape_location_cost.parquet'


# Nominatim configuration
USER_AGENT = 'tm2py_parking_geocoder_bayarea'
TIMEOUT = 10


def clean_address(address):
    """Remove parenthetical content from address
    
    Examples:
    - "123 Main St (enter on Oak)" -> "123 Main St"
    - "456 Broadway" -> "456 Broadway"
    """
    if pd.isna(address) or address == '':
        return ''
    
    # Take everything before first '('
    if '(' in address:
        address = address.split('(')[0]
    
    return address.strip()


def build_full_address(row):
    """Build full address string for geocoding
    
    Format: {cleaned_address}, {city}, CA, USA
    """
    cleaned = clean_address(row['address'])
    if not cleaned or pd.isna(row['city']):
        return None
    
    return f"{cleaned}, {row['city']}, CA, USA"


def geocode_parking_data():
    """Main function to geocode parking data"""
    
    ensure_directories()
    
    print("="*70)
    print("Geocoding Bay Area Parking Scrape Data")
    print("="*70)
    
    # Read input CSV
    input_path = INTERIM_CACHE_DIR / INPUT_FILE
    print(f"\nReading data from:\n  {input_path}")
    
    try:
        df = pd.read_csv(input_path)
        print(f"  ✓ Loaded {len(df)} records")
    except FileNotFoundError:
        print(f"  ✗ ERROR: File not found: {input_path}")
        return
    
    # Drop latitude/longitude columns if they exist
    cols_to_drop = [col for col in ['latitude', 'longitude'] if col in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
        print(f"  ✓ Removed columns: {', '.join(cols_to_drop)}")
    
    # Clean addresses and build full address strings
    print("\nPreparing addresses for geocoding...")
    tqdm.pandas(desc="Cleaning addresses")
    df['full_address'] = df.progress_apply(build_full_address, axis=1)
    
    # Count valid addresses
    valid_addresses = df['full_address'].notna().sum()
    print(f"  ✓ {valid_addresses}/{len(df)} addresses ready for geocoding")
    
    if valid_addresses == 0:
        print("  ✗ ERROR: No valid addresses to geocode")
        return
    
    # Geocode addresses
    print(f"\nGeocoding addresses using Nominatim (OpenStreetMap)...")
    print(f"  Provider: Nominatim")
    print(f"  User agent: {USER_AGENT}")
    print(f"  Timeout: {TIMEOUT}s")
    print(f"  Note: This may take several minutes due to rate limiting...")
    
    # Filter to only rows with valid addresses
    df_to_geocode = df[df['full_address'].notna()].copy()
    
    try:
        # Geocode using geopandas
        print(f"\n  Geocoding {len(df_to_geocode)} addresses...")
        start_time = time.time()
        
        # GeoPandas geocode returns a GeoDataFrame with geometry column
        geocoded_gdf = gpd.tools.geocode(
            df_to_geocode['full_address'],
            provider='nominatim',
            user_agent=USER_AGENT,
            timeout=TIMEOUT
        )
        
        elapsed = time.time() - start_time
        print(f"  ✓ Geocoding completed in {elapsed/60:.1f} minutes")
        
        # Merge geometry back to original DataFrame
        df_to_geocode['geometry'] = geocoded_gdf['geometry'].values
        
        # For rows that weren't geocoded, add empty geometry
        df_not_geocoded = df[df['full_address'].isna()].copy()
        df_not_geocoded['geometry'] = None
        
        # Combine back together
        df_final = pd.concat([df_to_geocode, df_not_geocoded], ignore_index=True)
        
        # Convert to GeoDataFrame first (needed for geometry operations)
        gdf_all = gpd.GeoDataFrame(df_final, geometry='geometry', crs='EPSG:4326')
        
        # Add geocoded flag - check for valid, non-empty geometry
        # Use apply to handle each geometry safely
        def is_valid_geometry(geom):
            if geom is None or pd.isna(geom):
                return False
            try:
                return not geom.is_empty
            except:
                return False
        
        gdf_all['geocoded'] = gdf_all['geometry'].apply(is_valid_geometry)
        
        # Filter to only successfully geocoded records with valid geometry
        gdf = gdf_all[gdf_all['geocoded'] == True].copy()
        
    except Exception as e:
        print(f"  ✗ ERROR during geocoding: {e}")
        return
    
    # Print summary statistics
    print("\n" + "="*70)
    print("GEOCODING SUMMARY")
    print("="*70)
    
    total_attempted = len(gdf_all)
    total_records = len(gdf)
    failed_count = total_attempted - total_records
    success_rate = (total_records / total_attempted * 100) if total_attempted > 0 else 0
    
    print(f"\nTotal records attempted: {total_attempted}")
    print(f"Successfully geocoded:    {total_records} ({success_rate:.1f}%)")
    print(f"Failed to geocode:        {failed_count} ({100-success_rate:.1f}%)")
    print(f"\nNote: Only successfully geocoded records will be saved.")
    
    # Breakdown by city (using all attempted records)
    print("\nGeocoding success by city:")
    city_summary = gdf_all.groupby('city')['geocoded'].agg(['count', 'sum'])
    city_summary.columns = ['Total', 'Geocoded']
    city_summary['Failed'] = city_summary['Total'] - city_summary['Geocoded']
    city_summary['Success %'] = (city_summary['Geocoded'] / city_summary['Total'] * 100).round(1)
    print(city_summary.to_string())
    
    # Breakdown by parking type (using all attempted records)
    print("\nGeocoding success by parking type:")
    type_summary = gdf_all.groupby('parking_type')['geocoded'].agg(['count', 'sum'])
    type_summary.columns = ['Total', 'Geocoded']
    type_summary['Failed'] = type_summary['Total'] - type_summary['Geocoded']
    type_summary['Success %'] = (type_summary['Geocoded'] / type_summary['Total'] * 100).round(1)
    print(type_summary.to_string())
    
    # Show sample of failed geocodes if any
    if failed_count > 0:
        print(f"\nSample of failed geocodes (first 5):")
        failed_samples = gdf_all[~gdf_all['geocoded']][['city', 'address', 'full_address']].head()
        print(failed_samples.to_string(index=False))
    
    # Save to Parquet
    output_path = INTERIM_CACHE_DIR / OUTPUT_FILE
    print(f"\nSaving results to:\n  {output_path}")
    
    try:
        gdf.to_parquet(output_path)
        print(f"  ✓ Saved {len(gdf)} records as Parquet")
        print(f"  ✓ CRS: {gdf.crs}")
        print(f"  ✓ Columns: {', '.join(gdf.columns.tolist())}")
    except Exception as e:
        print(f"  ✗ ERROR saving file: {e}")
        return
    
    print("\n" + "="*70)
    print("Geocoding complete!")
    print("="*70)


if __name__ == "__main__":
    # Run geocoding
    geocode_parking_data()


#%% Load parquet and create simple map

# import folium
# from folium import plugins

# MAP_OUTPUT_FILE = 'parking_scrape_map.html'
# INPUT_DIR = r'E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse'
# OUTPUT_FILE = 'parking_scrape_location_cost.parquet'

# # Load geocoded data
# gdf = gpd.read_parquet(f"{INPUT_DIR}\\{OUTPUT_FILE}")
# # Filter to only successfully geocoded records with valid geometry
# gdf_geocoded = gdf[
#     (gdf['geocoded'] == True) & 
#     (gdf['geometry'].notna()) & 
#     (~gdf['geometry'].is_empty)
# ].copy()

# print(f"Loaded {len(gdf)} total records")
# print(f"Mapping {len(gdf_geocoded)} successfully geocoded records")

# # Create simple folium map
# center_lat = gdf_geocoded.geometry.y.mean()
# center_lon = gdf_geocoded.geometry.x.mean()

# m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

# # Add markers
# for idx, row in gdf_geocoded.iterrows():
#     folium.CircleMarker(
#         location=[row.geometry.y, row.geometry.x],
#         radius=5,
#         popup=f"{row['address']}, {row['city']}",
#         color='blue',
#         fill=True,
#         fillOpacity=0.6
#     ).add_to(m)

# # Save map
# m.save(f"{INPUT_DIR}\\{MAP_OUTPUT_FILE}")
# m

