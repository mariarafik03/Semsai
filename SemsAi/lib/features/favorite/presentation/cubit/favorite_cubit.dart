import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/core/shared_pref/shared_pref_helper.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/favorite/presentation/cubit/favorite_state.dart';

class FavoriteCubit extends Cubit<FavoriteState> {
  FavoriteCubit() : super(FavoriteInitial());

  Future<void> loadFavorites() async {
    emit(FavoriteLoading());
    try {
      final favs = await SharedPrefHelper.getFavorites();
      emit(FavoriteLoaded(favs));
    } catch (e) {
      emit(FavoriteError(e.toString()));
    }
  }

  bool isFavorite(String id) {
    if (state is FavoriteLoaded) {
      return (state as FavoriteLoaded).isFavorite(id);
    }
    return false;
  }

  Future<void> toggleFavorite(CompoundUnit unit) async {
    if (state is FavoriteLoaded) {
      final current = List<CompoundUnit>.from(
        (state as FavoriteLoaded).favorites,
      );
      final exists = current.any((u) => u.id == unit.id);
      if (exists) {
        current.removeWhere((u) => u.id == unit.id);
      } else {
        current.insert(0, unit);
      }
      emit(FavoriteLoaded(current));
      await SharedPrefHelper.saveFavorites(current);
    }
  }

  Future<void> removeFavorite(String id) async {
    if (state is FavoriteLoaded) {
      final current = List<CompoundUnit>.from(
        (state as FavoriteLoaded).favorites,
      );
      current.removeWhere((u) => u.id == id);
      emit(FavoriteLoaded(current));
      await SharedPrefHelper.saveFavorites(current);
    }
  }
}
