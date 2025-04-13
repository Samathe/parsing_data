import requests
import csv
import json
import time
import os

class KazakhstanCityScraper:
    BASE_URL = "https://beeline.kz/restservices/telco"
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        }
        self.cities_file = "beeline_cities.csv"
        
    def fetch_all_cities(self):
        """Fetch all cities available in the Beeline API"""
        url = f"{self.BASE_URL}/cities"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            cities = response.json()
            
            # Save cities to CSV
            with open(self.cities_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=cities[0].keys())
                writer.writeheader()
                writer.writerows(cities)
            
            print(f"Saved {len(cities)} cities to {self.cities_file}")
            return cities
        
        except Exception as e:
            print(f"Error fetching cities: {e}")
            return []
            
    def get_cities(self):
        """Get cities either from API or from cached file"""
        if os.path.exists(self.cities_file):
            try:
                with open(self.cities_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    cities = list(reader)
                print(f"Loaded {len(cities)} cities from {self.cities_file}")
                return cities
            except Exception as e:
                print(f"Error loading cities from file: {e}")
                
        # If file doesn't exist or there was an error, fetch from API
        return self.fetch_all_cities()

def main():
    scraper = KazakhstanCityScraper()
    cities = scraper.get_cities()
    
    if cities:
        print("\nAvailable cities in Kazakhstan:")
        for city in cities:
            print(f"ID: {city['city_id']}, Name: {city['name']}")

if __name__ == "__main__":
    main()
