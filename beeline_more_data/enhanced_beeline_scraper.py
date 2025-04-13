import requests
import csv
import json
import time
import os
import argparse
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

class EnhancedBeelineDataCollector:
    BASE_URL = "https://beeline.kz/restservices/telco"
    
    def __init__(self, city_ids=None, max_workers=5, timeout=10, retry_attempts=3):
        """Initialize the data collector with improved parameters"""
        self.city_ids = city_ids if city_ids else []
        self.max_workers = max_workers
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        self.cities_file = "beeline_cities.csv"
        self.output_dir = "beeline_data"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def fetch_with_retry(self, url):
        """Make an HTTP request with retry logic"""
        for attempt in range(self.retry_attempts):
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < self.retry_attempts - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Request failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"Failed after {self.retry_attempts} attempts: {e}")
                    return None
    
    def fetch_all_cities(self):
        """Fetch all cities available in the Beeline API"""
        url = f"{self.BASE_URL}/cities"
        cities = self.fetch_with_retry(url)
        
        if cities:
            # Save cities to CSV
            with open(self.cities_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=cities[0].keys())
                writer.writeheader()
                writer.writerows(cities)
            
            print(f"Saved {len(cities)} cities to {self.cities_file}")
            return cities
        
        return []
            
    def get_cities(self):
        """Get cities either from API or from cached file"""
        if os.path.exists(self.cities_file):
            try:
                with open(self.cities_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    cities = list(reader)
                print(f"Loaded {len(cities)} cities from {self.cities_file}")
                if not self.city_ids:  # If no specific cities were requested
                    return cities
                # Filter cities based on provided city_ids
                filtered_cities = [city for city in cities if int(city['city_id']) in self.city_ids]
                print(f"Filtered to {len(filtered_cities)} cities")
                return filtered_cities
            except Exception as e:
                print(f"Error loading cities from file: {e}")
                
        # If file doesn't exist or there was an error, fetch from API
        cities = self.fetch_all_cities()
        if self.city_ids:
            return [city for city in cities if int(city['city_id']) in self.city_ids]
        return cities
    
    def fetch_streets(self, city_id):
        """Fetch all streets for the given city"""
        url = f"{self.BASE_URL}/streets?cityId={city_id}"
        streets = self.fetch_with_retry(url)
        
        if streets:
            streets_file = os.path.join(self.output_dir, f"beeline_streets_city_{city_id}.csv")
            with open(streets_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=streets[0].keys())
                writer.writeheader()
                writer.writerows(streets)
            
            print(f"Saved {len(streets)} streets to {streets_file}")
            return streets
        
        return []
    
    def fetch_houses_for_street(self, city_id, street_id):
        """Fetch all houses for a specific street"""
        url = f"{self.BASE_URL}/houses?cityId={city_id}&streetId={street_id}"
        houses = self.fetch_with_retry(url)
        
        if houses:
            # Enhance houses with street information
            for house in houses:
                house['street_id'] = street_id
                house['city_id'] = city_id
            
            return houses
        
        return []
    
    def process_street(self, city_id, street):
        """Process a single street and fetch its houses"""
        street_id = street['street_id']
        street_name = street['name']
        
        houses = self.fetch_houses_for_street(city_id, street_id)
        # Add a small delay to avoid rate limiting
        time.sleep(0.2)
        
        return houses
    
    def collect_houses_for_city(self, city_id, city_name):
        """Collect houses for a specific city using parallel processing"""
        print(f"\nProcessing city: {city_name} (ID: {city_id})")
        
        # Check if we already have partially collected data
        houses_file = os.path.join(self.output_dir, f"beeline_houses_city_{city_id}.csv")
        if os.path.exists(houses_file):
            print(f"Houses file already exists: {houses_file}")
            print("Skipping this city. Delete the file if you want to re-scrape.")
            return
        
        # Fetch streets for this city
        streets = self.fetch_streets(city_id)
        if not streets:
            print(f"No streets found for city {city_name}")
            return
        
        total_streets = len(streets)
        print(f"Found {total_streets} streets in {city_name}")
        
        all_houses = []
        batch_size = 500  # Save progress after this many houses
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_street = {
                executor.submit(self.process_street, city_id, street): street
                for street in streets
            }
            
            # Process completed tasks with progress bar
            with tqdm(total=total_streets, desc=f"Scraping {city_name}") as pbar:
                for future in future_to_street:
                    street = future_to_street[future]
                    try:
                        houses = future.result()
                        all_houses.extend(houses)
                        
                        # Save intermediate results
                        if len(all_houses) >= batch_size:
                            self.save_houses(all_houses, city_id, append=True)
                            all_houses = []
                            
                    except Exception as e:
                        print(f"Error processing street {street['name']}: {e}")
                    
                    pbar.update(1)
        
        # Save any remaining houses
        if all_houses:
            self.save_houses(all_houses, city_id, append=True)
    
    def save_houses(self, houses, city_id, append=False):
        """Save houses to CSV file"""
        if not houses:
            return
            
        houses_file = os.path.join(self.output_dir, f"beeline_houses_city_{city_id}.csv")
        mode = 'a' if append and os.path.exists(houses_file) else 'w'
        
        with open(houses_file, mode, newline='', encoding='utf-8') as f:
            # Write header only if it's a new file
            writer = csv.DictWriter(f, fieldnames=houses[0].keys())
            if mode == 'w':
                writer.writeheader()
            writer.writerows(houses)
            
        if mode == 'w':
            print(f"Saved {len(houses)} houses to {houses_file}")
        else:
            print(f"Appended {len(houses)} houses to {houses_file}")
    
    def collect_all_data(self):
        """Collect data for all specified cities"""
        cities = self.get_cities()
        
        if not cities:
            print("No cities found. Exiting.")
            return
            
        for city in cities:
            city_id = int(city['city_id'])
            city_name = city['name']
            self.collect_houses_for_city(city_id, city_name)

def main():
    parser = argparse.ArgumentParser(description="Scrape Beeline Kazakhstan FTTH data")
    parser.add_argument("--cities", type=int, nargs="+", help="City IDs to scrape (default: all cities)")
    parser.add_argument("--workers", type=int, default=5, help="Number of worker threads (default: 5)")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds (default: 10)")
    parser.add_argument("--retries", type=int, default=3, help="Number of retry attempts (default: 3)")
    
    args = parser.parse_args()
    
    collector = EnhancedBeelineDataCollector(
        city_ids=args.cities,
        max_workers=args.workers,
        timeout=args.timeout,
        retry_attempts=args.retries
    )
    
    collector.collect_all_data()

if __name__ == "__main__":
    main()
