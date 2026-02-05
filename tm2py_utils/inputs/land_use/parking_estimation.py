"""
Parking Cost Estimation Module

This module provides statistical modeling for estimating parking costs in MAZ zones
without observed data. It implements a hybrid approach:

Architecture:
- **Hourly parking (hparkcost)**: Logistic regression for binary classification
  - Trains on San Francisco, Oakland, San Jose observed data (paid vs free)
  - Predicts paid/free for other cities with parking capacity
  - Assigns flat $2.00/hr rate to predicted paid parking MAZs
  
- **Daily/Monthly parking (dparkcost, mparkcost)**: County-level density thresholds
  - Uses commercial employment density percentiles within each county
  - Daily: 95th percentile (top 5% of MAZs by commercial density)
  - Monthly: 98th percentile (top 2% of MAZs by commercial density)
  - Assigns median observed rates ($19.25 daily, $339.90 monthly)

Key Constraints:
- Hourly predictions only where on_all > 0 (on-street capacity)
- Daily/monthly predictions only where off_nres > 0 (off-street capacity)
- All predictions only in cities (place_name not null)
- Predictions exclude SF/Oakland/SJ (those use observed data only)
- Minimum commercial_emp_den threshold for paid parking consideration

Workflow:
1. add_density_features(): Calculate commercial/downtown employment densities
2. report_county_density_distributions(): Diagnostic percentile report by county
3. [Optional] validate_parking_cost_estimation(): Leave-one-city-out cross-validation
4. estimate_parking_costs(): Logistic regression for hourly parking
5. estimate_parking_by_county_threshold(): Threshold-based daily/monthly estimation

Entry Point:
- merge_estimated_costs(): Main function called from parking_prep.py orchestration
"""

import pandas as pd
import geopandas as gpd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


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
    
    Only predicts for cities OTHER than San Francisco, Oakland, and San Jose
    (those cities use observed data only).
    
    Capacity constraints:
    - hparkcost: only predict where on_all > 0
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


def merge_estimated_costs(
    maz,
    run_validation=False,
    commercial_density_threshold=1.0,
    daily_percentile=0.95,
    monthly_percentile=0.98
):
    """
    Estimate parking costs for MAZs without observed data.
    
    This is the main entry point called from parking_prep.py orchestration.
    Implements a hybrid estimation approach:
    - Hourly parking: Logistic regression trained on SF/Oakland/SJ
    - Daily/Monthly parking: County-level density thresholds
    
    Args:
        maz: GeoDataFrame with MAZ zones (must have employment, capacity, observed costs, 
             place_name, county_name)
        run_validation: If True, perform leave-one-city-out cross-validation (default False)
        commercial_density_threshold: Minimum commercial_emp_den for paid parking (default 1.0 jobs/acre)
        daily_percentile: County-level percentile for daily parking threshold (default 0.95)
        monthly_percentile: County-level percentile for monthly parking threshold (default 0.98)
    
    Returns:
        GeoDataFrame: maz with estimated hparkcost, dparkcost, mparkcost filled in
    """
    print("\n" + "="*80)
    print("PARKING COST ESTIMATION")
    print("="*80)
    
    # Add density features
    maz = add_density_features(maz)
    
    # Report county distributions
    county_stats = report_county_density_distributions(maz)
    
    # Optional validation
    if run_validation:
        validation_results = validate_parking_cost_estimation(
            maz, commercial_density_threshold
        )
    
    # Estimate hourly parking
    maz = estimate_parking_costs(maz, commercial_density_threshold)
    
    # Estimate daily/monthly parking
    maz = estimate_parking_by_county_threshold(
        maz, daily_percentile, monthly_percentile
    )
    
    print("\n" + "="*80)
    print("PARKING COST ESTIMATION COMPLETE")
    print("="*80)
    
    return maz
