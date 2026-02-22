import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:SemsAi/core/networking/api_constants.dart';

class ConversationService {
  static String get _base => ApiConstants.agentsUrl;

  /// Start a new chat session. Returns { session_id, message, phase, done }.
  static Future<Map<String, dynamic>> startChat() async {
    final res = await http.post(
      Uri.parse('$_base/chat/start'),
      headers: {'Content-Type': 'application/json'},
    );

    if (res.statusCode != 200) {
      throw Exception('Failed to start chat: ${res.statusCode} ${res.body}');
    }

    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  /// Send a user message. Returns { message, phase, done, results? }.
  static Future<Map<String, dynamic>> respond(
    String sessionId,
    String message,
  ) async {
    final res = await http.post(
      Uri.parse('$_base/chat/respond'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'session_id': sessionId, 'message': message}),
    );

    if (res.statusCode != 200) {
      throw Exception('Failed to respond: ${res.statusCode} ${res.body}');
    }

    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  /// Get session status.
  static Future<Map<String, dynamic>> getStatus(String sessionId) async {
    final res = await http.get(Uri.parse('$_base/chat/status/$sessionId'));

    if (res.statusCode != 200) {
      throw Exception('Failed to get status: ${res.body}');
    }

    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  /// Get final results/recommendations.
  static Future<Map<String, dynamic>> getResults(String sessionId) async {
    final res = await http.get(Uri.parse('$_base/chat/results/$sessionId'));

    if (res.statusCode != 200) {
      throw Exception('Failed to get results: ${res.body}');
    }

    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
