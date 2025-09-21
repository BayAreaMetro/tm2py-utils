#!/usr/bin/env python3
"""
Deep dive into the employment mismatch
"""
import pandas as pd

def analyze_employment_mismatch():
    """Analyze the 13,214 MAZs with emp_total != calculated empTotal"""
    print("=== EMPLOYMENT MISMATCH ANALYSIS ===")
    
    try:
        # Load the data
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        
        # Define the subcategories for empTotal calculation
        subcategories = [
            'ag', 'natres',  # agr_emp
            'prof', 'lease', 'serv_bus', 'fire',  # fps_emp
            'art_rec', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'health', 'hotel', 'serv_pers', 'serv_soc',  # her_emp
            'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'transp', 'util',  # mwt_emp
            'ret_loc', 'ret_reg',  # ret_emp
            'constr', 'gov', 'info'  # oth_emp (util already included in mwt_emp)
        ]
        
        # Remove duplicate 'util' 
        subcategories = list(dict.fromkeys(subcategories))  # preserves order, removes duplicates
        
        print(f"Using {len(subcategories)} subcategories for empTotal calculation:")
        print(subcategories)
        
        # Calculate what empTotal should be
        df['empTotal_calculated'] = df[subcategories].sum(axis=1)
        
        # Find mismatches
        tolerance = 0.01
        mismatch = abs(df['emp_total'] - df['empTotal_calculated']) > tolerance
        print(f"\nMAZs with emp_total != calculated empTotal (>{tolerance}): {mismatch.sum():,}")
        
        if mismatch.sum() > 0:
            print("\n=== MISMATCH ANALYSIS ===")
            mismatch_df = df[mismatch][['MAZ', 'emp_total', 'empTotal_calculated']].copy()
            mismatch_df['difference'] = mismatch_df['emp_total'] - mismatch_df['empTotal_calculated']
            
            print("Sample mismatched MAZs:")
            print(mismatch_df.head(10).to_string(index=False))
            
            print(f"\nDifference statistics:")
            print(f"  Min difference: {mismatch_df['difference'].min():,.1f}")
            print(f"  Max difference: {mismatch_df['difference'].max():,.1f}")
            print(f"  Mean difference: {mismatch_df['difference'].mean():,.1f}")
            
            # Check if the difference matches serv_per vs serv_pers
            print(f"\n=== CHECKING serv_per vs serv_pers ===")
            if 'serv_per' in df.columns:
                df['serv_diff'] = df['serv_pers'] - df['serv_per']
                
                # Check if emp_total was calculated using serv_per instead of serv_pers
                subcategories_alt = subcategories.copy()
                if 'serv_pers' in subcategories_alt:
                    idx = subcategories_alt.index('serv_pers')
                    subcategories_alt[idx] = 'serv_per'
                    
                df['empTotal_with_serv_per'] = df[subcategories_alt].sum(axis=1)
                
                matches_serv_per = abs(df['emp_total'] - df['empTotal_with_serv_per']) <= tolerance
                print(f"MAZs where emp_total matches calculation with serv_per: {matches_serv_per.sum():,}")
                
                # Check the opposite direction too
                remaining_mismatches = ~matches_serv_per
                print(f"Remaining mismatches after serv_per correction: {remaining_mismatches.sum():,}")
                
                if matches_serv_per.sum() > mismatch_df.shape[0] * 0.8:  # If >80% match
                    print("✅ FOUND IT! emp_total was calculated using serv_per instead of serv_pers")
                else:
                    print("❌ serv_per doesn't explain the difference")
            else:
                print("serv_per column not found")
        
        # Now check the critical question: Do any MAZs have employment subcategories > 0 but emp_total = 0?
        print(f"\n=== CRASH CONDITION CHECK ===")
        
        # Check each employment category
        emp_categories = {
            'agr_emp': ['ag', 'natres'],
            'fps_emp': ['prof', 'lease', 'serv_bus', 'fire'],
            'her_emp': ['art_rec', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'health', 'hotel', 'serv_pers', 'serv_soc'],
            'mwt_emp': ['logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'transp', 'util'],
            'ret_emp': ['ret_loc', 'ret_reg'],
            'oth_emp': ['constr', 'gov', 'info', 'util']
        }
        
        for category, fields in emp_categories.items():
            df[category] = df[fields].sum(axis=1)
            
            # Find MAZs where this category > 0 but emp_total = 0 (the crash condition)
            crash_condition = (df[category] > 0) & (df['emp_total'] == 0)
            
            if crash_condition.sum() > 0:
                print(f"❌ CRASH RISK: {crash_condition.sum():,} MAZs have {category}>0 but emp_total=0")
                
                # Show examples
                examples = df[crash_condition][['MAZ', category, 'emp_total'] + fields].head()
                print("Examples:")
                print(examples.to_string(index=False))
                print()
            else:
                print(f"✅ {category}: No crash conditions")
        
        # Final check: Are there MAZs with ANY employment but emp_total=0?
        any_employment = df[subcategories].sum(axis=1) > 0
        zero_total = df['emp_total'] == 0
        critical_condition = any_employment & zero_total
        
        if critical_condition.sum() > 0:
            print(f"\n❌❌ CRITICAL CRASH CONDITION: {critical_condition.sum():,} MAZs have employment>0 but emp_total=0")
            print("These WILL cause ExplicitTelecommute to crash!")
            
            examples = df[critical_condition][['MAZ', 'emp_total'] + subcategories[:10]].head()
            print("Examples:")
            print(examples.to_string(index=False))
        else:
            print(f"\n✅ No critical crash conditions found")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_employment_mismatch()