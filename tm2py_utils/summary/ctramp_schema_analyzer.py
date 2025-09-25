"""
CTRAMP Schema Analyzer - Core functionality for analyzing CTRAMP model output schemas
"""

import pandas as pd
import numpy as np
from pathlib import Path
import os
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class CTRAMPSchemaAnalyzer:
    """
    Analyzer for CTRAMP model output file schemas
    """
    
    def __init__(self, data_directory: str):
        """
        Initialize the schema analyzer
        
        Args:
            data_directory: Path to directory containing CTRAMP output files
        """
        self.data_directory = Path(data_directory)
        self.schema_results = None
        self.validation_results = None
        
    def get_file_info(self, file_path: Path) -> Dict:
        """
        Analyze a single file and return its schema information
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            Dictionary containing file schema information
        """
        file_info = {
            'filename': file_path.name,
            'file_size_mb': round(file_path.stat().st_size / (1024 * 1024), 2),
            'file_extension': file_path.suffix.lower(),
            'columns': [],
            'data_types': {},
            'shape': None,
            'sample_data': None,
            'error': None
        }
        
        try:
            # Determine file type and read accordingly
            if file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path, nrows=1000)
            elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, nrows=1000)
            elif file_path.suffix.lower() == '.parquet':
                df = pd.read_parquet(file_path)
                df = df.head(1000)
            elif file_path.suffix.lower() in ['.txt', '.tsv']:
                try:
                    df = pd.read_csv(file_path, sep='\t', nrows=1000)
                except:
                    df = pd.read_csv(file_path, nrows=1000)
            else:
                df = pd.read_csv(file_path, nrows=1000)
            
            # Extract schema information
            file_info['columns'] = list(df.columns)
            file_info['data_types'] = {col: str(dtype) for col, dtype in df.dtypes.items()}
            file_info['shape'] = df.shape
            file_info['sample_data'] = df.head(3).to_dict('records')
            
        except Exception as e:
            file_info['error'] = str(e)
        
        return file_info
    
    def analyze_directory_schema(self) -> Dict:
        """
        Analyze all files in the directory and return comprehensive schema information
        
        Returns:
            Dictionary containing analysis results for all files
        """
        if not self.data_directory.exists():
            return {'error': f"Directory {self.data_directory} does not exist"}
        
        # Find all data files (common formats)
        data_extensions = {'.csv', '.xlsx', '.xls', '.parquet', '.txt', '.tsv', '.json'}
        data_files = []
        
        for ext in data_extensions:
            data_files.extend(list(self.data_directory.glob(f"*{ext}")))
            data_files.extend(list(self.data_directory.glob(f"**/*{ext}")))
        
        print(f"Found {len(data_files)} data files")
        
        # Analyze each file
        file_schemas = []
        for file_path in data_files:
            print(f"Analyzing: {file_path.name}")
            schema_info = self.get_file_info(file_path)
            file_schemas.append(schema_info)
        
        self.schema_results = {
            'directory': str(self.data_directory),
            'total_files': len(data_files),
            'file_schemas': file_schemas
        }
        
        return self.schema_results
    
    def create_schema_dataframe(self) -> pd.DataFrame:
        """
        Create a consolidated DataFrame with all schema information
        
        Returns:
            DataFrame with schema information for all files
        """
        if not self.schema_results:
            raise ValueError("Must run analyze_directory_schema() first")
        
        schema_rows = []
        
        for file_info in self.schema_results['file_schemas']:
            if file_info['error']:
                schema_rows.append({
                    'filename': file_info['filename'],
                    'file_size_mb': file_info['file_size_mb'],
                    'file_extension': file_info['file_extension'],
                    'column_name': None,
                    'data_type': None,
                    'error': file_info['error'],
                    'total_columns': None,
                    'total_rows': None
                })
            else:
                for col in file_info['columns']:
                    schema_rows.append({
                        'filename': file_info['filename'],
                        'file_size_mb': file_info['file_size_mb'],
                        'file_extension': file_info['file_extension'],
                        'column_name': col,
                        'data_type': file_info['data_types'].get(col, 'unknown'),
                        'error': None,
                        'total_columns': len(file_info['columns']),
                        'total_rows': file_info['shape'][0] if file_info['shape'] else None
                    })
        
        return pd.DataFrame(schema_rows)
    
    def print_schema_summary(self):
        """
        Print a formatted summary of the schema analysis results
        """
        if not self.schema_results:
            raise ValueError("Must run analyze_directory_schema() first")
        
        results = self.schema_results
        
        if 'error' in results:
            print(f"Error: {results['error']}")
            return
        
        print(f"\n📁 DIRECTORY ANALYSIS SUMMARY")
        print(f"Directory: {results['directory']}")
        print(f"Total Files Found: {results['total_files']}")
        print("="*80)
        
        for i, file_info in enumerate(results['file_schemas'], 1):
            print(f"\n📄 FILE {i}: {file_info['filename']}")
            print(f"   Size: {file_info['file_size_mb']} MB")
            print(f"   Extension: {file_info['file_extension']}")
            
            if file_info['error']:
                print(f"   ❌ Error: {file_info['error']}")
                continue
                
            print(f"   Shape: {file_info['shape']} (rows, columns)")
            print(f"   Columns ({len(file_info['columns'])}):")
            
            for col in file_info['columns']:
                dtype = file_info['data_types'].get(col, 'unknown')
                print(f"      • {col:<30} ({dtype})")
            
            if file_info['sample_data'] and len(file_info['sample_data']) > 0:
                print(f"   Sample Data (first row):")
                first_row = file_info['sample_data'][0]
                for key, value in list(first_row.items())[:5]:
                    print(f"      {key}: {value}")
                if len(first_row) > 5:
                    print(f"      ... and {len(first_row)-5} more columns")
            
            print("-"*60)
    
    def export_schema_csv(self, output_filename: str = "ctramp_data_schema.csv"):
        """
        Export schema information to CSV
        
        Args:
            output_filename: Name of the output CSV file
        """
        schema_df = self.create_schema_dataframe()
        schema_df.to_csv(output_filename, index=False)
        print(f"✅ Schema information exported to: {output_filename}")
        return output_filename