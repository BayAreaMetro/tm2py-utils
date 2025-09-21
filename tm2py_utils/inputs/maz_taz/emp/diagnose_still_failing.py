#!/usr/bin/env python3
"""
Quick diagnostic to check if the model is using a different employment data source
"""
import pandas as pd

def check_failing_households():
    """Check the specific households that are still failing"""
    print("=== CHECKING STILL-FAILING HOUSEHOLDS ===")
    
    failing_households = [3099534, 1161286, 1205990]
    failing_persons = [7549395, 2912749, 3013291]
    
    try:
        # Check both the model run directory and the Box directory
        model_run_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data_withDensity.csv"
        box_path = r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-test\landuse\maz_data_withDensity.csv"
        
        print(f"Checking model run file: {model_run_path}")
        model_df = pd.read_csv(model_run_path)
        
        print(f"Checking Box file: {box_path}")
        box_df = pd.read_csv(box_path)
        
        # Load work location results to get MAZ for these persons
        wsLoc_path = r"E:\TM2_2023_LU_Test3\model-files\runtime\wsLocResults_1.csv"
        print(f"Checking work locations: {wsLoc_path}")
        
        try:
            wsLoc_df = pd.read_csv(wsLoc_path)
        except:
            print("Could not find wsLocResults_1.csv - checking alternative location")
            wsLoc_path = r"C:\GitHub\travel-model-two\model-files\runtime\wsLocResults_1.csv"
            try:
                wsLoc_df = pd.read_csv(wsLoc_path)
            except:
                print("Work location results not found - analyzing general employment data")
                wsLoc_df = None
        
        if wsLoc_df is not None:
            print(f"\nAnalyzing failing persons' work locations:")
            for i, person_id in enumerate(failing_persons):
                hh_id = failing_households[i]
                work_data = wsLoc_df[wsLoc_df['PersonID'] == person_id]
                
                if len(work_data) > 0:
                    work_maz = work_data['WorkLocation'].iloc[0]
                    print(f"\nHousehold {hh_id}, Person {person_id}: Work MAZ = {work_maz}")
                    
                    # Check employment data for this MAZ in both files
                    model_maz_data = model_df[model_df['MAZ'] == work_maz]
                    box_maz_data = box_df[box_df['MAZ'] == work_maz]
                    
                    if len(model_maz_data) > 0:
                        emp_total_model = model_maz_data['emp_total'].iloc[0]
                        her_emp_model = model_maz_data.get('her_emp', [0]).iloc[0] if 'her_emp' in model_maz_data.columns else 0
                        print(f"  Model file - emp_total: {emp_total_model}, her_emp: {her_emp_model}")
                    else:
                        print(f"  MAZ {work_maz} not found in model file!")
                    
                    if len(box_maz_data) > 0:
                        emp_total_box = box_maz_data['emp_total'].iloc[0]
                        her_emp_box = box_maz_data.get('her_emp', [0]).iloc[0] if 'her_emp' in box_maz_data.columns else 0
                        print(f"  Box file - emp_total: {emp_total_box}, her_emp: {her_emp_box}")
                    else:
                        print(f"  MAZ {work_maz} not found in Box file!")
                else:
                    print(f"Person {person_id} not found in work location results")
        
        # Check if files are identical
        print(f"\n=== FILE COMPARISON ===")
        print(f"Model file rows: {len(model_df)}")
        print(f"Box file rows: {len(box_df)}")
        
        # Compare employment totals
        model_emp_total = model_df['emp_total'].sum()
        box_emp_total = box_df['emp_total'].sum()
        
        print(f"Model file total employment: {model_emp_total:,.0f}")
        print(f"Box file total employment: {box_emp_total:,.0f}")
        print(f"Files identical: {'YES' if model_emp_total == box_emp_total else 'NO'}")
        
        if model_emp_total != box_emp_total:
            print("❌ FILES ARE DIFFERENT - The copy may not have worked!")
            
            # Check file timestamps
            import os
            model_time = os.path.getmtime(model_run_path)
            box_time = os.path.getmtime(box_path)
            
            from datetime import datetime
            print(f"Model file timestamp: {datetime.fromtimestamp(model_time)}")
            print(f"Box file timestamp: {datetime.fromtimestamp(box_time)}")
        else:
            print("✅ Files appear identical")
        
        # Check if the model might be using a different file entirely
        print(f"\n=== ALTERNATIVE DATA SOURCES ===")
        print("The model might be reading from:")
        print("1. maz_data.csv (without density) instead of maz_data_withDensity.csv")
        print("2. A cached/compiled version of the data")
        print("3. A different path entirely")
        
        # Check the non-density file
        try:
            model_basic_path = r"E:\TM2_2023_LU_Test3\inputs\landuse\maz_data.csv"
            basic_df = pd.read_csv(model_basic_path)
            basic_emp_total = basic_df['emp_total'].sum()
            print(f"4. maz_data.csv total employment: {basic_emp_total:,.0f}")
            
            if basic_emp_total != model_emp_total:
                print("   ❌ maz_data.csv is DIFFERENT from maz_data_withDensity.csv!")
        except:
            print("4. maz_data.csv not found")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_failing_households()