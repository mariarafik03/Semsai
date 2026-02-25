import 'package:equatable/equatable.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';

abstract class FavoriteState extends Equatable {
  const FavoriteState();

  @override
  List<Object?> get props => [];
}

class FavoriteInitial extends FavoriteState {}

class FavoriteLoading extends FavoriteState {}

class FavoriteLoaded extends FavoriteState {
  final List<CompoundUnit> favorites;

  const FavoriteLoaded(this.favorites);

  bool isFavorite(String id) => favorites.any((u) => u.id == id);

  @override
  List<Object?> get props => [favorites];
}

class FavoriteError extends FavoriteState {
  final String message;

  const FavoriteError(this.message);

  @override
  List<Object?> get props => [message];
}
