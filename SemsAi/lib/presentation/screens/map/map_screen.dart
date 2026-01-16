import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/business_logic/map/map_cubit.dart';
import 'package:SemsAi/business_logic/map/map_state.dart';

class MapScreen extends StatelessWidget {
  const MapScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<MapCubit, MapState>(
      builder: (context, state) {
        return Scaffold(
          body: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.map, size: 64, color: Colors.grey),
                const SizedBox(height: 16),
                const Text(
                  'Map View',
                  style: TextStyle(fontSize: 18, color: Colors.grey),
                ),
                const SizedBox(height: 8),
                if (state is MapLoading)
                  const CircularProgressIndicator()
                else if (state is MapError)
                  Text('Error: ${state.message}')
                else
                  const Text('Upcoming Map'),
              ],
            ),
          ),
        );
      },
    );
  }
}
