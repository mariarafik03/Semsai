import 'package:SemsAi/data/services/conversation_service.dart';

abstract class ConversationRepository {
  Future<Map<String, dynamic>> step(
    Map<String, dynamic> state,
    String? userInput,
  );
  Future<List<dynamic>> getRecommendations(Map<String, dynamic> finalState);
}

class ConversationRepositoryImpl implements ConversationRepository {
  @override
  Future<Map<String, dynamic>> step(
    Map<String, dynamic> state,
    String? userInput,
  ) async {
    return await ConversationService.step(state, userInput);
  }

  @override
  Future<List<dynamic>> getRecommendations(
    Map<String, dynamic> finalState,
  ) async {
    return await ConversationService.getRecommendations(finalState);
  }
}
