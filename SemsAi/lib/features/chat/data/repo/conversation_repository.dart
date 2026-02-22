import 'package:SemsAi/features/chat/data/repo/conversation_service.dart';

abstract class ConversationRepository {
  Future<Map<String, dynamic>> startChat();
  Future<Map<String, dynamic>> respond(String sessionId, String message);
  Future<Map<String, dynamic>> getResults(String sessionId);
}

class ConversationRepositoryImpl implements ConversationRepository {
  @override
  Future<Map<String, dynamic>> startChat() async {
    return await ConversationService.startChat();
  }

  @override
  Future<Map<String, dynamic>> respond(String sessionId, String message) async {
    return await ConversationService.respond(sessionId, message);
  }

  @override
  Future<Map<String, dynamic>> getResults(String sessionId) async {
    return await ConversationService.getResults(sessionId);
  }
}
