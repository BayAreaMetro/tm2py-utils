#!/usr/bin/env python3
"""
Check if the UEC employment expressions match the actual data columns
"""
import pandas as pd

def check_uec_employment_mapping():
    """Check if UEC expressions match the actual employment data"""
    print("=== UEC EMPLOYMENT MAPPING CHECK ===")
    
    # Employment categories from the UEC expressions (what the model expects)
    uec_employment_fields = {
        'agr_emp': ['ag', 'natres'],  # Expression 4: ag+natres
        'fps_emp': ['prof', 'lease', 'serv_bus', 'fire'],  # Expression 5: prof+lease+serv_bus+fire
        'her_emp': ['art_rec', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'health', 'hotel', 'serv_pers', 'serv_soc'],  # Expression 6
        'mwt_emp': ['logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'transp', 'util'],  # Expression 7
        'ret_emp': ['ret_loc', 'ret_reg'],  # Expression 8
        'oth_emp': ['constr', 'gov', 'info', 'util']  # Expression 10: constr+gov+info+util
    }
    
    try:
        # Load the model run data
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        
        print(f"Loaded {len(df)} MAZ records from model run directory")
        print(f"Available columns: {len(df.columns)}")
        
        # Get all employment-related columns
        emp_cols = [col for col in df.columns if any(x in col.lower() for x in ['emp', 'ag', 'art', 'constr', 'eat', 'ed_', 'fire', 'gov', 'health', 'hotel', 'info', 'lease', 'logis', 'man_', 'natres', 'prof', 'ret_', 'serv', 'transp', 'util'])]
        
        print(f"\nEmployment-related columns found ({len(emp_cols)}):")
        for col in sorted(emp_cols):
            non_zero = (df[col] > 0).sum()
            total_val = df[col].sum()
            print(f"  {col}: {non_zero:,} MAZs with >0 values, total = {total_val:,.0f}")
        
        print(f"\n=== UEC EXPRESSION ANALYSIS ===")
        
        # Check each UEC employment category
        for uec_category, required_fields in uec_employment_fields.items():
            print(f"\n{uec_category} (UEC Expression):")
            print(f"  Expected fields: {required_fields}")
            
            available_fields = [field for field in required_fields if field in df.columns]
            missing_fields = [field for field in required_fields if field not in df.columns]
            
            print(f"  Available fields: {available_fields}")
            if missing_fields:
                print(f"  ❌ Missing fields: {missing_fields}")
            
            if available_fields:
                # Calculate what the UEC would compute
                uec_calculated = df[available_fields].sum(axis=1)
                non_zero_mazs = (uec_calculated > 0).sum()
                total_employment = uec_calculated.sum()
                
                print(f"  UEC calculated total: {total_employment:,.0f}")
                print(f"  MAZs with >0 employment: {non_zero_mazs:,}")
                
                # Find MAZs where this category has employment but empTotal would be 0
                df[f'{uec_category}_calc'] = uec_calculated
            else:
                print(f"  ⚠️ No available fields - UEC would calculate 0")
        
        # Calculate what empTotal (Expression 9) would be
        print(f"\n=== EXPRESSION 9 (empTotal) ANALYSIS ===")
        
        all_subcategories = []
        for fields in uec_employment_fields.values():
            all_subcategories.extend(fields)
        
        # Remove duplicates (util appears twice)
        unique_subcategories = list(set(all_subcategories))
        available_subcategories = [field for field in unique_subcategories if field in df.columns]
        missing_subcategories = [field for field in unique_subcategories if field not in df.columns]
        
        print(f"All unique subcategories expected: {len(unique_subcategories)}")
        print(f"Available subcategories: {len(available_subcategories)}")
        if missing_subcategories:
            print(f"❌ Missing subcategories: {missing_subcategories}")
        
        if available_subcategories:
            df['empTotal_calculated'] = df[available_subcategories].sum(axis=1)
            
            # Compare with actual emp_total
            mismatch = abs(df['emp_total'] - df['empTotal_calculated']) > 0.01
            print(f"MAZs where emp_total ≠ calculated empTotal: {mismatch.sum():,}")
            
            # Find problematic cases (Expression 6 > 0 but empTotal = 0)
            if 'her_emp_calc' in df.columns:
                problematic = (df['her_emp_calc'] > 0) & (df['empTotal_calculated'] == 0)
                print(f"❌ CRITICAL: MAZs with her_emp>0 but empTotal=0: {problematic.sum():,}")
                
                if problematic.sum() > 0:
                    print("Sample problematic MAZs:")
                    sample = df[problematic][['MAZ', 'her_emp_calc', 'empTotal_calculated', 'emp_total']].head()
                    print(sample)
            
            # Check if empTotal=0 but subcategories>0 (the crash condition)
            zero_total_nonzero_subs = (df['empTotal_calculated'] == 0) & (df[available_subcategories] > 0).any(axis=1)
            if zero_total_nonzero_subs.sum() > 0:
                print(f"❌ CRASH CONDITION: {zero_total_nonzero_subs.sum():,} MAZs have empTotal=0 but subcategories>0")
                print("These would cause division by zero in ExplicitTelecommute!")
            else:
                print("✅ No crash conditions found")
                
        else:
            print("❌ Cannot calculate empTotal - no subcategories available")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_uec_employment_mapping()