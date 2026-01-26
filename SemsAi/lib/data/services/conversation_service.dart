import 'dart:convert';
import 'package:SemsAi/data/services/api_client.dart';

class ConversationService {
  static Future<Map<String, dynamic>> step(
    Map<String, dynamic> state,
    String? userInput,
  ) async {
    final res = await ApiClient.post('/conversation/step', {
      'state': state,
      'user_input': userInput,
    });

    if (res.statusCode != 200 && res.statusCode != 201) {
      // Check if error 
      try {
        final err = jsonDecode(res.body);
        throw Exception(err['error'] ?? res.body);
      } catch (e) {
        throw Exception('Failed to step: ${res.statusCode} ${res.body}');
      }
    }

    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  static Future<List<dynamic>> getRecommendations(
    Map<String, dynamic> finalState,
  ) async {
    final res = await ApiClient.post('/recommendations', {'state': finalState});

    if (res.statusCode != 200) {
      throw Exception('Failed to get recommendations: ${res.body}');
    }

    return jsonDecode(res.body) as List<dynamic>;
  }
}
