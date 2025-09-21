#!/usr/bin/env python3
"""
Investigate why ALL MAZs are becoming unavailable for stop location choice
The issue is likely that the filtering logic is excluding ALL MAZs instead of just empty ones
"""
import pandas as pd
import numpy as np

def analyze_stop_choice_availability():
    """Analyze what MAZs should be available for stop location choice"""
    print("=== STOP LOCATION CHOICE AVAILABILITY ANALYSIS ===")
    
    try:
        # Load the employment data
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        print(f"Loaded employment data: {len(df)} MAZ records")
        
        # Check the filtering logic: MAZs with zero employment AND zero households should be excluded
        print(f"\n=== STOP CHOICE FILTERING LOGIC ===")
        
        zero_employment = df['emp_total'] == 0
        zero_households = df['HH'] == 0 if 'HH' in df.columns else pd.Series([False] * len(df))
        
        # MAZs that SHOULD be excluded (both zero employment AND zero households)
        should_exclude = zero_employment & zero_households
        
        # MAZs that SHOULD be available (either has employment OR has households)
        should_include = (~zero_employment) | (~zero_households)
        
        print(f"Total MAZs: {len(df):,}")
        print(f"Zero employment: {zero_employment.sum():,}")
        print(f"Zero households: {zero_households.sum():,}")
        print(f"Should EXCLUDE (zero emp AND zero HH): {should_exclude.sum():,}")
        print(f"Should INCLUDE (has emp OR has HH): {should_include.sum():,}")
        
        if should_include.sum() > 0:
            print(f"✅ {should_include.sum():,} MAZs should be available for stops")
        else:
            print(f"❌ CRITICAL: NO MAZs would be available for stops!")
            return
            
        # Break down what types of MAZs should be available
        print(f"\n=== AVAILABLE MAZ BREAKDOWN ===")
        
        has_emp_and_hh = (~zero_employment) & (~zero_households)
        has_emp_no_hh = (~zero_employment) & zero_households
        has_hh_no_emp = zero_employment & (~zero_households)
        
        print(f"Has employment AND households: {has_emp_and_hh.sum():,}")
        print(f"Has employment, NO households: {has_emp_no_hh.sum():,}")
        print(f"Has households, NO employment: {has_hh_no_emp.sum():,}")
        
        # Check if the issue is with the size terms for stop purposes
        print(f"\n=== STOP PURPOSE SIZE TERMS ===")
        
        stop_purposes = {
            'shopping': ['ret_loc', 'ret_reg'],
            'personal': ['serv_pers', 'health'],  
            'social': ['serv_soc', 'art_rec'],
            'eating': ['eat'],
            'other': ['gov', 'info']
        }
        
        total_available_by_purpose = {}
        
        for purpose, emp_types in stop_purposes.items():
            available_cols = [col for col in emp_types if col in df.columns]
            
            if available_cols:
                # MAZs available for this purpose (has this type of employment)
                purpose_employment = df[available_cols].sum(axis=1)
                purpose_available = (purpose_employment > 0) & should_include  # Must also pass the basic filter
                
                total_available_by_purpose[purpose] = purpose_available.sum()
                total_employment = purpose_employment[purpose_available].sum()
                
                print(f"{purpose}: {purpose_available.sum():,} MAZs ({total_employment:,.0f} jobs)")
                
                if purpose_available.sum() == 0:
                    print(f"  ❌ CRITICAL: NO MAZs available for {purpose} stops!")
            else:
                print(f"{purpose}: ❌ No employment columns found")
                total_available_by_purpose[purpose] = 0
        
        # Check if ANY purpose has available MAZs
        total_purposes_with_mazs = sum(1 for count in total_available_by_purpose.values() if count > 0)
        
        if total_purposes_with_mazs == 0:
            print(f"\n❌ CRITICAL ISSUE FOUND!")
            print(f"NO stop purposes have any available MAZs!")
            print(f"This will cause ALL stop location choices to fail")
        else:
            print(f"\n✅ {total_purposes_with_mazs} stop purposes have available MAZs")
        
        # Now check what might be going wrong in the choice model
        print(f"\n=== CHOICE MODEL FAILURE DIAGNOSIS ===")
        
        # The most likely issues:
        
        # 1. UEC expressions expecting different size variables
        print(f"1. Size variable issues:")
        print(f"   - Check if UEC expects different employment categories")
        print(f"   - Look for missing or renamed employment fields")
        
        # 2. Distance/accessibility issues
        print(f"2. Accessibility issues:")
        print(f"   - Check MAZ coordinates for invalid values")
        invalid_coords = ((df['MAZ_X'] == -1) | (df['MAZ_Y'] == -1)).sum() if 'MAZ_X' in df.columns else 0
        print(f"   - Invalid coordinates: {invalid_coords:,} MAZs")
        
        # 3. Utility calculation overflow/underflow
        print(f"3. Utility calculation issues:")
        for col in ['EmpDen', 'RetEmpDen', 'PopDen', 'PopEmpDenPerMi']:
            if col in df.columns:
                extreme_vals = (df[col] > 10000).sum()
                print(f"   - {col} extreme values (>10000): {extreme_vals:,} MAZs")
        
        # 4. Sample rate or filtering issues
        print(f"4. Model configuration issues:")
        print(f"   - Check if sample rates are causing all alternatives to be filtered out")
        print(f"   - Verify choice set generation parameters")
        print(f"   - Check if distance/time constraints are too restrictive")
        
        # 5. Show which MAZs should definitely be available
        print(f"\n=== SAMPLE AVAILABLE MAZs ===")
        
        # Find MAZs that have both employment and households (most likely to be valid stops)
        best_stop_mazs = has_emp_and_hh & (df[['ret_loc', 'ret_reg', 'serv_pers', 'eat']].sum(axis=1) > 0)
        
        if best_stop_mazs.sum() > 0:
            sample = df[best_stop_mazs][['MAZ', 'TAZ', 'emp_total', 'HH', 'ret_loc', 'ret_reg', 'serv_pers', 'eat']].head(10)
            print("Sample MAZs that should definitely be available for stops:")
            print(sample.to_string(index=False))
        else:
            print("❌ No clear good stop MAZs found")
            
        return total_purposes_with_mazs > 0
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def suggest_debugging_steps():
    """Suggest specific debugging steps for the choice model failure"""
    print(f"\n=== DEBUGGING STEPS ===")
    
    print("To find why ALL MAZs are unavailable:")
    
    print(f"\n1. Check UEC Size Variable References:")
    print("   - Open Stop Location Choice UEC files")
    print("   - Verify size variable names match employment data columns")
    print("   - Check for typos in variable names (e.g., 'serv_per' vs 'serv_pers')")
    
    print(f"\n2. Add Debug Logging:")
    print("   - Add logging in IntermediateStopChoiceModels.java")
    print("   - Log the number of alternatives before/after filtering")
    print("   - Log utility calculations for sample alternatives")
    
    print(f"\n3. Check Choice Set Generation:")
    print("   - Verify distance/time constraints aren't excluding everything")
    print("   - Check if coordinate system issues cause distance calculations to fail")
    print("   - Look for accessibility matrix issues")
    
    print(f"\n4. Test with Simpler Data:")
    print("   - Try with a small subset of households/tours")
    print("   - Test if the issue is consistent or random")
    print("   - Check if it fails on the first tour or after many successful ones")

if __name__ == "__main__":
    success = analyze_stop_choice_availability()
    
    if success:
        suggest_debugging_steps()
    else:
        print(f"\n❌ CRITICAL DATA ISSUE: No MAZs would be available for stops")
        print("This explains the NullPointerException - the choice model has no alternatives to choose from")
    
    print(f"\n=== KEY INSIGHT ===")
    print("The crash happens because ChoiceModelApplication.getChoiceResult() returns null")
    print("when there are no alternatives available for the choice.")
    print("Need to find why the filtering/choice set generation excludes ALL MAZs.")