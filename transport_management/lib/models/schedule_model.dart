import 'route_model.dart';
import 'bus_model.dart';

class Schedule {
  final int id;
  final BusRoute route;
  final Bus bus;
  final Map<String, dynamic> driver;
  final DateTime date;
  final String departureTime;
  final String arrivalTime;
  final int totalSeats;
  final int availableSeats;

  // Nullable values coming from backend
  final int? currentPassengers;         
  final DateTime? lastPassengerUpdate;  
  final bool? isRunning;                
  final String? nextStopName;           
  final int? overflowLoad;              
  final int? maxLoad;                   

  Schedule({
    required this.id,
    required this.route,
    required this.bus,
    required this.driver,
    required this.date,
    required this.departureTime,
    required this.arrivalTime,
    required this.totalSeats,
    required this.availableSeats,
    this.currentPassengers,
    this.lastPassengerUpdate,
    this.isRunning,
    this.nextStopName,
    this.overflowLoad,
    this.maxLoad,
  });

  factory Schedule.fromJson(Map<String, dynamic> json) {
    // Safely parse last_passenger_update
    DateTime? lastUpdate;
    if (json['last_passenger_update'] != null &&
        json['last_passenger_update'] is String &&
        (json['last_passenger_update'] as String).isNotEmpty) {
      try {
        lastUpdate = DateTime.parse(json['last_passenger_update']);
      } catch (_) {
        lastUpdate = null;
      }
    }

    return Schedule(
      id: json['id'],
      route: BusRoute.fromJson(json['route']),
      bus: Bus.fromJson(json['bus']),
      driver: json['driver'] ?? const {},
      date: DateTime.parse(json['date']),
      departureTime: json['departure_time'],
      arrivalTime: json['arrival_time'],
      totalSeats: json['total_seats'],
      availableSeats: json['available_seats'],

      // Optional fields
      currentPassengers: json['current_passengers'],
      lastPassengerUpdate: lastUpdate,
      isRunning: json['is_running'],
      nextStopName: json['next_stop_name'],
      overflowLoad: json['overflow_load'],
      maxLoad: json['max_load'],
    );
  }

  // 👉 Always gives a safe, non-null number.
  // Uses backend live passengers if present else fallback.
  int get livePassengers {
    if (currentPassengers != null) {
      return currentPassengers!;
    }
    return totalSeats - availableSeats;
  }

  // Seats currently occupied
  int get occupiedSeats => livePassengers;

  // Percentage
  double get occupancyRate {
    if (totalSeats == 0) return 0;
    return (livePassengers / totalSeats) * 100;
  }

  // UI-friendly status
  String get seatStatus {
    if (totalSeats == 0) return 'No seat info';

    if (availableSeats > totalSeats * 0.5) {
      return 'Plenty of seats';
    } else if (availableSeats > 0) {
      return '$availableSeats seats left';
    } else {
      return 'Full';
    }
  }

  String get driverName => driver['name'] ?? 'Unknown';

  // Whether bus will overflow (based on backend prediction)
  bool get willOverflow {
    if (overflowLoad == null) return false;
    return overflowLoad! > totalSeats;
  }
}
