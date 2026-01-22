import 'package:flutter/material.dart';
import 'package:SemsAi/core/strings.dart';
import 'package:SemsAi/presentation/screens/splash/splash_screen.dart';
import 'package:SemsAi/presentation/screens/home/home_screen.dart';
import 'package:SemsAi/presentation/screens/map/map_screen.dart';
import 'package:SemsAi/presentation/screens/auth/login_screen.dart';
import 'package:SemsAi/presentation/screens/auth/register_screen.dart';

class AppRoutes {
  Route? generateRoute(RouteSettings settings) {
    switch (settings.name) {
      case AppStrings.splashRoute:
        return MaterialPageRoute(builder: (_) => const SplashScreen());
      case AppStrings.homeRoute:
        return MaterialPageRoute(builder: (_) => const HomeScreen());
      case AppStrings.mapRoute:
        return MaterialPageRoute(builder: (_) => const MapScreen());
      case AppStrings.register:
        return MaterialPageRoute(builder: (_) => const RegisterScreen());
      case AppStrings.login:
        return MaterialPageRoute(builder: (_) => const LoginScreen());
    }
    return null;
  }
}
