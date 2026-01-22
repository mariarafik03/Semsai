import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/business_logic/favorite/favorite_state.dart';

class FavoriteCubit extends Cubit<FavoriteState> {
  FavoriteCubit() : super(FavoriteInitial());

  void loadFavorites() {
    emit(FavoriteLoading());
    try {
      // TODO: Still need to implement
      emit(const FavoriteLoaded([]));
    } catch (e) {
      emit(FavoriteError(e.toString()));
    }
  }

  void addFavorite(String id) {
    if (state is FavoriteLoaded) {
      final currentFavorites = (state as FavoriteLoaded).favoriteIds;
      if (!currentFavorites.contains(id)) {
        emit(FavoriteLoaded([...currentFavorites, id]));
      }
    }
  }

  void removeFavorite(String id) {
    if (state is FavoriteLoaded) {
      final currentFavorites = (state as FavoriteLoaded).favoriteIds;
      emit(FavoriteLoaded(currentFavorites.where((fav) => fav != id).toList()));
    }
  }
}
