from pathlib import Path
import pandas as pd
import geopandas as gpd
import os
import sys

RAW_DATA_DIR = Path(r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\raw_data\enrollment")
MAZ_TAZ_DIR = Path(__file__).parent.parent / "maz_taz" / "shapefiles"
ANALYSIS_CRS = "EPSG:26910"

BAY_AREA_COUNTIES = [
    "Alameda",
    "Contra Costa",
    "Marin",
    "Napa",
    "San Francisco",
    "San Mateo",
    "Santa Clara",
    "Solano",
    "Sonoma"
]


def load_public_schools():
    """
    Loads public school data, filters to active schools in Bay Area counties, and derives enrollment vars.
    Returns:
        GeoDataFrame: Public schools with enrollment vars and geometry.
    """
    pubschls = gpd.read_file(RAW_DATA_DIR / "SchoolSites2425.gpkg").to_crs(ANALYSIS_CRS)
    pubschls = pubschls[pubschls["Status"]=="Active"]

    # Filter to Bay Area
    pubschls = pubschls[pubschls["CountyName"].isin(BAY_AREA_COUNTIES)]

    # Derive enrollment cols, ensuring adult school enrollment is tabulated seperately
    pubschls["publicEnrollGradeKto8"] = pubschls.apply(
        lambda row: row[["GradeTK", "GradeKG", "Grade1", "Grade2", "Grade3", "Grade4", "Grade5", "Grade6", "Grade7", "Grade8"]].sum() if row["SchoolLevel"] != "Adult Education" else 0,
        axis=1
    )

    pubschls["publicEnrollGrade9to12"] = pubschls.apply(
        lambda row: row[["Grade9", "Grad10", "Grade11", "Grade12"]].sum() if row["SchoolLevel"] != "Adult Education" else 0,
        axis=1
    )

    pubschls["AdultSchEnrl"] = pubschls.apply(
        lambda row: row["EnrollTotal"] if row["SchoolLevel"] == "Adult Education" else 0,
        axis=1
    )

    # Reduce to necessary cols
    pubschls = pubschls[[#"CDSCode", 
                        "publicEnrollGradeKto8", "publicEnrollGrade9to12", "AdultSchEnrl", "geometry"]]
    
    return pubschls


def load_private_schools():
    """
    Loads private school data, filters to Bay Area counties, and derives enrollment vars.
    Returns:
        GeoDataFrame: Private schools with enrollment vars and geometry.
    """
    prvschls = gpd.read_file(RAW_DATA_DIR / "cprs_2324.gpkg").to_crs(ANALYSIS_CRS)

    # Filter to Bay Area
    prvschls = prvschls[prvschls["County"].isin(BAY_AREA_COUNTIES)]

    # Derive enrollment cols
    prvschls["privateEnrollGradeKto8"] = prvschls[
        ["EnrollK", "Enroll01", "Enroll02", "Enroll03", "Enroll04", "Enroll05", "Enroll06", "Enroll07", "Enroll08"]
    ].sum(axis=1)
    prvschls["privateEnrollGrade9to12"] = prvschls[["Enroll09", "Enroll10", "Enroll11", "Enroll12"]].sum(axis=1)

    # Reduce to necessary cols
    prvschls = prvschls[[#"CDS", 
                        "privateEnrollGradeKto8", "privateEnrollGrade9to12", "geometry"]]
    
    return prvschls


def load_colleges():
    """
    Loads college location and seperate enrollment data, merges them, assigns college types, and derives enrollment vars.
    Returns:
        GeoDataFrame: Colleges with enrollment vars by type and geometry.
    """
    # Location and enrollment are seperate - start with locations
    colleges = gpd.read_file(RAW_DATA_DIR / "bayarea_postsec_2324.shp").to_crs(ANALYSIS_CRS)
    colleges["UNITID"] = colleges["UNITID"].astype(int)

    # Now enrollment
    college_enroll = pd.read_csv(RAW_DATA_DIR / "postsec_enroll_2324.csv")
    college_enroll = college_enroll.rename(columns={
        "Institutional category (HD2023)": "type", # Shorten long var names
        "Total 12-month unduplicated headcount (DRVEF122024)": "enrollment",
        "Control of institution (HD2023)": "control"
    })
    # Merge and make sure we keep only institutions with enrollment (a few administrative office locations make there way in otherwise)
    colleges = colleges.merge(college_enroll, left_on="UNITID", right_on="UnitID", how="inner", validate="1:1")
    colleges = colleges[colleges["enrollment"] > 0]

    # Distinguish college types based on the existing TM2 categories
    def assign_college_type(row):
        if row["type"] in [1, 2]: # Baccalaureate and above
            return "collegeEnroll" 
        elif row["type"] in [3, 4] and row["control"] == 1: # Associate's/certificates AND public 
            return "comm_coll_enroll"
        else:
            return "otherCollegeEnroll"
    colleges["college_type"] = colleges.apply(assign_college_type, axis=1)

    # Spread the college type variable so we have enrollment by collegeEnroll, comm_coll_enroll, and otherCollegeEnroll
    colleges = colleges.pivot_table(
        index=["UNITID", "geometry"], 
        columns="college_type", 
        values="enrollment", 
        fill_value=0
    ).reset_index().drop(columns="UNITID")

    colleges = gpd.GeoDataFrame(colleges, geometry="geometry", crs=ANALYSIS_CRS)

    print("Sum of collegeEnroll:", colleges["collegeEnroll"].sum())
    print("Sum of comm_coll_enroll:", colleges["comm_coll_enroll"].sum())
    print("Sum of otherCollegeEnroll:", colleges["otherCollegeEnroll"].sum())

    return colleges


def load_maz_shp(use_maz_orig=False):
    """
    Loads the MAZ shapefile. Uses the original MAZ file if use_maz_orig is True, otherwise loads the default version 2.5 shapefile.
    Returns:
        GeoDataFrame: MAZ polygons with MAZ_NODE, TAZ_NODE, and geometry columns.
    """
    print(f"Loading maz shapefile...")
    if use_maz_orig == True:
        maz = gpd.read_file(r"M:\Data\GIS layers\TM2_maz_taz_v2.2\mazs_TM2_v2_2.shp").to_crs(ANALYSIS_CRS)
        maz = maz.rename(columns={"maz": "MAZ_NODE", "taz": "TAZ_NODE"})
    else:
        maz_shp = os.path.join(MAZ_TAZ_DIR, "mazs_TM2_2_5.shp")
        maz = gpd.read_file(maz_shp).to_crs(ANALYSIS_CRS)

    maz = maz[["MAZ_NODE", "TAZ_NODE", "geometry"]]

    print(f"maz dtypes:\n{maz.dtypes}")

    return maz



def spatial_join_schools_to_maz(schools, maz): # This is copied from job_counts and should be standardized to join any point features to maz
    """
    Spatially joins school to MAZ polygons.  Performed in two steps:
    1. Attempts to join each school to a MAZ using the 'within' predicate (i.e., schools located inside a MAZ).
    2. For schools not matched in the first step, assigns them to the nearest MAZ using a nearest neighbor spatial join.
    Parameters:
        schools (GeoDataFrame): school locations.
        maz (GeoDataFrame): MAZ polygons.
    Returns:
        DataFrame: A DataFrame of schools with MAZ assignments.
    """

    # Spatial join 1 - within predicate
    print(f"Number of school records before spatial join to maz: {len(schools)}")
    schools = gpd.sjoin(schools, maz, how="left", predicate="within")
    schools = schools.drop(columns=['index_right'])
    print(f"Number of school records after spatial join to maz: {len(schools)}")
    print(f"Number of schools successfully joined to a MAZ:", schools["MAZ_NODE"].notnull().sum())

    # Spatial join 2 - nearest for any leftovers
    schools_missed = schools[schools["MAZ_NODE"].isnull()]
    if len(schools_missed) > 0:

        print(f"Number of schools unsuccessfully joined to a MAZ: {len(schools_missed)}")

        # Ensure the missed subset is still a gdf; drop any null MAZ/TAZ columns left over from the first attempt
        schools_missed = gpd.GeoDataFrame(schools_missed, geometry="geometry", crs=ANALYSIS_CRS).drop(columns=["MAZ_NODE", "TAZ_NODE"])
        
        print(f"Joining unmatched schools to nearest MAZ...")
        schools_nearest = gpd.sjoin_nearest(schools_missed, maz, how="left")
        print(f"Number of unmatched schools after nearest join operation:", schools_nearest["MAZ_NODE"].isnull().sum())
        schools_nearest = pd.DataFrame(schools_nearest)

        # Filter schools that successfully joined to maz in first step and concatenate results
        schools = pd.DataFrame(schools[schools["MAZ_NODE"].notnull()])
        schools = pd.concat([schools, schools_nearest])
        print(f"Total number schools now joined to a maz: ", schools["MAZ_NODE"].notnull().sum())
        schools = schools.drop(columns=['index_right'])

    return schools


def summarize_enrollment_by_maz(schools_maz, maz):
    """
    Summarize enrollment counts by MAZ.
    Groups by MAZ_NODE and sums all numeric columns.
    Returns a DataFrame with MAZ_NODE and summed enrollment columns.
    """
    ENROLL_COLS = ['publicEnrollGradeKto8', 'privateEnrollGradeKto8', 'EnrollGradeKto8',
    'publicEnrollGrade9to12', 'privateEnrollGrade9to12', 'EnrollGrade9to12', 
         'comm_coll_enroll', 'collegeEnroll',  'otherCollegeEnroll', 'AdultSchEnrl']

    # Only sum columns that are present in schools_maz and listed in ENROLL_COLS
    present_enroll_cols = [col for col in ENROLL_COLS if col in schools_maz.columns]
    enrollment_maz = schools_maz.groupby("MAZ_NODE", as_index=False)[present_enroll_cols].sum()

    # Concatenate maz with schools and maz w/o schools so we have a full set of maz
    maz["MAZ_NODE"] = maz["MAZ_NODE"].astype(int)
    # maz["TAZ_NODE"] = maz["TAZ_NODE"].astype(int)
    schools_maz["MAZ_NODE"] = schools_maz["MAZ_NODE"].astype(int)
    # schools_maz["TAZ_NODE"] = schools_maz["TAZ_NODE"].astype(int)

    print(f"maz dtypes: \n{maz.dtypes}")
    print(f"schools with maz dtypes: \n{schools_maz.dtypes}")

    maz_no_schools = maz[~maz["MAZ_NODE"].isin(schools_maz["MAZ_NODE"])].drop(columns="geometry")
    enrollment_maz = pd.concat([enrollment_maz, maz_no_schools], ignore_index=True)

    enrollment_maz["MAZ_NODE"] = enrollment_maz["MAZ_NODE"].astype(int)
    # enrollment_maz["TAZ_NODE"] = enrollment_maz["TAZ_NODE"].astype(int)
    print(f"enrollment maz after concat dtypes: \n{enrollment_maz.dtypes}")

    # Ensure we have the same set of maz ids post process 
    maz_id_in = set(maz["MAZ_NODE"])
    enrollment_maz_ids = set(enrollment_maz["MAZ_NODE"])

    # Ensure enrollment_maz has the same set of MAZ_NODE as maz_id_in
    if enrollment_maz_ids == maz_id_in:
        print("enrollment_maz has the same set of MAZ_NODE ids as maz_id_in.")
    else:
        print("enrollment_maz does NOT have the same set of MAZ_NODE ids as maz_id_in.")
        print("Missing in enrollment_maz:", maz_id_in - enrollment_maz_ids)
        print("Extra in enrollment_maz:", enrollment_maz_ids - maz_id_in)
    

    return enrollment_maz

def get_enrollment_maz(write=False, use_maz_orig=False):
    """
    Loads public, private, and college data, spatially joins to MAZ, summarizes enrollment by MAZ, and merges results.
    Optionally writes output to CSV.
    Returns:
        DataFrame: Enrollment counts by MAZ for all school types.
    """
    # Load
    pubschls = load_public_schools()
    prvschls = load_private_schools()
    colleges = load_colleges()
    maz = load_maz_shp(use_maz_orig=use_maz_orig)

    # Spatial join schools to maz
    pubschls_maz = spatial_join_schools_to_maz(pubschls, maz=maz)
    privschls_maz = spatial_join_schools_to_maz(prvschls, maz=maz)
    colleges_maz = spatial_join_schools_to_maz(colleges, maz=maz)

    # Collapse enrollment by maz
    pub_enroll_maz = summarize_enrollment_by_maz(pubschls_maz, maz)
    priv_enroll_maz = summarize_enrollment_by_maz(privschls_maz, maz)
    college_enroll_maz = summarize_enrollment_by_maz(colleges_maz, maz)

    # Combine
    enroll_maz = pub_enroll_maz.merge(
        priv_enroll_maz, on="MAZ_NODE", how="left", validate="1:1"
    ).merge(
        college_enroll_maz, on="MAZ_NODE", how="left", validate="1:1"
    ).fillna(0)

    # Add public + private enroll cols EnrollGradeKto8, EnrollGrade9to12
    enroll_maz["EnrollGradeKto8"] = enroll_maz["publicEnrollGradeKto8"] + enroll_maz["privateEnrollGradeKto8"]
    enroll_maz["EnrollGrade9to12"] = enroll_maz["publicEnrollGrade9to12"] + enroll_maz["privateEnrollGrade9to12"]

    # Sort by maz
    enroll_maz["MAZ_NODE"] = enroll_maz["MAZ_NODE"].sort_values()

    # Make enroll_maz a GeoDataFrame by merging with maz geometry
    # enroll_maz = enroll_maz.merge(maz[["MAZ_NODE", "geometry"]], on="MAZ_NODE", how="left")
    # enroll_maz = gpd.GeoDataFrame(enroll_maz, geometry="geometry", crs=ANALYSIS_CRS)

    if write==True:
        if use_maz_orig:
            # OUT_FILE = r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\enrollment_maz_v2_2_2023.gpkg"
            OUT_FILE = r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\enrollment_maz_v2_2_2023.csv"
        else:
            # OUT_FILE = r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\enrollment_maz_v2_5_2023.gpkg"
            OUT_FILE = r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\enrollment_maz_v2_5_2023.csv"
        print(f"Writing enrollment MAZ data to: {OUT_FILE}")
        # enroll_maz.to_file(OUT_FILE)
        enroll_maz.to_csv(OUT_FILE)
    return enroll_maz

def main():
    use_maz_orig = "--use-maz-orig" in sys.argv
    write = "--write" in sys.argv
    enroll_maz = get_enrollment_maz(write=write, use_maz_orig=use_maz_orig)

if __name__ == "__main__":
    main()