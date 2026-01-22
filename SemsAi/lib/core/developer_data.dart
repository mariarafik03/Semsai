import 'package:latlong2/latlong.dart';

class DeveloperData {
  static final List<Map<String, dynamic>> developers = [
    {
      'name': 'Zed Towers',
      'location': const LatLng(30.03380, 31.00608),
      'image': 'assets/images/Zed-towers.jpg',
      'description':
          'Luxury towers in the heart of Sheikh Zayed, overlooking the Park.',
    },
    {
      'name': 'Emaar Misr',
      'location': const LatLng(30.015, 31.425),
      'image': 'assets/images/Emaar-Misr.jpg',
      'description': 'Developing world-class communities in Egypt.',
    },
    {
      'name': 'Mountain View',
      'location': const LatLng(30.05, 31.45),
      'image':
          'assets/images/mv-giza-plateau-gpl-cairo-alex-desert-rd-mountain-view-4jpg-1200x900.jpg',
      'description': 'Leading developer offering unique living experiences.',
    },
  ];
}
