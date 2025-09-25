"""
CTRAMP Schema Analysis Suite - Modular Python tools for analyzing CTRAMP model outputs

This package provides a set of modular tools for analyzing Bay Area travel model (CTRAMP) outputs:

- Schema analysis and documentation
- Validation against expected file formats
- Pre-built analysis templates for common summaries
- Command line interface for batch processing

Example Usage:
    
    # Basic schema analysis
    from tm2py_utils.summary.ctramp_schema_analyzer import CTRAMPSchemaAnalyzer
    
    analyzer = CTRAMPSchemaAnalyzer("/path/to/ctramp/outputs")
    results = analyzer.analyze_directory_schema()
    analyzer.print_schema_summary()
    
    # Validation against documentation
    from tm2py_utils.summary.ctramp_validator import CTRAMPValidator
    
    validator = CTRAMPValidator()
    validation_results = validator.validate_multiple_files(results['file_schemas'])
    
    # Pre-built analysis templates
    from tm2py_utils.summary.ctramp_analysis_templates import CTRAMPAnalysisTemplates
    
    # Load your data
    import pandas as pd
    trips_df = pd.read_csv("indivTripData_1.csv")
    
    # Calculate mode share
    mode_share = CTRAMPAnalysisTemplates.mode_share_analysis(
        trips_df, 
        mode_field='trip_mode',
        groupby_field='tour_purpose'
    )
    
    # Calculate VMT
    vmt = CTRAMPAnalysisTemplates.vmt_calculation(
        trips_df,
        groupby_field='orig_purpose'  
    )
    
    # Command line usage
    python -m tm2py_utils.summary.ctramp_cli /path/to/outputs --show-recommendations
"""

from .ctramp_schema_analyzer import CTRAMPSchemaAnalyzer
from .ctramp_validator import CTRAMPValidator  
from .ctramp_analysis_templates import CTRAMPAnalysisTemplates, SUMMARY_TEMPLATES
from .ctramp_documentation import (
    ENHANCED_CTRAMP_SCHEMAS, 
    MODE_CODES, 
    TIME_PERIODS,
    get_analysis_guidance,
    get_common_summaries,
    get_key_analysis_fields
)

__all__ = [
    'CTRAMPSchemaAnalyzer',
    'CTRAMPValidator', 
    'CTRAMPAnalysisTemplates',
    'SUMMARY_TEMPLATES',
    'ENHANCED_CTRAMP_SCHEMAS',
    'MODE_CODES',
    'TIME_PERIODS', 
    'get_analysis_guidance',
    'get_common_summaries',
    'get_key_analysis_fields'
]

__version__ = "0.1.0"