import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:SemsAi/core/developer_data.dart';
import 'package:SemsAi/presentation/screens/map/widgets/developer_details_sheet.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  LatLng? _selectedLocation;
  final MapController _mapController = MapController();

  // start at tahrir square
  static const LatLng _defaultLocation = LatLng(30.0444, 31.2357);
  bool _isViewMode = false;
  String? _viewModeName;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    // -----------------------------------------------------------
    // HANDLING "VIEW MODE" ARGUMENTS
    // -----------------------------------------------------------
    // This logic runs when the screen is opened with specific arguments (e.g. from Saved Locations).
    // We check if 'lat', 'lng', and 'name' are passed to us.
    final args = ModalRoute.of(context)?.settings.arguments;

    if (args != null && args is Map) {
      final lat = args['lat'];
      final lng = args['lng'];

      if (lat != null && lng != null) {
        // Robustly parse coordinates whether they come as double, int, or String
        final double latitude = (lat is num)
            ? lat.toDouble()
            : double.tryParse(lat.toString()) ?? 0.0;
        final double longitude = (lng is num)
            ? lng.toDouble()
            : double.tryParse(lng.toString()) ?? 0.0;

        // Ensure we have valid coordinates before updating the map state
        if (latitude != 0.0 || longitude != 0.0) {
          final loc = LatLng(latitude, longitude);

          // Only set the location if we haven't already selected one (prevents overriding user actions)
          if (_selectedLocation == null) {
            setState(() {
              _selectedLocation = loc;
              _isViewMode =
                  true; // Locks the "Confirm" button since we are just viewing
              _viewModeName = args['name']?.toString();
            });
          }
        }
      }
    }
  }

  // List of Real Estate Developers with their details
  final List<Map<String, dynamic>> _developers = DeveloperData.developers;

  // Helper method to show the bottom sheet with developer details
  void _showDeveloperDetails(
    BuildContext context,
    Map<String, dynamic> developer,
  ) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return DeveloperDetailsSheet(
          developer: developer,
          onSelect: (result) {
            // Return the selected developer location back to the previous screen
            Navigator.of(context).pop(result);
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        // Dynamic Title: Shows specific name in View Mode, otherwise generic title
        title: Text(
          _isViewMode
              ? (_viewModeName ?? 'Location Details')
              : 'Select Location',
        ),
        actions: [
          // Show "Check" icon only if a location is selected
          if (_selectedLocation != null)
            IconButton(
              icon: const Icon(Icons.check),
              onPressed: () {
                // Return the custom pinned location to the home screen
                final result = {
                  'name': 'Pinned Location',
                  'lat': _selectedLocation!.latitude,
                  'lng': _selectedLocation!.longitude,
                };
                Navigator.of(context).pop(result);
              },
            ),
        ],
      ),
      body: Stack(
        children: [
          // -------------------- MAP WIDGET --------------------
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              // Center map on selected location if available, else default to Tahrir Square
              initialCenter: _selectedLocation ?? _defaultLocation,
              initialZoom: 11.0,

              // When the map is fully loaded, ensure we are focused on the right spot
              onMapReady: () {
                if (_isViewMode && _selectedLocation != null) {
                  _mapController.move(_selectedLocation!, 15.0);
                }
              },

              // Handle user tapping on the map
              onTap: (tapPosition, point) {
                setState(() {
                  _selectedLocation = point;
                });
              },
            ),
            children: [
              // 1. Map Tiles (The visual map)
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.semsai.app',
              ),

              // 2. Developer Markers (Blue Icons)
              MarkerLayer(
                markers: _developers.map((dev) {
                  return Marker(
                    point: dev['location'] as LatLng,
                    width: 60,
                    height: 60,
                    child: GestureDetector(
                      onTap: () => _showDeveloperDetails(context, dev),
                      child: Column(
                        children: [
                          // White circle background
                          Container(
                            padding: const EdgeInsets.all(4),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withOpacity(0.2),
                                  blurRadius: 6,
                                ),
                              ],
                            ),
                            child: const Icon(
                              Icons.business,
                              color: Colors.blue,
                              size: 30,
                            ),
                          ),
                          // Developer Name Label
                          Text(
                            dev['name'],
                            style: const TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              backgroundColor: Colors.white54,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  );
                }).toList(),
              ),

              // 3. Selected Location Marker (Red Pin)
              if (_selectedLocation != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: _selectedLocation!,
                      width: 80,
                      height: 80,
                      child: const Icon(
                        Icons.location_on,
                        color: Colors.red,
                        size: 40,
                      ),
                    ),
                  ],
                ),
            ],
          ),

          // -------------------- CONFIRM BUTTON --------------------
          // Only show "Confirm Location" button if we are NOT in View Mode
          if (!_isViewMode)
            Positioned(
              bottom: 20,
              left: 20,
              right: 20,
              child: SafeArea(
                child: ElevatedButton(
                  onPressed: _selectedLocation == null
                      ? null
                      : () {
                          final result = {
                            'name': 'Pinned Location',
                            'lat': _selectedLocation!.latitude,
                            'lng': _selectedLocation!.longitude,
                          };
                          Navigator.of(context).pop(result);
                        },
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    backgroundColor: Theme.of(context).primaryColor,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: Colors.grey,
                    disabledForegroundColor: Colors.black38,
                  ),
                  child: const Text('Confirm Location'),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
