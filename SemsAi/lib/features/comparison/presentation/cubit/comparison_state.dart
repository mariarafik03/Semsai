import 'package:equatable/equatable.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';

class ComparisonState extends Equatable {
  final List<CompoundUnit> units;

  const ComparisonState({this.units = const []});

  bool get canCompare => units.length >= 2;
  bool get isFull => units.length >= 3;
  int get count => units.length;

  bool isSelected(String unitId) => units.any((u) => u.id == unitId);

  ComparisonState copyWith({List<CompoundUnit>? units}) =>
      ComparisonState(units: units ?? this.units);

  @override
  List<Object?> get props => [units];
}
