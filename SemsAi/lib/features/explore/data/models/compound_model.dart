import 'package:equatable/equatable.dart';

class Compound extends Equatable {
  final String id;
  final String name;
  final double lat;
  final double lng;
  final String? location;
  final String? developerName;
  final int? unitCount;
  final String? description;
  final List<String> amenities;
  final List<String> imageUrls;
  final double? developerStartPrice;
  final double? resaleStartPrice;

  const Compound({
    required this.id,
    required this.name,
    required this.lat,
    required this.lng,
    this.location,
    this.developerName,
    this.unitCount,
    this.description,
    this.amenities = const [],
    this.imageUrls = const [],
    this.developerStartPrice,
    this.resaleStartPrice,
  });

  factory Compound.fromJson(Map<String, dynamic> json) => Compound(
    id: json['_id']?.toString() ?? '',
    name: json['name'] ?? '',
    lat: (json['lat'] as num?)?.toDouble() ?? 0.0,
    lng: (json['lng'] as num?)?.toDouble() ?? 0.0,
    location: json['location'],
    developerName: json['developer_name'],
    unitCount: json['unit_count'],
    description: json['description'],
    amenities: List<String>.from(
      json['amenities'] ?? json['amenities_list'] ?? [],
    ),
    imageUrls: List<String>.from(json['images_urls'] ?? []),
    developerStartPrice: (json['developer_start_price'] as num?)?.toDouble(),
    resaleStartPrice: (json['resale_start_price'] as num?)?.toDouble(),
  );

  /// Lowest available price (developer or resale)
  double? get startPrice {
    if (developerStartPrice != null && resaleStartPrice != null) {
      return developerStartPrice! < resaleStartPrice!
          ? developerStartPrice
          : resaleStartPrice;
    }
    return developerStartPrice ?? resaleStartPrice;
  }

  @override
  List<Object?> get props => [id, name, lat, lng];
}
