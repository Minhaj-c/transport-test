import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import '../models/route_model.dart';
import '../models/schedule_model.dart';
import '../models/preinform_model.dart';

class ApiService {
  static String? _sessionCookie;

  static void setSessionCookie(String? cookie) {
    _sessionCookie = cookie;
    print('API Service - Session cookie set: ${cookie != null ? "Yes" : "No"}');
  }

  static Map<String, String> get _headers {
    final headers = Map<String, String>.from(ApiConfig.headers);
    if (_sessionCookie != null && _sessionCookie!.isNotEmpty) {
      headers['Cookie'] = _sessionCookie!;
      print('Using cookie: $_sessionCookie');
    } else {
      print('WARNING: No session cookie available!');
    }
    return headers;
  }

  // -----------------------------
  // Routes
  // -----------------------------
  static Future<List<BusRoute>> getRoutes() async {
    try {
      print('Fetching routes from: ${ApiConfig.routes}');
      final response = await http.get(
        Uri.parse(ApiConfig.routes),
        headers: _headers,
      );
      print('Routes response status: ${response.statusCode}');
      if (response.statusCode == 200) {
        final List data = json.decode(response.body);
        return data.map((json) => BusRoute.fromJson(json)).toList();
      } else {
        throw Exception('Failed to load routes: ${response.statusCode}');
      }
    } catch (e) {
      print('Error getting routes: $e');
      throw Exception('Error: $e');
    }
  }

  static Future<BusRoute> getRouteDetail(int id) async {
    try {
      final response = await http.get(
        Uri.parse(ApiConfig.routeDetail(id)),
        headers: _headers,
      );
      if (response.statusCode == 200) {
        return BusRoute.fromJson(json.decode(response.body));
      } else {
        throw Exception('Failed to load route details: ${response.statusCode}');
      }
    } catch (e) {
      print('Error getting route detail: $e');
      throw Exception('Error: $e');
    }
  }

  // -----------------------------
  // Schedules (public)
  // -----------------------------
  static Future<List<Schedule>> getSchedules({int? routeId, String? date}) async {
    try {
      var url = ApiConfig.schedules;
      final params = <String, String>{};
      if (routeId != null) params['route_id'] = routeId.toString();
      if (date != null) params['date'] = date;
      if (params.isNotEmpty) {
        url += '?${params.entries.map((e) => '${e.key}=${e.value}').join('&')}';
      }
      final response = await http.get(Uri.parse(url), headers: _headers);
      if (response.statusCode == 200) {
        final List data = json.decode(response.body);
        return data.map((json) => Schedule.fromJson(json)).toList();
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required. Please login again.');
      } else {
        throw Exception('Failed to load schedules: ${response.statusCode}');
      }
    } catch (e) {
      print('Error getting schedules: $e');
      throw Exception('Error: $e');
    }
  }

  // -----------------------------
  // Driver schedules
  // -----------------------------
  static Future<List<Schedule>> getDriverSchedules() async {
    try {
      print('Fetching driver schedules from: ${ApiConfig.driverSchedules}');
      final response = await http.get(
        Uri.parse(ApiConfig.driverSchedules),
        headers: _headers,
      );
      print('Driver schedules response status: ${response.statusCode}');
      if (response.statusCode == 200) {
        final List data = json.decode(response.body);
        return data.map((json) => Schedule.fromJson(json)).toList();
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else if (response.statusCode == 403) {
        throw Exception('Access denied. Driver role required.');
      } else {
        throw Exception('Server error: ${response.statusCode}');
      }
    } catch (e) {
      print('Error getting driver schedules: $e');
      rethrow;
    }
  }

  // -----------------------------
  // PreInforms
  // -----------------------------
  static Future<Map<String, dynamic>> createPreInform({
    required int routeId,
    required String dateOfTravel,
    required String desiredTime,
    required int boardingStopId,
    required int dropoffStopId,
    required int passengerCount,
  }) async {
    try {
      final body = {
        'route': routeId,
        'date_of_travel': dateOfTravel,
        'desired_time': desiredTime,
        'boarding_stop': boardingStopId,
        'dropoff_stop': dropoffStopId,
        'passenger_count': passengerCount,
      };
      final response = await http.post(
        Uri.parse(ApiConfig.preinforms),
        headers: _headers,
        body: json.encode(body),
      );
      if (response.statusCode == 201) {
        final decoded = json.decode(response.body) as Map<String, dynamic>;
        if (decoded['data'] is Map<String, dynamic>) {
          return decoded['data'] as Map<String, dynamic>;
        }
        return decoded;
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else {
        try {
          final decoded = json.decode(response.body);
          if (decoded is Map<String, dynamic>) {
            if (decoded['error'] is String) throw Exception(decoded['error']);
            if (decoded['detail'] is String) throw Exception(decoded['detail']);
            final parts = <String>[];
            decoded.forEach((key, value) {
              if (value is List) {
                parts.add('$key: ${value.join(", ")}');
              } else {
                parts.add('$key: $value');
              }
            });
            if (parts.isNotEmpty) throw Exception(parts.join(' | '));
          }
          throw Exception('Failed to create pre-inform (${response.statusCode})');
        } catch (inner) {
          throw Exception('Failed to create pre-inform (${response.statusCode})');
        }
      }
    } catch (e) {
      print('Error creating pre-inform: $e');
      rethrow;
    }
  }

  static Future<List<PreInform>> getMyPreInforms() async {
    try {
      final response = await http.get(
        Uri.parse(ApiConfig.myPreinforms),
        headers: _headers,
      );
      if (response.statusCode == 200) {
        final List data = json.decode(response.body);
        return data.map((json) => PreInform.fromJson(json)).toList();
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else {
        throw Exception('Failed to load pre-informs');
      }
    } catch (e) {
      print('Error getting pre-informs: $e');
      rethrow;
    }
  }

  static Future<void> cancelPreInform(int id) async {
    try {
      final response = await http.delete(
        Uri.parse(ApiConfig.cancelPreinform(id)),
        headers: _headers,
      );
      if (response.statusCode != 200) {
        throw Exception('Failed to cancel pre-inform');
      }
    } catch (e) {
      print('Error canceling pre-inform: $e');
      rethrow;
    }
  }

  // -----------------------------
  // Bus Location Update (Driver)
  // -----------------------------
  static Future<void> updateBusLocation({
    required int busId,
    required double latitude,
    required double longitude,
    int? scheduleId,
  }) async {
    try {
      final response = await http.post(
        Uri.parse(ApiConfig.updateBusLocation),
        headers: _headers,
        body: json.encode({
          'bus_id': busId,
          'latitude': latitude,
          'longitude': longitude,
          if (scheduleId != null) 'schedule_id': scheduleId,
        }),
      );
      if (response.statusCode == 200) {
        print('Location updated successfully');
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else if (response.statusCode == 403) {
        throw Exception('Only the assigned driver can update location');
      } else {
        throw Exception('Failed to update location (${response.statusCode})');
      }
    } catch (e) {
      print('Error updating location: $e');
      rethrow;
    }
  }

  // -----------------------------
  // Passenger Count Update
  // -----------------------------
  static Future<Map<String, dynamic>> updatePassengerCount({
    required int scheduleId,
    required int count,
  }) async {
    try {
      final response = await http.post(
        Uri.parse(ApiConfig.updatePassengerCount),
        headers: _headers,
        body: json.encode({
          'schedule_id': scheduleId,
          'count': count,
        }),
      );
      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else if (response.statusCode == 403) {
        throw Exception('Only the assigned driver can update passenger count');
      } else {
        final decoded = json.decode(response.body);
        if (decoded is Map<String, dynamic> && decoded['detail'] is String) {
          throw Exception(decoded['detail']);
        }
        throw Exception('Failed to update passenger count (${response.statusCode})');
      }
    } catch (e) {
      print('Error updating passenger count: $e');
      rethrow;
    }
  }

  // -----------------------------
  // Update Current Stop (Driver)
  // -----------------------------
  static Future<Map<String, dynamic>> updateCurrentStop({
    required int scheduleId,
    required int stopSequence,
  }) async {
    final response = await http.post(
      Uri.parse(ApiConfig.updateCurrentStop),
      headers: _headers,
      body: json.encode({
        'schedule_id': scheduleId,
        'stop_sequence': stopSequence,
      }),
    );
    if (response.statusCode == 200) {
      return json.decode(response.body) as Map<String, dynamic>;
    } else if (response.statusCode == 401) {
      throw Exception('Authentication required');
    } else if (response.statusCode == 403) {
      throw Exception('Only the assigned driver can update current stop');
    } else {
      throw Exception('Failed to update current stop (${response.statusCode})');
    }
  }

  // -----------------------------
  // Live Status
  // -----------------------------
  static Future<Map<String, dynamic>> getLiveStatusForStop({
    required int routeId,
    required int stopId,
    String? date,
  }) async {
    try {
      var url = ApiConfig.routeLiveStatus(routeId);
      final params = <String, String>{'stop_id': stopId.toString()};
      if (date != null) params['date'] = date;
      url += '?${params.entries.map((e) => '${e.key}=${e.value}').join('&')}';
      final response = await http.get(Uri.parse(url), headers: _headers);
      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else {
        throw Exception('Failed to load live status (${response.statusCode})');
      }
    } catch (e) {
      print('Error getting live status: $e');
      rethrow;
    }
  }

  // -----------------------------
  // Spare Bus APIs
  // -----------------------------
  static Future<Map<String, dynamic>> enterSpareMode() async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.baseUrl}/api/schedules/spare/enter/'),
        headers: _headers,
      );
      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      } else {
        final decoded = json.decode(response.body);
        throw Exception(decoded['error'] ?? 'Failed to enter spare mode');
      }
    } catch (e) {
      print('Error entering spare mode: $e');
      rethrow;
    }
  }

  static Future<Map<String, dynamic>> getSpareStatus() async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.baseUrl}/api/schedules/spare/status/'),
        headers: _headers,
      );
      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      }
      return {'has_spare': false};
    } catch (e) {
      print('Error getting spare status: $e');
      return {'has_spare': false};
    }
  }

  static Future<Map<String, dynamic>> reportDelayedArrival({
    required int scheduleId,
    required String estimatedArrival,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.baseUrl}/api/schedules/spare/delayed/'),
        headers: _headers,
        body: json.encode({
          'schedule_id': scheduleId,
          'estimated_arrival': estimatedArrival,
        }),
      );
      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      } else {
        final decoded = json.decode(response.body);
        throw Exception(decoded['error'] ?? 'Failed to report delay');
      }
    } catch (e) {
      print('Error reporting delay: $e');
      rethrow;
    }
  }

  static Future<Map<String, dynamic>> exitSpareMode() async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.baseUrl}/api/schedules/spare/exit/'),
        headers: _headers,
      );
      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      } else {
        final decoded = json.decode(response.body);
        throw Exception(decoded['error'] ?? 'Failed to exit spare mode');
      }
    } catch (e) {
      print('Error exiting spare mode: $e');
      rethrow;
    }
  }

  static Future<Map<String, dynamic>> completeSpareTripAndCheckHandoff({
    required int scheduleId,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ApiConfig.baseUrl}/api/schedules/spare/complete/'),
        headers: _headers,
        body: json.encode({'schedule_id': scheduleId}),
      );
      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      } else {
        final decoded = json.decode(response.body);
        throw Exception(decoded['error'] ?? 'Failed to complete spare trip');
      }
    } catch (e) {
      print('Error completing spare trip: $e');
      rethrow;
    }
  }

  // -----------------------------
  // Issue Ticket
  // -----------------------------
  static Future<Map<String, dynamic>> issueTicket({
    required int scheduleId,
    required int boardingStopId,
    required int dropoffStopId,
    required int passengerCount,
  }) async {
    try {
      final response = await http.post(
        Uri.parse(ApiConfig.issueTicket),
        headers: _headers,
        body: json.encode({
          'schedule_id': scheduleId,
          'boarding_stop_id': boardingStopId,
          'dropoff_stop_id': dropoffStopId,
          'passenger_count': passengerCount,
        }),
      );
      print('Issue ticket response: ${response.statusCode}');
      print('Issue ticket body: ${response.body}');
      if (response.statusCode == 201) {
        return json.decode(response.body) as Map<String, dynamic>;
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else if (response.statusCode == 403) {
        throw Exception('Only the assigned driver can issue tickets');
      } else {
        final decoded = json.decode(response.body);
        throw Exception(decoded['error'] ?? 'Failed to issue ticket');
      }
    } catch (e) {
      print('Error issuing ticket: $e');
      rethrow;
    }
  }

  // -----------------------------
  // Arrived At Stop
  // -----------------------------
  static Future<Map<String, dynamic>> arrivedAtStop({
    required int scheduleId,
    required int stopId,
  }) async {
    try {
      final response = await http.post(
        Uri.parse(ApiConfig.arrivedAtStop),
        headers: _headers,
        body: json.encode({
          'schedule_id': scheduleId,
          'stop_id': stopId,
        }),
      );
      print('Arrived at stop response: ${response.statusCode}');
      print('Arrived at stop body: ${response.body}');
      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else if (response.statusCode == 403) {
        throw Exception('Only the assigned driver can update stop');
      } else {
        final decoded = json.decode(response.body);
        throw Exception(decoded['error'] ?? 'Failed to update stop');
      }
    } catch (e) {
      print('Error arriving at stop: $e');
      rethrow;
    }
  }
}