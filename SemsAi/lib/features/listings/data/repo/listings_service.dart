import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/core/networking/api_client.dart';

class ListingsService {
  static Future<ListingsResponse> getListings({
    int page = 1,
    int limit = 20,
    String? region,
    String? type,
    int? bedrooms,
    double? minPrice,
    double? maxPrice,
    String? search,
    String sort = 'newest',
  }) async {
    final params = <String, String>{
      'page': '$page',
      'limit': '$limit',
      'sort': sort,
    };
    if (region != null) params['region'] = region;
    if (type != null) params['type'] = type;
    if (bedrooms != null) params['bedrooms'] = '$bedrooms';
    if (minPrice != null) params['minPrice'] = '$minPrice';
    if (maxPrice != null) params['maxPrice'] = '$maxPrice';
    if (search != null && search.isNotEmpty) params['search'] = search;

    final query = params.entries.map((e) => '${e.key}=${e.value}').join('&');
    final res = await ApiClient.get('/units/listings?$query');

    if (res.statusCode == 200) {
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      final rawUnits = data['units'] as List;
      final units = <CompoundUnit>[];
      for (final j in rawUnits) {
        try {
          units.add(CompoundUnit.fromJson(j as Map<String, dynamic>));
        } catch (e) {
          debugPrint('Skip bad unit: $e');
        }
      }
      return ListingsResponse(
        units: units,
        total: data['total'] as int,
        page: data['page'] as int,
        totalPages: data['totalPages'] as int,
      );
    }
    throw Exception('Failed to load listings: ${res.statusCode}');
  }


  static Future<FiltersResponse> getFilters() async {
    final res = await ApiClient.get('/units/filters');
    if (res.statusCode == 200) {
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      final regions = (data['regions'] as List)
          .map(
            (r) => RegionFilter(
              name: r['name'] as String,
              count: r['count'] as int,
            ),
          )
          .toList();
      final types = List<String>.from(data['types'] as List);
      return FiltersResponse(regions: regions, types: types);
    }
    throw Exception('Failed to load filters: ${res.statusCode}');
  }
}

class ListingsResponse {
  final List<CompoundUnit> units;
  final int total;
  final int page;
  final int totalPages;

  const ListingsResponse({
    required this.units,
    required this.total,
    required this.page,
    required this.totalPages,
  });
}

class FiltersResponse {
  final List<RegionFilter> regions;
  final List<String> types;

  const FiltersResponse({required this.regions, required this.types});
}

class RegionFilter {
  final String name;
  final int count;

  const RegionFilter({required this.name, required this.count});
}
