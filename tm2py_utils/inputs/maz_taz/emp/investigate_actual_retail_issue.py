#!/usr/bin/env python3
"""
FRESH investigation of the retail share division by zero issue
No assumptions - find the actual problem
"""
import pandas as pd
import numpy as np

def investigate_actual_retail_issue():
    """Find the actual retail share division by zero problem"""
    print("=== ACTUAL RETAIL ISSUE INVESTIGATION ===")
    
    try:
        # Load the employment data
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        print(f"Loaded employment data: {len(df)} MAZ records")
        
        print(f"\nFirst, let's see the actual numbers:")
        print(f"emp_total = 0: {(df['emp_total'] == 0).sum():,} MAZs")
        print(f"emp_total > 0: {(df['emp_total'] > 0).sum():,} MAZs")
        
        # Check retail employment
        if all(col in df.columns for col in ['ret_loc', 'ret_reg']):
            df['retail_total'] = df['ret_loc'] + df['ret_reg']
            
            print(f"retail_total = 0: {(df['retail_total'] == 0).sum():,} MAZs")
            print(f"retail_total > 0: {(df['retail_total'] > 0).sum():,} MAZs")
            
            # The real question: how many MAZs have retail > 0 but emp_total = 0?
            retail_nonzero = df['retail_total'] > 0
            emp_zero = df['emp_total'] == 0
            
            problem_mazs = retail_nonzero & emp_zero
            print(f"\nretail_total > 0 AND emp_total = 0: {problem_mazs.sum():,} MAZs")
            
            if problem_mazs.sum() > 0:
                print("❌ FOUND THE DIVISION BY ZERO ISSUE!")
                print("\nThese MAZs would cause: retail_share = retail_total / emp_total = X / 0 = ∞")
                
                # Show examples
                examples = df[problem_mazs][['MAZ', 'retail_total', 'emp_total', 'ret_loc', 'ret_reg']].head(10)
                print("\nExamples of problematic MAZs:")
                print(examples.to_string(index=False))
                
                return problem_mazs.sum()
            else:
                print("✅ No retail/emp_total division by zero found")
                
        # Check the opposite direction - what if the issue is in the calculation itself?
        print(f"\n=== CHECKING CALCULATION CONSISTENCY ===")
        
        # Load all employment columns
        emp_cols = [col for col in df.columns if col in [
            'ag', 'art_rec', 'constr', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'fire', 'gov', 'health',
            'hotel', 'info', 'lease', 'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'natres', 
            'prof', 'ret_loc', 'ret_reg', 'serv_bus', 'serv_pers', 'serv_soc', 'transp', 'util'
        ]]
        
        print(f"Found {len(emp_cols)} employment columns")
        
        # Calculate what emp_total SHOULD be
        df['emp_total_calculated'] = df[emp_cols].sum(axis=1)
        
        # Compare with actual emp_total
        mismatch = abs(df['emp_total'] - df['emp_total_calculated']) > 0.01
        print(f"MAZs where emp_total ≠ sum of employment: {mismatch.sum():,}")
        
        # Now check the REAL issue - what happens when we use the correct emp_total?
        retail_nonzero = df['retail_total'] > 0
        calculated_emp_zero = df['emp_total_calculated'] == 0
        
        real_problem = retail_nonzero & calculated_emp_zero
        print(f"retail_total > 0 AND emp_total_calculated = 0: {real_problem.sum():,} MAZs")
        
        if real_problem.sum() > 0:
            print("❌ FOUND IT! The issue is with the CALCULATED emp_total")
            
            examples = df[real_problem][['MAZ', 'retail_total', 'emp_total', 'emp_total_calculated', 'ret_loc', 'ret_reg']].head(10)
            print("Examples:")
            print(examples.to_string(index=False))
            
            # This means retail employment exists but no other employment - which is impossible
            # Let's see what's actually in these MAZs
            problem_sample = df[real_problem].iloc[0]
            print(f"\nDetailed breakdown for MAZ {problem_sample['MAZ']}:")
            for col in emp_cols:
                value = problem_sample[col]
                if value > 0:
                    print(f"  {col}: {value}")
                    
        else:
            print("✅ No issues with calculated emp_total either")
            
        # Maybe the issue is that emp_total is correct but there are 9,842 MAZs with retail but zero total employment?
        # This would be a legitimate case where retail_share = retail / 0 = ∞
        
        zero_employment_mazs = df['emp_total_calculated'] == 0
        zero_with_retail = zero_employment_mazs & (df['retail_total'] > 0)
        
        print(f"\n=== ZERO EMPLOYMENT ANALYSIS ===")
        print(f"MAZs with zero total employment: {zero_employment_mazs.sum():,}")
        print(f"MAZs with zero employment but retail > 0: {zero_with_retail.sum():,}")
        
        if zero_with_retail.sum() > 0:
            print("❌ This IS the problem!")
            print("These MAZs have retail employment but their calculated total is 0")
            print("This suggests data inconsistency in the retail employment fields")
            
            # Check what's actually in ret_loc and ret_reg for these MAZs
            problem_retail = df[zero_with_retail]
            print(f"\nBreakdown of problematic retail MAZs:")
            print(f"ret_loc values: min={problem_retail['ret_loc'].min()}, max={problem_retail['ret_loc'].max()}, mean={problem_retail['ret_loc'].mean():.1f}")
            print(f"ret_reg values: min={problem_retail['ret_reg'].min()}, max={problem_retail['ret_reg'].max()}, mean={problem_retail['ret_reg'].mean():.1f}")
            
            return zero_with_retail.sum()
            
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return -1

if __name__ == "__main__":
    problem_count = investigate_actual_retail_issue()
    
    if problem_count > 0:
        print(f"\n=== SUMMARY ===")
        print(f"Found {problem_count:,} MAZs that will cause retail_share division by zero")
        print("This explains the Stop Location Choice crashes!")
    else:
        print(f"\n=== SUMMARY ===")
        print("No retail share division by zero issues found")
        print("The Stop Location Choice crash must be caused by something else")