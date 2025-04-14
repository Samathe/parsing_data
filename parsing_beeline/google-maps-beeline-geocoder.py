def get_coordinates_from_address(address, user_agent="BeelineGeocodeScript/1.0", max_retries=3, retry_delay=2, try_alternatives=True):
    """
    Get latitude and longitude coordinates for a given address using the Nominatim API
    
    Args:
        address (str): Full address to geocode
        user_agent (str): User agent identifier for the API request
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Delay between retries in seconds
        try_alternatives (bool): Whether to try alternative address formats if main format fails
    
    Returns:
        dict or None: Dictionary with latitude and longitude if successful, None otherwise
    """
    # Initialize retry counter for the primary address
    retry_count = 0
    
    # Primary address attempt
    while retry_count < max_retries:
        try:
            if retry_count > 0:
                print(f"Retry attempt {retry_count}/{max_retries} for address: {address}")
            
            # URL encode the address
            encoded_address = urllib.parse.quote(address)
            
            # Create the Nominatim API URL
            api_url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"
            
            # Set headers (Nominatim requires a User-Agent)
            headers = {
                "User-Agent": user_agent,
                "Accept-Language": "ru,kk"  # For Russian and Kazakh languages
            }
            
            # Make the request
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Parse the JSON response
            data = response.json()
            
            # Check if we got any results
            if data:
                # Extract the coordinates from the first result
                first_result = data[0]
                
                # Print the coordinates that were found
                print(f"Found coordinates for {address}: [{first_result['lat']}, {first_result['lon']}]")
                
                return {
                    "latitude": float(first_result["lat"]),
                    "longitude": float(first_result["lon"]),
                    "gis_full_name": first_result.get("display_name", "")
                }
            else:
                print(f"✗ No results found for address: {address}")
            
            retry_count += 1
            if retry_count < max_retries:
                print(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error making request for {address}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
        except (ValueError, KeyError) as e:
            print(f"✗ Error parsing response for {address}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
    
    # If try_alternatives is True and the primary address failed, try alternative address formats
    if try_alternatives:
        # Try to extract components from the address to create alternative formats
        parts = address.split(", ")
        if len(parts) >= 3:
            city_part = parts[0]
            street_name = parts[1]
            house_part = parts[2]
            
            # Extract house number and possible subhouse
            import re
            house_match = re.match(r"([0-9/]+)([а-яА-Я]?)", house_part)
            if house_match:
                house = house_match.group(1)
                sub_house = house_match.group(2) if house_match.group(2) else None
                
                # Get alternative formats
                alternatives = try_alternative_formats(street_name, house, sub_house)
                
                print(f"Trying {len(alternatives)} alternative address formats...")
                
                # Try each alternative
                for i, alt_address in enumerate(alternatives):
                    print(f"Trying alternative format ({i+1}/{len(alternatives)}): {alt_address}")
                    
                    # URL encode the address
                    encoded_address = urllib.parse.quote(alt_address)
                    
                    # Create the Nominatim API URL
                    api_url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"
                    
                    try:
                        # Make the request with a delay to respect API rate limits
                        time.sleep(retry_delay)
                        response = requests.get(api_url, headers=headers)
                        response.raise_for_status()
                        
                        # Parse the JSON response
                        data = response.json()
                        
                        # Check if we got any results
                        if data:
                            # Extract the coordinates from the first result
                            first_result = data[0]
                            
                            # Print the coordinates that were found
                            print(f"Found coordinates for alternative address {alt_address}: [{first_result['lat']}, {first_result['lon']}]")
                            
                            return {
                                "latitude": float(first_result["lat"]),
                                "longitude": float(first_result["lon"]),
                                "gis_full_name": first_result.get("display_name", "")
                            }
                        else:
                            print(f"✗ No results found for alternative address: {alt_address}")
                            
                    except Exception as e:
                        print(f"✗ Error with alternative address {alt_address}: {e}")
        
        # Try simpler formats for the address (just part of it)
        if len(parts) >= 2:
            # Try without city if it fails
            simpler_address = ", ".join(parts[1:])
            print(f"Trying simpler address format without city: {simpler_address}")
            
            try:
                # URL encode the address
                encoded_address = urllib.parse.quote(simpler_address)
                
                # Create the Nominatim API URL
                api_url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"
                
                # Make the request with a delay to respect API rate limits
                time.sleep(retry_delay)
                response = requests.get(api_url, headers=headers)
                response.raise_for_status()
                
                # Parse the JSON response
                data = response.json()
                
                # Check if we got any results
                if data:
                    # Extract the coordinates from the first result
                    first_result = data[0]
                    
                    # Print the coordinates that were found
                    print(f"Found coordinates for simpler address {simpler_address}: [{first_result['lat']}, {first_result['lon']}]")
                    
                    return {
                        "latitude": float(first_result["lat"]),
                        "longitude": float(first_result["lon"]),
                        "gis_full_name": first_result.get("display_name", "")
                    }
                else:
                    print(f"✗ No results found for simpler address: {simpler_address}")
                    
            except Exception as e:
                print(f"✗ Error with simpler address {simpler_address}: {e}")
    
    # If we've tried everything and still failed
    print(f"All attempts failed for address: {address}")
    return None
import pandas as pd
import requests
import urllib.parse
import time
import csv
import os

# Define the correct file paths based on your folder structure
BASE_DIR = "parsing_beeline"
INPUT_CSV_HOUSES = os.path.join(BASE_DIR, "beeline_houses_city_1.csv")
INPUT_CSV_STREETS = os.path.join(BASE_DIR, "beeline_streets_city_1.csv")
COMBINED_CSV = os.path.join(BASE_DIR, "combined_ftth_results.csv")  # Added combined file
OUTPUT_CSV = os.path.join(BASE_DIR, "beeline_ftth_with_coordinates.csv")
NEW_OUTPUT_CSV = os.path.join(BASE_DIR, "beeline_with_coordinates.csv")  # New output file
LOG_FILE = os.path.join(BASE_DIR, "geocoding_results.log")
TEMP_DIR = os.path.join(BASE_DIR, "temp_geocoding")

def get_coordinates_from_address(address, user_agent="BeelineGeocodeScript/1.0", max_retries=3, retry_delay=0.1, try_alternatives=True):
    """
    Get latitude and longitude coordinates for a given address using the Nominatim API
    
    Args:
        address (str): Full address to geocode
        user_agent (str): User agent identifier for the API request
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Delay between retries in seconds
        try_alternatives (bool): Whether to try alternative address formats if main format fails
    
    Returns:
        dict or None: Dictionary with latitude and longitude if successful, None otherwise
    """
    # Initialize retry counter for the primary address
    retry_count = 0
    
    # Primary address attempt
    while retry_count < max_retries:
        try:
            if retry_count > 0:
                print(f"Retry attempt {retry_count}/{max_retries} for address: {address}")
            
            # URL encode the address
            encoded_address = urllib.parse.quote(address)
            
            # Create the Nominatim API URL
            api_url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"
            
            # Set headers (Nominatim requires a User-Agent)
            headers = {
                "User-Agent": user_agent,
                "Accept-Language": "ru,kk"  # For Russian and Kazakh languages
            }
            
            # Make the request
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Parse the JSON response
            data = response.json()
            
            # Check if we got any results
            if data:
                # Extract the coordinates from the first result
                first_result = data[0]
                
                # Print the coordinates that were found
                print(f"Found coordinates for {address}: [{first_result['lat']}, {first_result['lon']}]")
                
                return {
                    "latitude": float(first_result["lat"]),
                    "longitude": float(first_result["lon"]),
                    "gis_full_name": first_result.get("display_name", "")
                }
            else:
                print(f"✗ No results found for address: {address}")
            
            retry_count += 1
            if retry_count < max_retries:
                print(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error making request for {address}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
        except (ValueError, KeyError) as e:
            print(f"✗ Error parsing response for {address}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
    
    # If try_alternatives is True and the primary address failed, try alternative address formats
    if try_alternatives:
        # Try to extract components from the address to create alternative formats
        # Assuming format is "Алматы г., StreetName, HouseNumber"
        parts = address.split(", ")
        if len(parts) >= 3:
            city_part = parts[0]
            street_name = parts[1]
            house_part = parts[2]
            
            # Extract house number and possible subhouse
            import re
            house_match = re.match(r"([0-9/]+)([а-яА-Я]?)", house_part)
            if house_match:
                house = house_match.group(1)
                sub_house = house_match.group(2) if house_match.group(2) else None
                
                # Get alternative formats
                alternatives = try_alternative_formats(street_name, house, sub_house)
                
                print(f"Trying {len(alternatives)} alternative address formats...")
                
                # Try each alternative
                for i, alt_address in enumerate(alternatives):
                    print(f"Trying alternative format ({i+1}/{len(alternatives)}): {alt_address}")
                    
                    # URL encode the address
                    encoded_address = urllib.parse.quote(alt_address)
                    
                    # Create the Nominatim API URL
                    api_url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"
                    
                    try:
                        # Make the request with a delay to respect API rate limits
                        time.sleep(retry_delay)
                        response = requests.get(api_url, headers=headers)
                        response.raise_for_status()
                        
                        # Parse the JSON response
                        data = response.json()
                        
                        # Check if we got any results
                        if data:
                            # Extract the coordinates from the first result
                            first_result = data[0]
                            
                            # Print the coordinates that were found
                            print(f"Found coordinates for alternative address {alt_address}: [{first_result['lat']}, {first_result['lon']}]")
                            
                            return {
                                "latitude": float(first_result["lat"]),
                                "longitude": float(first_result["lon"]),
                                "gis_full_name": first_result.get("display_name", "")
                            }
                        else:
                            print(f"✗ No results found for alternative address: {alt_address}")
                            
                    except Exception as e:
                        print(f"✗ Error with alternative address {alt_address}: {e}")
    
    # If we've tried everything and still failed
    print(f"All attempts failed for address: {address}")
    return None

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
    if sub_house and pd.notna(sub_house) and str(sub_house).strip():
        return f"Алматы г., {street_name}, {house}{sub_house}"
    else:
        return f"Алматы г., {street_name}, {house}"
        
def try_alternative_formats(street_name, house, sub_house=None):
    """Generate alternative address formats to try if the primary format fails"""
    alternatives = []
    
    # Extract the essence of the street name (remove prefixes like "улица", "микрорайон", etc.)
    clean_street = street_name
    prefixes = ["улица ", "ул. ", "проспект ", "пр. ", "микрорайон ", "мкр. ", "мкр "]
    for prefix in prefixes:
        if clean_street.lower().startswith(prefix):
            clean_street = clean_street[len(prefix):]
            break
    
    # Format house with subhouse if needed
    house_part = f"{house}{sub_house}" if sub_house and pd.notna(sub_house) and str(sub_house).strip() else house
    
    # Try different formats based on sample formats requested
    alternatives.extend([
        # Format 1: микрорайон Name, ул. Street, HouseNumber
        f"микрорайон {clean_street}, ул. {clean_street}, {house_part}",
        
        # Format 2: Just street and house
        f"ул. {clean_street}, {house_part}",
        
        # Format 3: Street, house, city
        f"ул. {clean_street}, {house_part}, Алматы",
        
        # Format 4: Just the raw address without city prefix
        f"{street_name}, {house_part}",
        
        # Format 5: Try with "город" prefix
        f"город Алматы, {street_name}, {house_part}",
        
        # Format 6: Try with just the neighborhood/district and house
        f"{clean_street}, {house_part}",
        
        # Format 7: Try with alternative city spellings
        f"Almaty, {street_name}, {house_part}",
        
        # Format 8: Try with г. prefix
        f"г. Алматы, {street_name}, {house_part}"
    ])
    
    # Return unique alternatives only (remove duplicates)
    return list(set(alternatives))

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
        lambda row: f"{row['street_type_full']} {row['street_name']}" if pd.notna(row['street_type_full']) else row['street_name'], 
        axis=1
    )
    
    # Format the sub_house field from building
    merged_df['sub_house'] = merged_df['building'].apply(
        lambda x: x if pd.notna(x) and str(x).strip() else ""
    )
    
    # Add is_available column based on avail_status (assuming 1 means available)
    merged_df['is_available'] = merged_df['avail_status'].apply(lambda x: 1 if x == 1 else 0)
    
    # Select and rename required columns
    result_df = merged_df[['street_id', 'full_street_name', 'house', 'sub_house', 'is_available']]
    result_df.rename(columns={'full_street_name': 'street_name'}, inplace=True)
    
    print(f"Prepared {len(result_df)} addresses for geocoding")
    return result_df

def display_real_time_progress(current, total, address, coords=None):
    """Display real-time progress with address details"""
    progress_pct = (current / total) * 100
    progress_bar = "▓" * int(progress_pct / 2) + "░" * (50 - int(progress_pct / 2))
    
    if coords:
        status = f"✓ Found: [{coords['latitude']:.6f}, {coords['longitude']:.6f}]"
    else:
        status = "✗ Not found"
        
    print(f"\r[{progress_bar}] {current}/{total} ({progress_pct:.1f}%) | {address} | {status}", end="")

def process_geocoding(existing_file=None, limit=None, max_retries=3):
    """
    Process Beeline data and add missing coordinates
    
    Args:
        existing_file: Path to existing CSV file with partial data
        limit: Optional limit on number of addresses to process (for testing)
        max_retries: Maximum number of retry attempts for each address
    """
    # Check if we should use the combined file first
    if os.path.exists(COMBINED_CSV):
        print(f"Loading data from combined file: {COMBINED_CSV}")
        df = pd.read_csv(COMBINED_CSV)
        print(f"Loaded {len(df)} records from combined file")
    elif existing_file and os.path.exists(existing_file):
        print(f"Loading existing data from {existing_file}")
        df = pd.read_csv(existing_file)
        print(f"Loaded {len(df)} records from existing file")
    else:
        # Prepare new data
        print("No existing file specified or found. Preparing new data...")
        df = prepare_beeline_data()
        if df is None:
            print("Failed to prepare data. Exiting.")
            return
        
        # Add empty columns for coordinates
        df['latitude'] = None
        df['longitude'] = None
        df['gis_full_name'] = None
        df['full_address'] = None
        df['provider'] = 'beeline'
        
        # Format full addresses
        df['full_address'] = df.apply(
            lambda row: format_address(row['street_name'], row['house'], row['sub_house']), 
            axis=1
        )
    
    # Count records with coordinates
    with_coords = df[df['latitude'].notna() & df['longitude'].notna()].shape[0]
    missing_coords = df[df['latitude'].isna() | df['longitude'].isna()].shape[0]
    print(f"Records with coordinates: {with_coords}")
    print(f"Records missing coordinates: {missing_coords}")
    
    # Setup for geocoding
    batch_size = 50  # Increased batch size for saving progress
    rate_limit_delay = 1.0  # Slightly reduced delay to speed up processing but still respect API limits
    
    # Process records missing coordinates
    missing_df = df[df['latitude'].isna() | df['longitude'].isna()]
    
    # Print information about the number of rows
    print(f"Total rows in dataset: {len(df)}")
    print(f"Rows missing coordinates: {len(missing_df)}")
    
    # If no rows are missing coordinates in the combined file, we can repopulate
    # a subset to test different geocoding approaches
    if len(missing_df) == 0 and os.path.exists(COMBINED_CSV):
        print("No missing coordinates. Selecting a subset to test different geocoding approaches...")
        # Select a random subset of rows to re-geocode (for testing purposes)
        test_subset = df.sample(min(100, len(df)))
        test_subset_indices = test_subset.index
        df.loc[test_subset_indices, 'latitude'] = None
        df.loc[test_subset_indices, 'longitude'] = None
        df.loc[test_subset_indices, 'gis_full_name'] = None
        missing_df = df[df['latitude'].isna() | df['longitude'].isna()]
        print(f"Selected {len(missing_df)} rows for re-geocoding with different formats")
    
    # Apply limit if specified (for testing only - set to None in production)
    if limit is not None and limit > 0:
        missing_df = missing_df.head(limit)
        print(f"Limiting to {limit} addresses for testing")
    
    total_missing = len(missing_df)
    
    if total_missing == 0:
        print("No addresses missing coordinates. Saving current data.")
        df.to_csv(OUTPUT_CSV, index=False)
        df.to_csv(NEW_OUTPUT_CSV, index=False)  # Save to the new file as well
        print(f"Data also saved to {NEW_OUTPUT_CSV}")
        return
    
    print(f"Processing {total_missing} addresses that need coordinates...")
    print(f"Will process ALL addresses until completion.")
    print(f"Results will be shown in real-time. Press Ctrl+C to stop and save progress.\n")
    print("=" * 80)
    print("REAL-TIME GEOCODING RESULTS")
    print("=" * 80)
    
    # Create temporary files folder
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Create a results log file or append to existing one
    log_mode = 'a' if os.path.exists(LOG_FILE) else 'w'
    with open(LOG_FILE, log_mode, encoding='utf-8') as log:
        if log_mode == 'w':  # Only write header for new file
            log.write("street_id,street_name,house,full_address,latitude,longitude,status\n")
    
    processed = 0
    successful = 0
    retry_success = 0  # Counter for addresses that required retries or alternative formats
    failure_counter = 0  # Track consecutive failures
    
    # Create a list to store all found coordinates for final printing
    all_found_coordinates = []
    
    try:
        # Initialize progress display
        print("\n\n")  # Make space for progress display
        
        # Process in batches to save progress regularly
        total_batches = (total_missing + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min((batch_num + 1) * batch_size, total_missing)
            
            print(f"\nProcessing batch {batch_num+1}/{total_batches} (records {start_idx+1}-{end_idx} of {total_missing})")
            
            # Get indices for this batch
            batch_indices = missing_df.index[start_idx:end_idx]
            
            for idx in batch_indices:
                row = df.loc[idx]
                address = row['full_address']
                street_id = row['street_id']
                street_name = row['street_name']
                house = row['house']
                sub_house = row['sub_house'] if 'sub_house' in row else ""
                
                print(f"\nProcessing address: {address}")
                
                # Get coordinates with multiple retry attempts
                coordinates = get_coordinates_from_address(address, max_retries=max_retries)
                
                if coordinates:
                    # Update the main dataframe
                    df.loc[idx, 'latitude'] = coordinates['latitude']
                    df.loc[idx, 'longitude'] = coordinates['longitude']
                    df.loc[idx, 'gis_full_name'] = coordinates['gis_full_name']
                    successful += 1
                    failure_counter = 0  # Reset failure counter on success
                    status = "Success"
                    
                    # Store coordinates for final summary
                    all_found_coordinates.append({
                        'address': address,
                        'latitude': coordinates['latitude'],
                        'longitude': coordinates['longitude']
                    })
                    
                    # Log the successful result
                    with open(LOG_FILE, 'a', encoding='utf-8') as log:
                        log.write(f"{street_id},{street_name},{house},\"{address}\",{coordinates['latitude']},{coordinates['longitude']},Success\n")
                else:
                    status = "Not Found"
                    failure_counter += 1
                    # Log the failure
                    with open(LOG_FILE, 'a', encoding='utf-8') as log:
                        log.write(f"{street_id},{street_name},{house},\"{address}\",,,Not Found\n")
                
                # Update progress display
                processed += 1
                display_real_time_progress(processed, total_missing, address, coordinates)
                print()  # Move to next line for next progress update
                
                # Print detailed information for each processed address
                print(f"PROCESSED [{processed}/{total_missing}]: {address}")
                if coordinates:
                    print(f"  ✓ COORDINATES: Lat={coordinates['latitude']:.6f}, Lon={coordinates['longitude']:.6f}")
                    print(f"  ✓ FULL NAME: {coordinates['gis_full_name']}")
                else:
                    print(f"  ✗ NO COORDINATES FOUND")
                print("-" * 80)
                
                # If we've had too many consecutive failures, take a longer break
                if failure_counter >= 5:
                    print("Too many consecutive failures. Taking a longer break (10 seconds)...")
                    time.sleep(10)
                    failure_counter = 0  # Reset after break
                
                # Respect rate limit
                time.sleep(rate_limit_delay)
            
            # Save progress at the end of each batch
            temp_file = os.path.join(TEMP_DIR, f"beeline_coords_progress_batch_{batch_num+1}.csv")
            df.to_csv(temp_file, index=False)
            print(f"Saved batch progress to {temp_file} ({processed}/{total_missing})")
            print(f"Success rate so far: {successful}/{processed} ({(successful/processed)*100:.1f}%)")
            
            # Also save to main output files periodically
            if batch_num % 5 == 0 or batch_num == total_batches - 1:
                df.to_csv(OUTPUT_CSV, index=False)
                df.to_csv(NEW_OUTPUT_CSV, index=False)
                print(f"Saved interim results to {OUTPUT_CSV} and {NEW_OUTPUT_CSV}")
            
            print("-" * 80)
    
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Saving current progress...")
    except Exception as e:
        print(f"\n\nError during processing: {e}")
        import traceback
        traceback.print_exc()
        print("Saving current progress...")
    
    # Save final results
    df.to_csv(OUTPUT_CSV, index=False)
    df.to_csv(NEW_OUTPUT_CSV, index=False)  # Save to the new file as well
    print(f"\n\nSaved {len(df)} records to {OUTPUT_CSV}")
    print(f"Data also saved to {NEW_OUTPUT_CSV}")
    
    # Count final statistics
    final_with_coords = df[df['latitude'].notna() & df['longitude'].notna()].shape[0]
    final_missing = df[df['latitude'].isna() | df['longitude'].isna()].shape[0]
    print(f"Final statistics:")
    print(f"Records with coordinates: {final_with_coords}")
    print(f"Records still missing coordinates: {final_missing}")
    print(f"Processed in this run: {processed} addresses")
    if processed > 0:
        print(f"Success rate: {successful}/{processed} ({(successful/processed)*100:.1f}%)")
    print(f"Detailed results have been logged to {LOG_FILE}")
    
    # Print summary of all found coordinates
    if all_found_coordinates:
        print("\n\n" + "=" * 80)
        print("SUMMARY OF ALL FOUND COORDINATES")
        print("=" * 80)
        for i, coord in enumerate(all_found_coordinates, 1):
            print(f"{i}. {coord['address']}: [{coord['latitude']:.6f}, {coord['longitude']:.6f}]")

if __name__ == "__main__":
    # Check if we have an existing file with partial coordinates
    existing_file = os.path.join(BASE_DIR, "beeline_ftth_with_coordinates.csv")
    combined_file = os.path.join(BASE_DIR, "combined_ftth_results.csv")
    
    # Set limit for testing (set to None for processing all addresses)
    test_limit = None  # Process ALL records
    
    # Set the number of retry attempts (increase for better reliability)
    max_retries = 5
    
    # Print current directory and check if files exist
    print(f"Current working directory: {os.getcwd()}")
    print(f"Checking if input files exist:")
    print(f"  {INPUT_CSV_HOUSES}: {os.path.exists(INPUT_CSV_HOUSES)}")
    print(f"  {INPUT_CSV_STREETS}: {os.path.exists(INPUT_CSV_STREETS)}")
    print(f"  {existing_file}: {os.path.exists(existing_file)}")
    print(f"  {combined_file}: {os.path.exists(combined_file)}")
    
    # Create a process restart mechanism
    restart_count = 0
    max_restarts = 3
    
    while restart_count < max_restarts:
        try:
            # First try to use the combined file if it exists
            if os.path.exists(combined_file):
                print(f"Using combined data file: {combined_file}")
                process_geocoding(existing_file=combined_file, limit=test_limit, max_retries=max_retries)
            elif os.path.exists(existing_file):
                process_geocoding(existing_file=existing_file, limit=test_limit, max_retries=max_retries)
            else:
                process_geocoding(limit=test_limit, max_retries=max_retries)
            
            # If we completed successfully, break the loop
            print("Processing completed successfully!")
            break
            
        except Exception as e:
            restart_count += 1
            print(f"\n\nCritical error occurred: {e}")
            import traceback
            traceback.print_exc()
            
            if restart_count < max_restarts:
                print(f"Restarting process (attempt {restart_count}/{max_restarts})...")
                time.sleep(30)  # Wait 30 seconds before restarting
            else:
                print("Maximum restart attempts reached. Exiting.")
    
    print("\nScript execution completed.")