import requests
import json
import pandas as pd
import time
import random
import os
from urllib.parse import quote
import csv

# 2GIS API Key 
API_KEY = "2424cc2b-ef4d-4d88-9dbb-89143fb588c1"
GEOCODE_URL = "https://catalog.api.2gis.com/3.0/items/geocode"

# Configuration
INPUT_CSV_HOUSES = "beeline_houses_city_1.csv"
INPUT_CSV_STREETS = "beeline_streets_city_1.csv"
OUTPUT_CSV = "beeline_ftth_with_coordinates.csv"
TEMP_CSV_PREFIX = "beeline_coordinates_partial_"
BATCH_SIZE = 100  # Save progress after processing this many records
MAX_RETRIES = 3
INITIAL_DELAY = 1
MAX_REQUESTS_PER_SECOND = 1  # Conservative rate limit
CITY_PREFIX = "Алматы г., "  # Prefix to add to all addresses

def format_address(street_name, house, sub_house=None):
    """Format the address for geocoding"""
    # Remove any existing city prefix if it's already there
    if street_name.startswith("Алматы г., "):
        street_name = street_name[len("Алматы г., "):]
    elif street_name.startswith("Алматы г, "):
        street_name = street_name[len("Алматы г, "):]
    elif street_name.startswith("г.Алматы, "):
        street_name = street_name[len("г.Алматы, "):]
    
    # Format the address with house number and subhouse if available
    if sub_house and not pd.isna(sub_house) and sub_house.strip():
        return f"Алматы г., {street_name}, {house}{sub_house}"
    else:
        return f"Алматы г., {street_name}, {house}"

def geocode_address(address, max_retries=MAX_RETRIES, initial_delay=INITIAL_DELAY):
    """
    Send address to 2GIS geocoding API and get coordinates and place type
    """
    retry_count = 0
    delay = initial_delay
    
    # URL encode the address
    encoded_address = quote(address)
    
    url = f"{GEOCODE_URL}?q={encoded_address}&fields=items.point,items.subtype,items.full_name&key={API_KEY}"
    print(f"Geocoding URL: {url}")
    
    while retry_count <= max_retries:
        try:
            response = requests.get(url)
            
            # If we hit rate limiting, wait and retry
            if response.status_code == 429:
                retry_count += 1
                wait_time = delay + random.uniform(1, 3)  # Add some randomness to the delay
                print(f"Rate limited. Waiting {wait_time:.2f} seconds before retry {retry_count}/{max_retries}")
                time.sleep(wait_time)
                delay *= 2  # Exponential backoff
                continue
                
            response.raise_for_status()  # Raise exception for other 4XX/5XX responses
            
            if response.content:
                data = response.json()
                # Debug: Print first part of response
                print(f"Response received. Status: {response.status_code}")
                if 'result' in data and 'items' in data['result'] and len(data['result']['items']) > 0:
                    print(f"Found {len(data['result']['items'])} items in response")
                    if 'point' in data['result']['items'][0]:
                        print(f"First item has coordinates: {data['result']['items'][0]['point']}")
                return data
            else:
                print(f"Empty response for address: {address}")
                return None
                
        except requests.exceptions.RequestException as e:
            if retry_count < max_retries and hasattr(e, 'response') and e.response and e.response.status_code == 429:
                retry_count += 1
                wait_time = delay + random.uniform(1, 3)
                print(f"Error: {e}. Waiting {wait_time:.2f} seconds before retry {retry_count}/{max_retries}")
                time.sleep(wait_time)
                delay *= 2  # Exponential backoff
            else:
                print(f"Error geocoding address '{address}': {e}")
                return None
                
        except json.JSONDecodeError as e:
            print(f"JSON decode error for address '{address}': {e}")
            return None
            
        except Exception as e:
            print(f"Unexpected error for address '{address}': {e}")
            return None
            
    return None  # If we've exhausted all retries

def extract_geocode_data(geocode_response):
    """
    Extract relevant data from the geocoding response
    """
    if not geocode_response or 'result' not in geocode_response or 'items' not in geocode_response['result']:
        return None
    
    items = geocode_response['result']['items']
    
    if not items:
        return None
    
    # Just take the first result
    item = items[0]
    
    result = {
        'gis_full_name': item.get('full_name', ''),
        'latitude': None,
        'longitude': None
    }
    
    # Extract coordinates if available
    if 'point' in item:
        result['latitude'] = item['point'].get('lat')
        result['longitude'] = item['point'].get('lon')
        print(f"Found coordinates: {result['latitude']}, {result['longitude']}")
    
    return result

def prepare_beeline_data():
    """
    Prepare Beeline data by merging houses and streets datasets
    """
    # Check if input files exist
    if not os.path.exists(INPUT_CSV_HOUSES):
        print(f"Error: Input file {INPUT_CSV_HOUSES} not found")
        return None
        
    if not os.path.exists(INPUT_CSV_STREETS):
        print(f"Error: Input file {INPUT_CSV_STREETS} not found")
        return None
    
    # Load the CSV files
    print(f"Loading data from {INPUT_CSV_HOUSES} and {INPUT_CSV_STREETS}...")
    try:
        houses_df = pd.read_csv(INPUT_CSV_HOUSES)
        streets_df = pd.read_csv(INPUT_CSV_STREETS)
        
        print(f"Loaded {len(houses_df)} houses and {len(streets_df)} streets")
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return None
    
    # Prepare columns for the merged dataset
    streets_df = streets_df[['street_id', 'name', 'street_type_full']]
    streets_df.rename(columns={'name': 'street_name'}, inplace=True)
    
    # Merge datasets on street_id
    merged_df = pd.merge(houses_df, streets_df, on='street_id', how='left')
    
    # Create full street name (with type)
    merged_df['full_street_name'] = merged_df.apply(
        lambda row: f"{row['street_type_full']} {row['street_name']}" if not pd.isna(row['street_type_full']) else row['street_name'], 
        axis=1
    )
    
    # Format the sub_house field from building
    merged_df['sub_house'] = merged_df['building'].apply(
        lambda x: x if not pd.isna(x) and x.strip() else None
    )
    
    # Add is_available column based on avail_status (assuming 1 means available)
    merged_df['is_available'] = merged_df['avail_status'].apply(lambda x: 1 if x == 1 else 0)
    
    # Select and rename required columns
    result_df = merged_df[['street_id', 'full_street_name', 'house', 'sub_house', 'is_available']]
    result_df.rename(columns={'full_street_name': 'street_name'}, inplace=True)
    
    print(f"Prepared {len(result_df)} addresses for geocoding")
    return result_df

def process_beeline_results():
    """
    Process Beeline results and add geocoding information
    """
    # Prepare the data
    df = prepare_beeline_data()
    if df is None:
        return
    
    # Check for existing progress
    temp_files = [f for f in os.listdir('.') if f.startswith(TEMP_CSV_PREFIX) and f.endswith('.csv')]
    
    if temp_files:
        # Find the latest progress file
        latest_file = max(temp_files, key=lambda x: int(x.replace(TEMP_CSV_PREFIX, '').replace('.csv', '')) if x.replace(TEMP_CSV_PREFIX, '').replace('.csv', '').isdigit() else 0)
        latest_index = int(latest_file.replace(TEMP_CSV_PREFIX, '').replace('.csv', ''))
        
        print(f"Found temporary file {latest_file}, resuming from index {latest_index}")
        start_index = latest_index
        
        # Load existing results
        existing_results_df = pd.read_csv(latest_file)
        existing_results = existing_results_df.to_dict('records')
    else:
        start_index = 0
        existing_results = []
    
    # Time tracking for rate limiting
    last_request_time = 0
    
    # Create a results list
    results = []
    
    total_rows = len(df)
    processed = 0
    
    try:
        # Create output CSV file and write header
        fieldnames = ['street_id', 'street_name', 'house', 'sub_house', 'is_available', 
                      'full_address', 'latitude', 'longitude', 'gis_full_name', 'provider']
        
        # Process each row
        for index, row in df.iloc[start_index:].iterrows():
            street_name = row['street_name']
            house = str(row['house'])
            sub_house = row['sub_house'] if 'sub_house' in row and not pd.isna(row['sub_house']) else ""
            
            # Format the full address
            full_address = format_address(street_name, house, sub_house)
            print(f"Processing {index+1}/{total_rows}: {full_address}")
            
            # Rate limiting
            current_time = time.time()
            elapsed = current_time - last_request_time
            sleep_time = max(0, (1.0 / MAX_REQUESTS_PER_SECOND) - elapsed)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            # Send geocoding request
            last_request_time = time.time()
            geocode_response = geocode_address(full_address)
            
            # Extract data from response
            geocode_data = extract_geocode_data(geocode_response)
            
            # Create result row
            result_row = {
                'street_id': row['street_id'],
                'street_name': street_name,
                'house': house,
                'sub_house': sub_house,
                'is_available': row['is_available'],
                'full_address': full_address,
                'latitude': None,
                'longitude': None,
                'gis_full_name': None,
                'provider': 'beeline'  # Add provider field
            }
            
            # Add geocoding data if available
            if geocode_data:
                result_row.update(geocode_data)
                
            # Debug: Print coordinates to ensure they're being captured
            print(f"Row coordinates: {result_row['latitude']}, {result_row['longitude']}")
            
            results.append(result_row)
            
            # Save progress periodically
            processed += 1
            if processed % BATCH_SIZE == 0:
                all_results = existing_results + results
                temp_df = pd.DataFrame(all_results)
                temp_file = f"{TEMP_CSV_PREFIX}{start_index + processed}.csv"
                temp_df.to_csv(temp_file, index=False)
                print(f"Saved intermediate results to {temp_file} ({processed} processed)")
        
        # Save final results
        all_results = existing_results + results
        results_df = pd.DataFrame(all_results)
        
        # Debug: Check if coordinates exist in the dataframe
        coord_count = results_df[results_df['latitude'].notna()].shape[0]
        print(f"Number of entries with coordinates: {coord_count} out of {len(results_df)}")
        
        # Ensure the DataFrame has all required columns
        for col in ['latitude', 'longitude', 'gis_full_name']:
            if col not in results_df.columns:
                results_df[col] = None
        
        # Save to CSV
        results_df.to_csv(OUTPUT_CSV, index=False)
        print(f"Saved {len(results_df)} geocoded locations to {OUTPUT_CSV}")
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Saving current progress...")
        if existing_results or results:
            all_results = existing_results + results
            results_df = pd.DataFrame(all_results)
            results_df.to_csv(OUTPUT_CSV, index=False)
            print(f"Saved {len(results_df)} geocoded locations to {OUTPUT_CSV}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Saving current progress...")
        if existing_results or results:
            all_results = existing_results + results
            results_df = pd.DataFrame(all_results)
            results_df.to_csv(OUTPUT_CSV, index=False)
            print(f"Saved {len(results_df)} geocoded locations to {OUTPUT_CSV}")

if __name__ == "__main__":
    process_beeline_results()