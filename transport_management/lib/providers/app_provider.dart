import 'package:flutter/material.dart';
import '../models/route_model.dart';
import '../models/schedule_model.dart';
import '../services/api_service.dart';

class AppProvider with ChangeNotifier {
  List<BusRoute> _routes = [];
  List<Schedule> _schedules = [];
  bool _isLoadingRoutes = false;
  bool _isLoadingSchedules = false;

  List<BusRoute> get routes => _routes;
  List<Schedule> get schedules => _schedules;
  bool get isLoadingRoutes => _isLoadingRoutes;
  bool get isLoadingSchedules => _isLoadingSchedules;

  // Load all routes
  Future<void> loadRoutes() async {
    _isLoadingRoutes = true;
    notifyListeners();

    try {
      _routes = await ApiService.getRoutes();
    } catch (e) {
      print('Error loading routes: $e');
    }

    _isLoadingRoutes = false;
    notifyListeners();
  }

  // 🔥 NEW: Load only routes that have schedules today
  Future<void> loadRoutesWithSchedules() async {
    _isLoadingRoutes = true;
    notifyListeners();

    try {
      // Get today's date in YYYY-MM-DD format
      final today = DateTime.now();
      final todayStr = '${today.year}-${today.month.toString().padLeft(2, '0')}-${today.day.toString().padLeft(2, '0')}';
      
      // Load all routes
      final allRoutes = await ApiService.getRoutes();
      
      // Load today's schedules
      final todaySchedules = await ApiService.getSchedules(date: todayStr);
      
      // Get unique route IDs that have schedules today
      final Set<int> routeIdsWithSchedules = {};
      for (var schedule in todaySchedules) {
        if (schedule.route.id != null) {
          routeIdsWithSchedules.add(schedule.route.id!);
        }
      }
      
      // Filter routes to only those with schedules today
      _routes = allRoutes
          .where((route) => routeIdsWithSchedules.contains(route.id))
          .toList();
          
    } catch (e) {
      print('Error loading routes with schedules: $e');
      _routes = [];
    }

    _isLoadingRoutes = false;
    notifyListeners();
  }

  // Load schedules
  Future<void> loadSchedules({int? routeId, String? date}) async {
    _isLoadingSchedules = true;
    notifyListeners();

    try {
      _schedules = await ApiService.getSchedules(
        routeId: routeId,
        date: date,
      );
    } catch (e) {
      print('Error loading schedules: $e');
    }

    _isLoadingSchedules = false;
    notifyListeners();
  }

  // Get route by ID
  BusRoute? getRouteById(int id) {
    try {
      return _routes.firstWhere((route) => route.id == id);
    } catch (e) {
      return null;
    }
  }
}