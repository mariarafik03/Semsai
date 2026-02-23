import 'dart:convert';
import 'package:SemsAi/features/explore/data/models/compound_model.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/core/networking/api_client.dart';

class ExploreService {
  /// get compounds with map data (id, name, location) for explore screen
  static Future<List<Compound>> getMapCompounds() async {
    final res = await ApiClient.get('/compounds/map');
    if (res.statusCode == 200) {
      final List data = jsonDecode(res.body);
      return data.map((j) => Compound.fromJson(j)).toList();
    }
    throw Exception('Failed to load compounds: ${res.statusCode}');
  }

  /// get units for a compound, with all details needed for listing and filtering (price, area, payment plans, etc)
  static Future<List<CompoundUnit>> getCompoundUnits(String compoundId) async {
    final res = await ApiClient.get('/compounds/$compoundId/units');
    if (res.statusCode == 200) {
      final List data = jsonDecode(res.body);
      return data.map((j) => CompoundUnit.fromJson(j)).toList();
    }
    throw Exception('Failed to load units: ${res.statusCode}');
  }

  /// get full compound details for details screen (description, amenities, developer info, etc)
  static Future<Compound> getCompoundDetails(String compoundId) async {
    final res = await ApiClient.get('/compounds/$compoundId');
    if (res.statusCode == 200) {
      final data = jsonDecode(res.body);
      return Compound.fromJson(data);
    }
    throw Exception('Failed to load compound: ${res.statusCode}');
  }

  /// get available areas for filtering 
  static Future<Map<String, dynamic>> getAreas() async {
    final res = await ApiClient.get('/explore/areas');
    if (res.statusCode == 200) {
      return jsonDecode(res.body) as Map<String, dynamic>;
    }
    throw Exception('Failed to load areas: ${res.statusCode}');
  }
}
