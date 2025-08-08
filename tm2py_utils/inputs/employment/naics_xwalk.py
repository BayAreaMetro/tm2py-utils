import pandas as pd
from pathlib import Path
import numpy as np
import openpyxl
import unittest


def create_naics_xwalk():
    """
    Creates a crosswalk, mapping 2022 6-digit NAICS codes to 27-way 'steelhead' sector categories.
    Dependency for building 2023 job count input for TM2. 
    Steps:
        1. Loads and preps 2022 NAICS descriptions file.
        2. Defines a mapping dictionary from NAICS codes (at varying digit lengths) to 'steelhead' categories.
        3. Creates 'steelhead' column, using prefix matching from dictionary keys to 'naicssix' and returns
        the DataFrame.
        
    Returns:
        pd.DataFrame: DataFrame with NAICS codes, descriptions, and mapped steelhead categories.

    Source:
        2022_NAICS_Descriptions.xlsx was downloaded from https://www.census.gov/naics/?48967

    Notes:
        The dictionary can only accurately handle the NAICS 2022 vintage.  When OMB updates NAICS in 2027, we 
        can potentially use the 2022 to 2027 concordance file as an additional input to flag and update codes 
        that have changed.

    """
    
    # Step 1: Load and prep 2022 NAICS descriptions
    NAICS_DIR = Path(r"M:/Crosswalks/NAICS")
    naics = pd.read_excel(NAICS_DIR / "2022_NAICS_Descriptions.xlsx",
                            dtype={"Code": str},
                            usecols={"Code", "Title"})

    # Filter to 6-dgit precision and rename
    naics = naics[naics["Code"].str.len() == 6].reset_index(drop=True)
    naics = naics.rename(columns={"Code": "naicssix", "Title": "description"})


    # Step 2: Define dictionary that maps 2022 NAICS codes to steelhead categories
    naics_to_steelhead = {
        # Agriculture, Forestry, Hunting, Fishing 
        '11': 'ag',
        
        # Arts, Entertainment, and Recreation 
        '71': 'art_rec',
        
        # Construction 
        '23': 'constr',
        
        # Food Services and Drinking Places 
        '722': 'eat',
        
        # Higher Educational Services 
        '6112': 'ed_high', # Juinior Colleges
        '6113': 'ed_high', # Colleges, Universities, and Professional Schools
        '6114': 'ed_high', # Business Schools and Computer and Management Training
        '6115': 'ed_high', # Technical and Trade Schools
        
        # Elementary and Secondary Schools 
        '6111': 'ed_k12',
        
        # Other Schools and Educational Support Services 
        '6116': 'ed_oth', # Other Schools and Instruction
        '6117': 'ed_oth', # Educational Support Services

        # Finance and Insurance, Real Estate, and Lessors of Nonfinancial Intangible Assets (e.g. assigning rights to patents, trademarks, etc) 
        '52': 'fire', # Finance and Insurance
        '531': 'fire', # Real Estate
        '533': 'fire', # Lessors of Nonfinancial Intangible Assets
        
        # Public Administration 
        '92': 'gov',

        # Healthcare 
        '621': 'health', # Ambulatory Health Care Services
        '622': 'health', # Hospitals
        '623': 'health', # Nursing and Residential Care Facilities

        # Hotels & Other Accommodations 
        '721': 'hotel',
        
        # Information-Based Services 
        '51': 'info',
        
        # Rental and Leasing Services 
        '532': 'lease',
        
        # Logistics 
        '42': 'logis', # Wholesale Trade
        '493': 'logis', # Warehousing and Storage
        
        # Pharmaceutical and Medicine Manufacturing 
        '3254': 'man_bio',

        # Heavy Manufacturing 
        '3221': 'man_hvy', # Pulp, Paper, and Paperboard Mills
        '331': 'man_hvy', # Primary Metal Manufacturing
        '3329': 'man_hvy', # Other Fabricated Metal Product Manufacturing
        '333': 'man_hvy', # Machinery Manufacturing
        '335': 'man_hvy', # Electrical Equipment, Appliance, and Component Manufacturing
        '336': 'man_hvy', # Transportation Equipment Manufacturing
        
        # Light Manufacturing 
        '31': 'man_lgt', # Food, Beverage and Tobacco Product, Textile, Apparel, Leather Manufacturing

        '321': 'man_lgt', # Wood Product Manufacturing
        '3222': 'man_lgt', # Converted Paper Product Manufacturing
        '323': 'man_lgt', # Printing and Related Support Activities
        '324': 'man_lgt', # Petroleum and Coal Products Manufacturing
        '3251': 'man_lgt', # Basic Chemical Manufacturing
        '3252': 'man_lgt', # Resin, Synthetic Rubber, and Artificial and Synthetic Fibers and Filaments Manufacturing
        '3253': 'man_lgt', # Pesticide, Fertilizer, and Other Agricultural Chemical Manufacturing
        '3255': 'man_lgt', # Paint, Coating, and Adhesive Manufacturing
        '3256': 'man_lgt', # Soap, Cleaning Compound, and Toilet Preparation Manufacturing
        '3259': 'man_lgt', # Other Chemical Product and Preparation Manufacturing
        '326': 'man_lgt', # Plastics and Rubber Product Manufacturing
        '327': 'man_lgt', # Nonmetallic Mineral Product Manufacturing

        '3321': 'man_lgt', # Forging and Stamping
        '3322': 'man_lgt', # Cutlery and Handtool Manufacturing
        '3323': 'man_lgt', # Architectural and Structural Metals Manufacturing
        '3324': 'man_lgt', # Boiler, Tank, and Shipping Container Manufacturing
        '3325': 'man_lgt', # Hardware Manufacturing
        '3326': 'man_lgt', # Spring and Wire Product Manufacturing
        '3327': 'man_lgt', # Machine Shops; Turned Product; and Screw, Nut, and Bolt Manufacturing
        '3328': 'man_lgt', # Coating, Engraving, Heat Treating, and Allied Activities
        '337': 'man_lgt', # Furniture and Related Product Manufacturing
        '339': 'man_lgt', # Miscellaneous Manufacturing
        
        # Computer and Electronic Product Manufacturing 
        '334': 'man_tech',
        
        # Mining, Quarrying, and Oil and Gas Extraction 
        '21': 'natres',
        
        # Professional, Scientific, and Technical Services 
        '54': 'prof',
        
        # Local-Serving Retail
        '444140': 'ret_loc', # Hardware Retailers
        '444180': 'ret_loc', # Other Building Material Dealers
        '4442': 'ret_loc', # Lawn and Garden Equipment and Supplies Retailers
        '445': 'ret_loc', # Food and Beverage Retailers

        '4552': 'ret_loc', # Warehouse Clubs, Supercenters, and Other General Merchandise Retailers
        '456': 'ret_loc', # Health and Personal Care Retailers
        '457': 'ret_loc', # Gasoline Stations and Fuel Dealers
        '458': 'ret_loc', # Clothing, Clothing Accessories, Shoe, and Jewelry Retailers
        '459': 'ret_loc', # Sporting Goods, Hobby, Musical Instrument, Book, and Miscellaneous Retailers
        
        # Regional Retail 
        '441': 'ret_reg', # Motor Vehicle and Parts Dealers
        '441330': 'ret_reg', # Automotive Parts and Accessories Retailers
        '444110': 'ret_reg', # Home Centers
        '444120': 'ret_reg', # Paint and Wallpaper Retailers
        '445132': 'ret_reg', # Vending Machine Operators
        '449': 'ret_reg', # Furniture, Home Furnishings, Electronics, and Appliance Retailers
        
        '455110': 'ret_reg', # Department Stores
        '457210': 'ret_reg', # Fuel Dealers
        '459410': 'ret_reg', # Office Supplies and Stationery Retailers

        # Business Services 
        '55': 'serv_bus', # Managerial Services
        '56': 'serv_bus', # Administrative and Business Services 
        
        # Other Personal Services
        '53': 'serv_per', # Real Estate and Rental and Leasing
        '81': 'serv_per', #  Other Services (except Public Administration)
        
        # Social Services & Childcare 
        '624': 'serv_soc',

        # Transportation Services
        '48': 'transp', # Transportation
        '491': 'transp', # Postal Service
        '492': 'transp', # Couriers and Messengers

        # Utilities 
        '22': 'util',

    }

    # Step 3: Create the new steelhead column
    def map_steelhead(naics_code):
        # Iterate through keys from highest precision to lowest precision NAICS
        for key in sorted(naics_to_steelhead, key=len, reverse=True):
            # Return steelhead value upon match
            if naics_code.startswith(key):
                return naics_to_steelhead[key]
        return np.nan
    
    naics_xwalk = naics.copy()
    naics_xwalk["steelhead"] = naics_xwalk["naicssix"].apply(map_steelhead)

    # Firms with NAICS 999990 have been previously categorized as "mis" - appending here
    naics_xwalk = pd.concat([
        naics_xwalk,
        pd.DataFrame([{
            "naicssix": "999990",
            "description": "Firm with unclassified NAICS",
            "steelhead": "mis"
        }])
    ], ignore_index=True)

    return naics_xwalk

# Some simple unit tests
class TestNAICSXwalk(unittest.TestCase):
    def setUp(self):
        self.naics_xwalk = create_naics_xwalk()

    def test_length_unique_steelhead(self):
        """
        Ensure we are getting 28 unique categories, including the "mis" category 
        """
        unique_count = len(self.naics_xwalk["steelhead"].unique())
        expected_count = 28
        self.assertEqual(
            unique_count, 
            expected_count, 
            f"Expected {expected_count} unique steelhead categories, but found {unique_count}.")
        
    def test_all_categorized(self):
        """
        Ensure every naics code gets categorized
        """
        has_nulls = self.naics_xwalk["steelhead"].isnull().any()
        self.assertFalse(
            has_nulls,
            f"Found nulls in steelhead.  All NAICS codes should be categorized."
        )


if __name__ == "__main__":
    naics_xwalk = create_naics_xwalk()
    # Run unittest without exiting so the session can be interactive
    unittest.main(exit=False)