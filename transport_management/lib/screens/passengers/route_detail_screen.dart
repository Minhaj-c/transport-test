import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/route_model.dart';
import '../../models/schedule_model.dart';
import '../../providers/app_provider.dart';
import '../../widgets/loading_widget.dart';
import 'preinform_screen.dart';
import 'bus_tracking_screen.dart';
import 'package:intl/intl.dart';
import '../../services/api_service.dart'; // 🔥 NEW

class RouteDetailScreen extends StatefulWidget {
  final BusRoute route;

  const RouteDetailScreen({super.key, required this.route});

  @override
  State<RouteDetailScreen> createState() => _RouteDetailScreenState();
}

class _RouteDetailScreenState extends State<RouteDetailScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<AppProvider>(context, listen: false)
          .loadSchedules(routeId: widget.route.id);
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Route ${widget.route.number}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.map),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => BusTrackingScreen(route: widget.route),
                ),
              );
            },
            tooltip: 'Track on Map',
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          indicatorColor: Colors.white,
          tabs: const [
            Tab(text: 'Buses', icon: Icon(Icons.directions_bus)),
            Tab(text: 'Stops', icon: Icon(Icons.stop_circle)),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _SchedulesTab(route: widget.route),
          _StopsTab(route: widget.route),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => PreInformScreen(route: widget.route),
            ),
          );
        },
        icon: const Icon(Icons.add_alert),
        label: const Text('Pre-Inform'),
        backgroundColor: Colors.orange,
      ),
    );
  }
}

class _SchedulesTab extends StatelessWidget {
  final BusRoute route;

  const _SchedulesTab({required this.route});

  @override
  Widget build(BuildContext context) {
    final appProvider = Provider.of<AppProvider>(context);

    if (appProvider.isLoadingSchedules) {
      return const LoadingWidget(message: 'Loading buses...');
    }

    final schedules = appProvider.schedules
        .where((s) => s.route.id == route.id)
        .toList();

    if (schedules.isEmpty) {
      return const EmptyWidget(
        message: 'No buses available for this route',
        icon: Icons.directions_bus_filled,
      );
    }

    return RefreshIndicator(
      onRefresh: () => appProvider.loadSchedules(routeId: route.id),
      child: Column(
        children: [
          // Legend
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey[100],
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Bus Status Legend:',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: const [
                    _LegendItem(color: Colors.green, label: 'Empty'),
                    _LegendItem(color: Colors.orange, label: 'Filling'),
                    _LegendItem(color: Colors.red, label: 'Almost Full'),
                    _LegendItem(color: Colors.grey, label: 'Full'),
                  ],
                ),
              ],
            ),
          ),

          // 🔥 NEW: "Check crowd at my stop"
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                icon: const Icon(Icons.visibility),
                label: const Text('Check crowd at my stop'),
                onPressed: () {
                  _showStopPickerAndLiveStatus(context, route);
                },
              ),
            ),
          ),
          const SizedBox(height: 8),

          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: schedules.length,
              itemBuilder: (context, index) {
                final schedule = schedules[index];
                return _ScheduleCard(schedule: schedule, route: route);
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _LegendItem extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendItem({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 16,
          height: 16,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 12)),
      ],
    );
  }
}

class _ScheduleCard extends StatelessWidget {
  final Schedule schedule;
  final BusRoute route;

  const _ScheduleCard({required this.schedule, required this.route});

  Color _getOccupancyColor() {
    final occupancyRate = schedule.occupancyRate;
    if (schedule.availableSeats == 0) return Colors.grey;
    if (occupancyRate >= 80) return Colors.red;
    if (occupancyRate >= 50) return Colors.orange;
    return Colors.green;
  }

  String _getOccupancyStatus() {
    final occupancyRate = schedule.occupancyRate;
    if (schedule.availableSeats == 0) return 'FULL';
    if (occupancyRate >= 80) return 'ALMOST FULL';
    if (occupancyRate >= 50) return 'FILLING UP';
    return 'AVAILABLE';
  }

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MMM dd, yyyy');
    final statusColor = _getOccupancyColor();

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 3,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: statusColor, width: 2),
      ),
      child: InkWell(
        onTap: () {
          _showBusDetails(context);
        },
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Status Badge
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: statusColor,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.circle, color: Colors.white, size: 12),
                        const SizedBox(width: 6),
                        Text(
                          _getOccupancyStatus(),
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.grey[200],
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      schedule.bus.numberPlate,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Date
              Text(
                dateFormat.format(schedule.date),
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),

              // Timing
              Row(
                children: [
                  const Icon(Icons.schedule, size: 16),
                  const SizedBox(width: 8),
                  Text(
                    '${schedule.departureTime} → ${schedule.arrivalTime}',
                    style: const TextStyle(fontSize: 14),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              // Driver
              Row(
                children: [
                  const Icon(Icons.person, size: 16),
                  const SizedBox(width: 8),
                  Text(
                    'Driver: ${schedule.driverName}',
                    style: const TextStyle(fontSize: 14),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Seat Progress Bar
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        '${schedule.availableSeats} seats left',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: statusColor,
                          fontSize: 14,
                        ),
                      ),
                      Text(
                        '${schedule.occupiedSeats}/${schedule.totalSeats}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: Colors.grey,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: LinearProgressIndicator(
                      value: schedule.occupiedSeats / schedule.totalSeats,
                      backgroundColor: Colors.grey[200],
                      valueColor: AlwaysStoppedAnimation<Color>(statusColor),
                      minHeight: 12,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Tap to view details
              Center(
                child: Text(
                  'Tap to view details',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showBusDetails(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        minChildSize: 0.4,
        maxChildSize: 0.9,
        expand: false,
        builder: (context, scrollController) => SingleChildScrollView(
          controller: scrollController,
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              
              // Bus Number
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _getOccupancyColor().withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      Icons.directions_bus,
                      color: _getOccupancyColor(),
                      size: 32,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          schedule.bus.numberPlate,
                          style: const TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          'Route ${route.number}',
                          style: TextStyle(
                            fontSize: 16,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              
              // Status Card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: _getOccupancyColor().withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: _getOccupancyColor()),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.airline_seat_recline_normal, color: _getOccupancyColor()),
                    const SizedBox(width: 12),
                    Text(
                      '${schedule.availableSeats} / ${schedule.totalSeats} Seats Available',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: _getOccupancyColor(),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              
              // Details
              _DetailRow(
                icon: Icons.calendar_today,
                label: 'Date',
                value: DateFormat('EEEE, MMM dd, yyyy').format(schedule.date),
              ),
              _DetailRow(
                icon: Icons.access_time,
                label: 'Departure',
                value: schedule.departureTime,
              ),
              _DetailRow(
                icon: Icons.access_time_filled,
                label: 'Arrival',
                value: schedule.arrivalTime,
              ),
              _DetailRow(
                icon: Icons.person,
                label: 'Driver',
                value: schedule.driverName,
              ),
              _DetailRow(
                icon: Icons.straighten,
                label: 'Distance',
                value: route.distanceInfo,
              ),
              _DetailRow(
                icon: Icons.schedule,
                label: 'Duration',
                value: route.durationInfo,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.grey[100],
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, size: 20, color: Colors.grey[700]),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
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

class _StopsTab extends StatelessWidget {
  final BusRoute route;

  const _StopsTab({required this.route});

  @override
  Widget build(BuildContext context) {
    if (route.stops.isEmpty) {
      return const EmptyWidget(
        message: 'No stops information available',
        icon: Icons.stop_circle,
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: route.stops.length,
      itemBuilder: (context, index) {
        final stop = route.stops[index];
        final isFirst = index == 0;
        final isLast = index == route.stops.length - 1;

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Stop indicator
            Column(
              children: [
                Container(
                  width: 24,
                  height: 24,
                  decoration: BoxDecoration(
                    color: isFirst
                        ? Colors.green
                        : isLast
                            ? Colors.red
                            : Colors.blue,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 2),
                  ),
                  child: Center(
                    child: Text(
                      '${stop.sequence}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
                if (!isLast)
                  Container(
                    width: 2,
                    height: 40,
                    color: Colors.grey[300],
                  ),
              ],
            ),
            const SizedBox(width: 12),

            // Stop details
            Expanded(
              child: Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.grey[50],
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey[200]!),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      stop.name,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      stop.distanceInfo,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[600],
                      ),
                    ),
                    if (stop.isLimitedStop)
                      Container(
                        margin: const EdgeInsets.only(top: 4),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 6,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          color: Colors.orange[100],
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'Limited Stop',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: Colors.orange,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

/// 🔥 Stop picker + live status for users who didn't pre-inform
void _showStopPickerAndLiveStatus(BuildContext context, BusRoute route) async {
  if (route.stops.isEmpty) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('No stops available for this route'),
      ),
    );
    return;
  }

  int? selectedStopId;

  await showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (context) {
      return StatefulBuilder(
        builder: (context, setState) {
          return SafeArea(
            child: SizedBox(
              height: MediaQuery.of(context).size.height * 0.7,
              child: Column(
                children: [
                  const SizedBox(height: 8),
                  Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.grey[300],
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Choose your stop',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Expanded(
                    child: ListView.builder(
                      itemCount: route.stops.length,
                      itemBuilder: (context, index) {
                        final stop = route.stops[index];
                        final isSelected = selectedStopId == stop.id;
                        return ListTile(
                          title: Text(stop.name),
                          subtitle: Text(stop.distanceInfo),
                          leading: CircleAvatar(
                            child: Text('${stop.sequence}'),
                          ),
                          trailing: isSelected
                              ? const Icon(Icons.check, color: Colors.green)
                              : null,
                          onTap: () {
                            setState(() {
                              selectedStopId = stop.id;
                            });
                          },
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 8),
                  Padding(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 8),
                    child: SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: selectedStopId == null
                            ? null
                            : () {
                                Navigator.pop(context);
                              },
                        icon: const Icon(Icons.visibility),
                        label: const Text('Show live crowd'),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      );
    },
  );

  if (selectedStopId == null) return;

  try {
    final today = DateTime.now();
    final dateStr = DateFormat('yyyy-MM-dd').format(today);

    final data = await ApiService.getLiveStatusForStop(
      routeId: route.id,
      stopId: selectedStopId!,
      date: dateStr,
    );

    _showLiveStatusBottomSheet(context, data);
  } catch (e) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Failed to load live status: $e'),
        backgroundColor: Colors.red,
      ),
    );
  }
}

/// Same UI as in my_preinforms_screen.dart, duplicated here
void _showLiveStatusBottomSheet(
    BuildContext context, Map<String, dynamic> data) {
  final route = data['route'] as Map<String, dynamic>?;
  final stop = data['target_stop'] as Map<String, dynamic>?;
  final buses = (data['buses'] as List<dynamic>? ?? []);

  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (context) {
      return DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.7,
        minChildSize: 0.4,
        maxChildSize: 0.9,
        builder: (context, scrollController) {
          return SingleChildScrollView(
            controller: scrollController,
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.grey[300],
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Live bus status',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                if (route != null)
                  Text(
                    'Route ${route['number']}: ${route['origin']} → ${route['destination']}',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey[700],
                    ),
                  ),
                if (stop != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    'Your stop: ${stop['name'] ?? 'Stop #${stop['sequence']}'}',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey[700],
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                if (buses.isEmpty)
                  Center(
                    child: Column(
                      children: [
                        Icon(Icons.directions_bus_filled,
                            size: 48, color: Colors.grey[400]),
                        const SizedBox(height: 8),
                        const Text(
                          'No upcoming buses found for this stop.',
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  )
                else
                  Column(
                    children: buses.map<Widget>((raw) {
                      final bus = raw as Map<String, dynamic>;
                      final busNumber =
                          bus['bus_number'] as String? ?? 'Unknown bus';
                      final eta = bus['eta_minutes'] ?? 0;
                      final stopsAway = bus['stops_away'] ?? 0;
                      final capacity = (bus['capacity'] ?? 0) as int;
                      final predicted =
                          (bus['predicted_passengers_at_stop'] ?? 0) as int;
                      final available =
                          (bus['available_seats_at_stop'] ?? 0) as int;
                      final isSpare =
                          (bus['is_spare_trip'] ?? false) as bool;
                      final overflowLater =
                          (bus['will_overflow_later'] ?? false) as bool;

                      String statusText;
                      Color statusColor;

                      if (capacity <= 0) {
                        statusText = 'No seat data';
                        statusColor = Colors.grey;
                      } else {
                        final occ = predicted / capacity;
                        if (available <= 0) {
                          statusText = 'FULL';
                          statusColor = Colors.grey;
                        } else if (occ >= 0.8) {
                          statusText = 'ALMOST FULL';
                          statusColor = Colors.red;
                        } else if (occ >= 0.5) {
                          statusText = 'FILLING UP';
                          statusColor = Colors.orange;
                        } else {
                          statusText = 'COMFORTABLE';
                          statusColor = Colors.green;
                        }
                      }

                      String etaText;
                      if (stopsAway < 0) {
                        etaText = 'Already passed this stop';
                      } else if (eta == 0) {
                        etaText = 'At the stop now';
                      } else {
                        etaText = '~$eta min • $stopsAway stop(s) away';
                      }

                      return Card(
                        margin: const EdgeInsets.only(bottom: 12),
                        elevation: 2,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                          side: BorderSide(color: statusColor, width: 2),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              // Top row: bus + status
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Row(
                                    children: [
                                      Container(
                                        padding: const EdgeInsets.all(8),
                                        decoration: BoxDecoration(
                                          color: statusColor.withOpacity(0.1),
                                          borderRadius:
                                              BorderRadius.circular(8),
                                        ),
                                        child: Icon(
                                          isSpare
                                              ? Icons.local_taxi
                                              : Icons.directions_bus,
                                          color: statusColor,
                                        ),
                                      ),
                                      const SizedBox(width: 12),
                                      Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            busNumber,
                                            style: const TextStyle(
                                              fontSize: 16,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                          if (isSpare)
                                            Text(
                                              'Spare bus',
                                              style: TextStyle(
                                                fontSize: 12,
                                                color: Colors.blue[700],
                                              ),
                                            ),
                                        ],
                                      ),
                                    ],
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 10, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: statusColor,
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: Text(
                                      statusText,
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 12,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 12),
                              // ETA
                              Row(
                                children: [
                                  const Icon(Icons.access_time, size: 16),
                                  const SizedBox(width: 8),
                                  Text(
                                    etaText,
                                    style: const TextStyle(fontSize: 14),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              // seats
                              Row(
                                children: [
                                  const Icon(Icons.people, size: 16),
                                  const SizedBox(width: 8),
                                  Text(
                                    '$predicted / $capacity seats used • $available left',
                                    style: const TextStyle(fontSize: 14),
                                  ),
                                ],
                              ),
                              if (overflowLater) ...[
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    const Icon(Icons.warning,
                                        size: 16, color: Colors.red),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        'This bus may become overloaded further ahead.',
                                        style: const TextStyle(
                                          fontSize: 12,
                                          color: Colors.red,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ],
                          ),
                        ),
                      );
                    }).toList(),
                  ),
              ],
            ),
          );
        },
      );
    },
  );
}
