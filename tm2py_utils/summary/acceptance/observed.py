"""Methods to handle observed data for the Acceptance Criteria summaries from a tm2py model run.

This module manages observed data from various sources including PeMS traffic counts,
transit on-board surveys, census data, and bridge toll transactions. It processes and
standardizes these data sources for comparison with simulated model outputs.
"""

from tm2py_utils.summary.acceptance.canonical import Canonical

import logging
import numpy as np
import geopandas as gpd
import pandas as pd
import pathlib
import pyproj
import toml

# TODO: This is not generic observed, but specific to 2015 Observed.
class Observed:
    """Manages observed data for acceptance criteria validation.
    
    This class handles loading, processing, and standardizing observed data from multiple
    sources for comparison with simulated model outputs. It applies data reduction and
    aggregation methods to prepare observed data for acceptance criteria evaluation.
    
    Attributes:
        canonical (Canonical): Canonical naming and crosswalk handler
        observed_dict (dict): Configuration from observed TOML file
        observed_file (str): Path to observed configuration file
        
        Traffic/Roadway Data:
        reduced_traffic_counts_df (pd.DataFrame): Processed traffic counts with columns:
            - model_link_id: Network link ID
            - source: Data source (PeMS, Caltrans)
            - station_id: Count station identifier
            - vehicle_class: Vehicle type (All Vehicles, Large Trucks)
            - time_period: Time period (am, pm, md, ev, ea, daily)
            - observed_flow: Traffic volume
            - odot_flow_category_daily/hourly: Volume category for error standards
            - odot_maximum_error: Maximum acceptable percent error
            - key_location: Key arterial or bridge name if applicable
            
        observed_bridge_transactions_df (pd.DataFrame): Bridge toll transactions:
            - plaza_name: Bridge toll plaza name
            - time_period: Time period
            - transactions: Number of toll transactions
            
        Transit Data:
        reduced_transit_on_board_df (pd.DataFrame): Transit survey boardings:
            - survey_tech: Technology type from survey
            - survey_operator: Agency name from survey
            - survey_route: Route identifier from survey
            - survey_boardings: Observed boardings
            - florida_threshold: Maximum error threshold percentage
            - standard_route_id: Standardized route ID
            - time_period: Time period (am, daily)
            
        reduced_transit_on_board_access_df (pd.DataFrame): Rail access mode data:
            - operator: Rail operator name
            - boarding_station: Station name
            - access_mode: Access mode (Walk, Park and Ride, etc.)
            - survey_trips: Number of trips by access mode
            - time_period: Time period
            
        observed_bart_boardings_df (pd.DataFrame): BART station-to-station flows:
            - boarding: Origin station name
            - alighting: Destination station name
            - observed: Average daily trips
            
        Census Data:
        ctpp_2012_2016_df (pd.DataFrame): County-to-county work flows:
            - residence_county: Home county
            - work_county: Work county
            - observed_flow: Number of workers
            
        census_2017_zero_vehicle_hhs_df (pd.DataFrame): Zero-vehicle households:
            - geoid: Census geography ID
            - total_households: Total households
            - observed_zero_vehicle_households: Households with no vehicles
            - observed_zero_vehicle_household_share: Share with no vehicles
            Set by: _reduce_census_zero_car_households()

        census_2010_geo_df (pd.DataFrame): Census 2010 block group boundaries:
            - tract: Census tract code
            - county_fips: County FIPS code
            - state_fips: State FIPS code
            - blockgroup: Full block group GEOID
            - geometry: Block group polygon geometry
            Set by: _make_census_geo_crosswalk()

        census_tract_centroids_gdf (gpd.GeoDataFrame): Census tract centroids:
            - tract: Census tract ID
            - geometry: Centroid point geometry
            Set by: _make_tract_centroids()

        reduced_transit_spatial_flow_df (pd.DataFrame): TAZ-to-TAZ transit flows:
            - orig_taz: Origin TAZ
            - dest_taz: Destination TAZ
            - time_period: Time period
            - observed_trips: Number of trips
            - is_loc_in_path, is_exp_in_path, etc.: Technology flags
            Set by: _reduce_observed_rail_flow_summaries()

        reduced_transit_district_flows_by_technology_df (pd.DataFrame): District transit flows:
            - orig_district: Origin district ID (1-34)
            - dest_district: Destination district ID (1-34)
            - tech: Technology (loc, exp, ltr, fry, hvy, com, total)
            - observed: Number of trips using this technology
            Set by: _make_district_to_district_transit_flows_by_technology()

    Constants:
        RELEVANT_PEMS_OBSERVED_YEARS_LIST: [2014, 2015, 2016] - Years to use for PeMS data
        RELEVANT_BRIDGE_TRANSACTIONS_YEARS_LIST: [2014, 2015, 2016] - Years for bridge data
        RELEVANT_BART_OBSERVED_YEARS_LIST: [2014, 2015, 2016] - Years for BART data
        RELEVANT_PEMS_VEHICLE_CLASSES_FOR_LARGE_TRUCK: [6, 7, 8, 9, 10, 11, 12] - Large truck classes
        ohio_rmse_standards_df: ODOT volume-based RMSE thresholds
            Columns: [daily_volume_midpoint, hourly_volume_midpoint, desired_percent_rmse]
        florida_transit_guidelines_df: Florida DOT boarding-based error thresholds
            Columns: [boardings, threshold]
        key_arterials_df: Key arterial locations for validation
            Columns: [name, county, route, direction, pems_station_id]
        bridges_df: Major bridge locations with PeMS stations
            Columns: [name, direction, pems_station_id]
    """
    canonical: Canonical

    observed_dict: dict
    observed_file: str

    ctpp_2012_2016_df: pd.DataFrame
    census_2010_geo_df: pd.DataFrame
    census_2017_zero_vehicle_hhs_df: pd.DataFrame
    census_tract_centroids_gdf: gpd.GeoDataFrame

    RELEVANT_PEMS_OBSERVED_YEARS_LIST = [2014, 2015, 2016]
    RELEVANT_BRIDGE_TRANSACTIONS_YEARS_LIST = [2014, 2015, 2016]
    RELEVANT_PEMS_VEHICLE_CLASSES_FOR_LARGE_TRUCK = [6, 7, 8, 9, 10, 11, 12]

    ohio_rmse_standards_df = pd.DataFrame(
        [
            [250, 24, 200],
            [1000, 100, 100],
            [2000, 200, 62],
            [3000, 300, 54],
            [4000, 400, 48],
            [5000, 500, 45],
            [6250, 625, 42],
            [7750, 775, 39],
            [9250, 925, 36],
            [11250, 1125, 34],
            [13750, 1375, 31],
            [16250, 1625, 30],
            [18750, 1875, 28],
            [22500, 2250, 26],
            [30000, 3000, 24],
            [45000, 4500, 21],
            [65000, 6500, 18],
            [97500, 9750, 12],
        ],
        columns=[
            "daily_volume_midpoint",
            "hourly_volume_midpoint",
            "desired_percent_rmse",
        ],
    )

    reduced_traffic_counts_df = pd.DataFrame(
        {
            "model_link_id": pd.Series(dtype="int"),
            "source": pd.Series(dtype="str"),
            "station_id": pd.Series(dtype="str"),
            "vehicle_class": pd.Series(dtype="str"),
            "time_period": pd.Series(dtype="str"),
            "observed_flow": pd.Series(dtype="float"),
            "odot_flow_category_daily": pd.Series(dtype="str"),
            "odot_flow_category_hourly": pd.Series(dtype="str"),
            "odot_maximum_error": pd.Series(dtype="float"),
            "key_location": pd.Series(dtype="str"),
        }
    )

    key_arterials_df = pd.DataFrame(
        [
            ["San Pablo", "Alameda", 123, "XB", np.nan],
            ["19th Ave", "San Francisco", 1, "XB", np.nan],
            ["El Camino Real", "San Mateo", 82, "XB", np.nan],
            ["El Camino Real", "Santa Clara", 82, "XB", np.nan],
            ["Mission Blvd", "Alameda", 238, "XB", np.nan],
            ["Ygnacio Valley Road", "Contra Costa", "XB", np.nan, np.nan],
            ["Hwy 12", "Solano", 12, "XB", "409485_W"],
            ["Hwy 37", "Marin", 37, "XB", "402038_W"],
            ["Hwy 29", "Napa", 29, "XB", "401796_N"],
            ["CA 128", "Sonoma", 128, "XB", np.nan],
        ],
        columns=[
            "name",
            "county",
            "route",
            "direction",
            "pems_station_id",
        ],
    )

    bridges_df = pd.DataFrame(
        [
            ["Antioch Bridge", "NB", np.nan],
            ["Antioch Bridge", "NB", np.nan],
            ["Benecia-Martinez Bridge", "NB", "402541_N"],
            ["Benecia-Martinez Bridge", "SB", "402412_S"],
            ["Carquinez Bridge", "WB", "401638_W"],
            ["Carquinez Bridge", "EB", np.nan],
            ["Dumbarton Bridge", "WB", "400841_W"],
            ["Dumbarton Bridge", "EB", np.nan],
            ["Richmond-San Rafael Bridge", "WB", np.nan],
            ["Richmond-San Rafael Bridge", "EB", np.nan],
            ["San Francisco-Oakland Bay Bridge", "WB", "404917_W"],
            ["San Francisco-Oakland Bay Bridge", "EB", "404906_E"],
            ["San Mateo-Hayward Bridge", "WB", "400071_W"],
            ["San Mateo-Hayward Bridge", "EB", "400683_E"],
            ["Golden Gate Bridge", "NB", np.nan],
            ["Golden Gate Bridge", "SB", np.nan],
        ],
        columns=["name", "direction", "pems_station_id"],
    )

    observed_bridge_transactions_df: pd.DataFrame

    observed_bart_boardings_df: pd.DataFrame
    RELEVANT_BART_OBSERVED_YEARS_LIST = [2014, 2015, 2016]

    florida_transit_guidelines_df = pd.DataFrame(
        [
            [0, 1.50],  # low end of volume range, maximum error as percentage
            [1000, 1.00],
            [2000, 0.65],
            [5000, 0.35],
            [10000, 0.25],
            [np.inf, 0.20],
        ],
        columns=["boardings", "threshold"],
    )

    reduced_transit_on_board_df = pd.DataFrame(
        {
            "survey_tech": pd.Series(dtype="str"),
            "survey_operator": pd.Series(dtype="str"),
            "survey_route": pd.Series(dtype="str"),
            "survey_boardings": pd.Series(dtype="float"),
        }
    )

    reduced_transit_on_board_access_df: pd.DataFrame
    reduced_transit_spatial_flow_df: pd.DataFrame
    reduced_transit_district_flows_by_technology_df: pd.DataFrame

    def _load_configs(self) -> None:
        """Load observed data configuration from TOML file.

        Reads configuration file containing paths to observed data sources.

        Returns:
            None
        """
        with open(self.observed_file, "r", encoding="utf-8") as toml_file:
            self.observed_dict = toml.load(toml_file)

        return

    def __init__(
        self,
        canonical: Canonical,
        observed_file: str,
        on_board_assign_summary: bool = False,
    ) -> None:
        """Initialize Observed data handler.
        
        Args:
            canonical (Canonical): Canonical naming and crosswalk handler instance
            observed_file (str): Path to observed configuration TOML file containing
                data source file paths and processing parameters
            on_board_assign_summary (bool, optional): If True, only loads transit
                access summaries for on-board assignment validation. Defaults to False.
        
        Returns:
            None
        """
        self.canonical = canonical
        self.observed_file = observed_file
        logging.info(f"Initializing Observed instance with {self.observed_file=}")
        self._load_configs()

        if not on_board_assign_summary:
            self._validate()
        elif on_board_assign_summary:
            self._reduce_observed_rail_access_summaries()

    def _validate(self) -> None:
        """Load and validate all observed data sources.

        Orchestrates loading of all observed data including transit surveys, traffic counts,
        bridge transactions, census data, and BART boardings. Validates that county names
        match expected Bay Area counties.

        Returns:
            None
        """
        if self.reduced_transit_on_board_df.empty:
            self.reduce_on_board_survey()

        if self.reduced_traffic_counts_df.empty:
            self.reduce_traffic_counts()

        self.reduce_bridge_transactions()

        self._reduce_observed_rail_access_summaries()
        self._reduce_observed_rail_flow_summaries()
        self._make_district_to_district_transit_flows_by_technology()
        self._reduce_ctpp_2012_2016()
        self._reduce_census_zero_car_households()
        self._reduce_observed_bart_boardings()

        assert sorted(
            self.ctpp_2012_2016_df.residence_county.unique().tolist()
        ) == sorted(self.canonical.county_names_list)
        assert sorted(self.ctpp_2012_2016_df.work_county.unique().tolist()) == sorted(
            self.canonical.county_names_list
        )

        self._make_census_geo_crosswalk()

        return

    def _join_florida_thresholds(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """Apply Florida DOT error thresholds based on boarding volumes.
        
        Joins Florida DOT guidelines that specify maximum acceptable error percentages
        based on observed boarding ranges (e.g., 150% for 0-1000 boardings, 35% for
        5000-10000 boardings).
        
        Args:
            input_df (pd.DataFrame): Transit boardings data with 'survey_boardings' column
        
        Returns:
            pd.DataFrame: Input data with added 'florida_threshold' column containing
                maximum acceptable error percentage for each route's boarding level
        """
        df = self.florida_transit_guidelines_df.copy()
        df["high"] = df["boardings"].shift(-1)
        df["low"] = df["boardings"]
        df = df.drop(["boardings"], axis="columns")
        df = df.rename(columns={"threshold": "florida_threshold"})

        all_df = (
            input_df[input_df["time_period"] == self.canonical.ALL_DAY_WORD]
            .copy()
            .reset_index(drop=True)
        )
        other_df = (
            input_df[input_df["time_period"] != self.canonical.ALL_DAY_WORD]
            .copy()
            .reset_index(drop=True)
        )
        other_df["florida_threshold"] = np.nan

        vals = all_df.survey_boardings.values
        high = df.high.values
        low = df.low.values

        i, j = np.where((vals[:, None] >= low) & (vals[:, None] <= high))

        return_df = pd.concat(
            [
                all_df.loc[i, :].reset_index(drop=True),
                df.loc[j, :].reset_index(drop=True),
            ],
            axis=1,
        )

        return_df = return_df.drop(["high", "low"], axis="columns")

        return pd.concat([return_df, other_df], axis="rows", ignore_index=True)

    def _join_standard_route_id(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """Join standard route IDs to survey data and adjust boardings for direction.

        Maps survey routes to standard network routes, handling daily and time-of-day
        aggregation differently. For non-rail routes, divides boardings by 2 to account
        for direction since observed records are bidirectional.

        Args:
            input_df (pd.DataFrame): Survey data with columns:
                - survey_operator: Operator name
                - survey_route: Route identifier
                - survey_boardings: Total boardings
                - time_period: Time period

        Returns:
            pd.DataFrame: Input data with added columns:
                - standard_route_id: Standard network route ID
                - standard_line_name: Standard line name
                - daily_line_name: Daily aggregated line name
                - canonical_operator: Canonical operator name
                - survey_boardings: Adjusted for direction (divided by 2 for non-rail)
        """
        df = self.canonical.standard_transit_to_survey_df.copy()

        df["survey_agency"] = df["survey_agency"].map(
            self.canonical.canonical_agency_names_dict
        )
        join_df = df[~df["survey_agency"].isin(self.canonical.rail_operators_vector)].copy()

        join_all_df = join_df.copy()
        join_time_of_day_df = join_df.copy()

        # for daily, aggregate across time of day
        join_all_df = self.canonical.aggregate_line_names_across_time_of_day(
            join_all_df, "standard_line_name"
        )
        join_all_df = (
            join_all_df.groupby(
                [
                    "survey_agency",
                    "survey_route",
                    "standard_route_id",
                    "daily_line_name",
                    "canonical_operator",
                    "standard_route_short_name",
                ]
            )
            .agg({"standard_route_long_name": "first"})
            .reset_index()
        )

        join_all_df["standard_line_name"] = "N/A -- Daily Record"
        join_all_df["standard_headsign"] = "N/A -- Daily Record"

        all_df = pd.merge(
            input_df[input_df["time_period"] == self.canonical.ALL_DAY_WORD],
            join_all_df,
            how="left",
            left_on=["survey_operator", "survey_route"],
            right_on=["survey_agency", "survey_route"],
        )

        # by time of day
        join_time_of_day_df = (
            join_time_of_day_df.groupby(
                [
                    "survey_agency",
                    "survey_route",
                    "standard_route_id",
                    "standard_line_name",
                    "canonical_operator",
                    "standard_route_short_name",
                ]
            )
            .agg({"standard_route_long_name": "first", "standard_headsign": "first"})
            .reset_index()
        )

        df = (
            join_time_of_day_df["standard_line_name"]
            .str.split(pat="_", expand=True)
            .copy()
        )
        df["time_period"] = df[3].str.lower()
        join_time_of_day_df = pd.concat(
            [join_time_of_day_df, df["time_period"]], axis="columns"
        )

        join_time_of_day_df = self.canonical.aggregate_line_names_across_time_of_day(
            join_time_of_day_df, "standard_line_name"
        )

        time_of_day_df = pd.merge(
            input_df[input_df["time_period"] != self.canonical.ALL_DAY_WORD],
            join_time_of_day_df,
            how="left",
            left_on=["survey_operator", "survey_route", "time_period"],
            right_on=["survey_agency", "survey_route", "time_period"],
        )

        # observed records are not by direction, so we need to scale the boardings by 2 when the cases match
        time_of_day_df["survey_boardings"] = np.where(
            (time_of_day_df["standard_route_id"].isna())
            | (time_of_day_df["survey_operator"].isin(self.canonical.rail_operators_vector)),
            time_of_day_df["survey_boardings"],
            time_of_day_df["survey_boardings"] / 2.0,
        )

        return pd.concat([all_df, time_of_day_df], axis="rows", ignore_index=True)

    def reduce_on_board_survey(self):
        """Reduce on-board survey data to route-level boardings.
        
        Processes raw on-board survey data, applies canonical naming, adds Florida DOT
        thresholds, and joins with standard route IDs. For non-rail routes, boardings
        are divided by 2 to account for direction.
        
        Results stored in reduced_transit_on_board_df with columns:
            - survey_tech: Technology type
            - survey_operator: Canonical operator name
            - survey_route: Route identifier
            - survey_boardings: Total boardings (adjusted for direction)
            - time_period: Time period (am, daily)
            - florida_threshold: Error threshold percentage
            - standard_route_id: Standard network route ID
            - standard_line_name: Standard line name
            - daily_line_name: Daily aggregated line name
        
        Returns:
            None
        """

        if not self.canonical.canonical_agency_names_dict:
            self.canonical._make_canonical_agency_names_dict()

        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["transit"]["on_board_survey_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["transit"]["on_board_survey_file"]

        logging.info(f"Reading {file_root / in_file}")
        tps_df = pd.read_csv(file_root / in_file)
        
        tps_df["survey_operator"] = tps_df["survey_operator"].map(
            self.canonical.canonical_agency_names_dict
        )
        tps_df = self._join_florida_thresholds(tps_df)
        tps_df = self._join_standard_route_id(tps_df)
        self.reduced_transit_on_board_df = tps_df
        logging.debug(f"self.reduced_transit_on_board_df:\n{self.reduced_transit_on_board_df}")

        return

    def _reduce_census_zero_car_households(self):
        """Process Census ACS zero-vehicle household data.
        
        Reads 2017 American Community Survey data on vehicle availability by block group
        and calculates zero-vehicle household shares.
        
        Results stored in census_2017_zero_vehicle_hhs_df with columns:
            - geoid: Census block group identifier
            - total_households: Total households in block group
            - observed_zero_vehicle_households: Count of zero-vehicle households
            - observed_zero_vehicle_household_share: Share of households with no vehicles
        
        Returns:
            None
        """
        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["census"]["vehicles_by_block_group_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["census"]["vehicles_by_block_group_file"]

        logging.info(f"Reading {in_file}")
        acs_vehs_df = pd.read_csv(in_file, skiprows=1, usecols=[
            "id", "Estimate!!Total", "Estimate!!Total!!No vehicle available"
        ])
        logging.debug(f"acs_vehs_df:\n{acs_vehs_df}")

        acs_vehs_df.rename(columns={
            "id": "geoid",
            "Estimate!!Total": "total_households",
            "Estimate!!Total!!No vehicle available": "observed_zero_vehicle_households",
        }, inplace=True)

        acs_vehs_df["observed_zero_vehicle_household_share"] = (
            acs_vehs_df["observed_zero_vehicle_households"] / acs_vehs_df["total_households"]
        )

        self.census_2017_zero_vehicle_hhs_df = acs_vehs_df
        logging.debug(f"self.census_2017_zero_vehicle_hhs_df:\n{self.census_2017_zero_vehicle_hhs_df}")
        return

    def _reduce_observed_bart_boardings(self):
        """Process observed BART station-to-station flows.
        
        Reads BART origin-destination data and applies canonical station names.
        Takes average of years 2014-2016.
        
        Results stored in observed_bart_boardings_df with columns:
            - boarding: Origin station canonical name
            - alighting: Destination station canonical name
            - observed: Average daily trips between stations
        
        Returns:
            None
        """
        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["transit"]["bart_boardings_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["transit"]["bart_boardings_file"]

        logging.info(f"Reading {in_file}")
        bart_df = pd.read_csv(in_file)

        assert "BART" in self.canonical.canonical_station_names_dict.keys()

        bart_df["boarding"] = bart_df["orig_name"].map(
            self.canonical.canonical_station_names_dict["BART"]
        )
        bart_df["alighting"] = bart_df["dest_name"].map(
            self.canonical.canonical_station_names_dict["BART"]
        )
        logging.debug(f"bart_df:\n{bart_df}")

        bart_df = bart_df[bart_df.year.isin(self.RELEVANT_BART_OBSERVED_YEARS_LIST)]
        logging.debug(f"bart_df:\n{bart_df}")

        bart_df = (
            bart_df.groupby(["boarding", "alighting"])
            .agg({"avg_trips": "mean"})
            .reset_index()
        )
        bart_df = bart_df.rename(columns={"avg_trips": "observed"})
        logging.debug(f"bart_df:\n{bart_df}")

        self.observed_bart_boardings_df = bart_df
        logging.debug(f"self.observed_bart_boardings_df:\n{self.observed_bart_boardings_df}")

        return

    def _make_census_geo_crosswalk(self) -> None:
        """Load census geography shapefile and calculate tract centroids.

        Reads 2010 census block group boundaries, calculates tract centroids, and
        renames columns to standard names.

        Returns:
            None
        """
        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["census"]["census_geographies_shapefile"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["census"]["census_geographies_shapefile"]

        logging.info(f"Reading {in_file}")
        self.census_2010_geo_df = gpd.read_file(in_file)
        logging.debug(f"self.census_2010_geo_df:\n{self.census_2010_geo_df}")
        logging.debug(f"self.census_2010_geo_df.crs:\n{self.census_2010_geo_df.crs}")

        self._make_tract_centroids(self.census_2010_geo_df)

        self.census_2010_geo_df.rename(columns={
            "TRACTCE10": "tract",
            "COUNTYFP10": "county_fips",
            "STATEFP10": "state_fips",
            "GEOID10": "blockgroup",
        }, inplace=True)

        return

    def _make_tract_centroids(
        self, census_blockgroup_gdf: gpd.GeoDataFrame
    ) -> None:
        """Calculate census tract centroids from block group geometries.

        Dissolves block groups to tract level, computes centroids in UTM projection,
        and converts back to WGS84 lat/long. Stores result in census_tract_centroids_gdf.

        Args:
            census_blockgroup_gdf (gpd.GeoDataFrame): Block group geometries with
                STATEFP10, COUNTYFP10, TRACTCE10 columns

        Returns:
            None

        TODO: Why do we need this?
        """
        # https://epsg.io/26910
        EPSG_NAD83_UTM_ZONE_10M = 26910
        # https://epsg.io/4326
        EPSG_WGS84 = 4326

        # This is to resolve errors like this:
        #  PROJ_ERROR: hgridshift: could not find required grid(s).
        #  PROJ_ERROR: pipeline: Pipeline: Bad step definition: proj=hgridshift (File not found or invalid)
        # Enable PROJ network capabilities
        pyproj.network.set_network_enabled(True)

        tract_gdf = census_blockgroup_gdf.copy()
        # consolidate ids into full geoid
        # TODO: I removed code to remove leading zero from this field because this is wrong! :p
        tract_gdf["tract"] = tract_gdf["STATEFP10"] + tract_gdf["COUNTYFP10"] + tract_gdf["TRACTCE10"]
        tract_gdf = tract_gdf.dissolve(by="tract").reset_index(drop=False)
        tract_gdf = tract_gdf[["tract","geometry"]]
        logging.debug(f"Dissolved census geographies to tracts:\n{tract_gdf}")

        # project to coordinate system appropriate for Northern California and create centroids
        tract_gdf['centroid_geometry'] = tract_gdf.to_crs(EPSG_NAD83_UTM_ZONE_10M).centroid
        # drop original geometry and keep centroid geometry instead
        tract_gdf.set_geometry(col="centroid_geometry", inplace=True)
        tract_gdf.drop(columns="geometry", inplace=True)

        # back to lat/long
        tract_gdf = tract_gdf.to_crs(EPSG_WGS84)
        self.census_tract_centroids_gdf = tract_gdf.rename(columns={"centroid_geometry":"geometry"})

        logging.debug(f"Calculated centroids:\n{self.census_tract_centroids_gdf}")
        logging.debug(f"{type(self.census_tract_centroids_gdf)=}")
        return

    def _reduce_ctpp_2012_2016(self):
        """Process CTPP county-to-county commute flows.
        
        Reads Census Transportation Planning Products (CTPP) 2012-2016 data for
        county-to-county worker flows in the nine Bay Area counties.
        
        Results stored in ctpp_2012_2016_df with columns:
            - residence_county: Home county name
            - work_county: Work county name
            - observed_flow: Number of workers making this commute
        
        Returns:
            None
        """
        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["census"]["ctpp_2012_2016_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["census"]["ctpp_2012_2016_file"]

        logging.info(f"Reading {in_file}")
        ctpp_df = pd.read_csv(in_file, skiprows=5, header=None, names=[
            "residence_county","work_county","observed_flow","margin_of_error"]
        )
        logging.debug(f"ctpp_df:\n{ctpp_df}")
        ctpp_df.drop(columns="margin_of_error", inplace=True)
        ctpp_df["residence_county"] = ctpp_df["residence_county"].str.replace(
            " County, California", ""
        )
        # drop bottom rows with metadata
        ctpp_df = ctpp_df.loc[ctpp_df.observed_flow.notna()]

        ctpp_df["work_county"] = ctpp_df["work_county"].str.replace(" County, California", "")
        ctpp_df["observed_flow"] = ctpp_df["observed_flow"].str.replace(",", "").astype(int)

        # filldown residence_county
        ctpp_df["residence_county"] = ctpp_df["residence_county"].ffill()

        self.ctpp_2012_2016_df = ctpp_df
        logging.debug(f"self.ctpp_2012_2016_df:\n{self.ctpp_2012_2016_df}")

        return

    def _reduce_observed_rail_access_summaries(self) -> None:
        """Load observed rail station access mode summaries.

        Reads pre-processed rail access mode data and applies canonical operator
        and station names.

        Returns:
            None
        """
        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["transit"]["reduced_access_summary_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["transit"]["reduced_access_summary_file"]

        logging.info(f"Reading {in_file}")
        df = pd.read_csv(in_file)

        assert "operator" in df.columns
        df["operator"] = df["operator"].map(self.canonical.canonical_agency_names_dict)

        assert "boarding_station" in df.columns
        for operator in self.canonical.canonical_station_names_dict.keys():
            df.loc[df["operator"] == operator, "boarding_station"] = df.loc[
                df["operator"] == operator, "boarding_station"
            ].map(self.canonical.canonical_station_names_dict[operator])

        self.reduced_transit_on_board_access_df = df.copy()
        logging.debug(f"self.reduced_transit_on_board_access_df:\n{self.reduced_transit_on_board_access_df}")

        return

    def _reduce_observed_rail_flow_summaries(self) -> None:
        """Load observed rail spatial flow summaries.

        Reads pre-processed rail TAZ-to-TAZ flow data from survey sources.

        Returns:
            None
        """
        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["transit"]["reduced_flow_summary_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["transit"]["reduced_flow_summary_file"]

        self.reduced_transit_spatial_flow_df = pd.read_csv(in_file)
        logging.debug(f"self.reduced_transit_spatial_flow_df:\n{self.reduced_transit_spatial_flow_df}")

        return

    def _make_district_to_district_transit_flows_by_technology(self) -> None:
        """Aggregate observed transit flows to district level by technology.

        Converts TAZ-to-TAZ transit flows to planning district-to-district flows,
        separated by transit technology (local bus, express bus, light rail, ferry,
        heavy rail, commuter rail). Only processes AM period data.

        Returns:
            None
        """
        o_df = self.reduced_transit_spatial_flow_df.copy()
        o_df = o_df[o_df["time_period"] == "am"].copy()

        tm2_district_dict = self.canonical.taz_to_district_df.set_index("taz")[
            "district"
        ].to_dict()
        o_df["orig_district"] = o_df["orig_taz"].map(tm2_district_dict)
        o_df["dest_district"] = o_df["dest_taz"].map(tm2_district_dict)

        for prefix in self.canonical.transit_technology_abbreviation_dict.keys():
            o_df["{}".format(prefix.lower())] = (
                o_df["is_{}_in_path".format(prefix.lower())] * o_df["observed_trips"]
            )

        agg_dict = {"observed_trips": "sum"}
        for prefix in self.canonical.transit_technology_abbreviation_dict.keys():
            agg_dict["{}".format(prefix.lower())] = "sum"

        sum_o_df = (
            o_df.groupby(["orig_district", "dest_district"]).agg(agg_dict).reset_index()
        )

        long_sum_o_df = sum_o_df.melt(
            id_vars=["orig_district", "dest_district"],
            var_name="tech",
            value_name="observed",
        )
        long_sum_o_df["tech"] = np.where(
            long_sum_o_df["tech"] == "observed_trips", "total", long_sum_o_df["tech"]
        )

        self.reduced_transit_district_flows_by_technology_df = long_sum_o_df.copy()

        return

    def _join_tm2_node_ids(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """Convert standard network node IDs to EMME node IDs.

        Joins A and B node IDs with standard-to-EMME node crosswalk to add
        emme_a_node_id and emme_b_node_id columns.

        Args:
            input_df (pd.DataFrame): Data with A and B columns (standard node IDs)

        Returns:
            pd.DataFrame: Input data with added emme_a_node_id and emme_b_node_id columns
        """
        df = input_df.copy()
        nodes_df = self.canonical.standard_to_emme_node_crosswalk_df.copy()

        df = (
            pd.merge(df, nodes_df, how="left", left_on="A", right_on="model_node_id")
            .rename(
                columns={
                    "emme_node_id": "emme_a_node_id",
                }
            )
            .drop(["model_node_id"], axis=1)
        )

        df = (
            pd.merge(df, nodes_df, how="left", left_on="B", right_on="model_node_id")
            .rename(
                columns={
                    "emme_node_id": "emme_b_node_id",
                }
            )
            .drop(["model_node_id"], axis=1)
        )

        return df

    def _join_ohio_standards(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """Apply Ohio DOT RMSE standards based on traffic volumes.
        
        Joins ODOT guidelines that specify maximum acceptable RMSE percentages based
        on observed traffic volume ranges. Higher volumes have stricter error tolerances.
        
        Args:
            input_df (pd.DataFrame): Traffic count data with 'observed_flow' column
        
        Returns:
            pd.DataFrame: Input data with added columns:
                - odot_flow_category_daily: Daily volume range (e.g., "1000-2000")
                - odot_flow_category_hourly: Hourly volume range
                - odot_maximum_error: Maximum acceptable percent RMSE
        """
        df = self.ohio_rmse_standards_df.copy()

        df["upper"] = (
            df["daily_volume_midpoint"].shift(-1) - df["daily_volume_midpoint"]
        ) / 2
        df["lower"] = (
            df["daily_volume_midpoint"].shift(1) - df["daily_volume_midpoint"]
        ) / 2
        df["low"] = df["daily_volume_midpoint"] + df["lower"]
        df["low"] = np.where(df["low"].isna(), 0, df["low"])
        df["high"] = df["daily_volume_midpoint"] + df["upper"]
        df["high"] = np.where(df["high"].isna(), np.inf, df["high"])

        df = df.drop(
            ["daily_volume_midpoint", "hourly_volume_midpoint", "upper", "lower"],
            axis="columns",
        )

        df = df.rename(
            columns={
                "desired_percent_rmse": "odot_maximum_error",
            }
        )

        vals = input_df.observed_flow.values
        high = df.high.values
        low = df.low.values

        i, j = np.where((vals[:, None] >= low) & (vals[:, None] <= high))

        return_df = pd.concat(
            [
                input_df.loc[i, :].reset_index(drop=True),
                df.loc[j, :].reset_index(drop=True),
            ],
            axis=1,
        )

        return_df["low_hourly"] = return_df["low"] / 10
        return_df["high_hourly"] = return_df["high"] / 10
        return_df["odot_flow_category_daily"] = (
            return_df["low"].astype("str") + "-" + return_df["high"].astype("str")
        )
        return_df["odot_flow_category_hourly"] = (
            return_df["low_hourly"].astype("str")
            + "-"
            + return_df["high_hourly"].astype("str")
        )

        return_df = return_df.drop(
            ["high", "low", "high_hourly", "low_hourly"], axis="columns"
        )

        return return_df

    def _identify_key_arterials_and_bridges(
        self, input_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Flag traffic counts at key arterials and bridge locations.

        Joins with key arterials and bridges lookup tables to add location names
        and directions for important facilities.

        Args:
            input_df (pd.DataFrame): Traffic count data with station_id column

        Returns:
            pd.DataFrame: Input data with added columns:
                - key_location_name: Arterial or bridge name (if applicable)
                - key_location_direction: Direction (if applicable)
        """
        df1 = self.key_arterials_df.copy()
        df2 = self.bridges_df.copy()
        df = pd.concat([df1, df2])[["name", "direction", "pems_station_id"]].rename(
            columns={
                "name": "key_location_name",
                "direction": "key_location_direction",
                "pems_station_id": "station_id",
            }
        )
        df = df.dropna().copy()
        out_df = pd.merge(input_df, df, how="left", on="station_id")

        return out_df

    def _reduce_truck_counts(self) -> pd.DataFrame:
        """Process PeMS large truck counts.

        Filters PeMS data for large truck vehicle classes (6-12), computes median
        flows across years 2014-2016 and by time period.

        Returns:
            pd.DataFrame: Large truck counts with columns:
                - station_id: PeMS station identifier
                - type: Station type
                - time_period: Time period
                - observed_flow: Median large truck volume
                - vehicle_class: "Large Trucks"
        """
        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["roadway"]["pems_truck_count_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["roadway"]["pems_truck_count_file"]

        logging.info(f"Reading {in_file}")
        in_df = pd.read_csv(in_file)

        df = in_df[in_df.year.isin(self.RELEVANT_PEMS_OBSERVED_YEARS_LIST)].copy()
        df = df[
            df["Vehicle.Class"].isin(self.RELEVANT_PEMS_VEHICLE_CLASSES_FOR_LARGE_TRUCK)
        ].copy()
        df = df.rename(
            columns={
                "Census.Station.Identifier": "station",
                "Freeway.Direction": "direction",
                "Station.Type": "type",
            }
        )
        df["station_id"] = df["station"].astype(str) + "_" + df["direction"]
        df = df[["station_id", "type", "year", "time_period", "median_flow"]].copy()

        return_df = (
            df.groupby(["station_id", "type", "time_period"])["median_flow"]
            .median()
            .reset_index()
        )
        return_df = return_df.rename(columns={"median_flow": "observed_flow"})

        return_df["vehicle_class"] = self.canonical.LARGE_TRUCK_VEHICLE_TYPE_WORD

        return return_df

    def reduce_bridge_transactions(self):
        """Prepare observed bridge toll transaction data.
        
        Processes bridge toll transaction data, aggregates to time periods and daily
        totals. Takes median across years 2014-2016.
        
        Results stored in observed_bridge_transactions_df with columns:
            - plaza_name: Bridge toll plaza name
            - time_period: Time period (am, pm, md, ev, ea, daily)
            - transactions: Number of toll transactions (median across years)
        
        Returns:
            None
        """
        time_period_dict = {
            "3 am": "ea",
            "4 am": "ea",
            "5 am": "ea",
            "6 am": "am",
            "7 am": "am",
            "8 am": "am",
            "9 am": "am",
            "10 am": "md",
            "11 am": "md",
            "Noon": "md",
            "1 pm": "md",
            "2 pm": "md",
            "3 pm": "pm",
            "4 pm": "pm",
            "5 pm": "pm",
            "6 pm": "pm",
            "7 pm": "ev",
            "8 pm": "ev",
            "9 pm": "ev",
            "10 pm": "ev",
            "11 pm": "ev",
            "Mdnt": "ev",
            "1 am": "ev",
            "2 am": "ev",
        }

        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file =pathlib.Path(self.observed_dict["roadway"]["bridge_transactions_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["roadway"]["bridge_transactions_file"]

        logging.info(f"Reading {in_file}")
        in_df = pd.read_csv(in_file)
        df = in_df[
            in_df["Year"].isin(self.RELEVANT_BRIDGE_TRANSACTIONS_YEARS_LIST)
        ].copy()
        df = df[df["Lane Designation"] == "all"].copy()
        hourly_median_df = (
            df.groupby(["Plaza Name", "Hour beginning"])["transactions"]
            .agg("median")
            .reset_index()
        )
        daily_df = (
            hourly_median_df.groupby(["Plaza Name"])["transactions"]
            .agg("sum")
            .reset_index()
            .rename(columns={"Plaza Name": "plaza_name"})
        )
        daily_df["time_period"] = self.canonical.ALL_DAY_WORD

        df = hourly_median_df.copy()
        df["time_period"] = hourly_median_df["Hour beginning"].map(time_period_dict)
        time_period_df = (
            df.groupby(["Plaza Name", "time_period"])["transactions"]
            .agg("sum")
            .reset_index()
            .rename(columns={"Plaza Name": "plaza_name"})
        )
        self.observed_bridge_transactions_df = pd.concat([time_period_df, daily_df]).reset_index(drop=True)
        logging.debug(f"self.observed_bridge_transactions_df:\n{self.observed_bridge_transactions_df}")
        return

    def reduce_traffic_counts(self):
        """Prepare observed traffic count data for acceptance comparisons.
        
        Processes PeMS and Caltrans traffic counts, computes daily totals, joins with
        network link crosswalk, and applies ODOT error standards based on volume ranges.
        
        Results stored in reduced_traffic_counts_df with columns:
            - emme_a_node_id, emme_b_node_id: Network node IDs
            - station_id: Count station identifier
            - type: Station type (mainline, ramp, etc.)
            - time_period: Time period (hourly or daily)
            - observed_flow: Traffic volume
            - vehicle_class: Vehicle type (All Vehicles, Large Trucks)
            - source: Data source (PeMS, Caltrans)
            - odot_flow_category_daily/hourly: Volume range category
            - odot_maximum_error: Maximum acceptable percent error
            - key_location_name/direction: Key location if applicable
        
        Returns:
            None
        """
        pems_df = self._reduce_pems_counts()
        caltrans_df = self._reduce_caltrans_counts()
        self.reduced_traffic_counts_df = pd.concat([pems_df, caltrans_df])

        return

    def _reduce_pems_counts(self) -> pd.DataFrame:
        """Prepare PeMS traffic counts for acceptance comparisons.

        Processes PeMS station data for years 2014-2016, computes median flows across years,
        aggregates to daily totals, joins with network link crosswalk, applies ODOT error
        standards, and identifies key arterial/bridge locations.

        Returns:
            pd.DataFrame: Processed traffic counts with columns:
                - emme_a_node_id, emme_b_node_id: Network node IDs
                - station_id: PeMS station identifier
                - type: Station type (mainline, ramp, etc.)
                - time_period: Time period
                - observed_flow: Median traffic volume
                - vehicle_class: All Vehicles or Large Trucks
                - source: "PeMS"
                - odot_flow_category_daily/hourly: Volume range
                - odot_maximum_error: Maximum acceptable percent error
                - key_location_name/direction: Key location if applicable
        """

        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["roadway"]["pems_traffic_count_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["roadway"]["pems_traffic_count_file"]

        logging.info(f"Reading {in_file}")
        pems_df = pd.read_csv(in_file)
        pems_df = pems_df[pems_df.year.isin(self.RELEVANT_PEMS_OBSERVED_YEARS_LIST)]
        pems_df["station_id"] = pems_df["station"].astype(str) + "_" + pems_df["direction"]
        pems_df = pems_df[["station_id", "type", "year", "time_period", "median_flow"]]
        logging.debug(f"pems_df:\n{pems_df}")

        median_across_years_all_vehs_df = (
            pems_df.groupby(["station_id", "type", "time_period"])["median_flow"]
            .median()
            .reset_index()
        )
        median_across_years_all_vehs_df = median_across_years_all_vehs_df.rename(
            columns={"median_flow": "observed_flow"}
        )
        median_across_years_all_vehs_df[
            "vehicle_class"
        ] = self.canonical.ALL_VEHICLE_TYPE_WORD
        logging.debug(f"median_across_years_all_vehs_df:\n{median_across_years_all_vehs_df}")
        logging.debug(f"vehicle_class:\n{median_across_years_all_vehs_df['vehicle_class'].value_counts()}")

        median_across_years_trucks_df = self._reduce_truck_counts()
        logging.debug(f"median_across_years_trucks_df:\n{median_across_years_trucks_df}")
        logging.debug(f"vehicle_class:\n{median_across_years_trucks_df['vehicle_class'].value_counts()}")

        median_across_years_df = pd.concat(
            [median_across_years_all_vehs_df, median_across_years_trucks_df],
            axis="rows",
            ignore_index=True,
        )
        logging.debug(f"median_across_years_df:\n{median_across_years_df}")

        all_day_df = (
            median_across_years_df.groupby(["station_id", "type", "vehicle_class"])[
                "observed_flow"
            ]
            .sum()
            .reset_index()
        )
        all_day_df["time_period"] = self.canonical.ALL_DAY_WORD
        logging.debug(f"all_day_df:\n{all_day_df}")

        out_df = pd.concat(
            [all_day_df, median_across_years_df], axis="rows", ignore_index=True
        )

        out_df = pd.merge(
            self.canonical.pems_to_link_crosswalk_df, out_df, how="left", on="station_id"
        )

        out_df = self._join_tm2_node_ids(out_df)

        # take median across multiple stations on same link
        median_df = (
            out_df.groupby(
                [
                    "A",
                    "B",
                    "emme_a_node_id",
                    "emme_b_node_id",
                    "time_period",
                    "vehicle_class",
                ]
            )["observed_flow"]
            .agg("median")
            .reset_index()
        )
        join_df = out_df[
            [
                "emme_a_node_id",
                "emme_b_node_id",
                "time_period",
                "station_id",
                "type",
                "vehicle_class",
            ]
        ].copy()
        return_df = pd.merge(
            median_df,
            join_df,
            how="left",
            on=["emme_a_node_id", "emme_b_node_id", "time_period", "vehicle_class"],
        ).reset_index(drop=True)

        # return_df = return_df.rename(columns = {"model_link_id" : "standard_link_id"})
        return_df = self._join_ohio_standards(return_df)
        return_df = self._identify_key_arterials_and_bridges(return_df)

        return_df["source"] = "PeMS"

        logging.debug(f"Returning\n{return_df}")
        return return_df

    def _reduce_caltrans_counts(self) -> pd.DataFrame:
        """Prepare Caltrans AADT traffic counts for acceptance comparisons.

        Processes Caltrans 2015 Annual Average Daily Traffic (AADT) data, separates
        all vehicles from large trucks, converts two-way AADT to one-way flow, joins
        with network nodes, and applies ODOT error standards.

        Returns:
            pd.DataFrame: Processed Caltrans counts with columns:
                - A, B: Standard network node IDs
                - emme_a_node_id, emme_b_node_id: EMME node IDs
                - station_id: Caltrans station identifier
                - observed_flow: AADT / 2 (one-way)
                - vehicle_class: All Vehicles or Large Trucks
                - time_period: "daily"
                - source: "Caltrans"
                - odot_flow_category_daily/hourly: Volume range
                - odot_maximum_error: Maximum acceptable percent error
        """
        file_root = pathlib.Path(self.observed_dict["remote_io"]["obs_folder_root"])
        in_file = pathlib.Path(self.observed_dict["roadway"]["caltrans_count_file"])

        # handle absolute or relative in_file
        if not in_file.is_absolute():
            in_file = file_root / self.observed_dict["roadway"]["caltrans_count_file"]

        logging.info(f"Reading {in_file}")
        caltrans_df = pd.read_csv(in_file, usecols=[
            "2015 Traffic AADT",
            "2015 Truck AADT",
            "IModelNODE",
            "JModelNODE",
            "Calt_stn2",
        ])
        caltrans_df.rename(columns={
            "IModelNODE": "A",
            "JModelNODE": "B",
            "Calt_stn2": "station_id",
        }, inplace=True)
        logging.debug(f"caltrans_df:\n{caltrans_df}")

        caltrans_cars_df = (
            caltrans_df.copy()
            .rename(columns={"2015 Traffic AADT": "observed_flow"})
            .drop(columns=["2015 Truck AADT"])
        )
        caltrans_cars_df["vehicle_class"] = self.canonical.ALL_VEHICLE_TYPE_WORD

        caltrans_trucks_df = (
            caltrans_df.copy()
            .rename(columns={"2015 Truck AADT": "observed_flow"})
            .drop(columns=["2015 Traffic AADT"])
        )
        caltrans_trucks_df["vehicle_class"] = self.canonical.LARGE_TRUCK_VEHICLE_TYPE_WORD

        caltrans_df = pd.concat([caltrans_cars_df, caltrans_trucks_df]).reset_index(drop=True)
        caltrans_df = caltrans_df[caltrans_df["observed_flow"].notna()]

        # convert to one-way flow
        caltrans_df["observed_flow"] = caltrans_df["observed_flow"] / 2.0

        caltrans_df = self._join_tm2_node_ids(caltrans_df)
        caltrans_df["time_period"] = self.canonical.ALL_DAY_WORD
        caltrans_df["source"] = "Caltrans"

        caltrans_df = self._join_ohio_standards(caltrans_df)
        logging.debug(f"final caltrans_df:\n{caltrans_df}")

        return caltrans_df
