#!/usr/bin/env python3
"""
Read and analyze the Stop Location Choice UEC file to identify issues
causing all MAZs to become unavailable for choice
"""
import pandas as pd
import numpy as np
import re

def read_stop_location_uec():
    """Read and analyze the Stop Location Choice UEC Excel file"""
    print("=== STOP LOCATION CHOICE UEC ANALYSIS ===")
    
    try:
        uec_path = r"c:\GitHub\travel-model-two\uec\StopLocationChoice.xls"
        
        # Read all sheets in the Excel file
        excel_file = pd.ExcelFile(uec_path)
        print(f"Found {len(excel_file.sheet_names)} sheets: {excel_file.sheet_names}")
        
        for i, sheet_name in enumerate(excel_file.sheet_names):
            print(f"\n=== SHEET {i}: {sheet_name} ===")
            
            try:
                df = pd.read_excel(uec_path, sheet_name=sheet_name, header=None)
                print(f"Sheet dimensions: {df.shape[0]} rows × {df.shape[1]} columns")
                
                # Look for key patterns in the UEC
                analyze_uec_sheet(df, sheet_name)
                
            except Exception as e:
                print(f"Error reading sheet {sheet_name}: {e}")
                
    except Exception as e:
        print(f"Error reading UEC file: {e}")
        import traceback
        traceback.print_exc()

def analyze_uec_sheet(df, sheet_name):
    """Analyze a UEC sheet for employment variables and size terms"""
    
    # Convert all cells to strings for pattern matching
    df_str = df.astype(str).fillna('')
    
    # Look for employment variable references
    employment_vars = [
        'emp_total', 'ret_loc', 'ret_reg', 'serv_pers', 'serv_per', 'health', 
        'eat', 'serv_soc', 'art_rec', 'gov', 'info', 'mfg', 'wtcu', 'fire',
        'retail', 'service'
    ]
    
    print(f"\n--- Employment Variable References ---")
    found_vars = set()
    
    for var in employment_vars:
        # Look for the variable name in any cell
        matches = df_str.apply(lambda x: x.str.contains(var, case=False, na=False)).any(axis=1).sum()
        if matches > 0:
            found_vars.add(var)
            print(f"  {var}: found in {matches} rows")
            
            # Show some examples
            for idx, row in df_str.iterrows():
                for col in df_str.columns:
                    cell_val = row[col]
                    if var.lower() in cell_val.lower() and len(cell_val) > len(var):
                        print(f"    Row {idx+1}, Col {col+1}: {cell_val[:100]}")
                        break
                if len([x for x in found_vars if var in str(x)]) >= 3:  # Limit examples
                    break
    
    print(f"\n--- Size Term Analysis ---")
    
    # Look for size-related expressions
    size_patterns = [
        r'size\w*',
        r'ln\s*\(',
        r'log\s*\(',
        r'exp\s*\(',
        r'/\s*[\w\.\s]+',  # Division operations
        r'\*\s*[\w\.\s]+', # Multiplication operations
    ]
    
    for pattern in size_patterns:
        pattern_matches = []
        for idx, row in df_str.iterrows():
            for col in df_str.columns:
                cell_val = row[col]
                if re.search(pattern, cell_val, re.IGNORECASE):
                    pattern_matches.append((idx+1, col+1, cell_val))
        
        if pattern_matches:
            print(f"\n  Pattern '{pattern}': {len(pattern_matches)} matches")
            for row_num, col_num, cell_val in pattern_matches[:5]:  # Show first 5
                print(f"    Row {row_num}, Col {col_num}: {cell_val[:80]}")
    
    print(f"\n--- Alternative Availability Analysis ---")
    
    # Look for availability conditions
    availability_patterns = [
        r'avail',
        r'available',
        r'!=\s*0',
        r'>\s*0',
        r'<\s*0',
        r'==\s*0',
    ]
    
    for pattern in availability_patterns:
        pattern_matches = []
        for idx, row in df_str.iterrows():
            for col in df_str.columns:
                cell_val = row[col]
                if re.search(pattern, cell_val, re.IGNORECASE):
                    pattern_matches.append((idx+1, col+1, cell_val))
        
        if pattern_matches:
            print(f"\n  Pattern '{pattern}': {len(pattern_matches)} matches")
            for row_num, col_num, cell_val in pattern_matches[:3]:  # Show first 3
                print(f"    Row {row_num}, Col {col_num}: {cell_val[:80]}")
    
    print(f"\n--- Utility Expressions ---")
    
    # Look for utility calculation expressions that might cause issues
    utility_patterns = [
        r'b_\w+',  # Beta coefficients
        r'@\w+',   # Variable references
        r'[+\-]\s*\d+\.?\d*\s*\*',  # Coefficient * variable patterns
    ]
    
    utility_expressions = []
    for idx, row in df_str.iterrows():
        for col in df_str.columns:
            cell_val = row[col]
            for pattern in utility_patterns:
                if re.search(pattern, cell_val, re.IGNORECASE) and len(cell_val) > 10:
                    utility_expressions.append((idx+1, col+1, cell_val))
                    break
    
    if utility_expressions:
        print(f"Found {len(utility_expressions)} utility expressions:")
        for row_num, col_num, expr in utility_expressions[:10]:  # Show first 10
            print(f"  Row {row_num}, Col {col_num}: {expr[:100]}")
    
    print(f"\n--- Potential Issues Detection ---")
    
    # Look for potential division by zero issues
    division_issues = []
    for idx, row in df_str.iterrows():
        for col in df_str.columns:
            cell_val = row[col]
            # Look for division where denominator could be zero
            if '/' in cell_val and ('emp_total' in cell_val or any(var in cell_val for var in employment_vars)):
                division_issues.append((idx+1, col+1, cell_val))
    
    if division_issues:
        print(f"⚠️  Found {len(division_issues)} potential division issues:")
        for row_num, col_num, expr in division_issues:
            print(f"  Row {row_num}, Col {col_num}: {expr}")
    else:
        print("✅ No obvious division by zero issues found")
    
    # Look for variable name mismatches
    print(f"\n--- Variable Name Issues ---")
    
    # Check for common typos
    typo_checks = [
        ('serv_per', 'serv_pers'),
        ('retail', 'ret_loc'),
        ('service', 'serv_pers'),
    ]
    
    for wrong_var, correct_var in typo_checks:
        wrong_count = df_str.apply(lambda x: x.str.contains(wrong_var, case=False, na=False)).sum().sum()
        correct_count = df_str.apply(lambda x: x.str.contains(correct_var, case=False, na=False)).sum().sum()
        
        if wrong_count > 0:
            print(f"⚠️  Found '{wrong_var}' ({wrong_count} times) - should be '{correct_var}'?")
        elif correct_count > 0:
            print(f"✅ Found '{correct_var}' ({correct_count} times)")

def check_variable_consistency():
    """Check if UEC variables match the employment data columns"""
    print(f"\n=== VARIABLE CONSISTENCY CHECK ===")
    
    # Our employment data columns
    emp_data_cols = [
        'emp_total', 'ret_loc', 'ret_reg', 'serv_pers', 'health', 'eat',
        'serv_soc', 'art_rec', 'gov', 'info', 'mfg', 'wtcu', 'fire'
    ]
    
    print("Employment data columns available:")
    for col in emp_data_cols:
        print(f"  ✅ {col}")
    
    print(f"\nNow check if the UEC file references any variables NOT in this list.")
    print("If the UEC references missing variables, that could cause all alternatives to be unavailable.")

if __name__ == "__main__":
    read_stop_location_uec()
    check_variable_consistency()
    
    print(f"\n=== DEBUGGING RECOMMENDATIONS ===")
    print("1. Look for employment variable references that don't match our data columns")
    print("2. Check for division operations that could cause division by zero")
    print("3. Examine availability conditions that might exclude all alternatives")
    print("4. Verify size term calculations use correct variable names")
    print("5. Check for negative utility expressions that make alternatives unavailable")