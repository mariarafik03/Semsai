import 'package:SemsAi/data/services/api_client.dart';
import 'package:flutter/material.dart';
import 'package:SemsAi/core/colors.dart';
import 'package:SemsAi/core/strings.dart';
import 'package:SemsAi/data/repositories/auth_repository.dart';

class LocationOptionsSheet extends StatefulWidget {
  const LocationOptionsSheet({super.key});

  @override
  State<LocationOptionsSheet> createState() => _LocationOptionsSheetState();
}

class _LocationOptionsSheetState extends State<LocationOptionsSheet> {
  List<Map<String, dynamic>> _savedLocations = [];
  bool _isLoading = true;
  String? _userEmail;

  @override
  void initState() {
    super.initState();
    _fetchLocations();
  }

  Future<void> _fetchLocations() async {
    setState(() => _isLoading = true);

    if (_userEmail == null) {
      final user = await AuthRepositoryImpl().getUser();
      if (user != null) {
        _userEmail = user.email;
      }
    }

    if (_userEmail != null) {
      final locations = await ApiClient.getLocations(_userEmail!);
      if (mounted) {
        setState(() {
          _savedLocations = locations;
          _isLoading = false;
        });
      }
    } else {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _deleteLocation(String locationId) async {
    if (_userEmail == null) return;

    final location = _savedLocations.firstWhere(
      (element) => element['_id'] == locationId,
    );
    setState(() {
      _savedLocations.removeWhere((element) => element['_id'] == locationId);
    });

    final success = await ApiClient.deleteLocation(_userEmail!, locationId);
    if (!success && mounted) {
      setState(() {
        _savedLocations.add(location);
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to delete location')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      // Styling for the Bottom Sheet
      padding: const EdgeInsets.all(20.0),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag Handle
          Container(
            height: 5,
            width: 50,
            decoration: BoxDecoration(
              color: myColors.lightgrayColor,
              borderRadius: BorderRadius.circular(10),
            ),
          ),
          const SizedBox(height: 20),

          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'My Locations',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: Colors.black,
                ),
              ),
            ],
          ),
          const Divider(height: 20),

          // Body: Loading | Empty | List
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(20.0),
              child: CircularProgressIndicator(),
            )
          else if (_savedLocations.isEmpty)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 20),
              child: Column(
                children: [
                  Icon(
                    Icons.location_off_outlined,
                    size: 50,
                    color: myColors.lightgrayColor.withOpacity(0.5),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'No saved locations yet',
                    style: TextStyle(fontSize: 16, color: Colors.grey),
                  ),
                ],
              ),
            )
          else
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 200),
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: _savedLocations.length,
                itemBuilder: (context, index) {
                  final loc = _savedLocations[index];
                  return ListTile(
                    leading: Icon(Icons.place, color: myColors.orangeColor),
                    title: Text(loc['name'] ?? 'Unknown'),

                    // Delete Button
                    trailing: IconButton(
                      icon: const Icon(Icons.close, color: Colors.grey),
                      onPressed: () {
                        if (loc['_id'] != null) {
                          _deleteLocation(loc['_id']);
                        }
                      },
                    ),

                    // Tap to Open Map
                    onTap: () async {
                      final navigator = Navigator.of(context);
                      navigator.pop(); // Close the sheet first

                      // Navigate to MapScreen in View Mode
                      await navigator.pushNamed(
                        AppStrings.mapRoute,
                        arguments: {
                          'lat': loc['lat'],
                          'lng': loc['lng'],
                          'name': loc['name'],
                        },
                      );
                    },
                  );
                },
              ),
            ),

          const SizedBox(height: 20),

          // "Add New" Button
          ElevatedButton(
            onPressed: () async {
              final navigator = Navigator.of(context);
              navigator.pop(); // Close sheet before opening map

              // Open Map to Pick Location
              final result = await navigator.pushNamed(AppStrings.mapRoute);

              // If user selected a location (and didn't just back out)
              if (result != null && result is Map<String, dynamic>) {
                if (_userEmail != null) {
                  // 1. Check for Duplicates
                  final isDuplicate = _savedLocations.any(
                    (loc) =>
                        (loc['lat'] == result['lat'] &&
                            loc['lng'] == result['lng']) ||
                        (loc['name'] == result['name'] &&
                            result['name'] != 'Pinned Location'),
                  );

                  if (isDuplicate) {
                    ScaffoldMessenger.of(navigator.context).showSnackBar(
                      const SnackBar(content: Text('Location already saved!')),
                    );
                    return;
                  }

                  // 2. Save Location
                  await ApiClient.saveLocation(_userEmail!, result);
                  ScaffoldMessenger.of(navigator.context).showSnackBar(
                    SnackBar(content: Text('${result['name']} Saved')),
                  );
                }
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: myColors.orangeColor,
              minimumSize: Size(double.infinity, 50),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: const Text(
              'Add New Location',
              style: TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(height: 10),
        ],
      ),
    );
  }
}
