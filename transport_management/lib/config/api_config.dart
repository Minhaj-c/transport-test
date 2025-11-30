class ApiConfig {
  // CHANGE THIS TO YOUR COMPUTER'S IP ADDRESS
  // Find your IP: 
  // - Windows: ipconfig (look for IPv4)
  // - Mac/Linux: ifconfig (look for inet)
  static const String baseUrl = 'http://172.17.29.81:8000';
  
  // API Endpoints
  static const String signup = '$baseUrl/api/signup/';
  static const String login = '$baseUrl/api/login/';
  static const String logout = '$baseUrl/api/logout/';
  static const String profile = '$baseUrl/api/profile/';
  
  // Routes
  static const String routes = '$baseUrl/api/routes/';
  static String routeDetail(int id) => '$baseUrl/api/routes/$id/';
  static String routeStops(int id) => '$baseUrl/api/routes/$id/stops/';
  
  // Schedules
  static const String schedules = '$baseUrl/api/schedules/';
  static const String driverSchedules = '$baseUrl/api/schedules/driver/';
  static const String nearbyBuses = '$baseUrl/api/buses/nearby/';
  static const String updateBusLocation = '$baseUrl/api/buses/update-location/';
  static const String updatePassengerCount = '$baseUrl/api/schedules/passenger-count/';  // ✅ FIXED
  static String busDetails(int id) => '$baseUrl/api/buses/$id/';
  
  // PreInforms
  static const String preinforms = '$baseUrl/api/preinforms/';
  static const String myPreinforms = '$baseUrl/api/preinforms/my/';
  static String cancelPreinform(int id) => '$baseUrl/api/preinforms/$id/cancel/';
  
  // Demand Alerts
  static const String demandAlerts = '$baseUrl/api/demand-alerts/';
  static const String activeDemandAlerts = '$baseUrl/api/demand-alerts/active/';
  
  // Headers
  static Map<String, String> get headers => {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
}