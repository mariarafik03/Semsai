import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/features/chat/presentation/cubit/chat_state.dart';
import 'package:SemsAi/features/chat/data/repo/conversation_repository.dart';

class ChatCubit extends Cubit<ChatState> {
  final ConversationRepository conversationRepository;

  ChatCubit({required this.conversationRepository}) : super(ChatInitial());

  /// Start a new conversation with the AI agent.
  Future<void> initializeChat() async {
    emit(ChatLoading());

    try {
      final response = await conversationRepository.startChat();

      final sessionId = response['session_id'] as String;
      final message = response['message'] as String? ?? '';
      final phase = response['phase'] as String? ?? 'purpose';

      emit(
        ChatLoaded(
          sessionId: sessionId,
          phase: phase,
          messages: [
            {'role': 'assistant', 'content': message},
          ],
        ),
      );
    } catch (e) {
      emit(ChatError(e.toString()));
    }
  }

  /// Send a user message and get the agent's response.
  Future<void> sendMessage(String message) async {
    if (state is! ChatLoaded) return;

    final current = state as ChatLoaded;

    // Add user message immediately + show typing indicator
    final updatedMessages = [
      ...current.messages,
      {'role': 'user', 'content': message},
    ];

    emit(current.copyWith(messages: updatedMessages, isTyping: true));

    try {
      final response = await conversationRepository.respond(
        current.sessionId,
        message,
      );

      final agentMessage = response['message'] as String? ?? '';
      final phase = response['phase'] as String? ?? current.phase;
      final done = response['done'] as bool? ?? false;
      final rawResults = response['results'] as Map<String, dynamic>?;

      final allMessages = [
        ...updatedMessages,
        if (agentMessage.isNotEmpty)
          {'role': 'assistant', 'content': agentMessage},
      ];

      emit(
        ChatLoaded(
          sessionId: current.sessionId,
          phase: phase,
          messages: allMessages,
          done: done,
          isTyping: false,
          results: rawResults,
        ),
      );
    } catch (e) {
      // Recover state with messages preserved, stop typing
      emit(current.copyWith(messages: updatedMessages, isTyping: false));
      emit(ChatError(e.toString()));
      // Re-emit loaded state so user can retry
      emit(current.copyWith(messages: updatedMessages, isTyping: false));
    }
  }

  /// Reset and start a new conversation.
  Future<void> resetChat() async {
    await initializeChat();
  }
}
