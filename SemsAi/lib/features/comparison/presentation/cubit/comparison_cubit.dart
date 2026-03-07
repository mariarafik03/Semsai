import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'comparison_state.dart';

class ComparisonCubit extends Cubit<ComparisonState> {
  ComparisonCubit() : super(const ComparisonState());

  
  bool toggle(CompoundUnit unit) {
    final current = List<CompoundUnit>.from(state.units);
    final idx = current.indexWhere((u) => u.id == unit.id);

    if (idx >= 0) {
      current.removeAt(idx);
      emit(state.copyWith(units: current));
      return true;
    }

    if (current.length >= 3) return false; 
    current.add(unit);
    emit(state.copyWith(units: current));
    return true;
  }

  void remove(String unitId) {
    final current = List<CompoundUnit>.from(state.units);
    current.removeWhere((u) => u.id == unitId);
    emit(state.copyWith(units: current));
  }

  void clear() => emit(const ComparisonState());
}
