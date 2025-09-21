#!/usr/bin/env python3
"""
Investigate Stop Location Choice data issues that might cause NullPointerException
"""
import pandas as pd
import numpy as np

def investigate_stop_choice_issues():
    """Check for data issues that could cause Stop Location Choice crashes"""
    print("=== STOP LOCATION CHOICE INVESTIGATION ===")
    
    try:
        # Load the employment data
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        print(f"Loaded MAZ data: {len(df)} records")
        
        # Check for critical fields used in Stop Location Choice
        critical_fields = [
            'MAZ', 'TAZ', 'ACRES', 'emp_total', 'ret_loc', 'ret_reg', 
            'PopEmpDenPerMi', 'EmpDen', 'RetEmpDen', 'PopDen'
        ]
        
        print(f"\n=== CRITICAL FIELD VALIDATION ===")
        missing_fields = []
        for field in critical_fields:
            if field not in df.columns:
                missing_fields.append(field)
                print(f"❌ Missing field: {field}")
            else:
                print(f"✅ Found field: {field}")
        
        if missing_fields:
            print(f"⚠️ WARNING: Missing {len(missing_fields)} critical fields")
            return
        
        # Check for NaN/Infinity values that could cause crashes
        print(f"\n=== NaN/INFINITY CHECK ===")
        problematic_mazs = 0
        
        for field in critical_fields:
            if field in df.columns:
                nan_count = df[field].isna().sum()
                inf_count = np.isinf(df[field]).sum()
                
                if nan_count > 0 or inf_count > 0:
                    print(f"❌ {field}: {nan_count} NaN, {inf_count} Infinity values")
                    problematic_mazs = max(problematic_mazs, nan_count + inf_count)
                else:
                    print(f"✅ {field}: No NaN/Infinity values")
        
        # Check for zero denominators in density calculations
        print(f"\n=== DENSITY CALCULATION VALIDATION ===")
        
        if 'ACRES' in df.columns:
            zero_acres = (df['ACRES'] == 0).sum()
            print(f"MAZs with zero acres: {zero_acres:,}")
            
            if zero_acres > 0:
                print(f"❌ CRITICAL: Zero acres will cause division by zero in density calculations!")
                
                # Show sample MAZs with zero acres
                zero_acre_mazs = df[df['ACRES'] == 0]
                print("Sample MAZs with zero acres:")
                print(zero_acre_mazs[['MAZ', 'ACRES', 'emp_total', 'EmpDen']].head())
        
        # Check employment density consistency
        if all(col in df.columns for col in ['emp_total', 'ACRES', 'EmpDen']):
            # Calculate what EmpDen should be
            expected_empden = df['emp_total'] / df['ACRES'].replace(0, np.nan)
            empden_mismatch = abs(df['EmpDen'] - expected_empden) > 0.01
            empden_mismatch = empden_mismatch & df['ACRES'] > 0  # Only check non-zero acres
            
            print(f"EmpDen calculation mismatches: {empden_mismatch.sum():,}")
            
            if empden_mismatch.sum() > 0:
                print("Sample EmpDen mismatches:")
                sample = df[empden_mismatch][['MAZ', 'emp_total', 'ACRES', 'EmpDen']].head()
                sample['expected_EmpDen'] = sample['emp_total'] / sample['ACRES']
                print(sample)
        
        # Check retail employment density
        if all(col in df.columns for col in ['ret_loc', 'ret_reg', 'ACRES', 'RetEmpDen']):
            df['ret_total'] = df['ret_loc'] + df['ret_reg']
            expected_retempden = df['ret_total'] / df['ACRES'].replace(0, np.nan)
            retempden_mismatch = abs(df['RetEmpDen'] - expected_retempden) > 0.01
            retempden_mismatch = retempden_mismatch & df['ACRES'] > 0
            
            print(f"RetEmpDen calculation mismatches: {retempden_mismatch.sum():,}")
        
        # Check for MAZs with employment but zero total employment (similar to our previous fix)
        print(f"\n=== EMPLOYMENT CONSISTENCY FOR STOP CHOICE ===")
        
        # Stop choice often uses retail employment specifically
        if all(col in df.columns for col in ['ret_loc', 'ret_reg']):
            df['retail_total'] = df['ret_loc'] + df['ret_reg']
            
            # MAZs with retail employment components but zero retail total
            retail_components_exist = (df[['ret_loc', 'ret_reg']] > 0).any(axis=1)
            zero_retail_total = df['retail_total'] == 0
            retail_inconsistency = retail_components_exist & zero_retail_total
            
            print(f"MAZs with retail components but zero retail total: {retail_inconsistency.sum():,}")
            
            if retail_inconsistency.sum() > 0:
                print("❌ RETAIL EMPLOYMENT INCONSISTENCY FOUND!")
                print("This could cause Stop Location Choice crashes similar to ExplicitTelecommute")
                
                sample = df[retail_inconsistency][['MAZ', 'ret_loc', 'ret_reg', 'retail_total', 'emp_total']].head()
                print(sample)
        
        # Check for stop location choice alternatives availability
        print(f"\n=== STOP DESTINATION AVAILABILITY ===")
        
        # MAZs with any activity that could be a stop destination
        stop_activities = ['ret_loc', 'ret_reg', 'serv_pers', 'serv_soc', 'eat', 'health']
        available_stop_cols = [col for col in stop_activities if col in df.columns]
        
        if available_stop_cols:
            df['stop_activity_total'] = df[available_stop_cols].sum(axis=1)
            
            mazs_with_stop_activities = (df['stop_activity_total'] > 0).sum()
            mazs_with_zero_stop_activities = (df['stop_activity_total'] == 0).sum()
            
            print(f"MAZs with stop activities: {mazs_with_stop_activities:,}")
            print(f"MAZs with NO stop activities: {mazs_with_zero_stop_activities:,}")
            
            if mazs_with_zero_stop_activities == len(df):
                print("❌ CRITICAL: NO MAZs have stop activities - this will crash stop choice!")
            elif mazs_with_zero_stop_activities > len(df) * 0.5:
                print(f"⚠️ WARNING: {mazs_with_zero_stop_activities/len(df)*100:.1f}% of MAZs have no stop activities")
        
        # Summary
        print(f"\n=== SUMMARY ===")
        if problematic_mazs == 0 and zero_acres == 0:
            print("✅ No obvious data issues found that would cause NullPointerException")
            print("The crash might be due to:")
            print("1. Specific household/tour combinations triggering the bug")
            print("2. Choice model configuration issues")
            print("3. Missing or corrupt UEC files")
        else:
            print(f"❌ Found {problematic_mazs + zero_acres} potentially problematic MAZs")
            print("These could cause Stop Location Choice crashes")
        
    except Exception as e:
        print(f"Error during investigation: {e}")
        import traceback
        traceback.print_exc()

def suggest_fixes():
    """Suggest potential fixes for Stop Location Choice crashes"""
    print(f"\n=== SUGGESTED FIXES ===")
    print("1. Check for zero ACRES causing division by zero in density calculations")
    print("2. Verify retail employment consistency (ret_loc + ret_reg)")
    print("3. Ensure stop destination alternatives are available")
    print("4. Check UEC files for Stop Location Choice model")
    print("5. Look for specific household/tour patterns in the crash")

if __name__ == "__main__":
    investigate_stop_choice_issues()
    suggest_fixes()