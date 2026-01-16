import 'dart:convert';
import 'package:SemsAi/core/strings.dart';
import 'package:http/http.dart' as http;

class ApiClient {

  static Future<http.Response> get(String path) async {
    final url = Uri.parse('$AppStrings.baseUrl$path');
    return await http.get(url);
  }

  static Future<http.Response> post(
    String path,
    Map<String, dynamic> body,
  ) async {
    final url = Uri.parse('$AppStrings.baseUrl$path');
    return await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
  }
}
