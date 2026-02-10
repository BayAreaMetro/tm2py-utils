"""
Bay Area Parking Scraping

"""

# Install required packages (run manually if needed)
# pip install selenium pandas geopy

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from collections import defaultdict
import time
import re
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Import configuration
from setup import INTERIM_CACHE_DIR, ensure_directories


# ============================================================================
# Configuration: Bay Area Cities
# ============================================================================

# Bay Area city configuration
# Each city has: id and kind (city or destination)

cities = {
    'San Francisco': {'id': 26, 'kind': 'city'},
    'Oakland': {'id': 95, 'kind': 'city'},
    'San Jose': {'id': 97, 'kind': 'city'},
    'Berkeley': {'id': 61984, 'kind': 'destination'},
    'Walnut Creek': {'id': 56116, 'kind': 'destination'},
    'Palo Alto': {'id': 61989, 'kind': 'destination'},
    'Millbrae': {'id': 61986, 'kind': 'destination'},
    'Concord': {'id': 61991, 'kind': 'destination'}
}

# Initialize geocoder (Nominatim from OpenStreetMap)
# TEMPORARILY DISABLED - geocoding will be done in a separate step
# geolocator = Nominatim(user_agent="bay_area_parking_scraper")
# geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# Time window for parking search (Feb 4, 2026, 8am-6pm)
start_time = '2026-02-04T08:00'
end_time = '2026-02-04T18:00'

# URL encode colons
start_encoded = start_time.replace(':', '%3A')
end_encoded = end_time.replace(':', '%3A')


# ============================================================================
# Debug: Inspect Page Structure (Optional - comment out after testing)
# ============================================================================

def debug_page_structure():
    """Run this function first to see what elements are actually on the page"""
    debug_url = f"https://spothero.com/search?kind=city&id=95&starts={start_encoded}&ends={end_encoded}"
    print(f"Testing URL: {debug_url}\n")

    driver = webdriver.Chrome()
    driver.get(debug_url)
    time.sleep(5)  # Give extra time for page to load

    print("Looking for spot list container...")
    try:
        # Look for elements with data-spot attribute
        print("\n" + "="*50)
        print("SPOT IDS")
        print("="*50)
        spot_elements = driver.find_elements(By.CSS_SELECTOR, "[data-spot]")
        print(f"Found {len(spot_elements)} elements with data-spot attribute")
        
        if spot_elements:
            print("\nFirst 5 spot IDs:")
            for i, elem in enumerate(spot_elements[:5]):
                spot_id = elem.get_attribute('data-spot')
                print(f"  {i+1}. Spot ID: {spot_id}")
        
        # Check for any elements with 'price' in the class name
        print("\n" + "="*50)
        print("PRICES")
        print("="*50)
        price_elements = driver.find_elements(By.CSS_SELECTOR, "[class*='price'], [class*='Price']")
        print(f"Found {len(price_elements)} elements with 'price' in class name")
        if price_elements:
            print("First 5 price elements:")
            for i, elem in enumerate(price_elements[:5]):
                print(f"  {i+1}. Text: '{elem.text}' | Class: {elem.get_attribute('class')}")
        
        # Check for addresses/facility names
        print("\n" + "="*50)
        print("ADDRESSES/NAMES")
        print("="*50)
        
        # Try various selectors
        address_candidates = [
            ("span[class*='FacilitySummary']", "FacilitySummary spans"),
            ("[class*='title']", "Elements with 'title' in class"),
            ("a[href*='spot']", "Links with 'spot' in href"),
        ]
        
        for selector, description in address_candidates:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"\n{description} ({selector}): {len(elements)} found")
                for i, elem in enumerate(elements[:3]):
                    text = elem.text.strip()
                    if text:
                        print(f"  {i+1}. {text[:100]}")
        
        # Find all links that might be facility links
        print("\n" + "="*50)
        print("FACILITY LINKS (might contain addresses)")
        print("="*50)
        links = driver.find_elements(By.TAG_NAME, "a")
        facility_links = [link for link in links if link.text and len(link.text.strip()) > 10][:10]
        for i, link in enumerate(facility_links):
            print(f"  {i+1}. {link.text.strip()[:80]}")
        
    except Exception as e:
        print(f"Error during inspection: {e}")
        
    finally:
        # Save page source for manual inspection
        with open('debug_page_source.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("\n" + "="*50)
        print("Page source saved to debug_page_source.html for manual inspection")
        print("="*50)
        driver.quit()


# ============================================================================
# Price Parsing Functions
# ============================================================================

def parse_price(price_text):
    """Extract numeric price value and rate type from price string
    
    Examples:
    - '$15.00' -> (15.00, 'unknown')
    - '$20/day' -> (20.00, 'daily')
    - '$8.50/hr' -> (8.50, 'hourly')
    - '$150/month' -> (150.00, 'monthly')
    """
    if not price_text or price_text.strip() == '':
        return None, None
    
    # Extract numeric value
    price_match = re.search(r'\$?([0-9,]+\.?[0-9]*)', price_text)
    if price_match:
        price_value = float(price_match.group(1).replace(',', ''))
    else:
        return None, None
    
    # Determine rate type
    price_lower = price_text.lower()
    if any(term in price_lower for term in ['hour', 'hr', '/hr', 'hourly']):
        rate_type = 'hourly'
    elif any(term in price_lower for term in ['day', '/day', 'daily']):
        rate_type = 'daily'
    elif any(term in price_lower for term in ['month', '/month', '/mo', 'monthly']):
        rate_type = 'monthly'
    elif any(term in price_lower for term in ['week', '/week', '/wk', 'weekly']):
        rate_type = 'weekly'
    else:
        rate_type = 'flat_rate'  # Flat rate for the time period searched
    
    return price_value, rate_type


# ============================================================================
# Geocoding Functions
# ============================================================================

def geocode_address(address, city_name):
    """Convert address to latitude/longitude coordinates
    
    Args:
        address: Street address
        city_name: City name to append for better geocoding accuracy
        
    Returns:
        tuple: (latitude, longitude) or (None, None) if geocoding fails
    """
    if not address or address.strip() == '':
        return None, None
    
    # Append city and state for better accuracy
    full_address = f"{address}, {city_name}, CA, USA"
    
    try:
        location = geocode(full_address)
        if location:
            return location.latitude, location.longitude
        else:
            # Try without city name if first attempt fails
            location = geocode(f"{address}, CA, USA")
            if location:
                return location.latitude, location.longitude
    except Exception as e:
        print(f"  Geocoding error for '{address}': {e}")
    
    return None, None


# ============================================================================
# Scrape Main Listing Pages for All Cities
# ============================================================================

def scrape_all_cities():
    """Scrape parking data for all configured Bay Area cities"""
    # Store results for all cities
    all_city_data = []
    all_spot_ids = {}

    # Scrape both daily and monthly parking
    parking_types = [
        {'name': 'daily', 'monthly_param': False},  # 10-hour window = daily parking
        {'name': 'monthly', 'monthly_param': True}
    ]

    for parking_type in parking_types:
        for city_name, city_info in cities.items():
            print(f"\n{'='*50}")
            print(f"Scraping {city_name} - {parking_type['name'].upper()} parking (ID: {city_info['id']})")
            print(f"{'='*50}")
            
            # Construct URL based on parking type
            if parking_type['monthly_param']:
                # Monthly parking URL
                url = f"https://spothero.com/search?kind={city_info['kind']}&id={city_info['id']}&monthly=true&starts={start_encoded}"
            else:
                # Hourly/daily parking URL
                url = f"https://spothero.com/search?kind={city_info['kind']}&id={city_info['id']}&starts={start_encoded}&ends={end_encoded}"
            print(f"URL: {url}")
            
            # Initialize driver
            driver = webdriver.Chrome()
            driver.get(url)
            time.sleep(5)  # Increased wait time for page to load
            
            # Initialize lists
            address_list = []
            price_list = []
            spot_ids = []
            
            # Extract addresses - try multiple selectors
            address_selectors = [
                "span.FacilitySummary-title",
                "span[class='chakra-text FacilitySummary-title css-18lhgdc']",
                "[class*='FacilitySummary-title']",
                "a[class*='FacilitySummary'] span"
            ]
            for selector in address_selectors:
                addresses = driver.find_elements(By.CSS_SELECTOR, selector)
                if addresses:
                    address_list = [addr.text for addr in addresses]
                    print(f"Found {len(address_list)} addresses using selector: {selector}")
                    break
            if not address_list:
                print("WARNING: No addresses found with any selector!")
            
            # Extract prices - use the selector from debug output
            price_selectors = [
                "span.FacilitySummary-FormattedPrice",  # The actual discounted price
                "div.FacilitySummary-price-container",
                "[class*='FormattedPrice']",
                "div[class='price']"
            ]
            for selector in price_selectors:
                prices = driver.find_elements(By.CSS_SELECTOR, selector)
                if prices:
                    price_list = [price.text for price in prices]
                    print(f"Found {len(price_list)} prices using selector: {selector}")
                    break
            if not price_list:
                print("WARNING: No prices found with any selector!")
            
            # Extract spot IDs - Try multiple methods
            try:
                # Method 1: Try direct CSS selector for data-spot attribute
                spot_elements = driver.find_elements(By.CSS_SELECTOR, "[data-spot]")
                if spot_elements:
                    spot_ids = [elem.get_attribute('data-spot') for elem in spot_elements]
                    print(f"Method 1 (CSS [data-spot]): Found {len(spot_ids)} spot IDs")
                else:
                    # Method 2: Try finding parent container with different XPath
                    try:
                        parent_xpaths = [
                            "/html/body/div[1]/div/main/div/div/div[2]/div[2]/div",
                            "//div[contains(@class, 'SpotList-spots')]",
                            "//div[@class='SpotList-spots']"
                        ]
                        
                        for xpath in parent_xpaths:
                            try:
                                element = driver.find_element(By.XPATH, xpath)
                                children = element.find_elements(By.XPATH, "./child::*")
                                spot_ids = [child.get_attribute('data-spot') for child in children if child.get_attribute('data-spot')]
                                if spot_ids:
                                    print(f"Method 2 (XPath: {xpath}): Found {len(spot_ids)} spot IDs")
                                    break
                            except:
                                continue
                    except Exception as e2:
                        print(f"Method 2 failed: {e2}")
            except Exception as e:
                print(f"Error extracting spot IDs for {city_name}: {e}")
            
            # If we still don't have spot IDs, generate placeholder IDs
            if not spot_ids and address_list:
                print(f"WARNING: No spot IDs found. Using indices as placeholders.")
                spot_ids = [f"{city_info['id']}_{i}" for i in range(len(address_list))]
            
            driver.quit()
            
            # Ensure all lists are the same length (use max of address and price lists)
            max_len = max(len(address_list), len(price_list), len(spot_ids))
            address_list += [''] * (max_len - len(address_list))
            price_list += [''] * (max_len - len(price_list))
            spot_ids += [''] * (max_len - len(spot_ids))
            
            # Split addresses into address and name
            address_split = pd.DataFrame([addr.split('-', 1) if '-' in addr else [addr, ''] for addr in address_list],
                                         columns=['address', 'name'])
            
            # Create DataFrame for this city
            city_df = pd.DataFrame({
                'city': city_name,
                'city_id': city_info['id'],
                'parking_type': parking_type['name'],
                'prices': price_list,
                'spot_id': spot_ids
            })
            
            # Add address and name columns
            city_df = pd.concat([city_df, address_split], axis=1)
            
            # Parse prices to extract numeric values and rate types
            print("Parsing prices...")
            price_parsed = city_df['prices'].apply(parse_price)
            city_df['price_value'] = price_parsed.apply(lambda x: x[0])
            city_df['rate_type'] = price_parsed.apply(lambda x: x[1])
                
            # Geocoding skipped for now - will be done in separate step
            print("Skipping geocoding (will be done separately)...")
            city_df['latitude'] = None
            city_df['longitude'] = None
            
            all_city_data.append(city_df)
            all_spot_ids[f"{city_name}_{parking_type['name']}"] = spot_ids
            
            print(f"Successfully scraped {len(city_df)} {parking_type['name']} parking spots in {city_name}")
            if len(city_df) > 0:
                print("\nFirst few rows with prices:")
                print(city_df[['city', 'parking_type', 'address', 'prices', 'price_value', 'rate_type']].head())
    
    return all_city_data, all_spot_ids


# ============================================================================
# Combine All Cities into Single DataFrame
# ============================================================================

def combine_city_data(all_city_data):
    """Combine all city data into single DataFrame"""
    combined_df = pd.concat(all_city_data, ignore_index=True)
    print(f"\nTotal spots scraped across all cities: {len(combined_df)}")
    print(f"\nBreakdown by city:")
    print(combined_df['city'].value_counts())
    
    # Show pricing summary
    if combined_df['price_value'].notna().any():
        print("\nPrice statistics by rate type:")
        valid_prices = combined_df[combined_df['rate_type'].notna()]
        if len(valid_prices) > 0:
            print(valid_prices.groupby('rate_type')['price_value'].agg(['count', 'mean', 'min', 'max']))
        else:
            print("  No valid prices found")
    else:
        print("\nWARNING: No prices were successfully scraped!")
    
    # Show geocoding success rate
    geocoded_count = combined_df['latitude'].notna().sum()
    if len(combined_df) > 0:
        print(f"\nGeocoding success: {geocoded_count}/{len(combined_df)} ({geocoded_count/len(combined_df)*100:.1f}%)")
    else:
        print("\nNo locations to geocode")
    
    print("\nSample data with key fields:")
    print(combined_df[['city', 'address', 'price_value', 'rate_type', 'latitude', 'longitude']].head(10))
    return combined_df


def save_main_results(combined_df):
    """Save combined results to interim cache directory"""
    ensure_directories()
    
    # Save full dataset
    output_path = INTERIM_CACHE_DIR / 'parking_scrape_spots.csv'
    combined_df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")
    
    # Also save a simplified version with just the essential fields
    essential_fields = ['city', 'parking_type', 'address', 'name', 'latitude', 'longitude', 
                       'price_value', 'rate_type', 'prices', 'spot_id']
    essential_df = combined_df[essential_fields]
    output_path_essential = INTERIM_CACHE_DIR / 'parking_scrape_location_cost.csv'
    essential_df.to_csv(output_path_essential, index=False)
    print(f"Saved essential fields to {output_path_essential}")
    print(f"  Fields: {', '.join(essential_fields)}")


# ============================================================================
# Generate Detail Page URLs for Each City
# ============================================================================

def generate_detail_urls(all_spot_ids):
    """Create detail URLs for each spot"""
    detail_urls = []

    for city_name, city_info in cities.items():
        for parking_type in ['daily', 'monthly']:
            key = f"{city_name}_{parking_type}"
            if key not in all_spot_ids:
                continue
            spot_list = all_spot_ids[key]
            for spot_id in spot_list:
                if parking_type == 'monthly':
                    url = f"https://spothero.com/search?kind={city_info['kind']}&id={city_info['id']}&monthly=true&starts={start_encoded}&spot-id={spot_id}"
                else:
                    url = f"https://spothero.com/search?kind={city_info['kind']}&id={city_info['id']}&starts={start_encoded}&ends={end_encoded}&spot-id={spot_id}"
                detail_urls.append({
                    'city': city_name,
                    'city_id': city_info['id'],
                    'parking_type': parking_type,
                    'spot_id': spot_id,
                    'detail_url': url
                })

    detail_urls_df = pd.DataFrame(detail_urls)
    print(f"Generated {len(detail_urls_df)} detail URLs")
    print(detail_urls_df.head())
    return detail_urls_df


def save_detail_urls(detail_urls_df):
    """Save detail URLs to CSV"""
    output_dir = r'E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse'
    detail_urls_df.to_csv(f'{output_dir}\\parking_scrape_detail_urls.csv', index=False)
    print(f"Saved to {output_dir}\\parking_scrape_detail_urls.csv")


# ============================================================================
# Scrape Amenities from Detail Pages (Optimized)
# ============================================================================

def scrape_amenities(detail_urls_df):
    """Scrape amenities using a single reusable WebDriver instance"""
    amenities_data = defaultdict(list)

    # Create single driver instance
    driver = webdriver.Chrome()

    try:
        for i, row in detail_urls_df.iterrows():
            if i % 10 == 0:
                print(f"Processing spot {i+1}/{len(detail_urls_df)} ({row['city']})")
            
            driver.get(row['detail_url'])
            time.sleep(2)  # Wait for page load
            
            amenities = driver.find_elements(By.CSS_SELECTOR, "span[class='AmenitiesList-item-content']")
            for amenity in amenities:
                amenities_data[i].append(amenity.text)
    finally:
        driver.quit()

    # Convert to DataFrame
    amenities_df = pd.DataFrame(dict([(k, pd.Series(v)) for k, v in amenities_data.items()])).transpose()
    print(f"\nScraped amenities for {len(amenities_df)} spots")
    print(amenities_df.head())
    return amenities_df


# def save_amenities(amenities_df):
#     """Save amenities to CSV"""
#     output_dir = r'E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse'
#     amenities_df.to_csv(f'{output_dir}\\bay_area_amenities.csv', index=False)
#     print(f"Saved to {output_dir}\\bay_area_amenities.csv")


# ============================================================================
# Scrape Access Hours from Detail Pages (Optimized)
# ============================================================================

def scrape_hours(detail_urls_df):
    """Scrape hours using a single reusable WebDriver instance"""
    hours_data = defaultdict(list)

    # Create single driver instance
    driver = webdriver.Chrome()

    try:
        for i, row in detail_urls_df.iterrows():
            if i % 10 == 0:
                print(f"Processing spot {i+1}/{len(detail_urls_df)} ({row['city']})")
            
            driver.get(row['detail_url'])
            time.sleep(2)  # Wait for page load
            
            hours = driver.find_elements(By.CSS_SELECTOR, "span div[class='AccessHoursDetails']")
            for hour in hours:
                hours_data[i].append(hour.text)
    finally:
        driver.quit()

    # Convert to DataFrame
    hours_df = pd.DataFrame(dict([(k, pd.Series(v)) for k, v in hours_data.items()])).transpose()
    print(f"\nScraped hours for {len(hours_df)} spots")
    print(hours_df.head())
    return hours_df


# def save_hours(hours_df):
#     """Save hours to CSV"""
#     output_dir = r'E:\Box\Modeling and Surveys\Development\Travel Model Two Conversion\Model Inputs\2023-tm22-dev-version-05\landuse'
#     hours_df.to_csv(f'{output_dir}\\bay_area_hours.csv', index=False)
#     print(f"Saved to {output_dir}\\bay_area_hours.csv")


# ============================================================================
# Data Summary and Analysis
# ============================================================================

def print_summary(combined_df):
    """Display summary statistics"""
    print("Bay Area Parking Spots Summary")
    print("="*50)
    print(f"Total spots: {len(combined_df)}")
    print("\nSpots by city:")
    print(combined_df['city'].value_counts())
    
    print("\n" + "="*50)
    print("PRICING SUMMARY")
    print("="*50)
    print(f"\nSpots with valid prices: {combined_df['price_value'].notna().sum()}/{len(combined_df)}")
    print("\nPrice statistics by rate type:")
    print(combined_df.groupby('rate_type')['price_value'].agg(['count', 'mean', 'min', 'max']))
    
    print("\n" + "="*50)
    print("LOCATION SUMMARY")
    print("="*50)
    geocoded = combined_df['latitude'].notna().sum()
    print(f"Successfully geocoded: {geocoded}/{len(combined_df)} ({geocoded/len(combined_df)*100:.1f}%)")
    
    print("\nSample data (essential fields):")
    print(combined_df[['city', 'address', 'price_value', 'rate_type', 'latitude', 'longitude']].head(15))


# ============================================================================
# Main Execution
# ============================================================================

if __name__ == "__main__":
    print("Starting Bay Area Parking Spot Scraper")
    print("="*50)
    
    # Offer to run debug inspection first
    run_debug = input("\nRun debug inspection first to check page structure? (recommended if scraping failed before) (y/n): ")
    if run_debug.lower() == 'y':
        print("\nRunning debug inspection...")
        debug_page_structure()
        print("\nCheck debug_page_source.html to see the actual page structure.")
        continue_scraping = input("\nContinue with scraping? (y/n): ")
        if continue_scraping.lower() != 'y':
            print("Exiting...")
            exit(0)
    
    # Scrape main listings
    print("\nScraping main listing pages...")
    all_city_data, all_spot_ids = scrape_all_cities()
    
    # Combine and save results
    print("\nCombining city data...")
    combined_df = combine_city_data(all_city_data)
    save_main_results(combined_df)
    
    # Generate detail URLs
    print("\nGenerating detail URLs...")
    detail_urls_df = generate_detail_urls(all_spot_ids)
    save_detail_urls(detail_urls_df)
    
    # Skip amenities and hours scraping - not needed
    # User only needs: city, parking_type, address, name, lat, long, price_value, rate_type
    
    # Display summary
    print("\n" + "="*50)
    print_summary(combined_df)
    
    print("\n" + "="*50)
    print("Scraping complete!")
