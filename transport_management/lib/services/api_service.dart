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
      print('Routes response body: ${response.body}');

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

      print('Route detail response: ${response.statusCode}');

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

      print('Fetching schedules from: $url');
      print('Headers: $_headers');

      final response = await http.get(
        Uri.parse(url),
        headers: _headers,
      );

      print('Schedules response status: ${response.statusCode}');
      print('Schedules response body: ${response.body}');

      if (response.statusCode == 200) {
        final List data = json.decode(response.body);
        print('Found ${data.length} schedules');
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
      print('Headers: $_headers');

      final response = await http.get(
        Uri.parse(ApiConfig.driverSchedules),
        headers: _headers,
      );

      print('Driver schedules response status: ${response.statusCode}');
      print('Driver schedules response body: ${response.body}');

      if (response.statusCode == 200) {
        final List data = json.decode(response.body);
        print('Found ${data.length} driver schedules');
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
      print('Creating pre-inform...');
      print('Headers: $_headers');

      final body = {
        'route': routeId,
        'date_of_travel': dateOfTravel,
        'desired_time': desiredTime,
        'boarding_stop': boardingStopId,
        'dropoff_stop': dropoffStopId,   
        'passenger_count': passengerCount,
      };

      print('Pre-inform data: $body');

      final response = await http.post(
        Uri.parse(ApiConfig.preinforms),
        headers: _headers,
        body: json.encode(body),
      );

      print('Create pre-inform response: ${response.statusCode}');
      print('Create pre-inform body: ${response.body}');

      if (response.statusCode == 201) {
        final decoded = json.decode(response.body) as Map<String, dynamic>;
        // your backend wraps it as {success, message, data}
        if (decoded['data'] is Map<String, dynamic>) {
          return decoded['data'] as Map<String, dynamic>;
        }
        return decoded;
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else {
        // ... your existing error parsing stays the same
        try {
          final decoded = json.decode(response.body);
          if (decoded is Map<String, dynamic>) {
            if (decoded['error'] is String) {
              throw Exception(decoded['error']);
            }
            if (decoded['detail'] is String) {
              throw Exception(decoded['detail']);
            }
            final parts = <String>[];
            decoded.forEach((key, value) {
              if (value is List) {
                parts.add('$key: ${value.join(", ")}');
              } else {
                parts.add('$key: $value');
              }
            });
            if (parts.isNotEmpty) {
              throw Exception(parts.join(' | '));
            }
          }
          throw Exception(
              'Failed to create pre-inform (${response.statusCode})');
        } catch (inner) {
          print('Error parsing pre-inform error body: $inner');
          throw Exception(
              'Failed to create pre-inform (${response.statusCode})');
        }
      }
    } catch (e) {
      print('Error creating pre-inform: $e');
      rethrow;
    }
  }

  static Future<List<PreInform>> getMyPreInforms() async {
    try {
      print('Fetching my pre-informs...');
      print('Headers: $_headers');

      final response = await http.get(
        Uri.parse(ApiConfig.myPreinforms),
        headers: _headers,
      );

      print('My pre-informs response: ${response.statusCode}');
      print('My pre-informs body: ${response.body}');

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
      print('Updating bus location...');
      print('Bus ID: $busId, Lat: $latitude, Lng: $longitude');

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

      print('Update location response: ${response.statusCode}');
      print('Update location body: ${response.body}');

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
  // 🔥 PASSENGER COUNT UPDATE - ENHANCED DEBUG VERSION
  // -----------------------------
  static Future<Map<String, dynamic>> updatePassengerCount({
    required int scheduleId,
    required int count,
  }) async {
    print('═══════════════════════════════════════════════════════════');
    print('🚨 updatePassengerCount CALLED');
    print('═══════════════════════════════════════════════════════════');
    print('📍 Function entry point reached');
    print('📊 Parameters:');
    print('   - scheduleId: $scheduleId');
    print('   - count: $count');
    print('🌐 Target URL: ${ApiConfig.updatePassengerCount}');
    print('🍪 Session cookie exists: ${_sessionCookie != null}');
    print('🍪 Cookie value: $_sessionCookie');
    
    try {
      final requestBody = {
        'schedule_id': scheduleId,
        'count': count,
      };
      
      print('📦 Request body: ${json.encode(requestBody)}');
      print('📋 Headers: $_headers');
      print('⏱️  About to send HTTP POST...');
      
      final beforeRequest = DateTime.now();
      
      final response = await http.post(
        Uri.parse(ApiConfig.updatePassengerCount),
        headers: _headers,
        body: json.encode(requestBody),
      );
      
      final afterRequest = DateTime.now();
      final duration = afterRequest.difference(beforeRequest).inMilliseconds;
      
      print('⏱️  Request completed in ${duration}ms');
      print('📥 Response received:');
      print('   - Status code: ${response.statusCode}');
      print('   - Body: ${response.body}');
      print('   - Headers: ${response.headers}');

      if (response.statusCode == 200) {
        print('✅ SUCCESS - Passenger count updated');
        final decoded = json.decode(response.body) as Map<String, dynamic>;
        print('📊 Decoded response: $decoded');
        print('═══════════════════════════════════════════════════════════');
        return decoded;
      } else if (response.statusCode == 401) {
        print('❌ ERROR 401 - Authentication required');
        print('═══════════════════════════════════════════════════════════');
        throw Exception('Authentication required');
      } else if (response.statusCode == 403) {
        print('❌ ERROR 403 - Permission denied');
        print('═══════════════════════════════════════════════════════════');
        throw Exception('Only the assigned driver can update passenger count');
      } else {
        print('❌ ERROR ${response.statusCode} - Server error');
        try {
          final decoded = json.decode(response.body);
          if (decoded is Map<String, dynamic> && decoded['detail'] is String) {
            print('Server message: ${decoded['detail']}');
            print('═══════════════════════════════════════════════════════════');
            throw Exception(decoded['detail']);
          }
        } catch (_) {
          // ignore parse error
        }
        print('═══════════════════════════════════════════════════════════');
        throw Exception(
          'Failed to update passenger count (${response.statusCode})',
        );
      }
    } catch (e, stackTrace) {
      print('💥 EXCEPTION in updatePassengerCount:');
      print('Error: $e');
      print('Stack trace:');
      print(stackTrace);
      print('═══════════════════════════════════════════════════════════');
      rethrow;
    }
  }

  // -----------------------------
// 🔥 NEW: Update current stop (Driver)
// -----------------------------
static Future<Map<String, dynamic>> updateCurrentStop({
  required int scheduleId,
  required int stopSequence,
}) async {
  print('🚏 updateCurrentStop CALLED');
  print('   scheduleId: $scheduleId');
  print('   stopSequence: $stopSequence');
  print('   URL: ${ApiConfig.updateCurrentStop}');
  print('   Headers: $_headers');

  final body = json.encode({
    'schedule_id': scheduleId,
    'stop_sequence': stopSequence,
  });

  final response = await http.post(
    Uri.parse(ApiConfig.updateCurrentStop),
    headers: _headers,
    body: body,
  );

  print('🚏 updateCurrentStop status: ${response.statusCode}');
  print('🚏 updateCurrentStop body: ${response.body}');

  if (response.statusCode == 200) {
    return json.decode(response.body) as Map<String, dynamic>;
  } else if (response.statusCode == 401) {
    throw Exception('Authentication required');
  } else if (response.statusCode == 403) {
    throw Exception('Only the assigned driver can update current stop');
  } else {
    throw Exception(
      'Failed to update current stop (${response.statusCode})',
    );
  }
}



  // -----------------------------
  // Passenger Live Status
  // -----------------------------
  static Future<Map<String, dynamic>> getLiveStatusForStop({
    required int routeId,
    required int stopId,
    String? date, // yyyy-MM-dd
  }) async {
    try {
      var url = ApiConfig.routeLiveStatus(routeId);
      final params = <String, String>{
        'stop_id': stopId.toString(),
      };
      if (date != null) {
        params['date'] = date;
      }

      if (params.isNotEmpty) {
        url += '?${params.entries.map((e) => '${e.key}=${e.value}').join('&')}';
      }

      print('🔍 Fetching live status from: $url');
      print('Headers: $_headers');

      final response = await http.get(
        Uri.parse(url),
        headers: _headers,
      );

      print('Live status response: ${response.statusCode}');
      print('Live status body: ${response.body}');

      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      } else if (response.statusCode == 401) {
        throw Exception('Authentication required');
      } else {
        throw Exception(
          'Failed to load live status (${response.statusCode})',
        );
      }
    } catch (e) {
      print('❌ Error getting live status: $e');
      rethrow;
    }
  }



}