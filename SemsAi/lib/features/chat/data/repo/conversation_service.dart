import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:SemsAi/core/networking/api_constants.dart';

class ConversationService {
  static String get _base => ApiConstants.agentsUrl;
  static const Duration _timeout = Duration(seconds: 35);

  /// Start a new chat session. Returns { session_id, message, phase, done }.
  static Future<Map<String, dynamic>> startChat() async {
    try {
      print('Starting chat session with: $_base/chat/start');
      final res = await http
          .post(
            Uri.parse('$_base/chat/start'),
            headers: {'Content-Type': 'application/json'},
          )
          .timeout(_timeout);

      print('Start chat response status: ${res.statusCode}');

      if (res.statusCode != 200) {
        throw Exception('Failed to start chat: ${res.statusCode} ${res.body}');
      }

      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (e) {
      print('ERROR starting chat: $e');
      rethrow;
    }
  }

  /// Send a user message. Returns { message, phase, done, results? }.
  static Future<Map<String, dynamic>> respond(
    String sessionId,
    String message,
  ) async {
    try {
      print('Sending message to: $_base/chat/respond');
      final res = await http
          .post(
            Uri.parse('$_base/chat/respond'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'session_id': sessionId, 'message': message}),
          )
          .timeout(_timeout);

      print('Respond response status: ${res.statusCode}');

      if (res.statusCode != 200) {
        throw Exception('Failed to respond: ${res.statusCode} ${res.body}');
      }

      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (e) {
      print('ERROR responding: $e');
      rethrow;
    }
  }

  /// Get session status.
  static Future<Map<String, dynamic>> getStatus(String sessionId) async {
    try {
      print('Getting status from: $_base/chat/status/$sessionId');
      final res = await http
          .get(Uri.parse('$_base/chat/status/$sessionId'))
          .timeout(_timeout);

      print('Status response: ${res.statusCode}');

      if (res.statusCode != 200) {
        throw Exception('Failed to get status: ${res.body}');
      }

      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (e) {
      print('ERROR getting status: $e');
      rethrow;
    }
  }

  /// Get final results/recommendations.
  static Future<Map<String, dynamic>> getResults(String sessionId) async {
    try {
      print('Getting results from: $_base/chat/results/$sessionId');
      final res = await http
          .get(Uri.parse('$_base/chat/results/$sessionId'))
          .timeout(_timeout);

      print('Results response: ${res.statusCode}');

      if (res.statusCode != 200) {
        throw Exception('Failed to get results: ${res.body}');
      }

      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (e) {
      print('ERROR getting results: $e');
      rethrow;
    }
  }
}
