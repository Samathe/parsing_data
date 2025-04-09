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
    let showBothProviders = true;
    let showSingleProvider = true;
    let selectedStreet = null;
    let selectedProvider = null;
    let providerCounts = {};
    let isSidebarOpen = false;
    
    // Initialize the application
    initializeMap();
    loadMapData();
    setupEventListeners();
    setupMobileLayout();
    
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
                <div><i class="both-providers"></i> Both Providers</div>
                <div><i class="single-provider"></i> Single Provider</div>
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
        
        // Process data to identify addresses with multiple providers
        processProviderData();
        
        // Update markers
        updateMarkers();
        
        // Update street list
        updateStreetList();
        
        // Update provider list
        updateProviderList();
        
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
     * Process provider data to identify locations with multiple providers
     */
    function processProviderData() {
        // Create a map to track addresses by their coordinates
        const addressMap = new Map();
        
        allData.forEach(point => {
            // Skip points without valid coordinates
            if (!point.latitude || !point.longitude) return;
            
            const key = `${point.latitude},${point.longitude}`;
            
            // If the address is already in the map, update its providers list
            if (addressMap.has(key)) {
                const address = addressMap.get(key);
                if (!address.providers.includes(point.provider)) {
                    address.providers.push(point.provider);
                }
            } else {
                // Otherwise, add it to the map
                addressMap.set(key, {
                    ...point,
                    providers: [point.provider]
                });
            }
        });
        
        // Convert the map back to an array and update allData
        allData = Array.from(addressMap.values());
        
        // Count unique providers
        const uniqueProviders = new Set();
        allData.forEach(point => {
            if (point.providers) {
                point.providers.forEach(provider => uniqueProviders.add(provider));
            }
        });
        
        // Count addresses by provider count
        providerCounts = {
            total: allData.length,
            bothProviders: allData.filter(point => point.providers && point.providers.length > 1).length,
            singleProvider: allData.filter(point => point.providers && point.providers.length === 1).length,
            available: allData.filter(point => point.isAvailable === 1).length,
            unavailable: allData.filter(point => point.isAvailable === 0).length
        };
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
            const hasBothProviders = point.providers && point.providers.length > 1;
            const hasSingleProvider = point.providers && point.providers.length === 1;
            
            const visibleByAvailability = (isAvailable && showAvailable) || 
                                        (!isAvailable && showUnavailable);
            
            const visibleByProviderCount = (hasBothProviders && showBothProviders) || 
                                          (hasSingleProvider && showSingleProvider);
            
            const visibleBySelectedProvider = !selectedProvider || 
                                            (point.providers && point.providers.includes(selectedProvider));
            
            const visibleByStreet = !selectedStreet || 
                                    point.streetName === selectedStreet;
            
            if (visibleByAvailability && visibleByProviderCount && visibleBySelectedProvider && visibleByStreet) {
                // Create marker only if coordinates are valid
                const lat = parseFloat(point.latitude);
                const lng = parseFloat(point.longitude);
                
                if (!isNaN(lat) && !isNaN(lng)) {
                    // Determine marker color based on availability and provider count
                    let markerColor;
                    if (hasBothProviders) {
                        markerColor = isAvailable ? '#8e24aa' : '#6a1b9a'; // Purple for both providers
                    } else if (hasSingleProvider) {
                        markerColor = isAvailable ? '#43a047' : '#e53935'; // Green/Red for single provider
                    } else {
                        markerColor = isAvailable ? '#43a047' : '#e53935'; // Fallback
                    }
                    
                    // Create a circle marker
                    const circleMarker = L.circleMarker([lat, lng], {
                        radius: hasBothProviders ? 10 : 8, // Larger radius for both providers
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
                    
                    const providersText = point.providers && point.providers.length > 0
                        ? `<p><strong>Providers:</strong> ${point.providers.join(', ')}</p>`
                        : '';
                    
                    const popupContent = `
                        <div class="popup-content">
                            <h3>${point.streetName}, ${point.house}${subHouseText ? ` ${subHouseText}` : ''}</h3>
                            <p class="availability ${isAvailable ? 'available' : 'unavailable'}">
                                <strong>Availability:</strong> ${isAvailable ? 'Available' : 'Unavailable'}
                            </p>
                            <p class="provider-count ${hasBothProviders ? 'both-providers' : 'single-provider'}">
                                <strong>Provider Count:</strong> ${hasBothProviders ? 'Both Providers' : 'Single Provider'}
                            </p>
                            ${providersText}
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
                
                // Close sidebar on mobile after selection
                if (window.innerWidth <= 768) {
                    closeSidebar();
                }
            });
            
            streetList.appendChild(streetItem);
        });
    }
    
    /**
     * Update the list of providers for filtering
     */
    function updateProviderList() {
        const providerList = document.getElementById('provider-list');
        if (!providerList) return;
        
        providerList.innerHTML = '';
        
        // Get unique providers
        const providers = [...new Set(allData.flatMap(point => point.providers || []))].sort();
        
        providers.forEach(provider => {
            const providerItem = document.createElement('div');
            providerItem.className = 'provider-item';
            providerItem.textContent = provider;
            providerItem.addEventListener('click', () => {
                selectedProvider = provider;
                
                // Update selected class
                document.querySelectorAll('.provider-item').forEach(item => {
                    item.classList.remove('selected');
                });
                providerItem.classList.add('selected');
                
                updateMarkers();
                
                // Close sidebar on mobile after selection
                if (window.innerWidth <= 768) {
                    closeSidebar();
                }
            });
            
            providerList.appendChild(providerItem);
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
     * Clear provider filter
     */
    function clearProviderFilter() {
        selectedProvider = null;
        
        // Remove selected class
        document.querySelectorAll('.provider-item').forEach(item => {
            item.classList.remove('selected');
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
     * Toggle both providers visibility
     */
    function toggleBothProviders() {
        showBothProviders = !showBothProviders;
        document.getElementById('filter-both-providers').classList.toggle('active', showBothProviders);
        updateMarkers();
    }
    
    /**
     * Toggle single provider visibility
     */
    function toggleSingleProvider() {
        showSingleProvider = !showSingleProvider;
        document.getElementById('filter-single-provider').classList.toggle('active', showSingleProvider);
        updateMarkers();
    }
    
    /**
     * Update statistics display
     */
    function updateStats() {
        document.getElementById('total-points').textContent = providerCounts.total || 0;
        document.getElementById('available-points').textContent = providerCounts.available || 0;
        document.getElementById('unavailable-points').textContent = providerCounts.unavailable || 0;
        document.getElementById('both-providers-points').textContent = providerCounts.bothProviders || 0;
        document.getElementById('single-provider-points').textContent = providerCounts.singleProvider || 0;
    }
    
    /**
     * Set up mobile layout
     */
    function setupMobileLayout() {
        const toggleSidebarButton = document.getElementById('toggle-sidebar');
        const sidebar = document.getElementById('sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        
        if (toggleSidebarButton && sidebar && overlay) {
            toggleSidebarButton.addEventListener('click', toggleSidebar);
            overlay.addEventListener('click', closeSidebar);
            
            // Close sidebar when map is clicked on mobile
            map.on('click', function() {
                if (window.innerWidth <= 768 && isSidebarOpen) {
                    closeSidebar();
                }
            });
            
            // Update map size when sidebar is toggled
            sidebar.addEventListener('transitionend', function() {
                map.invalidateSize();
            });
        }
        
        // Handle window resize
        window.addEventListener('resize', function() {
            // If returning to desktop view, reset sidebar
            if (window.innerWidth > 768) {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
                isSidebarOpen = false;
            }
            
            // Always update map size on resize
            map.invalidateSize();
        });
    }
    
    /**
     * Toggle sidebar visibility on mobile
     */
    function toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        
        if (sidebar.classList.contains('open')) {
            closeSidebar();
        } else {
            sidebar.classList.add('open');
            overlay.classList.add('active');
            isSidebarOpen = true;
        }
    }
    
    /**
     * Close sidebar on mobile
     */
    function closeSidebar() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
        isSidebarOpen = false;
    }
    
    /**
     * Set up event listeners for UI elements
     */
    function setupEventListeners() {
        // Availability filter buttons
        document.getElementById('filter-available').addEventListener('click', toggleAvailable);
        document.getElementById('filter-unavailable').addEventListener('click', toggleUnavailable);
        
        // Provider count filter buttons
        document.getElementById('filter-both-providers').addEventListener('click', toggleBothProviders);
        document.getElementById('filter-single-provider').addEventListener('click', toggleSingleProvider);
        
        // Street filter
        document.getElementById('street-filter').addEventListener('input', filterStreetList);
        document.getElementById('clear-street').addEventListener('click', clearStreetFilter);
        
        // Provider filter
        const clearProviderButton = document.getElementById('clear-provider');
        if (clearProviderButton) {
            clearProviderButton.addEventListener('click', clearProviderFilter);
        }
    }
});