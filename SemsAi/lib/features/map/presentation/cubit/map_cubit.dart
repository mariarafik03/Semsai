import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/features/map/presentation/cubit/map_state.dart';

class MapCubit extends Cubit<MapState> {
  MapCubit() : super(MapInitial());

  void loadMapData() {
    emit(MapLoading());
    try {
      // TODO: Still need to implement
      emit(const MapLoaded());
    } catch (e) {
      emit(MapError(e.toString()));
    }
  }

  void updateLocation(Map<String, dynamic> locationData) {
    emit(MapLoaded(locationData: locationData));
  }
}
