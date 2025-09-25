"""
CTRAMP Documentation and Validation - Reference schemas and validation functions
"""

from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class TransportMode(Enum):
    """Transport mode enumeration with CTRAMP codes"""
    DRIVEALONEFREE = 1
    DRIVEALONEPAY = 2
    SHARED2GP = 3
    SHARED2HOV = 4
    SHARED2PAY = 5
    SHARED3GP = 6
    SHARED3HOV = 7
    SHARED3PAY = 8
    WALK = 9
    BIKE = 10
    WALK_SET = 11
    PNR_SET = 12
    KNR_PERS = 13
    KNR_TNC = 14
    TAXI = 15
    TNC = 16
    SCHBUS = 17


class RecordLevel(Enum):
    """Record level enumeration for CTRAMP files"""
    ZONE = "zone"
    HOUSEHOLD = "household"
    PERSON = "person"
    TOUR = "tour"
    TRIP = "trip"
    JOINT_TOUR = "joint_tour"
    JOINT_TRIP = "joint_trip"


class FileType(Enum):
    """CTRAMP file type enumeration"""
    ACCESSIBILITY = "accessibility"
    AUTO_OWNERSHIP = "auto_ownership"
    HOUSEHOLD = "household"
    PERSON = "person"
    LOCATION_CHOICE = "location_choice"
    INDIVIDUAL_TOUR = "individual_tour"
    INDIVIDUAL_TRIP = "individual_trip"
    JOINT_TOUR = "joint_tour"
    JOINT_TRIP = "joint_trip"
    RESIMULATED_TRIP = "resimulated_trip"
    PARKING_DEMAND = "parking_demand"


class AnalysisNotes(BaseModel):
    """Analysis guidance for CTRAMP files"""
    purpose: str = Field(..., description="Purpose and use case of the file")
    common_summaries: List[str] = Field(default_factory=list, description="Common summary analyses")
    key_fields_for_analysis: List[str] = Field(default_factory=list, description="Most important fields for analysis")
    geographic_aggregation: Optional[str] = Field(None, description="Geographic aggregation guidance")
    model_validation: Optional[str] = Field(None, description="Model validation approaches")
    join_keys: Optional[str] = Field(None, description="Join strategies with other files")
    vmt_calculation: Optional[str] = Field(None, description="VMT calculation guidance")
    mode_choice_analysis: Optional[str] = Field(None, description="Mode choice model analysis")
    time_analysis: Optional[str] = Field(None, description="Time-of-day analysis guidance")
    geographic_analysis: Optional[str] = Field(None, description="Geographic analysis guidance")
    transit_analysis: Optional[str] = Field(None, description="Transit-specific analysis")
    cost_analysis: Optional[str] = Field(None, description="Cost analysis guidance")
    occupancy_analysis: Optional[str] = Field(None, description="Vehicle occupancy analysis")
    household_analysis: Optional[str] = Field(None, description="Household-level analysis")
    transit_validation: Optional[str] = Field(None, description="Transit validation approaches")
    path_analysis: Optional[str] = Field(None, description="Path choice analysis")
    comparison_file: Optional[str] = Field(None, description="Related files for comparison")
    occupancy_calculation: Optional[str] = Field(None, description="Occupancy calculation methods")
    vmt_adjustment: Optional[str] = Field(None, description="VMT adjustment notes")


class CTRAMPFileSchema(BaseModel):
    """Schema definition for CTRAMP output files"""
    description: str = Field(..., description="File description")
    primary_key: List[str] = Field(..., description="Primary key fields")
    expected_fields: List[str] = Field(..., description="Expected column names")
    file_type: FileType = Field(..., description="CTRAMP file type")
    record_level: RecordLevel = Field(..., description="Record level (zone, household, person, etc.)")
    typical_size: str = Field(..., description="Expected file size description")
    analysis_notes: AnalysisNotes = Field(..., description="Analysis guidance")
    
    @validator('expected_fields')
    def validate_primary_keys_in_expected(cls, v, values):
        """Ensure primary keys are included in expected fields"""
        primary_key = values.get('primary_key', [])
        for key in primary_key:
            if key not in v:
                v.append(key)
        return v


# Mode codes mapping (backward compatibility)
MODE_CODES = {mode.value: mode.name for mode in TransportMode}

# Time period mapping
TIME_PERIODS = {
    1: '03:00 AM to 05:00 AM', 2: '05:00 AM to 05:30 AM', 3: '05:30 AM to 06:00 AM',
    4: '06:00 AM to 06:30 AM', 5: '06:30 AM to 07:00 AM', 6: '07:00 AM to 07:30 AM',
    7: '07:30 AM to 08:00 AM', 8: '08:00 AM to 08:30 AM', 9: '08:30 AM to 09:00 AM',
    10: '09:00 AM to 09:30 AM', 11: '09:30 AM to 10:00 AM', 12: '10:00 AM to 10:30 AM',
    13: '10:30 AM to 11:00 AM', 14: '11:00 AM to 11:30 AM', 15: '11:30 AM to 12:00 PM',
    16: '12:00 PM to 12:30 PM', 17: '12:30 PM to 01:00 PM', 18: '01:00 PM to 01:30 PM',
    19: '01:30 PM to 02:00 PM', 20: '02:00 PM to 02:30 PM', 21: '02:30 PM to 03:00 PM',
    22: '03:00 PM to 03:30 PM', 23: '03:30 PM to 04:00 PM', 24: '04:00 PM to 04:30 PM',
    25: '04:30 PM to 05:00 PM', 26: '05:00 PM to 05:30 PM', 27: '05:30 PM to 06:00 PM',
    28: '06:00 PM to 06:30 PM', 29: '06:30 PM to 07:00 PM', 30: '07:00 PM to 07:30 PM',
    31: '07:30 PM to 08:00 PM', 32: '08:00 PM to 08:30 PM', 33: '08:30 PM to 09:00 PM',
    34: '09:00 PM to 09:30 PM', 35: '09:30 PM to 10:00 PM', 36: '10:00 PM to 10:30 PM',
    37: '10:30 PM to 11:00 PM', 38: '11:00 PM to 11:30 PM', 39: '11:30 PM to 12:00 AM',
    40: '12:00 AM to 03:00 AM'
}

# Enhanced CTRAMP file schemas with analysis guidance
ENHANCED_CTRAMP_SCHEMAS = {
    'accessibilities.csv': {
        'description': 'Zone-level accessibility measures by microzone (MGRA)',
        'primary_key': ['mgra'],
        'expected_fields': ['mgra'],
        'file_type': 'accessibility',
        'record_level': 'zone',
        'typical_size': '10K-50K rows (one per MGRA)',
        'analysis_notes': {
            'purpose': 'Accessibility to jobs, schools, other activities by mode and time period',
            'common_summaries': ['accessibility by county', 'accessibility by income', 'mode-specific accessibility'],
            'key_fields_for_analysis': ['mgra', 'auto_accessibility', 'transit_accessibility'],
            'geographic_aggregation': 'Can aggregate to TAZ, county, or equity zones using MGRA lookups'
        }
    },
    
    'aoResults_pre.csv': {
        'description': 'Household auto ownership before work/school location choice',
        'primary_key': ['hh_id'],
        'expected_fields': ['hh_id'],
        'file_type': 'auto_ownership',
        'record_level': 'household', 
        'typical_size': '500K-1M rows (one per household)',
        'analysis_notes': {
            'purpose': 'Pre-location choice vehicle ownership model results',
            'common_summaries': ['vehicles per household by income', 'ownership rates by area type'],
            'key_fields_for_analysis': ['hh_id', 'vehicles', 'income_category'],
            'comparison_file': 'aoResults.csv shows post-location choice results'
        }
    },
    
    'aoResults.csv': {
        'description': 'Household auto ownership after work/school location choice',
        'primary_key': ['hh_id'],
        'expected_fields': ['hh_id'],
        'file_type': 'auto_ownership',
        'record_level': 'household',
        'typical_size': '500K-1M rows (one per household)', 
        'analysis_notes': {
            'purpose': 'Final vehicle ownership after location choices',
            'common_summaries': ['change in ownership due to location', 'final ownership distribution'],
            'key_fields_for_analysis': ['hh_id', 'vehicles', 'change_from_pre'],
            'comparison_file': 'Compare with aoResults_pre.csv to see location impact'
        }
    },
    
    'householdData': {
        'description': 'Household characteristics and choice model results',
        'primary_key': ['hh_id'],
        'expected_fields': ['hh_id', 'transponder', 'cdap_pattern', 'jtf_choice'],
        'file_type': 'household',
        'record_level': 'household',
        'typical_size': '500K-1M rows (one per household)',
        'analysis_notes': {
            'purpose': 'Core household data with demographics and major choice model results',
            'common_summaries': ['household size distribution', 'income distribution', 'CDAP patterns', 'joint tour frequency'],
            'key_fields_for_analysis': ['hh_id', 'hhsize', 'income', 'workers', 'cdap_pattern', 'vehicles'],
            'geographic_aggregation': 'Use home_mgra to aggregate spatially',
            'model_validation': 'Compare CDAP patterns to survey data, check income distribution'
        }
    },
    
    'personData': {
        'description': 'Person characteristics and individual choice model results',
        'primary_key': ['hh_id', 'person_id'],
        'expected_fields': ['hh_id', 'person_id', 'person_num', 'value_of_time', 
                          'transitSubsidy_choice', 'transitSubsidy_percent', 'transitPass_choice',
                          'activity_pattern', 'imf_choice', 'inmf_choice', 'fp_choice', 
                          'reimb_pct', 'workDCLogsum', 'schoolDCLogsum'],
        'file_type': 'person',
        'record_level': 'person',
        'typical_size': '1M-2M rows (2-3 persons per household average)',
        'analysis_notes': {
            'purpose': 'Individual person attributes and activity/tour generation results',
            'common_summaries': ['person type distribution', 'activity patterns by demographics', 'value of time distribution'],
            'key_fields_for_analysis': ['person_type', 'age', 'gender', 'worker_status', 'activity_pattern', 'value_of_time'],
            'model_validation': 'Check activity pattern rates vs survey, validate value of time by income',
            'join_keys': 'Join to householdData on hh_id for household characteristics'
        }
    },
    
    'wsLocResults': {
        'description': 'Work and school location choice model results',
        'primary_key': ['hh_id', 'person_id'],
        'expected_fields': ['hh_id', 'person_id', 'EmploymentCategory', 'StudentCategory', 
                          'WorkSegment', 'SchoolSegment', 'WorkLocation', 'WorkLocationDistance',
                          'WorkLocationLogsum', 'SchoolLocation', 'SchoolLocationDistance', 'SchoolLocationLogsum'],
        'file_type': 'location_choice',
        'record_level': 'person',
        'typical_size': '500K-1M rows (workers and students only)',
        'analysis_notes': {
            'purpose': 'Workplace and school location choices with distances and logsums',
            'common_summaries': ['commute distance distribution', 'jobs-housing balance', 'school enrollment by district'],
            'key_fields_for_analysis': ['WorkLocation', 'WorkLocationDistance', 'SchoolLocation', 'employment_category'],
            'geographic_analysis': 'Map work/school flows, calculate commute patterns by county',
            'model_validation': 'Compare commute distances to survey data'
        }
    },
    
    'indivTourData': {
        'description': 'Individual tours with full mode choice model results',
        'primary_key': ['hh_id', 'person_id', 'tour_id'],
        'expected_fields': ['hh_id', 'person_id', 'person_num', 'person_type', 'tour_id', 
                          'tour_category', 'tour_purpose', 'orig_mgra', 'dest_mgra', 
                          'start_period', 'end_period', 'tour_mode', 'tour_distance', 
                          'tour_time', 'atWork_freq', 'num_ob_stops', 'num_ib_stops',
                          'out_btap', 'out_atap', 'in_btap', 'in_atap', 'out_set', 'in_set',
                          'sampleRate', 'dcLogsum'] + [f'util_{i}' for i in range(1,18)] + [f'prob_{i}' for i in range(1,18)],
        'file_type': 'individual_tour',
        'record_level': 'tour',
        'typical_size': '2M-5M rows (2-3 tours per person average)',
        'analysis_notes': {
            'purpose': 'Individual daily tours with mode choice utilities and probabilities',
            'common_summaries': ['mode share by purpose', 'tour generation rates', 'time-of-day patterns', 'tour length distribution'],
            'key_fields_for_analysis': ['tour_purpose', 'tour_mode', 'start_period', 'end_period', 'tour_distance', 'orig_mgra', 'dest_mgra'],
            'mode_choice_analysis': 'Use util_* and prob_* fields for mode choice model validation',
            'time_analysis': 'start_period and end_period for departure/arrival time analysis',
            'geographic_analysis': 'Origin-destination flows using orig_mgra and dest_mgra',
            'transit_analysis': 'Use *_btap and *_atap fields for transit boarding/alighting analysis'
        }
    },
    
    'indivTripData': {
        'description': 'Individual trips (tour components) with detailed attributes',
        'primary_key': ['hh_id', 'person_id', 'tour_id', 'stop_id'],
        'expected_fields': ['hh_id', 'person_id', 'person_num', 'tour_id', 'stop_id', 'inbound',
                          'tour_purpose', 'orig_purpose', 'dest_purpose', 'orig_mgra', 'dest_mgra',
                          'parking_mgra', 'stop_period', 'trip_mode', 'trip_board_tap', 
                          'trip_alight_tap', 'tour_mode', 'set', 'sampleRate', 'TRIP_TIME', 
                          'TRIP_DISTANCE', 'TRIP_COST'],
        'file_type': 'individual_trip',
        'record_level': 'trip',
        'typical_size': '5M-15M rows (multiple trips per tour)',
        'analysis_notes': {
            'purpose': 'Individual trip segments with time, distance, and cost',
            'common_summaries': ['trip mode share', 'trip length distribution', 'VMT by purpose', 'trip timing patterns'],
            'key_fields_for_analysis': ['trip_mode', 'orig_purpose', 'dest_purpose', 'TRIP_DISTANCE', 'TRIP_TIME', 'stop_period'],
            'vmt_calculation': 'Sum TRIP_DISTANCE by trip_mode for vehicle miles traveled',
            'transit_analysis': 'trip_board_tap and trip_alight_tap for detailed transit flows',
            'time_analysis': 'stop_period for hourly travel patterns',
            'cost_analysis': 'TRIP_COST for travel cost distribution by income/mode'
        }
    },
    
    'jointTourData': {
        'description': 'Joint household tours (multiple participants)',
        'primary_key': ['hh_id', 'tour_id'],
        'expected_fields': ['hh_id', 'tour_id', 'tour_category', 'tour_purpose', 'tour_composition',
                          'tour_participants', 'orig_mgra', 'dest_mgra', 'start_period', 'end_period',
                          'tour_mode', 'tour_distance', 'tour_time', 'num_ob_stops', 'num_ib_stops',
                          'out_btap', 'out_atap', 'in_btap', 'in_atap', 'out_set', 'in_set',
                          'sampleRate', 'dcLogsum'] + [f'util_{i}' for i in range(1,18)] + [f'prob_{i}' for i in range(1,18)],
        'file_type': 'joint_tour',
        'record_level': 'joint_tour',
        'typical_size': '500K-2M rows (fewer than individual tours)',
        'analysis_notes': {
            'purpose': 'Household joint travel with multiple participants per tour',
            'common_summaries': ['joint travel rates', 'joint tour purposes', 'household coordination patterns'],
            'key_fields_for_analysis': ['tour_purpose', 'tour_composition', 'tour_participants', 'tour_mode'],
            'occupancy_analysis': 'Use tour_participants to understand vehicle occupancy',
            'household_analysis': 'Compare joint vs individual travel patterns by household type'
        }
    },
    
    'jointTripData': {
        'description': 'Joint household trips (components of joint tours)',  
        'primary_key': ['hh_id', 'tour_id', 'stop_id'],
        'expected_fields': ['hh_id', 'tour_id', 'stop_id', 'inbound', 'tour_purpose', 'orig_purpose',
                          'dest_purpose', 'orig_mgra', 'dest_mgra', 'parking_mgra', 'stop_period',
                          'trip_mode', 'num_participants', 'trip_board_tap', 'trip_alight_tap',
                          'tour_mode', 'set', 'sampleRate', 'TRIP_TIME', 'TRIP_DISTANCE', 'TRIP_COST'],
        'file_type': 'joint_trip',
        'record_level': 'joint_trip',
        'typical_size': '1M-5M rows (trips within joint tours)',
        'analysis_notes': {
            'purpose': 'Joint trip segments with participant counts',
            'common_summaries': ['joint trip VMT', 'vehicle occupancy rates', 'joint trip destinations'],
            'key_fields_for_analysis': ['trip_mode', 'num_participants', 'TRIP_DISTANCE', 'orig_purpose', 'dest_purpose'],
            'occupancy_calculation': 'Use num_participants for accurate vehicle occupancy analysis',
            'vmt_adjustment': 'TRIP_DISTANCE represents vehicle miles, not person miles'
        }
    },
    
    'indivTripDataResim': {
        'description': 'Resimulated transit trips with additional transit assignment data',
        'primary_key': ['hh_id', 'person_id', 'tour_id', 'stop_id'],
        'expected_fields': ['hh_id', 'person_id', 'person_num', 'tour_id', 'stop_id', 'inbound',
                          'tour_purpose', 'orig_purpose', 'dest_purpose', 'orig_mgra', 'dest_mgra',
                          'parking_mgra', 'stop_period', 'trip_mode', 'trip_board_tap', 
                          'trip_alight_tap', 'tour_mode', 'set', 'sampleRate', 'resimulatedTrip',
                          'TRIP_TIME', 'TRIP_DISTANCE', 'TRIP_COST'],
        'file_type': 'resimulated_trip',
        'record_level': 'trip',
        'typical_size': 'Subset of indivTripData (transit trips only)',
        'analysis_notes': {
            'purpose': 'Transit trips with updated paths from transit assignment feedback',
            'common_summaries': ['transit mode share', 'transit boarding patterns', 'route choice validation'],
            'key_fields_for_analysis': ['resimulatedTrip', 'trip_board_tap', 'trip_alight_tap', 'set'],
            'transit_validation': 'Compare with original indivTripData to see assignment impacts',
            'path_analysis': 'Use set field to analyze transit route choices'
        }
    }
}


def get_analysis_guidance(file_type: str) -> Dict:
    """
    Get specific analysis guidance for a CTRAMP file type
    
    Args:
        file_type: Name or pattern of the CTRAMP file
        
    Returns:
        Dictionary with analysis guidance
    """
    for pattern, schema in ENHANCED_CTRAMP_SCHEMAS.items():
        if pattern.replace('_[iteration]', '').replace('[iteration]', '') in file_type.lower():
            return schema.get('analysis_notes', {})
    return {}


def get_common_summaries(filename: str) -> List[str]:
    """
    Get list of common summary analyses for a file type
    
    Args:
        filename: Name of the file
        
    Returns:
        List of common summary types
    """
    guidance = get_analysis_guidance(filename)
    return guidance.get('common_summaries', [])


def get_key_analysis_fields(filename: str) -> List[str]:
    """
    Get the most important fields for analysis in a file
    
    Args:
        filename: Name of the file
        
    Returns:
        List of key field names
    """
    guidance = get_analysis_guidance(filename)
    return guidance.get('key_fields_for_analysis', [])


def estimate_expected_size(filename: str) -> str:
    """
    Get expected file size/record count for validation
    
    Args:
        filename: Name of the file
        
    Returns:
        Expected size description
    """
    for pattern, schema in ENHANCED_CTRAMP_SCHEMAS.items():
        if pattern.replace('_[iteration]', '').replace('[iteration]', '') in filename.lower():
            return schema.get('typical_size', 'Size varies')
    return 'Unknown size'


def identify_ctramp_file_type(filename: str) -> tuple:
    """
    Identify the CTRAMP file type based on filename patterns
    
    Args:
        filename: Name of the file to identify
        
    Returns:
        Tuple of (file_type_key, expected_schema, description)
    """
    filename_lower = filename.lower()
    
    # Check each known pattern
    for pattern, schema in ENHANCED_CTRAMP_SCHEMAS.items():
        if pattern.replace('_[iteration]', '').replace('[iteration]', '') in filename_lower:
            return pattern, schema, schema['description']
    
    # Check for specific patterns with iterations
    for base_name in ['householdData', 'personData', 'wsLocResults', 'indivTourData', 
                      'indivTripData', 'jointTourData', 'jointTripData', 'indivTripDataResim']:
        if base_name.lower() in filename_lower:
            return base_name, ENHANCED_CTRAMP_SCHEMAS[base_name], ENHANCED_CTRAMP_SCHEMAS[base_name]['description']
    
    return None, None, "Unknown CTRAMP file type"