from pathlib import Path
import pandas as pd
import geopandas as gpd
import os

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

    return colleges


def load_maz_shp():
    """
    Load MAZ shapefile.  Currently hard coded to version2_5.
    
    Returns:
        gpd.GeoDataFrame: MAZ polygons with MAZ/TAZ ids
    """
    print(f"Loading maz shapefile...")
    maz_shp = os.path.join(MAZ_TAZ_DIR, "mazs_TM2_2_5.shp")
    maz = gpd.read_file(maz_shp).to_crs(ANALYSIS_CRS)
    maz = maz[["MAZ_NODE", "TAZ_NODE", "geometry"]]

    return maz

maz = load_maz_shp()


def spatil_join_schools_to_maz(schools, maz): # This is copied from job_counts and should be standardized to join any point features to maz
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
    numeric_cols = schools_maz.select_dtypes(include='number').columns
    enrollment_maz = schools_maz.groupby("MAZ_NODE")[numeric_cols].sum()


    # Concatenate maz with jobs and maz w/o jobs so we have a full set of maz
    maz_no_schools = maz[~maz["MAZ_NODE"].isin(schools_maz["MAZ_NODE"])].drop(columns="geometry")
    enrollment_maz = pd.concat([enrollment_maz, maz_no_schools]).reset_index(drop=True)

    return enrollment_maz

def get_enrollment_maz(write=False):
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
    maz = load_maz_shp()

    # Spatial join schools to maz
    pubschls_maz = spatil_join_schools_to_maz(pubschls, maz=maz)
    privschls_maz = spatil_join_schools_to_maz(prvschls, maz=maz)
    colleges_maz = spatil_join_schools_to_maz(colleges, maz=maz)

    # Collapse enrollment by maz
    pub_enroll_maz = summarize_enrollment_by_maz(pubschls_maz, maz)
    priv_enroll_maz = summarize_enrollment_by_maz(privschls_maz, maz)
    college_enroll_maz = summarize_enrollment_by_maz(colleges_maz, maz)

    # Combine
    enroll_maz = pub_enroll_maz.merge(
        priv_enroll_maz, on=["MAZ_NODE", "TAZ_NODE"], how="left"
    ).merge(
        college_enroll_maz, on=["MAZ_NODE", "TAZ_NODE"], how="left"
    ).fillna(0)

    # Add public + private enroll cols EnrollGradeKto8, EnrollGrade9to12
    enroll_maz["EnrollGradeKto8"] = enroll_maz["publicEnrollGradeKto8"] + enroll_maz["privateEnrollGradeKto8"]
    enroll_maz["EnrollGrade9to12"] = enroll_maz["publicEnrollGrade9to12"] + enroll_maz["privateEnrollGrade9to12"]

    if write==True:
        OUT_FILE = r"E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse\enrollment_maz_2023_v1.csv"
        enroll_maz.to_csv(OUT_FILE)        
    return enroll_maz

def main():
    enroll_maz = get_enrollment_maz()

if __name__ == "__main__":
    main()