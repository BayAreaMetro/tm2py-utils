"""Methods to handle simulation results for the Acceptance Criteria summaries from a tm2py model run.

This module processes simulated model outputs from tm2py runs including roadway assignments,
transit boardings, home-work flows, and accessibility metrics. It reads model outputs from
various sources (OMX matrices, shapefiles, CSV files) and prepares them for comparison with
observed data.
"""

from tm2py_utils.summary.acceptance.canonical import Canonical

import logging
import numpy as np
import time
import geopandas as gpd
import itertools

import openmatrix as omx
import pandas as pd
import pathlib
import polars as pl
import pprint
import toml


class Simulated:
    """Manages simulated model outputs for acceptance criteria validation.
    
    This class processes tm2py model outputs including roadway volumes, transit boardings,
    travel patterns, and demographic distributions. It reads outputs from various model
    components and standardizes them for comparison with observed data.
    
    Attributes:
        canonical (Canonical): Canonical naming and crosswalk handler
        scenario_dict (dict): Scenario configuration from TOML
        model_dict (dict): Model configuration from TOML
        scenario_file (str): Path to scenario configuration file
        model_file (str): Path to model configuration file
        model_time_periods (list): Time periods in model (e.g., ['ea', 'am', 'md', 'pm', 'ev'])
        model_morning_capacity_factor (float): AM peak capacity adjustment factor
        
        Roadway Data:
        roadway_am_shape_gdf (gpd.GeoDataFrame): AM roadway network geometry:
            - emme_a_node_id, emme_b_node_id: Network nodes
            - standard_link_id: Link identifier
            - geometry: Link shape
            
        roadway_assignment_results_df (pd.DataFrame): Link volumes by time:
            - emme_a_node_id, emme_b_node_id: Network nodes
            - standard_link_id: Link identifier
            - time_period: Time period
            - flow_da, flow_s2, flow_s3: Auto volumes by occupancy
            - flow_lrgt, flow_trk: Truck volumes by class
            - flow_total: Total volume
            - m_flow_*: Managed lane volumes
            - capacity, lanes: Link attributes
            - speed_mph: Congested speed
            - ft: Facility type
            
        Transit Data:
        boardings_df (pd.DataFrame): Route-level boardings:
            - line_name: Transit line identifier
            - daily_line_name: Daily aggregated line
            - operator: Transit agency
            - technology: Mode type
            - time_period: Time period
            - total_boarding: Total boardings
            - total_hour_cap: Hourly capacity
            
        transit_segments_gdf (gpd.GeoDataFrame): Segment-level transit:
            - LINE_ID: Line identifier
            - INODE, JNODE: Segment nodes
            - board: Segment boardings
            - am_segment_volume: Passenger volume
            - am_segment_capacity_total/seated: Capacity
            - am_segment_vc_ratio_total/seated: V/C ratios
            - geometry: Segment shape
            
        transit_access_df (pd.DataFrame): Rail station access:
            - operator: Rail operator
            - boarding: Station node
            - boarding_name: Station name
            - access_mode: Access mode (Walk, Park and Ride, etc.)
            - simulated_boardings: Boardings by access mode
            - time_period: Time period
            
        station_to_station_df (pd.DataFrame): Station OD flows:
            - operator: Transit operator
            - boarding_name, alighting_name: Station names
            - simulated: Passenger flow
            
        Home-Work & Demographics:
        home_work_flows_df (pd.DataFrame): County commute flows:
            - residence_county: Home county
            - work_county: Work county
            - simulated_flow: Number of workers
            
        zero_vehicle_hhs_df (pd.DataFrame): Zero-vehicle households by MAZ:
            - maz: Model zone ID
            - simulated_zero_vehicle_share: Share with no vehicles
            - simulated_households: Total households
            
        reduced_zero_vehicle_hhs_df (pd.DataFrame): By census tract:
            - tract: Census tract ID
            - simulated_zero_vehicle_share: Tract-level share
            - simulated_households: Total households
            
        Bridge Data:
        bridge_details_df (pd.DataFrame): Bridge toll links:
            - plaza_name: Bridge name
            - direction: Travel direction
            - standard_link_id: Link ID
            - pay_toll: Boolean for toll collection direction
    
    Constants:
        network_shapefile_names_dict: Maps time periods to EMME scenario names
        transit_access_mode_dict: Maps mode codes to access mode names
        transit_mode_dict: Maps mode IDs to mode descriptions
    """
    canonical: Canonical

    scenario_dict: dict
    model_dict: dict

    scenario_file: pathlib.Path
    # the model run directory
    scenario_dir: pathlib.Path
    model_file: pathlib.Path

    # list of strings which are names from self.model_dict['time_periods']
    model_time_periods = []
    model_morning_capacity_factor: float

    roadway_am_shape_gdf: gpd.GeoDataFrame

    roadway_assignment_results_df = pd.DataFrame

    transit_access_mode_dict = {}
    transit_mode_dict = {}


    boardings_df: pd.DataFrame
    home_work_flows_df: pd.DataFrame
    simulated_maz_data_df: pd.DataFrame
    transit_segments_gdf: gpd.GeoDataFrame
    transit_access_df: pd.DataFrame
    zero_vehicle_hhs_df: pd.DataFrame
    reduced_zero_vehicle_hhs_df: pd.DataFrame
    station_to_station_df: pd.DataFrame
    transit_demand_df: pd.DataFrame
    transit_tech_in_vehicle_times_df: pd.DataFrame
    transit_district_to_district_by_tech_df: pd.DataFrame
    transit_district_to_district_by_tech_pldf: pl.DataFrame
    am_segment_boardings_df: pd.DataFrame

    HEAVY_RAIL_NETWORK_MODE_DESCR: str
    COMMUTER_RAIL_NETWORK_MODE_DESCR: str

    standard_transit_stops_df: pd.DataFrame
    standard_transit_shapes_df: pd.DataFrame
    standard_transit_routes_df: pd.DataFrame
    standard_nodes_gdf: gpd.GeoDataFrame
    standard_to_emme_transit_nodes_df: pd.DataFrame

    bridge_details_df = pd.DataFrame(
        [
            ["Bay Bridge", "WB", 3082623, True],
            ["Bay Bridge", "EB", 3055540, False],
            ["San Mateo Bridge", "WB", 1034262, True],
            ["San Mateo Bridge", "EB", 3164437, False],
            ["Dumbarton Bridge", "WB", 3098698, True],
            ["Dumbarton Bridge", "EB", 3133722, False],
            ["Richmond Bridge", "WB", 4062186, True],
            ["Richmond Bridge", "EB", 4074386, False],
            ["Carquinez Bridge", "WB", 5051527, False],
            ["Carquinez Bridge", "EB", 5051375, True],
            ["Benicia Bridge", "SB", 4074831, False],
            ["Benicia Bridge", "NB", 5004246, True],
            ["Antioch Bridge", "SB", 26067351, False],
            ["Antioch Bridge", "NB", 26067350, True],
        ],
        columns=["plaza_name", "direction", "standard_link_id", "pay_toll"],
    )

    network_shapefile_names_dict = {
        "ea": "Scenario_11",
        "am": "Scenario_12",
        "md": "Scenario_13",
        "pm": "Scenario_14",
        "ev": "Scenario_15",
    }

    def _load_configs(self, scenario: bool = True, model: bool = True):
        """Load scenario and/or model configuration files.

        Reads TOML configuration files for scenario and model settings. Stores
        configurations in instance variables scenario_dict and model_dict.

        Args:
            scenario (bool, optional): If True, load scenario config. Defaults to True.
            model (bool, optional): If True, load model config. Defaults to True.

        Returns:
            None
        """
        if scenario:
            with open(self.scenario_file, "r", encoding="utf-8") as toml_file:
                self.scenario_dict = toml.load(toml_file)

        if model:
            with open(self.model_file, "r", encoding="utf-8") as toml_file:
                self.model_dict = toml.load(toml_file)

        return

    def _get_model_time_periods(self):
        """Extract time period names from model configuration.

        Populates model_time_periods list with time period names (e.g., 'ea', 'am',
        'md', 'pm', 'ev') from model configuration dictionary.

        Returns:
            None
        """
        if not self.model_time_periods:
            # this is a list of dictionaries
            for time_dict in self.model_dict["time_periods"]:
                self.model_time_periods.append(time_dict["name"])
        logging.debug(f"self.model_time_periods:{self.model_time_periods}")
        return

    def _get_morning_commute_capacity_factor(self):
        """Get AM period highway capacity factor from model configuration.

        Extracts the highway capacity factor for the AM time period, used for
        scaling transit vehicle capacities in the morning peak period.

        Returns:
            None
        """
        for time_dict in self.model_dict["time_periods"]:
            if time_dict["name"] == "am":
                self.model_morning_capacity_factor = time_dict[
                    "highway_capacity_factor"
                ]

        return

    def __init__(
        self,
        canonical: Canonical,
        scenario_file: pathlib.Path = None,
        model_file: pathlib.Path = None,
        on_board_assign_summary: bool = False,
        iteration: int = 3,
    ) -> None:
        """Initialize Simulated data handler.
        
        Args:
            canonical (Canonical): Canonical naming and crosswalk handler instance
            scenario_file (pathlib.Path, optional): Path to scenario TOML configuration.
                Defaults to None.
            model_file (pathlib.Path, optional): Path to model TOML configuration.
                Defaults to None.
            on_board_assign_summary (bool, optional): If True, only loads transit
                boardings for on-board assignment validation. Defaults to False.
            iteration (int, optional): Model iteration number to read (for iterative
                assignment outputs). Defaults to 3.
        
        Returns:
            None
        """
        self.canonical = canonical
        self.scenario_file = scenario_file
        self.scenario_dir = scenario_file.parent
        self.iter = iteration
        logging.info(f"Initializing Simulated instance with {self.scenario_file=} {self.iter=}")

        self._load_configs(scenario=True, model=False)

        # TODO: why is on_board_assign_summary an option?  This seems like it does nothing?
        if not on_board_assign_summary:
            self.model_file = model_file
            self._load_configs()
            self._get_model_time_periods()
            self._get_morning_commute_capacity_factor()
            self._validate()

    def reduce_on_board_assignment_boardings(self, time_period_list: list = ["am"]):
        """Process transit boardings for on-board assignment validation.
        
        Simplified method that only processes transit boarding data when validating
        on-board survey assignments.
        
        Args:
            time_period_list (list, optional): Time periods to process.
                Defaults to ["am"].
        
        Returns:
            None
        """
        self.model_time_periods = time_period_list
        self._reduce_simulated_transit_boardings()

        return

    def _validate(self):
        """Prepare and validate all simulated model outputs.

        Orchestrates the loading and processing of all simulated data outputs including
        transit demand, roadway volumes, demographics, and accessibility metrics. Despite
        the name, this method primarily prepares simulation data rather than validates it.

        Processes:
        - Transit mode dictionaries and network stops/routes/shapes
        - Transit demand matrices (pandas and polars versions)
        - Transit technology in-vehicle times from skims
        - District-to-district transit summaries
        - Transit segments, boardings, and access summaries
        - Home-work flows and zero-vehicle households
        - Station-to-station flows
        - Roadway assignment volumes and speeds

        Returns:
            None

        #TODO: I don't think of these things as "validation"; this is just preparing simulation data...
        """
        self._make_transit_mode_dict()
        self._read_standard_transit_stops()
        self._read_standard_transit_shapes()
        self._read_standard_transit_routes()
        self._read_standard_node()

        # these methods uses polars
        self._read_transit_demand()
        # TODO: long-term: do this in tm2py postprocessing
        self._make_transit_technology_in_vehicle_table_from_skims()
        self._make_district_to_district_transit_summaries()

        self._reduce_simulated_transit_by_segment()
        self._reduce_simulated_transit_boardings()
        self._reduce_simulated_transit_shapes()
        self._reduce_simulated_home_work_flows()
        self._reduce_simulated_zero_vehicle_households()
        self._reduce_simulated_station_to_station()
        self._reduce_simulated_rail_access_summaries()

        assert sorted(
            self.home_work_flows_df.residence_county.unique().tolist()
        ) == sorted(self.canonical.county_names_list)
        assert sorted(
            self.home_work_flows_df.work_county.unique().tolist()
        ) == sorted(self.canonical.county_names_list)

        # requires emme_links.py from post_process.py
        self._reduce_simulated_roadway_assignment_outcomes()

        return

    def _reduce_simulated_transit_by_segment(self):
        """Process AM transit segment boardings.

        Reads transit segment data for AM period, extracts segment-level boarding
        counts, and parses line names to get line IDs and node pairs. Excludes
        park-and-ride dummy routes.

        Results stored in am_segment_boardings_df with columns:
            - LINE_ID: Transit line identifier
            - line: Full line name
            - INODE, JNODE: Segment node pair
            - board: Segment boardings

        Returns:
            None
        """
        file_prefix = "transit_segment_"
        time_period = "am"  # am only

        in_file = self.scenario_dir / f"output_summaries/transit_segment_{time_period}.csv"
        logging.info(f"Reading {in_file}")
        df = pd.read_csv(in_file, low_memory=False)
        logging.debug(f"df:\n{df}")

        a_df = df[~(df["line"].str.contains("pnr_"))].reset_index().copy()

        # remove nodes from line name and add node fields
        a_df["line_long"] = df["line"].copy()
        temp = a_df["line_long"].str.split(pat="-", expand=True)
        a_df["LINE_ID"] = temp[0]
        a_df = a_df.rename(columns={"i_node": "INODE", "j_node": "JNODE"})
        a_df = a_df[~(a_df["JNODE"] == "None")].reset_index().copy()
        a_df["JNODE"] = a_df["JNODE"].astype("float").astype("Int64")
        df = a_df[["LINE_ID", "line", "INODE", "JNODE", "board"]]

        self.am_segment_boardings_df = df

    def _get_operator_name_from_line_name(
        self, input_df: pd.DataFrame, input_column_name: str, output_column_name: str
    ) -> pd.DataFrame:
        """Extract operator name from transit line name.

        Parses line names to extract operator code (second element when split by
        underscore). Adds operator name as new column to input DataFrame.

        Args:
            input_df (pd.DataFrame): Input DataFrame with line names
            input_column_name (str): Name of column containing line names
            output_column_name (str): Name for output operator column

        Returns:
            pd.DataFrame: Input DataFrame with added operator column
        """
        df = input_df[input_column_name].str.split(pat="_", expand=True).copy()
        df[output_column_name] = df[1]
        return_df = pd.concat([input_df, df[output_column_name]], axis="columns")

        return return_df

    def _reduce_simulated_transit_shapes(self):
        """Process AM transit segment shapes with volumes and V/C ratios.

        Reads transit segment GeoJSON, joins with boarding data, calculates segment
        volumes, capacities, and volume-to-capacity ratios. Computes mean V/C by line.
        Excludes park-and-ride dummy routes from capacity calculations.

        Results stored in transit_segments_gdf (GeoDataFrame) with columns documented
        in class docstring.

        Returns:
            None
        """
        time_period = "am"  # am only

        in_file = self.scenario_dir / f"output_summaries/boardings_by_segment_{time_period}.geojson"
        logging.info(f"Reading {in_file}")
        gdf = gpd.read_file(in_file)
        logging.debug(f"gdf:\n{gdf}")

        gdf["first_row_in_line"] = gdf.groupby("LINE_ID").cumcount() == 0

        df = pd.DataFrame(gdf.drop(columns=["geometry"]))

        # Add am boards
        a_df = self.am_segment_boardings_df

        df = pd.merge(df, a_df, how="left", on=["LINE_ID", "INODE", "JNODE"])

        # Compute v/c ratio, excluding pnr dummy routes
        a_df = df[~(df["LINE_ID"].str.contains("pnr_"))].reset_index().copy()
        a_df["am_segment_capacity_total"] = (
            a_df["capt"] * self.model_morning_capacity_factor
        )
        a_df["am_segment_capacity_seated"] = (
            a_df["caps"] * self.model_morning_capacity_factor
        )
        a_df["am_segment_vc_ratio_total"] = (
            a_df["VOLTR"] / a_df["am_segment_capacity_total"]
        )
        a_df["am_segment_vc_ratio_seated"] = (
            a_df["VOLTR"] / a_df["am_segment_capacity_seated"]
        )
        a_df = a_df.rename(columns={"VOLTR": "am_segment_volume"})

        sum_df = (
            a_df.groupby(["LINE_ID"])
            .agg({"am_segment_vc_ratio_total": "mean"})
            .reset_index()
        )
        sum_df.columns = [
            "LINE_ID",
            "mean_am_segment_vc_ratio_total",
        ]

        a_gdf = pd.merge(
            gdf,
            sum_df,
            on="LINE_ID",
            how="left",
        )
        logging.debug(a_gdf.head())
        logging.debug(a_gdf.columns)


        self.transit_segments_gdf = pd.merge(
            a_gdf,
            a_df[
                [
                    "LINE_ID",
                    "INODE",
                    "JNODE",
                    "am_segment_volume",
                    "am_segment_capacity_total",
                    "am_segment_capacity_seated",
                    "am_segment_vc_ratio_total",
                    "am_segment_vc_ratio_seated",
                    "board",
                ]
            ],
            on=["LINE_ID", "INODE", "JNODE"],
            how="left",
        )

        return

    def _join_coordinates_to_stations(self, input_df, input_column_name):
        station_list = input_df[input_column_name].unique().tolist()

        x_df = self.canonical.standard_to_emme_transit_nodes_df.copy()
        n_gdf = self.standard_nodes_gdf.copy()

        df = x_df[x_df["emme_node_id"].isin(station_list)].copy().reset_index(drop=True)
        n_trim_df = n_gdf[["model_node_id", "X", "Y"]].copy()
        df = pd.merge(df, n_trim_df, how="left", on="model_node_id")
        df = (
            df[["emme_node_id", "X", "Y"]]
            .copy()
            .rename(
                columns={
                    "emme_node_id": input_column_name,
                    "X": "boarding_lon",
                    "Y": "boarding_lat",
                }
            )
        )
        return_df = pd.merge(input_df, df, how="left", on=input_column_name)

        return return_df

    def _read_standard_node(self):
        # TODO: This is not a generic filename...
        in_file = self.scenario_dir / "inputs/trn/standard/v12_node.geojson"
        logging.info(f"Reading {in_file}")
        self.standard_nodes_gdf = gpd.read_file(in_file, driver="GEOJSON")
        logging.debug(f"self.standard_nodes_gdf:\n{self.standard_nodes_gdf}")

    def _read_standard_transit_stops(self):
        # TODO: This is not a generic filename...
        in_file = self.scenario_dir / "inputs/trn/standard/v12_stops.txt"
        logging.info(f"Reading {in_file}")
        self.standard_transit_stops_df = pd.read_csv(in_file)
        logging.debug(f"self.standard_transit_stops_df:\n{self.standard_transit_stops_df}")

    def _read_standard_transit_shapes(self):
        # TODO: This is not a generic filename...
        in_file = self.scenario_dir / "inputs/trn/standard/v12_shapes.txt"
        logging.info(f"Reading {in_file}")
        self.standard_transit_shapes_df = pd.read_csv(in_file)
        logging.debug(f"self.standard_transit_shapes_df:\n{self.standard_transit_shapes_df}")


    def _read_standard_transit_routes(self):
        # TODO: This is not a generic filename...
        in_file = self.scenario_dir / "inputs/trn/standard/v12_routes.txt"
        logging.info(f"Reading {in_file}")
        self.standard_transit_routes_df = pd.read_csv(in_file)
        logging.debug(f"self.standard_transit_routes_df:\n{self.standard_transit_routes_df}")

    def _reduce_simulated_home_work_flows(self):
        """Process simulated home-to-work county flows.
        
        Reads workplace location results from CTRAMP, aggregates to county-to-county
        flows for comparison with CTPP data.
        
        Results stored in home_work_flows_df with columns:
            - residence_county: Home county name
            - work_county: Work county name
            - simulated_flow: Number of workers making this commute
        
        Returns:
            None
        """
        # if self.simulated_maz_data_df.empty:
        #    self._make_simulated_maz_data()
        # TODO: This should use the iteration not 1
        in_file = self.scenario_dir / "ctramp_output/wsLocResults_1.csv"
        logging.info(f"Reading {in_file}")
        workloc_df = pd.read_csv(in_file, usecols=[
            "HHID", "HomeMGRA", "WorkLocation"
        ])
        logging.debug(f"workloc_df:\n{workloc_df}")

        # get home county from home MAZ
        workloc_df = pd.merge(
            workloc_df,
            self.canonical.simulated_maz_data_df[["MAZ_SEQ", "CountyName"]],
            how="left",
            left_on="HomeMGRA",
            right_on="MAZ_SEQ",
            validate="many_to_one",
            indicator=True
        )
        logging.debug(workloc_df['_merge'].value_counts())
        assert (workloc_df['_merge'] == 'both').all()
        workloc_df.rename(columns={"CountyName": "residence_county"}, inplace=True)
        workloc_df.drop(columns=["MAZ_SEQ","_merge"], inplace=True)

        # get work county from work MAZ
        workloc_df = pd.merge(
            workloc_df,
            self.canonical.simulated_maz_data_df[["MAZ_SEQ", "CountyName"]],
            how="left",
            left_on="WorkLocation",
            right_on="MAZ_SEQ",
            validate="many_to_one",
            indicator=True
        )
        # WorkLocation either matches to county or is 0 or 99999
        assert ((workloc_df['_merge'] == 'both') | (workloc_df['WorkLocation'].isin([0,99999]))).all()
        workloc_df.rename(columns={"CountyName": "work_county"}, inplace=True)
        workloc_df.drop(columns=["MAZ_SEQ","_merge"], inplace=True)

        # TODO: this should use household samplerate
        workloc_df["num_workers"] = 1

        workloc_df = workloc_df.groupby(["residence_county", "work_county"]).agg(
            simulated_flow = pd.NamedAgg(column="num_workers", aggfunc="sum")
        ).reset_index()

        self.home_work_flows_df = workloc_df
        logging.debug(f"self.home_work_flows_df:\nself.home_work_flows_df")

        return

    def _make_simulated_maz_data(self):
        in_file = self.scenario_dir / self.scenario_dict["scenario"]["maz_landuse_file"]
        logging.info(f"Reading {in_file}")
        df = pd.read_csv(in_file)
        logging.debug(f"df:\n{df}")

        index_file = self.scenario_dir / "inputs/landuse/mtc_final_network_zone_seq.csv"
        logging.info(f"Reading {index_file}")
        index_df = pd.read_csv(index_file)
        logging.debug(f"df:\n{df}")
        join_df = index_df.rename(columns={"N": "MAZ_ORIGINAL"})[
            ["MAZ_ORIGINAL", "MAZSEQ"]
        ].copy()

        self.simulated_maz_data_df = pd.merge(
            df,
            join_df,
            how="left",
            on="MAZ_ORIGINAL",
        )

        self._make_taz_district_crosswalk()

        return

    def _make_taz_district_crosswalk(self):
        df = self.simulated_maz_data_df[["TAZ_ORIGINAL", "DistID"]].copy()
        df = df.rename(columns={"TAZ_ORIGINAL": "taz", "DistID": "district"})
        self.taz_to_district_df = df.drop_duplicates().reset_index(drop=True)

        return

    def _reduce_simulated_rail_access_summaries(self):
        """Process rail station access mode summaries.
        
        Reads transit segment files to extract boardings by access mode at rail stations.
        Focuses on heavy rail and commuter rail stations. Aggregates walk access from
        multiple sub-modes (walk-to-transit, walk-transfer-walk, etc.).
        
        Results stored in transit_access_df with columns:
            - operator: Rail operator canonical name
            - boarding: Station node ID
            - boarding_name: Station canonical name
            - boarding_standard_node_id: Standard network node
            - access_mode: Access mode (Walk, Park and Ride, Kiss and Ride)
            - simulated_boardings: Number of boardings by access mode
            - time_period: Time period
        
        Returns:
            None
        """
        if not self.transit_mode_dict:
            self._make_transit_mode_dict()

        file_prefix = "transit_segment_"

        out_df = pd.DataFrame()

        for time_period in self.model_time_periods:
            in_file = self.scenario_dir / f"output_summaries/transit_segment_{time_period}.csv"
            logging.info(f"Reading {in_file}")
            transit_df = pd.read_csv(
                in_file,
                dtype={"stop_name": str, "mdesc": str},
                low_memory=False,
            )
            logging.debug(f"transit_df:\n{transit_df}")

            # filter to heavy and commuter rail
            rail_df = transit_df.loc[transit_df["mdesc"].isin(["HVY", "COM"])].copy()

            rail_df["operator"] = rail_df["line"].str.split("_").str.get(1)
            logging.debug(f"rail_df.operator.value_counts():\n{rail_df.operator.value_counts(dropna=False)}")

            rail_df["operator"] = rail_df["operator"].map(
                self.canonical.canonical_agency_names_dict
            )
            logging.debug(f"rail_df.operator.value_counts():\n{rail_df.operator.value_counts(dropna=False)}")

            # collect rail nodes from i_node and j_node column
            # rail_nodes_df has two columns: operator, boarding (which is the node ID for the operator's stations)
            rail_nodes_df = pd.concat([
                rail_df[['operator','i_node']].rename(columns={'i_node':'boarding'}),
                rail_df[['operator','j_node']].rename(columns={'j_node':'boarding'}),
            ]).drop_duplicates().reset_index(drop=True)
            rail_nodes_df = rail_nodes_df.loc[ rail_nodes_df["boarding"].notna() ] # drop NA values
            rail_nodes_df["boarding"] = rail_nodes_df["boarding"].astype(int, errors="ignore")
            logging.debug(f"rail_nodes_df:\n{rail_nodes_df}")

            names_df = self._get_station_names_from_standard_network(rail_nodes_df)
            logging.debug(f"names_df:\n{names_df}")
            if "level_0" in names_df.columns:
                names_df = names_df.drop(columns=["level_0", "index"])
            station_list = names_df.boarding.astype(str).unique().tolist()

            access_df = transit_df.copy()
            access_df = access_df[access_df["j_node"].isin(station_list)].copy()
            access_df["board_ptw"] = (
                access_df["initial_board_ptw"] + access_df["direct_transfer_board_ptw"]
            )
            access_df["board_wtp"] = (
                access_df["initial_board_wtp"] + access_df["direct_transfer_board_wtp"]
            )
            access_df["board_ktw"] = (
                access_df["initial_board_ktw"] + access_df["direct_transfer_board_ktw"]
            )
            access_df["board_wtk"] = (
                access_df["initial_board_wtk"] + access_df["direct_transfer_board_wtk"]
            )
            access_df["board_wtw"] = (
                access_df["initial_board_wtw"] + access_df["direct_transfer_board_wtw"]
            )
            access_df = access_df[
                [
                    "i_node",
                    "board_ptw",
                    "board_wtp",
                    "board_ktw",
                    "board_wtk",
                    "board_wtw",
                ]
            ].copy()
            access_df["i_node"] = access_df.i_node.astype(int)

            access_dict = {
                "board_ptw": self.canonical.PARK_AND_RIDE_ACCESS_WORD,
                "board_wtp": self.canonical.WALK_ACCESS_WORD,
                "board_ktw": self.canonical.KISS_AND_RIDE_ACCESS_WORD,
                "board_wtk": self.canonical.WALK_ACCESS_WORD,
                "board_wtw": self.canonical.WALK_ACCESS_WORD,
            }
            long_df = pd.melt(
                access_df,
                id_vars=["i_node"],
                value_vars=[
                    "board_ptw",
                    "board_wtp",
                    "board_ktw",
                    "board_wtk",
                    "board_wtw",
                ],
                var_name="mode",
                value_name="boardings",
            )
            long_df["access_mode"] = long_df["mode"].map(access_dict)  # check

            join_df = pd.merge(
                long_df,
                names_df,
                how="left",
                left_on=["i_node"],
                right_on=["boarding"],
            ).reset_index(drop=True)

            running_df = (
                join_df.groupby(
                    [
                        "operator",
                        "i_node",
                        "boarding_name",
                        "boarding_standard_node_id",
                        "access_mode",
                    ]
                )
                .agg({"boardings": "sum"})
                .reset_index()
            )
            running_df = running_df.rename(
                columns={"boardings": "simulated_boardings", "i_node": "boarding"}
            )

            running_df["time_period"] = time_period

            out_df = pd.concat([out_df, running_df], axis="rows", ignore_index=True)

        self.transit_access_df = out_df
        logging.debug(f"self.transit_access_df:\n{self.transit_access_df}")

        return

    def _reduce_simulated_station_to_station(self):
        """Process simulated rail station-to-station flows.
        
        Reads station-to-station matrices for BART and Caltrain across all access
        modes (walk, drive, park-and-ride) and time periods. Applies canonical
        station names and sums across all paths.
        
        Results stored in station_to_station_df with columns:
            - operator: Rail operator (BART, Caltrain)
            - boarding_name: Origin station canonical name
            - alighting_name: Destination station canonical name
            - simulated: Total trips between stations
            - boarding_lat, boarding_lon: Station coordinates
        
        Returns:
            None
        """
        # if self.model_time_periods is None:
        #     self._get_model_time_periods()

        path_list = [
            "WLK_TRN_WLK",
            "WLK_TRN_KNR",
            "KNR_TRN_WLK",
            "WLK_TRN_PNR",
            "PNR_TRN_WLK",
        ]
        operator_list = ["bart", "caltrain"]

        df = pd.DataFrame(
            {
                "operator": pd.Series(dtype=str),
                "time_period": pd.Series(dtype=str),
                "boarding": pd.Series(dtype=str),
                "alighting": pd.Series(dtype=str),
                "simulated": pd.Series(dtype=str),
            }
        )

        for operator, time_period, path in itertools.product(
            operator_list, self.model_time_periods, path_list
        ):
            in_file = self.scenario_dir / \
                f"output_summaries/{operator}_station_to_station_{path}_{time_period}.txt"
            logging.info(f"Reading {in_file}")
            file = open(in_file, "r")
            logging.debug(f"df:\n{df}")

            while True:
                line = file.readline()
                if not line:
                    break
                if line[0] == "c" or line[0] == "t" or line[0] == "d" or line[0] == "a":
                    continue
                else:
                    data = line.split()
                    subject_df = pd.DataFrame(
                        [[operator, time_period, data[0], data[1], data[2]]],
                        columns=[
                            "operator",
                            "time_period",
                            "boarding",
                            "alighting",
                            "simulated",
                        ],
                    )

                    df = pd.concat([df, subject_df], axis="rows", ignore_index=True)

            df["boarding"] = df["boarding"].astype(int)
            df["alighting"] = df["alighting"].astype(int)
            # there are occasional odd simulated values with characters, such as '309u4181'
            df["simulated"] = pd.to_numeric(df['simulated'], errors='coerce').fillna(0)

            file.close()

        a_df = self._get_station_names_from_standard_network(
            df, operator_list=["BART", "Caltrain"]
        )
        sum_df = (
            a_df.groupby(["operator", "boarding_name", "alighting_name"])
            .agg({"simulated": "sum", "boarding_lat": "first", "boarding_lon": "first"})
            .reset_index()
        )

        self.station_to_station_df = sum_df.copy()

        return

    def _join_tm2_mode_codes(self, input_df):
        df = self.canonical.gtfs_to_tm2_mode_codes_df.copy()
        i_df = input_df["line_name"].str.split(pat="_", expand=True).copy()
        i_df["tm2_operator"] = i_df[0]
        i_df["tm2_operator"] = (
            pd.to_numeric(i_df["tm2_operator"], errors="coerce")
            .fillna(0)
            .astype(np.int64)
        )
        j_df = pd.concat([input_df, i_df["tm2_operator"]], axis="columns")

        return_df = pd.merge(
            j_df,
            df,
            how="left",
            on=["tm2_operator", "tm2_mode"],
        )

        return return_df

    def _reduce_simulated_transit_boardings(self):
        """Process simulated transit boardings by route and time period.
        
        Reads boardings_by_line CSV files for each time period, joins with mode/operator
        crosswalk, applies canonical naming, and aggregates to daily totals.
        
        Results stored in boardings_df with columns:
            - line_name: Time-specific line identifier
            - daily_line_name: Daily aggregated line name
            - tm2_mode: TM2 mode code
            - line_mode: Line mode description
            - operator: Canonical operator name
            - technology: Mode technology (Bus, Rail, etc.)
            - time_period: Time period (am, pm, daily, etc.)
            - total_boarding: Total boardings on route
            - total_hour_cap: Total hourly capacity
        
        Returns:
            None
        """
        c_df = pd.DataFrame()
        for time_period in self.model_time_periods:
            in_file = self.scenario_dir / f"output_summaries/boardings_by_line_{time_period}.csv"
            logging.info(f"Reading {in_file}")
            df = pd.read_csv(in_file)
            logging.debug(f"df:\n{df}")

            df["time_period"] = time_period
            c_df = pd.concat([c_df, df], axis="rows", ignore_index=True)

        c_df = self._join_tm2_mode_codes(c_df)
        c_df["operator"] = c_df["operator"].map(self.canonical.canonical_agency_names_dict)
        c_df = self.canonical.aggregate_line_names_across_time_of_day(c_df, "line_name")

        time_period_df = (
            c_df.groupby(
                [
                    "daily_line_name",
                    "line_name",
                    "tm2_mode",
                    "line_mode",
                    "operator",
                    "technology",
                    "fare_system",
                    "time_period",
                ]
            )
            .agg({"total_boarding": np.sum, "total_hour_cap": np.sum})
            .reset_index()
        )

        daily_df = (
            time_period_df.groupby(
                [
                    "daily_line_name",
                    "tm2_mode",
                    "line_mode",
                    "operator",
                    "technology",
                    "fare_system",
                ]
            )
            .agg({"total_boarding": np.sum, "total_hour_cap": np.sum})
            .reset_index()
        )
        daily_df["time_period"] = self.canonical.ALL_DAY_WORD
        daily_df["line_name"] = "N/A -- Daily Record"

        self.boardings_df = pd.concat(
            [daily_df, time_period_df], axis="rows", ignore_index=True
        )

        return

    def _reduce_simulated_zero_vehicle_households(self):
        """Process simulated zero-vehicle household shares.
        
        Reads household vehicle ownership from CTRAMP outputs, calculates zero-vehicle
        shares by MAZ, then aggregates to census tract level using MAZ-to-blockgroup
        crosswalk.
        
        Results stored in:
        - zero_vehicle_hhs_df: MAZ-level data
        - reduced_zero_vehicle_hhs_df: Census tract-level aggregation
            with columns: tract, simulated_zero_vehicle_share, simulated_households
        
        Returns:
            None
        """
        # TODO: This should use the iteration not 1
        in_file = self.scenario_dir / "ctramp_output/householdData_1.csv"
        logging.info(f"Reading {in_file}")
        hhlds_df = pd.read_csv(in_file)
        logging.debug(f"hhlds_df:\n{hhlds_df}")
        hhlds_df.rename(columns={"home_mgra":"HOME_MAZ_SEQ"}, inplace=True)
        assert(hhlds_df.HOME_MAZ_SEQ.max() < 100_000)

        # sum households by home MAZ and number of autos
        hhlds_df["hhld_count"] = 1.0 / hhlds_df["sampleRate"]
        hhld_summary_df = hhlds_df.groupby(["HOME_MAZ_SEQ", "autos"]).agg(
            hhld_count = pd.NamedAgg(column="hhld_count", aggfunc="sum")
        ).reset_index(drop=False)
        logging.debug(f"hhld_summary_df:\n{hhld_summary_df}")

        # sum households by MAZ
        home_maz_summary_df = hhlds_df.groupby("HOME_MAZ_SEQ").agg(
            maz_hhld_count = pd.NamedAgg(column="hhld_count", aggfunc="sum")
        ).reset_index(drop=False)
        logging.debug(f"home_maz_summary_df:\n{home_maz_summary_df}")

        hhld_summary_df = pd.merge(
            left=hhld_summary_df,
            right=home_maz_summary_df,
            how="left",
            on="HOME_MAZ_SEQ",
            validate="many_to_one"
        )
        logging.debug(f"hhld_summary_df:\n{hhld_summary_df}")
        # keep only zero autos
        self.zero_vehicle_hhs_df = hhld_summary_df.loc[hhld_summary_df.autos == 0].copy()
        self.zero_vehicle_hhs_df.rename(columns={
            "hhld_count": "zero_auto_hhld_count",
        }, inplace=True)

        # add column MAZ_NODE equivalent for HOME_MAZ_SEQ
        zero_vehicle_hhs_df = pd.merge(
            self.zero_vehicle_hhs_df,
            self.canonical.simulated_maz_data_df[["MAZ_NODE", "MAZ_SEQ"]].rename(columns={"MAZ_SEQ":"HOME_MAZ_SEQ"}),
            on="HOME_MAZ_SEQ",
            how="left",
            validate="many_to_one",
            indicator=True
        )
        logging.debug(f"zero_vehicle_hhs_df:\n{zero_vehicle_hhs_df}")
        assert (zero_vehicle_hhs_df['_merge'] == 'both').all()
        zero_vehicle_hhs_df.drop(columns=["_merge"], inplace=True)

        # add column blockgroup
        # TODO: BUG: This isn't valid because MAZ_NODE is not unique
        zero_vehicle_hhs_df = pd.merge(
            zero_vehicle_hhs_df,
            self.canonical.census_2010_to_maz_crosswalk_df,
            how="left",
            on="MAZ_NODE",
            # validate="many_to_one",  # TODO
            indicator=True,
        )
        logging.debug(f"zero_vehicle_hhs_df['_merge'].value_counts():\n{zero_vehicle_hhs_df['_merge'].value_counts()}")
        assert (zero_vehicle_hhs_df['_merge'] == 'both').all()
        zero_vehicle_hhs_df.drop(columns=["_merge"], inplace=True)
        zero_vehicle_hhs_df["tract"] = zero_vehicle_hhs_df["blockgroup"].astype("str").str.slice(stop=-1)

        # summarize to tract
        zero_vehicle_tract_df = zero_vehicle_hhs_df.groupby("tract").agg(
            zero_auto_hhld_count = pd.NamedAgg(column="zero_auto_hhld_count", aggfunc="sum"),
            maz_hhld_count       = pd.NamedAgg(column="maz_hhld_count",       aggfunc="sum")
        ).reset_index(drop=False)
        zero_vehicle_tract_df["simulated_zero_vehicle_share"] = \
            zero_vehicle_tract_df["zero_auto_hhld_count"] / zero_vehicle_tract_df["maz_hhld_count"]
        logging.debug(f"zero_vehicle_tract_df:\n{zero_vehicle_tract_df}")

        self.reduced_zero_vehicle_hhs_df = zero_vehicle_tract_df

        return

    def _get_station_names_from_standard_network(
        self,
        input_df: pd.DataFrame,
        operator_list: list = None,
    ) -> pd.DataFrame:
        """Get canonical station names and coordinates from node IDs.
        
        Takes a dataframe with station node IDs and adds canonical station names
        and coordinates by joining with standard network stops data.
        
        Args:
            input_df (pd.DataFrame): DataFrame with columns:
                - boarding (int, optional): Boarding station node ID
                - alighting (int, optional): Alighting station node ID
                - operator (str): Transit operator name
            operator_list (list, optional): List of operators to process.
                Defaults to all operators in canonical_station_names_dict.
        
        Returns:
            pd.DataFrame: Input DataFrame with added columns:
                - boarding_name: Canonical boarding station name
                - boarding_lat, boarding_lon: Boarding station coordinates
                - boarding_standard_node_id: Standard network node ID
                - alighting_name: Canonical alighting station name (if applicable)
                - alighting_lat, alighting_lon: Alighting station coordinates
                - alighting_standard_node_id: Standard network node ID

        # TODO: returned dataframe has columns 'level_0' and 'index' when called from 
        # TODO: _reduce_simulated_rail_access_summaries()

        # TODO: Calling a boarding node "boarding" is confusing and sounds
        # TODO: like a count of boardings.
        """

        x_df = self.canonical.standard_to_emme_transit_nodes_df.copy()

        stations_list = []
        if "boarding" in input_df.columns:
            stations_list.extend(input_df["boarding"].unique().astype(int).tolist())

        if "alighting" in input_df.columns:
            stations_list.extend(input_df["alighting"].unique().astype(int).tolist())

        assert (
            len(stations_list) > 0
        ), "No boarding or alighting columns found in input_df."

        stations_list = list(set(stations_list))

        x_trim_df = (
            x_df[x_df["emme_node_id"].isin(stations_list)].copy().reset_index(drop=True)
        )

        station_df = self.standard_transit_stops_df[
            ["stop_name", "stop_lat", "stop_lon", "model_node_id"]
        ].copy()

        if "boarding" in input_df.columns:
            r_df = (
                pd.merge(
                    input_df,
                    x_trim_df,
                    left_on="boarding",
                    right_on="emme_node_id",
                    how="left",
                )
                .rename(columns={"model_node_id": "boarding_standard_node_id"})
                .reset_index(drop=True)
            )
            r_df = r_df.drop(columns=["emme_node_id"])

            r_df = (
                pd.merge(
                    r_df,
                    station_df,
                    left_on="boarding_standard_node_id",
                    right_on="model_node_id",
                    how="left",
                )
                .rename(
                    columns={
                        "stop_name": "boarding_name",
                        "stop_lat": "boarding_lat",
                        "stop_lon": "boarding_lon",
                    }
                )
                .reset_index(drop=True)
            )
            r_df = r_df.drop(columns=["model_node_id"])

        if "alighting" in input_df.columns:
            r_df = (
                pd.merge(
                    r_df,
                    x_trim_df,
                    left_on="alighting",
                    right_on="emme_node_id",
                    how="left",
                )
                .rename(columns={"model_node_id": "alighting_standard_node_id"})
                .reset_index(drop=True)
            )
            r_df = r_df.drop(columns=["emme_node_id"])

            r_df = (
                pd.merge(
                    r_df,
                    station_df,
                    left_on="alighting_standard_node_id",
                    right_on="model_node_id",
                    how="left",
                )
                .rename(
                    columns={
                        "stop_name": "alighting_name",
                        "stop_lat": "alighting_lat",
                        "stop_lon": "alighting_lon",
                    }
                )
                .reset_index(drop=True)
            )
            r_df = r_df.drop(columns=["model_node_id"])

        r_df["operator"] = r_df["operator"].map(self.canonical.canonical_agency_names_dict)

        return_df = None
        if operator_list is None:
            operator_list = self.canonical.canonical_station_names_dict.keys()
        for operator in operator_list:
            if operator in r_df["operator"].unique().tolist():
                sub_df = r_df[r_df["operator"] == operator].copy()

                if "boarding" in input_df.columns:
                    sub_df["boarding_name"] = sub_df["boarding_name"].map(
                        self.canonical.canonical_station_names_dict[operator]
                    )

                if "alighting" in input_df.columns:
                    sub_df["alighting_name"] = sub_df["alighting_name"].map(
                        self.canonical.canonical_station_names_dict[operator]
                    )

                if return_df is None:
                    return_df = sub_df.copy()
                else:
                    return_df = pd.concat([return_df, sub_df]).reset_index()

        return return_df

    def _make_transit_mode_dict(self):  # check
        transit_mode_dict = {}
        for lil_dict in self.model_dict["transit"]["modes"]:
            add_dict = {lil_dict["mode_id"]: lil_dict["name"]}
            transit_mode_dict.update(add_dict)

        # TODO: this will be in model_config in TM2.2
        transit_mode_dict.update({"p": "pnr"})

        # self.HEAVY_RAIL_NETWORK_MODE_DESCR = transit_mode_dict["h"]
        # self.COMMUTER_RAIL_NETWORK_MODE_DESCR = transit_mode_dict["r"]

        access_mode_dict = {
            transit_mode_dict["w"]: self.canonical.WALK_ACCESS_WORD,
            transit_mode_dict["a"]: self.canonical.WALK_ACCESS_WORD,
            transit_mode_dict["e"]: self.canonical.WALK_ACCESS_WORD,
            transit_mode_dict["p"]: self.canonical.PARK_AND_RIDE_ACCESS_WORD,
        }
        access_mode_dict.update(
            {
                "knr": self.canonical.KISS_AND_RIDE_ACCESS_WORD,
                "bike": self.canonical.BIKE_ACCESS_WORD,
                self.canonical.WALK_ACCESS_WORD: self.canonical.WALK_ACCESS_WORD,
                self.canonical.BIKE_ACCESS_WORD: self.canonical.BIKE_ACCESS_WORD,
                self.canonical.PARK_AND_RIDE_ACCESS_WORD: self.canonical.PARK_AND_RIDE_ACCESS_WORD,
                self.canonical.KISS_AND_RIDE_ACCESS_WORD: self.canonical.KISS_AND_RIDE_ACCESS_WORD,
            }
        )

        self.transit_mode_dict = transit_mode_dict
        self.transit_access_mode_dict = access_mode_dict

        logging.debug(f"self.transit_mode_dict:\n{pprint.pformat(self.transit_mode_dict)}")
        logging.debug(f"self.transit_access_mode_dict:\n{pprint.pformat(self.transit_access_mode_dict)}")
        return

    def _make_transit_technology_in_vehicle_table_from_skims(self, time_period_list: list = ["am"]):
        """Create in-vehicle time by technology from transit skims.
        
        Reads transit skim matrices to extract in-vehicle times by technology
        (local bus, express bus, light rail, ferry, heavy rail, commuter rail)
        for each OD pair. Used to allocate trips to technologies based on
        in-vehicle time shares.
        
        Results stored in transit_tech_in_vehicle_times_df with columns:
            - origin, destination: TAZ pair
            - path: Access mode path (WLK_TRN_WLK, PNR_TRN_WLK, etc.)
            - time_period: Time period
            - ivt: Total in-vehicle time
            - boards: Number of boardings
            - loc, exp, ltr, fry, hvy, com: IVT by technology
        
        Returns:
            None
        """
        start_time = time.perf_counter()
        logging.info("_make_transit_technology_in_vehicle_table_from_skims()")
        path_list = [
            "WLK_TRN_WLK",
            "PNR_TRN_WLK",
            "WLK_TRN_PNR",
            "KNR_TRN_WLK",
            "WLK_TRN_KNR",
        ]

        self.model_time_periods =  time_period_list

        tech_list = self.canonical.transit_technology_abbreviation_dict.keys()

        skim_dir = self.scenario_dir / "skim_matrices/transit"

        self.transit_tech_in_vehicle_times_pldf = pl.DataFrame()
        for path, time_period in itertools.product(path_list, self.model_time_periods):
            filename = skim_dir / f"trnskm{time_period.upper()}_{path}.omx"

            if not filename.exists:
                continue
            
            logging.info(f"Reading {filename}")
            omx_handle = omx.open_file(filename)
            # IVT
            TIME_PERIOD = time_period.upper()
            matrix_name = TIME_PERIOD + "_" + path + "_IVT"
            logging.debug(f"Extracting {matrix_name}")
            assert(matrix_name in omx_handle.listMatrices())
            ivt_pldf = self._make_dataframe_from_omx(
                omx_handle[matrix_name], matrix_name, filter_zero=True
            )
            ivt_pldf = ivt_pldf.rename({matrix_name: "ivt"})

            # Transfers to get boardings from trips

            matrix_name = TIME_PERIOD + "_" + path + "_BOARDS"
            logging.debug(f"Extracting {matrix_name}")
            assert(matrix_name in omx_handle.listMatrices())
            boards_pldf = self._make_dataframe_from_omx(
                omx_handle[matrix_name], matrix_name, filter_zero=True
            )
            boards_pldf = boards_pldf.rename({matrix_name: "boards"})

            path_time_pldf = ivt_pldf.join(
                boards_pldf,
                on=["origin_TAZ_SEQ", "destination_TAZ_SEQ"],
                how="left",
                coalesce=True,
                validate="1:1"
            )
            # path_time_pldf["path"] = path
            path_time_pldf = path_time_pldf.with_columns(pl.lit(path).alias("path"))
            # path_time_pldf["time_period"] = time_period
            path_time_pldf = path_time_pldf.with_columns(pl.lit(time_period).alias("time_period"))
            # there shouldn't be any null boards...

            for tech in tech_list:
                matrix_name = TIME_PERIOD + "_" + path + "_IVT" + tech
                logging.debug(f"Extracting {matrix_name}")
                assert(matrix_name in omx_handle.listMatrices())
                tech_ivt_pldf = self._make_dataframe_from_omx(
                    omx_handle[matrix_name], matrix_name, filter_zero=True
                )
                tech_ivt_pldf = tech_ivt_pldf.rename({matrix_name:tech.lower()})
                path_time_pldf = path_time_pldf.join(
                    tech_ivt_pldf,
                    how="left",
                    on=["origin_TAZ_SEQ", "destination_TAZ_SEQ"],
                    coalesce=True,
                    validate="1:1"
                )
                # fill null tech-IVT
                path_time_pldf = path_time_pldf.with_columns(pl.col(tech.lower()).fill_null(0))

            self.transit_tech_in_vehicle_times_pldf = pl.concat([
                self.transit_tech_in_vehicle_times_pldf, 
                path_time_pldf
            ])
            omx_handle.close()
        end_time = time.perf_counter()
        logging.debug(f"self.transit_tech_in_vehicle_times_pldf:\n{self.transit_tech_in_vehicle_times_pldf}")
        logging.debug(f"description:\n{self.transit_tech_in_vehicle_times_pldf.describe()}")
        logging.info(f"memory usage: {self.transit_tech_in_vehicle_times_pldf.estimated_size('mb'):.2f} MB")
        logging.info(f"time taken: {(end_time - start_time)/60:.1f} minutes")
        return    

    def _read_transit_demand(self):
        start_time = time.perf_counter()
        logging.info("_read_transit_demand()")
        path_list = [
            "WLK_TRN_WLK",
            "PNR_TRN_WLK",
            "WLK_TRN_PNR",
            "KNR_TRN_WLK",
            "WLK_TRN_KNR",
        ]
        transit_demand_dir = self.scenario_dir / "demand_matrices/transit"

        # polars version
        self.simulated_transit_demand_pldf = pl.DataFrame()
        for time_period in self.model_time_periods:
            filename = transit_demand_dir / f"trn_demand_{time_period}_{self.iter}.omx"
            logging.info(f"Reading {filename}")
            omx_handle = omx.open_file(filename)

            for path in path_list:
                assert(path in omx_handle.listMatrices())
                demand_pldf = self._make_dataframe_from_omx(omx_handle[path], path, filter_zero=True)
                demand_pldf = demand_pldf.rename({path: "simulated_flow"})
                # df["path"] = path
                demand_pldf = demand_pldf.with_columns(pl.lit(path).alias("path"))
                # df["time_period"] = time_period
                demand_pldf = demand_pldf.with_columns(pl.lit(time_period).alias("time_period"))

                self.simulated_transit_demand_pldf = pl.concat([
                    self.simulated_transit_demand_pldf,
                    demand_pldf
                ])
            omx_handle.close()
        end_time = time.perf_counter()
        logging.debug(f"self.simulated_transit_demand_pldf:\n{self.simulated_transit_demand_pldf}")
        logging.debug(f"description:\n{self.simulated_transit_demand_pldf.describe()}")
        logging.info(f"memory usage: {self.simulated_transit_demand_pldf.estimated_size('mb'):.2f} MB")
        logging.info(f"time taken: {(end_time - start_time)/60:.1f} minutes")
        return


    def _make_dataframe_from_omx(
            self, 
            input_mtx: omx,
            core_name: str,
            filter_zero: bool
        ) -> pl.DataFrame:
        """_summary_

        Args:
            input_mtx (omx): OpenMatrix matrix object
            core_name (str): Name of matrix core to extract
            filter_zero (bool): If true, filters out rows with core_name == 0

        Returns:
            pl.DataFrame: Long-format DataFrame with columns:
                - origin_TAZ_SEQ: Origin TAZ
                - destination_TAZ_SEQ: Destination TAZ
                - {core_name}: Matrix value
        """
        np_matrix = np.array(input_mtx)
        origins, destinations = np.indices(np_matrix.shape)
        polars_df = pl.DataFrame({
            "origin_TAZ_SEQ": origins.flatten() + 1,
            "destination_TAZ_SEQ": destinations.flatten() + 1,
            core_name:np_matrix.flatten()
        })

        if filter_zero:
            polars_df = polars_df.filter(pl.col(core_name) > 0)
        return polars_df

    def _make_district_to_district_transit_summaries(self):
        """Create district-to-district transit flows by technology using polars.

        Combines transit demand and in-vehicle times to allocate trips to technologies.
        Aggregates TAZ-level flows to planning districts. Calculates trips using each
        technology based on in-vehicle time proportions.

        Uses polars DataFrames: simulated_transit_demand_pldf and transit_tech_in_vehicle_times_pldf

        Results stored in transit_district_to_district_by_tech_pldf with columns:
            - orig_district: Origin district ID (1-34)
            - dest_district: Destination district ID (1-34)
            - tech: Technology code (loc, exp, ltr, fry, hvy, com, total)
            - simulated: Number of trips using this technology

        Returns:
            None
        """
        start_time = time.perf_counter()
        logging.info("_make_district_to_district_transit_summaries()")

        # Create TAZ-to-district lookup dictionary for mapping zones to districts
        taz_seq_district_dict = self.canonical.taz_to_district_df.set_index("TAZ_SEQ")[
            "district"
        ].to_dict()
        logging.debug(f"taz_seq_district_dict:{taz_seq_district_dict}")

        # Aggregate demand by OD pair and time period (sum across all paths/modes)
        summary_pldf = self.simulated_transit_demand_pldf.group_by(
            ["origin_TAZ_SEQ", "destination_TAZ_SEQ", "time_period"]
        ).agg(pl.col("simulated_flow").sum())
        
        # Join demand with path/skim data to get in-vehicle times and boardings
        summary_pldf = summary_pldf.join(
            self.transit_tech_in_vehicle_times_pldf,
            on=["origin_TAZ_SEQ", "destination_TAZ_SEQ", "time_period"],
            how="inner",
        )

        # Filter to AM period only
        summary_pldf = summary_pldf.filter(pl.col("time_period") == "am")

        # Calculate technology-specific flows using formula:
        # tech_flow = total_flow * boards * tech_ivt / total_ivt
        # This allocates trips to technologies based on their share of in-vehicle time
        for tech in self.canonical.transit_technology_abbreviation_dict.keys():
            column_name = f"simulated_{tech.lower()}_flow"
            summary_pldf = summary_pldf.with_columns(
                (
                    pl.col("simulated_flow")
                    * pl.col("boards")
                    * pl.col("{}".format(tech.lower()))
                    / pl.col("ivt")
                ).alias(column_name)
            )

        # Map TAZ origins and destinations to planning districts
        summary_pldf = summary_pldf.with_columns([
            pl.col("origin_TAZ_SEQ").replace_strict(taz_seq_district_dict, default=None).alias("orig_district"),
            pl.col("destination_TAZ_SEQ").replace_strict(taz_seq_district_dict, default=None).alias("dest_district"),
        ])

        # Build aggregation expressions for all flow columns
        agg_exprs = [pl.col("simulated_flow").sum()]
        for tech in self.canonical.transit_technology_abbreviation_dict.keys():
            agg_exprs.append(pl.col("simulated_{}_flow".format(tech.lower())).sum())

        # Aggregate flows by district OD pairs
        summary_pldf = (
            summary_pldf.group_by(["orig_district", "dest_district"]).agg(agg_exprs)
        )

        # Reshape from wide to long format (one row per district OD + technology)
        summary_pldf = summary_pldf.melt(
            id_vars=["orig_district", "dest_district"],
            variable_name="tech",
            value_name="simulated",
        )
        logging.debug(f"summary_pldf:\n{summary_pldf}")

        # Create mapping to rename flow columns to technology codes
        # e.g., "simulated_flow" -> "total", "simulated_loc_flow" -> "loc"
        rename_dict = {"simulated_flow": "total"}
        for tech in self.canonical.transit_technology_abbreviation_dict.keys():
            rename_dict[f"simulated_{tech.lower()}_flow"] = tech.lower()

        # Apply the renaming to get clean technology codes
        summary_pldf = summary_pldf.with_columns(
            pl.col("tech").replace_strict(rename_dict, default=None)
        )

        # Store the result - convert to pandas
        self.transit_district_to_district_by_tech_df = summary_pldf.to_pandas()

        end_time = time.perf_counter()
        logging.info(f"time taken: {(end_time - start_time):.2f} seconds")

        # Log pivoted matrices by technology for easier comparison
        for tech_value in sorted(self.transit_district_to_district_by_tech_df['tech'].unique()):
            tech_df = self.transit_district_to_district_by_tech_df[
                self.transit_district_to_district_by_tech_df['tech'] == tech_value
            ].copy()
            pivot_df = tech_df.pivot(
                index='orig_district',
                columns='dest_district',
                values='simulated'
            )
            logging.debug(f"transit_district_to_district matrix (polars) - {tech_value}:\n{pivot_df}")


        return

    def _reduce_simulated_traffic_flow(self):
        time_of_day_df = pd.DataFrame()

        for time_period in self.model_time_periods:
            emme_scenario = self.network_shapefile_names_dict[time_period]
            in_file = self.scenario_dir / f"output_summaries/{emme_scenario}/emme_links.shp"
            logging.info(f"Reading {in_file}")
            gdf = gpd.read_file(in_file)
            logging.debug(f"df:\n{df}")
            df = gdf[
                [
                    "ID",
                    "@flow_da",
                    "@flow_lrgt",
                    "@flow_sr2",
                    "@flow_sr3",
                    "@flow_trk",
                    "@flow_dato",
                    "@flow_lrg0",
                    "@flow_sr2t",
                    "@flow_sr3t",
                    "@flow_trkt",
                ]
            ]
            df = df.rename(columns={"ID": "model_link_id"})
            df["time_period"] = time_period
            time_of_day_df = pd.concat(
                [time_of_day_df, df], axis="rows", ignore_index="True"
            )

            time_of_day_df["simulated_flow_auto"] = time_of_day_df[
                [
                    "@flow_da",
                    "@flow_sr2",
                    "@flow_sr3",
                    "@flow_dato",
                    "@flow_sr2t",
                    "@flow_sr3t",
                ]
            ].sum(axis=1)

            time_of_day_df["simulated_flow_truck"] = time_of_day_df[
                ["@flow_trk", "@flow_trkt"]
            ].sum(axis=1)
            time_of_day_df["simulated_flow"] = time_of_day_df[
                [
                    "simulated_flow_auto",
                    "simulated_flow_truck",
                    "@flow_lrgt",
                    "@flow_lrg0",
                ]
            ].sum(axis=1)

            all_day_df = time_of_day_df.groupby(["model_link_id"]).sum().reset_index()
            all_day_df["time_period"] = self.canonical.ALL_DAY_WORD

            out_df = pd.concat(
                [time_of_day_df, all_day_df], axis="rows", ignore_index=True
            )

        out_df = out_df[
            [
                "model_link_id",
                "time_period",
                "simulated_flow_auto",
                "simulated_flow_truck",
                "simulated_flow",
            ]
        ]

        self.simulated_traffic_flow_df = out_df

        return

    def _reduce_simulated_roadway_assignment_outcomes(self):
        """Process simulated roadway volumes and speeds.
        
        Reads EMME link shapefiles for each time period, extracts volumes by vehicle
        class, speeds, and capacities. Combines general purpose and managed lane
        volumes. Aggregates to daily totals.
        
        Results stored in roadway_assignment_results_df with columns:
            - emme_a_node_id, emme_b_node_id: Link nodes
            - standard_link_id: Link identifier
            - time_period: Time period (am, pm, daily, etc.)
            - flow_da, flow_s2, flow_s3: Auto volumes by occupancy
            - flow_lrgt, flow_trk: Large truck and truck volumes
            - flow_total: Total volume all vehicles
            - m_flow_*: Managed lane volumes by class
            - capacity: Link capacity
            - lanes: Number of lanes
            - speed_mph: Congested speed
            - ft: Facility type code
            - distance_in_miles: Link length
        
        Also creates roadway_am_shape_gdf with AM period geometry.
        
        Returns:
            None
        """
        # step 1: get the shape
        shape_period = "am"
        emme_scenario = self.network_shapefile_names_dict[shape_period]

        in_file = self.scenario_dir / f"output_summaries/{emme_scenario}/emme_links.shp"
        logging.info(f"Reading {in_file}")
        shape_gdf = gpd.read_file(in_file)
        logging.debug(f"shape_gdf:\n{shape_gdf}")
        self.roadway_am_shape_gdf = (
            shape_gdf[["INODE", "JNODE", "#link_id", "geometry"]]
            .copy()
            .rename(
                columns={
                    "INODE": "emme_a_node_id",
                    "JNODE": "emme_b_node_id",
                    "#link_id": "standard_link_id",
                }
            )
        )

        # step 2: fetch the roadway volumes
        across_df = pd.DataFrame()
        for t in self.model_time_periods:
            if t == shape_period:
                gdf = shape_gdf
            else:
                emme_scenario = self.network_shapefile_names_dict[t]
                in_file = self.scenario_dir / f"output_summaries/{emme_scenario}/emme_links.shp"
                logging.info(f"Reading {in_file}")
                gdf = gpd.read_file(in_file)
                logging.debug(f"gdf:\n{gdf}")

            df = pd.DataFrame(gdf)[
                [
                    "INODE",
                    "JNODE",
                    "#link_id",
                    "LENGTH",
                    "TIMAU",
                    "@lanes",
                    "@useclass",
                    "@capacity",
                    "@managed",
                    "@tollbooth",
                    "@tollseg",
                    "@ft",
                    "@flow_da",
                    "@flow_sr2",
                    "@flow_sr3",
                    "@flow_lrgt",
                    "@flow_trk",
                    "@free_flow",
                    "@flow_dato",
                    "@flow_sr2t",
                    "@flow_sr3t",
                    "@flow_lrg0",
                    "@flow_trkt",
                ]
            ]
            df = df.rename(
                columns={
                    "INODE": "emme_a_node_id",
                    "JNODE": "emme_b_node_id",
                    "#link_id": "standard_link_id",
                    "LENGTH": "distance_in_miles",
                    "TIMAU": "time_in_minutes",
                    "@managed": "managed",
                    "@tollbooth": "tollbooth",
                    "@tollseg": "tollseg",
                    "@ft": "ft",
                    "@useclass": "useclass",
                    "@capacity": "capacity",
                    "@lanes": "lanes",
                }
            )

            df["flow_da"] = df["@flow_da"] + df["@flow_dato"]
            df["flow_s2"] = df["@flow_sr2"] + df["@flow_sr2t"]
            df["flow_s3"] = df["@flow_sr3"] + df["@flow_sr3t"]
            df["flow_lrgt"] = df["@flow_lrgt"] + df["@flow_lrg0"]
            df["flow_trk"] = df["@flow_trk"] + df["@flow_trkt"]

            df["time_period"] = t
            df["speed_mph"] = np.where(
                df["distance_in_miles"] > 0,
                df["distance_in_miles"] / (df["time_in_minutes"] / 60.0),
                df["@free_flow"],
            )
            df["flow_total"] = df[
                [col for col in df.columns if col.startswith("flow_")]
            ].sum(axis=1)

            # join managed lane flows to general purpose
            managed_df = df[df["managed"] == 1].copy()
            managed_df["join_link_id"] = (
                managed_df["standard_link_id"] - self.canonical.MANAGED_LANE_OFFSET
            )
            managed_df = managed_df[
                [
                    "join_link_id",
                    "flow_da",
                    "flow_s2",
                    "flow_s3",
                    "flow_lrgt",
                    "flow_trk",
                    "flow_total",
                    "time_period",
                    "lanes",
                    "capacity",
                    "speed_mph",
                ]
            ].copy()
            managed_df = managed_df.rename(
                columns={
                    "join_link_id": "standard_link_id",
                    "lanes": "m_lanes",
                    "flow_da": "m_flow_da",
                    "flow_s2": "m_flow_s2",
                    "flow_s3": "m_flow_s3",
                    "flow_lrgt": "m_flow_lrgt",
                    "flow_trk": "m_flow_trk",
                    "flow_total": "m_flow_total",
                    "speed_mph": "m_speed_mph",
                    "capacity": "m_capacity",
                }
            )

            df = pd.merge(
                df, managed_df, how="left", on=["standard_link_id", "time_period"]
            )
            df.fillna(
                {
                    "m_flow_da": 0,
                    "m_flow_s2": 0,
                    "m_flow_s3": 0,
                    "m_flow_lrgt": 0,
                    "m_flow_trk": 0,
                    "m_flow_total": 0,
                    "m_lanes": 0,
                    "m_speed_mph": 0,
                    "m_capacity": 0,
                },
                inplace=True,
            )

            variable_list = [
                "flow_da",
                "flow_s2",
                "flow_s3",
                "flow_lrgt",
                "flow_trk",
                "flow_total",
                "lanes",
                "capacity",
            ]
            for variable in variable_list:
                m_variable = "m_" + variable
                df[variable] = df[variable] + df[m_variable]

            # can now drop managed lane entries
            df = df[df["managed"] == 0].copy()

            if len(across_df.index) == 0:
                across_df = df.copy()
            else:
                across_df = pd.concat([across_df, df], axis="rows")

        daily_df = (
            across_df.groupby(["emme_a_node_id", "emme_b_node_id", "standard_link_id"])
            .agg(
                {
                    "ft": "median",
                    "distance_in_miles": "median",
                    "lanes": "median",
                    "flow_da": "sum",
                    "flow_s2": "sum",
                    "flow_s3": "sum",
                    "flow_trk": "sum",
                    "flow_lrgt": "sum",
                    "flow_total": "sum",
                    "m_flow_da": "sum",
                    "m_flow_s2": "sum",
                    "m_flow_s3": "sum",
                    "m_flow_lrgt": "sum",
                    "m_flow_trk": "sum",
                    "m_flow_total": "sum",
                }
            )
            .reset_index(drop=False)
        )
        daily_df["time_period"] = self.canonical.ALL_DAY_WORD

        return_df = pd.concat([across_df, daily_df], axis="rows").reset_index(drop=True)

        self.roadway_assignment_results_df = return_df

        return
