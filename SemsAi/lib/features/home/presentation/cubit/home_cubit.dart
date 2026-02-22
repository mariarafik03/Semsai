import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/features/home/presentation/cubit/home_state.dart';

class HomeCubit extends Cubit<HomeState> {
  HomeCubit() : super(const HomeInitial());

  void changeBottomNavIndex(int index) {
    emit(
      HomeLoaded(
        bottomNavIndex: index,
        selectedCategory: state.selectedCategory,
      ),
    );
  }

  void changeCategory(String category) {
    emit(
      HomeLoaded(
        bottomNavIndex: state.bottomNavIndex,
        selectedCategory: category,
      ),
    );
  }

  void loadData() {
    emit(
      HomeLoading(
        bottomNavIndex: state.bottomNavIndex,
        selectedCategory: state.selectedCategory,
      ),
    );
    Future.delayed(Duration(milliseconds: 500), () {
      emit(
        HomeLoaded(
          bottomNavIndex: state.bottomNavIndex,
          selectedCategory: state.selectedCategory,
        ),
      );
    });
  }
}
