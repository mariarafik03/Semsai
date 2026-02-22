import 'package:flutter/material.dart';
import 'package:SemsAi/core/routing/app_routes.dart';
import 'package:SemsAi/features/splash/presentation/screens/splash_screen.dart';
import 'package:SemsAi/features/home/presentation/screens/home_screen.dart';
import 'package:SemsAi/features/explore/presentation/screens/explore_screen.dart';
import 'package:SemsAi/features/auth/presentation/screens/login_screen.dart';
import 'package:SemsAi/features/auth/presentation/screens/register_screen.dart';
import 'package:SemsAi/features/auth/presentation/screens/forgot_password_screen.dart';

class AppRouter {
  Route? generateRoute(RouteSettings settings) {
    switch (settings.name) {
      case AppRoutes.splash:
        return MaterialPageRoute(
          builder: (_) => SplashScreen(nextScreen: LoginScreen()),
        );
      case AppRoutes.home:
        return MaterialPageRoute(builder: (_) => const HomeScreen());
      case AppRoutes.explore:
        return MaterialPageRoute(builder: (_) => const ExploreScreen());
      case AppRoutes.register:
        return MaterialPageRoute(builder: (_) => const RegisterScreen());
      case AppRoutes.login:
        return MaterialPageRoute(builder: (_) => const LoginScreen());
      case AppRoutes.forgotPassword:
        return MaterialPageRoute(builder: (_) => const ForgotPasswordScreen());
      default:
        return MaterialPageRoute(
          builder: (_) => Scaffold(
            body: Center(child: Text('No route defined for ${settings.name}')),
          ),
        );
    }
  }
}
