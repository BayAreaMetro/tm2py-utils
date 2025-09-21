#!/usr/bin/env python3
"""
Show before/after UEC calculations for MAZs that would have crashed
"""
import pandas as pd

def demonstrate_uec_fix():
    """Show UEC calculations with both old and new employment calculation methods"""
    print("=== UEC EXPRESSION FIX DEMONSTRATION ===")
    
    try:
        # Load the fixed employment data
        model_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        df = pd.read_csv(model_path)
        print(f"Loaded employment data: {len(df)} MAZ records")
        
        # Calculate UEC expressions the NEW way (using serv_pers)
        df['agr_emp_new'] = df['ag'] + df['natres']
        df['fps_emp_new'] = df['prof'] + df['lease'] + df['serv_bus'] + df['fire'] 
        df['her_emp_new'] = df['art_rec'] + df['eat'] + df['ed_high'] + df['ed_k12'] + df['ed_oth'] + df['health'] + df['hotel'] + df['serv_pers'] + df['serv_soc']  # Uses serv_pers
        df['mwt_emp_new'] = df['logis'] + df['man_bio'] + df['man_hvy'] + df['man_lgt'] + df['man_tech'] + df['transp'] + df['util']
        df['ret_emp_new'] = df['ret_loc'] + df['ret_reg']
        df['oth_emp_new'] = df['constr'] + df['gov'] + df['info'] + df['util']
        
        # empTotal NEW way (using serv_pers) - matches emp_total field
        unique_emp_cols_new = ['ag', 'natres', 'prof', 'lease', 'serv_bus', 'fire', 'art_rec', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'health', 'hotel', 'serv_pers', 'serv_soc', 'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'transp', 'util', 'ret_loc', 'ret_reg', 'constr', 'gov', 'info']
        df['empTotal_new'] = df[unique_emp_cols_new].sum(axis=1)
        
        # Calculate UEC expressions the OLD way (using serv_per - what was causing crashes)
        if 'serv_per' in df.columns:
            df['her_emp_old'] = df['art_rec'] + df['eat'] + df['ed_high'] + df['ed_k12'] + df['ed_oth'] + df['health'] + df['hotel'] + df['serv_per'] + df['serv_soc']  # Uses serv_per
            unique_emp_cols_old = ['ag', 'natres', 'prof', 'lease', 'serv_bus', 'fire', 'art_rec', 'eat', 'ed_high', 'ed_k12', 'ed_oth', 'health', 'hotel', 'serv_per', 'serv_soc', 'logis', 'man_bio', 'man_hvy', 'man_lgt', 'man_tech', 'transp', 'util', 'ret_loc', 'ret_reg', 'constr', 'gov', 'info']
            df['empTotal_old'] = df[unique_emp_cols_old].sum(axis=1)
        else:
            print("serv_per column not found - cannot demonstrate old calculation")
            return
            
        # Find MAZs that would have crashed with old calculation
        crash_candidates_old = (df['her_emp_new'] > 0) & (df['empTotal_old'] == 0)
        crash_candidates_new = (df['her_emp_new'] > 0) & (df['empTotal_new'] == 0)
        
        print(f"\n=== CRASH CONDITION ANALYSIS ===")
        print(f"MAZs with her_emp > 0 but empTotal = 0 (OLD method): {crash_candidates_old.sum():,}")
        print(f"MAZs with her_emp > 0 but empTotal = 0 (NEW method): {crash_candidates_new.sum():,}")
        
        if crash_candidates_old.sum() > 0:
            print(f"\n=== SAMPLE MAZs THAT WOULD HAVE CRASHED (OLD METHOD) ===")
            
            sample_mazs = df[crash_candidates_old].head(5)
            
            for idx, maz in sample_mazs.iterrows():
                maz_id = maz['MAZ'] if 'MAZ' in df.columns else maz['MAZ_ORIGINAL']
                print(f"\n--- MAZ {maz_id} ---")
                print(f"  serv_pers: {maz['serv_pers']:.1f}")
                print(f"  serv_per:  {maz['serv_per']:.1f}")
                print(f"  ")
                print(f"  OLD calculation (would crash):")
                print(f"    Expression 6 (her_emp): {maz['her_emp_old']:.1f}")
                print(f"    Expression 9 (empTotal): {maz['empTotal_old']:.1f}")
                if maz['empTotal_old'] == 0:
                    print(f"    Expression 13 (her_share): {maz['her_emp_old']:.1f} / 0.0 = ∞ → NaN → CRASH! 💥")
                else:
                    print(f"    Expression 13 (her_share): {maz['her_emp_old']:.1f} / {maz['empTotal_old']:.1f} = {maz['her_emp_old']/maz['empTotal_old']:.4f}")
                
                print(f"  ")
                print(f"  NEW calculation (fixed):")
                print(f"    Expression 6 (her_emp): {maz['her_emp_new']:.1f}")
                print(f"    Expression 9 (empTotal): {maz['empTotal_new']:.1f}")
                print(f"    Expression 13 (her_share): {maz['her_emp_new']:.1f} / {maz['empTotal_new']:.1f} = {maz['her_emp_new']/maz['empTotal_new']:.4f} ✅")
                
                print(f"  emp_total field: {maz['emp_total']:.1f}")
                print(f"  Consistency check: empTotal_new = emp_total? {abs(maz['empTotal_new'] - maz['emp_total']) < 0.01}")
        else:
            print("No crash candidates found with old method")
            
        # Show overall fix statistics
        print(f"\n=== FIX EFFECTIVENESS ===")
        total_her_emp = (df['her_emp_new'] > 0).sum()
        
        if 'empTotal_old' in df.columns:
            old_crashes = ((df['her_emp_new'] > 0) & (df['empTotal_old'] == 0)).sum()
            new_crashes = ((df['her_emp_new'] > 0) & (df['empTotal_new'] == 0)).sum()
            
            print(f"MAZs with her_emp > 0: {total_her_emp:,}")
            print(f"Would crash with OLD empTotal calculation: {old_crashes:,} ({100*old_crashes/total_her_emp:.1f}%)")
            print(f"Will crash with NEW empTotal calculation: {new_crashes:,} ({100*new_crashes/total_her_emp:.1f}%)")
            print(f"Crashes prevented: {old_crashes - new_crashes:,}")
            
            if new_crashes == 0:
                print(f"🎉 100% SUCCESS: All ExplicitTelecommute crashes prevented!")
            else:
                print(f"⚠️ Partial fix: {new_crashes:,} potential crashes remain")
        
        # Verify the employment shares sum correctly
        print(f"\n=== EMPLOYMENT SHARE VALIDATION ===")
        
        # Take a sample MAZ with employment
        sample_maz = df[df['empTotal_new'] > 0].iloc[0]
        maz_id = sample_maz['MAZ'] if 'MAZ' in df.columns else sample_maz['MAZ_ORIGINAL']
        
        agr_share = sample_maz['agr_emp_new'] / sample_maz['empTotal_new']
        fps_share = sample_maz['fps_emp_new'] / sample_maz['empTotal_new']
        her_share = sample_maz['her_emp_new'] / sample_maz['empTotal_new']
        mwt_share = sample_maz['mwt_emp_new'] / sample_maz['empTotal_new']
        ret_share = sample_maz['ret_emp_new'] / sample_maz['empTotal_new']
        oth_share = sample_maz['oth_emp_new'] / sample_maz['empTotal_new']
        
        total_share = agr_share + fps_share + her_share + mwt_share + ret_share + oth_share
        
        print(f"Sample MAZ {maz_id} employment shares:")
        print(f"  agr_share: {agr_share:.4f}")
        print(f"  fps_share: {fps_share:.4f}")
        print(f"  her_share: {her_share:.4f}")
        print(f"  mwt_share: {mwt_share:.4f}")
        print(f"  ret_share: {ret_share:.4f}")
        print(f"  oth_share: {oth_share:.4f}")
        print(f"  Total:     {total_share:.4f} {'✅' if abs(total_share - 1.0) < 0.001 else '❌'}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demonstrate_uec_fix()