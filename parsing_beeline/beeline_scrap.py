import requests
import csv
import json
import time
import os
from urllib.parse import quote

class BeelineDataCollector:
    BASE_URL = "https://beeline.kz/restservices/telco"
    
    def __init__(self, city_id=1):
        self.city_id = city_id
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        }
    
    def fetch_streets(self):
        """Fetch all streets for the given city"""
        url = f"{self.BASE_URL}/streets?cityId={self.city_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            streets = response.json()
            
            # Save streets to CSV
            streets_file = f"beeline_streets_city_{self.city_id}.csv"
            with open(streets_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=streets[0].keys())
                writer.writeheader()
                writer.writerows(streets)
            
            print(f"Saved {len(streets)} streets to {streets_file}")
            return streets
        
        except Exception as e:
            print(f"Error fetching streets: {e}")
            return []
    
    def fetch_houses_for_street(self, street_id):
        """Fetch all houses for a specific street"""
        url = f"{self.BASE_URL}/houses?cityId={self.city_id}&streetId={street_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            houses = response.json()
            
            # Enhance houses with street information
            for house in houses:
                house['street_id'] = street_id
            
            return houses
        
        except Exception as e:
            print(f"Error fetching houses for street {street_id}: {e}")
            return []
    
    def collect_all_houses(self, streets=None):
        """Collect houses for all streets"""
        if not streets:
            streets = self.fetch_streets()
        
        all_houses = []
        total_streets = len(streets)
        
        for index, street in enumerate(streets, 1):
            street_id = street['street_id']
            street_name = street['name']
            
            print(f"Processing street {index}/{total_streets}: {street_name} (ID: {street_id})")
            
            houses = self.fetch_houses_for_street(street_id)
            all_houses.extend(houses)
            
            # Pause to avoid rate limiting
            time.sleep(0.5)
        
        # Save all houses to CSV
        houses_file = f"beeline_houses_city_{self.city_id}.csv"
        with open(houses_file, 'w', newline='', encoding='utf-8') as f:
            if houses:
                writer = csv.DictWriter(f, fieldnames=houses[0].keys())
                writer.writeheader()
                writer.writerows(all_houses)
        
        print(f"Saved {len(all_houses)} houses to {houses_file}")
        return all_houses

def main():
    collector = BeelineDataCollector()
    streets = collector.fetch_streets()
    collector.collect_all_houses(streets)

if __name__ == "__main__":
    main()