import 'dart:convert';
import 'package:SemsAi/core/networking/api_constants.dart';
import 'package:http/http.dart' as http;

class ApiClient {
  static const Duration _timeout = Duration(seconds: 30);

  static Future<http.Response> get(String path) async {
    final url = Uri.parse('${ApiConstants.baseUrl}$path');
    try {
      print('GET request to: $url');
      final response = await http.get(url).timeout(_timeout);
      print('GET response status: ${response.statusCode}');
      return response;
    } catch (e) {
      print('GET Error connecting to $url: $e');
      rethrow;
    }
  }

  static Future<http.Response> post(
    String path,
    Map<String, dynamic> body,
  ) async {
    final url = Uri.parse('${ApiConstants.baseUrl}$path');
    try {
      print('POST request to: $url');
      final response = await http
          .post(
            url,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(_timeout);
      print('POST response status: ${response.statusCode}');
      return response;
    } catch (e) {
      print('POST Error connecting to $url: $e');
      rethrow;
    }
  }

  static Future<bool> saveLocation(
    String email,
    Map<String, dynamic> location,
  ) async {
    try {
      final res = await post('/users/locations', {
        'email': email,
        'location': location,
      });
      return res.statusCode == 201;
    } catch (e) {
      print('Save Location Error: $e');
      return false;
    }
  }

  static Future<List<Map<String, dynamic>>> getLocations(String email) async {
    try {
      final url = Uri.parse(
        '${ApiConstants.baseUrl}/users/locations?email=$email',
      );
      final res = await http.get(url);
      if (res.statusCode == 200) {
        final List<dynamic> data = jsonDecode(res.body);
        return data.cast<Map<String, dynamic>>();
      }
      return [];
    } catch (e) {
      print('Get Locations Error: $e');
      return [];
    }
  }

  static Future<bool> deleteLocation(String email, String locationId) async {
    try {
      final url = Uri.parse(
        '${ApiConstants.baseUrl}/users/locations/$locationId',
      );
      final res = await http.delete(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email}),
      );
      return res.statusCode == 200;
    } catch (e) {
      print('Delete Location Error: $e');
      return false;
    }
  }
}
