#!/usr/bin/env python3
"""
Analyze TM2 model run logs to identify crashes and issues
"""
import os
import glob
from pathlib import Path

def analyze_tm2_logs():
    """Scan TM2 logs for crashes and errors"""
    print("=== TM2 LOG ANALYSIS ===")
    
    log_dir = Path(r"E:\TM2_2023_LU_Test3\logs")
    
    if not log_dir.exists():
        print(f"❌ Log directory not found: {log_dir}")
        return
    
    print(f"Scanning logs in: {log_dir}")
    
    # Find all log files
    log_files = []
    for ext in ['*.log', '*.txt', '*.out', '*.err']:
        log_files.extend(log_dir.glob(ext))
    
    if not log_files:
        print("No log files found")
        return
    
    print(f"Found {len(log_files)} log files:")
    for log_file in sorted(log_files):
        size = log_file.stat().st_size
        modified = log_file.stat().st_mtime
        print(f"  {log_file.name} ({size:,} bytes)")
    
    # Keywords to search for crashes/errors
    error_keywords = [
        "Exception", "Error", "CRASH", "FATAL", "java.lang.InvocationTargetException",
        "no available explicit telecommute options", "NaN", "Infinity", "division by zero",
        "OutOfMemoryError", "NullPointerException", "RuntimeException", "StackOverflowError",
        "Unable to", "Cannot", "Failed", "Terminated", "Aborted"
    ]
    
    print(f"\n=== ERROR ANALYSIS ===")
    
    # Analyze each log file
    total_errors = 0
    
    for log_file in sorted(log_files):
        try:
            print(f"\n--- {log_file.name} ---")
            
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            file_errors = 0
            recent_errors = []  # Keep track of recent errors
            
            for i, line in enumerate(lines):
                line_clean = line.strip()
                
                # Check for error keywords
                for keyword in error_keywords:
                    if keyword.lower() in line_clean.lower():
                        file_errors += 1
                        total_errors += 1
                        
                        # Store error context (line number, content)
                        context_start = max(0, i-2)
                        context_end = min(len(lines), i+3)
                        context_lines = [f"  {j+1:4d}: {lines[j].rstrip()}" for j in range(context_start, context_end)]
                        
                        error_info = {
                            'line_num': i+1,
                            'keyword': keyword,
                            'line': line_clean,
                            'context': context_lines
                        }
                        recent_errors.append(error_info)
                        break  # Don't double-count same line
            
            if file_errors > 0:
                print(f"  🚨 {file_errors} errors found")
                
                # Show the most recent/relevant errors
                for error in recent_errors[-3:]:  # Show last 3 errors
                    print(f"\n  Error at line {error['line_num']} (keyword: {error['keyword']}):")
                    for context_line in error['context']:
                        if str(error['line_num']) in context_line.split(':')[0]:
                            print(f"  >>> {context_line}")  # Highlight the error line
                        else:
                            print(f"      {context_line}")
            else:
                print(f"  ✅ No errors detected")
                
        except Exception as e:
            print(f"  ❌ Could not read log file: {e}")
    
    print(f"\n=== SUMMARY ===")
    print(f"Total errors found: {total_errors}")
    
    if total_errors == 0:
        print("✅ No errors detected in log files")
        print("The model may have run successfully or the crash might be elsewhere")
    else:
        print("🚨 Errors detected - review the details above")
        print("Recent/largest log files are most likely to contain the current crash")
    
    # Show most recent files
    print(f"\n=== MOST RECENT LOG FILES ===")
    recent_files = sorted(log_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]
    
    for log_file in recent_files:
        import datetime
        modified_time = datetime.datetime.fromtimestamp(log_file.stat().st_mtime)
        size = log_file.stat().st_size
        print(f"  {log_file.name}: {modified_time.strftime('%Y-%m-%d %H:%M:%S')} ({size:,} bytes)")

def search_specific_errors():
    """Search for specific error patterns that might indicate the new crash"""
    print(f"\n=== SPECIFIC ERROR SEARCH ===")
    
    log_dir = Path(r"E:\TM2_2023_LU_Test3\logs")
    
    # Specific patterns to look for
    search_patterns = [
        ("ExplicitTelecommute", "Telecommute model issues"),
        ("InvocationTargetException", "Java RMI call failures"),
        ("NaN", "Mathematical computation errors"),
        ("Infinity", "Division by zero or overflow"),
        ("OutOfMemoryError", "Memory exhaustion"),
        ("no available.*options", "Choice model failures"),
        ("Exception in thread", "Threading issues"),
        ("at com.pb.mtctm2", "MTCTM2-specific crashes"),
        ("choiceModelApplication", "Choice model crashes")
    ]
    
    for pattern, description in search_patterns:
        print(f"\nSearching for: {pattern} ({description})")
        
        matching_files = 0
        matching_lines = 0
        
        for log_file in log_dir.glob("*.log"):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                file_matches = []
                for i, line in enumerate(lines):
                    if pattern.lower() in line.lower():
                        matching_lines += 1
                        file_matches.append((i+1, line.strip()))
                
                if file_matches:
                    matching_files += 1
                    print(f"  📁 {log_file.name}: {len(file_matches)} matches")
                    
                    # Show first few matches
                    for line_num, line_content in file_matches[:2]:
                        print(f"    Line {line_num}: {line_content[:100]}...")
                        
            except Exception as e:
                continue
        
        if matching_lines == 0:
            print(f"  ✅ No matches found")
        else:
            print(f"  🔍 Found {matching_lines} lines in {matching_files} files")

if __name__ == "__main__":
    analyze_tm2_logs()
    search_specific_errors()
    
    print(f"\n=== NEXT STEPS ===")
    print(f"1. Look at the most recent log files with errors")
    print(f"2. Check for Java stack traces or specific error messages")
    print(f"3. Look for household IDs or model components mentioned in crashes")
    print(f"4. Check if the crash is in a different model step than ExplicitTelecommute")