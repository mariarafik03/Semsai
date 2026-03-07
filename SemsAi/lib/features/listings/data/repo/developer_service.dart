import 'dart:convert';
import 'package:SemsAi/core/networking/api_client.dart';
import 'package:SemsAi/features/listings/data/models/developer_model.dart';

class DeveloperService {
  static Future<Developer> getDeveloperByName(String name) async {
    final encoded = Uri.encodeQueryComponent(name);
    final res = await ApiClient.get('/developers/search?name=$encoded');
    if (res.statusCode == 200) {
      final json = jsonDecode(res.body) as Map<String, dynamic>;
      return Developer.fromJson(json);
    }
    throw Exception('Developer not found');
  }
}
