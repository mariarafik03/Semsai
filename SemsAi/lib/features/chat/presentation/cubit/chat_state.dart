import 'package:equatable/equatable.dart';

abstract class ChatState extends Equatable {
  const ChatState();

  @override
  List<Object?> get props => [];
}

class ChatInitial extends ChatState {}

class ChatLoading extends ChatState {}

class ChatLoaded extends ChatState {
  final String sessionId;
  final String phase;
  final bool done;
  final bool isTyping;
  final List<Map<String, String>> messages;
  final Map<String, dynamic>? results;

  const ChatLoaded({
    required this.sessionId,
    required this.phase,
    required this.messages,
    this.done = false,
    this.isTyping = false,
    this.results,
  });

  ChatLoaded copyWith({
    String? sessionId,
    String? phase,
    bool? done,
    bool? isTyping,
    List<Map<String, String>>? messages,
    Map<String, dynamic>? results,
  }) {
    return ChatLoaded(
      sessionId: sessionId ?? this.sessionId,
      phase: phase ?? this.phase,
      messages: messages ?? this.messages,
      done: done ?? this.done,
      isTyping: isTyping ?? this.isTyping,
      results: results ?? this.results,
    );
  }

  @override
  List<Object?> get props => [
    sessionId,
    phase,
    done,
    isTyping,
    messages,
    results,
  ];
}

class ChatError extends ChatState {
  final String message;

  const ChatError(this.message);

  @override
  List<Object?> get props => [message];
}
