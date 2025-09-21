#!/usr/bin/env python3
"""
Calculate UEC expression values for the previously failing households
to verify that the division by zero crashes are resolved
"""
import pandas as pd

def calculate_uec_values_for_failing_households():
    """Calculate UEC expressions for households that were previously crashing"""
    print("=== UEC EXPRESSION VALUES FOR PREVIOUSLY FAILING HOUSEHOLDS ===")
    
    # Previously failing households and their work MAZs
    failing_cases = {
        3099534: 7549395,
        1161286: 2912749, 
        1205990: 3013291
    }
    
    try:
        # Load the fixed employment data
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        print(f"Loaded employment data: {len(df)} MAZ records")
        
        # UEC expressions from ExplicitTelecommute.xls
        # Expression 4: agr_emp = ag + natres
        # Expression 5: fps_emp = prof + lease + serv_bus + fire  
        # Expression 6: her_emp = art_rec + eat + ed_high + ed_k12 + ed_oth + health + hotel + serv_pers + serv_soc
        # Expression 7: mwt_emp = logis + man_bio + man_hvy + man_lgt + man_tech + transp + util
        # Expression 8: ret_emp = ret_loc + ret_reg
        # Expression 9: empTotal = ag + natres + prof + lease + serv_bus + fire + art_rec + eat + ed_high + ed_k12 + ed_oth + health + hotel + serv_pers + serv_soc + logis + man_bio + man_hvy + man_lgt + man_tech + transp + util + ret_loc + ret_reg + constr + gov + info
        # Expression 10: oth_emp = constr + gov + info + util (NOTE: util appears twice - in mwt_emp and oth_emp)
        
        # Calculate UEC expressions
        df['agr_emp'] = df['ag'] + df['natres']  # Expression 4
        df['fps_emp'] = df['prof'] + df['lease'] + df['serv_bus'] + df['fire']  # Expression 5
        df['her_emp'] = df['art_rec'] + df['eat'] + df['ed_high'] + df['ed_k12'] + df['ed_oth'] + df['health'] + df['hotel'] + df['serv_pers'] + df['serv_soc']  # Expression 6
        df['mwt_emp'] = df['logis'] + df['man_bio'] + df['man_hvy'] + df['man_lgt'] + df['man_tech'] + df['transp'] + df['util']  # Expression 7
        df['ret_emp'] = df['ret_loc'] + df['ret_reg']  # Expression 8
        
        # Expression 9: empTotal - sum of all unique employment categories (util counted only once)
        unique_emp_cols = ['ag', 'natres', 'prof', 'lease', 'serv_bus', 'fire', 'art_rec', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'health', 'hotel', 'serv_pers', 'serv_soc', 'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'transp', 'util', 'ret_loc', 'ret_reg', 'constr', 'gov', 'info']
        df['empTotal'] = df[unique_emp_cols].sum(axis=1)  # Expression 9
        
        df['oth_emp'] = df['constr'] + df['gov'] + df['info'] + df['util']  # Expression 10
        
        # UEC expressions 11-16: Employment shares (these were causing division by zero)
        df['agr_share'] = df['agr_emp'] / df['empTotal']  # Expression 11: agr_emp / empTotal 
        df['fps_share'] = df['fps_emp'] / df['empTotal']  # Expression 12: fps_emp / empTotal
        df['her_share'] = df['her_emp'] / df['empTotal']  # Expression 13: her_emp / empTotal  ← This was crashing!
        df['mwt_share'] = df['mwt_emp'] / df['empTotal']  # Expression 14: mwt_emp / empTotal
        df['ret_share'] = df['ret_emp'] / df['empTotal']  # Expression 15: ret_emp / empTotal
        df['oth_share'] = df['oth_emp'] / df['empTotal']  # Expression 16: oth_emp / empTotal
        
        print(f"\n=== ANALYSIS OF PREVIOUSLY FAILING HOUSEHOLDS ===")
        
        for household_id, work_maz in failing_cases.items():
            print(f"\n--- Household {household_id} (Work MAZ: {work_maz}) ---")
            
            # Find the MAZ record
            maz_record = df[df['MAZ'] == work_maz]
            if len(maz_record) == 0:
                # Try MAZ_ORIGINAL
                maz_record = df[df['MAZ_ORIGINAL'] == work_maz]
            
            if len(maz_record) == 0:
                print(f"  ❌ Work MAZ {work_maz} not found in employment data")
                continue
                
            maz = maz_record.iloc[0]
            
            print(f"  Work MAZ {work_maz} employment data:")
            print(f"    Expression 4 (agr_emp): {maz['agr_emp']:.1f}")
            print(f"    Expression 5 (fps_emp): {maz['fps_emp']:.1f}")
            print(f"    Expression 6 (her_emp): {maz['her_emp']:.1f}")  # This had values before
            print(f"    Expression 7 (mwt_emp): {maz['mwt_emp']:.1f}")
            print(f"    Expression 8 (ret_emp): {maz['ret_emp']:.1f}")
            print(f"    Expression 9 (empTotal): {maz['empTotal']:.1f}")  # This was 0 before, causing crashes
            print(f"    Expression 10 (oth_emp): {maz['oth_emp']:.1f}")
            
            # Check if this would still cause division by zero
            if maz['empTotal'] == 0:
                print(f"    ❌ STILL WOULD CRASH: empTotal = 0, cannot calculate shares")
                if maz['her_emp'] > 0:
                    print(f"    ❌ CRITICAL: her_emp = {maz['her_emp']:.1f} but empTotal = 0")
            else:
                print(f"    ✅ NO CRASH: empTotal > 0, can calculate employment shares")
                print(f"    Employment shares:")
                print(f"      Expression 11 (agr_share): {maz['agr_share']:.4f}")
                print(f"      Expression 12 (fps_share): {maz['fps_share']:.4f}")
                print(f"      Expression 13 (her_share): {maz['her_share']:.4f}")  # The problematic one
                print(f"      Expression 14 (mwt_share): {maz['mwt_share']:.4f}")
                print(f"      Expression 15 (ret_share): {maz['ret_share']:.4f}")
                print(f"      Expression 16 (oth_share): {maz['oth_share']:.4f}")
                
                # Verify shares sum to 1.0
                total_share = maz['agr_share'] + maz['fps_share'] + maz['her_share'] + maz['mwt_share'] + maz['ret_share'] + maz['oth_share']
                print(f"      Total shares: {total_share:.4f} {'✅' if abs(total_share - 1.0) < 0.001 else '❌'}")
            
            # Show key employment details
            print(f"    Key employment fields:")
            print(f"      serv_pers (personal services): {maz['serv_pers']:.1f}")
            if 'serv_per' in df.columns:
                print(f"      serv_per (old field): {maz['serv_per']:.1f}")
            print(f"      emp_total (stored field): {maz['emp_total']:.1f}")
            
            # Check consistency
            if abs(maz['empTotal'] - maz['emp_total']) < 0.01:
                print(f"      ✅ CONSISTENT: empTotal matches emp_total")
            else:
                print(f"      ❌ INCONSISTENT: empTotal ({maz['empTotal']:.1f}) ≠ emp_total ({maz['emp_total']:.1f})")
        
        # Overall statistics
        print(f"\n=== OVERALL EMPLOYMENT DATA HEALTH ===")
        zero_empTotal = (df['empTotal'] == 0).sum()
        nonzero_components_zero_total = ((df[unique_emp_cols] > 0).any(axis=1) & (df['empTotal'] == 0)).sum()
        
        print(f"MAZs with empTotal = 0: {zero_empTotal:,}")
        print(f"MAZs with employment>0 but empTotal=0 (crash risk): {nonzero_components_zero_total:,}")
        
        if nonzero_components_zero_total == 0:
            print(f"✅ SUCCESS: No MAZs will cause ExplicitTelecommute division by zero crashes!")
        else:
            print(f"❌ WARNING: {nonzero_components_zero_total:,} MAZs still at risk of crashes")
            
        # Check her_emp specifically (Expression 6) since this was the main failing one
        her_emp_nonzero = (df['her_emp'] > 0).sum()
        her_emp_with_zero_total = ((df['her_emp'] > 0) & (df['empTotal'] == 0)).sum()
        
        print(f"MAZs with her_emp > 0: {her_emp_nonzero:,}")
        print(f"MAZs with her_emp > 0 but empTotal = 0: {her_emp_with_zero_total:,}")
        
        if her_emp_with_zero_total == 0:
            print(f"✅ EXPRESSION 13 SAFE: her_emp/empTotal will never divide by zero")
        else:
            print(f"❌ EXPRESSION 13 RISK: {her_emp_with_zero_total:,} MAZs would cause her_share crashes")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    calculate_uec_values_for_failing_households()