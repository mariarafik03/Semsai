import 'package:equatable/equatable.dart';

class Developer extends Equatable {
  final String? id;
  final String devName;
  final int projectsCompleted;
  final int totalProjects;
  final String specialization;
  final double rating;
  final String devHistory;
  final int? yearsActive;
  final double googleReviewsScore;
  final double facebookReviewsScore;
  final String deliveryDelays;
  final double? developerScore;
  final List<String> areas;
  final List<String> compoundNames;
  final int? compoundsCount;
  final String? description;
  final String? logoUrl;
  final String? phone;
  final String? website;
  final double? priceMin;
  final double? priceMax;
  final String? developerClass;
  final String? nawyUrl;

  const Developer({
    this.id,
    required this.devName,
    required this.projectsCompleted,
    required this.totalProjects,
    required this.specialization,
    required this.rating,
    required this.devHistory,
    this.yearsActive,
    this.googleReviewsScore = 0,
    this.facebookReviewsScore = 0,
    this.deliveryDelays = 'None',
    this.developerScore,
    this.areas = const [],
    this.compoundNames = const [],
    this.compoundsCount,
    this.description,
    this.logoUrl,
    this.phone,
    this.website,
    this.priceMin,
    this.priceMax,
    this.developerClass,
    this.nawyUrl,
  });

  Map<String, dynamic> toJson() => {
    'dev_name': devName,
    'projects_completed': projectsCompleted,
    'total_projects': totalProjects,
    'specialization': specialization,
    'rating': rating,
    'dev_history': devHistory,
  };

  factory Developer.fromJson(Map<String, dynamic> json) => Developer(
    id: json['_id']?.toString(),
    devName: json['dev_name'] ?? '',
    projectsCompleted: _toInt(json['projects_completed']) ?? 0,
    totalProjects: _toInt(json['total_projects']) ?? 0,
    specialization: json['specialization']?.toString() ?? '',
    rating: _toDouble(json['rating']) ?? 0.0,
    devHistory: json['dev_history']?.toString() ?? '',
    yearsActive: _toInt(json['years_active']),
    googleReviewsScore: _toDouble(json['google_reviews_score']) ?? 0,
    facebookReviewsScore: _toDouble(json['facebook_reviews_score']) ?? 0,
    deliveryDelays: json['delivery_delays']?.toString() ?? 'None',
    developerScore: _toDouble(json['developer_score']),
    areas: _toStringList(json['areas']),
    compoundNames: _toStringList(json['compound_names']),
    compoundsCount: _toInt(json['compounds_count']),
    description: json['description']?.toString(),
    logoUrl: json['logo_url']?.toString(),
    phone: json['phone']?.toString(),
    website: json['website']?.toString(),
    priceMin: _toDouble(json['price_min']),
    priceMax: _toDouble(json['price_max']),
    developerClass: json['Developer_Class']?.toString(),
    nawyUrl: json['nawy_url']?.toString(),
  );

  static double? _toDouble(dynamic v) {
    if (v == null) return null;
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v);
    return null;
  }

  static int? _toInt(dynamic v) {
    if (v == null) return null;
    if (v is int) return v;
    if (v is num) return v.toInt();
    if (v is String) return int.tryParse(v);
    return null;
  }

  static List<String> _toStringList(dynamic v) {
    if (v is List) return v.map((e) => e.toString()).toList();
    return const [];
  }

  @override
  List<Object?> get props => [id, devName];
}
