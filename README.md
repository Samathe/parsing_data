# FTTH Availability Map

A modern, interactive web application for visualizing Fiber-to-the-Home (FTTH) availability across Almaty, Kazakhstan. This application provides an intuitive interface to explore internet service provider coverage, filter by availability status, and analyze connectivity data across different neighborhoods.

## Features

### 🗺️ Interactive Map
- **Leaflet-based mapping** with OpenStreetMap tiles
- **Marker clustering** for better performance with large datasets
- **Custom markers** with color-coded availability status
- **Responsive popups** with detailed address information
- **Auto-fit bounds** to show all data points optimally

### 🎛️ Advanced Filtering
- **Availability filters**: Show/hide available and unavailable locations
- **Provider count filters**: Filter by single provider vs. multiple providers
- **Street-based filtering**: Search and filter by specific street names
- **Provider-specific filtering**: Filter by individual service providers
- **Real-time updates**: All filters work in combination and update instantly

### 📊 Statistics Dashboard
- **Real-time counters** for total points, availability status
- **Provider coverage statistics** showing single vs. multiple provider locations
- **Visible points counter** that updates based on active filters
- **Clean, organized layout** with color-coded statistics

### 📱 Mobile-First Design
- **Responsive layout** that works on all screen sizes
- **Touch-friendly interface** optimized for mobile devices
- **Collapsible sidebar** on mobile with overlay functionality
- **Smooth animations** and transitions

## Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Mapping**: Leaflet.js with MarkerCluster plugin
- **Icons**: Font Awesome
- **Styling**: Modern CSS with CSS Grid and Flexbox
- **Data Format**: JSON
- **No dependencies**: Pure vanilla JavaScript, no build process required

## Installation & Setup

### Prerequisites
- A modern web browser (Chrome, Firefox, Safari, Edge)
- A local web server (recommended for development)

### Quick Start
1. **Clone or download** the project files
2. **Prepare your data** in the required JSON format (see Data Structure section)
3. **Place your JSON file** in the project root and name it `addresses.json`
4. **Serve the files** using a local web server:
   ```bash
   # Using Python 3
   python -m http.server 8080
   
   # Using Node.js http-server
   npx http-server -p 8080
   
   # Using PHP
   php -S localhost:8080
   ```
5. **Open your browser** and navigate to `http://localhost:8080`

### Development Setup
If you're using VS Code, the included `launch.json` configuration allows you to:
1. Start your local server on port 8080
2. Press F5 to launch Chrome and start debugging
3. Set breakpoints and inspect the application

## Data Structure

The application expects a JSON file named `addresses.json` in the project root. This file should contain an array of address objects with the following structure:

### Required JSON Format
```json
[
  {
    "latitude": 43.238949,
    "longitude": 76.889709,
    "streetName": "Abay Avenue",
    "house": "123",
    "subHouse": "A",
    "fullAddress": "Abay Avenue, 123A, Almaty",
    "isAvailable": 1,
    "provider": "KazTelecom",
    "gisFullName": "улица Абая, дом 123А"
  },
  {
    "latitude": 43.240123,
    "longitude": 76.891234,
    "streetName": "Satpaev Street",
    "house": "45",
    "subHouse": "",
    "fullAddress": "Satpaev Street, 45, Almaty",
    "isAvailable": 0,
    "provider": "Beeline",
    "gisFullName": "улица Сатпаева, дом 45"
  }
]
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `latitude` | number | ✅ | GPS latitude coordinate (decimal degrees) |
| `longitude` | number | ✅ | GPS longitude coordinate (decimal degrees) |
| `streetName` | string | ✅ | Name of the street |
| `house` | string | ✅ | Building/house number |
| `subHouse` | string | ❌ | Sub-building identifier (apartment, unit, etc.) |
| `fullAddress` | string | ❌ | Complete formatted address |
| `isAvailable` | number | ✅ | Availability status (1 = available, 0 = unavailable) |
| `provider` | string | ✅ | Internet service provider name |
| `gisFullName` | string | ❌ | GIS system full name (optional, for reference) |

### Data Processing Notes

- **Duplicate handling**: The application automatically processes multiple entries for the same coordinates and combines them into single locations with multiple providers
- **Provider aggregation**: Locations with multiple providers are identified and marked with special purple markers
- **Coordinate validation**: Invalid or missing coordinates are automatically filtered out
- **String handling**: Empty strings and whitespace are handled gracefully

### Sample Data Files

You can create test data using this format. For a large dataset, consider:
- **Performance**: The application handles thousands of points efficiently with clustering
- **Memory**: Large datasets are processed client-side, so consider file size
- **Updates**: Data can be updated by replacing the JSON file and refreshing the page

## File Structure

```
ftth-map/
├── index.html          # Main HTML file
├── map.js             # Core application JavaScript
├── styles.css         # CSS styling and responsive design
├── addresses.json     # Your FTTH data (create this file)
├── .vscode/
│   └── launch.json    # VS Code debugging configuration
└── README.md          # This file
```

## Configuration

### Map Settings
You can modify map settings in `map.js`:
```javascript
const mapConfig = {
    center: [43.238949, 76.889709], // Almaty coordinates
    zoom: 12,
    dataUrl: 'addresses.json' // Path to your JSON file
};
```

### Marker Clustering
Customize clustering behavior:
```javascript
markersLayer = L.markerClusterGroup({
    maxClusterRadius: 50,        // Cluster radius in pixels
    disableClusteringAtZoom: 16, // Zoom level to disable clustering
    spiderfyOnMaxZoom: false,    // Disable spiderfy on max zoom
    showCoverageOnHover: false,  // Hide coverage area on hover
    zoomToBoundsOnClick: true    // Zoom to cluster bounds on click
});
```

## Customization

### Color Scheme
The application uses CSS custom properties for easy theming:
```css
:root {
    --primary-color: #2196f3;     /* Blue */
    --secondary-color: #4caf50;   /* Green - Available */
    --danger-color: #f44336;      /* Red - Unavailable */
    --purple-color: #8e24aa;      /* Purple - Both Providers */
    --orange-color: #ff9800;      /* Orange - Single Provider */
}
```

### Marker Styles
Markers are styled based on availability and provider count:
- **Green**: Available with single provider
- **Red**: Unavailable with single provider
- **Purple**: Multiple providers (darker purple for unavailable)
- **Size**: Larger markers indicate multiple providers

### Adding New Filters
To add new filtering capabilities:
1. Add filter UI elements in `index.html`
2. Add filter state variables in `map.js`
3. Update the `updateMarkers()` function with new filter logic
4. Add event listeners in `setupEventListeners()`

## Browser Compatibility

- **Chrome/Chromium**: Full support
- **Firefox**: Full support
- **Safari**: Full support
- **Edge**: Full support
- **Mobile browsers**: Optimized for iOS Safari and Chrome Mobile

## Performance Considerations

- **Large datasets**: Marker clustering prevents performance issues with thousands of points
- **Memory usage**: Data is processed and stored in memory; very large datasets (>50k points) may require optimization
- **Mobile performance**: CSS animations and transitions are optimized for 60fps on mobile devices

## Troubleshooting

### Common Issues

**Map doesn't load**
- Check browser console for JavaScript errors
- Ensure you're serving files via HTTP(S), not opening directly in browser
- Verify `addresses.json` exists and is valid JSON

**No markers appear**
- Check console for data loading errors
- Verify JSON structure matches required format
- Ensure latitude/longitude values are valid numbers

**Markers in wrong location**
- Verify coordinate format (decimal degrees, not degrees/minutes/seconds)
- Check that latitude/longitude aren't swapped
- Ensure coordinates are for the correct geographic region

**Mobile layout issues**
- Clear browser cache
- Check viewport meta tag is present
- Verify CSS media queries are working

### Debug Mode
Open browser developer tools (F12) to see:
- Data loading progress
- Filter application logs
- Marker creation details
- Performance metrics

## Contributing

To contribute to this project:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly on different devices
5. Submit a pull request

## License

This project is open source. You may use, modify, and distribute it according to your needs.

## Support

For support or questions about implementation:
- Check browser console for error messages
- Verify data format matches specifications
- Test with a small sample dataset first
- Ensure all required fields are present in your data
