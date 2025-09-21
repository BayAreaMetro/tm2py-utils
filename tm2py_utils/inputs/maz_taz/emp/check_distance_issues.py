#!/usr/bin/env python3
"""
Check for distance calculation issues that could cause 
Stop Location Choice to have no valid alternatives
"""
import pandas as pd
import numpy as np

def check_distance_calculation_issues():
    """Check for coordinate and distance issues"""
    print("=== DISTANCE CALCULATION ISSUES ANALYSIS ===")
    
    try:
        # Load land use data
        landuse_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(landuse_path)
        
        print(f"Loaded {len(df)} MAZ records")
        
        # Check coordinate validity
        print(f"\n=== COORDINATE VALIDATION ===")
        
        invalid_x = (df['MAZ_X'] == -1).sum()
        invalid_y = (df['MAZ_Y'] == -1).sum()  
        invalid_both = ((df['MAZ_X'] == -1) | (df['MAZ_Y'] == -1)).sum()
        
        print(f"MAZs with invalid X coordinate (-1): {invalid_x}")
        print(f"MAZs with invalid Y coordinate (-1): {invalid_y}")
        print(f"MAZs with any invalid coordinates: {invalid_both}")
        
        if invalid_both > 0:
            print(f"⚠️  {invalid_both} MAZs have invalid coordinates!")
            
            # Show sample of MAZs with invalid coordinates
            invalid_mazs = df[(df['MAZ_X'] == -1) | (df['MAZ_Y'] == -1)]
            print(f"\nSample MAZs with invalid coordinates:")
            print(invalid_mazs[['MAZ', 'TAZ', 'MAZ_X', 'MAZ_Y', 'emp_total', 'HH']].head(10))
        
        # Check coordinate ranges
        print(f"\n=== COORDINATE RANGES ===")
        valid_coords = df[(df['MAZ_X'] != -1) & (df['MAZ_Y'] != -1)]
        
        print(f"Valid coordinate MAZs: {len(valid_coords)}")
        print(f"X coordinate range: {valid_coords['MAZ_X'].min():.1f} to {valid_coords['MAZ_X'].max():.1f}")
        print(f"Y coordinate range: {valid_coords['MAZ_Y'].min():.1f} to {valid_coords['MAZ_Y'].max():.1f}")
        
        # Check for extreme coordinate values that might cause calculation issues
        extreme_coords = 0
        if len(valid_coords) > 0:
            x_std = valid_coords['MAZ_X'].std()
            y_std = valid_coords['MAZ_Y'].std()
            x_mean = valid_coords['MAZ_X'].mean()
            y_mean = valid_coords['MAZ_Y'].mean()
            
            # Flag coordinates more than 5 standard deviations from mean
            extreme_x = abs(valid_coords['MAZ_X'] - x_mean) > 5 * x_std
            extreme_y = abs(valid_coords['MAZ_Y'] - y_mean) > 5 * y_std
            extreme_coords = (extreme_x | extreme_y).sum()
            
            print(f"MAZs with extreme coordinates (>5σ from mean): {extreme_coords}")
        
        # Check impact on available alternatives
        print(f"\n=== IMPACT ON STOP ALTERNATIVES ===")
        
        # MAZs that should be available for stops but have invalid coordinates
        should_be_available = (df['emp_total'] > 0) | (df['HH'] > 0)
        invalid_coords_mask = (df['MAZ_X'] == -1) | (df['MAZ_Y'] == -1)
        
        unavailable_due_to_coords = should_be_available & invalid_coords_mask
        
        print(f"MAZs that should be stop alternatives: {should_be_available.sum():,}")
        print(f"Of these, MAZs with invalid coordinates: {unavailable_due_to_coords.sum()}")
        
        if unavailable_due_to_coords.sum() > 0:
            print(f"⚠️  {unavailable_due_to_coords.sum()} potential stop locations have invalid coordinates!")
            
            # Show some examples
            problematic = df[unavailable_due_to_coords][['MAZ', 'TAZ', 'emp_total', 'HH', 'MAZ_X', 'MAZ_Y']]
            print(f"\nSample problematic MAZs:")
            print(problematic.head(10))
        
        # Check if this could explain the crash
        valid_alternatives = should_be_available & ~invalid_coords_mask
        print(f"\nMAZs available as stop alternatives (with valid coords): {valid_alternatives.sum():,}")
        
        if valid_alternatives.sum() == 0:
            print(f"❌ CRITICAL: NO MAZs have both valid coordinates AND activity!")
            return False
        elif valid_alternatives.sum() < 100:
            print(f"⚠️  Very few MAZs available as alternatives ({valid_alternatives.sum()})")
        else:
            print(f"✅ Sufficient MAZs available as alternatives")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_distance_matrix_issues():
    """Check for issues that could affect distance matrix calculations"""
    print(f"\n=== DISTANCE MATRIX ISSUES ===")
    
    print("Potential distance calculation problems:")
    print("1. Invalid coordinates (-1, -1) cause distance = NaN or infinity")
    print("2. Coordinate system mismatch between MAZ locations and network")
    print("3. Missing or corrupted distance matrices")
    print("4. Extremely large distances due to coordinate errors")
    
    print(f"\n=== DIAGNOSTIC RECOMMENDATIONS ===")
    print("1. Check model logs for distance calculation errors")
    print("2. Verify coordinate system (State Plane, UTM, etc.)")
    print("3. Test distance calculations between sample MAZ pairs")
    print("4. Check if network and MAZ coordinates use same projection")

def suggest_coordinate_fix():
    """Suggest how to fix coordinate issues"""
    print(f"\n=== COORDINATE FIX SUGGESTIONS ===")
    
    print("For MAZs with invalid coordinates (-1, -1):")
    print("1. Check if these MAZs should exist (maybe they're water/unbuildable areas)")
    print("2. If they should exist, get correct coordinates from GIS data")
    print("3. If they shouldn't be alternatives, ensure they have emp_total=0 AND HH=0")
    
    print(f"\nImmediate fix to test:")
    print("1. Filter out MAZs with invalid coordinates from choice sets")
    print("2. Add validation in choice model to skip alternatives with coord = -1")
    print("3. Update land use data with correct coordinates")

if __name__ == "__main__":
    coords_ok = check_distance_calculation_issues()
    
    if not coords_ok:
        print(f"\n❌ COORDINATE ISSUES FOUND - This could explain the crash")
    else:
        print(f"\n✅ Coordinate issues present but not fatal")
    
    check_distance_matrix_issues()
    suggest_coordinate_fix()
    
    print(f"\n=== HYPOTHESIS UPDATE ===")
    print("The crash may be caused by:")
    print("1. Distance calculations failing due to invalid coordinates")
    print("2. Alternative sampling excluding all MAZs due to distance issues") 
    print("3. Choice model finding no valid alternatives after distance filtering")
    print("4. ChoiceModelApplication.getChoiceResult() returning null")
    print("5. NullPointerException at line 1843")