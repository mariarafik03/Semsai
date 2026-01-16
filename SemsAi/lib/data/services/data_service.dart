import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:SemsAi/data/models/developer.dart';
import 'api_client.dart';

class DataService {
  static Future<List<Developer>> getDevelopers() async {
    final http.Response res = await ApiClient.get('/developers');
    final List list = jsonDecode(res.body);
    return list.map((e) => Developer.fromJson(e)).toList();
  }
}
