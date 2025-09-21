#!/usr/bin/env python3
"""
Analyze Stop Location Choice UEC expressions for data consistency issues
Similar to the ExplicitTelecommute analysis that found serv_per vs serv_pers issue
"""
import pandas as pd
import numpy as np

def analyze_stop_location_choice_uecs():
    """Analyze UEC expressions in Stop Location Choice for potential division by zero issues"""
    print("=== STOP LOCATION CHOICE UEC ANALYSIS ===")
    
    try:
        # Load the employment data
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        print(f"Loaded employment data: {len(df)} MAZ records")
        
        # Stop Location Choice UEC expressions (based on typical TM2 structure)
        # These are the likely expressions causing NullPointerException:
        
        # Size variables for different stop purposes (similar to ExplicitTelecommute employment shares)
        print(f"\n=== STOP LOCATION CHOICE SIZE VARIABLES ===")
        
        # Shopping stops - typically use retail employment
        df['shop_size'] = df['ret_loc'] + df['ret_reg']  # Total retail employment
        
        # Personal business stops - typically use service employment  
        df['personal_size'] = df['serv_pers'] + df['health'] + df['gov']
        
        # Social/recreation stops
        df['social_size'] = df['serv_soc'] + df['art_rec']
        
        # Eating out stops
        df['eat_size'] = df['eat']
        
        # Work-related stops (pick-up/drop-off)
        df['work_size'] = df['emp_total']
        
        # Check each size variable for crash conditions
        size_variables = {
            'shop_size': 'Shopping stops (ret_loc + ret_reg)',
            'personal_size': 'Personal business (serv_pers + health + gov)', 
            'social_size': 'Social/recreation (serv_soc + art_rec)',
            'eat_size': 'Eating out (eat)',
            'work_size': 'Work-related (emp_total)'
        }
        
        total_crash_risk_mazs = set()
        
        for size_var, description in size_variables.items():
            if size_var in df.columns:
                zero_size = (df[size_var] == 0).sum()
                nonzero_size = (df[size_var] > 0).sum()
                
                print(f"\n{description}:")
                print(f"  MAZs with zero size: {zero_size:,}")
                print(f"  MAZs with non-zero size: {nonzero_size:,}")
                print(f"  Total employment: {df[size_var].sum():,.0f}")
                
                # Find MAZs where this would be the only purpose but size = 0
                if zero_size > 0:
                    zero_size_mazs = df[df[size_var] == 0]['MAZ'].tolist()[:5]
                    print(f"  Sample MAZs with zero size: {zero_size_mazs}")
                    total_crash_risk_mazs.update(df[df[size_var] == 0]['MAZ'].tolist())
        
        # Check for stop accessibility/impedance calculations that might cause issues
        print(f"\n=== ACCESSIBILITY AND IMPEDANCE CHECKS ===")
        
        # Check for distance/impedance issues
        distance_fields = [col for col in df.columns if 'dist' in col.lower() or 'time' in col.lower()]
        if distance_fields:
            print(f"Distance/time fields found: {distance_fields}")
            
            for field in distance_fields:
                try:
                    # Convert to numeric first to handle potential string values
                    numeric_field = pd.to_numeric(df[field], errors='coerce')
                    zero_dist = (numeric_field == 0).sum()
                    inf_dist = np.isinf(numeric_field).sum()
                    nan_dist = numeric_field.isna().sum()
                    
                    if zero_dist > 0 or inf_dist > 0 or nan_dist > 0:
                        print(f"  {field}: {zero_dist:,} zero, {inf_dist:,} infinite, {nan_dist:,} NaN")
                except Exception as e:
                    print(f"  {field}: Cannot analyze ({e})")
        else:
            print("No obvious distance/time fields found")
        
        # Check density variables that might be used in utility calculations
        density_fields = ['EmpDen', 'RetEmpDen', 'PopDen', 'DUDen', 'PopEmpDenPerMi']
        
        print(f"\n=== DENSITY VARIABLES USED IN UTILITY ===")
        
        for field in density_fields:
            if field in df.columns:
                zero_density = (df[field] == 0).sum()
                nan_density = df[field].isna().sum()
                inf_density = np.isinf(df[field]).sum()
                
                print(f"\n{field}:")
                print(f"  Zero values: {zero_density:,}")
                print(f"  NaN values: {nan_density:,}")
                print(f"  Infinite values: {inf_density:,}")
                
                # For employment density, check if it matches calculated values
                if field == 'EmpDen' and 'emp_total' in df.columns and 'ACRES' in df.columns:
                    calculated_empden = df['emp_total'] / df['ACRES'].replace(0, np.nan)
                    mismatch = abs(df['EmpDen'] - calculated_empden) > 0.01
                    mismatch = mismatch & df['ACRES'] > 0
                    
                    if mismatch.sum() > 0:
                        print(f"  ❌ EmpDen calculation mismatches: {mismatch.sum():,}")
                        
                        sample = df[mismatch][['MAZ', 'emp_total', 'ACRES', 'EmpDen']].head(3)
                        sample['calculated'] = sample['emp_total'] / sample['ACRES']
                        print("  Sample mismatches:")
                        print(sample)
        
        # Check for stop location choice specific issues
        print(f"\n=== STOP-SPECIFIC CHOICE ANALYSIS ===")
        
        # Look for MAZs that have NO activity at all (would never be chosen)
        activity_cols = ['ret_loc', 'ret_reg', 'serv_pers', 'serv_soc', 'art_rec', 'eat', 'health', 'gov', 'emp_total']
        available_activity_cols = [col for col in activity_cols if col in df.columns]
        
        if available_activity_cols:
            df['total_activity'] = df[available_activity_cols].sum(axis=1)
            
            no_activity = (df['total_activity'] == 0).sum()
            has_activity = (df['total_activity'] > 0).sum()
            
            print(f"MAZs with NO activity (never choosable): {no_activity:,}")
            print(f"MAZs with some activity: {has_activity:,}")
            
            if no_activity > 0:
                print("❌ MAZs with no activity will never be available as stop destinations")
                no_activity_mazs = df[df['total_activity'] == 0]['MAZ'].tolist()[:10]
                print(f"Sample no-activity MAZs: {no_activity_mazs}")
        
        # Check for potential log/ln calculations in utility (common crash source)
        print(f"\n=== LOGARITHMIC UTILITY EXPRESSIONS ===")
        
        # Size variables that might be used in log() expressions
        log_candidates = ['shop_size', 'personal_size', 'social_size', 'eat_size', 'work_size']
        
        for var in log_candidates:
            if var in df.columns:
                zero_or_negative = (df[var] <= 0).sum()
                
                if zero_or_negative > 0:
                    print(f"❌ {var}: {zero_or_negative:,} MAZs with zero/negative values")
                    print(f"   This will cause -∞ in ln({var}) expressions!")
                else:
                    print(f"✅ {var}: All positive values, safe for ln() expressions")
        
        # Look for division expressions that might cause issues
        print(f"\n=== DIVISION EXPRESSIONS ANALYSIS ===")
        
        # Common ratios used in stop choice utility
        if all(col in df.columns for col in ['ret_loc', 'ret_reg', 'emp_total']):
            # Retail share of total employment
            df['retail_share'] = (df['ret_loc'] + df['ret_reg']) / df['emp_total'].replace(0, np.nan)
            
            nan_retail_share = df['retail_share'].isna().sum()
            inf_retail_share = np.isinf(df['retail_share']).sum()
            
            print(f"Retail employment share:")
            print(f"  NaN values (division by zero): {nan_retail_share:,}")
            print(f"  Infinite values: {inf_retail_share:,}")
            
            if nan_retail_share > 0:
                print("❌ Division by zero in retail_share calculation!")
                print("This happens when emp_total = 0 but retail employment > 0")
                
                # Find the problematic MAZs
                problematic = (df['ret_loc'] + df['ret_reg'] > 0) & (df['emp_total'] == 0)
                if problematic.sum() > 0:
                    print(f"❌ CRITICAL: {problematic.sum():,} MAZs have retail > 0 but emp_total = 0")
                    sample = df[problematic][['MAZ', 'ret_loc', 'ret_reg', 'emp_total']].head()
                    print("Sample problematic MAZs:")
                    print(sample)
        
        # Check for the same issue we found in ExplicitTelecommute
        print(f"\n=== EMPLOYMENT CONSISTENCY CHECK (LIKE EXPLICIT TELECOMMUTE) ===")
        
        # Check if emp_total matches sum of subcategories
        emp_subcategories = ['ag', 'art_rec', 'constr', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'fire', 'gov', 'health',
                            'hotel', 'info', 'lease', 'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'natres', 
                            'prof', 'ret_loc', 'ret_reg', 'serv_bus', 'serv_pers', 'serv_soc', 'transp', 'util']
        
        available_emp_cols = [col for col in emp_subcategories if col in df.columns]
        
        if available_emp_cols and 'emp_total' in df.columns:
            df['calculated_emp_total'] = df[available_emp_cols].sum(axis=1)
            
            mismatch = abs(df['emp_total'] - df['calculated_emp_total']) > 0.01
            print(f"Employment total mismatches: {mismatch.sum():,}")
            
            if mismatch.sum() == 0:
                print("✅ Employment totals are consistent (our ExplicitTelecommute fix worked!)")
            else:
                print("❌ Employment totals still inconsistent - similar issue to ExplicitTelecommute")
        
        # Final assessment
        print(f"\n=== CRASH RISK ASSESSMENT ===")
        
        total_issues = 0
        critical_issues = []
        
        # Count various issues that could cause crashes
        if 'retail_share' in df.columns:
            retail_div_zero = df['retail_share'].isna().sum()
            if retail_div_zero > 0:
                total_issues += retail_div_zero
                critical_issues.append(f"retail_share division by zero: {retail_div_zero:,} MAZs")
        
        for var in log_candidates:
            if var in df.columns:
                zero_log = (df[var] <= 0).sum()
                if zero_log > 0:
                    total_issues += zero_log
                    critical_issues.append(f"ln({var}) undefined: {zero_log:,} MAZs")
        
        print(f"Total MAZs at risk of causing choice model crashes: {len(total_crash_risk_mazs):,}")
        
        if critical_issues:
            print("❌ CRITICAL ISSUES FOUND:")
            for issue in critical_issues:
                print(f"  - {issue}")
            
            print(f"\nThese issues could cause:")
            print(f"  1. NullPointerException when no valid alternatives exist")
            print(f"  2. -∞ utilities making all alternatives unavailable")
            print(f"  3. Division by zero in size or utility calculations")
        else:
            print("✅ No obvious UEC-related crash conditions found")
            print("The NullPointerException might be due to:")
            print("  1. Specific household/tour combination edge cases") 
            print("  2. UEC file configuration issues")
            print("  3. Missing choice model parameters")
        
    except Exception as e:
        print(f"Error during UEC analysis: {e}")
        import traceback
        traceback.print_exc()

def suggest_stop_choice_fixes():
    """Suggest fixes for Stop Location Choice issues"""
    print(f"\n=== SUGGESTED FIXES FOR STOP LOCATION CHOICE ===")
    print("1. Fix any division by zero in size variables (similar to ExplicitTelecommute)")
    print("2. Add small constants to prevent ln(0) in utility expressions")
    print("3. Ensure all MAZs have at least some minimal activity for stop purposes")
    print("4. Validate employment share calculations")
    print("5. Check UEC expressions for missing or invalid coefficients")
    print("6. Add fallback alternatives when primary choices are unavailable")

if __name__ == "__main__":
    analyze_stop_location_choice_uecs()
    suggest_stop_choice_fixes()