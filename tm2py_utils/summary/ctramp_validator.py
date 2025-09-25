"""
CTRAMP Validator - Validation functions for CTRAMP model outputs
"""

import pandas as pd
from typing import Dict, List
from .ctramp_documentation import (
    ENHANCED_CTRAMP_SCHEMAS, 
    identify_ctramp_file_type,
    get_analysis_guidance
)


class CTRAMPValidator:
    """
    Validator for CTRAMP model output files
    """
    
    def __init__(self):
        self.validation_results = []
    
    def validate_schema_against_documentation(self, file_info: Dict) -> Dict:
        """
        Validate discovered schema against expected CTRAMP documentation
        
        Args:
            file_info: Dictionary containing file schema information
            
        Returns:
            Dictionary containing validation results
        """
        filename = file_info['filename']
        file_type_key, expected_schema, description = identify_ctramp_file_type(filename)
        
        validation_result = {
            'filename': filename,
            'identified_type': file_type_key,
            'description': description,
            'validation_status': 'unknown',
            'missing_fields': [],
            'unexpected_fields': [],
            'field_match_percentage': 0,
            'total_expected_fields': 0,
            'total_actual_fields': len(file_info.get('columns', [])),
            'has_utility_fields': False,
            'has_probability_fields': False,
            'appears_to_be_ctramp': False
        }
        
        if file_info.get('error'):
            validation_result['validation_status'] = 'error'
            return validation_result
            
        actual_columns = set(file_info.get('columns', []))
        
        if expected_schema:
            expected_fields = set(expected_schema['expected_fields'])
            validation_result['total_expected_fields'] = len(expected_fields)
            validation_result['appears_to_be_ctramp'] = True
            
            # Find missing and unexpected fields
            validation_result['missing_fields'] = list(expected_fields - actual_columns)
            validation_result['unexpected_fields'] = list(actual_columns - expected_fields)
            
            # Calculate match percentage (only for core fields, utility/prob fields are dynamic)
            core_expected = {f for f in expected_fields if not (f.startswith('util_') or f.startswith('prob_'))}
            matching_fields = len(core_expected & actual_columns)
            if len(core_expected) > 0:
                validation_result['field_match_percentage'] = (matching_fields / len(core_expected)) * 100
            
            # Check for utility and probability fields (mode choice models)
            validation_result['has_utility_fields'] = any(col.startswith('util_') for col in actual_columns)
            validation_result['has_probability_fields'] = any(col.startswith('prob_') for col in actual_columns)
            
            # Determine overall validation status
            if validation_result['field_match_percentage'] >= 80:
                validation_result['validation_status'] = 'excellent'
            elif validation_result['field_match_percentage'] >= 60:
                validation_result['validation_status'] = 'good'
            elif validation_result['field_match_percentage'] >= 40:
                validation_result['validation_status'] = 'partial'
            else:
                validation_result['validation_status'] = 'poor'
        else:
            # Check if it looks like a CTRAMP file based on common fields
            ctramp_indicators = {'hh_id', 'person_id', 'tour_id', 'trip_mode', 'tour_mode', 'mgra'}
            if any(indicator in actual_columns for indicator in ctramp_indicators):
                validation_result['appears_to_be_ctramp'] = True
                validation_result['validation_status'] = 'unrecognized_ctramp'
            else:
                validation_result['validation_status'] = 'non_ctramp'
                
        return validation_result
    
    def validate_with_enhanced_schemas(self, file_info: Dict) -> Dict:
        """
        Enhanced validation using the detailed analysis-ready schemas
        
        Args:
            file_info: Dictionary containing file schema information
            
        Returns:
            Dictionary containing enhanced validation results
        """
        filename = file_info['filename']
        
        # Find matching enhanced schema
        enhanced_schema = None
        schema_key = None
        for pattern, schema in ENHANCED_CTRAMP_SCHEMAS.items():
            if pattern.replace('_[iteration]', '').replace('[iteration]', '') in filename.lower():
                enhanced_schema = schema
                schema_key = pattern
                break
        
        validation_result = {
            'filename': filename,
            'identified_type': schema_key,
            'record_level': enhanced_schema.get('record_level', 'unknown') if enhanced_schema else 'unknown',
            'expected_size': enhanced_schema.get('typical_size', 'unknown') if enhanced_schema else 'unknown',
            'primary_keys': enhanced_schema.get('primary_key', []) if enhanced_schema else [],
            'analysis_ready': enhanced_schema is not None,
            'common_analyses': enhanced_schema.get('analysis_notes', {}).get('common_summaries', []) if enhanced_schema else [],
            'key_analysis_fields': enhanced_schema.get('analysis_notes', {}).get('key_fields_for_analysis', []) if enhanced_schema else [],
            'field_coverage': 0,
            'missing_critical_fields': [],
            'validation_notes': []
        }
        
        if file_info.get('error'):
            validation_result['validation_notes'].append(f"ERROR: {file_info['error']}")
            return validation_result
        
        actual_columns = set(file_info.get('columns', []))
        
        if enhanced_schema:
            expected_fields = set(enhanced_schema['expected_fields'])
            critical_fields = set(enhanced_schema.get('primary_key', []))
            analysis_fields = set(enhanced_schema.get('analysis_notes', {}).get('key_fields_for_analysis', []))
            
            # Calculate field coverage
            matching_expected = len(expected_fields & actual_columns)
            if len(expected_fields) > 0:
                validation_result['field_coverage'] = (matching_expected / len(expected_fields)) * 100
            
            # Check for missing critical fields
            validation_result['missing_critical_fields'] = list(critical_fields - actual_columns)
            missing_analysis_fields = list(analysis_fields - actual_columns)
            
            # Validation notes
            if validation_result['field_coverage'] >= 90:
                validation_result['validation_notes'].append("✅ Excellent field coverage")
            elif validation_result['field_coverage'] >= 70:
                validation_result['validation_notes'].append("👍 Good field coverage")
            else:
                validation_result['validation_notes'].append("⚠️ Low field coverage - check schema")
                
            if validation_result['missing_critical_fields']:
                validation_result['validation_notes'].append(f"❌ Missing primary keys: {validation_result['missing_critical_fields']}")
                
            if missing_analysis_fields:
                validation_result['validation_notes'].append(f"📊 Missing key analysis fields: {missing_analysis_fields[:3]}")
                
            # Size validation
            if file_info.get('shape'):
                actual_rows = file_info['shape'][0]
                expected_size = enhanced_schema.get('typical_size', '')
                if 'K' in expected_size:
                    min_expected = int(expected_size.split('-')[0].replace('K', '')) * 1000
                    if actual_rows < min_expected * 0.5:  # Allow 50% tolerance
                        validation_result['validation_notes'].append(f"⚠️ Low row count: {actual_rows:,} vs expected {expected_size}")
        else:
            validation_result['validation_notes'].append("❓ File type not in enhanced documentation")
        
        return validation_result
    
    def validate_multiple_files(self, file_schemas: List[Dict]) -> List[Dict]:
        """
        Validate multiple files and return results
        
        Args:
            file_schemas: List of file schema dictionaries
            
        Returns:
            List of validation result dictionaries
        """
        validation_results = []
        
        for file_info in file_schemas:
            validation = self.validate_with_enhanced_schemas(file_info)
            validation_results.append(validation)
        
        self.validation_results = validation_results
        return validation_results
    
    def analyze_data_quality_with_ctramp_context(self, schema_results: Dict, validation_results: List[Dict]) -> List[Dict]:
        """
        Perform data quality analysis using CTRAMP domain knowledge
        
        Args:
            schema_results: Results from schema analysis
            validation_results: Results from validation
            
        Returns:
            List of issues found
        """
        issues_found = []
        
        for file_info, validation in zip(schema_results['file_schemas'], validation_results):
            if file_info.get('error'):
                continue
                
            filename = file_info['filename'] 
            columns = file_info.get('columns', [])
            file_type = validation['identified_type']
            
            # Check for common CTRAMP data quality issues
            file_issues = []
            
            # 1. Check for required ID fields
            if validation.get('analysis_ready'):
                if 'hh_id' not in columns and file_type not in ['accessibilities.csv']:
                    file_issues.append("Missing household ID (hh_id)")
                
                if file_type in ['personData', 'indivTourData', 'indivTripData', 'indivTripDataResim']:
                    if 'person_id' not in columns:
                        file_issues.append("Missing person ID (person_id)")
                        
                if file_type in ['indivTourData', 'jointTourData']:
                    if 'tour_id' not in columns:
                        file_issues.append("Missing tour ID (tour_id)")
                        
                if file_type in ['indivTripData', 'jointTripData', 'indivTripDataResim']:
                    if 'stop_id' not in columns:
                        file_issues.append("Missing stop/trip ID (stop_id)")
            
            # 2. Check for mode and time period fields
            mode_fields = [col for col in columns if 'mode' in col.lower()]
            period_fields = [col for col in columns if 'period' in col.lower()]
            
            if validation.get('analysis_ready') and file_type in ['indivTourData', 'indivTripData', 'jointTourData', 'jointTripData']:
                if not mode_fields:
                    file_issues.append("No mode fields found")
                if not period_fields:
                    file_issues.append("No time period fields found")
            
            # 3. Check for utility/probability field consistency
            util_fields = [col for col in columns if col.startswith('util_')]
            prob_fields = [col for col in columns if col.startswith('prob_')]
            
            if util_fields and not prob_fields:
                file_issues.append("Has utility fields but missing probability fields")
            elif prob_fields and not util_fields:
                file_issues.append("Has probability fields but missing utility fields")
            elif util_fields and prob_fields:
                if len(util_fields) != len(prob_fields):
                    file_issues.append(f"Utility/probability field count mismatch ({len(util_fields)} vs {len(prob_fields)})")
            
            # 4. Check for geographic fields (MAZ/TAZ)
            geo_fields = [col for col in columns if 'mgra' in col.lower() or 'taz' in col.lower() or 'tap' in col.lower()]
            if validation.get('analysis_ready') and file_type not in ['householdData', 'personData']:
                if not geo_fields:
                    file_issues.append("No geographic fields (MGRA/TAZ/TAP) found")
            
            # 5. Sample size estimation
            if file_info.get('shape'):
                rows = file_info['shape'][0]
                if validation.get('analysis_ready'):
                    if file_type in ['householdData'] and rows < 100000:
                        file_issues.append(f"Low household count ({rows:,}) - expected 100K+ for Bay Area")
                    elif file_type in ['personData'] and rows < 200000:
                        file_issues.append(f"Low person count ({rows:,}) - expected 200K+ for Bay Area")
                    elif file_type in ['indivTripData'] and rows < 1000000:
                        file_issues.append(f"Low trip count ({rows:,}) - expected 1M+ for Bay Area")
            
            if file_issues:
                issues_found.append({
                    'filename': filename,
                    'file_type': file_type,
                    'issues': file_issues,
                    'issue_count': len(file_issues)
                })
        
        return issues_found
    
    def create_validation_dataframe(self, validation_results: List[Dict] = None) -> pd.DataFrame:
        """
        Create a detailed validation DataFrame
        
        Args:
            validation_results: List of validation results (uses self.validation_results if None)
            
        Returns:
            DataFrame with validation information
        """
        if validation_results is None:
            validation_results = self.validation_results
        
        validation_rows = []
        
        for validation in validation_results:
            validation_rows.append({
                'filename': validation['filename'],
                'identified_ctramp_type': validation['identified_type'],
                'record_level': validation.get('record_level', 'unknown'),
                'expected_size': validation.get('expected_size', 'unknown'),
                'analysis_ready': validation.get('analysis_ready', False),
                'field_coverage': validation.get('field_coverage', 0),
                'missing_critical_fields_count': len(validation.get('missing_critical_fields', [])),
                'validation_notes': '; '.join(validation.get('validation_notes', []))
            })
        
        return pd.DataFrame(validation_rows)