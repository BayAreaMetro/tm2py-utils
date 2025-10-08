import os
import pandas as pd
import numpy as np
import re
from pathlib import Path
import pickle
from typing import Dict, List, Tuple, Optional
import openmatrix as omx
import itertools
from pydantic import BaseModel, Field

## TODO: Add logging
## TODO: Potentially move this to .toml configuration? Or reference .toml file

# TM2 Test Directory
#TARGET_DIR = "E:/TM2/2015_TM2_20250619"
TARGET_DIR = "E:/Box/Modeling and Surveys/Development/Travel Model Two Conversion/Model Outputs/2015-tm22-dev-sprint-04"
#TARGET_DIR = 'V:/Projects/2050_TM161_FBP_Plan_16'
ITER = 3
#SAMPLESHARE = 0.1

class Config:
    """Configuration class for model parameters and paths."""
    ## TODO: These will most likely change for TM2

    def __init__(self):
        # Environment variables
        self.target_dir = TARGET_DIR
        self.iter = ITER
        #self.target_dir = os.getenv("TARGET_DIR", "")
        #self.iter = os.getenv("ITER", "")
        self.sampleshare = float(os.getenv("SAMPLESHARE", "1.0"))
        self.just_mes = os.getenv("JUST_MES", "0") == "1"
        
        # Validate required parameters
        if not self.target_dir or not self.iter or not self.sampleshare:
            raise ValueError("TARGET_DIR, ITER, and SAMPLESHARE environment variables must be set")
        
        # Directory paths
        self.target_dir = self.target_dir.replace("\\", "/")
        if self.just_mes:
            self.main_dir = Path(self.target_dir) / "main" / "just_mes"
            self.results_dir = Path(self.target_dir) / "core_summaries" / "just_mes"
            self.updated_dir = Path(self.target_dir) / "updated_output" / "just_mes"
        else:
            self.main_dir = Path(self.target_dir) / "ctramp_output"
            self.results_dir = Path(self.target_dir) / "core_summaries"
            self.updated_dir = Path(self.target_dir) / "updated_output"
        
        # Create directories if they don't exist
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.updated_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse means-based cost factors
        #self._parse_cost_factors()
        
        print(f"TARGET_DIR  = {self.target_dir}")
        print(f"ITER        = {self.iter}")
        print(f"SAMPLESHARE = {self.sampleshare}")
        print(f"JUST_MES    = {self.just_mes}")
    
    ## TODO: Where is this and does this still need to be incorporated
    def _parse_cost_factors(self):
        """Parse means-based cost factors from parameter files."""
        # Read highway parameters
        hwy_param_file = Path(self.target_dir) / "ctramp" / "scripts" / "block" / "hwyParam.block"
        trn_param_file = Path(self.target_dir) / "ctramp" / "scripts" / "block" / "trnParam.block"
        
        with open(hwy_param_file, 'r') as f:
            hwy_lines = f.readlines()
        
        with open(trn_param_file, 'r') as f:
            trn_lines = f.readlines()
        
        # Extract MBT Q1 Factor
        mbt_q1_pattern = r'^Means_Based_Tolling_Q1Factor\s*=\s*([0-9.]+)'
        self.mbt_q1_factor = self._extract_factor(hwy_lines, mbt_q1_pattern, "MBT_Q1_factor")
        
        # Extract MBT Q2 Factor
        mbt_q2_pattern = r'^Means_Based_Tolling_Q2Factor\s*=\s*([0-9.]+)'
        self.mbt_q2_factor = self._extract_factor(hwy_lines, mbt_q2_pattern, "MBT_Q2_factor")
        
        # Extract MBF Poverty Threshold
        mbf_threshold_pattern = r'^Means_Based_Fare_PctOfPoverty_Threshold\s*=\s*([0-9]+)'
        self.mbf_pct_poverty_threshold = self._extract_factor(trn_lines, mbf_threshold_pattern, "MBF_PctOfPoverty_Threshold")
        
        # Extract MBF Factor
        mbf_factor_pattern = r'^Means_Based_Fare_Factor\s*=\s*([0-9.]+)'
        self.mbf_factor = self._extract_factor(trn_lines, mbf_factor_pattern, "MBF_factor")
    
    def _extract_factor(self, lines: List[str], pattern: str, name: str) -> float:
        """Extract a factor from parameter lines using regex."""
        for line in lines:
            match = re.match(pattern, line)
            if match:
                factor = float(match.group(1))
                print(f"{name}: {factor}")
                return factor
        raise ValueError(f"Could not find {name} in parameter file")

## Move this to dictionary? 
## TODO: Update to correct dictionary values
class LookupTables:
    """Class containing lookup tables for data recoding."""
    
    def __init__(self):
        # Time periods
        self.timeperiod = pd.DataFrame({
            'timeCodeNum': [1, 2, 3, 4, 5],
            'timeperiod_label': ['Early AM', 'AM Peak', 'Midday', 'PM Peak', 'Evening'],
            'timeperiod_abbrev': ['EA', 'AM', 'MD', 'PM', 'EV']
        })
        
        # Counties
        self.county = pd.DataFrame({
            'COUNTY': [1, 2, 3, 4, 5, 6, 7, 8, 9],
            'county_name': ['San Francisco', 'San Mateo', 'Santa Clara', 'Alameda',
                           'Contra Costa', 'Solano', 'Napa', 'Sonoma', 'Marin']
        })
        
        # Walk subzones
        self.walk_subzone = pd.DataFrame({
            'walk_subzone': [0, 1, 2],
            'walk_subzone_label': [
                'Cannot walk to transit (more than two-thirds of a mile away)',
                'Short-walk to transit (less than one-third of a mile)',
                'Long-walk to transit (between one-third and two-thirds of a mile)'
            ]
        })
        
        # Person types
        self.ptype = pd.DataFrame({
            'ptype': [1, 2, 3, 4, 5, 6, 7, 8],
            'ptype_label': [
                'Full-time worker', 'Part-time worker', 'College student', 'Non-working adult',
                'Retired', 'Driving-age student', 'Non-driving-age student', 'Child too young for school'
            ]
        })
        
        # Income quartiles
        self.incq = pd.DataFrame({
            'incQ': [1, 2, 3, 4],
            'incQ_label': ['Less than $30k', '$30k to $60k', '$60k to $100k', 'More than $100k']
        })
        
        # Auto sufficiency
        self.autosuff = pd.DataFrame({
            'autoSuff': [0, 1, 2],
            'autoSuff_label': ['Zero automobiles', 'Automobiles < workers', 'Automobiles >= workers']
        })

        # Trip and Tour Modes
        self.tripMode = pd.DataFrame(
            {'code': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
             'mode': ['DRIVEALONEFREE' , 'DRIVEALONEPAY', 'SHARED2GP' , 'SHARED2HOV' , 'SHARED2PAY' , 'SHARED3GP' , 
                      'SHARED3HOV' , 'SHARED3PAY' , 'WALK' , 'BIKE' , 'WALK_SET' , 'PNR_SET' , 'KNR_PERS' , 
                      'KNR_TNC' , 'TAXI' , 'TNC', 'SCHBUS'],
             'simple_mode': ['DA', 'DA', 'HOV2', 'HOV2', 'HOV2', 'HOV3', 'HOV3', 'HOV3', 'WALK', 'BIKE', 'WALKTOTRANS',
                             'DRIVETOTRANS', 'DRIVETOTRANS', 'DRIVETOTRANS', 'TNC', 'TNC', 'SCHBUS']
             }
        )

        #Transit Modes
        self.transitMode = pd.DataFrame({
            'mode': ['LOC', 'EXP', 'LTR', 'FRY', 'HVY', 'COM'],
            'mode_label': ['Local Bus', 'Express Bus', 'Light Rail', 'Ferry', 'Heavy Rail', 'Commuter Rail']
        })


class DataReader:
    """Class for reading and processing input data files.
    
    This includes:
    land use 
    persons
    households
    trips
    tours
    work-school location
    """
    
    def __init__(self, config: Config, lookups: LookupTables):
        self.config = config
        self.lookups = lookups
    
    def read_land_use(self) -> pd.DataFrame:
        """Read and process land use data."""

        # TM1
        # taz_file = Path(self.config.target_dir) / "landuse" / "tazData.csv"
        # taz_data = pd.read_csv(taz_file)
        # taz_data.columns = taz_data.columns.str.upper()
        # taz_data = taz_data[['ZONE', 'SD', 'COUNTY', 'PRKCST', 'OPRKCST']]
        # taz_data = taz_data.merge(self.lookups.county, on='COUNTY', how='left')
        # taz_data.rename(columns={'ZONE': 'taz'}, inplace=True)

        ## TM2
        maz_file = Path(self.config.target_dir) / "inputs" / "landuse" / "maz_data_withDensity.csv"
        maz_data = pd.read_csv(maz_file, usecols = ['MAZ', 'TAZ','MAZ_ORIGINAL', 'TAZ_ORIGINAL', 'CountyID', 'DistID', 'hparkcost'])

        ## TODO: What parking data do we want to include
        #maz_data = maz_data[['MAZ_ORIGINAL', 'TAZ_ORIGINAL', 'CountyID', 'DistID', 'hparkcost']]
        maz_data = maz_data.rename(columns = {'MAZ_ORIGINAL':'ORIG_MAZ', 'TAZ_ORIGINAL':'ORIG_TAZ'})

        return maz_data
    
    def read_persons(self, households: pd.DataFrame) -> pd.DataFrame:
        """Read and process person data."""
        
        ## If processed file exist, read that instead:
        if (self.config.updated_dir / 'persons.pickle').exists():
            print("Reading cached processed persons file")
            persons = pd.read_pickle(self.config.updated_dir/ 'persons.pickle')
            return persons
        # Read input files
        popsyn_file = Path(self.config.target_dir) / "inputs" / "popsyn" / "persons.csv"
        ct_file = self.config.main_dir / f"personData_{self.config.iter}.csv"
        
        input_pop_persons = pd.read_csv(popsyn_file)
        input_ct_persons = pd.read_csv(ct_file)
        
        # Rename columns
        input_pop_persons.rename(columns={'HHID': 'hh_id', 'PERID': 'person_id'}, inplace=True)
        
        # Join datasets
        persons = input_pop_persons.merge(input_ct_persons, on=['hh_id', 'person_id'], how='inner')
        
        # Add income quartile from households
        persons = persons.merge(households[['hh_id', 'incQ', 'incQ_label']], on='hh_id', how='left')
        
        # Add person type labels
        # TODO: Update for TM2
        ## persons = persons.merge(self.lookups.ptype, on='ptype', how='left')
        
        print(f"Read persons files; have {len(persons):,} rows")

        # Add kids no driver indicator

        ## TODO: Add kids no driver - need to figure out data dictionary for types
        # persons['kidsNoDr'] = ((persons['ptype'] == 7) | (persons['ptype'] == 8)).astype(int)
        
        print(persons.columns)
        print(persons.head())
        return persons

    ## TODO: Update for the MAZ level
    def read_households(self, land_use: pd.DataFrame) -> pd.DataFrame:
        """Read and process household data."""
        # Read input files
        # ##TM1
        # ## TODO: Make this not hard carded
        # popsyn_file = Path(self.config.target_dir) / "popsyn" / "hhFile.FBP.2050.PBA50Plus_Final_Blueprint_v65.csv"
        # ct_file = self.config.main_dir / f"householdData_{self.config.iter}.csv"
        
        # input_pop_hh = pd.read_csv(popsyn_file)
        # input_ct_hh = pd.read_csv(ct_file)
        
        # # Drop random number fields from CT file
        # drop_cols = [col for col in input_ct_hh.columns if col.endswith('_rn')] + ['pct_of_poverty']
        # input_ct_hh = input_ct_hh.drop(columns=drop_cols, errors='ignore')
        
        # # Rename HHID column
        # input_pop_hh.rename(columns={'HHID': 'hh_id'}, inplace=True)
        
        # # Join datasets
        # households = input_pop_hh.merge(input_ct_hh, on='hh_id', how='inner')
        # households = households.merge(taz_data, on='taz', how='inner')
        
        # print(f"Read household files; have {len(households):,} rows")
        # # Add derived variables
        # households = self._add_household_variables(households)
        # print(households.columns)

        ## TM2
        ## If processed file exist, read that instead:
        if (self.config.updated_dir / 'households.pickle').exists():
            print("Reading cached processed household file")
            persons = pd.read_pickle(self.config.updated_dir/ 'households.pickle')
            return persons
        popsyn_file = Path(self.config.target_dir) / "inputs" / "popsyn" / "households.csv"
        ct_file = self.config.main_dir / f"householdData_{self.config.iter}.csv"

        input_pop_hh = pd.read_csv(popsyn_file)
        print(input_pop_hh.columns)

        output_ct_hh = pd.read_csv(ct_file)
        print(output_ct_hh.columns)

        # Join input and output datasets
        households = input_pop_hh.merge(output_ct_hh, left_on = 'HHID', right_on = 'hh_id', how = 'inner')

        # Add land use data
        households = households.merge(land_use, on= ['ORIG_MAZ', 'ORIG_TAZ'], how = 'inner')
        print(households.columns)

        # Add household variables
        households = self._add_household_variables(households)
       
        return households
    
    def _add_household_variables(self, households: pd.DataFrame) -> pd.DataFrame:
        """
        Add derived variables to households data.
        This includes income quartiles, auto sufficiency, walk subzone
        
        """
        # Income quartiles
        households['incQ'] = pd.cut(households['income'], 
                                   bins=[households['income'].min(), 30000, 60000, 100000, float('inf')],
                                   labels=[1, 2, 3, 4], include_lowest=True).astype(int)
        households = households.merge(self.lookups.incq, on='incQ', how='left')
        
        # Workers (capped at 4)
        # TODO: Do we need to do this?
        #Households['workers'] = np.minimum(households['workers'], 4)
        
        # Auto sufficiency
        households['autoSuff'] = np.where(households['autos'] == 0, 0,
                                 np.where(households['autos'] < households['NWRKRS_ESR'], 1, 2))
        households = households.merge(self.lookups.autosuff, on='autoSuff', how='left')
        
        # Walk subzone label
        # TODO: Find TM2 equivalent - doesn't look like we have this
        #households = households.merge(self.lookups.walk_subzone, on='walk_subzone', how='left')
        
        print(households.head())
        
        return households

    
    def add_kids_no_driver(self,persons, households):
        """
        Add kids No Driver as a variable to the household data.
        
        """
        #  No Driver as a binary (1 for kid, 0 for no kid)
        kidsNoDr_hhlds = persons[['hh_id', 'kidsNoDr']].groupby('hh_id', as_index= False ).agg({'kidsNoDr': 'max'})
        households = households.merge(kidsNoDr_hhlds, on = 'hh_id')

        return households          
    
    ## TODO: Update for TM2
    def combine_tours(self, households: pd.DataFrame, landuse: pd.DataFrame) -> pd.DataFrame:
        """Combine joint and individual tours into a single DataFrame."""

        ## If processed file exist, read that instead:
        if (self.config.updated_dir / 'tours.pickle').exists():
            print("Reading cached processed tours file")
            tours = pd.read_pickle(self.config.updated_dir/ 'tours.pickle')
            return tours

        jointTours = self._read_tours('Joint')
        indivTours = self._read_tours('Indiv')
        jointTours = jointTours.drop(columns = ['tour_composition'])
        indivTours = indivTours.drop(columns = ['person_type', 'atWork_freq'])
        tours = pd.concat([jointTours, indivTours], ignore_index=True)
        print(tours.columns)
        # Add Residence Landuse Info
        tours = tours.merge(households[['hh_id', 'ORIG_MAZ', 'ORIG_TAZ', 'CountyID', 'DistID', 'incQ', 'incQ_label']], on='hh_id', how='left')
        print(tours.columns)

        ## TODO: Add CountyID for Destination MAZ
        tours = tours.merge(landuse[['MAZ', 'TAZ', 'ORIG_MAZ', 'ORIG_TAZ','CountyID', 'DistID']], left_on='dest_mgra', right_on='MAZ', how='left', suffixes= (None, "_dest"))


        print(f"Combined tours; have {len(tours):,} rows")
        print(tours.columns)
        tours['tour_mode_label'] = tours['tour_mode'].map(self.lookups.tripMode.set_index('code')['mode'])
        print(tours.head())
        #tours = tours._add_tours_attrs()
        return tours

    def _read_tours(self, IndivJoint: str) -> pd.DataFrame:
        """Read and process tour data.
        Arguments:
        - households: DataFrame of households to join with tours
        - persons: DataFrame of persons to join with tours
        - IndivJoint: 'Indiv' or 'Joint' to specify tour type
                                                                           """
        # Read input file
        tour_file = self.config.main_dir / f"{IndivJoint}TourData_{self.config.iter}.csv"
        tour = pd.read_csv(tour_file)

        # Drop probability and util columns
        tour.drop(list(tour.filter(regex='util|prob')), axis = 1, inplace = True)

        # Add income and percent of poverty from households
        ## TODO: Add in percent of poverty calculation for households
        ## Do this after combining tours 
        #tour = tour.merge(households[['hh_id', 'incQ', 'incQ_label']], on='hh_id', how='left')

        # TODO: Merge on MAZ for this - this is at a MAZ level (mgra_dest instead of dest_taz)
        # TODO: Add parking back in later
        # Add in Land Use Info for the Tour Destination
        # TODO: Unclear about the landuse input file since there's two - for now, merge on household which also has these fields
        # Since dest_mgra is based on sequential MAZ numbering,
        #tour = tour.merge(households[['MAZ', 'TAZ', 'ORIG_MAZ', 'ORIG_TAZ','CountyID', 'DistID']], left_on='dest_mgra', right_on='MAZ', how='left', suffixes= (None, "_dest"))

        
        if IndivJoint == 'Indiv':
            tour['num_participants'] = 1
            tour['tour_participants'] = tour['person_num']
            ## TODO: Add parking information later
            # Add free-parking choice from persons table
            # tour = tour.merge(persons[['person_id', 'fp_choice']], on='person_id', how='left')

            # # Compute the tour parking rate
            # tour['parking_rate'] = np.where(tour['tour_category'] == 'MANDATORY', tour['PRKCST'], tour['OPRKCST'])
            # # Free parking for work tours if fp_choice == 1
            # tour['parking_rate'] = np.where((tour['tour_purpose'][:4] == 'work') & (tour['fp_choice'] == 1) ,0.0, tour['parking_rate'])
        else:
            ## TODO: TM2 output do not have OPRKCST - what is an alternative for this? 
            #tour['parking_rate'] = tour['OPRKCST']  # Joint tours always use OPRKCST
            # Merge number of participants from trips file
            tour['num_participants'] = (tour['tour_participants'].str.split(' '))
            tour['num_participants'] = tour['num_participants'].str.len()
            tour['person_id'] = 0
            tour['person_num'] = 0
 

        print(f"Read {len(tour):,} rows from {tour_file}")
        print(tour.head())
        return tour
    
    def combine_trips(self, persons: pd.DataFrame) -> pd.DataFrame:

        ## If processed file exist, read that instead:
        if (self.config.updated_dir / 'trips.pickle').exists():
            print("Reading cached processed trips file")
            trips = pd.read_pickle(self.config.updated_dir/ 'trips.pickle')
            return trips

        indiv_trip = self._read_trips('Indiv')
        joint_trip = self._read_trips('Joint')
        joint_person_trips = self._get_joint_persons_trips(joint_trip, persons)

        combined = pd.concat([joint_person_trips, indiv_trip], ignore_index=True)
        combined['trip_mode_label'] = combined['trip_mode'].map(self.lookups.tripMode.set_index('code')['mode'])

        combined['timePeriod'] = pd.cut(combined['stop_period'], bins = [1, 4, 12, 22, 30, 40], labels = ['EA', 'AM', 'MD', 'PM', 'EV'], include_lowest= True)

        print(f"Combined individual trips with joint person trips to make {len(combined):,} rows")
        print(combined.head())
        return combined
    
    def _read_trips(self, IndivJoint: str) -> pd.DataFrame:
        """Read and process trip data.
        Arguments:
        - tours: DataFrame of tours to join with trips
        - IndivJoint: 'Indiv' or 'Joint' to specify trip type
        """
        # Read input file
        trip_file = self.config.main_dir / f"{IndivJoint}TripData_{self.config.iter}.csv"
        trip = pd.read_csv(trip_file)

        if IndivJoint == 'Indiv':
            trip['num_participants'] = 1
            trip['tour_participants'] = trip['person_num']

        print(f"Read {len(trip):,} rows from {trip_file}")
        print(trip.head())
        return trip

    def _get_joint_persons_trips(self, trips: pd.DataFrame, persons: pd.DataFrame) -> pd.DataFrame:
        """Get persons associated with each tour and trip."""
        
        # Unwind the participants for joint tours and make each person their own row
        # TODO: Verify the TM2 uses person_num in the persons file
        tour_files = self.config.main_dir / f"JointTourData_{self.config.iter}.csv"
        participants = pd.read_csv(tour_files)
        participants = participants[['hh_id', 'tour_id', 'tour_participants']]
        participants['person_num'] = participants['tour_participants'].str.split(' ')
        participants = participants.explode('person_num')
        participants['person_num'] = participants['person_num'].astype(int)

        ## Join on household and person num to get person_id
        joint_tour_persons = pd.merge(participants, persons[['hh_id', 'person_num', 'person_id']], on=['hh_id', 'person_num'], how='left')

        print(f"Combined joint tours and persons; have {len(joint_tour_persons):,} rows")
        print(joint_tour_persons.head())

        print("Attaching person to joint trips")
        joint_persons_trips = pd.merge(trips, joint_tour_persons, on= ['hh_id', 'tour_id'], how = 'inner')

        print(('Created joint_person_trips with {0} rows from {1} rows from joint trips {2} rows from joint_tour_persons')
              .format(len(joint_persons_trips), len(trips), len(joint_tour_persons))
              )

        return joint_persons_trips 

    def _add_tours_attributes(self, tours: pd.DataFrame):
        # Add duration
        # TM1
        """Add duration and parking costs to tours"""
        ## TM1: start_hour and end_hour
        tours['duration'] = tours['end_hour'] - tours['start_hour']
        ## TM2: start_time and end_time
        tours['duration'] = tours['end_time'] - tours['start_time']

        # Parking Cost is based on tour duration
        tours['parking_cost'] = tours['parking_rate'] * tours['duration']
        
        #Distribute costs across shared ride modes for individual tours
        tours['parking_cost'] = np.where((tours['num_participants'] == 1) & (tours['tour_mode'].isin([3,4])), tours['parking_cost']/ 1.75, tours['parking_cost']) 

        tours['parking_cost'] = np.where((tours['num_participants'] == 1) & (tours['tour_mode'].isin([5,6])), tours['parking_cost']/ 2.5, tours['parking_cost'])

        # Set transit parking cost to zero
        tours['parking_cost'] = np.where(tours['tour_mode'] >= 9, 0.0, tours['parking_cost'])


        ## TODO: Do we need to do this if tours have tour_time?
        ## Stop and End Period are coded with different increments of time

        # Add Parking Costs
        # TODO: Add in parking cost once we determine which field to use for parking

        return tours
    
    def read_work_school_location(self, landuse: pd.DataFrame):
        wsLoc_File = self.config.main_dir / f'wsLocResults_{ITER}.csv'
        wsLoc = pd.read_csv(wsLoc_File)
        
        # Filter out non-work travel
        work_location = wsLoc[wsLoc['WorkLocation'] != 0]

        # Add home county
        work_location = work_location.merge(landuse[['MAZ', 'ORIG_MAZ', 'ORIG_TAZ','DistID', 'CountyID']], left_on = 'HomeMGRA', right_on = 'MAZ', suffixes = (None, '_home'))
        ## Rename columns
        #work_location.rename({"MAZ": "HomeMAZ", 'ORIG_MAZ': 'HomeORIGMAZ', 'ORIG_TAZ':'HomeORIGTAZ', 'CountyID': 'HomeCountyID', 'DistID': "HomeDistID"}, inplace=True)

        # Add work county
        work_location = work_location.merge(landuse[['MAZ', 'ORIG_MAZ', 'ORIG_TAZ', 'DistID', 'CountyID']], left_on = 'WorkLocation', right_on = 'MAZ', suffixes = ('_home', '_work'))
        ## Rename columns
        # work_location.rename({"MAZ": "WorkMAZ", 'ORIG_MAZ': 'WorkORIGMAZ', 'ORIG_TAZ':'WorkORIGTAZ', 'CountyID': 'WorkCountyID', 'DistID': "WorkDistID"}, inplace = True)


        return work_location


class SkimReader:
    """Class for processing skim data and adding costs, distances, and times to trips/tours.
    
    """
    ## TODO: What is part of skim processing vs data reading? - should we be adding costs/distances/times here? This could also be used for acceptance criteria 
    ## TM1 uses simple skims; TM2 uses more complex skims -> do we create simple skims from our skim matrices?
    ## TODO: Use make_transit_in_vehicle_time_table function from simulated.py for transit in-vehicle times
    ## What skims do we want for transit and roadway


    def __init__(self, config: Config, lookups: LookupTables):
        self.config = config
        self.lookups = lookups
        
        ## TM1 Skims
        # self.cost_skim = self.read_skim_csv('Cost')
        # self.distance_skim = self.read_skim_csv('Distance')
        # self.time_skim = self.read_skim_csv('Time')
        # self.active_time_skim = self.read_skim_csv('ActiveTime')
        
        ## TM2 Skims

    ## Simple skims readings for TM1
    def read_skim_csv(self, skim_type: str) -> pd.DataFrame:
        """
        Read skim data from a CSV file. This will loop through all time periods and concatenate them.
        Arguments:
        - skim_type: Type of skim to read (e.g., 'Cost', 'Distance', 'Time', 'ActiveTime')
        """
        combined_skim = None
        for timeperiod in self.lookups.timeperiod['timeperiod_abbrev']:
            skim_file = Path(self.config.target_dir) / "database" / f"{skim_type}SkimsDatabase{timeperiod}.csv"
            skims = pd.read_csv(skim_file)
            skims.rename(columns={'orig': 'orig_taz', 'dest': 'dest_taz'}, inplace=True)
            skims['time_period'] = timeperiod

            if combined_skim is None:
                combined_skim = skims.copy()
            else:
                combined_skim = pd.concat([combined_skim, skims], ignore_index=True)
        return combined_skim
    
    
    ## Complex skims reading for TM2 
    ## TODO: What do we need to consolidate from each skim (cost, distance, time, active time)

    
    def _read_transit_skims(self, components: list, time_period):
        """Create table from reading specific components
        
        Reads transit skim matrices to extract certain components. 

        Transit Components may include the following:
        |Components| Description|
        |-----|-----|
        | `IWAIT` | Initial wait time
        | `XWAIT` | Transfer wait time
        | `WAIT` | Total wait time
        | `FARE` | Transit fare cost
        | `BOARDS` | Number of boardings
        | `WAUX` | Walk auxiliary time
        | `DTIME` | Drive access time
        | `DDIST` | Drive access distance
        | `IVT` | Total in-vehicle time
        | `IN_VEHICLE_COST` | In-vehicle cost
        | `WACC` | Walk access time
        | `WEGR` | Walk egress time
        | `CROWD` | Crowding penalty (if enabled)
        | `XBOATIME` | Transfer Boarding Time Penalty
        | `DTOLL` | Drive access/egress toll price
        | `TRIM` |  Used to Trim demand

        Args:
            components: A list of transit components to process
                    
        Returns:
            DataFrame
                Unstacked dataframe with the following columns:

                    - orig: origin taz
                    - dest: destination taz
                    - path: access and egress path
                    - time_period: time period
                    - {components}: process transit component

        """

        path_list = [
            "WLK_TRN_WLK",
            "PNR_TRN_WLK",
            "WLK_TRN_PNR",
            "KNR_TRN_WLK",
            "WLK_TRN_KNR",
        ]

        if 'IVT' in components:
            mode = list(self.lookups.transitMode['mode'])
            mode_list = ['IVT' + str(i) for i in mode]
            #components.extend(mode_list)

        skim_dir = Path(self.config.target_dir) / "skim_matrices" / "transit"

        running_df = None
        for path in path_list:
            filename = os.path.join(
                skim_dir, "trnskm{}_{}.omx".format(time_period.upper(), path)
            )
            if os.path.exists(filename):
                merged_df = None
                omx_handle = omx.open_file(filename)
                TIME_PERIOD = time_period.upper()
                for name in components:
                    print(f"Extracting {name} for {path} during {time_period} period")
                    
                    ## Matrix Name dependent on component
                    matrix_name = TIME_PERIOD + "_" + path + "_" + name
                    if matrix_name in omx_handle.listMatrices():
                        df = self._make_dataframe_from_omx(
                            omx_handle[matrix_name], matrix_name
                        )
                        df = df[df[matrix_name] > 0.0].copy()
                        df.rename(columns={df.columns[2]: name}, inplace=True)
                        print(df.head())
                        print(df.columns)
                        if merged_df is None:
                            merged_df = df.copy()
                            print(merged_df)
                        else:
                            merged_df = merged_df.merge(df, on = ['origin', 'destination'], how = 'left')
                            print(merged_df.head())
                omx_handle.close()

            merged_df['path'] = path
            merged_df['time_period'] = time_period

            print(merged_df.head())
            print(merged_df.columns)

            if running_df is None:
                running_df = merged_df.copy()
            else:
                running_df = pd.concat([running_df,merged_df], axis ="rows", ignore_index = True)

        running_df.describe()
        return running_df
    
    def _read_highway_skims(self, highway_components: list, time_period, vehicle_type):
        """Create tables from highway skims components
        
        Args: 
            highway_components: A list of components to be process.
                List may include the following:
                    time, dist, cost, hovdist, tolldist, freeflowtime, bridgetoll, valuetoll, rlbty, autotime

        Returns:
            DataFrame
                Unstacked Dataframe with the following columns:
                    - orig: origin taz
                    - dest: destination taz
                    - time_period: time period
                    - {highway_component}_{vehicle_type}: highway component by vehicle type
        
        """

        vehicle_types = [
            "da","sr2", "sr3", 
            'datoll', 'sr2toll', 'sr3toll',
            'trk', 'trktoll', 'lrgtrk', 'lrgtrktoll'
        ]

        skim_dir = Path(self.config.target_dir) / "skim_matrices" / "highway"

        running_df = None
    
        filename = os.path.join(
            skim_dir, "HWYSKM{}_taz.omx".format(time_period.upper())
        )
        if os.path.exists(filename):
            merged_df = None
            omx_handle = omx.open_file(filename)
            for name in highway_components:
                print(f"Extracting {name} for {vehicle_type} during {time_period} period")
                ## Matrix Name dependent on component
                matrix_name = time_period + "_" + vehicle + "_" + name
                if matrix_name in omx_handle.listMatrices():
                    df = self._make_dataframe_from_omx(
                        omx_handle[matrix_name], matrix_name
                    )
                    df = df[df[matrix_name] > 0.0].copy()
                    df.rename(columns={df.columns[2]: name }, inplace=True)
                    print(df.head())
                    print(df.columns)
                    if merged_df is None:
                        merged_df = df.copy()
                        print(merged_df)
                    else:
                        merged_df = merged_df.merge(df, on = ['origin', 'destination'], how = 'left')
                        print(merged_df.head())
            omx_handle.close()

            print(merged_df.head())
            print(merged_df.columns)
        
        return merged_df

    def read_skim_omx(self, skim_type: str, timeperiod: str):
        """
        Read skims and format it for core summaries purpose (cost, distance, time, active time)

        """

        if skim_type == 'cost':
            highway_components = ['cost'] #, 'valuetoll', 'bridgetoll']
            transit_components = ['in_vehicle_cost', 'fare']
                        
        highway_skim = self._read_highway_skims(highway_components)
        transit_skim = self._read_transit_skims(transit_components)

        skim = pd.merge(highway_skim, transit_skim, on = ['origin', 'destination'])

        #self._read_transit_skims()


        return skim
    
    def _make_dataframe_from_omx(self, matrix: omx, matrix_name: str):
        """Convert OMX matrix to long-format DataFrame
        
        Reads OpenMatrix Files and convert to pandas DataFrame 
        with origin-destination pairs. 

        Args:
            matrix (omx): OpenMatrix matrix object
            matrix_name (str): Name of matrix core to extract

        Returns:
            pd.DataFrame: Long-format DataFrame with columns:
                - origin: Origin TAZ
                - destination: Destination TAZ
                - {core_name}: Matrix value

        """
        a = np.array(matrix)
        df = pd.DataFrame(a)
        df = (
            df.unstack()
            .reset_index()
            .rename(
                columns = {"level_0": "origin", "level_1":"destination", 0: matrix_name}
            )
        )

        df['origin'] = df['origin'] + 1
        df['destination'] = df['destination'] + 1

        return df


    ## TODO: REVAMP
    def add_cost(self, trips_or_tours: pd.DataFrame, timeperiod: str, reverse_od: bool = False) -> pd.DataFrame:
        """Add cost data to trips or tours for a specific time period."""
        # Filter for relevant time period
        relevant = trips_or_tours[trips_or_tours['timeCode'] == timeperiod].copy()
        irrelevant = trips_or_tours[trips_or_tours['timeCode'] != timeperiod].copy()
        
        if len(relevant) == 0:
            return trips_or_tours
        
        # Read cost skims
        skim_file = Path(self.config.target_dir) / "database" / f"CostSkimsDatabase{timeperiod}.csv"
        cost_skims = pd.read_csv(skim_file)
        
        # Rename columns for joining
        if reverse_od:
            cost_skims.rename(columns={'dest': 'orig_taz', 'orig': 'dest_taz'}, inplace=True)
        else:
            cost_skims.rename(columns={'orig': 'orig_taz', 'dest': 'dest_taz'}, inplace=True)
        
        # Join skims to data
        relevant = relevant.merge(cost_skims, on=['orig_taz', 'dest_taz'], how='left')
        
        # Calculate costs based on mode and income
        relevant = self._calculate_costs(relevant)
        
        # Handle missing values
        relevant['cost2'] = relevant['cost2'].fillna(0)
        relevant['cost_fail2'] = (relevant['cost2'] < -990).astype(int)
        relevant.loc[relevant['cost2'] < -990, 'cost2'] = 0
        
        # Add to existing cost
        if 'cost' not in relevant.columns:
            relevant['cost'] = 0
        if 'cost_fail' not in relevant.columns:
            relevant['cost_fail'] = 0
            
        relevant['cost'] += relevant['cost2']
        relevant['cost_fail'] += relevant['cost_fail2']
        
        print(f"For {timeperiod} assigned {(relevant['cost2'] > 0).sum():,} nonzero costs")
        
        # Clean up
        skim_cols = ['da', 'daToll', 's2', 's2Toll', 's3', 's3Toll', 'wTrnW', 'dTrnW', 'wTrnD', 'cost2', 'cost_fail2']
        relevant = relevant.drop(columns=[col for col in skim_cols if col in relevant.columns])
        
        return pd.concat([relevant, irrelevant], ignore_index=True)
    
    def _calculate_costs(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate costs based on mode and income quartile."""
        df['cost2'] = 0.0
        
        # Drive alone
        df.loc[df['costMode'] == 1, 'cost2'] = df.loc[df['costMode'] == 1, 'da']
        
        # Drive alone toll with means-based tolling
        mask = df['costMode'] == 2
        df.loc[mask & (df['incQ'] == 1), 'cost2'] = df.loc[mask & (df['incQ'] == 1), 'daToll'] * self.config.mbt_q1_factor
        df.loc[mask & (df['incQ'] == 2), 'cost2'] = df.loc[mask & (df['incQ'] == 2), 'daToll'] * self.config.mbt_q2_factor
        df.loc[mask & (df['incQ'] >= 3), 'cost2'] = df.loc[mask & (df['incQ'] >= 3), 'daToll']
        
        # Shared ride 2
        df.loc[df['costMode'] == 3, 'cost2'] = df.loc[df['costMode'] == 3, 's2']
        
        # Shared ride 2 toll
        mask = df['costMode'] == 4
        df.loc[mask & (df['incQ'] == 1), 'cost2'] = df.loc[mask & (df['incQ'] == 1), 's2Toll'] * self.config.mbt_q1_factor
        df.loc[mask & (df['incQ'] == 2), 'cost2'] = df.loc[mask & (df['incQ'] == 2), 's2Toll'] * self.config.mbt_q2_factor
        df.loc[mask & (df['incQ'] >= 3), 'cost2'] = df.loc[mask & (df['incQ'] >= 3), 's2Toll']
        
        # Continue for other modes...
        # (Similar pattern for modes 5-6, 7-8 are free, 9-11 transit with means-based fares)
        
        # Walk-transit
        mask = df['costMode'] == 9
        low_income_mask = df['pct_of_poverty'] <= self.config.mbf_pct_poverty_threshold
        df.loc[mask & low_income_mask, 'cost2'] = df.loc[mask & low_income_mask, 'wTrnW'] * self.config.mbf_factor
        df.loc[mask & ~low_income_mask, 'cost2'] = df.loc[mask & ~low_income_mask, 'wTrnW']
        
        return df
    
    def add_distance(self, trips_or_tours: pd.DataFrame, timeperiod: str, vehicle: str) -> pd.DataFrame:
        """Add distance data to trips or tours for a specific time period."""
        # Similar structure to add_cost but for distance skims
        relevant = trips_or_tours[trips_or_tours['timeCode'] == timeperiod].copy()
        irrelevant = trips_or_tours[trips_or_tours['timeCode'] != timeperiod].copy()
        
        if len(relevant) == 0:
            return trips_or_tours
        
        # Read distance skims - only for TM1
        skim_file = Path(self.config.target_dir) / "database" / f"DistanceSkimsDatabase{timeperiod}.csv"
        dist_skims = pd.read_csv(skim_file)
        dist_skims.rename(columns={'orig': 'orig_taz', 'dest': 'dest_taz'}, inplace=True)

        ## TM2 Read Skims
        dist_skims = self._read_highway_skims(highway_components = ['dist'], time_period = timeperiod, vehicle_type = vehicle)
        
        
        # Join and calculate distance--
        relevant = relevant.merge(dist_skims, on=['orig_taz', 'dest_taz'], how='left')
        
        if 'distance' not in relevant.columns:
            relevant['distance'] = 0.0
        
        # Calculate distance based on mode
        relevant['distance2'] = 0.0
        for mode in [1, 2, 3, 4, 5, 6]:  # Auto modes
            mode_col = {1: 'da', 2: 'daToll', 3: 's2', 4: 's2Toll', 5: 's3', 6: 's3Toll'}[mode]
            relevant.loc[relevant['distance_mode'] == mode, 'distance2'] = relevant.loc[relevant['distance_mode'] == mode, mode_col]
        
        # Handle walk/bike
        relevant.loc[relevant['distance_mode'] == 7, 'distance2'] = relevant.loc[relevant['distance_mode'] == 7, 'walk']
        relevant.loc[relevant['distance_mode'] == 8, 'distance2'] = relevant.loc[relevant['distance_mode'] == 8, 'bike']
        
        # Handle transit (use auto distance as proxy)
        transit_mask = relevant['distance_mode'] >= 9
        relevant.loc[transit_mask, 'distance2'] = np.minimum(
            relevant.loc[transit_mask, 'da'], 
            relevant.loc[transit_mask, 'daToll']
        )
        
        relevant['distance2'] = relevant['distance2'].fillna(0)
        relevant.loc[relevant['distance2'] < -990, 'distance2'] = 0
        relevant['distance'] += relevant['distance2']
        
        print(f"For {timeperiod} assigned {(relevant['distance2'] > 0).sum():,} nonzero distances")
        
        # Clean up
        skim_cols = ['da', 'daToll', 's2', 's2Toll', 's3', 's3Toll', 'walk', 'bike', 'distance2']
        relevant = relevant.drop(columns=[col for col in skim_cols if col in relevant.columns])
        
        return pd.concat([relevant, irrelevant], ignore_index=True)

    ## THis is function for TM1 only
    def add_simple_purpose(self, tours: pd.DataFrame) -> pd.DataFrame:
        """Add simplified purpose categories to tours."""
        purpose_map = {
            'work_low': 'Work',
            'work_med': 'Work',
            'work_high': 'Work',
            'work_very high': 'Work',
            'school_grade': 'School',
            'school_high': 'School',
            'university': 'College',
            'atwork_business': 'At Work',
            'atwork_eat': 'At Work',
            'atwork_maaint': 'At Work'
        }
        tours['simple_purpose'] = tours['tour_purpose'].map(purpose_map).fillna('non-work')
        return tours
       
    def add_active_modes(self, trips: pd.DataFrame) -> pd.DataFrame:
        """Add indicators for active transportation modes."""
 
        conditions = [
            trips['trip_mode'] == 7,
            trips['trip_mode'] == 8,
            (trips['trip_mode'] >= 9) & (trips['trip_mode'] <= 13),
            (trips['trip_mode'] >= 14) & (trips['trip_mode'] <= 18) & (trips['orig_purpose'] == 'Home'),
            (trips['trip_mode'] >= 14) & (trips['trip_mode'] <= 18) & (trips['dest_purpose'] == 'Home')
        ]
        
        choices = [1, 2, 3, 4, 5]

        trips['amode'] = np.select(conditions, choices, default=0)
        
        trips['wlk_trip'] = (trips['amode'] == 1).astype(int)
        trips['bik_trip'] = (trips['amode'] == 2).astype(int)
        trips['wtr_trip'] = (trips['amode'] == 3).astype(int)
        trips['dtr_trip'] = np.where(
            trips['amode'] == 4, 1, 
            np.where(trips['amode'] == 5, 1 + trips['amode'], 0
        ))
        trips['active'] = 0

        ## Add active transportation time to trips based on 

        return trips
    
    def add_active_skim(self, trips: pd.DataFrame) -> pd.DataFrame:
        """Add the active skim to the given trip data frame (Remove the time period).
        Joins on columns orig_taz and dest_taz and timeCode (may change for TM2)
        TODO: This could taken from the acceptance test for TM2
        """
        # Separate out the relevant and irrelevant tours/trips
        relevant = trips[trips['timeCode'] == timeperiod].copy()
        irrelevant = trips[trips['timeCode'] != timeperiod].copy()
        
        if len(relevant) == 0:
            return trips
        for timeperiod in self.lookups.timeperiod_abbrev:
        # Read active skims
            skim_file = Path(self.config.target_dir) / "database" / f"ActiveSkimsDatabase{timeperiod}.csv"
            active_skims = pd.read_csv(skim_file)
            active_skims.rename(columns={'orig': 'orig_taz', 'dest': 'dest_taz'}, inplace=True)
        
        # Join and calculate active times
        relevant = relevant.merge(active_skims, on=['orig_taz', 'dest_taz'], how='left')
        
        if 'active_time' not in relevant.columns:
            relevant['active_time'] = 0.0
        
        # Calculate active time based on mode
        relevant['active_time2'] = 0.0
        relevant.loc[relevant['amode'] == 1, 'active_time2'] = relevant.loc[relevant['amode'] == 1, 'walk']
        relevant.loc[relevant['amode'] == 2, 'active_time2'] = relevant.loc[relevant['amode'] == 2, 'bike']
        
        # For walk-transit and drive-transit, use walk access/egress time
        transit_mask = relevant['amode'].isin([3, 4, 5])
        #relevant.loc[transit_mask, 'active_time2

class SummaryGenerator:
    """Class for generating various summary reports."""
    
    # TODO: Need to make this run properly
    def __init__(self, config: Config, lookups: LookupTables):
        self.config = config
        self.lookups = lookups
    
    # TODO: Update
    def generate_active_transport_summary(self, trips_by_person: pd.DataFrame) -> None:
        """Generate active transportation summary."""
        # Calculate summary statistics
        summary = trips_by_person.groupby(['taz', 'county_name', 'ptype', 'zeroAuto']).agg({
            'person_id': 'count',  # frequency
            'active': 'mean',
            'more15': 'mean',
            'more30': 'mean',
            'wlk_trip': 'mean',
            'bik_trip': 'mean',
            'wtr_trip': 'mean',
            'dtr_trip': 'mean',
            'atHomeA': 'mean'
        }).reset_index()
        
        summary.rename(columns={'person_id': 'freq'}, inplace=True)
        summary['freq'] = summary['freq'] / self.config.sampleshare
        
        # Save results
        output_file = self.config.results_dir / "ActiveTransport.csv"
        summary.to_csv(output_file, index=False)
        
        with open(self.config.results_dir / "ActiveTransport.pickle", 'wb') as f:
            pickle.dump(summary, f)
        
        print(f"Wrote {len(summary):,} rows of active_summary")

    def generate_activity_pattern_summary(self, persons: pd.DataFrame) -> None:
        """
        Generate activity pattern summary.

        Universe: Persons
        
        """
        summary = persons.groupby(['type', 'cdap', 'imf_choice', 
                                   'inmf_choice', 'incQ', 'incQ_label']).agg({'person_id':'count'}).reset_index()
        
        summary.rename(columns={'person_id': 'freq'}, inplace=True)
        summary['freq'] = summary['freq'] / self.config.sampleshare
        
        # Save results
        output_file = self.config.results_dir / "ActivityPattern.csv"
        summary.to_csv(output_file, index=False)
        
        with open(self.config.results_dir / "ActivityPattern.pickle", 'wb') as f:
            pickle.dump(summary, f)
        
        print(f"Wrote {len(summary):,} rows of activity_pattern_summary")     
    
    # TODO: Update
    def generate_auto_ownership_summary(self, households: pd.DataFrame) -> None:
        """Generate auto ownership summary."""
        summary = households.groupby([
            'SD', 'COUNTY', 'county_name', 'autos', 'incQ', 'incQ_label',
            'walk_subzone', 'walk_subzone_label', 'workers', 'kidsNoDr'
        ]).size().reset_index(name='freq')
        
        summary['freq'] = summary['freq'] / self.config.sampleshare
        
        # Save results
        output_file = self.config.results_dir / "AutomobileOwnership.csv"
        summary.to_csv(output_file, index=False)
        
        with open(self.config.results_dir / "AutomobileOwnership.pickle", 'wb') as f:
            pickle.dump(summary, f)
        
        print(f"Wrote {len(summary):,} rows of autoown_summary")
    
    def generate_journey_to_work_summary(self, work_locations: pd.DataFrame) -> None:
        """
        Generate journey to work summary

        Universe: Persons with work location
        """

        summary = work_locations.groupby([
            'CountyID_home', 'MAZ_home', 'ORIG_MAZ_home', 'WorkLocation', 'CountyID_work'
        ]).agg({'PersonID': 'count'}).reset_index()

        summary.rename(columns = {'PersonID': 'freq'}, inplace = True)
        summary['freq'] = summary['freq'] / self.config.sampleshare

        # Save results
        output_file = self.config.results_dir / "JourneyToWork.csv"
        summary.to_csv(output_file, index = False)


    
    # TODO: update
    def generate_vmt_summary(self, persons: pd.DataFrame) -> None:
        """Generate vehicle miles traveled summary."""
        summary = persons.groupby([
            'COUNTY', 'county_name', 'SD', 'taz', 'walk_subzone', 'walk_subzone_label',
            'ptype', 'ptype_label', 'autoSuff', 'autoSuff_label'
        ]).agg({
            'person_id': 'count',
            'vmt_indiv': 'mean',
            'vmt_joint': 'mean',
            'vmt': 'mean',
            'person_trips': 'sum',
            'vehicle_trips': 'sum'
        }).reset_index()
        
        summary.rename(columns={'person_id': 'freq'}, inplace=True)
        summary['freq'] = summary['freq'] / self.config.sampleshare
        summary['person_trips'] = summary['person_trips'] / self.config.sampleshare
        summary['vehicle_trips'] = summary['vehicle_trips'] / self.config.sampleshare
        
        # Save results
        output_file = self.config.results_dir / "VehicleMilesTraveled.csv"
        summary.to_csv(output_file, index=False)
        
        with open(self.config.results_dir / "VehicleMilesTraveled.pickle", 'wb') as f:
            pickle.dump(summary, f)
        
        print(f"Wrote {len(summary):,} rows of vmt_summary")
    
    def generate_trips_tours_summary(
            self,
            df: pd.DataFrame,
            trip_or_tour: str,
            group_by: List[str],
            output_suffix: str,
    ):
        """
        Generate trip or tour summaries with flexible groupin

        Args:
            df: Dataframe to summarize (trips or tours)
            trip_or_tour: String to indicate which universe ('trip' or 'tour')
            group_by: List of column names to groupby
            output_suffix: Suffix for output filename (e.g., 'ByMode', 'ByPurpose')
        
        Returns:
            Summary CSV

        """
        summary = df.groupby(group_by).size().reset_index(name = 'freq')
        summary['freq'] = summary['freq']/self.config.sampleshare
        summary['share'] = (summary['freq'] / summary['freq'].sum())*100

        # Save results
        output_file = self.config.results_dir/f'{trip_or_tour.capitalize()}Summary{output_suffix}.csv'
        summary.to_csv(output_file, index = False)        
      
    def generate_trip_summary_survey(
            self,
            df: pd.DataFrame
    ):
        """
        Generate trip summary for comparsion against BATS Survey results
        """
        dest_purpose_dict ={
           'Discretionary': 'Socrec', 'Visiting': 'Socrec', 'Maintenance': 'Pers_Bus'
        }
        df['simple_trip_mode'] = df['trip_mode'].map(self.lookups.tripMode.set_index('code')['simple_mode'])
        df['simple_dest_purpose'] = df['dest_purpose'].replace(dest_purpose_dict)
        print(df.head())
        summary = df.groupby(['simple_trip_mode', 'simple_dest_purpose']).size().reset_index(name = 'freq')

        summary['freq'] = summary['freq']/self.config.sampleshare
        summary['share'] = (summary['freq'] / summary['freq'].sum())*100

        output_file = self.config.results_dir/f'TripSummarySimpleModePurpose.csv'
        summary.to_csv(output_file, index = False)        


class CoreSummaries:
    """Main class orchestrating the entire core summaries process."""
    
    def __init__(self):
        self.config = Config()
        self.lookups = LookupTables()
        self.data_reader = DataReader(self.config, self.lookups)
        self.skim_reader = SkimReader(self.config, self.lookups)
        self.summary_generator = SummaryGenerator(self.config, self.lookups)


    def run_analysis(self):
        """Run the complete core summaries analysis."""
        print("Starting Core Summaries Analysis...")
        
        # Read base data
        print("Reading land use data...")
        landuse = self.data_reader.read_land_use()
        print(f"Land Use: \n {landuse.head()}")
        
        print("Reading household data...")
        households = self.data_reader.read_households(landuse)
        print(f"Household: \n {households.head()}")

        print("Reading person data...")
        persons = self.data_reader.read_persons(households)
        print(f"Persons: \n {persons.head()}")
        
        #print("Adding kids no driver variable")
        ## TODO: Skipping this for now until I resolve type dictionary 
        #households = self.data_reader.add_kids_no_driver(persons, households)
        
        # Read tour and trip data
        print("Reading tour data...")
        # This would involve reading tour and trip files and processing them
        
        tours = self.data_reader.combine_tours(households, landuse)
        print(f"Tours: \n {tours.head()}")

        print("Reading trip data ...")
        trips = self.data_reader.combine_trips(persons)
        print(f"Trips \n {trips.head()}")


        print("Reading work-school location...")
        work_locations = self.data_reader.read_work_school_location(landuse)
        print(f"Trips \n {work_locations.head()}")
  

        # Generate summaries
        print("Generating summaries...")

        print("Gerenate Activity Pattern summary")
        self.summary_generator.generate_activity_pattern_summary(persons)

        print("Generate trips summary")
        self.summary_generator.generate_trip_summary_survey(trips)
        self.summary_generator.generate_trips_tours_summary(trips, 'trip', ['trip_mode', 'trip_mode_label'], 'ByMode')
        self.summary_generator.generate_trips_tours_summary(trips, 'trip', ['trip_mode', 'trip_mode_label', 'tour_purpose'], 'ByModePurpose')
        self.summary_generator.generate_trips_tours_summary(trips, 'trip', ['tour_purpose'], 'ByPurpose')
        
        print("Generate tours summaries")
        self.summary_generator.generate_trips_tours_summary(tours, 'tour', ['tour_mode', 'tour_mode_label'], 'ByMode')
        self.summary_generator.generate_trips_tours_summary(tours, 'tour', ['tour_mode', 'tour_mode_label', 'tour_purpose'], 'ByModePurpose')
        self.summary_generator.generate_trips_tours_summary(tours, 'tour', ['tour_purpose'], 'ByPurpose')

        print("Generating journey to work summary")
        self.summary_generator.generate_journey_to_work_summary(work_locations)
        # Save processed data
        print("Saving processed data...")
        households.to_pickle(self.config.updated_dir / "households.pickle")
        persons.to_pickle(self.config.updated_dir / "persons.pickle")
        trips.to_pickle(self.config.updated_dir / "trips.pickle")
        tours.to_pickle(self.config.updated_dir / "tours.pickle")
        work_locations.to_pickle(self.config.updated_dir / "work_locations.pickle")
        

        
        print("Core Summaries Analysis completed successfully!")


def main():
    """Main execution function."""
    try:
        core_summaries = CoreSummaries()
        core_summaries.run_analysis()
    except Exception as e:
        print(f"Error running analysis: {e}")
        raise


if __name__ == "__main__":
    main()
