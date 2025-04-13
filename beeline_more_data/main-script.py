#!/usr/bin/env python3
"""
Enhanced Kazakhstan Telecom Data Collector and Geocoder - Main Script
- Coordinates the entire data collection and geocoding pipeline
- Manages city processing, error handling, and overall process flow
- Provides comprehensive command-line interface and monitoring

Usage:
    python main.py --cities [city_ids] --mode [collect|geocode|all|merge] [options]
    python main.py --mode all                          # Process all cities
    python main.py --cities 1,2,3 --mode collect       # Collect data for specific cities
    python main.py --cities 1-10 --mode geocode        # Geocode specific city range
    python main.py --mode merge                        # Merge all results
    python main.py --stats                             # Show statistics only
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from tqdm import tqdm

# Import the enhanced geocoder
from enhanced_geocoder import EnhancedKazakhstanGeocoderManager

# Configuration
DEFAULT_API_KEY = "2424cc2b-ef4d-4d88-9dbb-89143fb588c1"  # Default 2GIS API key
DEFAULT_MAX_WORKERS = 5
DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_RETRIES = 3
DEFAULT_REQUEST_DELAY = 1.5

def setup_logging():
    """Set up logging configuration"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"kaz_geocoder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def parse_city_ids(city_input):
    """Parse city IDs from command line input, supporting ranges and comma-separated values"""
    if not city_input:
        return None
        
    city_ids = set()
    
    for part in city_input.split(','):
        part = part.strip()
        
        # Handle ranges (e.g., "1-5")
        if '-' in part:
            start, end = part.split('-')
            try:
                start, end = int(start.strip()), int(end.strip())
                city_ids.update(range(start, end + 1))
            except ValueError:
                print(f"Warning: Invalid city range '{part}', skipping")
                
        # Handle individual values
        else:
            try:
                city_ids.add(int(part))
            except ValueError:
                print(f"Warning: Invalid city ID '{part}', skipping")
    
    return sorted(list(city_ids)) if city_ids else None

def parse_arguments():
    """Parse command-line arguments with enhanced options"""
    parser = argparse.ArgumentParser(description="Enhanced Kazakhstan Telecom Data Collector and Geocoder")
    
    # Main operation mode
    parser.add_argument("--mode", choices=["collect", "geocode", "all", "merge", "stats"], 
                        default="all", help="Operation mode (default: all)")
    
    # City selection
    parser.add_argument("--cities", type=str, help="City IDs to process (comma-separated or ranges, e.g., '1,2,3-5')")
    
    # API configuration
    parser.add_argument("--api-key", type=str, default=DEFAULT_API_KEY, 
                        help=f"2GIS API key (default: {DEFAULT_API_KEY})")
    
    # Performance tuning
    parser.add_argument("--workers", type=int, default=DEFAULT_MAX_WORKERS, 
                        help=f"Number of worker threads (default: {DEFAULT_MAX_WORKERS})")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, 
                        help=f"Batch size for processing and saving (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--retries", type=int, default=DEFAULT_MAX_RETRIES, 
                        help=f"Maximum retry attempts (default: {DEFAULT_MAX_RETRIES})")
    parser.add_argument("--delay", type=float, default=DEFAULT_REQUEST_DELAY, 
                        help=f"Initial request delay in seconds (default: {DEFAULT_REQUEST_DELAY})")
    
    # Directory configuration
    parser.add_argument("--input-dir", type=str, default="beeline_data", 
                        help="Input directory for collected data (default: beeline_data)")
    parser.add_argument("--output-dir", type=str, default="geocoded_data", 
                        help="Output directory for geocoded results (default: geocoded_data)")
    
    # Additional options
    parser.add_argument("--stats", action="store_true", help="Show statistics only, without processing")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of already processed data")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Process city IDs
    args.city_ids = parse_city_ids(args.cities)
    
    return args

def show_statistics(manager):
    """Display statistics about current data collection and geocoding progress"""
    logger = logging.getLogger(__name__)
    logger.info("Generating statistics...")
    
    # Check city data
    cities = manager.get_cities()
    logger.info(f"Found information for {len(cities)} cities")
    
    # Count available data files
    input_dir = manager.input_dir
    output_dir = manager.output_dir
    
    # Count collected data files
    streets_files = [f for f in os.listdir(input_dir) if f.startswith("beeline_streets_city_")]
    houses_files = [f for f in os.listdir(input_dir) if f.startswith("beeline_houses_city_")]
    
    logger.info(f"Data collection status:")
    logger.info(f"  - Streets data files: {len(streets_files)} cities")
    logger.info(f"  - Houses data files: {len(houses_files)} cities")
    
    # Count geocoded data files
    geocoded_files = [f for f in os.listdir(output_dir) if f.startswith("geocoded_city_")]
    
    # Calculate geocoding completion rate
    total_geocoded = 0
    total_houses = 0
    geocoded_with_coords = 0
    
    for geocoded_file in geocoded_files:
        try:
            file_path = os.path.join(output_dir, geocoded_file)
            df = pd.read_csv(file_path)
            file_total = len(df)
            file_geocoded = df['latitude'].notna().sum()
            
            total_geocoded += file_total
            geocoded_with_coords += file_geocoded
            
            city_id = geocoded_file.replace("geocoded_city_", "").replace(".csv", "")
            logger.info(f"  - City {city_id}: {file_geocoded}/{file_total} geocoded ({file_geocoded/max(1, file_total)*100:.1f}%)")
        except Exception as e:
            logger.warning(f"Error reading geocoded file {geocoded_file}: {e}")
    
    # Count total houses
    for houses_file in houses_files:
        try:
            file_path = os.path.join(input_dir, houses_file)
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                # Skip header
                next(reader, None)
                count = sum(1 for _ in reader)
                total_houses += count
        except Exception as e:
            logger.warning(f"Error counting houses in {houses_file}: {e}")
    
    logger.info(f"Geocoding status:")
    logger.info(f"  - Geocoded files: {len(geocoded_files)} cities")
    if total_geocoded > 0:
        logger.info(f"  - Total addresses geocoded with coordinates: {geocoded_with_coords}/{total_geocoded} ({geocoded_with_coords/total_geocoded*100:.1f}%)")
    
    logger.info(f"Overall progress:")
    logger.info(f"  - Total houses in database: {total_houses}")
    if total_houses > 0:
        logger.info(f"  - Overall geocoding completion: {geocoded_with_coords}/{total_houses} ({geocoded_with_coords/total_houses*100:.1f}%)")
    
    # Check if merged file exists
    merged_file = os.path.join(output_dir, "all_geocoded_results.csv")
    if os.path.exists(merged_file):
        try:
            df = pd.read_csv(merged_file)
            logger.info(f"  - Combined dataset: {len(df)} entries, {df['latitude'].notna().sum()} with coordinates")
        except Exception as e:
            logger.warning(f"Error reading merged file: {e}")

def combine_results(output_dir):
    """Combine all geocoded results into a single file for visualization and analysis"""
    logger = logging.getLogger(__name__)
    logger.info("Combining all geocoded results...")
    
    # Final output files
    combined_csv = os.path.join(output_dir, "all_geocoded_results.csv")
    combined_json = os.path.join(output_dir, "all_geocoded_results.json")
    
    # Find all geocoded city files
    geocoded_files = [f for f in os.listdir(output_dir) if f.startswith("geocoded_city_") and f.endswith(".csv")]
    
    if not geocoded_files:
        logger.warning("No geocoded city files found to combine")
        return
    
    logger.info(f"Found {len(geocoded_files)} geocoded city files to combine")
    
    # Import pandas for data manipulation
    try:
        import pandas as pd
    except ImportError:
        logger.error("Pandas is required for combining results. Please install it using 'pip install pandas'")
        return
    
    # Read and combine all files
    all_data = []
    total_records = 0
    geocoded_records = 0
    
    for file in geocoded_files:
        file_path = os.path.join(output_dir, file)
        try:
            df = pd.read_csv(file_path)
            records = len(df)
            geocoded = df[df['latitude'].notna()].shape[0]
            
            logger.info(f"File {file}: {geocoded}/{records} geocoded entries")
            
            # Add city ID to each record
            city_id = int(file.replace("geocoded_city_", "").replace(".csv", ""))
            df['city_id'] = city_id
            
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
    combined_df.to_csv(combined_csv, index=False)
    
    # Log summary
    geocoded_rate = (geocoded_records / total_records) * 100 if total_records > 0 else 0
    logger.info(f"Merged {len(geocoded_files)} files into {combined_csv}")
    logger.info(f"Total records: {total_records}, Geocoded: {geocoded_records} ({geocoded_rate:.1f}%)")
    
    # Convert to JSON format for web applications
    convert_to_json(combined_df, combined_json)
    logger.info(f"Created JSON file at {combined_json}")

def convert_to_json(dataframe, json_file):
    """Convert DataFrame to JSON format for web applications"""
    try:
        # Filter out entries without coordinates
        filtered_df = dataframe[dataframe['latitude'].notna() & dataframe['longitude'].notna()]
        
        # Process data for JSON format
        json_data = []
        
        for _, row in filtered_df.iterrows():
            # Create JSON entry
            entry = {
                'streetId': int(row['street_id']) if not pd.isna(row['street_id']) else None,
                'streetName': row['street_name'] if not pd.isna(row['street_name']) else "",
                'house': row['house'] if not pd.isna(row['house']) else "",
                'subHouse': row['sub_house'] if 'sub_house' in row.index and not pd.isna(row['sub_house']) else "",
                'isAvailable': int(row['is_available']) if not pd.isna(row['is_available']) else 0,
                'fullAddress': row['full_address'] if 'full_address' in row.index and not pd.isna(row['full_address']) else "",
                'gisFullName': row['gis_full_name'] if 'gis_full_name' in row.index and not pd.isna(row['gis_full_name']) else "",
                'provider': row['provider'] if 'provider' in row.index else "beeline",
                'latitude': float(row['latitude']),
                'longitude': float(row['longitude']),
                'city_id': int(row['city_id']) if 'city_id' in row.index and not pd.isna(row['city_id']) else None
            }
            
            json_data.append(entry)
        
        # Write to JSON file
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Converted {len(json_data)} geocoded entries to JSON")
        
    except Exception as e:
        logger.error(f"Error converting to JSON: {e}")

def main():
    """Main function to run the geocoder with command line options"""
    args = parse_arguments()
    logger = setup_logging()
    
    # Configure log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Create geocoder manager
    manager = EnhancedKazakhstanGeocoderManager(
        api_key=args.api_key,
        mode=args.mode,
        city_ids=args.city_ids,
        max_workers=args.workers,
        batch_size=args.batch_size,
        max_retries=args.retries,
        request_delay=args.delay,
        input_dir=args.input_dir,
        output_dir=args.output_dir
    )
    
    # Show statistics if requested
    if args.stats:
        show_statistics(manager)
        return
    
    # Run the geocoder in the requested mode
    if args.mode == "merge":
        combine_results(args.output_dir)
    else:
        logger.info(f"Starting geocoder in {args.mode} mode")
        manager.run()
        logger.info("Geocoder execution completed")
    
    # Show final statistics
    show_statistics(manager)

if __name__ == "__main__":
    main()