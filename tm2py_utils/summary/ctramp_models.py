"""
CTRAMP Data Models

Pydantic models defining the expected structure of CTRAMP output files
based on the tm2py documentation specifications.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, validator
import pandas as pd
from enum import IntEnum


class PersonType(IntEnum):
    """Person type categories from CTRAMP."""
    FULL_TIME_WORKER = 1
    PART_TIME_WORKER = 2  
    UNIVERSITY_STUDENT = 3
    NON_WORKING_ADULT = 4
    RETIRED = 5
    DRIVING_AGE_STUDENT = 6
    NON_DRIVING_STUDENT = 7
    PRESCHOOL_CHILD = 8


class TourPurpose(IntEnum):
    """Tour purpose codes from CTRAMP."""
    WORK = 1
    UNIVERSITY = 2
    SCHOOL = 3
    ESCORT = 4
    SHOP = 5
    MAINTENANCE = 6
    EAT_OUT = 7
    VISIT = 8
    DISCRETIONARY = 9
    WORK_BASED = 10


class CTRAMPHousehold(BaseModel):
    """Household data model based on CTRAMP specifications."""
    hh_id: int = Field(..., description="Unique household identifier")
    home_mgra: int = Field(..., description="Home MGRA (micro-zone)")
    income: int = Field(..., description="Income category (1-4 or 1-5)")
    vehicles: int = Field(..., description="Number of vehicles owned")
    workers: int = Field(..., description="Number of workers in household")
    hhsize: int = Field(..., description="Household size")
    HHT: int = Field(..., description="Household type")
    BLD: int = Field(..., description="Building type") 
    TYPE: int = Field(..., description="Unit type")
    
    # Optional fields that may be present
    sampleRate: Optional[float] = Field(None, description="Sample expansion factor")
    originalPUMA: Optional[int] = Field(None, description="Original PUMA code")
    
    @validator('income')
    def income_valid_range(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Income must be between 1 and 5')
        return v
    
    @validator('vehicles')
    def vehicles_non_negative(cls, v):
        if v < 0:
            raise ValueError('Vehicles cannot be negative')
        return v


class CTRAMPPerson(BaseModel):
    """Person data model based on CTRAMP specifications."""
    person_id: int = Field(..., description="Unique person identifier")
    hh_id: int = Field(..., description="Household identifier") 
    person_num: int = Field(..., description="Person number within household (1-based)")
    person_type: PersonType = Field(..., description="Person type category")
    age: int = Field(..., description="Age in years")
    gender: int = Field(..., description="Gender (1=male, 2=female)")
    
    # Work/school location
    work_mgra: Optional[int] = Field(None, description="Work location MGRA")
    school_mgra: Optional[int] = Field(None, description="School location MGRA")
    
    # Optional activity pattern and telecommute fields
    cdap_activity: Optional[str] = Field(None, description="CDAP activity pattern")
    telecommute_frequency: Optional[int] = Field(None, description="Telecommute frequency")
    
    # Choice model results
    fp_choice: Optional[int] = Field(None, description="Free parking choice: 0=No, 1=Yes")
    imf_choice: Optional[int] = Field(None, description="Individual mandatory tour frequency")
    inmf_choice: Optional[int] = Field(None, description="Individual non-mandatory tour frequency")
    
    # Transportation economics
    value_of_time: Optional[float] = Field(None, description="Value of time ($/hour)")
    transitSubsidy_choice: Optional[int] = Field(None, description="Transit subsidy: 0=No, 1=Yes")
    transitPass_choice: Optional[int] = Field(None, description="Transit pass: 0=No, 1=Yes")
    
    @validator('fp_choice')
    def fp_choice_valid(cls, v):
        if v is not None and v not in [0, 1]:
            raise ValueError('Free parking choice must be 0 or 1')
        return v
    
    @validator('age')
    def age_valid_range(cls, v):
        if v < 0 or v > 120:
            raise ValueError('Age must be between 0 and 120')
        return v
    
    @validator('person_num')
    def person_num_positive(cls, v):
        if v < 1:
            raise ValueError('Person number must be positive')
        return v


class CTRAMPTour(BaseModel):
    """Individual tour data model based on CTRAMP specifications."""
    tour_id: int = Field(..., description="Unique tour identifier")
    person_id: int = Field(..., description="Person making the tour")
    hh_id: int = Field(..., description="Household identifier")
    person_num: int = Field(..., description="Person number within household")
    person_type: PersonType = Field(..., description="Person type")
    
    tour_purpose: TourPurpose = Field(..., description="Purpose of tour")
    tour_mode: int = Field(..., description="Primary tour mode")
    dest_mgra: int = Field(..., description="Primary destination MGRA")
    
    # Time of day
    start_period: Optional[int] = Field(None, description="Tour start time period")
    end_period: Optional[int] = Field(None, description="Tour end time period")
    
    # Tour characteristics  
    tour_distance: Optional[float] = Field(None, description="Tour distance in miles")
    valueOfTime: Optional[float] = Field(None, description="Value of time for this tour")
    
    # Model results
    dcLogsum: Optional[float] = Field(None, description="Destination choice logsum")
    
    @validator('tour_mode')
    def tour_mode_positive(cls, v):
        if v <= 0:
            raise ValueError('Tour mode must be positive')
        return v


class CTRAMPTrip(BaseModel):
    """Individual trip data model based on CTRAMP specifications."""
    person_id: int = Field(..., description="Person making the trip")
    hh_id: int = Field(..., description="Household identifier")
    person_num: int = Field(..., description="Person number within household") 
    tour_id: int = Field(..., description="Tour containing this trip")
    
    # Trip sequence
    stop_id: int = Field(..., description="Stop number within tour half (0-based)")
    inbound: bool = Field(..., description="True if inbound trip, False if outbound")
    
    # Geography
    orig_mgra: int = Field(..., description="Origin MGRA")
    dest_mgra: int = Field(..., description="Destination MGRA")
    
    # Trip characteristics
    trip_mode: int = Field(..., description="Trip mode")
    trip_purpose: int = Field(..., description="Trip purpose code")
    trip_period: Optional[int] = Field(None, description="Trip time period")
    trip_distance: Optional[float] = Field(None, description="Trip distance in miles")
    
    @validator('stop_id')
    def stop_id_non_negative(cls, v):
        if v < 0:
            raise ValueError('Stop ID cannot be negative')
        return v


class CTRAMPWorkSchoolLocation(BaseModel):
    """Workplace and school location results."""
    person_id: int = Field(..., description="Person identifier")
    hh_id: int = Field(..., description="Household identifier") 
    person_num: int = Field(..., description="Person number within household")
    person_type: PersonType = Field(..., description="Person type")
    
    # Location results
    WorkLocation: Optional[int] = Field(None, description="Selected work location MGRA")
    WorkLocationDistance: Optional[float] = Field(None, description="Distance to work location")
    WorkLocationLogsum: Optional[float] = Field(None, description="Work location choice logsum")
    
    SchoolLocation: Optional[int] = Field(None, description="Selected school location MGRA")  
    SchoolLocationDistance: Optional[float] = Field(None, description="Distance to school location")
    SchoolLocationLogsum: Optional[float] = Field(None, description="School location choice logsum")


def validate_dataframe_against_model(df: pd.DataFrame, model_class: BaseModel) -> List[str]:
    """
    Validate a pandas DataFrame against a Pydantic model.
    Returns a list of validation errors.
    """
    errors = []
    
    # Check required fields are present
    required_fields = []
    for field_name, field_info in model_class.__fields__.items():
        if field_info.required:
            required_fields.append(field_name)
    
    missing_fields = set(required_fields) - set(df.columns)
    if missing_fields:
        errors.append(f"Missing required fields: {missing_fields}")
    
    # Sample validation on subset of rows
    if len(errors) == 0 and len(df) > 0:
        try:
            # Validate first few rows
            sample_size = min(100, len(df))
            sample_df = df.head(sample_size)
            
            for idx, row in sample_df.iterrows():
                try:
                    model_class(**row.to_dict())
                except Exception as e:
                    errors.append(f"Row {idx} validation error: {str(e)}")
                    break  # Don't spam with too many row errors
        except Exception as e:
            errors.append(f"General validation error: {str(e)}")
    
    return errors


def get_model_for_file_type(file_type: str) -> Optional[BaseModel]:
    """Return the appropriate Pydantic model for a given file type."""
    model_mapping = {
        'households': CTRAMPHousehold,
        'persons': CTRAMPPerson,
        'individual_tours': CTRAMPTour,
        'individual_trips': CTRAMPTrip,
        'workplace_school': CTRAMPWorkSchoolLocation
    }
    return model_mapping.get(file_type)