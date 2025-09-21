#!/usr/bin/env python3
"""
Investigate the specific household/person that crashed to understand
what MAZ data issues are causing NaN/Infinity in choice models
"""
import pandas as pd
import numpy as np
import os

def find_crashed_household_mazs():
    """Find the home and work MAZs for the crashed household/person"""
    print("=== INVESTIGATING CRASHED HOUSEHOLD/PERSON ===")
    print("HHID=2893704, PERSID=7049746")
    
    # File paths
    popsyn_dir = r"E:\TM2_2023_LU_Test3\inputs\popsyn"
    landuse_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
    
    try:
        # Load household data
        households_path = os.path.join(popsyn_dir, "households.csv")
        if not os.path.exists(households_path):
            print(f"❌ Households file not found: {households_path}")
            return None, None
        
        households_df = pd.read_csv(households_path)
        print(f"Loaded {len(households_df):,} households")
        
        # Find the specific household
        target_hh = households_df[households_df['HHID'] == 2893704]
        
        if len(target_hh) == 0:
            print(f"❌ Household HHID=2893704 not found in households.csv")
            return None, None
        
        print(f"\n--- HOUSEHOLD INFORMATION ---")
        print(f"Found household HHID=2893704:")
        
        # Show household details
        for col in target_hh.columns:
            value = target_hh[col].iloc[0]
            print(f"  {col}: {value}")
        
        home_maz = target_hh['MAZ'].iloc[0] if 'MAZ' in target_hh.columns else None
        home_maz_original = target_hh['MAZ_ORIGINAL'].iloc[0] if 'MAZ_ORIGINAL' in target_hh.columns else None
        
        print(f"\nHome MAZ: {home_maz}")
        print(f"Home MAZ_ORIGINAL: {home_maz_original}")
        
        # Load work location results to get work MAZ
        work_results_path = r"E:\TM2_2023_LU_Test3\ctramp_output\wsLocResults_2.csv"
        work_maz = None
        
        if os.path.exists(work_results_path):
            print(f"\n--- WORK LOCATION INFORMATION ---")
            work_results_df = pd.read_csv(work_results_path)
            print(f"Loaded {len(work_results_df):,} work location records")
            
            # Find the specific person's work location
            target_work = work_results_df[work_results_df['person_id'] == 7049746]
            
            if len(target_work) > 0:
                print(f"Found work location for PERSID=7049746:")
                work_record = target_work.iloc[0]
                
                # Show work location details
                for col in target_work.columns:
                    value = work_record[col]
                    print(f"  {col}: {value}")
                
                work_maz = work_record.get('WorkLocation', work_record.get('work_maz', work_record.get('MAZ', None)))
                print(f"\nWork MAZ: {work_maz}")
            else:
                print(f"❌ Person PERSID=7049746 work location not found in wsLocResults_2.csv")
        else:
            print(f"⚠️ Work location results file not found: {work_results_path}")
            print("   Trying to load from persons.csv instead...")
            
            # Fallback to persons.csv
            persons_path = os.path.join(popsyn_dir, "persons.csv")
            if os.path.exists(persons_path):
                persons_df = pd.read_csv(persons_path)
                print(f"Loaded {len(persons_df):,} persons from fallback file")
                
                # Find the specific person
                target_person = persons_df[persons_df['PERID'] == 7049746]
                
                if len(target_person) > 0:
                    print(f"Found person PERSID=7049746 in persons.csv:")
                    person_record = target_person.iloc[0]
                    
                    # Show person details
                    for col in target_person.columns:
                        value = person_record[col]
                        print(f"  {col}: {value}")
                    
                    work_maz = person_record.get('MAZ_wploc', person_record.get('work_maz', None))
                else:
                    print(f"❌ Person PERSID=7049746 not found in persons.csv either")
        
        return home_maz, work_maz
        
    except Exception as e:
        print(f"Error loading household/person data: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def analyze_maz_data(home_maz, work_maz):
    """Analyze the MAZ data for home and work locations"""
    print(f"\n=== ANALYZING MAZ DATA FOR CRASH LOCATIONS ===")
    
    if home_maz is None and work_maz is None:
        print("❌ No MAZ information found - cannot analyze")
        return
    
    try:
        # Load land use data
        landuse_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        landuse_df = pd.read_csv(landuse_path)
        print(f"Loaded land use data: {len(landuse_df):,} MAZ records")
        
        mazs_to_check = []
        if home_maz is not None:
            mazs_to_check.append(('Home', home_maz))
        if work_maz is not None:
            mazs_to_check.append(('Work', work_maz))
        
        for location_type, maz_id in mazs_to_check:
            print(f"\n--- {location_type.upper()} MAZ {maz_id} ANALYSIS ---")
            
            # Find the MAZ in land use data
            maz_data = landuse_df[landuse_df['MAZ'] == maz_id]
            
            if len(maz_data) == 0:
                print(f"❌ MAZ {maz_id} not found in land use data!")
                print("   This could cause choice model crashes!")
                continue
            
            maz_record = maz_data.iloc[0]
            
            # Check all key fields for issues
            print(f"MAZ {maz_id} data:")
            
            # Employment data
            emp_total = maz_record.get('emp_total', 'MISSING')
            hh_count = maz_record.get('HH', 'MISSING')
            pop = maz_record.get('POP', 'MISSING')
            acres = maz_record.get('ACRES', 'MISSING')
            
            print(f"  emp_total: {emp_total}")
            print(f"  HH: {hh_count}")
            print(f"  POP: {pop}")
            print(f"  ACRES: {acres}")
            
            # Coordinates
            maz_x = maz_record.get('MAZ_X', 'MISSING')
            maz_y = maz_record.get('MAZ_Y', 'MISSING')
            
            print(f"  MAZ_X: {maz_x}")
            print(f"  MAZ_Y: {maz_y}")
            
            # Density fields (these often cause NaN/Infinity)
            emp_den = maz_record.get('EmpDen', 'MISSING')
            ret_emp_den = maz_record.get('RetEmpDen', 'MISSING')
            pop_den = maz_record.get('PopDen', 'MISSING')
            pop_emp_den = maz_record.get('PopEmpDenPerMi', 'MISSING')
            
            print(f"  EmpDen: {emp_den}")
            print(f"  RetEmpDen: {ret_emp_den}")
            print(f"  PopDen: {pop_den}")
            print(f"  PopEmpDenPerMi: {pop_emp_den}")
            
            # Check for problematic values
            issues = []
            
            # Check for division by zero sources
            if acres == 0:
                issues.append("ACRES = 0 → causes Infinity in density calculations")
            
            # Check for invalid coordinates
            if maz_x == -1 or maz_y == -1:
                issues.append("Invalid coordinates (-1) → causes NaN in distance calculations")
            
            # Check for NaN/Infinity in density fields
            if pd.isna(emp_den) or np.isinf(emp_den):
                issues.append(f"EmpDen is NaN/Infinity: {emp_den}")
            
            if pd.isna(ret_emp_den) or np.isinf(ret_emp_den):
                issues.append(f"RetEmpDen is NaN/Infinity: {ret_emp_den}")
            
            if pd.isna(pop_den) or np.isinf(pop_den):
                issues.append(f"PopDen is NaN/Infinity: {pop_den}")
            
            if pd.isna(pop_emp_den) or np.isinf(pop_emp_den):
                issues.append(f"PopEmpDenPerMi is NaN/Infinity: {pop_emp_den}")
            
            # Check for zero values that might cause ln(0)
            if emp_total == 0:
                issues.append("emp_total = 0 → ln(emp_total) = NaN")
            
            if hh_count == 0:
                issues.append("HH = 0 → ln(HH) = NaN")
            
            if pop == 0:
                issues.append("POP = 0 → ln(POP) = NaN")
            
            # Report issues
            if issues:
                print(f"\n❌ ISSUES FOUND for {location_type} MAZ {maz_id}:")
                for i, issue in enumerate(issues, 1):
                    print(f"   {i}. {issue}")
                print("\n🎯 These issues likely caused the choice model crash!")
            else:
                print(f"\n✅ No obvious issues found for {location_type} MAZ {maz_id}")
            
            # Show employment breakdown
            print(f"\n  Employment breakdown:")
            emp_cols = ['ret_loc', 'ret_reg', 'serv_pers', 'health', 'eat', 'serv_soc', 'art_rec', 'gov', 'info']
            for emp_col in emp_cols:
                if emp_col in maz_record:
                    value = maz_record[emp_col]
                    print(f"    {emp_col}: {value}")
    
    except Exception as e:
        print(f"Error analyzing MAZ data: {e}")
        import traceback
        traceback.print_exc()

def suggest_specific_fixes(home_maz, work_maz):
    """Suggest specific fixes for the identified issues"""
    print(f"\n=== SPECIFIC FIX RECOMMENDATIONS ===")
    
    print("Based on the analysis above, here are targeted fixes:")
    print("\n1. If ACRES = 0:")
    print("   - Replace with small positive value (0.001)")
    print("   - Or set all density fields to 0 when ACRES = 0")
    
    print("\n2. If coordinates are -1:")
    print("   - Set emp_total = 0 and HH = 0")
    print("   - This excludes MAZ from choice sets")
    
    print("\n3. If density fields are Infinity/NaN:")
    print("   - Recalculate using corrected ACRES")
    print("   - Add bounds checking (cap at reasonable max)")
    
    print("\n4. If employment/population = 0 causes ln(0):")
    print("   - Add small constant: ln(value + 0.001)")
    print("   - Or add availability conditions in UEC")

if __name__ == "__main__":
    home_maz, work_maz = find_crashed_household_mazs()
    
    if home_maz is not None or work_maz is not None:
        analyze_maz_data(home_maz, work_maz)
        suggest_specific_fixes(home_maz, work_maz)
    else:
        print("\n❌ Could not find household/person data for analysis")
    
    print(f"\n=== SUMMARY ===")
    print("This analysis should reveal exactly which MAZ data values")
    print("are causing the NaN/Infinity in choice model utilities.")