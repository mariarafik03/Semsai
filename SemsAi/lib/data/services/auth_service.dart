import 'dart:convert';
import 'package:SemsAi/data/models/user.dart';
import 'package:http/http.dart' as http;
import 'api_client.dart';

class AuthService {
  static Future<User?> register(User user) async {
    final http.Response res = await ApiClient.post(
      '/auth/register',
      user.toJson(),
    );

    print('${res.statusCode}');
    print('${res.body}');

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

    print('${res.statusCode}');
    print('${res.body}');

    if (res.statusCode == 200) {
      final Map<String, dynamic> data = jsonDecode(res.body);
      return User.fromJson(data);
    }
    return null;
  }
}
