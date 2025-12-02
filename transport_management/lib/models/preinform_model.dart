class PreInform {
  final int id;
  final int userId;
  final String userName;
  final int routeId;
  final Map<String, dynamic>? routeDetails;
  final DateTime dateOfTravel;
  final String desiredTime;
  final int boardingStopId;
  final int? dropoffStopId;                        
  final Map<String, dynamic>? stopDetails;
  final Map<String, dynamic>? dropoffStopDetails;   
  final int passengerCount;
  final String status;
  final DateTime createdAt;

  PreInform({
     required this.id,
    required this.userId,
    required this.userName,
    required this.routeId,
    this.routeDetails,
    required this.dateOfTravel,
    required this.desiredTime,
    required this.boardingStopId,
    this.dropoffStopId,
    this.stopDetails,
    this.dropoffStopDetails,
    required this.passengerCount,
    required this.status,
    required this.createdAt,
  });

  factory PreInform.fromJson(Map<String, dynamic> json) {
    return PreInform(
      id: json['id'],
      userId: json['user'],
      userName: json['user_name'] ?? '',
      routeId: json['route'],
      routeDetails: json['route_details'],
      dateOfTravel: DateTime.parse(json['date_of_travel']),
      desiredTime: json['desired_time'],
      boardingStopId: json['boarding_stop'],
      dropoffStopId: json['dropoff_stop'],                 
      stopDetails: json['stop_details'],
      dropoffStopDetails: json['dropoff_stop_details'],    
      passengerCount: json['passenger_count'],
      status: json['status'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }


  String get routeName => routeDetails?['name'] ?? 'Route $routeId';
  String get boardingStopName =>
      stopDetails?['name'] ?? 'Stop $boardingStopId';
  String get dropoffStopName =>
      dropoffStopDetails?['name'] ??
      (dropoffStopId != null ? 'Stop $dropoffStopId' : 'Not set');

  String get statusText {
    switch (status) {
      case 'pending':
        return 'Pending';
      case 'noted':
        return 'Noted';
      case 'completed':
        return 'Completed';
      case 'cancelled':
        return 'Cancelled';
      default:
        return status;
    }
  }
}