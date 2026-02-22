import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/features/auth/presentation/cubit/auth_cubit.dart';
import 'package:SemsAi/features/home/presentation/cubit/home_cubit.dart';
import 'package:SemsAi/features/favorite/presentation/cubit/favorite_cubit.dart';
import 'package:SemsAi/features/chat/presentation/cubit/chat_cubit.dart';
import 'package:SemsAi/features/map/presentation/cubit/map_cubit.dart';
import 'package:SemsAi/features/auth/data/repo/auth_repository.dart';
import 'package:SemsAi/features/chat/data/repo/conversation_repository.dart';
import 'package:SemsAi/core/routing/app_router.dart';
import 'package:SemsAi/core/routing/app_routes.dart';

void main() {
  runApp(MyApp(appRouter: AppRouter()));
}

class MyApp extends StatelessWidget {
  final AppRouter appRouter;
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
        initialRoute: AppRoutes.splash,
        onGenerateRoute: appRouter.generateRoute,
      ),
    );
  }
}
