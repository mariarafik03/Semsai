import 'package:SemsAi/features/auth/data/models/user_model.dart';
import 'package:SemsAi/features/auth/data/repo/auth_service.dart';
import 'package:SemsAi/core/shared_pref/shared_pref_helper.dart';

abstract class AuthRepository {
  Future<User?> login(String email, String password);
  Future<User?> register(User user);
  Future<void> logout();
  Future<bool> isLoggedIn();
  Future<void> saveUser(User user);
  Future<User?> getUser();
}

class AuthRepositoryImpl implements AuthRepository {
  @override
  Future<User?> login(String email, String password) async {
    try {
      final user = await AuthService.login(email, password);
      if (user != null) {
        await saveUser(user);
      }
      return user;
    } catch (e) {
      print('Login error: $e');
      return null;
    }
  }

  @override
  Future<User?> register(User user) async {
    try {
      final registeredUser = await AuthService.register(user);
      if (registeredUser != null) {
        await saveUser(registeredUser);
      }
      return registeredUser;
    } catch (e) {
      print('Register error: $e');
      return null;
    }
  }

  @override
  Future<void> logout() async {
    await SharedPrefHelper.clear();
  }

  @override
  Future<bool> isLoggedIn() async {
    return await SharedPrefHelper.isLoggedIn();
  }

  @override
  Future<void> saveUser(User user) async {
    await SharedPrefHelper.saveUser(user);
  }

  @override
  Future<User?> getUser() async {
    return await SharedPrefHelper.getUser();
  }
}
