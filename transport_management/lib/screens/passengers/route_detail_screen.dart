import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import 'dart:async';

import '../../models/route_model.dart';
import '../../models/schedule_model.dart';
import '../../providers/app_provider.dart';
import '../../widgets/loading_widget.dart';
import 'preinform_screen.dart';
import 'bus_tracking_screen.dart';
import '../../services/api_service.dart';

class RouteDetailScreen extends StatefulWidget {
  final BusRoute route;
  const RouteDetailScreen({super.key, required this.route});

  @override
  State<RouteDetailScreen> createState() => _RouteDetailScreenState();
}

class _RouteDetailScreenState extends State<RouteDetailScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isRefreshing = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _refreshData();
    });
  }

  Future<void> _refreshData() async {
    setState(() => _isRefreshing = true);
    await Provider.of<AppProvider>(context, listen: false)
        .loadSchedules(routeId: widget.route.id);
    setState(() => _isRefreshing = false);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Color _withOpacity(Color color, double opacity) {
    return color.withAlpha((color.alpha * opacity).round());
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = Theme.of(context).primaryColor;
    
    return Scaffold(
      body: NestedScrollView(
        headerSliverBuilder: (context, innerBoxIsScrolled) {
          return [
            SliverAppBar(
              expandedHeight: 180,
              collapsedHeight: kToolbarHeight,
              floating: true,
              pinned: true,
              snap: false,
              flexibleSpace: FlexibleSpaceBar(
                title: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.black.withAlpha(128),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    'Route ${widget.route.number}',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                ),
                background: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        _withOpacity(primaryColor, 0.9),
                        _withOpacity(primaryColor, 0.7),
                      ],
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 16, left: 16, right: 16),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.end,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: Colors.white.withAlpha(51),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(Icons.directions_bus, color: Colors.white),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '${widget.route.origin} → ${widget.route.destination}',
                                    style: const TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w500,
                                      color: Colors.white,
                                    ),
                                    maxLines: 2,
                                  ),
                                  const SizedBox(height: 4),
                                  Row(
                                    children: [
                                      Icon(Icons.access_time, size: 12, color: Colors.white.withAlpha(204)),
                                      const SizedBox(width: 4),
                                      Text(
                                        widget.route.durationInfo,
                                        style: TextStyle(
                                          fontSize: 11,
                                          color: Colors.white.withAlpha(204),
                                        ),
                                      ),
                                      const SizedBox(width: 12),
                                      Icon(Icons.straighten, size: 12, color: Colors.white.withAlpha(204)),
                                      const SizedBox(width: 4),
                                      Text(
                                        widget.route.distanceInfo,
                                        style: TextStyle(
                                          fontSize: 11,
                                          color: Colors.white.withAlpha(204),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              actions: [
                IconButton(
                  icon: Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Colors.white.withAlpha(51),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.map, size: 20, color: Colors.white),
                  ),
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
              bottom: PreferredSize(
                preferredSize: const Size.fromHeight(48),
                child: Container(
                  color: primaryColor,
                  child: TabBar(
                    controller: _tabController,
                    labelColor: Colors.white,
                    unselectedLabelColor: Colors.white.withAlpha(178),
                    indicatorColor: Colors.white,
                    indicatorWeight: 3,
                    indicatorSize: TabBarIndicatorSize.label,
                    labelStyle: const TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                    unselectedLabelStyle: const TextStyle(
                      fontWeight: FontWeight.normal,
                      fontSize: 13,
                    ),
                    tabs: const [
                      Tab(icon: Icon(Icons.directions_bus, size: 20), text: 'Buses'),
                      Tab(icon: Icon(Icons.location_pin, size: 20), text: 'Stops'),
                    ],
                  ),
                ),
              ),
            ),
          ];
        },
        body: TabBarView(
          controller: _tabController,
          children: [
            _SchedulesTab(route: widget.route, onRefresh: _refreshData, isRefreshing: _isRefreshing),
            _StopsTab(route: widget.route),
          ],
        ),
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
        icon: const Icon(Icons.notifications_active, color: Colors.white),
        label: const Text('Pre-Inform', style: TextStyle(color: Colors.white)),
        backgroundColor: Colors.orange,
        elevation: 4,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(30),
        ),
      ),
    );
  }
}

class _SchedulesTab extends StatelessWidget {
  final BusRoute route;
  final VoidCallback onRefresh;
  final bool isRefreshing;

  const _SchedulesTab({
    required this.route,
    required this.onRefresh,
    required this.isRefreshing,
  });

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

  void _showLiveStatusBottomSheet(
      BuildContext context, Map<String, dynamic> data) {
    final routeData = data['route'] as Map<String, dynamic>?;
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
                  if (routeData != null)
                    Text(
                      'Route ${routeData['number']}: ${routeData['origin']} → ${routeData['destination']}',
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
                                            color: Color.alphaBlend(statusColor.withAlpha(25), Colors.white),
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

  @override
  Widget build(BuildContext context) {
    final appProvider = Provider.of<AppProvider>(context);
    final primaryColor = Theme.of(context).primaryColor;

    Color _withOpacity(Color color, double opacity) {
      return color.withAlpha((color.alpha * opacity).round());
    }

    if (appProvider.isLoadingSchedules) {
      return const LoadingWidget(message: 'Loading buses...');
    }

    final schedules = appProvider.schedules
        .where((s) => s.route.id == route.id)
        .toList();

    return RefreshIndicator(
      onRefresh: () => appProvider.loadSchedules(routeId: route.id),
      backgroundColor: primaryColor,
      color: Colors.white,
      child: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(
            child: Column(
              children: [
                // Legend
                Container(
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        Colors.grey[50]!,
                        Colors.grey[100]!,
                      ],
                    ),
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withAlpha(13),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(4),
                            decoration: BoxDecoration(
                              color: primaryColor,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: const Icon(Icons.info, size: 16, color: Colors.white),
                          ),
                          const SizedBox(width: 8),
                          const Text(
                            'Bus Status Legend',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: Colors.black87,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 12,
                        runSpacing: 8,
                        children: const [
                          _LegendItem(color: Colors.green, label: 'Available', icon: Icons.check_circle),
                          _LegendItem(color: Colors.orange, label: 'Filling', icon: Icons.trending_up),
                          _LegendItem(color: Colors.red, label: 'Almost Full', icon: Icons.warning),
                          _LegendItem(color: Colors.grey, label: 'Full', icon: Icons.block),
                        ],
                      ),
                    ],
                  ),
                ),

                // Check Crowd Button
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Card(
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                      side: BorderSide(color: Colors.blue.shade100, width: 1),
                    ),
                    child: InkWell(
                      onTap: () {
                        _showStopPickerAndLiveStatus(context, route);
                      },
                      borderRadius: BorderRadius.circular(12),
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: Color.alphaBlend(Colors.blue.withAlpha(25), Colors.white),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(Icons.visibility, color: Colors.blue),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Check crowd at my stop',
                                    style: TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w600,
                                      color: Colors.blue.shade800,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    'Select your stop to see live bus occupancy',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.blue.shade600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            Icon(Icons.chevron_right, color: Colors.blue.shade800),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),

                // Bus count
                if (schedules.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: _withOpacity(primaryColor, 0.1),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.directions_bus, size: 14),
                              const SizedBox(width: 6),
                              Text(
                                '${schedules.length} bus${schedules.length > 1 ? 'es' : ''} available',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: primaryColor,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),

          if (schedules.isEmpty)
            const SliverFillRemaining(
              child: _EmptyWidget(
                message: 'No buses available for this route',
                icon: Icons.directions_bus_filled,
                subMessage: 'Check back later for schedules',
              ),
            )
          else
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final schedule = schedules[index];
                  return Padding(
                    padding: EdgeInsets.fromLTRB(16, 8, 16, index == schedules.length - 1 ? 100 : 8),
                    child: _ScheduleCard(schedule: schedule, route: route),
                  );
                },
                childCount: schedules.length,
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
  final IconData icon;

  const _LegendItem({
    required this.color,
    required this.label,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Color.alphaBlend(color.withAlpha(25), Colors.white),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w500,
              color: color,
            ),
          ),
        ],
      ),
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
    
    final currentStopName = schedule.currentStopName;
    final currentStopSeq = schedule.currentStopSequence;
    final nextStopName = schedule.nextStopName;
    final nextStopSeq = schedule.nextStopSequence;

    Color _withOpacity(Color color, double opacity) {
      return color.withAlpha((color.alpha * opacity).round());
    }

    return Card(
      margin: EdgeInsets.zero,
      elevation: 4,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
      ),
      child: InkWell(
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => BusLiveScreen(
                schedule: schedule,
                route: route,
              ),
            ),
          );
        },
        borderRadius: BorderRadius.circular(16),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Colors.white,
                Colors.grey[50]!,
              ],
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header row
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Bus info
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: _withOpacity(statusColor, 0.1),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Icon(
                            Icons.directions_bus,
                            color: statusColor,
                            size: 20,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              schedule.bus.numberPlate,
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w700,
                                color: Colors.black87,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${schedule.departureTime} - ${schedule.arrivalTime}',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey[600],
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    
                    // Status badge
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: _withOpacity(statusColor, 0.15),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: _withOpacity(statusColor, 0.3)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                              color: statusColor,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 6),
                          Text(
                            _getOccupancyStatus(),
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                              color: statusColor,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                
                const SizedBox(height: 16),
                
                // Date and driver row
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: _withOpacity(Colors.blueGrey, 0.1),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.calendar_today, size: 12, color: Colors.blueGrey),
                          const SizedBox(width: 4),
                          Text(
                            dateFormat.format(schedule.date),
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.blueGrey,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.person, size: 12, color: Colors.blueGrey),
                          const SizedBox(width: 4),
                          Text(
                            schedule.driverName,
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.blueGrey,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                
                const SizedBox(height: 12),
                
                // Current and next stop info
                if (currentStopName != null || nextStopName != null) ...[
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _withOpacity(Colors.blue, 0.05),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: _withOpacity(Colors.blue, 0.1)),
                    ),
                    child: Column(
                      children: [
                        if (currentStopName != null)
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(Icons.location_on, size: 14, color: Colors.blue),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Current Stop',
                                      style: TextStyle(
                                        fontSize: 10,
                                        color: Colors.blueGrey,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      '$currentStopName${currentStopSeq != null ? ' (Stop $currentStopSeq)' : ''}',
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w600,
                                        color: Colors.black87,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        if (currentStopName != null && nextStopName != null)
                          const SizedBox(height: 8),
                        if (nextStopName != null)
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(Icons.flag, size: 14, color: Colors.green),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Next Stop',
                                      style: TextStyle(
                                        fontSize: 10,
                                        color: Colors.blueGrey,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      '$nextStopName${nextStopSeq != null ? ' (Stop $nextStopSeq)' : ''}',
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w600,
                                        color: Colors.black87,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                
                // Seats progress
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Seat Availability',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[700],
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        Text(
                          '${schedule.availableSeats} seats left',
                          style: TextStyle(
                            fontSize: 12,
                            color: statusColor,
                            fontWeight: FontWeight.w600,
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
                        minHeight: 10,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          '${schedule.occupiedSeats}/${schedule.totalSeats} seats used',
                          style: TextStyle(
                            fontSize: 10,
                            color: Colors.grey[600],
                          ),
                        ),
                        Text(
                          '${schedule.occupancyRate.toStringAsFixed(0)}% full',
                          style: TextStyle(
                            fontSize: 10,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                
                const SizedBox(height: 12),
                
                // View details prompt
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: _withOpacity(Theme.of(context).primaryColor, 0.05),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.touch_app,
                        size: 14,
                        color: Theme.of(context).primaryColor,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        'Tap to view live bus status',
                        style: TextStyle(
                          fontSize: 11,
                          color: Theme.of(context).primaryColor,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
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
      return const _EmptyWidget(
        message: 'No stops information available',
        icon: Icons.location_off,
        subMessage: 'Stop data will be added soon',
      );
    }

    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Card(
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: BorderSide(color: Colors.grey.shade200),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Color.alphaBlend(Theme.of(context).primaryColor.withAlpha(25), Colors.white),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            Icons.route,
                            color: Theme.of(context).primaryColor,
                            size: 20,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Route Stops',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.black87,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                '${route.stops.length} stops total',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey[600],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        _StopLegendItem(color: Colors.green, label: 'Start'),
                        const SizedBox(width: 16),
                        _StopLegendItem(color: Colors.blue, label: 'Regular'),
                        const SizedBox(width: 16),
                        _StopLegendItem(color: Colors.orange, label: 'Limited'),
                        const SizedBox(width: 16),
                        _StopLegendItem(color: Colors.red, label: 'End'),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        SliverList(
          delegate: SliverChildBuilderDelegate(
            (context, index) {
              final stop = route.stops[index];
              final isFirst = index == 0;
              final isLast = index == route.stops.length - 1;
              final isLimited = stop.isLimitedStop;

              Color stopColor = isFirst
                  ? Colors.green
                  : isLast
                      ? Colors.red
                      : isLimited
                          ? Colors.orange
                          : Colors.blue;

              Color _withOpacity(Color color, double opacity) {
                return color.withAlpha((color.alpha * opacity).round());
              }

              return Padding(
                padding: EdgeInsets.fromLTRB(24, index == 0 ? 0 : 4, 24, index == route.stops.length - 1 ? 100 : 4),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Timeline
                    Column(
                      children: [
                        Container(
                          width: 28,
                          height: 28,
                          decoration: BoxDecoration(
                            color: stopColor,
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color: _withOpacity(stopColor, 0.3),
                                blurRadius: 6,
                                spreadRadius: 2,
                              ),
                            ],
                            border: Border.all(color: Colors.white, width: 3),
                          ),
                          child: Center(
                            child: Text(
                              '${stop.sequence}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ),
                        if (!isLast)
                          Container(
                            width: 2,
                            height: 60,
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [
                                  _withOpacity(stopColor, 0.5),
                                  Colors.grey[300]!,
                                ],
                                begin: Alignment.topCenter,
                                end: Alignment.bottomCenter,
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(width: 16),
                    
                    // Stop card
                    Expanded(
                      child: Card(
                        elevation: 2,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(14),
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [
                                Colors.white,
                                Colors.grey[50]!,
                              ],
                            ),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            children: [
                                              Expanded(
                                                child: Text(
                                                  stop.name,
                                                  style: const TextStyle(
                                                    fontSize: 15,
                                                    fontWeight: FontWeight.w600,
                                                    color: Colors.black87,
                                                  ),
                                                ),
                                              ),
                                              if (isLimited)
                                                Container(
                                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                                  decoration: BoxDecoration(
                                                    color: _withOpacity(Colors.orange, 0.1),
                                                    borderRadius: BorderRadius.circular(10),
                                                  ),
                                                  child: Row(
                                                    mainAxisSize: MainAxisSize.min,
                                                    children: [
                                                      Icon(Icons.flash_on, size: 10, color: Colors.orange),
                                                      const SizedBox(width: 4),
                                                      Text(
                                                        'Limited',
                                                        style: TextStyle(
                                                          fontSize: 9,
                                                          fontWeight: FontWeight.w600,
                                                          color: Colors.orange,
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                ),
                                            ],
                                          ),
                                          const SizedBox(height: 4),
                                          Text(
                                            stop.distanceInfo,
                                            style: TextStyle(
                                              fontSize: 12,
                                              color: Colors.grey[600],
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                if (isFirst || isLast)
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: _withOpacity(stopColor, 0.1),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(
                                          isFirst ? Icons.play_arrow : Icons.flag,
                                          size: 12,
                                          color: stopColor,
                                        ),
                                        const SizedBox(width: 6),
                                        Text(
                                          isFirst ? 'Starting Point' : 'Terminal Point',
                                          style: TextStyle(
                                            fontSize: 11,
                                            fontWeight: FontWeight.w600,
                                            color: stopColor,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
            childCount: route.stops.length,
          ),
        ),
      ],
    );
  }
}

class _StopLegendItem extends StatelessWidget {
  final Color color;
  final String label;

  const _StopLegendItem({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 2),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            color: Colors.grey[700],
          ),
        ),
      ],
    );
  }
}

class BusLiveScreen extends StatefulWidget {
  final Schedule schedule;
  final BusRoute route;

  const BusLiveScreen({
    super.key,
    required this.schedule,
    required this.route,
  });

  @override
  State<BusLiveScreen> createState() => _BusLiveScreenState();
}

class _BusLiveScreenState extends State<BusLiveScreen> {
  late Schedule _schedule;
  Timer? _timer;
  bool _isRefreshing = false;

  @override
  void initState() {
    super.initState();
    _schedule = widget.schedule;
    _startAutoRefresh();
  }

  void _startAutoRefresh() {
    _timer = Timer.periodic(const Duration(seconds: 15), (_) {
      _refreshSchedule();
    });
  }

  Future<void> _refreshSchedule() async {
    if (_isRefreshing) return;
    _isRefreshing = true;

    try {
      final today = DateTime.now();
      final dateStr = DateFormat('yyyy-MM-dd').format(today);

      final list = await ApiService.getSchedules(
        routeId: widget.route.id,
        date: dateStr,
      );

      final updated = list.firstWhere(
        (s) => s.id == _schedule.id,
        orElse: () => _schedule,
      );

      if (!mounted) return;
      setState(() {
        _schedule = updated;
      });
    } catch (e) {
      debugPrint('Error refreshing schedule: $e');
    } finally {
      _isRefreshing = false;
    }
  }

  Color _withOpacity(Color color, double opacity) {
    return color.withAlpha((color.alpha * opacity).round());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final schedule = _schedule;
    final dateFormat = DateFormat('EEEE, MMM dd, yyyy');

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
      return 'COMFORTABLE';
    }

    final statusColor = _getOccupancyColor();
    final currentStopName = schedule.currentStopName;
    final currentStopSeq = schedule.currentStopSequence;
    final nextStopName = schedule.nextStopName;
    final nextStopSeq = schedule.nextStopSequence;

    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: Text(
          'Bus ${schedule.bus.numberPlate}',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        actions: [
          IconButton(
            icon: Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: _withOpacity(Theme.of(context).primaryColor, 0.1),
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.map,
                size: 20,
                color: Theme.of(context).primaryColor,
              ),
            ),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => BusTrackingScreen(route: widget.route),
                ),
              );
            },
            tooltip: 'View on map',
          ),
          if (_isRefreshing)
            const Padding(
              padding: EdgeInsets.all(8.0),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
        ],
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Status Overview Card
            Card(
              elevation: 4,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
              ),
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(20),
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      _withOpacity(statusColor, 0.1),
                      _withOpacity(statusColor, 0.05),
                    ],
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: _withOpacity(statusColor, 0.2),
                                  blurRadius: 8,
                                  spreadRadius: 2,
                                ),
                              ],
                            ),
                            child: Icon(
                              Icons.directions_bus,
                              color: statusColor,
                              size: 28,
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
                                    fontSize: 20,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.black87,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'Route ${widget.route.number}',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: Colors.grey[600],
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 8,
                            ),
                            decoration: BoxDecoration(
                              color: statusColor,
                              borderRadius: BorderRadius.circular(20),
                              boxShadow: [
                                BoxShadow(
                                  color: _withOpacity(statusColor, 0.3),
                                  blurRadius: 6,
                                  spreadRadius: 1,
                                ),
                              ],
                            ),
                            child: Text(
                              _getOccupancyStatus(),
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      
                      // Progress bar with stats
                      Column(
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                'Seat Occupancy',
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.grey[700],
                                ),
                              ),
                              Text(
                                '${schedule.availableSeats} seats available',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: statusColor,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          ClipRRect(
                            borderRadius: BorderRadius.circular(10),
                            child: LinearProgressIndicator(
                              value: schedule.occupiedSeats / schedule.totalSeats,
                              backgroundColor: Colors.grey[200],
                              valueColor: AlwaysStoppedAnimation<Color>(statusColor),
                              minHeight: 14,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                '${schedule.occupiedSeats} occupied',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey[600],
                                ),
                              ),
                              Text(
                                '${schedule.totalSeats} total',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey[600],
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
            
            const SizedBox(height: 20),

            // Live Position Card
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: _withOpacity(Colors.blue, 0.1),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.location_on,
                            color: Colors.blue,
                            size: 20,
                          ),
                        ),
                        const SizedBox(width: 12),
                        const Text(
                          'Live Position',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: Colors.black87,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    
                    if (currentStopName == null && nextStopName == null)
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.grey[100],
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Center(
                          child: Column(
                            children: [
                              Icon(
                                Icons.location_searching,
                                size: 32,
                                color: Colors.grey[400],
                              ),
                              const SizedBox(height: 8),
                              Text(
                                'Waiting for position update',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: Colors.grey[600],
                                ),
                              ),
                            ],
                          ),
                        ),
                      )
                    else ...[
                      if (currentStopName != null)
                        _LocationItem(
                          icon: Icons.location_on,
                          iconColor: Colors.blue,
                          title: 'Current Stop',
                          subtitle: currentStopName,
                          sequence: currentStopSeq,
                        ),
                      
                      if (currentStopName != null && nextStopName != null)
                        Container(
                          height: 20,
                          width: 2,
                          margin: const EdgeInsets.symmetric(horizontal: 12),
                          color: Colors.grey[300],
                        ),
                      
                      if (nextStopName != null)
                        _LocationItem(
                          icon: Icons.flag,
                          iconColor: Colors.green,
                          title: 'Next Stop',
                          subtitle: nextStopName,
                          sequence: nextStopSeq,
                        ),
                    ],
                    
                    const SizedBox(height: 16),
                    
                    const Divider(color: Color(0xFFE0E0E0)),
                    
                    const SizedBox(height: 8),
                    
                    Row(
                      children: [
                        Icon(Icons.update, size: 14, color: Colors.grey[600]),
                        const SizedBox(width: 8),
                        Text(
                          'Last update: ${schedule.lastPassengerUpdate != null ? DateFormat.Hm().format(schedule.lastPassengerUpdate!) : "—"}',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                        const Spacer(),
                        if (_timer != null)
                          Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.autorenew, size: 12, color: Colors.green),
                              const SizedBox(width: 4),
                              Text(
                                'Auto-refresh on',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.green,
                                ),
                              ),
                            ],
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 20),

            // Schedule Details Card
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: _withOpacity(Colors.purple, 0.1),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.schedule,
                            color: Colors.purple,
                            size: 20,
                          ),
                        ),
                        const SizedBox(width: 12),
                        const Text(
                          'Schedule Details',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: Colors.black87,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    
                    _DetailRow(
                      icon: Icons.calendar_today,
                      iconColor: Colors.purple,
                      label: 'Date',
                      value: dateFormat.format(schedule.date),
                    ),
                    _DetailRow(
                      icon: Icons.directions_bus,
                      iconColor: Colors.blue,
                      label: 'Departure',
                      value: schedule.departureTime,
                    ),
                    _DetailRow(
                      icon: Icons.done_all,
                      iconColor: Colors.green,
                      label: 'Arrival',
                      value: schedule.arrivalTime,
                    ),
                    _DetailRow(
                      icon: Icons.person,
                      iconColor: Colors.orange,
                      label: 'Driver',
                      value: schedule.driverName,
                    ),
                    _DetailRow(
                      icon: Icons.alt_route,
                      iconColor: Colors.red,
                      label: 'Distance',
                      value: widget.route.distanceInfo,
                    ),
                    _DetailRow(
                      icon: Icons.timer,
                      iconColor: Colors.teal,
                      label: 'Duration',
                      value: widget.route.durationInfo,
                    ),
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }
}

class _LocationItem extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final int? sequence;

  const _LocationItem({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    this.sequence,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[200]!),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Color.alphaBlend(iconColor.withAlpha(25), Colors.white),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, size: 18, color: iconColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '$subtitle${sequence != null ? ' (Stop $sequence)' : ''}',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.black87,
                  ),
                ),
              ],
            ),
          ),
        ],
      )
    );
  }
}

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String label;
  final String value;

  const _DetailRow({
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.value,
  });

  Color _withOpacity(Color color, double opacity) {
    return color.withAlpha((color.alpha * opacity).round());
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: _withOpacity(iconColor, 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 18, color: iconColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.grey[600],
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: Colors.black87,
                  ),
                ),
              ],
            ),
          ),
        ],
      )
    );
  }
}

class _EmptyWidget extends StatelessWidget {
  final String message;
  final IconData icon;
  final String? subMessage;

  const _EmptyWidget({
    required this.message,
    required this.icon,
    this.subMessage,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.grey[100],
                shape: BoxShape.circle,
              ),
              child: Icon(
                icon,
                size: 48,
                color: Colors.grey[400],
              ),
            ),
            const SizedBox(height: 20),
            Text(
              message,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Colors.grey,
              ),
              textAlign: TextAlign.center,
            ),
            if (subMessage != null) ...[
              const SizedBox(height: 8),
              Text(
                subMessage!,
                style: const TextStyle(
                  fontSize: 14,
                  color: Colors.grey,
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      )
    );
  }
}