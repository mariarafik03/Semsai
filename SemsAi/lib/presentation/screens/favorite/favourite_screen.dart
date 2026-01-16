import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/business_logic/favorite/favorite_cubit.dart';
import 'package:SemsAi/business_logic/favorite/favorite_state.dart';

class FavouriteScreen extends StatelessWidget {
  const FavouriteScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<FavoriteCubit, FavoriteState>(
      builder: (context, state) {
        if (state is FavoriteLoading) {
          return const Center(child: CircularProgressIndicator());
        } else if (state is FavoriteLoaded) {
          if (state.favoriteIds.isEmpty) {
            return const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.favorite_border, size: 64, color: Colors.grey),
                  SizedBox(height: 16),
                  Text(
                    'No favorites yet',
                    style: TextStyle(fontSize: 18, color: Colors.grey),
                  ),
                ],
              ),
            );
          }
          return ListView.builder(
            itemCount: state.favoriteIds.length,
            itemBuilder: (context, index) {
              return ListTile(
                title: Text('Favorite ${state.favoriteIds[index]}'),
                trailing: IconButton(
                  icon: const Icon(Icons.delete),
                  onPressed: () {
                    context.read<FavoriteCubit>().removeFavorite(
                      state.favoriteIds[index],
                    );
                  },
                ),
              );
            },
          );
        } else if (state is FavoriteError) {
          return Center(child: Text('Error: ${state.message}'));
        }
        return const Center(child: Text('No favorites'));
      },
    );
  }
}
