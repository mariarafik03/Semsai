import 'package:SemsAi/data/models/developer.dart';
import 'package:SemsAi/data/services/data_service.dart';

abstract class DataRepository {
  Future<List<Developer>> getDevelopers();
}

class DataRepositoryImpl implements DataRepository {
  @override
  Future<List<Developer>> getDevelopers() async {
    try {
      return await DataService.getDevelopers();
    } catch (e) {
      print('Error getting developers: $e');
      return [];
    }
  }
}
