#!/usr/bin/env python3
"""
Investigate and fix retail employment share division by zero issues
Similar to the ExplicitTelecommute fix but for Stop Location Choice
"""
import pandas as pd
import numpy as np

def analyze_retail_share_division_by_zero():
    """Analyze the retail_share = retail_emp / emp_total division by zero issue"""
    print("=== RETAIL SHARE DIVISION BY ZERO ANALYSIS ===")
    
    try:
        # Load the employment data
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        print(f"Loaded employment data: {len(df)} MAZ records")
        
        # Calculate retail employment (what the UEC would calculate)
        if all(col in df.columns for col in ['ret_loc', 'ret_reg']):
            df['retail_emp'] = df['ret_loc'] + df['ret_reg']
        else:
            print("❌ ERROR: ret_loc and/or ret_reg columns not found")
            return
            
        # Identify the division by zero problem
        retail_emp_nonzero = df['retail_emp'] > 0
        emp_total_zero = df['emp_total'] == 0
        
        # The crash condition: retail_emp > 0 but emp_total = 0
        crash_condition = retail_emp_nonzero & emp_total_zero
        
        print(f"\n=== DIVISION BY ZERO ANALYSIS ===")
        print(f"MAZs with retail_emp > 0: {retail_emp_nonzero.sum():,}")
        print(f"MAZs with emp_total = 0: {emp_total_zero.sum():,}")
        print(f"MAZs with retail_emp > 0 BUT emp_total = 0 (CRASH): {crash_condition.sum():,}")
        
        if crash_condition.sum() > 0:
            print(f"\n❌ CRITICAL: {crash_condition.sum():,} MAZs will cause retail_share division by zero!")
            
            # Show examples of the crash condition
            crash_examples = df[crash_condition][['MAZ', 'retail_emp', 'emp_total', 'ret_loc', 'ret_reg']].head(10)
            print("\nSample MAZs that will crash:")
            print(crash_examples.to_string(index=False))
            
            # Calculate what the retail_share would be (∞)
            print(f"\nUEC Expression calculation:")
            sample_maz = crash_examples.iloc[0]
            print(f"Example MAZ {sample_maz['MAZ']}:")
            print(f"  retail_emp = ret_loc + ret_reg = {sample_maz['ret_loc']} + {sample_maz['ret_reg']} = {sample_maz['retail_emp']}")
            print(f"  emp_total = {sample_maz['emp_total']}")
            print(f"  retail_share = retail_emp / emp_total = {sample_maz['retail_emp']} / {sample_maz['emp_total']} = ∞ → NaN → CRASH! 💥")
        else:
            print(f"✅ No division by zero conditions found")
        
        # Check the reverse: MAZs with emp_total > 0 but retail_emp = 0 (valid, no crash)
        valid_zero_retail = (~retail_emp_nonzero) & (~emp_total_zero)
        print(f"MAZs with emp_total > 0 but retail_emp = 0 (valid): {valid_zero_retail.sum():,}")
        
        # Show the employment breakdown for crash MAZs
        if crash_condition.sum() > 0:
            print(f"\n=== EMPLOYMENT BREAKDOWN FOR CRASH MAZs ===")
            
            crash_mazs = df[crash_condition]
            
            # Show which employment categories these MAZs actually have
            emp_cols = ['ag', 'art_rec', 'constr', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'fire', 'gov', 'health',
                       'hotel', 'info', 'lease', 'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'natres', 
                       'prof', 'ret_loc', 'ret_reg', 'serv_bus', 'serv_pers', 'serv_soc', 'transp', 'util']
            
            available_emp_cols = [col for col in emp_cols if col in df.columns]
            
            # Calculate what emp_total SHOULD be
            crash_mazs_copy = crash_mazs.copy()
            crash_mazs_copy['emp_total_calculated'] = crash_mazs_copy[available_emp_cols].sum(axis=1)
            
            print("Sample crash MAZs with corrected emp_total:")
            sample_cols = ['MAZ', 'retail_emp', 'emp_total', 'emp_total_calculated', 'ret_loc', 'ret_reg']
            print(crash_mazs_copy[sample_cols].head().to_string(index=False))
            
            # Show what retail_share would be with corrected emp_total
            crash_sample = crash_mazs_copy.iloc[0]
            corrected_retail_share = crash_sample['retail_emp'] / crash_sample['emp_total_calculated']
            print(f"\nWith corrected emp_total:")
            print(f"  retail_share = {crash_sample['retail_emp']} / {crash_sample['emp_total_calculated']} = {corrected_retail_share:.4f} ✅")
            
        return crash_condition.sum()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return -1

def check_other_employment_shares():
    """Check if other employment share calculations have similar issues"""
    print(f"\n=== OTHER EMPLOYMENT SHARE ISSUES ===")
    
    try:
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        
        # Define employment categories for different shares (similar to ExplicitTelecommute)
        employment_categories = {
            'agr_share': ['ag', 'natres'],
            'fps_share': ['prof', 'lease', 'serv_bus', 'fire'],
            'her_share': ['art_rec', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'health', 'hotel', 'serv_pers', 'serv_soc'],
            'mwt_share': ['logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'transp', 'util'],
            'ret_share': ['ret_loc', 'ret_reg'],  # This is the problematic one
            'oth_share': ['constr', 'gov', 'info', 'util']
        }
        
        total_crash_mazs = 0
        
        for share_name, emp_cols in employment_categories.items():
            available_cols = [col for col in emp_cols if col in df.columns]
            
            if not available_cols:
                print(f"{share_name}: ❌ No employment columns available")
                continue
                
            # Calculate the employment category total
            df[f'{share_name}_emp'] = df[available_cols].sum(axis=1)
            
            # Find crash condition: category > 0 but emp_total = 0
            category_nonzero = df[f'{share_name}_emp'] > 0
            emp_total_zero = df['emp_total'] == 0
            crash_condition = category_nonzero & emp_total_zero
            
            crash_count = crash_condition.sum()
            total_crash_mazs += crash_count
            
            if crash_count > 0:
                print(f"{share_name}: ❌ {crash_count:,} MAZs will cause division by zero")
            else:
                print(f"{share_name}: ✅ No division by zero issues")
        
        print(f"\nTotal MAZs with employment share division by zero issues: {total_crash_mazs:,}")
        
        if total_crash_mazs > 0:
            print(f"❌ CRITICAL: These will cause Stop Location Choice and other choice model crashes!")
        
    except Exception as e:
        print(f"Error checking other shares: {e}")

def propose_fix():
    """Propose the fix for retail share division by zero"""
    print(f"\n=== PROPOSED FIX ===")
    
    print("The issue is identical to what we fixed with ExplicitTelecommute:")
    print("1. emp_total field has incorrect values (likely calculated with wrong employment categories)")
    print("2. This causes division by zero when calculating employment shares in UEC expressions")
    print("3. The fix is to recalculate emp_total correctly using the employment fixing script")
    
    print(f"\nSolution:")
    print("1. The employment fixing script (update_emp.py) should have already fixed this")
    print("2. If crashes persist, there may be cached/different employment data being used")
    print("3. Need to verify which employment data files the Stop Location Choice model actually reads")
    
    print(f"\nNext steps:")
    print("1. Verify the current employment data has been properly fixed")
    print("2. Check if Stop Location Choice uses different data files")
    print("3. Ensure all choice models use consistent employment totals")

if __name__ == "__main__":
    crash_count = analyze_retail_share_division_by_zero()
    
    if crash_count > 0:
        check_other_employment_shares()
        propose_fix()
    else:
        print("✅ No retail share division by zero issues found!")
        print("The crash might be caused by a different issue.")