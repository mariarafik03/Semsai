import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

class DeveloperDetailsSheet extends StatelessWidget {
  final Map<String, dynamic> developer;
  final Function(Map<String, dynamic>)? onSelect;

  const DeveloperDetailsSheet({
    super.key,
    required this.developer,
    this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (developer['image'] != null)
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.asset(
                developer['image'],
                height: 150,
                width: double.infinity,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) => Container(
                  height: 150,
                  color: Colors.grey[300],
                  child: const Icon(
                    Icons.broken_image,
                    size: 50,
                    color: Colors.grey,
                  ),
                ),
              ),
            ),
          const SizedBox(height: 16),
          Text(
            developer['name'] ?? 'Unknown Location',
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
          ),
          if (developer['description'] != null) ...[
            const SizedBox(height: 8),
            Text(
              developer['description'],
              style: const TextStyle(fontSize: 14, color: Colors.grey),
            ),
          ],
          const SizedBox(height: 24),
          if (onSelect != null)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                  final result = {
                    'name': developer['name'],
                    // Handle cases where location might be LatLng object or separated lat/lng double
                    'lat': developer['location'] is LatLng
                        ? (developer['location'] as LatLng).latitude
                        : developer['lat'],
                    'lng': developer['location'] is LatLng
                        ? (developer['location'] as LatLng).longitude
                        : developer['lng'],
                  };
                  onSelect!(result);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Select This Project',
                  style: TextStyle(color: Colors.white),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
