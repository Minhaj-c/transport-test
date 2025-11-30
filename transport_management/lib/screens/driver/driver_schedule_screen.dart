import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/schedule_model.dart';
import '../../services/api_service.dart';
import '../../services/location_service.dart';
import '../../widgets/loading_widget.dart';

class DriverScheduleScreen extends StatefulWidget {
  const DriverScheduleScreen({super.key});

  @override
  State<DriverScheduleScreen> createState() => DriverScheduleScreenState();
}

// 👇 Make the state class accessible globally so we can share state
class DriverScheduleScreenState extends State<DriverScheduleScreen> with AutomaticKeepAliveClientMixin {
  List<Schedule> _schedules = [];
  bool _isLoading = true;
  String? _error;
  Schedule? _activeSchedule;
  bool _isRunning = false;
  bool _isStarting = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _loadSchedules();
  }

  Future<void> _loadSchedules() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final schedules = await ApiService.getDriverSchedules();
      
      // 👇 Check if any schedule is currently running
      final now = DateTime.now();
      final todaySchedules = schedules.where((s) {
        return s.date.year == now.year &&
            s.date.month == now.month &&
            s.date.day == now.day;
      }).toList();

      // If we had an active schedule running, keep it
      if (_isRunning && _activeSchedule != null) {
        // Find the matching schedule from the fresh data
        final matchingSchedule = todaySchedules.firstWhere(
          (s) => s.id == _activeSchedule!.id,
          orElse: () => _activeSchedule!,
        );
        
        if (mounted) {
          setState(() {
            _schedules = schedules;
            _activeSchedule = matchingSchedule;
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _schedules = schedules;
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load schedules: ${e.toString()}';
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _startBus(Schedule schedule) async {
    setState(() => _isStarting = true);

    try {
      final position = await LocationService.getCurrentLocation();
      
      if (position == null) {
        throw Exception('Could not get location. Please enable GPS.');
      }

      await ApiService.updateBusLocation(
        busId: schedule.bus.id,
        latitude: position.latitude,
        longitude: position.longitude,
        scheduleId: schedule.id,
      );

      if (mounted) {
        setState(() {
          _activeSchedule = schedule;
          _isRunning = true;
          _isStarting = false;
        });

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Row(
              children: [
                Icon(Icons.check_circle, color: Colors.white),
                SizedBox(width: 12),
                Text('Bus started successfully!'),
              ],
            ),
            backgroundColor: Colors.green,
            duration: Duration(seconds: 2),
          ),
        );

        _startLocationTracking(schedule);
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isStarting = false);
        
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.error, color: Colors.white),
                const SizedBox(width: 12),
                Expanded(child: Text('Error: ${e.toString()}')),
              ],
            ),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 4),
            action: SnackBarAction(
              label: 'Retry',
              textColor: Colors.white,
              onPressed: () => _startBus(schedule),
            ),
          ),
        );
      }
    }
  }

  void _startLocationTracking(Schedule schedule) {
    if (!_isRunning || _activeSchedule?.id != schedule.id) return;

    Future.delayed(const Duration(seconds: 30), () async {
      if (!mounted || !_isRunning || _activeSchedule?.id != schedule.id) return;

      try {
        final position = await LocationService.getCurrentLocation();
        if (position != null && mounted) {
          await ApiService.updateBusLocation(
            busId: schedule.bus.id,
            latitude: position.latitude,
            longitude: position.longitude,
            scheduleId: schedule.id,
          );
          
          _startLocationTracking(schedule);
        }
      } catch (e) {
        if (mounted) _startLocationTracking(schedule);
      }
    });
  }

  void _stopBus() {
    if (mounted) {
      setState(() {
        _isRunning = false;
        _activeSchedule = null;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Row(
            children: [
              Icon(Icons.stop_circle, color: Colors.white),
              SizedBox(width: 12),
              Text('Bus stopped'),
            ],
          ),
          backgroundColor: Colors.orange,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);

    if (_isLoading && _schedules.isEmpty) {
      return const LoadingWidget(message: 'Loading your schedule...');
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 64, color: Colors.red),
              const SizedBox(height: 16),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 16),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: _loadSchedules,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadSchedules,
      child: Column(
        children: [
          if (_isRunning && _activeSchedule != null)
            _ActiveScheduleCard(
              schedule: _activeSchedule!,
              onStop: _stopBus,
            ),

          Expanded(
            child: _schedules.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.event_busy, size: 64, color: Colors.grey[400]),
                          const SizedBox(height: 16),
                          Text(
                            'No schedules assigned',
                            style: TextStyle(
                              fontSize: 18,
                              color: Colors.grey[600],
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Check back later for new assignments',
                            style: TextStyle(color: Colors.grey[500]),
                          ),
                        ],
                      ),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _schedules.length,
                    itemBuilder: (context, index) {
                      final schedule = _schedules[index];
                      final isActive = _activeSchedule?.id == schedule.id;
                      final now = DateTime.now();
                      final isToday = schedule.date.year == now.year &&
                          schedule.date.month == now.month &&
                          schedule.date.day == now.day;

                      return _ScheduleCard(
                        schedule: schedule,
                        isActive: isActive,
                        isToday: isToday,
                        onStart: () => _startBus(schedule),
                        isStarting: _isStarting,
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _isRunning = false;
    super.dispose();
  }
}

class _ActiveScheduleCard extends StatelessWidget {
  final Schedule schedule;
  final VoidCallback onStop;

  const _ActiveScheduleCard({
    required this.schedule,
    required this.onStop,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.green[400]!, Colors.green[600]!],
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.green.withOpacity(0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: const BoxDecoration(
                  color: Colors.white,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.directions_bus,
                  color: Colors.green,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Bus Running',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                    Text(
                      'Location tracking active',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.white70,
                      ),
                    ),
                  ],
                ),
              ),
              ElevatedButton.icon(
                onPressed: onStop,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                ),
                icon: const Icon(Icons.stop, size: 18),
                label: const Text('Stop'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              children: [
                Text(
                  'Route ${schedule.route.number}: ${schedule.route.name}',
                  style: const TextStyle(
                    fontSize: 14,
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Bus: ${schedule.bus.numberPlate}',
                  style: const TextStyle(
                    color: Colors.white70,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ScheduleCard extends StatelessWidget {
  final Schedule schedule;
  final bool isActive;
  final bool isToday;
  final VoidCallback onStart;
  final bool isStarting;

  const _ScheduleCard({
    required this.schedule,
    required this.isActive,
    required this.isToday,
    required this.onStart,
    required this.isStarting,
  });

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MMM dd, yyyy');

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: isToday ? 4 : 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: isToday
            ? BorderSide(color: Theme.of(context).primaryColor, width: 2)
            : BorderSide.none,
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  dateFormat.format(schedule.date),
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: isToday ? Theme.of(context).primaryColor : null,
                  ),
                ),
                if (isToday)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: Theme.of(context).primaryColor,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Text(
                      'TODAY',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
              ],
            ),
            const Divider(),

            Text(
              'Route ${schedule.route.number}',
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            Text(
              schedule.route.name,
              style: TextStyle(color: Colors.grey[700]),
            ),
            const SizedBox(height: 8),

            Row(
              children: [
                const Icon(Icons.trip_origin, size: 16, color: Colors.green),
                const SizedBox(width: 8),
                Expanded(child: Text(schedule.route.origin)),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(Icons.location_on, size: 16, color: Colors.red),
                const SizedBox(width: 8),
                Expanded(child: Text(schedule.route.destination)),
              ],
            ),
            const SizedBox(height: 12),

            Row(
              children: [
                const Icon(Icons.access_time, size: 16),
                const SizedBox(width: 8),
                Text(
                  '${schedule.departureTime} - ${schedule.arrivalTime}',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ],
            ),
            const SizedBox(height: 8),

            Row(
              children: [
                const Icon(Icons.directions_bus, size: 16),
                const SizedBox(width: 8),
                Text(
                  'Bus: ${schedule.bus.numberPlate}',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ],
            ),
            const SizedBox(height: 16),

            if (isToday && !isActive)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: isStarting ? null : onStart,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    disabledBackgroundColor: Colors.grey,
                  ),
                  icon: isStarting 
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation(Colors.white),
                          ),
                        )
                      : const Icon(Icons.play_arrow),
                  label: Text(isStarting ? 'Starting...' : 'Start Bus'),
                ),
              ),
          ],
        ),
      ),
    );
  }
}