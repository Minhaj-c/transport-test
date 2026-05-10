import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/user_model.dart';
import '../services/auth_service.dart';

// Keys for bus running state (same as driver_schedule_screen.dart)
const String _kIsRunning     = 'bus_is_running';
const String _kActiveSchedId = 'bus_active_schedule_id';

class AuthProvider with ChangeNotifier {
  User? _user;
  bool _isLoading = true;

  User? get user => _user;
  bool get isLoggedIn => _user != null;
  bool get isLoading => _isLoading;
  bool get isPassenger => _user?.isPassenger ?? false;
  bool get isDriver => _user?.isDriver ?? false;

  AuthProvider() {
    _loadUser();
  }

  Future<void> _loadUser() async {
    _isLoading = true;
    notifyListeners();

    _user = await AuthService.getStoredUser();

    _isLoading = false;
    notifyListeners();
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final result = await AuthService.login(
      email: email,
      password: password,
    );

    if (result['success']) {
      _user = result['user'];
      notifyListeners();
    }

    return result;
  }

  Future<Map<String, dynamic>> signup({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required String role,
  }) async {
    final result = await AuthService.signup(
      email: email,
      password: password,
      firstName: firstName,
      lastName: lastName,
      role: role,
    );

    return result;
  }

  Future<void> logout() async {
    // ✅ Clear bus running state on logout
    // This ensures when driver logs back in, bus is not shown as running
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_kIsRunning);
      await prefs.remove(_kActiveSchedId);
    } catch (e) {
      print('Error clearing bus state on logout: $e');
    }

    await AuthService.logout();
    _user = null;
    notifyListeners();
  }
}