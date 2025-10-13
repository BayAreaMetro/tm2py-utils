USAGE = """

MAZ and TAZ checker.

Reads the definition of MAZs and TAZs in blocks_mazs_tazs.csv

The following verifications are performed
  - Verifies that there are not multiple tazs or counties per maz
  - Verifies that there are not multiple counties per taz
  - Verifies that all blocks with nonzero land area are assigned a maz/taz
  - Verifies that all blocks with zero land area are not assigned a maz/taz
  - Verifies that maz and taz numbers are numbered according to county ranges:
   https://bayareametro.github.io/tm2py/inputs/#county-node-numbering-system
  - Verifies that mazs are not nested within other mazs

Also, given the following issue:
  - If there are mazs with multiple block groups, tracts
The script attempts to fix them with move_small_block_to_neighbor()
  - For each small (<25 percent land area) blocks in the maz
  - Looks at neighboring blocks in the same block group
  - If there are any with a maz, picks the one with the most border length in common
  - Move the original block to inherit the maz/taz of this neighbor

If the mazs are aok, then given the following issue:
  - If there are tazs with multiple tracts
The script attempts to fix them with split_taz_for_tract()
  - For each taz that spans multiple tracts, if the smallest portion in a tract is
    non-trivial (>10 percent of land), then split the taz on the tract boundary,
    creating new tazs.

This draft update is saved into blocks_mazs_tazs_v{version}.csv

  Notes:
  - Block "06 075 017902 1009" (maz 10186, taz 592) is the little piece of Alameda island that the Census 2010
    calls San Francisco.  Left in SF as its own maz.

  - Blocks "06 075 980401 100[1,2,3]" (maz 16084, taz 287) are the Farallon Islands.  It's a standalone maz but the
    taz spans tracts because it's not worth it's own taz.

  - Block "06 081 608002 2004" (maz 112279, taz 100178) spans a block group boundary but not doing so would split up
    and island with two blocks.

  - Blocks "06 075 017902 10[05,80]" (maz 16495, taz 327) is a tiny sliver that's barely land so not worth
    making a new maz, so that maz includes a second tract (mostly water)

  - Blocks "06 041 104300 10[17,18,19]" (maz 810745, taz 800095) spans a block group/tract boundary but the're a
    tiny bit on the water's edge and moving them would separate them from the rest of the maz/taz

  - Blocks "06 041 122000 100[0,1,2]" (maz 813480, taz 800203) are a tract (San Quentin Rehabilitation Center)
    that is inside another tract so keeping as is so as not to create a donut hole maz

  - Block "06 013 301000 3000" (maz 410304, taz 400507) is a block that Census 2010 claims has no land area ("Webb Tract")
    but appears to be a delta island so it's an exception to the zero-land/non-zero water blocks having a maz/taz

Input files:
  - M:\Data\Census\Geography\\tl_2020_06_tabblock10\\tl_2020_06_tabblock10_9CBA.shp
  - blocks crosswalk file (input arg)
  - CENSUS_BLOCK_NEIGHBOR_CSV
  - CENSUS_TRACT_PUMA
  - SUPERDISTRICT_FILE
Output files:
  - shapefiles\\mazs_TM2_{version}.shp with columns:
    MAZ_NODE, COUNTYFP10, ALAND10, AWATER10, blockcount, TAZ_NODE, partcount, PERIM_MI, AREA_SQMI, psq_overa, acres, MAZ_X, MAZ_Y, MAZ_SEQ

  - shapefiles\\tazs_TM2_{version}.shp with columns:
    TAZ_NODE, COUNTYFP10, ALAND10, AWATER10, blockcount, mazcount, partcount, PERIM_MI, AREA_SQMI, psq_overa, acres, TAZ_X, TAZ_Y, TAZ_SEQ

  - mazs_tazs_county_tract_PUMA_{version}.csv where MAZ_NODE & MAZ_SEQ are unique; columns:
    MAZ_NODE,MAZ_SEQ,TAZ_NODE,TAZ_SEQ,COUNTY,county_name,COUNTYFP10,TRACTCE10,PUMA10,DistID,DistName,MAZ_X,MAZ_Y

  - tazs_county_tract_PUMA_{version}.csv where TAZ_NODE & TAZ_SEQ are unique; columns:
    TAZ_NODE,TAZ_SEQ,COUNTY,county_name,COUNTYFP10,TRACTCE10,PUMA10,DistID,DistName,TAZ_X,TAZ_Y

"""
EXEMPT_MAZ = [     16495, 112279, 810745, 813480]
EXEMPT_TAZ = [287,                800095, 800203]

EXEMPT_NOLAND_BLOCK = ["060133010003000"]

# These blocks were exempted because they were blocks with primarily water
EXEMPT_LAND_BLOCK = ['060014273002003','060014301021079','060014415031031','060133010003003','060133010003023','060133010003025','060133010003026',
                     '060133010003050','060133010003064','060133010003071','060133010003074','060133010003078','060133010003085','060133010003130',
                     '060133010003139','060133010003175','060133010003178','060133020061000','060133020061005','060133020062000','060133020081009',
                     '060133020081015','060133020081017','060133040021008','060133040021114','060133040021138','060133040042000','060133040052005',
                     '060133050003058','060133551071007','060133551071018','060133800001025','060133800001029','060133800002068','060411250001013',
                     '060411262002014','060411262002020','060411322003000','060411330002014','060750601001000','060750607001016','060816061001000',
                     '060816080043002','060816103034021','060816135012045','060855119111005','060952521021065','060952527026251','060952531083023',
                     '060952535001147','060952535001211','060971501003015','060971517002024','060971538011005']


import argparse, csv, logging, os, pathlib, sys, numpy, shutil
import pandas
import geopandas
import pyproj
import shapely

# The script should be run from the tm2py-utils directory
WORKSPACE          = pathlib.Path(".")
CROSSWALK_ROOT     = "blocks_mazs_tazs"

# Set directory to the Census Block Version
CENSUS_BLOCK_SHP   = pathlib.Path("M:\\Data\\Census\\Geography\\tl_2020_06_tabblock10\\tl_2020_06_tabblock10_9CBA.shp")
CENSUS_BLOCK_COLS  = ["STATEFP10", "COUNTYFP10", "TRACTCE10", "BLOCKCE10", "GEOID10", "ALAND10", "AWATER10"]

CENSUS_BLOCK_NEIGHBOR_CSV = "E:\\GitHub\\tm2\\tm2py-utils\\tm2py_utils\\inputs\\maz_taz\\tl_2020_06_tabblock10_9CBA_neighbors.csv"
CENSUS_TRACT_PUMA  = pathlib.Path("M:\\Data\\Census\\Geography\\tl_2010_06_puma10\\2010_Census_Tract_to_2010_PUMA.txt")

SUPERDISTRICT_FILE = "E:\\GitHub\\tm2\\tm2py-utils\\tm2py_utils\\inputs\\maz_taz\\shapefiles\\travel_model_super_districts.shp"

MAZS_SHP           = "mazs_TM2"
TAZS_SHP           = "tazs_TM2"

# Default CRS for analysis
LOCAL_CRS_FEET = "EPSG:2227"
WGS84_CRS = "EPSG:4326"
FEET_PER_MILE = 5280

#Number of Iteration for moving mazs/tazs
NUM_ITER = 5


def move_small_block_to_neighbor(
        blocks_maz_df: pandas.DataFrame, 
        blocks_neighbor_df: pandas.DataFrame,
        maz_multiple_geo_df: pandas.DataFrame, 
        bigger_geo: str,
        crosswalk_out_df: pandas.DataFrame
    ) -> int:
    """
    The simplest fix is to move small blocks to a neighboring maz/taz.
    Returns number of blocks moved.
    """
    blocks_moved = 0
    logging.info(f"move_small_block_to_neighbor for {bigger_geo}")
    for maz,row in maz_multiple_geo_df.iterrows():
        logging.info(f"Attempting to fix maz {maz:6d}")

        # these we'll leave; see Notes
        if maz in EXEMPT_MAZ:
            logging.info("Special exception -- skipping")
            continue

        # if it spans more than 3, leave it for now
        if row[bigger_geo] > 3:
            logging.info(f"Spans more than 3 {bigger_geo} elements {row[bigger_geo]} -- skipping")
            continue

        # if there's three, 25% or less of land area is ok to move
        # if two, 32% or less of land area
        if row[bigger_geo] == 3:
            pct_threshold = 0.25
        else:
            pct_threshold = 0.32

        # let's look at the blocks in this maz in the blocks_maz_df
        this_maz_blocks_df = blocks_maz_df.loc[ blocks_maz_df.maz == maz]
        logging.debug(f"\n{this_maz_blocks_df}")
        this_maz_aland = this_maz_blocks_df.ALAND10.sum()

        # check if the odd one or two out are smaller than the threshold
        # Looping through the blocks in this maz and determining whichs are smaller than the threshold and can be moved to a neighboring block
        this_maz_grouped = this_maz_blocks_df.groupby(bigger_geo)
        for name,group in this_maz_grouped:
            land_pct = group.ALAND10.sum()/this_maz_aland
            logging.debug(f"group {name} has {len(group)} rows and {100.0*land_pct:.1f} percent of land")
            logging.debug(f"\n{group}")

            # is this land area too much to move?
            if land_pct > pct_threshold: continue

            # these blocks are candidates for moving -- let's look at where to move to
            for block_index,block_row in group.iterrows():

                # find the neighboring blocks
                this_block_id = block_row["GEOID10"]
                this_block_maz = block_row["maz"]
                # look at neighbors for candidates
                this_block_neighbors = blocks_neighbor_df.loc[blocks_neighbor_df.src_GEOID10 == this_block_id].copy()
                # only neighbors in the same block group with maz/taz set and maz differs
                this_block_neighbors = this_block_neighbors.loc[ (this_block_neighbors.nbr_GEOID10_BG == block_row["GEOID10_BG"]) &
                                                                 (this_block_neighbors.maz != 0) &
                                                                 (this_block_neighbors.maz != this_block_maz)]

                if len(this_block_neighbors) == 0:
                    logging.debug("  No neighbors in same block group with maz/taz")
                    continue

                # pick the neighboring block with the most length adjacent
                this_block_neighbors.sort_values(by="LENGTH", ascending=False, inplace=True)
                # print(this_block_neighbors)
                this_neighbor_id = this_block_neighbors.nbr_GEOID10.iloc[0]
                logging.info(f"  => block {this_block_id} picking up maz/taz from neighboring block {this_neighbor_id}")

                # look up the neighbor's maz and taz to inherit
                match_row = crosswalk_out_df.loc[ crosswalk_out_df.GEOID10 == this_neighbor_id]
                crosswalk_out_df.loc[ crosswalk_out_df.GEOID10 == this_block_id, "maz"] = match_row["maz"].iloc[0]
                crosswalk_out_df.loc[ crosswalk_out_df.GEOID10 == this_block_id, "taz"] = match_row["taz"].iloc[0]
                blocks_moved += 1
                logging.debug(f"\n{crosswalk_out_df.loc[ (crosswalk_out_df.GEOID10 == this_block_id)|(crosswalk_out_df.GEOID10 == this_neighbor_id) ]}")

    logging.info(f"====> moved {blocks_moved} blocks to neighbor")
    return blocks_moved

def find_next_unused_taz_id(crosswalk_out_df: pandas.DataFrame, taz:int) -> int:
    """
    Find the next unused taz id after taz
    """
    # this is a little wasteful but ok
    taz_ids = crosswalk_out_df["taz"].drop_duplicates() # series
    # also I'm assuming these are easy to find
    unused_taz_id = taz + 1
    while True:
        if unused_taz_id in taz_ids.values:
            unused_taz_id += 1
        else:
            logging.debug(f"find_next_unused_taz_id for {taz:6d} returning {unused_taz_id:6d}")
            return unused_taz_id
    return -1

def split_taz_for_tract(
        blocks_maz_df: pandas.DataFrame,
        taz_multiple_geo_df: pandas.DataFrame, 
        crosswalk_out_df: pandas.DataFrame
    ) -> int:
    """
    The simplest fix for TAZs that span tract boundaries is to split the TAZ.
    Since there aren't that many, let's do that so long as the tract portions are non-trivial (>10%)
    """
    tazs_split = 0
    logging.info("splitting taz for tract")
    for taz,row in taz_multiple_geo_df.iterrows():
        logging.info(f"Attempting to fix taz {taz:6d}")

        # if it spans more than 3, leave it for now
        if row[bigger_geo] > 3:
            logging.info(f"Spans more than 3 {bigger_geo} elements {row[bigger_geo]} -- skipping")
            continue

        # let's look at the blocks in this taz in the blocks_maz_df
        this_taz_blocks_df = blocks_maz_df.loc[ blocks_maz_df.taz == taz]
        this_taz_aland = this_taz_blocks_df.ALAND10.sum()

        # check if the chunks are all pretty big
        this_taz_grouped = this_taz_blocks_df.groupby(bigger_geo)
        groups_aland = this_taz_grouped.agg({"ALAND10":"sum"})
        groups_aland["ALAND10_pct"] = groups_aland["ALAND10"]/this_taz_aland
        logging.debug(f"\n{groups_aland}")

        # if too small, punt
        if groups_aland["ALAND10_pct"].min() < 0.10:
            logging.info("Tract/taz portion too small -- skipping")
            continue

        first = True
        for name,group in this_taz_grouped:
            land_pct = group.ALAND10.sum()/this_taz_aland
            # logging.debug("\n{0}".format(group))

            # don't touch the first tract
            if first:
                logging.info(f"  group {name} has {len(group):3d} rows and {100.0*land_pct:.1f} percent of land")
                first = False
                continue

            # move the mazs in this tract to a new taz
            new_taz_id = find_next_unused_taz_id(crosswalk_out_df, taz)

            # convert these mazs into the new taz
            crosswalk_out_df.loc[ (crosswalk_out_df.taz==taz)&(crosswalk_out_df[bigger_geo]==name), "taz"] = new_taz_id
            logging.info(f"  group {name} has {len(group):3d} rows and {100.0*land_pct:.1f} percent of land => new taz {new_taz_id:6d}")
            tazs_split += 1

    return tazs_split

def dissolve_into_shapefile(blocks_maz_gdf: geopandas.GeoDataFrame, maz_or_taz: str):
    """
    Dissolve the blocks into final MAZ/TAZ shapefile
    """
    try:
        # create maz_or_taz_gdf 
        if maz_or_taz == 'maz':
            agg_field = {'ALAND10':'sum', 'AWATER10':'sum', 'GEOID10':'count', 'taz':'first'}
        else:
            agg_field = {'ALAND10':'sum', 'AWATER10':'sum', 'GEOID10':'count', 'maz':'count'}
        
        maz_or_taz_gdf = blocks_maz_gdf.dissolve(by = [maz_or_taz, 'COUNTYFP10'], aggfunc = agg_field, as_index = False)
        logging.debug(f"blocks_maz_gdf.crs:{blocks_maz_gdf.crs}")
        logging.debug(f"blocks_maz_gdf:\n{blocks_maz_gdf}")
        # Calculate partcount -number of geometries in the multi
        maz_or_taz_gdf['partcount'] = maz_or_taz_gdf.count_geometries()
        logging.info(f'Calculated part count for {maz_or_taz}s')

        # convert to local projected CRS first
        maz_or_taz_gdf.to_crs(LOCAL_CRS_FEET, inplace=True)
        # Add perimeter in miles and area in square miles
        maz_or_taz_gdf['PERIM_MI'] = maz_or_taz_gdf.geometry.length / FEET_PER_MILE
        maz_or_taz_gdf['AREA_SQMI']  = maz_or_taz_gdf.geometry.area / (FEET_PER_MILE*FEET_PER_MILE)
        logging.info(f'Calculated perimeter length for {maz_or_taz}s')

        # Add perimeter squared over area, or isoperimetric ratio
        # https://en.wikipedia.org/wiki/Isoperimetric_ratio - measure of how far from circular a shape is
        maz_or_taz_gdf['psq_overa'] = maz_or_taz_gdf['PERIM_MI'] * maz_or_taz_gdf['PERIM_MI'] / maz_or_taz_gdf['AREA_SQMI']
        logging.info(f'Calculated perim*perim/area for {maz_or_taz}s')

        # Add acres from ALAND10
        SQUARE_METERS_PER_ACRE = 4046.86
        maz_or_taz_gdf['acres'] = maz_or_taz_gdf['ALAND10'] / SQUARE_METERS_PER_ACRE
        logging.info(f'Calculated acres for {maz_or_taz}s')

        # Delete maz/taz = 0 since it is not a real maz/taz 
        maz_or_taz_gdf = maz_or_taz_gdf[maz_or_taz_gdf[maz_or_taz] != 0]

        # Rename fields for clarity
        maz_or_taz_gdf.rename(columns = {'GEOID10': 'blockcount'},inplace = True)
        if maz_or_taz == 'taz': maz_or_taz_gdf.rename(columns = {'maz': 'mazcount'}, inplace = True)

        # Create centroids for mazs and tazs
        logging.info(f"Creating centroids for {maz_or_taz}")
        # create centroid in LOCAL_CRS_FEET and then transform back to WGS84
        maz_or_taz_gdf["centroid"] = maz_or_taz_gdf.geometry.centroid.to_crs(WGS84_CRS)
        # transform the boundary geometry back to WGS84
        maz_or_taz_gdf.to_crs(WGS84_CRS, inplace=True)
        logging.debug(f"maz_or_taz_gdf with crs {WGS84_CRS}:\n{maz_or_taz_gdf}")

        # save coords
        maz_or_taz_gdf[f'{maz_or_taz.upper()}_X'] = maz_or_taz_gdf['centroid'].x
        maz_or_taz_gdf[f'{maz_or_taz.upper()}_Y'] = maz_or_taz_gdf['centroid'].y
        maz_or_taz_gdf.drop(columns=['centroid'],inplace=True)

        # rename to [MAZ,TAZ]_NODE or and create sequential version, [MAZ,TAZ]_SEQ
        maz_or_taz_gdf.sort_values(by=maz_or_taz, inplace=True)
        maz_or_taz_gdf.rename(columns={maz_or_taz:f"{maz_or_taz.upper()}_NODE"}, inplace=True)
        if maz_or_taz == "maz":
            maz_or_taz_gdf.rename(columns={"taz":f"TAZ_NODE"}, inplace=True)

        maz_or_taz_gdf = maz_or_taz_gdf.reset_index(drop=True)
        maz_or_taz_gdf[f"{maz_or_taz.upper()}_SEQ"] = maz_or_taz_gdf.index + 1
        logging.debug(f"Final version of maz_or_taz_gdf for {maz_or_taz} len={len(maz_or_taz_gdf):,}:\n{maz_or_taz_gdf}")

        # verify maz/taz numbering alignment with https://bayareametro.github.io/tm2py/inputs/#county-node-numbering-system
        county_check_df = maz_or_taz_gdf.groupby("COUNTYFP10").agg({
            f'{maz_or_taz.upper()}_NODE':['min','max'],
            f'{maz_or_taz.upper()}_SEQ':['min','max']
        })
        logging.info(f"county_check_df for {maz_or_taz}:\n{county_check_df}")

        # Save the dissolved maz_or_taz_gdf
        shapefile_name = MAZS_SHP if maz_or_taz=="maz" else TAZS_SHP
        output_dir = WORKSPACE / "shapefiles"
        output_dir.mkdir(exist_ok=True)
        
        version_shp = VERSION.replace(".", "_")
        output_file = output_dir / f"{shapefile_name}_{version_shp}.shp"
        logging.info(f"Writing {maz_or_taz}s into {output_file}")
        maz_or_taz_gdf.to_file(output_file)
        return maz_or_taz_gdf

    except Exception as err:
        logging.error(err)
        raise err
      
if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument("crosswalk_csv", help = 'Block/MAZ/TAZ Crosswalk file to build the latest crosswalk from', metavar= 'blocks_mazs_tazs.csv' )
    parser.add_argument("version",help = 'Set the version of the MAZ/TAZs')
    args = parser.parse_args()

    VERSION = args.version
    CROSSWALK_CSV = pathlib.Path(args.crosswalk_csv)
    LOG_FILE = f"maz_taz_checker_{VERSION}.log"
    
    pandas.options.display.width = None
    pandas.options.display.max_columns = None
    pandas.options.display.float_format = '{:.2f}'.format
    # This is to resolve errors like this:
    #  PROJ_ERROR: hgridshift: could not find required grid(s).
    #  PROJ_ERROR: pipeline: Pipeline: Bad step definition: proj=hgridshift (File not found or invalid)
    # Enable PROJ network capabilities
    pyproj.network.set_network_enabled(True)

    # create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'))
    logger.addHandler(ch)
    # file handler
    fh = logging.FileHandler(LOG_FILE, mode='w')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'))
    logger.addHandler(fh)
    print(f"Writing log file to {LOG_FILE}")
    
     #######################################################
    # Create a GeoDataFrame from the 2010 block shapefile
    # and converting dataframe to the default analysis CRS
    blocks_maz_shp = geopandas.read_file(CENSUS_BLOCK_SHP)
    blocks_maz_shp.to_crs(WGS84_CRS,  inplace=True)
    logging.info(f"Reading {CENSUS_BLOCK_SHP}; Read {len(blocks_maz_shp):,} rows")
    logging.debug(blocks_maz_shp.head())

    logging.info(f"Reading crosswalk file: {CROSSWALK_CSV}")
    crosswalk_df = pandas.read_csv(CROSSWALK_CSV)

    # drop the Farallon Islands
    FARALLON_ISLANDS = [
        "060759804011000",
        "060759804011001",
        "060759804011002",
        "060759804011003",
    ]
    blocks_maz_shp = blocks_maz_shp.loc[ ~blocks_maz_shp.GEOID10.isin(FARALLON_ISLANDS)]
    block_count = len(blocks_maz_shp)

    for x in range(1,NUM_ITER + 1,1):
        logging.info(f"Starting iteration {x} of {NUM_ITER}")
        try:        

            ########################################################
            # Join the census blocks to the maz/taz crosswalk - this needs to be included in the looping
            crosswalk_df['GEOID10'] = crosswalk_df['GEOID10'].astype(str).str.zfill(15)  # Ensure GEOID10 is string with leading zeros
            blocks_maz_gdf = blocks_maz_shp.merge(crosswalk_df, on = 'GEOID10')
            block_join_count = len(blocks_maz_gdf)
            logging.info(f"Join block shapefile to crosswalk csv resulting in {block_join_count} rows")

            # assert we didn't lose rows in the join
            assert(block_count==block_join_count)

            # verify
            ## Printing out field columns and types
            logging.debug(f"blocks_maz_gdf.type:{type(blocks_maz_gdf)}")
            logging.debug(f"blocks_maz_gdf.dtypes:\n{blocks_maz_gdf.dtypes}")
            
            # create Dataframe from merged GeoDataFrame
            blocks_maz_df = pandas.DataFrame(blocks_maz_gdf) #, columns = fields)
            logging.info(f"blocks_maz_df has length {len(blocks_maz_df):,}")

            # the GEOID10 = state(2) + county(3) + tract(6) + block(4)
            # block group is the firist digit of the block number
            blocks_maz_df["GEOID10_BG"]     = blocks_maz_df["GEOID10"].str[:12]
            blocks_maz_df["GEOID10_TRACT"]  = blocks_maz_df["GEOID10"].str[:11]
            blocks_maz_df["GEOID10_COUNTY"] = blocks_maz_df["GEOID10"].str[:5]
            logging.debug(f"\n{blocks_maz_df.head()}")

            # this dataframe is the one we'll modify and output 
            crosswalk_out_df = blocks_maz_df[["GEOID10","maz","taz","GEOID10_TRACT"]]

            #####################################################
            # Create a table from the 2010 block neighbor mapping
            # For use in move_small_block_to_neighbor()
            logging.info(f"Reading {CENSUS_BLOCK_NEIGHBOR_CSV}")
            blocks_neighbor_df = pandas.read_csv(CENSUS_BLOCK_NEIGHBOR_CSV, dtype= {"src_GEOID10":str, "nbr_GEOID10":str, "LENGTH":float, "NODE_COUNT":int})
            blocks_neighbor_df["nbr_GEOID10_BG"] = blocks_neighbor_df["nbr_GEOID10"].str[:12]
            # get the maz/taz for these neighbors
            blocks_neighbor_df = pandas.merge(
                left    =blocks_neighbor_df,
                right   =blocks_maz_df[["GEOID10","maz","taz"]],
                how     ="left",
                left_on ="nbr_GEOID10",
                right_on="GEOID10")
            logging.debug(f"blocks_neighbor_df has length {len(blocks_neighbor_df)}")
            logging.debug(f"\n{blocks_neighbor_df.head()}")

        except Exception as err:
            logging.error(err.args[0])

        logging.info(f"Number of unique GEOID10: {blocks_maz_df.GEOID10.nunique()}")
        logging.info(f"  Min: {blocks_maz_df.GEOID10.min()}")
        logging.info(f"  Max: {blocks_maz_df.GEOID10.max()}")
        logging.info("")

        # maz 0 aren't real -- these are blocks without mazs
        # split the blocks up
        blocks_nomaz_df = blocks_maz_df.loc[blocks_maz_df.maz == 0]
        blocks_maz_df   = blocks_maz_df.loc[blocks_maz_df.maz != 0]

        logging.info(f"Number of unique maz: {blocks_maz_df.maz.nunique()}")
        logging.info(f"   Min: {blocks_maz_df.maz.min()}")
        logging.info(f"   Max: {blocks_maz_df.maz.max()}")
        logging.info("")

        logging.info(f"Number of unique taz: {blocks_maz_df.taz.nunique()}")
        logging.info(f"   Min: {blocks_maz_df.taz.min()}")
        logging.info(f"   Max: {blocks_maz_df.taz.max()}")
        logging.info("")

        # if maz is zero, taz should be zero
        assert(blocks_nomaz_df.taz == 0).all()
        # if maz is not zero, taz should not be zero
        assert(blocks_maz_df.taz != 0).all()

        #####################################################   
        # verify one taz/BLOCK GROUP/TRACT/COUNTY per unique maz
        # error for taz/COUNTY
        # warn/log for BLOCK GROUP/TRACT
        blocks_moved = 0
        for bigger_geo in ["taz","GEOID10_COUNTY","GEOID10_TRACT","GEOID10_BG"]:
            maz_geo_df = blocks_maz_df[["maz",bigger_geo]].groupby(["maz"]).agg("nunique")
            maz_multiple_geo_df = maz_geo_df.loc[ (maz_geo_df[bigger_geo] > 1) & ( maz_geo_df.index.isin(EXEMPT_MAZ)==False) ]
            if len(maz_multiple_geo_df) == 0:
                logging.info(f"Verified one {bigger_geo} per maz")
                continue

            if bigger_geo in ["GEOID10_BG","GEOID10_TRACT"]:
                # warn and try to fix
                logging.warning(f"Multiple {bigger_geo} for a single maz: {len(maz_multiple_geo_df)}")
                logging.warning(f"\n{maz_multiple_geo_df.head(30)}")
                blocks_moved += move_small_block_to_neighbor(blocks_maz_df, blocks_neighbor_df,
                                                            maz_multiple_geo_df, bigger_geo, crosswalk_out_df)
            else:
                # fatal
                logging.fatal(f"Multiple {bigger_geo} for a single maz: {len(maz_multiple_geo_df)}")
                logging.fatal(f"\n{maz_multiple_geo_df.head(30)}")
                sys.exit(2)

        # verify one TRACT/COUNTY per unique taz
        # error for COUNTY
        # warn/log for TRACT 
        tazs_split = 0
        for bigger_geo in ["GEOID10_TRACT","GEOID10_COUNTY"]:
            taz_geo_df = blocks_maz_df[["taz",bigger_geo]].groupby(["taz"]).agg("nunique")
            taz_multiple_geo_df = taz_geo_df.loc[ (taz_geo_df[bigger_geo] > 1) & (taz_geo_df.index.isin(EXEMPT_TAZ)==False) ]
            if len(taz_multiple_geo_df) == 0:
                logging.info(f"Verified one {bigger_geo} per taz")
                continue

            if bigger_geo in ["GEOID10_TRACT"]:
                # warn
                logging.warning(f"Multiple {bigger_geo} for a single taz: {len(taz_multiple_geo_df)}")
                logging.warning(f"\n{taz_multiple_geo_df.head(30)}")
                # try to fix if mazs are all stable (so blocks_moved == 0) -- that should be fixed first
                if blocks_moved == 0:
                    tazs_split = split_taz_for_tract(blocks_maz_df, taz_multiple_geo_df, crosswalk_out_df)
            else:
                # fatal
                logging.fatal(f"Multiple {bigger_geo} for a single taz: {len(taz_multiple_geo_df)}")
                logging.fatal(f"\n{taz_multiple_geo_df.head(30)}")
                sys.exit()

        # save updated draft crosswalk to look at if blocks have been moved or tazs have been split
        if (blocks_moved > 0) or (tazs_split > 0):
            crosswalk_out_df = crosswalk_out_df[["GEOID10","maz","taz"]]
            crosswalk_out_df.sort_values(by="GEOID10", ascending=True, inplace=True)
            crosswalk_df = crosswalk_out_df
            
        # Once loops end or no blocks moved or tazs split, save the final crosswalk
        else:
            logging.info("No blocks moved or tazs split -- exiting iterations")
            output_file = WORKSPACE / f"{CROSSWALK_ROOT}_{VERSION}.csv"
            # if the input file is the same as this, don't write it
            if CROSSWALK_CSV.samefile(output_file):
                logging.info(f"Skipping write of {output_file} since it's the same as the input file")
            else:
                logging.info(f"Saving crosswalk as final crosswalk: {CROSSWALK_ROOT}_{VERSION}.csv")
                crosswalk_out_df = crosswalk_out_df[["GEOID10","maz","taz"]]
                crosswalk_out_df.sort_values(by="GEOID10", ascending=True, inplace=True)
                crosswalk_out_df.to_csv(output_file, index=False, quoting=csv.QUOTE_NONNUMERIC)
            break

    # count blocks per maz
    count_df = blocks_maz_df[["GEOID10","maz"]].groupby(["maz"]).agg("nunique")
    logging.info("Number of blocks per maz: ")
    logging.info(f"   Min: {count_df['GEOID10'].min()}")
    logging.info(f"   Max: {count_df['GEOID10'].max()}")
    logging.info(f"  Mean: {count_df['GEOID10'].mean()}")
    logging.info("")

    # count maz per taz
    count_df = blocks_maz_df[["maz","taz"]].groupby(["taz"]).agg("nunique")
    logging.info("Number of maz per taz: ")
    logging.info(f"   Min: {count_df['maz'].min()}")
    logging.info(f"   Max: {count_df['maz'].max()}")
    logging.info(f"  Mean: {count_df['maz'].mean()}")
    logging.info("")

    # lets look at the zeros
    logging.info(f"Number of blocks without maz/taz: {blocks_nomaz_df.GEOID10.nunique()}")

    # blocks with land should have mazs/tazs - Error if blocks with land does not have mazs/tazs
    block_nomaz_land_df = blocks_nomaz_df.loc[ (blocks_nomaz_df.ALAND10 > 0) & (blocks_nomaz_df.GEOID10.isin(EXEMPT_LAND_BLOCK) == False) ]
    logging.info(f"Number of blocks without maz/taz with land area: {len(block_nomaz_land_df)}")
    if len(block_nomaz_land_df) > 0:
        logging.fatal(f"\n{block_nomaz_land_df}")
        logging.fatal("")
        sys.exit("ERROR")

    # blocks with no land should not have mazs/tazs
    blocks_maz_noland_df = blocks_maz_df.loc[ (blocks_maz_df.ALAND10 == 0)&(blocks_maz_df.GEOID10.isin(EXEMPT_NOLAND_BLOCK)==False) ]
    logging.info(f"Number of blocks with maz/taz without land area: {len(blocks_maz_noland_df)}")
    if len(blocks_maz_noland_df) > 0:
        logging.fatal(f"\n{blocks_maz_noland_df}")
        logging.fatal("")
        logging.info(f"Writing block_noland.csv")
        blocks_maz_noland_df[["GEOID10","ALAND10"]].to_csv("block_noland.csv", index=False)
        sys.exit("ERROR")

    # verify maz/taz numbering alignment with https://bayareametro.github.io/tm2py/inputs/#county-node-numbering-system
    maz_taz_county_check = blocks_maz_df.groupby("GEOID10_COUNTY").agg({'maz':['min','max'],
                                                                        'taz':['min','max']})
    logging.info(f"maz_taz_county_check:\n{maz_taz_county_check}")

    logging.info("Dissolving blocks into MAZs and TAZs")
    maz_gdf = dissolve_into_shapefile(blocks_maz_gdf, "maz")
    taz_gdf = dissolve_into_shapefile(blocks_maz_gdf, "taz")

    ## Join MAZs/TAZs to superdistricts
    logging.info("Joining mazs/tazs to superdistricts")
    superdistricts = geopandas.read_file(SUPERDISTRICT_FILE)
    superdistricts.to_crs(WGS84_CRS, inplace=True)
    logging.debug(f"superdistricts:\n{superdistricts}")

    taz_gdf = geopandas.overlay(taz_gdf, superdistricts, how='intersection')
    # switch to feet for area calculation
    taz_gdf.to_crs(LOCAL_CRS_FEET, inplace=True)
    taz_gdf['area'] = taz_gdf.geometry.area
    taz_gdf.to_crs(WGS84_CRS, inplace=True)
    taz_gdf.sort_values(by = ['area'], inplace = True)
    taz_gdf.drop_duplicates(subset = ['TAZ_NODE'], keep = 'last', inplace = True)
    # add district to mazs
    maz_gdf = maz_gdf.merge(taz_gdf[['TAZ_NODE','suprdistid', 'DistName']], on='TAZ_NODE', how='left')
  
    # create MAZ_TAZ_COUNTY_PUMA_FILE with columns,MAZ,TAZ,COUNTY,county_name,PUMA
    census_tract_puma_df = pandas.read_csv(CENSUS_TRACT_PUMA, dtype=str)
    census_tract_puma_df.rename(columns={
        'STATEFP' :'STATEFP10',
        'COUNTYFP':'COUNTYFP10',
        'TRACTCE' :'TRACTCE10',
        'PUMA5CE' :'PUMA10'
    }, inplace=True)
    logging.info(f"Read {CENSUS_TRACT_PUMA}")
    logging.debug(f"census_tract_puma_df:\n{census_tract_puma_df}")
    logging.debug(f"blocks_maz_df len={len(blocks_maz_df):,}:\n{blocks_maz_df}")

    # merge blocks to get MAZ centroid
    blocks_maz_df = pandas.merge(
        left=blocks_maz_df.rename(columns={"maz":"MAZ_NODE"}),
        right=maz_gdf[['MAZ_NODE','MAZ_SEQ','suprdistid','DistName','MAZ_X','MAZ_Y']],
        how='left',
        on=['MAZ_NODE'],
        validate="many_to_one"
    )

    blocks_maz_df = pandas.merge(
        left=blocks_maz_df,
        right=census_tract_puma_df,
        how='left',
        on=['STATEFP10','COUNTYFP10','TRACTCE10'],
        validate='many_to_one'
    )
    logging.debug(f"blocks_maz_df len={len(blocks_maz_df):,}:\n{blocks_maz_df}")

    # this should be defined somewhere standard; mtcpy? 
    blocks_maz_df['county_name'] = blocks_maz_df.COUNTYFP10.map({
        "001": "Alameda",
        "013": "Contra Costa",
        "041": "Marin",
        "055": "Napa",
        "075": "San Francisco",
        "081": "San Mateo",
        "085": "Santa Clara",
        "095": "Solano",
        "097": "Sonoma",
    })
    # https://github.com/BayAreaMetro/modeling-website/wiki/TazData
    blocks_maz_df['COUNTY'] = blocks_maz_df.county_name.map({
        "San Francisco": 1,
        "San Mateo": 2,
        "Santa Clara": 3,
        "Alameda": 4,
        "Contra Costa": 5,
        "Solano": 6,
        "Napa": 7,
        "Sonoma": 8,
        "Marin": 9,
    })
    blocks_maz_df.rename(columns={'suprdistid':'DistID','taz':'TAZ_NODE'}, inplace=True)
    blocks_maz_df = pandas.merge(
        left=blocks_maz_df,
        right=taz_gdf[['TAZ_NODE','TAZ_SEQ']],
        how='left',
        on='TAZ_NODE',
        validate='many_to_one',
        indicator=True
    )
    assert(blocks_maz_df['_merge'] == "both").all()
    blocks_maz_df.drop(columns=['_merge'], inplace=True)

    # keep only these columns
    blocks_maz_df = blocks_maz_df[['MAZ_NODE','MAZ_SEQ','TAZ_NODE','TAZ_SEQ','COUNTY','county_name','COUNTYFP10','TRACTCE10','PUMA10', 'DistID', 'DistName','MAZ_X','MAZ_Y']]
    blocks_maz_df.sort_values(by='MAZ_SEQ', inplace=True)
    blocks_maz_df.drop_duplicates(inplace=True)
    logging.debug(f"After drop_duplicates, len(blocks_maz_df)={len(blocks_maz_df):,} blocks_maz_df.MAZ_NODE.nunique()={blocks_maz_df.MAZ_NODE.nunique():,}")

    # manual fixes for mazs that map to more than one tract due to exceptions documented above
    # drop TAZ_NODE=327 TRACTCE10='017902' -- the sliver from a mostly water/Treasure Island track
    blocks_maz_df = blocks_maz_df.loc[ ~((blocks_maz_df.MAZ_NODE ==  16495) & (blocks_maz_df.TRACTCE10 == '017902'))]
    # drop TAZ_NODE=700241 TRACTCE10='151700' -- sliver from a mostly water tract in Sonoma, south part of Santa Rosa Creek Reservoir
    blocks_maz_df = blocks_maz_df.loc[ ~((blocks_maz_df.MAZ_NODE == 718685) & (blocks_maz_df.TRACTCE10 == '151700'))]
    # drop TAZ_NODE=800095 TRACTCE10='104300' -- sliver from an adjacent tract in Marin
    blocks_maz_df = blocks_maz_df.loc[ ~((blocks_maz_df.MAZ_NODE == 810745) & (blocks_maz_df.TRACTCE10 == '104300'))]
    # drop TAZ_NODE=800203 TRACTCE10='122000' -- San Quentin Rehabilitation Center is nested within another donut tract
    blocks_maz_df = blocks_maz_df.loc[ ~((blocks_maz_df.MAZ_NODE == 813480) & (blocks_maz_df.TRACTCE10 == '122000'))]
    logging.debug(f"After manual fixes, len(blocks_maz_df)={len(blocks_maz_df):,} blocks_maz_df.MAZ_NODE.nunique()={blocks_maz_df.MAZ_NODE.nunique():,}")

    # verify MAZs are unique
    dupe_maz = blocks_maz_df.loc[ blocks_maz_df['MAZ_NODE'].duplicated(keep=False)]
    logging.debug(f"dupe_maz:\n{dupe_maz}")
    assert(len(dupe_maz)==0)

    output_mapping_file = f'mazs_tazs_county_tract_PUMA_{VERSION}.csv'
    logging.info(f"Writing {len(blocks_maz_df):,} rows to {output_mapping_file}")
    blocks_maz_df.to_csv(output_mapping_file, index=False)

    taz_tract_df = blocks_maz_df[['TAZ_NODE','TAZ_SEQ','COUNTY','county_name','COUNTYFP10','TRACTCE10','PUMA10','DistID', 'DistName']].drop_duplicates()
    logging.debug(f"taz_tract_df:\n{taz_tract_df}")

    # add taz centroid coordinates
    taz_tract_df = pandas.merge(
        left=taz_tract_df,
        right=taz_gdf[['TAZ_NODE','TAZ_X','TAZ_Y']],
        how='left',
        on="TAZ_NODE",
        validate="one_to_one"
    )
    taz_tract_df = taz_tract_df.sort_values(by="TAZ_SEQ").reset_index(drop=True)
    logging.debug(f"taz_tract_df:\n{taz_tract_df}")

    # verify TAZs are unique
    dupe_taz = taz_tract_df.loc[ taz_tract_df['TAZ_NODE'].duplicated(keep=False)]
    assert(len(dupe_taz)==0)

    output_mapping_file = f'tazs_county_tract_PUMA_{VERSION}.csv'
    logging.info(f"Writing {len(taz_tract_df):,} rows to {output_mapping_file}")
    taz_tract_df.to_csv(output_mapping_file, index=False)
    sys.exit(0)
