import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/business_logic/auth/auth_cubit.dart';
import 'package:SemsAi/business_logic/home/home_cubit.dart';
import 'package:SemsAi/business_logic/favorite/favorite_cubit.dart';
import 'package:SemsAi/business_logic/chat/chat_cubit.dart';
import 'package:SemsAi/business_logic/map/map_cubit.dart';
import 'package:SemsAi/data/repositories/auth_repository.dart';
import 'package:SemsAi/data/repositories/conversation_repository.dart';
import 'package:SemsAi/presentation/routes/app_routes.dart';
import 'package:SemsAi/core/strings.dart';

void main() {
  runApp(MyApp(appRouter: AppRoutes()));
}

class MyApp extends StatelessWidget {
  final AppRoutes appRouter;
  const MyApp({super.key, required this.appRouter});

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider<AuthCubit>(
          create: (context) =>
              AuthCubit(authRepository: AuthRepositoryImpl())
                ..checkAuthStatus(),
        ),
        BlocProvider<HomeCubit>(create: (context) => HomeCubit()),
        BlocProvider<FavoriteCubit>(
          create: (context) => FavoriteCubit()..loadFavorites(),
        ),
        BlocProvider<ChatCubit>(
          create: (context) =>
              ChatCubit(conversationRepository: ConversationRepositoryImpl()),
        ),
        BlocProvider<MapCubit>(create: (context) => MapCubit()),
      ],
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'Sems AI',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        ),
        initialRoute: AppStrings.splashRoute,
        onGenerateRoute: appRouter.generateRoute,
      ),
    );
  }
}
