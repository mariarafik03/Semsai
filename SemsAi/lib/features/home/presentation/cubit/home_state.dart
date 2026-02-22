import 'package:equatable/equatable.dart';

abstract class HomeState extends Equatable {
  final int bottomNavIndex;
  final String selectedCategory;

  const HomeState({
    required this.bottomNavIndex,
    required this.selectedCategory,
  });

  @override
  List<Object?> get props => [bottomNavIndex, selectedCategory];
}

class HomeInitial extends HomeState {
  const HomeInitial() : super(bottomNavIndex: 0, selectedCategory: 'All');
}

class HomeLoading extends HomeState {
  const HomeLoading({
    required super.bottomNavIndex,
    required super.selectedCategory,
  });
}

class HomeLoaded extends HomeState {
  const HomeLoaded({
    required super.bottomNavIndex,
    required super.selectedCategory,
  });
}

class HomeError extends HomeState {
  final String message;

  const HomeError({
    required super.bottomNavIndex,
    required super.selectedCategory,
    required this.message,
  });

  @override
  List<Object?> get props => [bottomNavIndex, selectedCategory, message];
}
