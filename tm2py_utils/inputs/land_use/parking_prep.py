#%%
import pytidycensus
import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.preprocessing import StandardScaler

# Import job_counts module to get MAZ employment data
from job_counts import get_jobs_maz

# Import utils module directly to avoid loading full package
utils_path = Path(__file__).parent / "utils.py"
import importlib.util
spec = importlib.util.spec_from_file_location("utils", utils_path)
utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils)

ANALYSIS_CRS = "EPSG:26910"
WGS84_CRS = "EPSG:4326"
OUTPUT_DIR = Path(__file__).parent / "outputs"
SQUARE_METERS_PER_ACRE = 4046.86


def load_bay_area_places():
    # Set Census API key
    pytidycensus.set_census_api_key("a3928abdddafbb9bbd88399816c55c82337c3ca6")

    # Load census place geographies for California
    places = pytidycensus.get_acs(
        geography="place",
        variables=["B01001_001E"],  # Total population
        state="CA",
        year=2021,
        geometry=True
    ) 

    counties = pytidycensus.get_acs(
        geography="county",
        variables=["B01001_001E"],  # Total population
        state="CA",
        year=2021,
        geometry=True
    ) 

    COUNTY_FIPS = {
        "Alameda": "001",
        "Contra Costa": "013",
        "Marin": "041",
        "Napa": "055",
        "San Francisco": "075",
        "San Mateo": "081",
        "Santa Clara": "085",
        "Solano": "095",
        "Sonoma": "097",
    }


    counties = counties[counties["county"].isin(COUNTY_FIPS.values())]
    counties = counties.rename(columns={"NAME": "county_name"})

    # Clean up the county name string
    counties["county_name"] = counties["county_name"].str.split("County", n=1).str[0].str.strip()
    counties = counties[["county", "county_name", "geometry"]]

    places = places.rename(columns={"GEOID": "place_id", "NAME": "place_name"})

    places = gpd.sjoin(places, counties, how="inner", predicate="intersects")
    places = places[["place_id", "place_name", "county_name", "geometry"]]

    # Remove unincorporated and towns - using cities as a filter for parking cost prediction
    places = places[~places["place_name"].str.contains("CDP|Town", case=False, na=False)]
    
    # Extract everything before "city" (case insensitive)
    places["place_name"] = places["place_name"].str.split("city", n=1).str[0].str.strip()

    
    # Convert to analysis CRS for spatial operations
    print(f"  Converting places from {places.crs} to {ANALYSIS_CRS}")
    places = places.to_crs(ANALYSIS_CRS)
    
    return places


def load_maz_data():
    # Load MAZ shapefile
    print(f"Loading MAZ shapefile...")
    maz = utils.load_maz_shp().to_crs(ANALYSIS_CRS)
    print(f"  Loaded {len(maz):,} MAZ polygons")
    
    # Calculate acres from geometry
    maz['ACRES'] = maz.geometry.area / SQUARE_METERS_PER_ACRE

    # Load employment data
    print(f"\nLoading MAZ employment data...")
    jobs_maz = get_jobs_maz(write=False)
    print(f"  Loaded employment for {len(jobs_maz):,} MAZs")
    print(f"  Jobs MAZ columns: {list(jobs_maz.columns)[:10]}...")  # Debug: show first 10 columns
    
    # Merge the synthetic pop data - IMPORTANT: UPDATE THIS TO LATEST SYNTH POP
    SYNTH_POP_FILE = Path(r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\maz_data_old.csv")
    pop_maz = pd.read_csv(SYNTH_POP_FILE)
    pop_maz = pop_maz[["MAZ_NODE", "POP", "HH"]]
    
    # Ensure consistent data types for all dataframes
    maz['MAZ_NODE'] = maz['MAZ_NODE'].astype(str)
    maz['TAZ_NODE'] = maz['TAZ_NODE'].astype(str)
    jobs_maz['MAZ_NODE'] = jobs_maz['MAZ_NODE'].astype(str)
    jobs_maz['TAZ_NODE'] = jobs_maz['TAZ_NODE'].astype(str)
    pop_maz['MAZ_NODE'] = pop_maz['MAZ_NODE'].astype(str)

    # Merge job data
    maz = maz.merge(
        jobs_maz[['MAZ_NODE', 'TAZ_NODE', 'emp_total', 'ret_loc', 'ret_reg',
                   'prof', 'fire', 'info', 'serv_bus', 'serv_per', 'gov', 'eat', 'art_rec']], 
        on='MAZ_NODE', 
        how='left',
        validate="1:1"
    )

    # Merge pop/hh data
    maz = maz.merge(pop_maz, on="MAZ_NODE", how='left',
        validate="1:1"
    )

    return maz

def spatial_join_maz_to_place(maz, places):
    # Ensure both are in same CRS
    print(f"  MAZ CRS: {maz.crs}")
    print(f"  Places CRS: {places.crs}")
    
    if maz.crs != places.crs:
        print(f"  WARNING: CRS mismatch! Converting places to {maz.crs}")
        places = places.to_crs(maz.crs)
    
    # Perform spatial overlay to get intersection areas
    print(f"  Performing spatial overlay...")
    overlay = gpd.overlay(maz, places, how='intersection')
    print(f"  Found {len(overlay):,} MAZ-place intersections")
    
    if len(overlay) == 0:
        print("  ERROR: No intersections found! Check geometries and CRS.")
        return maz
    
    # Calculate the area of each intersection
    overlay['intersection_area'] = overlay.geometry.area
    
    # For each MAZ, find the place with the largest intersection area
    idx_max_area = overlay.groupby('MAZ_NODE')['intersection_area'].idxmax()
    maz_place = overlay.loc[idx_max_area, ['MAZ_NODE', 'place_id', 'place_name', 'county_name']]
    print(f"  Assigned {len(maz_place):,} unique MAZs to places")
    
    # Merge back to original MAZ data
    maz = maz.merge(maz_place, on='MAZ_NODE', how='left')
    
    # Report on unmatched MAZs
    unmatched = maz['place_id'].isna().sum()
    if unmatched > 0:
        print(f"  WARNING: {unmatched:,} MAZs did not match any place")
    
    return maz

def merge_scraped_cost(maz):
    """
    Spatially join parking scrape data to MAZ zones and calculate average costs.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have MAZ_NODE)
    
    Returns:
        GeoDataFrame: maz with added dparkcost and mparkcost columns
    """
    INPUT_DIR = Path(r'E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse')
    INPUT_FILE = 'parking_scrape_location_cost.parquet'

    print("Loading parking scrape data...")
    parking_scrape = gpd.read_parquet(INPUT_DIR / INPUT_FILE)
    parking_scrape = parking_scrape[["spot_id", "parking_type", "price_value", "geometry"]]
    print(f"  Loaded {len(parking_scrape):,} parking spots")
    
    # Ensure both are in the same CRS
    print(f"  Parking scrape CRS: {parking_scrape.crs}")
    print(f"  MAZ CRS: {maz.crs}")
    if parking_scrape.crs != maz.crs:
        print(f"  Converting parking scrape to {maz.crs}")
        parking_scrape = parking_scrape.to_crs(maz.crs)
    
    # Spatial join: assign MAZ_NODE to each parking spot
    print("  Performing spatial join...")
    parking_with_maz = gpd.sjoin(
        parking_scrape[['geometry', 'price_value', 'parking_type']], 
        maz[['geometry', 'MAZ_NODE']], 
        how='left',
        predicate='within'
    )
    print(f"  Matched {parking_with_maz['MAZ_NODE'].notna().sum():,} spots to MAZs")
    
    # Group by MAZ_NODE and parking_type, calculate average price
    print("  Calculating average prices by MAZ and parking type...")
    avg_prices = parking_with_maz.groupby(['MAZ_NODE', 'parking_type'])['price_value'].mean().reset_index()
    print(f"  Calculated averages for {len(avg_prices):,} MAZ-parking_type combinations")
    
    # Pivot to get daily and monthly as separate columns
    avg_prices_pivot = avg_prices.pivot(
        index='MAZ_NODE', 
        columns='parking_type', 
        values='price_value'
    ).reset_index()
    
    # Rename columns
    avg_prices_pivot = avg_prices_pivot.rename(columns={
        'daily': 'dparkcost',
        'monthly': 'mparkcost'
    })
    print(f"  Created dparkcost and mparkcost columns")
    
    # Merge back to maz
    print("  Merging parking costs back to MAZ...")
    maz = maz.merge(avg_prices_pivot, on='MAZ_NODE', how='left')
    
    # Report statistics
    mazs_with_daily = maz['dparkcost'].notna().sum()
    mazs_with_monthly = maz['mparkcost'].notna().sum()
    print(f"  MAZs with daily parking cost: {mazs_with_daily:,}/{len(maz):,}")
    print(f"  MAZs with monthly parking cost: {mazs_with_monthly:,}/{len(maz):,}")
    
    if mazs_with_daily > 0:
        print(f"  Daily parking cost range: ${maz['dparkcost'].min():.2f} - ${maz['dparkcost'].max():.2f}")
        print(f"  Daily parking cost mean: ${maz['dparkcost'].mean():.2f}")
    if mazs_with_monthly > 0:
        print(f"  Monthly parking cost range: ${maz['mparkcost'].min():.2f} - ${maz['mparkcost'].max():.2f}")
        print(f"  Monthly parking cost mean: ${maz['mparkcost'].mean():.2f}")
    
    return maz

def merge_published_cost(maz):
    """
    Merge published parking meter costs to MAZ.
    
    Calls published_cost() from parking_published module to get hourly parking costs
    from Oakland, San Jose, and San Francisco meters, then merges to MAZ.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have MAZ_NODE)
    
    Returns:
        GeoDataFrame: maz with added hparkcost column
    """
    from parking_published import published_cost
    
    # Store original count for validation
    original_count = len(maz)
    
    # Get published parking costs
    hparkcost_data = published_cost()
    
    # Ensure consistent data types
    hparkcost_data['MAZ_NODE'] = hparkcost_data['MAZ_NODE'].astype(str)
    
    # Merge to maz (left join to keep all MAZ records)
    print("  Merging published costs to MAZ...")
    maz = maz.merge(
        hparkcost_data[['MAZ_NODE', 'hparkcost']], 
        on='MAZ_NODE', 
        how='left',
        validate="1:1"
    )
    
    # Validate no records were lost
    if len(maz) != original_count:
        print(f"  WARNING: Record count changed from {original_count:,} to {len(maz):,}")
    else:
        print(f"  ✓ All {original_count:,} MAZ records retained")
    
    return maz

def merge_capacity(maz):
    """
    Merge parking capacity data to MAZ and create stall columns.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have MAZ_NODE and mparkcost from merge_scraped_cost)
    
    Returns:
        GeoDataFrame: maz with added parking stall columns
    """
    INPUT_DIR = Path(r'E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse')
    INPUT_FILE = 'parking_capacity.gpkg'

    print("Loading parking capacity data...")
    parking_capacity = gpd.read_file(INPUT_DIR / INPUT_FILE)
    parking_capacity = parking_capacity.drop(columns=["emp_total"])
    print(f"  Loaded capacity data for {len(parking_capacity):,} MAZs")
    
    # Store original count for validation
    original_count = len(maz)
    
    # Ensure consistent data types
    parking_capacity['MAZ_NODE'] = parking_capacity['MAZ_NODE'].astype(str)
    
    # Merge capacity data to maz (left join to keep all MAZ records)
    print("  Merging capacity data to MAZ...")
    maz = maz.merge(
        parking_capacity[['MAZ_NODE', 'on_all', 'off_nres']], 
        on='MAZ_NODE', 
        how='left',
        validate="1:1"
    )
    
    # Validate no records were lost
    if len(maz) != original_count:
        print(f"  WARNING: Record count changed from {original_count:,} to {len(maz):,}")
    else:
        print(f"  ✓ All {original_count:,} MAZ records retained")
    
    # Fill NaN values with 0 for MAZs without capacity data
    maz['on_all'] = maz['on_all'].fillna(0)
    maz['off_nres'] = maz['off_nres'].fillna(0)
    
    # Create hourly stalls columns (on-street parking)
    maz['hstallsoth'] = maz['on_all']
    maz['hstallssam'] = maz['on_all']
    print(f"  Created hourly stalls columns (hstallsoth, hstallssam) from on_all")
    
    # Create daily stalls columns (off-street non-residential)
    maz['dstallsoth'] = maz['off_nres']
    maz['dstallssam'] = maz['off_nres']
    print(f"  Created daily stalls columns (dstallsoth, dstallssam) from off_nres")
    
    # Create monthly stalls columns (off-street non-residential, only where monthly parking cost exists)
    # Fill NaN in mparkcost with 0 for comparison
    maz['mparkcost'] = maz['mparkcost'].fillna(0)
    maz['mstallsoth'] = maz['off_nres'].where(maz['mparkcost'] > 0, 0)
    maz['mstallssam'] = maz['off_nres'].where(maz['mparkcost'] > 0, 0)
    print(f"  Created monthly stalls columns (mstallsoth, mstallssam) from off_nres where mparkcost > 0")
    
    # Report statistics
    total_mazs = len(maz)
    mazs_with_hourly = (maz['hstallsoth'] > 0).sum()
    mazs_with_daily = (maz['dstallsoth'] > 0).sum()
    mazs_with_monthly = (maz['mstallsoth'] > 0).sum()
    
    print(f"  MAZs with hourly stalls: {mazs_with_hourly:,}/{total_mazs:,}")
    print(f"  MAZs with daily stalls: {mazs_with_daily:,}/{total_mazs:,}")
    print(f"  MAZs with monthly stalls: {mazs_with_monthly:,}/{total_mazs:,}")
    
    if mazs_with_hourly > 0:
        print(f"  Total hourly stalls: {maz['hstallsoth'].sum():,.0f}")
    if mazs_with_daily > 0:
        print(f"  Total daily stalls: {maz['dstallsoth'].sum():,.0f}")
    if mazs_with_monthly > 0:
        print(f"  Total monthly stalls: {maz['mstallsoth'].sum():,.0f}")
    
    return maz


def add_density_features(maz):
    """
    Add employment density features for parking cost estimation.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have employment columns and ACRES)
    
    Returns:
        GeoDataFrame: maz with added density feature columns
    """
    print("Calculating density features for parking cost estimation...")
    
    # Define retail and service employment for commercial areas
    # ret_loc, ret_reg: retail (local and regional)
    # eat: restaurants
    # serv_bus, serv_per: business and personal services
    maz['commercial_emp'] = (
        maz['ret_loc'] + maz['ret_reg'] + maz['eat'] + 
        maz['serv_bus'] + maz['serv_per']
    )
    
    # Define downtown/office employment
    # prof: professional services, fire: finance/insurance/real estate
    # info: information, gov: government
    # art_rec: arts and recreation
    maz['downtown_emp'] = (
        maz['prof'] + maz['fire'] + maz['info'] + 
        maz['serv_bus'] + maz['gov'] + maz['art_rec'] + maz['eat']
    )
    
    # Calculate densities (jobs per acre)
    # Use np.where to avoid division by zero
    maz['commercial_emp_den'] = np.where(
        maz['ACRES'] > 0,
        maz['commercial_emp'] / maz['ACRES'],
        0
    )
    
    maz['downtown_emp_den'] = np.where(
        maz['ACRES'] > 0,
        maz['downtown_emp'] / maz['ACRES'],
        0
    )
    
    maz['emp_total_den'] = np.where(
        maz['ACRES'] > 0,
        maz['emp_total'] / maz['ACRES'],
        0
    )
    
    # Report statistics
    print(f"  Commercial employment density (jobs/acre):")
    print(f"    Mean: {maz['commercial_emp_den'].mean():.2f}")
    print(f"    Median: {maz['commercial_emp_den'].median():.2f}")
    print(f"    90th percentile: {maz['commercial_emp_den'].quantile(0.90):.2f}")
    print(f"    95th percentile: {maz['commercial_emp_den'].quantile(0.95):.2f}")
    
    print(f"  Downtown employment density (jobs/acre):")
    print(f"    Mean: {maz['downtown_emp_den'].mean():.2f}")
    print(f"    Median: {maz['downtown_emp_den'].median():.2f}")
    print(f"    90th percentile: {maz['downtown_emp_den'].quantile(0.90):.2f}")
    print(f"    95th percentile: {maz['downtown_emp_den'].quantile(0.95):.2f}")
    
    return maz


def report_county_density_distributions(maz):
    """
    Report commercial employment density distributions by county for MAZs with off-street capacity.
    
    Shows percentile thresholds per county to inform daily vs monthly parking cost estimation.
    Only includes MAZs with off_nres > 0 and place_name not null.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have county_name, commercial_emp_den, off_nres)
    """
    print("\n" + "="*80)
    print("COUNTY-LEVEL COMMERCIAL EMPLOYMENT DENSITY DISTRIBUTIONS")
    print("="*80)
    print("For MAZs with off-street parking capacity (off_nres > 0) in cities")
    print()
    
    # Filter to MAZs with off-street capacity and in cities
    eligible_mazs = maz[(maz['off_nres'] > 0) & (maz['place_name'].notna()) & (maz['county_name'].notna())].copy()
    
    print(f"Total eligible MAZs: {len(eligible_mazs):,}\n")
    
    # Cities with observed data
    OBSERVED_CITIES = ['San Francisco', 'Oakland', 'San Jose']
    
    # Calculate percentiles by county
    county_stats = []
    
    for county in sorted(eligible_mazs['county_name'].unique()):
        county_mazs = eligible_mazs[eligible_mazs['county_name'] == county]
        
        # Check if county has observed data cities
        has_observed = county_mazs['place_name'].isin(OBSERVED_CITIES).any()
        observed_cities = county_mazs[county_mazs['place_name'].isin(OBSERVED_CITIES)]['place_name'].unique()
        
        stats = {
            'County': county,
            'N_MAZs': len(county_mazs),
            'Mean': county_mazs['commercial_emp_den'].mean(),
            'Median': county_mazs['commercial_emp_den'].median(),
            'P90': county_mazs['commercial_emp_den'].quantile(0.90),
            'P95': county_mazs['commercial_emp_den'].quantile(0.95),
            'P98': county_mazs['commercial_emp_den'].quantile(0.98),
            'P99': county_mazs['commercial_emp_den'].quantile(0.99),
            'Has_Observed': 'Yes' if has_observed else 'No',
            'Observed_Cities': ', '.join(observed_cities) if len(observed_cities) > 0 else 'None'
        }
        county_stats.append(stats)
    
    # Create DataFrame for nice printing
    df_stats = pd.DataFrame(county_stats)
    
    # Print table
    print("Commercial Employment Density (jobs/acre) Percentiles by County:")
    print("─" * 80)
    print(f"{'County':<20} {'N_MAZs':>8} {'Mean':>8} {'P90':>8} {'P95':>8} {'P98':>8} {'P99':>8} {'Obs':>4}")
    print("─" * 80)
    
    for _, row in df_stats.iterrows():
        obs_marker = '✓' if row['Has_Observed'] == 'Yes' else ''
        print(f"{row['County']:<20} {row['N_MAZs']:>8,} {row['Mean']:>8.2f} {row['P90']:>8.2f} "
              f"{row['P95']:>8.2f} {row['P98']:>8.2f} {row['P99']:>8.2f} {obs_marker:>4}")
    
    print("─" * 80)
    print("\nObserved Data Cities:")
    for _, row in df_stats[df_stats['Has_Observed'] == 'Yes'].iterrows():
        print(f"  {row['County']}: {row['Observed_Cities']}")
    
    print("\nInterpretation:")
    print("  - P95 = 95th percentile (top 5% of MAZs by commercial density)")
    print("  - P98 = 98th percentile (top 2% of MAZs by commercial density)")
    print("  - Higher percentiles = stricter criteria for paid parking prediction")
    print("  - Counties with ✓ have observed parking cost data for validation")
    print("\nRecommendation:")
    print("  - Daily parking: Consider P95 (captures high-density commercial areas)")
    print("  - Monthly parking: Consider P98 (more restrictive, downtown cores only)")
    print("="*80)
    
    return df_stats


def estimate_parking_costs(maz, commercial_density_threshold=1.0):
    """
    Estimate parking costs for MAZs without observed data using logistic regression.
    
    Uses binary classification to predict paid (1) vs free (0) parking, then assigns:
    - hparkcost: $2.00 flat rate (typical SF/Oakland hourly rate)
    - dparkcost: median of observed daily costs
    - mparkcost: median of observed monthly costs
    
    Only predicts for cities OTHER than San Francisco, Oakland, and San Jose
    (those cities use observed data only).
    
    Capacity constraints:
    - hparkcost: only predict where on_all > 0
    - dparkcost, mparkcost: only predict where off_nres > 0
    - All costs: only predict where place_name is not null
    - All costs: only predict where commercial_emp_den >= threshold
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have density features, observed costs, capacity)
        commercial_density_threshold: Minimum commercial_emp_den for paid parking consideration (default 1.0 jobs/acre)
    
    Returns:
        GeoDataFrame: maz with estimated parking costs filled in
    """
    print(f"\nEstimating parking costs for MAZs without observed data...")
    print(f"  Approach: Logistic regression (binary classification) + flat rates")
    print(f"  Excluding from prediction: San Francisco, Oakland, San Jose (observed data only)")
    print(f"  Commercial density threshold: {commercial_density_threshold:.2f} jobs/acre")
    
    # Cities with observed data - exclude from predictions
    OBSERVED_CITIES = ['San Francisco', 'Oakland', 'San Jose']
    
    # Feature columns for regression
    feature_cols = ['commercial_emp_den', 'downtown_emp_den', 'emp_total_den']
    
    # Initialize predicted cost columns (start with NaN)
    maz['hparkcost_pred'] = np.nan
    
    # Define flat rates
    HOURLY_FLAT_RATE = 2.00  # $2/hour typical for SF/Oakland
    
    # Process only hourly parking (daily/monthly handled by county threshold function)
    for cost_type, capacity_col in [('hparkcost', 'on_all')]:
        print(f"\n  Processing {cost_type}...")
        
        # Create training mask: has capacity AND has place_name in observed cities
        # Train on ALL three cities with observed data (including free parking)
        has_capacity = maz[capacity_col] > 0
        has_place = maz['place_name'].notna()
        in_observed_cities = maz['place_name'].isin(OBSERVED_CITIES)
        
        training_mask = has_capacity & has_place & in_observed_cities
        n_training = training_mask.sum()
        
        print(f"    Training samples (SF/Oakland/SJ): {n_training:,}")
        
        if n_training < 10:
            print(f"    WARNING: Insufficient training data (<10 samples). Skipping {cost_type} estimation.")
            continue
        
        # Extract training data
        X_train = maz.loc[training_mask, feature_cols].values
        y_train_raw = maz.loc[training_mask, cost_type].values
        
        # Binary classification: paid (1) vs free (0)
        # Treat NaN and 0 as free parking, > 0 as paid
        y_train_binary = (pd.Series(y_train_raw).fillna(0) > 0).astype(int).values
        
        # Check for variation
        if y_train_binary.sum() == 0 or y_train_binary.sum() == len(y_train_binary):
            print(f"    WARNING: No variation in paid/free parking. Skipping estimation.")
            continue
        
        # Calculate flat rate from observed paid parking
        paid_costs = pd.Series(y_train_raw).dropna()
        paid_costs = paid_costs[paid_costs > 0].values
        
        if cost_type == 'hparkcost':
            flat_rate = HOURLY_FLAT_RATE
            print(f"    Using hourly flat rate: ${flat_rate:.2f}")
        else:
            flat_rate = np.median(paid_costs)
            print(f"    Using median of observed {cost_type}: ${flat_rate:.2f}")
        
        n_paid = y_train_binary.sum()
        n_free = len(y_train_binary) - n_paid
        
        print(f"    Training data - Paid: {n_paid:,} ({n_paid/len(y_train_binary)*100:.1f}%), Free: {n_free:,} ({n_free/len(y_train_binary)*100:.1f}%)")
        
        # Standardize features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        
        # Train logistic regression
        model = LogisticRegression(random_state=42, max_iter=1000)
        model.fit(X_train_scaled, y_train_binary)
        
        print(f"    Logit coefficients: commercial={model.coef_[0][0]:.3f}, downtown={model.coef_[0][1]:.3f}, total_emp={model.coef_[0][2]:.3f}")
        
        # Create prediction mask: NO observed cost AND has capacity AND has place_name AND NOT in observed cities AND above density threshold
        has_observed = maz[cost_type].notna()
        needs_prediction = (
            ~has_observed & 
            has_capacity & 
            has_place &
            ~in_observed_cities &  # Exclude SF, Oakland, San Jose
            (maz['commercial_emp_den'] >= commercial_density_threshold)  # Only predict for commercial areas
        )
        n_predictions = needs_prediction.sum()
        
        print(f"    MAZs eligible for prediction (other cities): {n_predictions:,}")
        
        if n_predictions > 0:
            # Extract prediction features
            X_pred = maz.loc[needs_prediction, feature_cols].values
            X_pred_scaled = scaler.transform(X_pred)
            
            # Predict probability of paid parking
            y_pred_proba = model.predict_proba(X_pred_scaled)[:, 1]  # Probability of class 1 (paid)
            
            # Use 0.5 threshold to classify
            y_pred_binary = (y_pred_proba >= 0.5).astype(int)
            
            # Assign flat rate to predicted paid parking MAZs
            y_pred = np.where(y_pred_binary == 1, flat_rate, 0)
            
            # Store predictions
            maz.loc[needs_prediction, f'{cost_type}_pred'] = y_pred
            
            n_predicted_paid = y_pred_binary.sum()
            print(f"    Predicted paid parking: {n_predicted_paid:,} MAZs at ${flat_rate:.2f}")
            print(f"    Predicted free parking: {n_predictions - n_predicted_paid:,} MAZs")
    
    # Fill in observed costs with predictions where missing
    # Fill NaN with predictions
    maz['hparkcost'] = maz['hparkcost'].fillna(maz['hparkcost_pred'])
    
    # Fill any remaining NaN with 0 (free parking)
    maz['hparkcost'] = maz['hparkcost'].fillna(0)
    
    # Report final statistics
    nonzero_count = (maz['hparkcost'] > 0).sum()
    if nonzero_count > 0:
        print(f"\n  Final hparkcost: {nonzero_count:,} MAZs with cost > $0 (mean=${maz.loc[maz['hparkcost'] > 0, 'hparkcost'].mean():.2f})")
    else:
        print(f"\n  Final hparkcost: 0 MAZs with cost > $0")
    
    # Drop intermediate prediction columns
    maz = maz.drop(columns=['hparkcost_pred'])
    
    return maz


def validate_parking_cost_estimation(maz, commercial_density_threshold=1.0):
    """
    Perform leave-one-city-out cross-validation for hourly parking cost estimation using logistic regression.
    
    Trains binary classification models on 2 cities and tests on the 3rd to evaluate generalization.
    Explicitly validates on San Francisco, Oakland, and San Jose (cities with observed data).
    
    Note: Only validates hourly parking (hparkcost) since daily/monthly use county-level thresholds.
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have density features, observed costs, capacity)
        commercial_density_threshold: Minimum commercial_emp_den for paid parking (default 1.0 jobs/acre)
    
    Returns:
        dict: Validation metrics for each cost type and held-out city
    """
    print("\n" + "="*80)
    print("LEAVE-ONE-CITY-OUT CROSS-VALIDATION (Logistic Regression)")
    print("="*80)
    print("Validating hourly parking only (daily/monthly use county thresholds)")
    
    # Cities with observed parking cost data
    TARGET_CITIES = ['San Francisco', 'Oakland', 'San Jose']
    
    # Feature columns for regression
    feature_cols = ['commercial_emp_den', 'downtown_emp_den', 'emp_total_den']
    
    results = {}
    
    # Only validate hourly parking (hparkcost) - daily/monthly use thresholds
    for cost_type, capacity_col in [('hparkcost', 'on_all')]:
        print(f"\n{'='*80}")
        print(f"Validating {cost_type.upper()}")
        print(f"{'='*80}")
        
        # Count observed data by city (including free parking)
        # For SF/Oakland/SJ, treat any MAZ with capacity as "observed" (paid or free)
        has_capacity = maz[capacity_col] > 0
        has_place = maz['place_name'].notna()
        in_target_cities = maz['place_name'].isin(TARGET_CITIES)
        
        # "Observed" = has capacity in target cities (we know it's either paid or free)
        has_observed = has_capacity & has_place & in_target_cities
        
        # Count by city
        city_counts = maz[has_observed]['place_name'].value_counts()
        
        # Filter to target cities with sufficient data (at least 10 observations)
        cities_to_test = [city for city in TARGET_CITIES if city in city_counts.index and city_counts[city] >= 10]
        
        if len(cities_to_test) < 2:
            print(f"  Insufficient target cities with observed {cost_type} (need >= 2 of {TARGET_CITIES}). Skipping validation.")
            continue
        
        print(f"  Validating on cities: {', '.join(cities_to_test)}")
        print(f"  Observations per city: {dict(city_counts[cities_to_test])}")
        
        results[cost_type] = {}
        
        # Leave-one-city-out cross-validation
        for held_out_city in cities_to_test:
            # Determine training cities (all target cities except held-out)
            training_cities = [city for city in cities_to_test if city != held_out_city]
            
            print(f"\n  {'─'*70}")
            print(f"  TRAINING ON: {', '.join(training_cities)}")
            print(f"  TESTING ON:  {held_out_city}")
            print(f"  {'─'*70}")
            
            # For training cities: all MAZs with capacity are "observed" (ground truth)
            # Paid = cost > 0, Free = cost <= 0 or NaN (but has capacity)
            train_mask = (
                has_capacity & has_place & 
                (maz['place_name'].isin(training_cities))
            )
            
            # For test city: same logic
            test_mask = (
                has_capacity & has_place & 
                (maz['place_name'] == held_out_city) &
                (maz['commercial_emp_den'] >= commercial_density_threshold)
            )
            
            n_train = train_mask.sum()
            n_test = test_mask.sum()
            
            print(f"    Training samples (other cities): {n_train:,}")
            print(f"    Test samples ({held_out_city}): {n_test:,}")
            
            if n_train < 10 or n_test < 5:
                print(f"    Insufficient data for validation. Skipping.")
                continue
            
            # Extract training data
            X_train = maz.loc[train_mask, feature_cols].values
            y_train_raw = maz.loc[train_mask, cost_type].values
            
            # Convert to binary: paid (1) or free (0)
            # Treat NaN and 0 as free parking, > 0 as paid
            y_train_binary = (pd.Series(y_train_raw).fillna(0) > 0).astype(int).values
            
            # Debug: show distribution of paid vs free
            n_train_paid = y_train_binary.sum()
            n_train_free = len(y_train_binary) - n_train_paid
            print(f"    Training data: {n_train_paid:,} paid, {n_train_free:,} free")
            
            # Check for variation
            if y_train_binary.sum() == 0 or y_train_binary.sum() == len(y_train_binary):
                print(f"    WARNING: No variation in paid/free parking. Skipping.")
                continue
            
            # Extract test data
            X_test = maz.loc[test_mask, feature_cols].values
            y_test_raw = maz.loc[test_mask, cost_type].values
            y_test_binary = (pd.Series(y_test_raw).fillna(0) > 0).astype(int).values
            
            # Standardize features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train logistic regression model
            model = LogisticRegression(random_state=42, max_iter=1000)
            model.fit(X_train_scaled, y_train_binary)
            
            # Predict on held-out city
            y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
            y_pred_binary = (y_pred_proba >= 0.5).astype(int)
            
            # Calculate classification metrics
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
            
            accuracy = accuracy_score(y_test_binary, y_pred_binary)
            
            # Handle case where there are no positive predictions
            if y_pred_binary.sum() == 0:
                precision = 0.0
                recall = 0.0
                f1 = 0.0
            else:
                precision = precision_score(y_test_binary, y_pred_binary, zero_division=0)
                recall = recall_score(y_test_binary, y_pred_binary, zero_division=0)
                f1 = f1_score(y_test_binary, y_pred_binary, zero_division=0)
            
            # Count true positives, false positives, etc.
            n_actual_paid = y_test_binary.sum()
            n_actual_free = len(y_test_binary) - n_actual_paid
            n_predicted_paid = y_pred_binary.sum()
            n_predicted_free = len(y_pred_binary) - n_predicted_paid
            
            # Store results
            results[cost_type][held_out_city] = {
                'n_train': n_train,
                'n_test': n_test,
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'n_actual_paid': n_actual_paid,
                'n_actual_free': n_actual_free,
                'n_predicted_paid': n_predicted_paid,
                'n_predicted_free': n_predicted_free,
            }
            
            # Print metrics
            print(f"    Classification Metrics:")
            print(f"      Accuracy: {accuracy:.1%} ({int(accuracy * n_test)}/{n_test} correct)")
            print(f"      Precision: {precision:.1%} (of predicted paid, % actually paid)")
            print(f"      Recall: {recall:.1%} (of actual paid, % correctly predicted)")
            print(f"      F1 Score: {f1:.3f}")
            print(f"    Actual: {n_actual_paid:,} paid, {n_actual_free:,} free")
            print(f"    Predicted: {n_predicted_paid:,} paid, {n_predicted_free:,} free")
    
    # Print summary
    print(f"\n{'='*80}")
    print("VALIDATION SUMMARY")
    print(f"{'='*80}")
    
    # Map cities to counties
    CITY_TO_COUNTY = {
        'San Francisco': 'San Francisco',
        'Oakland': 'Alameda',
        'San Jose': 'Santa Clara'
    }
    
    for cost_type, city_results in results.items():
        if not city_results:
            continue
        
        print(f"\n{cost_type.upper()}:")
        
        # Calculate average metrics across cities
        avg_accuracy = np.mean([r['accuracy'] for r in city_results.values()])
        avg_precision = np.mean([r['precision'] for r in city_results.values()])
        avg_recall = np.mean([r['recall'] for r in city_results.values()])
        avg_f1 = np.mean([r['f1'] for r in city_results.values()])
        
        print(f"  Average Accuracy: {avg_accuracy:.1%}")
        print(f"  Average Precision: {avg_precision:.1%}")
        print(f"  Average Recall: {avg_recall:.1%}")
        print(f"  Average F1 Score: {avg_f1:.3f}")
        print(f"  Tested on {len(city_results)} cities")
        
        # County-level breakdown
        print(f"\n  County-Level Breakdown:")
        print(f"  {'─'*76}")
        print(f"  {'County':<20} {'City':<15} {'Accuracy':>10} {'Precision':>10} {'Recall':>10}")
        print(f"  {'─'*76}")
        
        for city, metrics in city_results.items():
            county = CITY_TO_COUNTY.get(city, 'Unknown')
            print(f"  {county:<20} {city:<15} {metrics['accuracy']:>9.1%} {metrics['precision']:>9.1%} {metrics['recall']:>9.1%}")
        
        print(f"  {'─'*76}")
        print(f"  {'Total':<20} {'All cities':<15} {avg_accuracy:>9.1%} {avg_precision:>9.1%} {avg_recall:>9.1%}")
        print(f"  {'─'*76}")
    
    return results


def estimate_parking_by_county_threshold(maz, daily_percentile=0.95, monthly_percentile=0.98):
    """
    Estimate daily and monthly parking costs using county-level density thresholds.
    
    Applies county-specific commercial employment density percentiles to identify
    high-density areas likely to have paid parking. Only predicts for cities OTHER
    than San Francisco, Oakland, and San Jose (those use observed data).
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have county_name, commercial_emp_den, off_nres)
        daily_percentile: Percentile threshold for daily parking (default 0.95 = 95th percentile)
        monthly_percentile: Percentile threshold for monthly parking (default 0.98 = 98th percentile)
    
    Returns:
        GeoDataFrame: maz with dparkcost and mparkcost filled in
    """
    print(f"\nEstimating daily/monthly parking costs using county-level thresholds...")
    print(f"  Daily parking: {daily_percentile*100:.0f}th percentile of commercial_emp_den per county")
    print(f"  Monthly parking: {monthly_percentile*100:.0f}th percentile of commercial_emp_den per county")
    print(f"  Excluding from prediction: San Francisco, Oakland, San Jose (observed data only)")
    
    # Cities with observed data - exclude from predictions
    OBSERVED_CITIES = ['San Francisco', 'Oakland', 'San Jose']
    
    # Flat rates from observed data
    daily_flat_rate = maz[maz['dparkcost'] > 0]['dparkcost'].median()
    monthly_flat_rate = maz[maz['mparkcost'] > 0]['mparkcost'].median()
    
    # Handle case where no observed data exists
    if pd.isna(daily_flat_rate):
        daily_flat_rate = 21.15  # Default from previous analysis
    if pd.isna(monthly_flat_rate):
        monthly_flat_rate = 343.95  # Default from previous analysis
    
    print(f"  Using flat rates: Daily=${daily_flat_rate:.2f}, Monthly=${monthly_flat_rate:.2f}")
    
    # Initialize prediction columns
    maz['dparkcost_pred'] = np.nan
    maz['mparkcost_pred'] = np.nan
    
    # Calculate county-level thresholds
    print(f"\n  County-Level Thresholds:")
    print(f"  {'─'*70}")
    print(f"  {'County':<20} {'N_MAZs':>8} {'Daily_P{int(daily_percentile*100)}':>12} {'Monthly_P{int(monthly_percentile*100)}':>12}")
    print(f"  {'─'*70}")
    
    county_thresholds = {}
    
    for county in sorted(maz[maz['county_name'].notna()]['county_name'].unique()):
        # Get MAZs in county with off-street capacity and in cities
        county_mazs = maz[
            (maz['county_name'] == county) & 
            (maz['off_nres'] > 0) & 
            (maz['place_name'].notna())
        ]
        
        if len(county_mazs) == 0:
            continue
        
        # Calculate thresholds
        daily_threshold = county_mazs['commercial_emp_den'].quantile(daily_percentile)
        monthly_threshold = county_mazs['commercial_emp_den'].quantile(monthly_percentile)
        
        county_thresholds[county] = {
            'daily': daily_threshold,
            'monthly': monthly_threshold
        }
        
        print(f"  {county:<20} {len(county_mazs):>8,} {daily_threshold:>12.2f} {monthly_threshold:>12.2f}")
    
    print(f"  {'─'*70}")
    
    # Apply thresholds by county
    total_daily_predicted = 0
    total_monthly_predicted = 0
    
    for county, thresholds in county_thresholds.items():
        # Daily parking prediction mask
        daily_mask = (
            (maz['county_name'] == county) &
            (maz['off_nres'] > 0) &
            (maz['place_name'].notna()) &
            ~(maz['place_name'].isin(OBSERVED_CITIES)) &
            (maz['dparkcost'].isna()) &
            (maz['commercial_emp_den'] >= thresholds['daily'])
        )
        
        # Monthly parking prediction mask
        # Note: mparkcost was fillna(0) in merge_capacity, so check <= 0 instead of isna()
        monthly_mask = (
            (maz['county_name'] == county) &
            (maz['off_nres'] > 0) &
            (maz['place_name'].notna()) &
            ~(maz['place_name'].isin(OBSERVED_CITIES)) &
            (maz['mparkcost'] <= 0) &
            (maz['commercial_emp_den'] >= thresholds['monthly'])
        )
        
        # Apply flat rates
        maz.loc[daily_mask, 'dparkcost_pred'] = daily_flat_rate
        maz.loc[monthly_mask, 'mparkcost_pred'] = monthly_flat_rate
        
        n_daily = daily_mask.sum()
        n_monthly = monthly_mask.sum()
        
        total_daily_predicted += n_daily
        total_monthly_predicted += n_monthly
        
        if n_daily > 0 or n_monthly > 0:
            print(f"  {county}: Predicted {n_daily:,} daily, {n_monthly:,} monthly paid parking MAZs")
    
    # Fill in predictions
    maz['dparkcost'] = maz['dparkcost'].fillna(maz['dparkcost_pred'])
    maz['mparkcost'] = maz['mparkcost'].fillna(maz['mparkcost_pred'])
    
    # Fill remaining NaN with 0 (free parking)
    maz['dparkcost'] = maz['dparkcost'].fillna(0)
    maz['mparkcost'] = maz['mparkcost'].fillna(0)
    
    # Drop intermediate columns
    maz = maz.drop(columns=['dparkcost_pred', 'mparkcost_pred'])
    
    # Report final statistics
    print(f"\n  Summary:")
    print(f"    Total predicted daily paid parking: {total_daily_predicted:,} MAZs at ${daily_flat_rate:.2f}")
    print(f"    Total predicted monthly paid parking: {total_monthly_predicted:,} MAZs at ${monthly_flat_rate:.2f}")
    
    final_daily = (maz['dparkcost'] > 0).sum()
    final_monthly = (maz['mparkcost'] > 0).sum()
    
    print(f"\n  Final dparkcost: {final_daily:,} MAZs with cost > $0 (mean=${maz.loc[maz['dparkcost'] > 0, 'dparkcost'].mean():.2f})")
    print(f"  Final mparkcost: {final_monthly:,} MAZs with cost > $0 (mean=${maz.loc[maz['mparkcost'] > 0, 'mparkcost'].mean():.2f})")
    
    return maz


def main(run_validation=False, commercial_density_threshold=1.0):
    """
    Main entry point that sequences the workflow.
    
    Args:
        run_validation: If True, perform leave-one-city-out cross-validation before estimation
        commercial_density_threshold: Minimum commercial_emp_den for paid parking prediction (default 1.0 jobs/acre)
    
    Returns:
        GeoDataFrame: MAZ data with estimated parking costs
    """
    print("Loading Bay Area census places...")
    places = load_bay_area_places()
    print(f"  Loaded {len(places):,} places")
    
    print("\nLoading MAZ data...")
    maz = load_maz_data()
    
    print("\nPerforming spatial join of MAZ to places...")
    maz = spatial_join_maz_to_place(maz, places)
    print(f"  Completed spatial join for {len(maz):,} MAZs")
    
    print("\nMerging parking scrape data...")
    maz = merge_scraped_cost(maz)
    print(f"  Completed parking cost merge")
    
    print("\nMerging published parking meter costs...")
    maz = merge_published_cost(maz)
    print(f"  Completed published parking cost merge")
    
    print("\nMerging parking capacity data...")
    maz = merge_capacity(maz)
    print(f"  Completed parking capacity merge")
    
    print("\nAdding density features...")
    maz = add_density_features(maz)
    print(f"  Completed density feature calculation")
    
    # Report county-level density distributions to inform threshold selection
    county_stats = report_county_density_distributions(maz)
    
    # Optional validation before estimation
    if run_validation:
        validation_results = validate_parking_cost_estimation(maz, commercial_density_threshold)
    
    # Estimate hourly parking using logistic regression
    print("\nEstimating hourly parking costs for MAZs without observed data...")
    maz = estimate_parking_costs(maz, commercial_density_threshold)
    print(f"  Completed hourly parking cost estimation")
    
    # Estimate daily/monthly parking using county-level thresholds
    maz = estimate_parking_by_county_threshold(maz, daily_percentile=0.95, monthly_percentile=0.98)
    print(f"  Completed daily/monthly parking cost estimation")
    
    return maz


if __name__ == "__main__":
    maz_prepped = main(run_validation=True)


#%%
maz_gdf = maz_prepped.copy()
maz_gdf = maz_gdf[maz_gdf["place_name"].notnull()]
m = maz_gdf.explore(column="hparkcost", tooltip=False, popup=True)
m.save("est_hparkcost.html")

# %%
maz_gdf = maz_prepped.copy()
maz_gdf = maz_gdf[maz_gdf["place_name"].notnull()]
m = maz_gdf.explore(column="dparkcost", tooltip=False, popup=True)
m.save("est_dparkcost.html")

# %%
maz_gdf = maz_prepped.copy()
maz_gdf = maz_gdf[maz_gdf["place_name"].notnull()]
m = maz_gdf.explore(column="mparkcost", tooltip=False, popup=True)
m.save("est_mparkcost.html")
# %%
