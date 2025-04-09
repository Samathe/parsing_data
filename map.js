// FTTH Availability Map JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Map configuration
    const mapConfig = {
        center: [43.238949, 76.889709], // Almaty coordinates
        zoom: 12,
        dataUrl: 'addresses.json' // Path to JSON data file
    };
    
    // Global variables
    let map;
    let markersLayer;
    let allData = [];
    let showAvailable = true;
    let showUnavailable = true;
    let selectedStreet = null;
    
    // Initialize the application
    initializeMap();
    loadMapData();
    setupEventListeners();
    
    /**
     * Initialize the map with base layers
     */
    function initializeMap() {
        // Create the map centered on Almaty
        map = L.map('map').setView(mapConfig.center, mapConfig.zoom);
        
        // Add OpenStreetMap tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);
        
        // Create marker group with optional clustering
        markersLayer = L.markerClusterGroup({
            maxClusterRadius: 50,
            disableClusteringAtZoom: 16,
            spiderfyOnMaxZoom: false,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true
        });
        map.addLayer(markersLayer);
        
        // Add legend to map
        const legend = L.control({position: 'bottomright'});
        legend.onAdd = function(map) {
            const div = L.DomUtil.create('div', 'legend');
            div.innerHTML = `
                <h4>FTTH Availability</h4>
                <div><i class="available"></i> Available</div>
                <div><i class="unavailable"></i> Unavailable</div>
            `;
            return div;
        };
        legend.addTo(map);
    }
    
    /**
     * Load and process map data from JSON file
     */
    function loadMapData() {
        fetch(mapConfig.dataUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data && data.length > 0) {
                    processData(data);
                } else {
                    console.error('No data found in the JSON file');
                }
            })
            .catch(error => {
                console.error('Error loading data:', error);
            });
    }
    
    /**
     * Process the JSON data and initialize the map display
     */
    function processData(data) {
        // Store the data
        allData = data;
        
        // Update markers
        updateMarkers();
        
        // Update street list
        updateStreetList();
        
        // Update statistics
        updateStats();
        
        // Fit map to markers
        const group = L.featureGroup(markersLayer.getLayers());
        if (group.getBounds().isValid()) {
            map.fitBounds(group.getBounds(), {
                padding: [50, 50]  // Add some padding around the bounds
            });
        }
    }
    
    /**
     * Update markers based on current filters
     */
    function updateMarkers() {
        // Clear existing markers
        markersLayer.clearLayers();
        
        let visibleCount = 0;
        
        // Add filtered markers
        allData.forEach(point => {
            // Check if the point should be visible based on filters
            const isAvailable = point.isAvailable === 1;
            
            const visibleByAvailability = (isAvailable && showAvailable) || 
                                        (!isAvailable && showUnavailable);
            
            const visibleByStreet = !selectedStreet || 
                                    point.streetName === selectedStreet;
            
            if (visibleByAvailability && visibleByStreet) {
                // Create marker only if coordinates are valid
                const lat = parseFloat(point.latitude);
                const lng = parseFloat(point.longitude);
                
                if (!isNaN(lat) && !isNaN(lng)) {
                    const markerColor = isAvailable ? '#43a047' : '#e53935';
                    
                    // Create a circle marker
                    const circleMarker = L.circleMarker([lat, lng], {
                        radius: 8,
                        fillColor: markerColor,
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.8
                    });
                    
                    // Prepare popup content
                    let subHouseText = point.subHouse && point.subHouse.trim() !== '' 
                        ? point.subHouse 
                        : '';
                    
                    const popupContent = `
                        <div class="popup-content">
                            <h3>${point.streetName}, ${point.house}${subHouseText ? ` ${subHouseText}` : ''}</h3>
                            <p class="availability ${isAvailable ? 'available' : 'unavailable'}">
                                <strong>Availability:</strong> ${isAvailable ? 'Available' : 'Unavailable'}
                            </p>
                            <p><strong>Full Address:</strong> ${point.fullAddress || ''}</p>
                            <p><strong>Coordinates:</strong> ${lat.toFixed(6)}, ${lng.toFixed(6)}</p>
                            ${point.gisFullName ? `<p><strong>GIS Full Name:</strong> ${point.gisFullName}</p>` : ''}
                        </div>
                    `;
                    
                    // Bind popup to marker
                    circleMarker.bindPopup(popupContent);
                    
                    // Add to markers layer
                    markersLayer.addLayer(circleMarker);
                    visibleCount++;
                }
            }
        });
        
        // Update visible count
        document.getElementById('visible-points').textContent = visibleCount;
    }
    
    /**
     * Update the list of streets for filtering
     */
    function updateStreetList() {
        const streetList = document.getElementById('street-list');
        streetList.innerHTML = '';
        
        // Get unique streets
        const streets = [...new Set(allData.map(point => point.streetName))].sort();
        
        streets.forEach(street => {
            const streetItem = document.createElement('div');
            streetItem.className = 'street-item';
            streetItem.textContent = street;
            streetItem.addEventListener('click', () => {
                selectedStreet = street;
                
                // Update selected class
                document.querySelectorAll('.street-item').forEach(item => {
                    item.classList.remove('selected');
                });
                streetItem.classList.add('selected');
                
                updateMarkers();
            });
            
            streetList.appendChild(streetItem);
        });
    }
    
    /**
     * Filter the street list based on search input
     */
    function filterStreetList() {
        const filterText = document.getElementById('street-filter').value.toLowerCase();
        const streetItems = document.querySelectorAll('.street-item');
        
        streetItems.forEach(item => {
            const streetName = item.textContent.toLowerCase();
            if (streetName.includes(filterText)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }
    
    /**
     * Clear street filter
     */
    function clearStreetFilter() {
        selectedStreet = null;
        document.getElementById('street-filter').value = '';
        
        // Remove selected class
        document.querySelectorAll('.street-item').forEach(item => {
            item.classList.remove('selected');
            item.style.display = 'block';
        });
        
        updateMarkers();
    }
    
    /**
     * Toggle available points visibility
     */
    function toggleAvailable() {
        showAvailable = !showAvailable;
        document.getElementById('filter-available').classList.toggle('active', showAvailable);
        updateMarkers();
    }
    
    /**
     * Toggle unavailable points visibility
     */
    function toggleUnavailable() {
        showUnavailable = !showUnavailable;
        document.getElementById('filter-unavailable').classList.toggle('active', showUnavailable);
        updateMarkers();
    }
    
    /**
     * Update statistics display
     */
    function updateStats() {
        const totalPoints = allData.length;
        const availablePoints = allData.filter(point => point.isAvailable === 1).length;
        const unavailablePoints = totalPoints - availablePoints;
        
        document.getElementById('total-points').textContent = totalPoints;
        document.getElementById('available-points').textContent = availablePoints;
        document.getElementById('unavailable-points').textContent = unavailablePoints;
    }
    
    /**
     * Set up event listeners for UI elements
     */
    function setupEventListeners() {
        // Filter buttons
        document.getElementById('filter-available').addEventListener('click', toggleAvailable);
        document.getElementById('filter-unavailable').addEventListener('click', toggleUnavailable);
        
        // Street filter
        document.getElementById('street-filter').addEventListener('input', filterStreetList);
        document.getElementById('clear-street').addEventListener('click', clearStreetFilter);
    }
});