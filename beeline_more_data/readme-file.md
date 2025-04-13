# Kazakhstan Telecom Data Collection and Geocoding

This project collects and geocodes telecom data from Beeline Kazakhstan, allowing for comprehensive mapping of FTTH (Fiber To The Home) coverage across the country.

## Overview

The system is designed to:

1. Collect street and address data from the Beeline Kazakhstan API
2. Geocode addresses using the 2GIS API
3. Merge and process the data for visualization and analysis
4. Handle large datasets with robust error recovery and checkpointing

## Prerequisites

- Python 3.6 or higher
- Required packages: `requests`, `pandas`, `tqdm`

To install required packages:
```bash
pip install requests pandas tqdm
```

## Project Structure

```
- main.py                      # Main script for running the application
- enhanced_geocoder.py         # Core geocoding engine
- logs/                        # Log files directory
- beeline_data/                # Raw data collection directory
  - beeline_streets_city_*.csv # Street data for each city
  - beeline_houses_city_*.csv  # House data for each city
- geocoded_data/               # Geocoded results directory
  - geocoded_city_*.csv        # Geocoded results for each city
  - checkpoints/               # Progress checkpoints
  - all_geocoded_results.csv   # Combined results file
  - all_geocoded_results.json  # JSON format for web applications
```

## Usage

### Basic Usage

Process all cities with default settings:
```bash
python main.py --mode all
```

Show statistics about current progress:
```bash
python main.py --stats
```

### Data Collection Only

Collect data for specific cities:
```bash
python main.py --mode collect --cities 1,2,3
```

Collect data for a range of cities:
```bash
python main.py --mode collect --cities 1-10
```

### Geocoding Only

Geocode previously collected data:
```bash
python main.py --mode geocode --cities 1-10
```

### Merge Results

Combine all geocoded cities into a single dataset:
```bash
python main.py --mode merge
```

### Advanced Options

```
--api-key KEY        Specify a custom 2GIS API key
--workers N          Number of parallel workers (default: 5)
--batch-size N       Size of processing batches (default: 100)
--retries N          Number of retry attempts (default: 3)
--delay N            Request delay in seconds (default: 1.5)
--input-dir DIR      Custom input directory
--output-dir DIR     Custom output directory
--force              Force reprocessing of already processed data
--verbose            Enable detailed logging
```

## Process Flow

1. **Collection Phase**
   - Fetch all cities from Beeline API
   - For each city, fetch all streets
   - For each street, fetch all houses
   - Save data to CSV files with proper organization

2. **Geocoding Phase**
   - For each city, read the collected house data
   - Merge with street data to form complete addresses
   - Geocode each address using 2GIS API
   - Save results with coordinates to CSV files
   - Create checkpoints for error recovery

3. **Merge Phase**
   - Combine all geocoded city files
   - Process and standardize the data
   - Create CSV and JSON outputs for analysis and visualization

## Performance Considerations

- The script uses multithreading to speed up data collection and geocoding
- Intelligent rate limiting prevents API throttling
- Checkpoint system allows for resuming interrupted operations
- Batch processing minimizes memory usage for large datasets

## Troubleshooting

- **API Rate Limiting**: If you encounter rate limiting issues, increase the `--delay` parameter
- **Missing Geocodes**: Try alternative address formats by modifying the `format_address` function in `enhanced_geocoder.py`
- **Memory Issues**: Reduce the `--batch-size` parameter for large datasets
- **Slow Processing**: Increase `--workers` parameter, but be careful of API rate limits

## Next Steps for Improvement

1. Add support for additional geocoding providers
2. Implement geospatial validation and cleaning
3. Create visualization tools for the collected data
4. Enhance address formatting for better geocoding results
5. Add support for incremental updates

## License

This project is licensed under the MIT License - see the LICENSE file for details.
