import requests
import json
import os
import time
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variables
API_KEY = os.getenv("API_KEY")
GEOCODE_API_URL = os.getenv("GEOCODE_API_URL", "https://geocode-api.example.com")

# Telecom.kz API endpoints
TELECOM_BASE_URL = "https://telecom.kz/ru/api/v1.0"
REGIONS_URL = f"{TELECOM_BASE_URL}/locations/geo-states"
# Other URLs will be constructed dynamically based on IDs

def fetch_json(url, params=None):
    """Fetch JSON data from URL with optional parameters"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://telecom.kz/ru/technical-check",
            "Origin": "https://telecom.kz"
        }
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        if response.content:
            return response.json()
        else:
            print(f"Empty response from {url}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON decode error from {url}: {e}")
        print(f"Response content: {response.content[:100]}")  # Print first 100 chars of response
        return None

def get_coordinates(address):
    """Get coordinates for an address using geocoding API"""
    try:
        url = f"{GEOCODE_API_URL}/geocode"
        params = {
            "q": address,
            "fields": "items.point",
            "key": API_KEY
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error getting coordinates for {address}: {e}")
        return None

def main():
    # Create a list to store all location data
    all_locations = []
    
    # Track IDs for hierarchical structure
    location_id = 1
    
    # Step 1: Fetch all regions
    print("Fetching regions...")
    regions = fetch_json(REGIONS_URL)
    if not regions:
        print("Failed to fetch regions")
        return
    
    print(f"Found {len(regions)} regions")
    
    # Process each region
    for region in regions:
        region_id = region["id"]
        region_name = region["name"]
        print(f"Processing region: {region_name} (ID: {region_id})")
        
        # Create region entry
        region_entry = {
            "id": location_id,
            "parent_id": None,
            "type": "region",
            "name": region_name,
            "original_id": region_id,
            "full_address": region_name
        }
        all_locations.append(region_entry)
        region_location_id = location_id
        location_id += 1
        
        # Step 2: Get districts for this region
        districts_url = f"{TELECOM_BASE_URL}/locations/geo-state/{region_id}/geo-state-district"
        print(f"  Fetching districts from: {districts_url}")
        districts = fetch_json(districts_url)
        
        if not districts or len(districts) == 0:
            print(f"  No districts found for region {region_name}")
            continue
        
        print(f"  Found {len(districts)} districts")
        
        # Process each district
        for district in districts:
            district_id = district["id"]
            district_name = district["name"]
            print(f"  Processing district: {district_name} (ID: {district_id})")
            
            # Create district entry
            district_entry = {
                "id": location_id,
                "parent_id": region_location_id,
                "type": "district", 
                "name": district_name,
                "original_id": district_id,
                "full_address": f"{region_name}, {district_name}"
            }
            all_locations.append(district_entry)
            district_location_id = location_id
            location_id += 1
            
            # Step 3: Get towns for this district
            towns_url = f"{TELECOM_BASE_URL}/locations/town-states"
            towns_params = {"geoStateDistrictId": district_id}
            print(f"    Fetching towns with params: {towns_params}")
            towns = fetch_json(towns_url, towns_params)
            
            if not towns or len(towns) == 0:
                print(f"    No towns found for district {district_name}")
                continue
            
            print(f"    Found {len(towns)} towns")
            
            # Process each town
            for town in towns:
                town_id = town["id"]
                town_name = town["name"]
                print(f"    Processing town: {town_name} (ID: {town_id})")
                
                # Create town entry
                town_entry = {
                    "id": location_id,
                    "parent_id": district_location_id,
                    "type": "town",
                    "name": town_name,
                    "original_id": town_id,
                    "full_address": f"{region_name}, {district_name}, {town_name}"
                }
                all_locations.append(town_entry)
                town_location_id = location_id
                location_id += 1
                
                # Step 4: Get streets for this town
                streets_url = f"{TELECOM_BASE_URL}/locations/town-states/{town_id}/streets"
                print(f"      Fetching streets from: {streets_url}")
                streets = fetch_json(streets_url)
                
                if not streets or len(streets) == 0:
                    print(f"      No streets found for town {town_name}")
                    continue
                
                print(f"      Found {len(streets)} streets")
                
                # Process each street
                for street in streets:
                    street_id = street.get("id")
                    street_name = street.get("name", "")
                    if street_name:
                        # Create street entry
                        street_entry = {
                            "id": location_id,
                            "parent_id": town_location_id,
                            "type": "street",
                            "name": street_name,
                            "original_id": street_id,
                            "full_address": f"{region_name}, {district_name}, {town_name}, {street_name}"
                        }
                        all_locations.append(street_entry)
                        location_id += 1
                
                # Add a small delay to avoid overwhelming the server
                time.sleep(0.1)
            
            # Add a small delay between district requests
            time.sleep(0.2)
        
        # Add a small delay between region requests
        time.sleep(0.5)
    
    print(f"Collected {len(all_locations)} locations.")
    
    # Optional: Get coordinates for locations
    if API_KEY and GEOCODE_API_URL != "https://geocode-api.example.com":
        print("Getting coordinates...")
        for i, location in enumerate(all_locations):
            if i % 10 == 0:
                print(f"Processing coordinates for location {i+1}/{len(all_locations)}")
                
            coords = get_coordinates(location["full_address"])
            if coords and "items" in coords and len(coords["items"]) > 0:
                point = coords["items"][0].get("point", {})
                location["coordX"] = point.get("lon")
                location["coordY"] = point.get("lat")
            else:
                location["coordX"] = None
                location["coordY"] = None
            
            # Add a small delay between geocoding requests
            time.sleep(0.3)
    
    # Save results to JSON and CSV files
    print("Saving data to files...")
    
    # Save as JSON
    with open("telecom_locations.json", "w", encoding="utf-8") as f:
        json.dump(all_locations, f, ensure_ascii=False, indent=2)
    
    # Convert to DataFrame and save as CSV
    df = pd.DataFrame(all_locations)
    df.to_csv("telecom_locations.csv", index=False, encoding="utf-8")
    
    # Create a hierarchical representation
    # Prepare data in a format that shows the hierarchy clearly
    hierarchy_data = []
    
    # First, organize by parent-child relationships
    locations_by_id = {loc["id"]: loc for loc in all_locations}
    children_by_parent = {}
    
    for loc in all_locations:
        parent_id = loc["parent_id"]
        if parent_id not in children_by_parent:
            children_by_parent[parent_id] = []
        children_by_parent[parent_id].append(loc)
    
    # Create a hierarchical CSV with path information
    hierarchy_rows = []
    
    # Start with root items (regions)
    root_items = children_by_parent.get(None, [])
    
    for region in root_items:
        region_row = {
            "id": region["id"],
            "original_id": region["original_id"],
            "name": region["name"],
            "path": region["name"],
            "type": region["type"],
            "parent_id": region["parent_id"]
        }
        hierarchy_rows.append(region_row)
        
        # Add districts
        districts = children_by_parent.get(region["id"], [])
        for district in districts:
            district_row = {
                "id": district["id"],
                "original_id": district["original_id"],
                "name": district["name"],
                "path": f"{region['name']} > {district['name']}",
                "type": district["type"],
                "parent_id": district["parent_id"]
            }
            hierarchy_rows.append(district_row)
            
            # Add towns
            towns = children_by_parent.get(district["id"], [])
            for town in towns:
                town_row = {
                    "id": town["id"],
                    "original_id": town["original_id"],
                    "name": town["name"],
                    "path": f"{region['name']} > {district['name']} > {town['name']}",
                    "type": town["type"],
                    "parent_id": town["parent_id"]
                }
                hierarchy_rows.append(town_row)
                
                # Add streets
                streets = children_by_parent.get(town["id"], [])
                for street in streets:
                    street_row = {
                        "id": street["id"],
                        "original_id": street["original_id"],
                        "name": street["name"],
                        "path": f"{region['name']} > {district['name']} > {town['name']} > {street['name']}",
                        "type": street["type"],
                        "parent_id": street["parent_id"]
                    }
                    hierarchy_rows.append(street_row)
    
    # Save hierarchical data
    hierarchy_df = pd.DataFrame(hierarchy_rows)
    hierarchy_df.to_csv("telecom_locations_hierarchical.csv", index=False, encoding="utf-8")
    
    print(f"Saved {len(all_locations)} locations to:")
    print("- telecom_locations.json")
    print("- telecom_locations.csv")
    print("- telecom_locations_hierarchical.csv")

if __name__ == "__main__":
    main()