USAGE = """
  Quick script to dissolve block groups into tracts

"""
import pathlib
import geopandas
import pandas

# Set directory to the Census Block Version
CENSUS_BLOCK_SHP   = pathlib.Path("M:\\Data\\Census\\Geography\\tl_2020_06_tabblock10\\tl_2020_06_tabblock10_9CBA.shp")
CENSUS_TRACT_SHP   = CENSUS_BLOCK_SHP.parent / "tl_2020_06_tract10_9CBA.shp"

if __name__ == '__main__':

    pandas.options.display.max_columns = None
    pandas.options.display.width = 500

    blocks_gdf = geopandas.read_file(CENSUS_BLOCK_SHP)
    print(f"Read {CENSUS_BLOCK_SHP}")
    # print(blocks_gdf)
    print(blocks_gdf.dtypes)
    blocks_gdf["num_blocks"] = 1

    print("Dissolving to tracts...")
    tract_gdf = blocks_gdf.dissolve(
        by=["STATEFP10","COUNTYFP10","TRACTCE10"],
        aggfunc = { "ALAND10":"sum", "AWATER10": "sum", "num_blocks":"count", "GEOID10":"first" },
        as_index = False
    )
    # tract only has 11 characters
    tract_gdf["GEOID10"] = tract_gdf["GEOID10"].str.slice(stop=11)
    print(f"Saving to {CENSUS_TRACT_SHP}")
    tract_gdf.to_file(CENSUS_TRACT_SHP)

    # [109228 rows x 16 columns]
    # STATEFP10       object
    # COUNTYFP10      object
    # TRACTCE10       object
    # BLOCKCE10       object
    # GEOID10         object
    # NAME10          object
    # MTFCC10         object
    # UR10            object
    # UACE10          object
    # UATYPE          object
    # FUNCSTAT10      object
    # ALAND10          int64
    # AWATER10         int64
    # INTPTLAT10      object
    # INTPTLON10      object
    # geometry      geometry
    # dtype: object