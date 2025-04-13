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
                    self