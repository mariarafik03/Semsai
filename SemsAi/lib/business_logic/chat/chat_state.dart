import 'package:equatable/equatable.dart';

abstract class ChatState extends Equatable {
  const ChatState();

  @override
  List<Object?> get props => [];
}

class ChatInitial extends ChatState {}

class ChatLoading extends ChatState {}

class ChatLoaded extends ChatState {
  final Map<String, dynamic> conversationState;
  final List<Map<String, String>> messages;

  const ChatLoaded({required this.conversationState, required this.messages});

  @override
  List<Object?> get props => [conversationState, messages];
}

class ChatError extends ChatState {
  final String message;

  const ChatError(this.message);

  @override
  List<Object?> get props => [message];
}
