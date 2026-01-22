import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/business_logic/chat/chat_state.dart';
import 'package:SemsAi/data/repositories/conversation_repository.dart';

class ChatCubit extends Cubit<ChatState> {
  final ConversationRepository conversationRepository;

  ChatCubit({required this.conversationRepository}) : super(ChatInitial());

  void initializeChat() {
    emit(
      const ChatLoaded(conversationState: {'phase': 'greeting'}, messages: []),
    );
  }

  Future<void> sendMessage(String message) async {
    if (state is! ChatLoaded) return;

    final currentState = state as ChatLoaded;
    final updatedMessages = [
      ...currentState.messages,
      {'role': 'user', 'content': message},
    ];

    emit(
      ChatLoaded(
        conversationState: currentState.conversationState,
        messages: updatedMessages,
      ),
    );

    emit(ChatLoading());

    try {
      final response = await conversationRepository.step(
        currentState.conversationState,
        message,
      );

      final assistantMessage = response['message'] as String? ?? '';
      final newState =
          response['state'] as Map<String, dynamic>? ??
          currentState.conversationState;

      emit(
        ChatLoaded(
          conversationState: newState,
          messages: [
            ...updatedMessages,
            {'role': 'assistant', 'content': assistantMessage},
          ],
        ),
      );
    } catch (e) {
      emit(ChatError(e.toString()));
      emit(
        ChatLoaded(
          conversationState: currentState.conversationState,
          messages: updatedMessages,
        ),
      );
    }
  }

  Future<void> getRecommendations() async {
    if (state is! ChatLoaded) return;

    final currentState = state as ChatLoaded;
    emit(ChatLoading());

    try {
      final recommendations = await conversationRepository.getRecommendations(
        currentState.conversationState,
      );

      emit(
        ChatLoaded(
          conversationState: currentState.conversationState,
          messages: currentState.messages,
        ),
      );
    } catch (e) {
      emit(ChatError(e.toString()));
      emit(currentState);
    }
  }
}
