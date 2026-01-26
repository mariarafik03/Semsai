import 'package:SemsAi/data/models/user.dart';
import 'package:SemsAi/data/services/auth_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

abstract class AuthRepository {
  Future<User?> login(String email, String password);
  Future<User?> register(User user);
  Future<void> logout();
  Future<bool> isLoggedIn();
  Future<void> saveUser(User user);
  Future<User?> getUser();
}

class AuthRepositoryImpl implements AuthRepository {
  static const String _keyUserId = 'user_id';
  static const String _keyUserName = 'user_name';
  static const String _keyUserEmail = 'user_email';
  static const String _keyIsLoggedIn = 'is_logged_in';

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
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
  }

  @override
  Future<bool> isLoggedIn() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyIsLoggedIn) ?? false;
  }

  @override
  Future<void> saveUser(User user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyUserId, user.id ?? '');
    await prefs.setString(_keyUserName, user.name);
    await prefs.setString(_keyUserEmail, user.email);
    await prefs.setBool(_keyIsLoggedIn, true);
  }

  @override
  Future<User?> getUser() async {
    final prefs = await SharedPreferences.getInstance();
    final isLoggedIn = prefs.getBool(_keyIsLoggedIn) ?? false;

    if (!isLoggedIn) return null;

    final id = prefs.getString(_keyUserId);
    final name = prefs.getString(_keyUserName);
    final email = prefs.getString(_keyUserEmail);

    if (name == null || email == null) return null;

    return User(
      id: id,
      name: name,
      email: email,
      pass: '', 
    );
  }
}
