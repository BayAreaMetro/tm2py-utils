"""Methods to handle canonical names for the Acceptance Criteria summaries from a tm2py model run.

This module provides canonical naming conventions and crosswalk mappings between different
data sources used in acceptance criteria validation. It ensures consistent naming across
PeMS, GTFS, census, and model network data.
"""

import logging
import pandas as pd
import pathlib
import pprint
import toml

class Canonical:
    """Manages canonical naming conventions and crosswalk mappings.
    
    This class handles standardization of names and IDs across different data sources,
    including transit agencies, station names, network nodes, and geographic units.
    It loads configuration from TOML files and provides crosswalk mappings.
    
    Attributes:
        canonical_file (str): Path to canonical configuration TOML file.
            Set by: __init__()
        scenario_file (str): Path to scenario TOML file.
            Set by: __init__()
        scenario_dir (pathlib.Path): Parent directory of scenario file.
            Set by: __init__()
        canonical_dict (dict): Configuration loaded from canonical TOML file.
            Set by: _load_configs()
        scenario_dict (dict): Scenario configuration from TOML file.
            Set by: _load_configs()
        canonical_agency_names_dict (dict): Maps agency name variations to canonical names.
            Set by: _make_canonical_agency_names_dict()
        canonical_station_names_dict (dict): Maps station name variations to canonical names by operator.
            Set by: _make_canonical_station_names_dict()
        standard_to_emme_transit_nodes_df (pd.DataFrame): Standard to EMME transit node crosswalk.
            Columns: [model_node_id, emme_node_id]
            Set by: _read_standard_to_emme_transit()
        gtfs_to_tm2_mode_codes_df (pd.DataFrame): GTFS to TM2 mode code mapping.
            Columns: [tm2_mode, tm2_operator, operator, technology]
            Set by: _make_tm2_to_gtfs_mode_crosswalk()
        standard_transit_to_survey_df (pd.DataFrame): Transit survey crosswalk.
            Columns: [survey_route, survey_agency, survey_tech, standard_route_id,
                     standard_line_name, standard_operator, canonical_operator]
            Set by: _read_standard_transit_to_survey_crosswalk()
        simulated_maz_data_df (pd.DataFrame): MAZ-level land use data with county and district IDs.
            Key columns: [MAZ_NODE, MAZ_SEQ, TAZ_NODE, TAZ_SEQ, DistID, CountyName] plus
            land use variables from maz_landuse_file
            Set by: _make_simulated_maz_data()
        taz_to_district_df (pd.DataFrame): TAZ to planning district mapping.
            Columns: [taz, district]
            Set by: _make_taz_district_crosswalk()
        census_2010_to_maz_crosswalk_df (pd.DataFrame): Census block group to MAZ mapping.
            Columns: [maz, blockgroup, maz_share]
            Set by: _make_census_maz_crosswalk()
        pems_to_link_crosswalk_df (pd.DataFrame): PeMS stations to network links.
            Columns: [station_id, A, B]
            Set by: _read_pems_to_link_crosswalk()
        standard_to_emme_node_crosswalk_df (pd.DataFrame): Standard to EMME node mapping.
            Columns: [model_node_id, emme_node_id]
            Set by: _read_standard_to_emme_node_crosswalk()
        
    Constants:
        ALL_DAY_WORD: "daily" - keyword for daily summaries
        WALK_ACCESS_WORD: "Walk" - standard walk access label
        PARK_AND_RIDE_ACCESS_WORD: "Park and Ride" - standard PNR label
        KISS_AND_RIDE_ACCESS_WORD: "Kiss and Ride" - standard KNR label
        BIKE_ACCESS_WORD: "Bike" - standard bike access label
        ALL_VEHICLE_TYPE_WORD: "All Vehicles" - all vehicle types label
        LARGE_TRUCK_VEHICLE_TYPE_WORD: "Large Trucks" - truck category label
        MANAGED_LANE_OFFSET: 10000000 - offset for managed lane link IDs
        transit_technology_abbreviation_dict: Maps codes to technology names
        rail_operators_vector: List of rail operator names
        county_names_list: Nine Bay Area county names
    """
    canonical_dict: dict
    canonical_file: str
    scenario_dict: dict
    scenario_file: str

    census_2010_to_maz_crosswalk_df: pd.DataFrame

    canonical_agency_names_dict = {}
    canonical_station_names_dict = {}

    gtfs_to_tm2_mode_codes_df: pd.DataFrame
    standard_transit_to_survey_df: pd.DataFrame

    standard_to_emme_node_crosswalk_df: pd.DataFrame
    pems_to_link_crosswalk_df: pd.DataFrame
    taz_to_district_df: pd.DataFrame

    ALL_DAY_WORD = "daily"
    WALK_ACCESS_WORD = "Walk"
    PARK_AND_RIDE_ACCESS_WORD = "Park and Ride"
    KISS_AND_RIDE_ACCESS_WORD = "Kiss and Ride"
    BIKE_ACCESS_WORD = "Bike"

    ALL_VEHICLE_TYPE_WORD = "All Vehicles"
    LARGE_TRUCK_VEHICLE_TYPE_WORD = "Large Trucks"

    MANAGED_LANE_OFFSET = 10000000

    transit_technology_abbreviation_dict = {
        "LOC": "Local Bus",
        "EXP": "Express Bus",
        "LTR": "Light Rail",
        "FRY": "Ferry",
        "HVY": "Heavy Rail",
        "COM": "Commuter Rail",
    }

    rail_operators_vector = [
        "BART",
        "Caltrain",
        "ACE",
        "Sonoma-Marin Area Rail Transit",
        "SMART",
    ]

    county_names_list = [
        "San Francisco",
        "San Mateo",
        "Santa Clara",
        "Alameda",
        "Contra Costa",
        "Solano",
        "Napa",
        "Sonoma",
        "Marin",
    ]

    def _load_configs(self):
        """Load configuration from TOML files.
        
        Reads canonical and scenario configuration files specified during initialization.
        
        Returns:
            None
        """
        logging.debug(f"Loading canonical_dict from {self.canonical_file}")
        with open(self.canonical_file, "r", encoding="utf-8") as toml_file:
            self.canonical_dict = toml.load(toml_file)

        logging.debug(f"Loading scenario_dict from {self.scenario_file}")
        with open(self.scenario_file, "r", encoding="utf-8") as toml_file:
            self.scenario_dict = toml.load(toml_file)

        return

    def __init__(
        self, canonical_file: pathlib.Path, scenario_file: pathlib.Path = None, on_board_assign_summary: bool = False
    ) -> None:
        """Initialize the Canonical class with configuration files.
        
        Args:
            canonical_file (pathlib.Path): Path to canonical configuration TOML file containing
                crosswalk file paths and canonical naming conventions
            scenario_file (pathlib.Path, optional): Path to scenario TOML file with model inputs.
                Defaults to None.
            on_board_assign_summary (bool, optional): If True, only loads transit-related
                crosswalks for on-board assignment summaries. Defaults to False.
        
        Returns:
            None
        """
        self.canonical_file = canonical_file
        self.scenario_file = scenario_file
        self.scenario_dir = scenario_file.parent
        logging.info(f"Initialzing Canonical instance with {self.scenario_dir=}")
        self._load_configs()
        self._make_canonical_agency_names_dict()
        self._make_canonical_station_names_dict()
        self._read_standard_to_emme_transit()
        self._make_tm2_to_gtfs_mode_crosswalk()
        self._read_standard_transit_to_survey_crosswalk()
        self._make_simulated_maz_data()

        if not on_board_assign_summary:
            self._make_census_maz_crosswalk()
            self._read_pems_to_link_crosswalk()
            self._read_standard_to_emme_node_crosswalk()

        return

    def _make_simulated_maz_data(self):
        """Load simulated MAZ land use data.
        
        Reads MAZ-level land use file and joins with zone sequencing to create
        simulated_maz_data_df with MAZ attributes including county and district IDs.
        
        Returns:
            None
        """
        in_file = self.scenario_dict["scenario"]["landuse_file"]

        logging.info(f"Reading {self.scenario_dir / in_file}")
        self.simulated_maz_data_df = pd.read_csv(self.scenario_dir / in_file)
        logging.debug(f"self.simulated_maz_data_df.head()\n{self.simulated_maz_data_df.head()}")

        # TODO Note this is here -- this should be updated for 2023 & MAZ/TAZ updates
        node_map_file = self.scenario_dir / "inputs/landuse/mtc_final_network_zone_seq.csv"
        logging.info(f"Reading {node_map_file}")
        node_map_df = pd.read_csv(node_map_file, usecols=["N","MAZSEQ","TAZSEQ"])
        logging.debug(f"node_map_df.head()\n{node_map_df.head()}")

        # map MAZ_ORIGINAL -> MAZSEQ and add that column to self.simulated_maz_data_df
        maz_map_df = node_map_df[["N","MAZSEQ"]].rename(columns={"N": "MAZ_NODE"})
        maz_map_df = maz_map_df.loc[maz_map_df.MAZSEQ > 0]
        maz_map_df.set_index("MAZ_NODE", inplace=True)
        logging.debug(f"maz_map_df.head()\n{maz_map_df.head()}")
        maz_map = maz_map_df["MAZSEQ"].to_dict()
        logging.debug(f"maz_map: {maz_map}")

        # map TAZ_ORIGINAL -> TAZSEQ
        taz_map_df = node_map_df[["N","TAZSEQ"]].rename(columns={"N": "TAZ_NODE"})
        taz_map_df = taz_map_df.loc[taz_map_df.TAZSEQ > 0]
        taz_map_df.set_index("TAZ_NODE", inplace=True)
        logging.debug(f"taz_map_df.head()\n{taz_map_df.head()}")
        taz_map = taz_map_df["TAZSEQ"].to_dict()
        logging.debug(f"taz_map: {taz_map}")

        if "TAZ_ORIGINAL" in self.simulated_maz_data_df.columns:
            self.simulated_maz_data_df.rename(columns={"TAZ_ORIGINAL":"TAZ_NODE", "MAZ_ORIGINAL":"MAZ_NODE"}, inplace=True)
        self.simulated_maz_data_df["MAZ_SEQ"] = self.simulated_maz_data_df["MAZ_NODE"].map(maz_map)
        self.simulated_maz_data_df["TAZ_SEQ"] = self.simulated_maz_data_df["TAZ_NODE"].map(taz_map)
        logging.debug(f"self.simulated_maz_data_df:\n{self.simulated_maz_data_df}")

        self._make_taz_district_crosswalk()

        return
        
    def _make_taz_district_crosswalk(self):
        """Create TAZ to planning district crosswalk.
        
        Extracts unique TAZ to district mappings from MAZ data for use in
        district-level summaries. Districts are numbered 1-34 in the MTC region.
        
        Returns:
            None
        """

        df = self.simulated_maz_data_df[["TAZ_NODE", "TAZ_SEQ", "DistID"]].copy()
        df = df.rename(columns={"DistID": "district"})
        self.taz_to_district_df = df.drop_duplicates().reset_index(drop=True)
        logging.debug(f"self.taz_to_district_df:\n{self.taz_to_district_df}")

        return
        
    def _make_canonical_agency_names_dict(self):
        """Create dictionary mapping agency name variations to canonical names.
        
        Reads agency names CSV file and builds a dictionary that maps all variations
        (canonical_name, alternate_01 through alternate_05) to the canonical name.
        
        Returns:
            None
        """
        file_root = pathlib.Path(self.canonical_dict["remote_io"]["crosswalk_folder_root"])
        in_file = self.canonical_dict["crosswalks"]["canonical_agency_names_file"]

        # if not absolute, assume file_root is relative to self.scenario_dir
        if not file_root.is_absolute():
            file_root = self.scenario_dir / file_root

        logging.info(f"Reading {file_root / in_file}")
        df = pd.read_csv(file_root / in_file)
        # columns: canonical_name, alternative_01, alternative_02, etc.
        # transform to dictionary with { alternative -> canonical_name }
        logging.debug(f"Read:\n{df}")

        # start out with just canonical_name:canonical_name
        self.canonical_agency_names_dict = {name:name for name in df['canonical_name'].unique()}
        # add alternates
        for colname in df.columns:
            if not colname.startswith("alternate_"): continue

            alt_names_df = df[["canonical_name",colname]]
            alt_names_df = alt_names_df.loc[ alt_names_df[colname].notna() ]
            alt_names_df.set_index(colname, inplace=True)

            # update the dictionary with alternative -> canonical_name
            self.canonical_agency_names_dict.update(alt_names_df["canonical_name"].to_dict())
        logging.debug(f"self.canonical_agency_names_dict:\n{pprint.pformat(self.canonical_agency_names_dict)}")

        return

    def _make_canonical_station_names_dict(self):
        """Create nested dictionary mapping station name variations to canonical names.
        
        Reads station names CSV file and builds a nested dictionary where the outer key
        is the operator name and inner dictionary maps all station name variations to
        canonical station names.
        
        Returns:
            None
        """
        file_root = pathlib.Path(self.canonical_dict["remote_io"]["crosswalk_folder_root"])
        in_file = self.canonical_dict["crosswalks"]["canonical_station_names_file"]

        # if not absolute, assume file_root is relative to self.scenario_dir
        if not file_root.is_absolute():
            file_root = self.scenario_dir / file_root

        logging.info(f"Reading {file_root / in_file}")
        df = pd.read_csv(file_root / in_file)
        # columns: operator, canonical, alternative_01, alternative_02, etc.
        # transform to dictionary with { operator -> { alternative -> canonical }}
        logging.debug(f"Read:\n{df}")

        self.canonical_station_names_dict = {}
        for operator in df["operator"].unique():
            operator_df = df[df["operator"] == operator]
            # start out with just canonical:canonical
            self.canonical_station_names_dict[operator] =  {name:name for name in operator_df['canonical'].unique()}

            for colname in operator_df.columns:
                if not colname.startswith("alternate_"): continue

                alt_names_df = operator_df[["canonical",colname]]
                alt_names_df = alt_names_df.loc[ alt_names_df[colname].notna() ]
                alt_names_df.set_index(colname, inplace=True)

                # update the dictionary with alternative -> canonical_name
                self.canonical_station_names_dict[operator].update(alt_names_df["canonical"].to_dict())
           
        logging.debug(f"self.canonical_station_names_dict:\n{pprint.pformat(self.canonical_station_names_dict)}")

        return

    def _make_census_maz_crosswalk(self):
        """Load census block group to MAZ crosswalk.
        
        Downloads/reads CSV mapping census block groups to model MAZs with share allocations.
        
        Returns:
            None
        """
        url_string = self.canonical_dict["crosswalks"]["block_group_to_maz_url"]
        logging.info(f"Reading {url_string}")

        # TODO: This is out of date with updated MAZ/TAZ and will need to be fixed
        self.census_2010_to_maz_crosswalk_df = pd.read_csv(url_string)
        self.census_2010_to_maz_crosswalk_df.rename(columns={"maz":"MAZ_NODE"},inplace=True)

        # TODO: blockgroup should be 12 chracters
        self.census_2010_to_maz_crosswalk_df['blockgroup'] = self.census_2010_to_maz_crosswalk_df['blockgroup'].astype(str).str.zfill(12) 
        logging.debug(f"self.census_2010_to_maz_crosswalk_df:\n{self.census_2010_to_maz_crosswalk_df}")

        # note: neither blockgroup nor MAZ_NODE are unique
        dupe_maz_node = self.census_2010_to_maz_crosswalk_df.loc[ self.census_2010_to_maz_crosswalk_df['MAZ_NODE'] != 0 ].copy()
        dupe_maz_node = dupe_maz_node.loc[ dupe_maz_node['MAZ_NODE'].duplicated(keep=False) ]
        logging.debug(f"dupe_maz_node:\n{dupe_maz_node}")
        return

    def _read_standard_to_emme_transit(self):
        """Read standard to EMME transit node crosswalk.
        
        Loads mapping between standard network node IDs and EMME node IDs for transit stops.
        
        Returns:
            None
        """
        # file_root = pathlib.Path(self.canonical_dict["remote_io"]["crosswalk_folder_root"])
        # TODO: handle this better; this doesn't belong in acceptance/crosswalk
        file_root = self.scenario_dir / "emme_project" / "Database_transit"
        in_file = self.canonical_dict["crosswalks"]["standard_to_emme_transit_file"]

        # if not absolute, assume file_root is relative to self.scenario_dir
        if not file_root.is_absolute():
            file_root = self.scenario_dir / file_root

        logging.info(f"Reading {file_root / in_file}")
        self.standard_to_emme_transit_nodes_df = pd.read_csv(file_root / in_file)
        return

    def _make_tm2_to_gtfs_mode_crosswalk(self):
        """Create TM2 mode to GTFS agency/technology crosswalk.
        
        Reads mode mapping file to link TM2 mode codes with GTFS agencies and technologies.
        Creates gtfs_to_tm2_mode_codes_df with columns: [tm2_mode, tm2_operator, operator, technology]
        
        Returns:
            None
        """
        file_root = pathlib.Path(self.canonical_dict["remote_io"]["crosswalk_folder_root"])
        in_file = self.canonical_dict["crosswalks"]["standard_to_tm2_modes_file"]

        # if not absolute, assume file_root is relative to self.scenario_dir
        if not file_root.is_absolute():
            file_root = self.scenario_dir / file_root

        logging.info(f"Reading {file_root / in_file}")
        self.gtfs_to_tm2_mode_codes_df = pd.read_csv(file_root / in_file)
        logging.debug(f"Read:\n{self.gtfs_to_tm2_mode_codes_df}")
        # columns are
        #   agency_raw_name, agency_name, agency_id, TM2_operator, route_type, TM2_mode, TM2_line_haul_name, TM2_faresystem, 
        #   is_express_bus, VEHTYPE

        self.gtfs_to_tm2_mode_codes_df = self.gtfs_to_tm2_mode_codes_df[["TM2_mode", "TM2_operator", "agency_name", "TM2_line_haul_name"]]
        self.gtfs_to_tm2_mode_codes_df.rename(
            columns={
                "TM2_mode": "tm2_mode",
                "TM2_operator": "tm2_operator",
                "agency_name": "operator",
                "TM2_line_haul_name": "technology",
            },
            inplace=True
        )
        logging.debug(f"self.gtfs_to_tm2_mode_codes_df:\n{self.gtfs_to_tm2_mode_codes_df}")

        return

    def _read_standard_transit_to_survey_crosswalk(self):
        """Read crosswalk between standard transit network and survey data.
        
        Loads mapping that links transit survey routes to standard network routes,
        including operator names, route IDs, and technology types.
        
        Returns:
            None
        """
        file_root = pathlib.Path(self.canonical_dict["remote_io"]["crosswalk_folder_root"])
        in_file = self.canonical_dict["crosswalks"]["crosswalk_standard_survey_file"]

        # if not absolute, assume file_root is relative to self.scenario_dir
        if not file_root.is_absolute():
            file_root = self.scenario_dir / file_root

        logging.info(f"Reading {file_root / in_file}")
        self.standard_transit_to_survey_df = pd.read_csv(file_root / in_file)
        self.standard_transit_to_survey_df = self.standard_transit_to_survey_df[[
            "survey_route",
            "survey_agency",
            "survey_tech",
            "standard_route_id",
            "standard_line_name",
            "standard_operator",
            "standard_headsign",
            "standard_agency",
            "standard_route_short_name",
            "standard_route_long_name",
            "canonical_operator",
        ]].drop_duplicates()

        logging.debug(f"self.standard_transit_to_survey_df:\n{self.standard_transit_to_survey_df}")

        return

    def aggregate_line_names_across_time_of_day(
        self, input_df: pd.DataFrame, input_column_name: str
    ) -> pd.DataFrame:
        """Extract daily line name from time-specific line names.
        
        Parses line names like "Mode_Operator_Route_TimePeriod" to extract
        "Mode_Operator_Route" as the daily line name.
        
        Args:
            input_df (pd.DataFrame): DataFrame containing line names
            input_column_name (str): Column with time-specific line names
        
        Returns:
            pd.DataFrame: Input DataFrame with added 'daily_line_name' column
        """
        df = input_df[input_column_name].str.split(pat="_", expand=True).copy()
        df["daily_line_name"] = df[0] + "_" + df[1] + "_" + df[2]
        return_df = pd.concat([input_df, df["daily_line_name"]], axis="columns")

        return return_df

    def _read_pems_to_link_crosswalk(self) -> None:
        """Read PeMS station to network link crosswalk.

        Loads mapping of PeMS traffic count stations to model network links.
        Creates station_id as combination of station number and direction.

        Returns:
            None
        """
        file_root = pathlib.Path(self.canonical_dict["remote_io"]["crosswalk_folder_root"])
        in_file = self.canonical_dict["crosswalks"]["pems_station_to_tm2_links_file"]

        # if not absolute, assume file_root is relative to self.scenario_dir
        if not file_root.is_absolute():
            file_root = self.scenario_dir / file_root
    
        logging.info(f"Reading {file_root / in_file}")
        self.pems_to_link_crosswalk_df = pd.read_csv(file_root / in_file)
        self.pems_to_link_crosswalk_df["station_id"] = self.pems_to_link_crosswalk_df["station"].astype(str) + \
            "_" + self.pems_to_link_crosswalk_df["direction"]
        self.pems_to_link_crosswalk_df = self.pems_to_link_crosswalk_df[["station_id", "A", "B"]]

        logging.debug(f"self.pems_to_link_crosswalk_df:\n{self.pems_to_link_crosswalk_df}")

        return

    def _read_standard_to_emme_node_crosswalk(self) -> None:
        """Read standard to EMME roadway node crosswalk.

        Loads mapping between standard network node IDs and EMME node IDs for roadway network.

        Returns:
            None
        """
        # file_root = self.canonical_dict["remote_io"]["crosswalk_folder_root"]
        # TODO: handle this better; this doesn't belong in acceptance/crosswalk
        file_root = self.scenario_dir / "emme_project" / "Database_highway"
        in_file = self.canonical_dict["crosswalks"]["standard_to_emme_nodes_file"]

        logging.info(f"Reading {file_root / in_file}")
        self.standard_to_emme_node_crosswalk_df = pd.read_csv(file_root / in_file)

        logging.debug(f"self.standard_to_emme_node_crosswalk_df:\n{self.standard_to_emme_node_crosswalk_df}")

        return
