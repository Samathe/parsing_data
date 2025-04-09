import pandas as pd
import json
import csv

# Configuration
TELECOM_CSV = "ftth_results_with_coordinates.csv"
BEELINE_CSV = "beeline_ftth_with_coordinates.csv"
COMBINED_CSV = "combined_ftth_results.csv"
COMBINED_JSON = "combined_addresses.json"

def combine_data():
    """
    Combine data from Telecom and Beeline into a single CSV and JSON file
    """
    # Load Telecom data
    try:
        telecom_df = pd.read_csv(TELECOM_CSV)
        print(f"Loaded {len(telecom_df)} records from Telecom")
        
        # Add provider column if not exists
        if 'provider' not in telecom_df.columns:
            telecom_df['provider'] = 'telecom'
    except Exception as e:
        print(f"Error loading Telecom data: {e}")
        telecom_df = pd.DataFrame()
    
    # Load Beeline data
    try:
        beeline_df = pd.read_csv(BEELINE_CSV)
        print(f"Loaded {len(beeline_df)} records from Beeline")
        
        # Ensure provider column exists
        if 'provider' not in beeline_df.columns:
            beeline_df['provider'] = 'beeline'
    except Exception as e:
        print(f"Error loading Beeline data: {e}")
        beeline_df = pd.DataFrame()
    
    # Combine datasets
    if not telecom_df.empty and not beeline_df.empty:
        # Ensure columns match
        telecom_cols = set(telecom_df.columns)
        beeline_cols = set(beeline_df.columns)
        
        # Find missing columns in each dataset
        missing_in_telecom = beeline_cols - telecom_cols
        missing_in_beeline = telecom_cols - beeline_cols
        
        # Add missing columns to each dataframe
        for col in missing_in_telecom:
            telecom_df[col] = None
        
        for col in missing_in_beeline:
            beeline_df[col] = None
        
        # Combine the dataframes
        combined_df = pd.concat([telecom_df, beeline_df], ignore_index=True)
        
        # Remove duplicates based on coordinates
        # Two points are considered duplicates if they are within a small distance
        combined_df = combined_df.dropna(subset=['latitude', 'longitude'])
        
        # Round coordinates to 5 decimal places (approx. 1-meter precision)
        # to help identify nearby duplicates
        combined_df['lat_rounded'] = combined_df['latitude'].round(5)
        combined_df['lon_rounded'] = combined_df['longitude'].round(5)
        
        # Group by rounded coordinates and keep the first one in each group
        # (prioritizing telecom data if there's an overlap)
        combined_df = combined_df.sort_values('provider', ascending=True).drop_duplicates(
            subset=['lat_rounded', 'lon_rounded'], keep='first'
        )
        
        # Drop the temporary columns
        combined_df = combined_df.drop(['lat_rounded', 'lon_rounded'], axis=1)
        
    elif not telecom_df.empty:
        print("Only Telecom data available")
        combined_df = telecom_df
        if 'provider' not in combined_df.columns:
            combined_df['provider'] = 'telecom'
    elif not beeline_df.empty:
        print("Only Beeline data available")
        combined_df = beeline_df
        if 'provider' not in combined_df.columns:
            combined_df['provider'] = 'beeline'
    else:
        print("No data available to combine")
        return
    
    # Save combined data to CSV
    combined_df.to_csv(COMBINED_CSV, index=False)
    print(f"Saved {len(combined_df)} records to {COMBINED_CSV}")
    
    # Convert to JSON for the map
    convert_to_json(COMBINED_CSV, COMBINED_JSON)

def convert_to_json(csv_file, json_file):
    """
    Convert CSV file to JSON format for the FTTH map application
    """
    data = []
    
    with open(csv_file, 'r', encoding='utf-8') as csvfile:
        # Read CSV data
        reader = csv.DictReader(csvfile)
        
        # Process each row
        for row in reader:
            try:
                # Extract the necessary fields
                processed_row = {
                    'streetId': int(float(row['street_id'])) if row['street_id'] and row['street_id'] != 'None' else None,
                    'streetName': row['street_name'],
                    'subHouse': row['sub_house'] if 'sub_house' in row and row['sub_house'] else '',
                    'isAvailable': int(float(row['is_available'])) if row['is_available'] and row['is_available'] != 'None' else 0,
                    'fullAddress': row['full_address'] if 'full_address' in row else '',
                    'gisFullName': row['gis_full_name'] if 'gis_full_name' in row and row['gis_full_name'] != 'None' else '',
                    'provider': row['provider'] if 'provider' in row else 'telecom'
                }
                
                # Handle house number - convert to int when possible
                try:
                    processed_row['house'] = int(float(row['house']))
                except (ValueError, TypeError):
                    processed_row['house'] = row['house'] if row['house'] else ''
                
                # Only add points with valid coordinates
                if (row['latitude'] and row['latitude'] != 'None' and 
                    row['longitude'] and row['longitude'] != 'None'):
                    processed_row['latitude'] = float(row['latitude'])
                    processed_row['longitude'] = float(row['longitude'])
                    data.append(processed_row)
            except (ValueError, KeyError) as e:
                print(f"Error processing row: {row}")
                print(f"Error message: {e}")
                continue
    
    # Write JSON file
    with open(json_file, 'w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, ensure_ascii=False, indent=2)
    
    print(f"Conversion complete! Processed {len(data)} valid data points.")
    print(f"JSON data saved to {json_file}")

if __name__ == "__main__":
    combine_data()