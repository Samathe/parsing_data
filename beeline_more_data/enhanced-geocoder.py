#!/usr/bin/env python3
"""
Enhanced Kazakhstan Telecom Data Collector and Geocoder
- Collects address data from Beeline Kazakhstan API for all cities
- Geocodes addresses using 2GIS API with improved reliability
- Manages the process with robust error handling, logging, and progress tracking
- Implements improved batching, checkpoints, and fallback strategies

Usage:
    python enhanced_geocoder.py --cities [city_ids] --mode [collect|geocode|all|merge]
    python enhanced_geocoder.py --mode all                  # Process all cities
    python enhanced_geocoder.py --cities 1 2 3 --mode all   # Process specific cities
    python enhanced_geocoder.py --mode merge                # Merge all results
"""

import argparse
import csv
import json
import logging
import os
import random
import requests
import sys
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import quote
from tqdm import tqdm

# Configure logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"geocoding_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnhancedKazakhstanGeocoderManager:
    """Enhanced manager class to coordinate data collection and geocoding for all Kazakhstan"""
    
    BASE_URL = "https://beeline.kz/restservices/telco"
    GEOCODE_URL = "https://catalog.api.2gis.com/3.0/items/geocode"
    
    # Kazakhstan bounding box (rough coordinates for validation)
    KZ_MIN_LAT, KZ_MAX_LAT = 40.0, 56.0
    KZ_MIN_LON, KZ_MAX_LON = 45.0, 88.0
    
    def __init__(self, api_key, mode="all", city_ids=None, max_workers=5, batch_size=100, 
                 max_retries=3, request_delay=1.5, input_dir="beeline_data", output_dir="geocoded_data"):
        
        # 2GIS API Key
        self.API_KEY = api_key
        
        # Processing mode
        self.mode = mode
        
        # Configuration
        self.city_ids = city_ids
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.request_delay = request_delay
        
        # Directories
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.cities_file = "beeline_cities.csv"
        self.checkpoint_dir = os.path.join(self.output_dir, "checkpoints")
        
        # Create directories
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        # HTTP Headers with more realistic browser simulation
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8,kk;q=0.7",
            "Referer": "https://beeline.kz/",
            "Origin": "https://beeline.kz",
            "Connection": "keep-alive"
        }
        
        # Stats
        self.total_processed = 0
        self.total_geocoded = 0
        self.successful_geocodes = 0
        self.failed_geocodes = 0
        self.start_time = time.time()
        
        # Dynamic rate limiting
        self.current_delay = request_delay
        self.consecutive_429s = 0
        self.consecutive_successes = 0
        
        # City data cache for faster access
        self.city_name_cache = {}
    
    def run(self):
        """Main execution method with enhanced robustness"""
        logger.info(f"Starting Enhanced Kazakhstan Geocoder in {self.mode} mode")
        
        # Handle merge mode separately
        if self.mode == 'merge':
            self.merge_city_results()
            return
        
        # Get cities
        cities = self.get_cities()
        if not cities:
            logger.error("No cities found. Exiting.")
            return
        
        # Filter cities if specific IDs were provided
        if self.city_ids:
            cities = [city for city in cities if int(city['city_id']) in self.city_ids]
            logger.info(f"Filtered to {len(cities)} cities based on provided IDs")
        
        # Populate city name cache for faster lookup
        self.city_name_cache = {int(city['city_id']): city['name'] for city in cities}
        
        # Process each city with better status reporting
        for idx, city in enumerate(cities, 1):
            city_id = int(city['city_id'])
            city_name = city['name']
            
            logger.info(f"========== Processing city {idx}/{len(cities)}: {city_name} (ID: {city_id}) ==========")
            
            try:
                # Step 1: Collect data from Beeline API (if mode is 'collect' or 'all')
                if self.mode in ['collect', 'all']:
                    logger.info(f"Collecting Beeline data for city {city_name}")
                    self.collect_city_data(city_id, city_name)
                
                # Step 2: Geocode addresses (if mode is 'geocode' or 'all')
                if self.mode in ['geocode', 'all']:
                    logger.info(f"Geocoding addresses for city {city_name}")
                    self.geocode_city_data(city_id, city_name)
                    
                # Report progress after each city
                elapsed_time = time.time() - self.start_time
                logger.info(f"City {city_name} completed. Time taken: {elapsed_time:.2f} seconds")
                logger.info(f"Current progress: {idx}/{len(cities)} cities processed ({(idx/len(cities))*100:.1f}%)")
                
            except Exception as e:
                logger.error(f"Error processing city {city_name}: {e}")
                logger.info("Continuing with next city...")
        
        # Print summary
        elapsed_time = time.time() - self.start_time
        logger.info(f"========== Process completed ==========")
        logger.info(f"Total time: {elapsed_time:.2f} seconds")
        logger.info(f"Total processed: {self.total_processed} addresses")
        logger.info(f"Total geocoded: {self.total_geocoded} addresses")
        logger.info(f"Geocoding success rate: {(self.total_geocoded/max(1, self.total_processed))*100:.2f}%")
    
    def fetch_with_retry(self, url, max_retries=None, initial_delay=None):
        """Make an HTTP request with retry logic and dynamic rate limiting"""
        if max_retries is None:
            max_retries = self.max_retries
        if initial_delay is None:
            initial_delay = self.current_delay
            
        retry_count = 0
        delay = initial_delay
        
        while retry_count <= max_retries:
            try:
                # Apply current delay for rate limiting
                time.sleep(self.current_delay)
                
                response = requests.get(url, headers=self.headers, timeout=15)
                
                # If we hit rate limiting, wait and retry with exponential backoff
                if response.status_code == 429:
                    retry_count += 1
                    self.consecutive_429s += 1
                    self.consecutive_successes = 0
                    
                    # Increase delay exponentially
                    self.current_delay = min(self.current_delay * 1.5, 10.0)  # Cap at 10 seconds
                    
                    wait_time = delay + random.uniform(1, 3)  # Add some randomness
                    logger.warning(f"Rate limited (429). Increasing delay to {self.current_delay:.2f}s. Waiting {wait_time:.2f}s before retry {retry_count}/{max_retries}")
                    time.sleep(wait_time)
                    delay *= 2  # Exponential backoff
                    continue
                    
                # Successful request
                if response.status_code == 200:
                    self.consecutive_successes += 1
                    self.consecutive_429s = 0
                    
                    # Gradually decrease delay after consistent successes
                    if self.consecutive_successes > 10 and self.current_delay > self.request_delay:
                        self.current_delay = max(self.current_delay * 0.9, self.request_delay)
                
                response.raise_for_status()  # Raise exception for other 4XX/5XX responses
                
                if response.content:
                    return response.json()
                else:
                    logger.warning(f"Empty response from URL: {url}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                if retry_count < max_retries and hasattr(e, 'response') and e.response and e.response.status_code == 429:
                    retry_count += 1
                    wait_time = delay + random.uniform(1, 3)
                    logger.warning(f"Error: {e}. Waiting {wait_time:.2f} seconds before retry {retry_count}/{max_retries}")
                    time.sleep(wait_time)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Error fetching URL {url}: {e}")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for URL {url}: {e}")
                return None
                
            except Exception as e:
                logger.error(f"Unexpected error for URL {url}: {e}")
                return None
                
        return None  # If we've exhausted all retries
    
    def get_cities(self):
        """Get cities either from API or from cached file with improved caching"""
        if os.path.exists(self.cities_file):
            try:
                with open(self.cities_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    cities = list(reader)
                logger.info(f"Loaded {len(cities)} cities from {self.cities_file}")
                return cities
            except Exception as e:
                logger.error(f"Error loading cities from file: {e}")
                
        # If file doesn't exist or there was an error, fetch from API
        logger.info("Fetching cities from Beeline API")
        url = f"{self.BASE_URL}/cities"
        cities = self.fetch_with_retry(url)
        
        if cities:
            # Save cities to CSV
            with open(self.cities_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=cities[0].keys())
                writer.writeheader()
                writer.writerows(cities)
            
            logger.info(f"Saved {len(cities)} cities to {self.cities_file}")
            return cities
        
        return []
    
    def fetch_streets(self, city_id):
        """Fetch all streets for the given city with better caching"""
        streets_file = os.path.join(self.input_dir, f"beeline_streets_city_{city_id}.csv")
        
        # Check if streets file already exists
        if os.path.exists(streets_file):
            try:
                streets_df = pd.read_csv(streets_file)
                streets = streets_df.to_dict('records')
                logger.info(f"Loaded {len(streets)} streets from existing file for city {city_id}")
                return streets
            except Exception as e:
                logger.error(f"Error loading streets file: {e}")
                logger.info("Will attempt to re-fetch streets from API")
        
        # Fetch from API
        url = f"{self.BASE_URL}/streets?cityId={city_id}"
        streets = self.fetch_with_retry(url)
        
        if streets:
            with open(streets_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=streets[0].keys())
                writer.writeheader()
                writer.writerows(streets)
            
            logger.info(f"Saved {len(streets)} streets to {streets_file}")
            return streets
        
        logger.warning(f"No streets found for city {city_id}")
        return []
    
    def process_street(self, city_id, street):
        """Process a single street and fetch its houses with better error handling"""
        street_id = street['street_id']
        street_name = street.get('name', 'Unknown Street')
        
        # Add retry logic specifically for house fetching
        for attempt in range(self.max_retries):
            url = f"{self.BASE_URL}/houses?cityId={city_id}&streetId={street_id}"
            houses = self.fetch_with_retry(url)
            
            if houses is not None:
                # Enhance houses with street information
                for house in houses:
                    house['street_id'] = street_id
                    house['city_id'] = city_id
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.2)
                return houses
            
            # If we got None, retry
            time.sleep(2 ** attempt)  # Exponential backoff
        
        return []  # Return empty list if all attempts failed
    
    def collect_city_data(self, city_id, city_name):
        """Collect all street and house data for a city with checkpoint support"""
        houses_file = os.path.join(self.input_dir, f"beeline_houses_city_{city_id}.csv")
        checkpoint_file = os.path.join(self.checkpoint_dir, f"collect_checkpoint_city_{city_id}.json")
        
        # Check if houses file already exists and is complete
        if os.path.exists(houses_file):
            try:
                houses_df = pd.read_csv(houses_file)
                if len(houses_df) > 0:
                    logger.info(f"Houses file for city {city_id} already exists with {len(houses_df)} records")
                    # Verify if the file has required fields
                    required_fields = ['house_id', 'street_id', 'city_id', 'house']
                    if all(field in houses_df.columns for field in required_fields):
                        logger.info(f"Houses file for city {city_id} appears complete - skipping collection")
                        return
                    else:
                        logger.warning(f"Houses file for city {city_id} is missing required fields - re-collecting")
            except Exception as e:
                logger.error(f"Error checking existing houses file: {e}")
        
        # Fetch streets for this city
        streets = self.fetch_streets(city_id)
        if not streets:
            logger.warning(f"No streets found for city {city_name} - skipping")
            return
        
        total_streets = len(streets)
        logger.info(f"Found {total_streets} streets in {city_name}")
        
        # Check for checkpoint to resume progress
        completed_street_ids = set()
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
                    completed_street_ids = set(checkpoint.get('completed_street_ids', []))
                    logger.info(f"Resuming from checkpoint with {len(completed_street_ids)} completed streets")
            except Exception as e:
                logger.error(f"Error loading checkpoint: {e}")
                completed_street_ids = set()
        
        # Filter out already completed streets
        streets_to_process = [street for street in streets if str(street['street_id']) not in completed_street_ids]
        logger.info(f"Remaining streets to process: {len(streets_to_process)}/{total_streets}")
        
        all_houses = []
        temp_file = os.path.join(self.input_dir, f"beeline_houses_temp_{city_id}.csv")
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_street = {
                executor.submit(self.process_street, city_id, street): street
                for street in streets_to_process
            }
            
            # Process streets with progress bar
            with tqdm(total=len(streets_to_process), desc=f"Collecting streets in {city_name}") as pbar:
                completed = 0
                batch_count = 0
                newly_completed_street_ids = set()
                
                for future in as_completed(future_to_street):
                    street = future_to_street[future]
                    try:
                        houses = future.result()
                        if houses:
                            all_houses.extend(houses)
                            newly_completed_street_ids.add(str(street['street_id']))
                        
                        completed += 1
                        pbar.update(1)
                        
                        # Save batch periodically
                        if len(all_houses) >= self.batch_size or completed == len(streets_to_process):
                            if all_houses:
                                self.save_houses_batch(all_houses, temp_file, batch_count == 0)
                                batch_count += 1
                                all_houses = []
                        
                        # Update checkpoint periodically
                        if completed % 10 == 0 or completed == len(streets_to_process):
                            all_completed = completed_street_ids.union(newly_completed_street_ids)
                            self.save_checkpoint(checkpoint_file, {'completed_street_ids': list(all_completed)})
                            logger.debug(f"Updated checkpoint: {len(all_completed)} streets completed")
                        
                    except Exception as e:
                        logger.error(f"Error processing street {street.get('name', 'Unknown')}: {e}")
                        pbar.update(1)
        
        # Update final checkpoint
        all_completed = completed_street_ids.union(newly_completed_street_ids)
        self.save_checkpoint(checkpoint_file, {'completed_street_ids': list(all_completed)})
        
        # Rename temp file to final file if we have data
        if os.path.exists(temp_file):
            try:
                if os.path.exists(houses_file):
                    os.remove(houses_file)
                os.rename(temp_file, houses_file)
                logger.info(f"Renamed temporary file to {houses_file}")
            except Exception as e:
                logger.error(f"Error renaming temp file: {e}")
    
    def save_checkpoint(self, checkpoint_file, data):
        """Save checkpoint data to file"""
        try:
            with open(checkpoint_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
    
    def save_houses_batch(self, houses, file_path, write_header=False):
        """Save a batch of houses to CSV file"""
        if not houses:
            return
        
        mode = 'w' if write_header else 'a'
        
        try:
            with open(file_path, mode, newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=houses[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(houses)
            
            logger.debug(f"{len(houses)} houses {'saved to' if write_header else 'appended to'} {file_path}")
            self.total_processed += len(houses)
        except Exception as e:
            logger.error(f"Error saving houses batch: {e}")
    
    def format_address(self, street_name, house, sub_house=None, city_name=None):
        """Format the address for geocoding with enhanced variants"""
        # City name handling
        if city_name is None:
            city_name = "Алматы"  # Default city
            
        # Clean up inputs
        if isinstance(house, float) and house.is_integer():
            house = int(house)
        house = str(house).strip()
        
        # Handle sub_house variations
        sub_house_str = ""
        if sub_house and not pd.isna(sub_house) and str(sub_house).strip():
            sub_house_str = str(sub_house).strip()
        
        # Remove any existing city prefix
        prefixes = [f"{city_name} г., ", f"{city_name} г, ", f"г.{city_name}, ", f"{city_name}, "]
        for prefix in prefixes:
            if street_name.startswith(prefix):
                street_name = street_name[len(prefix):]
        
        # Format the address with house number and subhouse if available
        if sub_house_str:
            return f"{city_name} г., {street_name}, {house}{sub_house_str}"
        else:
            return f"{city_name} г., {street_name}, {house}"
    
    def create_address_variations(self, street_name, house, sub_house, city_name):
        """Create variations of the address format to increase geocoding success"""
        variations = []
        
        # Clean inputs
        if isinstance(house, float) and house.is_integer():
            house = int(house)
        house = str(house).strip()
        
        sub_house_str = ""
        if sub_house and not pd.isna(sub_house) and str(sub_house).strip():
            sub_house_str = str(sub_house).strip()
        
        # Standard format
        variations.append(f"{city_name} г., {street_name}, {house}{sub_house_str}")
        
        # Alternative formats
        variations.append(f"{city_name}, {street_name}, {house}{sub_house_str}")
        variations.append(f"г. {city_name}, {street_name}, {house}{sub_house_str}")
        
        # Format with dash if sub_house
        if sub_house_str:
            # Try with dash
            if not sub_house_str.startswith('-'):
                variations.append(f"{city_name} г., {street_name}, {house}-{sub_house_str}")
            
            # Try without sub_house as a fallback
            variations.append(f"{city_name} г., {street_name}, {house}")
        
        # Return unique variations
        return list(set(variations))
    
    def geocode_address(self, address_variations):
        """Try geocoding with multiple address variations"""
        for address in address_variations:
            # URL encode the address
            encoded_address = quote(address)
            
            url = f"{self.GEOCODE_URL}?q={encoded_address}&fields=items.point,items.subtype,items.full_name&key={self.API_KEY}"
            
            # Enforce rate limiting
            time.sleep(self.current_delay)
            
            response = self.fetch_with_retry(url)
            
            # If we get a valid response, return it
            if response and 'result' in response and 'items' in response['result'] and response['result']['items']:
                self.successful_geocodes += 1
                return response, address  # Return the successful address too
            
            # Brief delay between variations
            time.sleep(0.5)
        
        # If all variations failed
        self.failed_geocodes += 1
        return None, None
    
    def extract_geocode_data(self, geocode_response, used_address):
        """Extract relevant data from the geocoding API response"""
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
            'longitude': None,
            'geocoded_address': used_address,  # Add the address that was successfully used
            'geocode_confidence': 1.0 if len(items) == 1 else 0.8,  # Simple confidence measure
        }
        
        # Extract coordinates if available
        if 'point' in item:
            result['latitude'] = item['point'].get('lat')
            result['longitude'] = item['point'].get('lon')
            
            # Only count as geocoded if we got coordinates
            if result['latitude'] is not None and result['longitude'] is not None:
                # Validate coordinates are within Kazakhstan
                if (self.KZ_MIN_LAT <= result['latitude'] <= self.KZ_MAX_LAT and 
                    self.KZ_MIN_LON <= result['longitude'] <= self.KZ_MAX_LON):
                    self.total_geocoded += 1
                else:
                    # Mark as suspicious if outside Kazakhstan bounds
                    result['geocode_confidence'] = 0.3
                    logger.warning(f"Suspicious coordinates outside Kazakhstan bounds: {result['latitude']}, {result['longitude']}")
        
        return result
    
    def process_address(self, row, city_name):
        """Process a single address for geocoding with fallback strategies"""
        street_name = row['street_name']
        house = str(row['house'])
        sub_house = row.get('sub_house', '') if 'sub_house' in row and not pd.isna(row['sub_house']) else ""
        
        # Create address variations to try
        address_variations = self.create_address_variations(street_name, house, sub_house, city_name)
        
        # Send geocoding request with variations
        geocode_response, used_address = self.geocode_address(address_variations)
        
        # Extract data from response
        geocode_data = self.extract_geocode_data(geocode_response, used_address) if geocode_response else None
        
        # Create result row
        result_row = {
            'street_id': row['street_id'],
            'city_id': row['city_id'],
            'street_name': street_name,
            'house': house,
            'sub_house': sub_house,
            'is_available': row.get('is_available', 1),  # Default to 1 if not present
            'full_address': address_variations[0] if address_variations else "",  # Use first variation as standard
            'latitude': None,
            'longitude': None,
            'gis_full_name': None,
            'geocoded_address': None,
            'geocode_confidence': 0.0,
            'provider': 'beeline'
        }
        
        # Add geocoding data if available
        if geocode_data:
            result_row.update(geocode_data)
        
        return result_row
    
    def prepare_city_data(self, city_id, city_name):
        """Prepare data for geocoding by merging houses and streets data"""
        # Input file paths
        houses_file = os.path.join(self.input_dir, f"beeline_houses_city_{city_id}.csv")
        streets_file = os.path.join(self.input_dir, f"beeline_streets_city_{city_id}.csv")
        
        # Check if input files exist
        if not os.path.exists(houses_file):
            logger.error(f"Error: Input file {houses_file} not found")
            return None
            
        if not os.path.exists(streets_file):
            logger.error(f"Error: Input file {streets_file} not found")
            return None
        
        # Load the CSV files
        logger.info(f"Loading data from {houses_file} and {streets_file}...")
        try:
            houses_df = pd.read_csv(houses_file)
            streets_df = pd.read_csv(streets_file)
            
            logger.info(f"Loaded {len(houses_df)} houses and {len(streets_df)} streets")
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
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
            lambda x: str(x) if not pd.isna(x) and str(x).strip() else ""
        )
        
        # Add is_available column based on avail_status
        merged_df['is_available'] = merged_df['avail_status'].apply(lambda x: 1 if x == 1 else 0)
        
        # Select and rename required columns
        result_df = merged_df[['street_id', 'full_street_name', 'house', 'sub_house', 'is_available', 'city_id']]
        result_df.rename(columns={'full_street_name': 'street_name'}, inplace=True)
        
        logger.info(f"Prepared {len(result_df)} addresses for geocoding")
        return result_df
                               
    def geocode_city_data(self, city_id, city_name):
    """Geocode addresses for a specific city with robust checkpointing and error handling"""
    # Output file
    output_file = os.path.join(self.output_dir, f"geocoded_city_{city_id}.csv")
    checkpoint_file = os.path.join(self.checkpoint_dir, f"geocode_checkpoint_city_{city_id}.json")
    
    # Check if output file already exists and is complete
    if os.path.exists(output_file):
        try:
            output_df = pd.read_csv(output_file)
            required_fields = ['street_id', 'street_name', 'house', 'latitude', 'longitude']
            
            if len(output_df) > 0 and all(field in output_df.columns for field in required_fields):
                geocoded_count = output_df[output_df['latitude'].notna()].shape[0]
                logger.info(f"Found existing geocoded file with {geocoded_count}/{len(output_df)} geocoded entries")
                
                # If a reasonable amount is geocoded, consider it complete
                if geocoded_count > 0 and geocoded_count / len(output_df) > 0.7:
                    logger.info(f"Geocoded file for city {city_name} appears complete - skipping")
                    return
                else:
                    logger.warning(f"Geocoded file for city {city_name} exists but has low completion rate ({geocoded_count}/{len(output_df)}) - re-geocoding")
        except Exception as e:
            logger.error(f"Error checking existing geocoded file: {e}")
    
    # Prepare data for geocoding
    df = self.prepare_city_data(city_id, city_name)
    
    if df is None or len(df) == 0:
        logger.warning(f"No data to geocode for city {city_name} - skipping")
        return
    
    total_addresses = len(df)
    logger.info(f"Starting geocoding of {total_addresses} addresses for {city_name}")
    
    # Check for checkpoint to resume progress
    processed_indexes = set()
    geocoded_rows = []
    
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                processed_indexes = set(checkpoint.get('processed_indexes', []))
                geocoded_rows = checkpoint.get('geocoded_rows', [])
                logger.info(f"Resuming from checkpoint with {len(processed_indexes)} processed addresses")
        except Exception as e:
            logger.error(f"Error loading checkpoint: {e}")
            processed_indexes = set()
            geocoded_rows = []
    
    # Convert any previously geocoded rows to a DataFrame and save as baseline
    if geocoded_rows:
        prev_geocoded_df = pd.DataFrame(geocoded_rows)
        prev_geocoded_df.to_csv(output_file, index=False)
        logger.info(f"Restored {len(geocoded_rows)} previously geocoded entries from checkpoint")
    
    # Filter out already processed indexes
    remaining_df = df.loc[~df.index.isin(processed_indexes)].copy()
    logger.info(f"Remaining addresses to geocode: {len(remaining_df)}/{total_addresses}")
    
    # Time tracking for rate limiting
    last_request_time = time.time()
    total_geocoded = len(geocoded_rows)
    new_geocoded_rows = []
    newly_processed_indexes = set()
    
    try:
        # Process each address with progress bar
        with tqdm(total=len(remaining_df), desc=f"Geocoding addresses in {city_name}") as pbar:
            for index, row in remaining_df.iterrows():
                # Format address
                address_variations = self.create_address_variations(
                    row['street_name'], 
                    row['house'], 
                    row['sub_house'] if 'sub_house' in row else "", 
                    city_name
                )
                
                # Rate limiting
                current_time = time.time()
                elapsed = current_time - last_request_time
                sleep_time = max(0, self.current_delay - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
                # Geocode the address
                last_request_time = time.time()
                geocode_response, used_address = self.geocode_address(address_variations)
                
                # Process the result
                geocode_data = self.extract_geocode_data(geocode_response, used_address)
                
                # Create result row
                result_row = {
                    'street_id': row['street_id'],
                    'city_id': row['city_id'],
                    'street_name': row['street_name'],
                    'house': row['house'],
                    'sub_house': row['sub_house'] if 'sub_house' in row else "",
                    'is_available': row['is_available'],
                    'full_address': address_variations[0] if address_variations else "",
                    'latitude': None,
                    'longitude': None,
                    'gis_full_name': None,
                    'geocoded_address': None,
                    'geocode_confidence': 0.0,
                    'provider': 'beeline'
                }
                
                # Add geocoding data if available
                if geocode_data:
                    result_row.update(geocode_data)
                    total_geocoded += 1
                
                # Add to results
                new_geocoded_rows.append(result_row)
                newly_processed_indexes.add(index)
                
                # Update progress bar
                pbar.update(1)
                
                # Update and save checkpoint periodically
                if len(new_geocoded_rows) % self.batch_size == 0:
                    self.save_geocoded_batch(new_geocoded_rows, output_file, 
                                          len(geocoded_rows) == 0 and len(newly_processed_indexes) == self.batch_size)
                    
                    # Update checkpoint
                    all_processed = processed_indexes.union(newly_processed_indexes)
                    all_geocoded = geocoded_rows + new_geocoded_rows
                    self.save_checkpoint(checkpoint_file, {
                        'processed_indexes': list(all_processed),
                        'geocoded_rows': all_geocoded  # Save all rows for recovery
                    })
                    
                    logger.debug(f"Updated checkpoint: {len(all_processed)}/{total_addresses} addresses processed")
                    
                    # Reset batch tracking
                    geocoded_rows = all_geocoded
                    processed_indexes = all_processed
                    new_geocoded_rows = []
                    newly_processed_indexes = set()
        
        # Save final batch if any left
        if new_geocoded_rows:
            self.save_geocoded_batch(new_geocoded_rows, output_file, 
                                  len(geocoded_rows) == 0 and len(newly_processed_indexes) == len(new_geocoded_rows))
            
            # Update final checkpoint
            all_processed = processed_indexes.union(newly_processed_indexes)
            all_geocoded = geocoded_rows + new_geocoded_rows
            self.save_checkpoint(checkpoint_file, {
                'processed_indexes': list(all_processed),
                'geocoded_rows': all_geocoded
            })
        
        # Log summary
        geocoded_rate = (total_geocoded / total_addresses) * 100 if total_addresses > 0 else 0
        logger.info(f"Geocoding complete for city {city_name}: {total_geocoded}/{total_addresses} geocoded ({geocoded_rate:.1f}%)")
        
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        # Save progress on interrupt
        if new_geocoded_rows:
            self.save_geocoded_batch(new_geocoded_rows, output_file, 
                                  len(geocoded_rows) == 0 and len(newly_processed_indexes) == len(new_geocoded_rows))
            
            # Update checkpoint with current progress
            all_processed = processed_indexes.union(newly_processed_indexes)
            all_geocoded = geocoded_rows + new_geocoded_rows
            self.save_checkpoint(checkpoint_file, {
                'processed_indexes': list(all_processed),
                'geocoded_rows': all_geocoded
            })
            
        logger.info(f"Saved progress: {len(processed_indexes.union(newly_processed_indexes))}/{total_addresses} addresses processed")
        
    except Exception as e:
        logger.error(f"Error during geocoding: {e}")
        # Save progress on error
        if new_geocoded_rows:
            self.save_geocoded_batch(new_geocoded_rows, output_file, 
                                  len(geocoded_rows) == 0 and len(newly_processed_indexes) == len(new_geocoded_rows))
            
            # Update checkpoint with current progress
            all_processed = processed_indexes.union(newly_processed_indexes)
            all_geocoded = geocoded_rows + new_geocoded_rows
            self.save_checkpoint(checkpoint_file, {
                'processed_indexes': list(all_processed),
                'geocoded_rows': all_geocoded
            })
            
        logger.info(f"Saved progress after error: {len(processed_indexes.union(newly_processed_indexes))}/{total_addresses} addresses processed")

def save_geocoded_batch(self, rows, file_path, write_header=False):
    """Save a batch of geocoded results to CSV file"""
    if not rows:
        return
    
    mode = 'w' if write_header else 'a'
    
    try:
        with open(file_path, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            if write_header:
                writer.writeheader()
            writer.writerows(rows)
        
        logger.debug(f"{len(rows)} geocoded entries {'saved to' if write_header else 'appended to'} {file_path}")
    except Exception as e:
        logger.error(f"Error saving geocoded batch: {e}")

def merge_city_results(self):
    """Merge geocoded results from all cities into a single file"""
    logger.info("Merging geocoded results from all cities")
    
    # Final output file
    output_file = os.path.join(self.output_dir, "all_geocoded_results.csv")
    
    # Find all geocoded city files
    geocoded_files = [f for f in os.listdir(self.output_dir) if f.startswith("geocoded_city_") and f.endswith(".csv")]
    
    if not geocoded_files:
        logger.warning("No geocoded city files found to merge")
        return
    
    logger.info(f"Found {len(geocoded_files)} geocoded city files to merge")
    
    # Read and combine all files
    all_data = []
    total_records = 0
    geocoded_records = 0
    
    for file in geocoded_files:
        file_path = os.path.join(self.output_dir, file)
        try:
            df = pd.read_csv(file_path)
            records = len(df)
            geocoded = df[df['latitude'].notna()].shape[0]
            
            logger.info(f"File {file}: {geocoded}/{records} geocoded entries")
            
            # Add city name to each record
            city_id = int(file.replace("geocoded_city_", "").replace(".csv", ""))
            city_name = self.city_name_cache.get(city_id, f"City {city_id}")
            df['city_name'] = city_name
            
            all_data.append(df)
            total_records += records
            geocoded_records += geocoded
            
        except Exception as e:
            logger.error(f"Error processing file {file}: {e}")
    
    if not all_data:
        logger.warning("No valid data found for merging")
        return
    
    # Combine all dataframes
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Save combined results
    combined_df.to_csv(output_file, index=False)
    
    # Log summary
    geocoded_rate = (geocoded_records / total_records) * 100 if total_records > 0 else 0
    logger.info(f"Merged {len(geocoded_files)} files into {output_file}")
    logger.info(f"Total records: {total_records}, Geocoded: {geocoded_records} ({geocoded_rate:.1f}%)")
    
    # Also convert to JSON format for web applications
    self.convert_to_json(combined_df, os.path.join(self.output_dir, "all_geocoded_results.json"))
    
def convert_to_json(self, dataframe, json_file):
    """Convert DataFrame to JSON format for web applications"""
    try:
        # Process data for JSON format
        json_data = []
        
        for _, row in dataframe.iterrows():
            # Skip entries without coordinates
            if pd.isna(row['latitude']) or pd.isna(row['longitude']):
                continue
                
            # Create JSON entry
            entry = {
                'streetId': int(row['street_id']) if not pd.isna(row['street_id']) else None,
                'streetName': row['street_name'] if not pd.isna(row['street_name']) else "",
                'house': row['house'] if not pd.isna(row['house']) else "",
                'subHouse': row['sub_house'] if 'sub_house' in row and not pd.isna(row['sub_house']) else "",
                'isAvailable': int(row['is_available']) if not pd.isna(row['is_available']) else 0,
                'fullAddress': row['full_address'] if 'full_address' in row and not pd.isna(row['full_address']) else "",
                'gisFullName': row['gis_full_name'] if 'gis_full_name' in row and not pd.isna(row['gis_full_name']) else "",
                'provider': row['provider'] if 'provider' in row else "beeline",
                'latitude': float(row['latitude']),
                'longitude': float(row['longitude']),
                'city': row['city_name'] if 'city_name' in row else "Unknown"
            }
            
            json_data.append(entry)
        
        # Write to JSON file
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Converted {len(json_data)} geocoded entries to JSON: {json_file}")
        
    except Exception as e:
        logger.error(f"Error converting to JSON: {e}")
                             