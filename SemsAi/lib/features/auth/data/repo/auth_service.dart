import 'dart:convert';
import 'package:SemsAi/features/auth/data/models/user_model.dart';
import 'package:SemsAi/core/networking/api_client.dart';
import 'package:http/http.dart' as http;

class AuthService {
  static Future<User?> register(User user) async {
    final http.Response res = await ApiClient.post(
      '/auth/register',
      user.toJson(),
    );
    if (res.statusCode == 201) {
      final Map<String, dynamic> data = jsonDecode(res.body);
      return User.fromJson(data);
    }
    return null;
  }

  static Future<User?> login(String email, String pass) async {
    final http.Response res = await ApiClient.post('/auth/login', {
      'email': email,
      'pass': pass,
    });
    if (res.statusCode == 200) {
      final Map<String, dynamic> data = jsonDecode(res.body);
      return User.fromJson(data);
    }
    return null;
  }

  // Returns a result map: {"success": true/false, "error": "..."}
  static Future<Map<String, dynamic>> resetPassword(
    String email,
    String newPass,
  ) async {
    final http.Response res = await ApiClient.post('/auth/forgot-password', {
      'email': email.toLowerCase(),
      'newPass': newPass,
    });
    final Map<String, dynamic> data = jsonDecode(res.body);
    if (res.statusCode == 200) {
      return {'success': true, 'message': data['message']};
    } else if (res.statusCode == 404) {
      return {'success': false, 'error': data['error'] ?? 'Account not found'};
    } else {
      return {'success': false, 'error': data['error'] ?? 'Something went wrong'};
    }
  }
}
