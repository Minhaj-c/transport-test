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
  final bool? isRunning; // (may be null if backend doesn't send it)
  final String? nextStopNameLegacy; // legacy field if backend ever used it

  // Prediction / extra info (may be null)
  final int? overflowLoad;
  final int? maxLoad;

  // 🔥 NEW – live stop fields from backend ScheduleSerializer
  final int? currentStopSequence;
  final String? currentStopName;
  final int? nextStopSequence;
  final String? nextStopName;
  final bool isSpareTrip;

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
    this.nextStopNameLegacy,
    this.overflowLoad,
    this.maxLoad,
    this.currentStopSequence,
    this.currentStopName,
    this.nextStopSequence,
    this.nextStopName,
    this.isSpareTrip = false,
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
      id: json['id'] as int,
      route: BusRoute.fromJson(json['route'] as Map<String, dynamic>),
      bus: Bus.fromJson(json['bus'] as Map<String, dynamic>),
      driver: (json['driver'] as Map<String, dynamic>?) ?? const {},
      date: DateTime.parse(json['date'] as String),
      departureTime: json['departure_time'] as String,
      arrivalTime: json['arrival_time'] as String,
      totalSeats: json['total_seats'] as int,
      availableSeats: json['available_seats'] as int,

      // Optional fields
      currentPassengers: json['current_passengers'] as int?,
      lastPassengerUpdate: lastUpdate,
      isRunning: json['is_running'] as bool?,
      nextStopNameLegacy: json['next_stop_name'] as String?, // legacy

      overflowLoad: json['overflow_load'] as int?,
      maxLoad: json['max_load'] as int?,

      // 🔥 Live-stop fields (same keys as ScheduleSerializer)
      currentStopSequence: json['current_stop_sequence'] as int?,
      currentStopName: json['current_stop_name'] as String?,
      nextStopSequence: json['next_stop_sequence'] as int?,
      nextStopName: json['next_stop_name'] as String?,
      isSpareTrip: json['is_spare_trip'] as bool? ?? false,
    );
  }

  // 👉 Always gives a safe, non-null number.
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
