import os
import pandas as pd
import numpy as np
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import openmatrix as omx
import itertools
from pydantic import BaseModel, Field
import logging
from tm2py.config import Configuration

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
        _model_config = os.path.join(TARGET_DIR, 'model_config.toml')
        _scenario_config = os.path.join(TARGET_DIR, 'scenario_config.toml')
        self.config = Configuration.load_toml([_scenario_config, _model_config])
        self.target_dir = TARGET_DIR
        self.iter = ITER
        self.sampleshare = self.config.household.sample_rate_by_iteration[self.iter - 1]
        self.timeperiod = pd.DataFrame(self.config.time_periods)
        self.income_quartiles = pd.DataFrame(self.config.household.income_segment)
        self.modes = pd.DataFrame(self.config.household.ctramp_mode_names.items(), columns = ['code', 'mode'])


        
        # Adding additional lookups
        # Counties
        self.county = pd.DataFrame({
            'COUNTY': [1, 2, 3, 4, 5, 6, 7, 8, 9],
            'county_name': ['San Francisco', 'San Mateo', 'Santa Clara', 'Alameda',
                           'Contra Costa', 'Solano', 'Napa', 'Sonoma', 'Marin']
        })

        # Auto sufficiency
        self.autosuff = pd.DataFrame({
            'autoSuff': [0, 1, 2],
            'autoSuff_label': ['Zero automobiles', 'Automobiles < workers', 'Automobiles >= workers']
        })
        
                

        # Validate required parameters
        if not self.target_dir or not self.iter or not self.sampleshare:
            raise ValueError("TARGET_DIR, ITER, and SAMPLESHARE environment variables must be set")
        

        # Directory paths
        self.target_dir = self.target_dir.replace("\\", "/")
        self.main_dir = Path(self.target_dir) / "ctramp_output"
        self.results_dir = Path(self.target_dir) / "core_summaries"
        self.updated_dir = Path(self.target_dir) / "updated_output"
        
        # Create directories if they don't exist
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.updated_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse means-based cost factors
        #self._parse_cost_factors()
        
        self._setup_logging()    
        
        logging.info(f"TARGET_DIR  = {self.target_dir}")
        logging.info(f"ITER        = {self.iter}")
        logging.info(f"SAMPLESHARE = {self.sampleshare}")
    
    def _setup_logging(self):
        """
        Set up logging to file and console.
        """
        log_file = Path(self.results_dir) /'core_summaries.log'

        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        # console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'))
        self.logger.addHandler(ch)

        # file handler
        fh = logging.FileHandler(log_file, mode = 'w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'))
        self.logger.addHandler(fh)


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
    
    def __init__(self, config: Config):
        self.config = config
    
    def add_kids_no_driver(self, persons, households):
        """
        Add kids No Driver as a variable to the household data.
        
        """
        # If variable already exists, return households
        if 'kidsNoDr' in households.columns:
            logging.info("kidsNoDr variable already exists in households")
            return households

        logging.info("Adding kidsNoDr variable to households")
        #  No Driver as a binary (1 for kid, 0 for no kid)
        kidsNoDr_hhlds = persons[['hh_id', 'kidsNoDr']].groupby('hh_id', as_index= True ).agg({'kidsNoDr': 'max'})
        households = households.merge(kidsNoDr_hhlds, on = 'hh_id', how = 'left', validate = 'one_to_one')

        return households  

    def combine_tours(self, households: pd.DataFrame, landuse: pd.DataFrame) -> pd.DataFrame:
        """Combine joint and individual tours into a single DataFrame."""

        ## If processed file exist, read that instead:
        if (self.config.updated_dir / 'tours.parquet').exists():
            logging.info("Reading cached processed tours file")
            tours = pd.read_parquet(self.config.updated_dir/ 'tours.parquet')
            return tours

        logging.info("Reading and combining tours")
        jointTours = self._read_tours('Joint')
        indivTours = self._read_tours('Indiv')
        jointTours = jointTours.drop(columns = ['tour_composition'])
        indivTours = indivTours.drop(columns = ['person_type', 'atWork_freq'])
        tours = pd.concat([jointTours, indivTours], ignore_index=True)

        #tours.rename(columns = {'orig_mgra': 'origin_MAZ_SEQ', 'dest_mgra':'destination_MAZ_SEQ'}, inplace = True)
        
        # Add Residence Landuse Info
        logging.info("Adding residence land use info to tours")
        tours = tours.merge(households[['hh_id', 'CountyID', 'DistID', 'incQ']], on='hh_id', how='left', validate=  'many_to_one')
        logging.debug(tours.head())

        ## TODO: Add CountyID for Destination MAZ
        logging.info("Adding destination land use info to tours")
        tours = tours.merge(landuse.rename(columns = {'MAZ_NODE':'destination_MAZ_NODE',
                                  'DistID':'destination_DistID',
                                  'CountyID': 'destination_CountyID'
                            })[['destination_MAZ_NODE', 'destination_CountyID', 'destination_DistID']], 
                            on = 'destination_MAZ_NODE', validate= 'many_to_one')
        logging.debug(tours.head())

        tours['tour_mode_label'] = tours['tour_mode'].map(self.config.modes.set_index('code')['mode'])
        logging.info(f"Combined tours; have {len(tours):,} rows")
        logging.debug(tours.head())
        #tours = tours._add_tours_attrs()
        return tours
    
    def combine_trips(self, persons: pd.DataFrame, households: pd.DataFrame) -> pd.DataFrame:
        """
        Combined individual and joint trips together. Joint trips will be unwind so each person will have a trip

        The following variables will also be merged from the household table:
            - Home_MAZ
            - incQ
            - autoSuff
        """
        ## If processed file exist, read that instead:
        if (self.config.updated_dir / 'trips.parquet').exists():
            logging.info("Reading cached processed trips file")
            trips = pd.read_parquet(self.config.updated_dir/ 'trips.parquet')
            return trips

        logging.info("Reading and combining trips")
        indiv_trip = self._read_trips('Indiv')
        joint_trip = self._read_trips('Joint')
        joint_person_trips = self._get_joint_persons_trips(joint_trip, persons)

        combined = pd.concat([joint_person_trips, indiv_trip], ignore_index=True)
        print(combined.columns)
        combined['trip_mode_label'] = combined['trip_mode'].map(self.config.modes.set_index('code')['mode'])
        
        # Join with household data
        combined = combined.merge(households[['hh_id', 'incQ', 'autoSuff', 'autoSuff_label']], 
                                  on = 'hh_id', validate = 'm:1')
        
        # Don't need to include timePeriod since updated trips output with skims should have timePeriods
        #combined['timePeriod'] = pd.cut(combined['stop_period'], bins = [1, 4, 12, 22, 30, 40], labels = ['EA', 'AM', 'MD', 'PM', 'EV'], include_lowest= True)

        combined.rename(columns= {'parking_mgra': 'parking_MAZ_SEQ'}, inplace= True)
        logging.info(f"Combined individual trips with joint person trips to make {len(combined):,} rows")
        logging.debug(combined.head())
        return combined

    def read_households(self, land_use: pd.DataFrame) -> pd.DataFrame:
        """Read and process household data."""
        
        ## TM2
        ## If processed file exist, read that instead:
        if (self.config.updated_dir / 'households.parquet').exists():
            logging.info("Reading cached processed household file")
            persons = pd.read_parquet(self.config.updated_dir/ 'households.parquet')
            return persons
        popsyn_file = Path(self.config.target_dir) / "inputs" / "popsyn" / "households.csv"
        ct_file = self.config.main_dir / f"householdData_{self.config.iter}.csv"

        input_pop_hh = pd.read_csv(popsyn_file)
        input_pop_hh.rename(columns={'HHID': 'hh_id', 'MAZ': 'MAZ_SEQ', 'TAZ': 'TAZ_SEQ', 'ORIG_MAZ': 'MAZ_NODE', 'ORIG_TAZ': 'TAZ_NODE'}, inplace=True)

        output_ct_hh = pd.read_csv(ct_file)
        output_ct_hh.rename(columns = {'home_mgra': 'HOME_MAZ_SEQ'}, inplace = True)
        logging.debug(f"Read {len(input_pop_hh):,} rows from popsyn households and {len(output_ct_hh):,} rows from ct households")

        # Join input and output datasets
        households = input_pop_hh.merge(output_ct_hh, left_on = 'hh_id', right_on = 'hh_id', how = 'inner', validate = 'one_to_one')

        logging.info(f"Read input household files; have {len(households):,} rows")
        # Add land use data
        households = households.merge(land_use, on= ['MAZ_NODE', 'TAZ_NODE', 'MAZ_SEQ', 'TAZ_SEQ'], how = 'left', validate = 'many_to_one')
        logging.info(f"After merging land use, have {len(households):,} rows")
        logging.debug(households.head())

        # Add household variables
        households = self._add_household_variables(households)
       
        return households
    
    
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
        # TODO: Confirm land use file after update
        logging.info("Reading land use data")
        maz_file = Path(self.config.target_dir) / "inputs" / "landuse" / "maz_data_withDensity.csv"
        maz_data = pd.read_csv(maz_file ) #, usecols = ['MAZ', 'TAZ','MAZ_ORIGINAL', 'TAZ_ORIGINAL', 'CountyID', 'DistID', 'hparkcost'])

        ## TODO: What parking data do we want to include
        maz_data = maz_data.rename(columns = {'MAZ_ORIGINAL':'MAZ_NODE', 'TAZ_ORIGINAL':'TAZ_NODE', 'MAZ': 'MAZ_SEQ', 'TAZ': 'TAZ_SEQ'})
        maz_data = maz_data[['MAZ_SEQ', 'TAZ_SEQ', 'MAZ_NODE', 'TAZ_NODE', 'CountyID', 'DistID', 'hparkcost']]

        logging.info(f"Read land use data; have {len(maz_data):,} rows")
        logging.debug(maz_data.head())
        return maz_data
    
    def read_persons(self, households: pd.DataFrame) -> pd.DataFrame:
        """Read and process person data."""
        
        ## If processed file exist, read that instead:
        if (self.config.updated_dir / 'persons.parquet').exists():
            logging.info("Reading cached processed persons file")
            persons = pd.read_parquet(self.config.updated_dir / 'persons.parquet')
            return persons
        # Read input files
        logging.info("Reading and processing persons input and output data")
        popsyn_file = Path(self.config.target_dir) / "inputs" / "popsyn" / "persons.csv"
        ct_file = self.config.main_dir / f"personData_{self.config.iter}.csv"
        
        input_pop_persons = pd.read_csv(popsyn_file)
        input_ct_persons = pd.read_csv(ct_file)
        
        # Rename columns
        input_pop_persons.rename(columns={'HHID': 'hh_id', 'PERID': 'person_id'}, inplace=True)
        
        logging.info(f"Read {len(input_pop_persons):,} rows from input persons data and {len(input_ct_persons):,} rows from output persons data")

        # Join datasets
        logging.info("Merging input and output persons data")
        persons = input_pop_persons.merge(input_ct_persons, on=['hh_id', 'person_id'], how='inner', validate = 'one_to_one')
        logging.info(f"After merging input and output persons data, have {len(persons):,} rows")

        # Add income quartile, household size, auto ownership, home MAZ from households
        logging.info("Adding household attributes to persons data")
        persons = persons.merge(households[['hh_id', 'incQ', 'size', 'autos', 'MAZ_NODE', 'TAZ_NODE', 'MTCCountyID']], on='hh_id', how='left', validate = 'many_to_one')
        logging.debug(persons.head())
        
        # Add kids no driver indicator
        logging.info("Adding kidsNoDr dummy variable to persons data")
        persons['kidsNoDr'] = np.where(persons['type'].isin(['Child too young for school', 'Non-driving-age student']), 1, 0)
        
        logging.info(f"Read persons files; have {len(persons):,} rows")
        logging.debug(persons.head())

        return persons
    
    def read_work_school_location(self, landuse: pd.DataFrame, tours: pd.DataFrame):
        """
        Read and process work school location file

        Args:
            Landuse (df): Processed landuse dataframe
            tours (df): Processed Tours dataframe

        Return:
            Dataframe with work locations only

        """
        if (self.config.updated_dir / 'work_locations.parquet').exists():
            logging.info("Reading cached processed work_location file")
            work_location = pd.read_parquet(self.config.updated_dir / 'work_locations.parquet')
            return work_location

        logging.info("Reading work-school location data")
        wsLoc_File = self.config.main_dir / f'wsLocResults_{ITER}.csv'
        wsLoc = pd.read_csv(wsLoc_File)
        
        # Filter out non-work travel
        work_location = wsLoc[wsLoc['WorkLocation'] != 0]
        logging.info(f"Filtered work-school location data to work locations; have {len(work_location):,} rows")

        work_location.rename(columns={'HHID': 'hh_id', 'HomeMGRA': 'HOME_MAZ_SEQ'}, inplace=True)
        # Add home county
        logging.info("Adding home county to work location data")
        work_location = work_location.merge(landuse.rename(columns = {'MAZ_SEQ':'HOME_MAZ_SEQ', 'MAZ_NODE': 'HOME_MAZ_NODE',
                                                                    'TAZ_NODE': 'HOME_TAZ_NODE','DistID':'HOME_DistID','CountyID': 'HOME_CountyID'})
                                                                    [['HOME_MAZ_SEQ', 'HOME_MAZ_NODE', 'HOME_TAZ_NODE','HOME_DistID', 'HOME_CountyID']], 
                                                                    on = 'HOME_MAZ_SEQ', how = 'left')
        logging.debug(work_location.head())

        # Add work county
        ## WFH tours do not have a work county 
        logging.info("Adding work county to work location data")
        work_location = work_location.merge(landuse.rename(columns = {'MAZ_SEQ':'WORK_MAZ_SEQ', 'MAZ_NODE': 'WORK_MAZ_NODE',
                                                                    'TAZ_NODE': 'WORK_TAZ_NODE','DistID':'WORK_DistID','CountyID': 'WORK_CountyID'})
                                                                    [['WORK_MAZ_SEQ', 'WORK_MAZ_NODE', 'WORK_TAZ_NODE', 'WORK_DistID', 'WORK_CountyID']],
                                                                      left_on = 'WorkLocation', right_on = 'WORK_MAZ_SEQ',  how = 'left')
        logging.debug(work_location.head())
        
        
        ## Add relevant information for journey to work by modes (tour)
        # Add tour mode, wfh, walk subzone(?) - this may not be included in our outputs
        ## Filter commute tours

        # Adding WFH variable - these will not have a work county or taz
        logging.info("Adding WFH variable to work location data")
        work_location['WFH'] = np.where(work_location['WorkSegment'] == 99999, 1, 0)

        # Filtering tours to only tours with commutes
        # TODO: Determine which id to merge on
        logging.info("Filtering tours to only tours with commutes")
        commute_tours = tours[tours['tour_purpose']== 'Work']
        commute_tours = commute_tours[['hh_id', 'tour_participants', 'person_id','tour_purpose','tour_mode']]
        commute_tours['person_num'] = commute_tours['tour_participants'].astype(int)
        logging.debug(f"Commute tours: \n{commute_tours.head()}")

        #Merging tour mode from commute tour 
        logging.info("Adding tour mode to work location data")
        work_location = work_location.merge(right = commute_tours[['person_num', 'person_id', 'tour_mode']], how = 'left',
                                            left_on = 'PersonID', right_on = 'person_id', validate= 'one_to_many')
        logging.debug(work_location.head())
        
        # Fill in missing values for all merges 
        work_location.fillna(0, inplace = True)

        return work_location
 
    def _add_household_variables(self, households: pd.DataFrame) -> pd.DataFrame:
        """
        Add derived variables to households data.
        This includes income quartiles, auto sufficiency, walk subzone
        
        """
        # Income quartiles
        logging.info("Adding income quartile to households data")
        logging.warning("There are {0} households with negative income".format((households['income'] < 0).sum()))
        households['incQ'] = pd.cut(households['income'], 
                                   bins=pd.concat([self.config.income_quartiles['cutoffs'],pd.Series(np.inf)], ignore_index=True),
                                   labels=self.config.income_quartiles['segment_suffixes'], include_lowest=True)
        
        logging.warning("There are {0} households with missing income quartile".format(households['incQ'].isna().sum()))
        #households = households.merge(self.config.income_quartiles, on='incQ', how='left')
        
        # Workers (capped at 4)
        # TODO: Do we need to do this?
        households['workers'] = np.minimum(households['workers'], 4)
        
        # Auto sufficiency
        households['autoSuff'] = np.where(households['autos'] == 0, 0,
                                 np.where(households['autos'] < households['NWRKRS_ESR'], 1, 2))
        households = households.merge(self.config.autosuff, on='autoSuff', how='left', validate = 'many_to_one')
        
        logging.info("Added household variables: income quartile, auto sufficiency")
        logging.debug(households.head())
        
        return households

    ## TODO: Revise this
    

    # TODO: This still needs to be revised        
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
    
    def _get_joint_persons_trips(self, joint_trips: pd.DataFrame, persons: pd.DataFrame) -> pd.DataFrame:
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
        joint_tour_persons = pd.merge(participants, persons[['hh_id', 'person_num', 'person_id']], on=['hh_id', 'person_num'], how='left', validate = 'many_to_one')

        logging.info(f"Combined joint tours and persons; have {len(joint_tour_persons):,} rows")
        logging.debug(joint_tour_persons.head())

        logging.debug("Attaching person to joint trips")
        # This is a many to many inner join since we are unwinding joint trips by persons on the trip. Each joint trip becomes a row per participant
        joint_persons_trips = pd.merge(joint_trips, joint_tour_persons, on= ['hh_id', 'tour_id'], how = 'inner', indicator= True, validate = 'many_to_many')

        logging.debug(('Created joint_person_trips with {0} rows from {1} rows from joint trips {2} rows from joint_tour_persons')
              .format(len(joint_persons_trips), len(joint_trips), len(joint_tour_persons))
              )

        return joint_persons_trips 
    
    def _read_tours(self, IndivJoint: str) -> pd.DataFrame:
        """Read and process tour data.
        Arguments:
        - households: DataFrame of households to join with tours
        - persons: DataFrame of persons to join with tours
        - IndivJoint: 'Indiv' or 'Joint' to specify tour type
        """

        # Read input file

        tour_file = self.config.updated_dir/f"{IndivJoint}TourData_{self.config.iter}.parquet"
        if tour_file.exists():
            logging.info(f"Reading tour file from {tour_file}")
            tour = pd.read_parquet(tour_file)
        else:
            logging.warning("The updated tour file with skims attached does not exist. Reading original output file")
            tour_file = self.config.main_dir / f"{IndivJoint}TourData_{self.config.iter}.csv"
            tour = pd.read_csv(tour_file)


        # Drop probability and util columns
        tour.drop(list(tour.filter(regex='util|prob')), axis = 1, inplace = True)

        # Add income and percent of poverty from households
        ## TODO: Add in percent of poverty calculation for households

        # TODO: Merge on MAZ for this - this is at a MAZ level (mgra_dest instead of dest_taz)
        # TODO: Add parking back in later
        # Add in Land Use Info for the Tour Destination
        # TODO: Unclear about the landuse input file since there's two - for now, merge on household which also has these fields
        # Since dest_mgra is based on sequential MAZ numbering,
        #tour = tour.merge(households[['MAZ', 'TAZ', 'ORIG_MAZ', 'ORIG_TAZ','CountyID', 'DistID']], left_on='dest_mgra', right_on='MAZ', how='left', suffixes= (None, "_dest"))

        
        if IndivJoint == 'Indiv':
            tour['num_participants'] = 1
            tour['tour_participants'] = tour['person_num'].astype(str)
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
 

        logging.debug(f"Read {len(tour):,} rows from {tour_file}")
        logging.debug(tour.head())
        return tour
    
    def _read_trips(self, IndivJoint: str) -> pd.DataFrame:
        """Read and process trip data.
        Arguments:
        - tours: DataFrame of tours to join with trips
        - IndivJoint: 'Indiv' or 'Joint' to specify trip type
        """
        # Read input file
        # Read post-processed trips file - if not default to ctramp output but note that there is no skims attached
        trip_file = self.config.updated_dir/f"{IndivJoint}TripData_{self.config.iter}.parquet"
        if trip_file.exists():
            trip = pd.read_parquet(trip_file)
        else:
            logging.warning("The updated trip file with skims attached does not exist. Reading original output file")
            trip_file = self.config.main_dir / f"{IndivJoint}TripData_{self.config.iter}.csv"
            trip = pd.read_csv(trip_file)

        if IndivJoint == 'Indiv':
            trip['num_participants'] = 1
            trip['tour_participants'] = trip['person_num'].astype(str)

        logging.debug(f"Read {len(trip):,} rows from {IndivJoint} trips")
        logging.debug(trip.head())
        return trip
    

class SummaryGenerator:
    """Class for generating various summary reports."""
    
    # TODO: Need to make this run properly
    def __init__(self, config: Config):
        self.config = config

    def generate_active_time_summary(self, trips: pd.DataFrame) -> None:
        """
        Generate active time summary.

        Universe: Trips

        """
        summary = trips.groupby([])

    def generate_activity_pattern_summary(self, persons: pd.DataFrame) -> None:
        """
        Generate activity pattern summary.

        Universe: Persons
        
        Args:
            persons: Dataframe of the processed Persons output data

        Returns:
            Outputs a csv and parquet of the summary
        """
        summary = persons.groupby(['type', 'cdap', 'imf_choice', 
                                   'inmf_choice', 'incQ']).agg({'person_id':'count'}).reset_index()
        
        summary.rename(columns={'person_id': 'freq'}, inplace=True)
        summary['freq'] = summary['freq'] / self.config.sampleshare
        
        # Save results
        output_file = self.config.results_dir / "ActivityPattern.csv"
        summary.to_csv(output_file, index=False)

        summary.to_parquet(self.config.results_dir / "ActivityPattern.parquet")
        
        logging.debug(f"Wrote {len(summary):,} rows of activity_pattern_summary")     
    
    # TODO: Update
    def generate_auto_ownership_summary(self, households: pd.DataFrame) -> None:
        """Generate auto ownership summary."""
        summary = households.groupby([
            'DistID', 'CountyID', 'autos', 'incQ',
            'workers', 'kidsNoDr'
        ]).size().reset_index(name='freq')
        
        summary['freq'] = summary['freq'] / self.config.sampleshare
        
        # Save results
        output_file = self.config.results_dir / "AutomobileOwnership.csv"
        summary.to_csv(output_file, index=False)

        summary.to_parquet(self.config.results_dir / "AutomobileOwnership.parquet")
        
        logging.debug(f"Wrote {len(summary):,} rows of autoown_summary")
    
    def generate_auto_trips_person(self, persons: pd.DataFrame) -> None:
        """
        Generate automobile trips by person's home and work location

        Universe: Persons
        """
        summary = persons.groupby(
            ['CountyID', 'MAZ_NODE']
        )
    
    def generate_cdap_summary(self, persons: pd.DataFrame, group_by: List[str], output_suffix = ""):
        """
        Generate CDAP Summary by different groupings (person type, age, household size/composition, home geography, auto ownership)

        Args:
            persons: Dataframe of the processed persons output data
            group_by: List of columns to group by for the summary
            output_suffix: Suffix to append to the output file name (Optional)
        
        Universe: persons
        """
        summary = persons.groupby(group_by).agg({'hh_id':'count'}).reset_index()
        summary.rename(columns={'hh_id': 'freq'}, inplace=True)
        summary['freq'] = summary['freq'] / self.config.sampleshare

        # Save results
        output_file = self.config.results_dir/f'CDAPSummary{output_suffix}.csv'

        summary.to_csv(output_file, index = False)        
        if output_suffix == "":
            summary.to_parquet(self.config.results_dir / "CDAPSummary.parquet")

    ## TODO: Currently summaries are to a MAZ level - may need to change to TAZ for a more aggregated
    def generate_journey_to_work_summary(self, work_locations: pd.DataFrame) -> None:
        """
        Generate workplace location summaries.

        Universe: Persons with work location
        """

        summary = work_locations.groupby([
            'HOME_CountyID', 'HOME_MAZ_SEQ', 'HOME_MAZ_NODE', 'WorkLocation', 'WORK_CountyID', 'WFH'
        ]).agg({'PersonID': 'count',
                'Income': 'mean'}).reset_index()

        summary.rename(columns = {'PersonID': 'freq'}, inplace = True)
        summary['freq'] = summary['freq'] / self.config.sampleshare

        # Save results
        output_file = self.config.results_dir / "JourneyToWork.csv"
        summary.to_csv(output_file, index = False)
        
        summary.to_parquet(self.config.results_dir / "JourneyToWork.parquet")


    def generate_journey_to_work_mode_summary(self, work_locations: pd.DataFrame) -> None:
        """
        Generate journey to work by mode summary.

        Universe: Persons with work location
        """

        summary = work_locations.groupby([
            'HOME_CountyID', 'HOME_MAZ_SEQ', 'HOME_MAZ_NODE', 'WorkLocation', 'WORK_CountyID', 'WFH', 'tour_mode'
        ]).agg({'PersonID': 'count',
                'Income': 'mean'}).reset_index()

        summary.rename(columns = {'PersonID': 'freq'}, inplace = True)
        summary['freq'] = summary['freq'] / self.config.sampleshare

        # Save results
        output_file = self.config.results_dir / "JourneyToWorkByMode.csv"
        summary.to_csv(output_file, index = False)

        summary.to_parquet(self.config.results_dir / "JourneyToWorkByMode.parquet")
    
    def generate_time_summary(self, tours: pd.DataFrame):
        """
        Generate time summary for tours and number of persons touring at a given hour summary via generate_time_persons_summary function

        Args:
            tours: Dataframe of the processed Tours output data

        Returns:
            Outputs a csv and parquet of the summary with columns:
                - DistID: Superdistrict of residence
                - CountyID: County of residence
                - tour_purpose: one of {'Work', 'School', 'Maintenace', 'Escort', Discretionary', 'Shop', 'Visiting', 'University', 'Work-Based', 'Eating Out'}
                - tour_mode
                - start_period
                - end_period
                - freq (number of tours)
                - num_participants: Number of person participants 
        """

        summary = tours.groupby(['DistID', 'CountyID', 'tour_purpose', 'tour_mode', 'start_period', 'end_period']).agg({
            'tour_id': 'count',
            'num_participants': 'sum'
        }).reset_index()
        summary.rename(columns={'tour_id': 'freq'}, inplace=True)
        summary['freq'] = summary['freq'] / self.config.sampleshare

        # Save results
        output_file = self.config.results_dir / "TimeOfDay.csv"
        summary.to_csv(output_file, index=False)
        summary.to_parquet(self.config.results_dir / "TimeOfDay.parquet")

        # Create number of persons touring at a given hour summary
        self.generate_time_persons_summary(summary)
        


    def generate_time_persons_summary(self, timeofday_summary: pd.DataFrame):
        """
        Generate summary of how many persons are touring at a given hour
        
        Args:
            timeofday_summary: Dataframe of the time of day summary from generate_time_summary function

        Returns:
            Outputs a csv and parquet of the summary with columns:
                - tour_purpose: purpose of the tour
                - persons_touring: Number of persons touring during that time period
                - time_period: Time period (https://bayareametro.github.io/tm2py/output/ctramp/#time-period-codes)
        """
        
        persons_touring = pd.DataFrame(columns=['tour_purpose', 'time_period', 'persons_touring'])

        time_period_range = range(1, 41) # Time periods from 1 to 40 based on the time period codes

        for time_period in time_period_range:
            # Filter for activites active during this time period
            touring_mask = ((timeofday_summary['start_period'] <= time_period) &
                             (timeofday_summary['end_period'] >= time_period))
            touring_at_hour = timeofday_summary[touring_mask]

            # Group by purpose and sum participants
            hour_summary = (touring_at_hour.groupby('tour_purpose')
                            ['num_participants'].sum().reset_index())

            # Add time period column
            hour_summary['time_period'] = time_period
            hour_summary.rename(columns={'num_participants': 'persons_touring'}, inplace=True)

            #Append to results
            persons_touring = pd.concat([persons_touring, hour_summary], ignore_index=True)
        

        # Save results
        output_file = self.config.results_dir / "TimeOfDay_personsTouring.csv"
        persons_touring.to_csv(output_file, index=False)

    
    def generate_trip_distance_summary(self, df: pd.DataFrame):
        """
        Generate trip distance summary

        NOTE: Trips taken by transit do not have a skim distance
        """
        summary = df.groupby(['autoSuff', 'autoSuff_label', 'incQ', 'timeperiod', 'trip_mode', 'tour_purpose']).agg({
            'hh_id': 'count',
            'trip_distance': 'mean'
        })

        summary.rename(columns = {'hh_id':'freq'}, inplace = True)
        summary['freq'] = summary['freq']/self.config.sampleshare

        # Save results
        output_file = self.config.results_dir/'TripDistance'
        summary.to_csv(output_file + '.csv', index = False)
        summary.to_parquet(output_file + '.parquet')

    
    def generate_trip_travel_time_summary(self, df: pd.DataFrame):
        """
        Generate trip travel time summary. Group by income, trip mode, and tour purpose

        Universe: Trips

        Args:
            df (DataFrame): Processed trips dataframe
        """
        summary = df.groupby(['incQ', 'trip_mode', 'tour_purpose']).agg({
            'hh_id': 'count',
            'num_participants': 'sum',
            'trip_time': 'mean'
        })

        summary.rename(columns = {'hh_id': 'freq'}, inplace = True)
        summary['freq'] = summary['freq']/self.config.sampleshare

        # Save results
        output_file = self.config.results_dir/'TripTravelTime.csv'
        summary.to_csv(output_file,index = False)


        

    def generate_trips_tours_summary(
            self,
            df: pd.DataFrame,
            trip_or_tour: str,
            group_by: List[str],
            output_suffix: str,
    ):
        """
        Generate trip or tour summaries with flexible grouping

        NOTE: Trips are done at a person trip level

        Args:
            df: Dataframe to summarize (trips or tours)
            trip_or_tour: String to indicate which universe ('trip' or 'tour')
            group_by: List of column names to groupby
            output_suffix: Suffix for output filename (e.g., 'ByMode', 'ByPurpose')
        
        Returns:
            Summary in CSV and Parquet files

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
        simple_mode_dict = {
            1: 'DA', 2: 'DA', 3: 'HOV2', 4: 'HOV2', 5: 'HOV2', 6: 'HOV3',
            7: 'HOV3', 8: 'HOV3', 9: 'Walk', 10: 'Bike', 11: 'WALKTRAN', 12: 'DRIVETRAN',
            13: 'DRIVETRAN', 14: 'DRIVETRAN', 15: 'TNC', 16: 'TNC', 17: 'SCHBUS'}
        
        df['simple_trip_mode'] = df['trip_mode'].replace(simple_mode_dict)
        df['simple_dest_purpose'] = df['dest_purpose'].replace(dest_purpose_dict)
        logging.debug(df.head())
        summary = df.groupby(['simple_trip_mode', 'simple_dest_purpose']).size().reset_index(name = 'freq')

        summary['freq'] = summary['freq']/self.config.sampleshare
        summary['share'] = (summary['freq'] / summary['freq'].sum())*100

        output_file = self.config.results_dir/f'TripSummarySimpleModePurpose.csv'
        summary.to_csv(output_file, index = False)      

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
        
        summary.to_parquet(self.config.results_dir / "VehicleMilesTraveled.parquet")

        logging.debug(f"Wrote {len(summary):,} rows of vmt_summary")
      


class CoreSummaries:
    """Main class orchestrating the entire core summaries process."""
    
    def __init__(self):
        self.config = Config()
        self.data_reader = DataReader(self.config)
        self.summary_generator = SummaryGenerator(self.config)



    def run_analysis(self):
        """Run the complete core summaries analysis."""
        logging.info("Starting Core Summaries Analysis...")
        
        # Read base data
        landuse = self.data_reader.read_land_use()
       
        households = self.data_reader.read_households(landuse)

        
        persons = self.data_reader.read_persons(households)

        households = self.data_reader.add_kids_no_driver(persons, households)
        
        # Read tour and trip data    
        tours = self.data_reader.combine_tours(households, landuse)
        trips = self.data_reader.combine_trips(persons, households)


        logging.info("Filtering commute tours ...")
        commute_tours =tours[tours['tour_purpose'] == 'Work']


        work_locations = self.data_reader.read_work_school_location(landuse, commute_tours)
  
        # Save processed data
        logging.info("Saving processed data...")
        households.to_parquet(self.config.updated_dir / "households.parquet")
        persons.to_parquet(self.config.updated_dir / "persons.parquet")
        trips.to_parquet(self.config.updated_dir / "trips.parquet")
        tours.to_parquet(self.config.updated_dir / "tours.parquet")
        work_locations.to_parquet(self.config.updated_dir / "work_locations.parquet")
        commute_tours.to_parquet(self.config.updated_dir / "commute_tours.parquet")

        # Generate summaries
        logging.info("Generating summaries...")

        logging.info("Gerenate Activity Pattern summary")
        self.summary_generator.generate_activity_pattern_summary(persons)

        logging.info("Generate Auto Ownership summary")
        self.summary_generator.generate_auto_ownership_summary(households)

        logging.info("Generate CDAP Summaries")
        self.summary_generator.generate_cdap_summary(persons, ['cdap'], "ByShare")
        self.summary_generator.generate_cdap_summary(persons, ['cdap', 'type' ], "ByPersonType")
        self.summary_generator.generate_cdap_summary(persons, ['cdap', 'age'], 'ByAge')
        self.summary_generator.generate_cdap_summary(persons, ['cdap', 'MTCCountyID'], 'ByHomeCounty')
        self.summary_generator.generate_cdap_summary(persons, ['cdap', 'MAZ_NODE'], 'ByMAZ')
        self.summary_generator.generate_cdap_summary(persons, ['cdap','autos'], 'ByAutoOwnership')
        self.summary_generator.generate_cdap_summary(persons,['cdap', 'MTCCountyID','MAZ_NODE', 'autos', 'type', 'age'])

        logging.info("Generate time of day summary")
        self.summary_generator.generate_time_summary(tours) 

        logging.info("Generate trips summary")
        self.summary_generator.generate_trip_summary_survey(trips)
        self.summary_generator.generate_trips_tours_summary(trips, 'trip', ['trip_mode', 'trip_mode_label'], 'ByMode')
        self.summary_generator.generate_trips_tours_summary(trips, 'trip', ['trip_mode', 'trip_mode_label', 'tour_purpose'], 'ByModePurpose')
        self.summary_generator.generate_trips_tours_summary(trips, 'trip', ['tour_purpose'], 'ByPurpose')
        self.summary_generator.generate_trips_tours_summary(trips, 'trip', ['timeperiod','trip_mode_label'], 'ByModeTimePeriod')
        
        logging.info("Generate tours summaries")
        self.summary_generator.generate_trips_tours_summary(tours, 'tour', ['tour_mode', 'tour_mode_label'], 'ByMode')
        self.summary_generator.generate_trips_tours_summary(tours, 'tour', ['tour_mode', 'tour_mode_label', 'tour_purpose'], 'ByModePurpose')
        self.summary_generator.generate_trips_tours_summary(tours, 'tour', ['tour_purpose'], 'ByPurpose')

        logging.info("Generating journey to work summary")
        self.summary_generator.generate_journey_to_work_summary(work_locations)
        self.summary_generator.generate_journey_to_work_mode_summary(work_locations)
        

        
        logging.info("Core Summaries Analysis completed successfully!")


def main():
    """Main execution function."""
    try:
        core_summaries = CoreSummaries()
        core_summaries.run_analysis()
    except Exception as e:
        logging.debug(f"Error running analysis: {e}")
        raise


if __name__ == "__main__":
    main()


