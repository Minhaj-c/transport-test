import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/preinform_model.dart';
import '../../services/api_service.dart';
import '../../widgets/loading_widget.dart' as app_widgets;

class MyPreInformsScreen extends StatefulWidget {
  const MyPreInformsScreen({super.key});

  @override
  State<MyPreInformsScreen> createState() => _MyPreInformsScreenState();
}

class _MyPreInformsScreenState extends State<MyPreInformsScreen> {
  List<PreInform> _preinforms = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPreInforms();
  }

  Future<void> _loadPreInforms() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final preinforms = await ApiService.getMyPreInforms();
      setState(() {
        _preinforms = preinforms;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _cancelPreInform(PreInform preinform) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel Pre-Inform'),
        content:
            const Text('Are you sure you want to cancel this pre-inform?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('No'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text(
              'Yes, Cancel',
              style: TextStyle(color: Colors.red),
            ),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await ApiService.cancelPreInform(preinform.id);

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Pre-inform cancelled'),
          backgroundColor: Colors.orange,
        ),
      );

      _loadPreInforms();
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to cancel: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  /// 🔥 NEW: Use this pre-inform to fetch live crowd / buses at that stop
  Future<void> _viewLiveStatus(PreInform preinform) async {
    try {
      final dateStr = DateFormat('yyyy-MM-dd').format(preinform.dateOfTravel);

      final data = await ApiService.getLiveStatusForStop(
        routeId: preinform.routeId,
        stopId: preinform.boardingStopId,
        date: dateStr,
      );

      if (!mounted) return;
      _showLiveStatusBottomSheet(context, data);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to load live status: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const app_widgets.LoadingWidget(
        message: 'Loading your pre-informs...',
      );
    }

    if (_error != null) {
      return app_widgets.ErrorWidget(
        message: _error!,
        onRetry: _loadPreInforms,
      );
    }

    if (_preinforms.isEmpty) {
      return const app_widgets.EmptyWidget(
        message: 'No pre-informs yet\nTap on a route to create one',
        icon: Icons.notifications_none,
      );
    }

    return RefreshIndicator(
      onRefresh: _loadPreInforms,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _preinforms.length,
        itemBuilder: (context, index) {
          final preinform = _preinforms[index];
          return _PreInformCard(
            preinform: preinform,
            onCancel: () => _cancelPreInform(preinform),
            onViewLiveStatus: () => _viewLiveStatus(preinform), // 🔥 NEW
          );
        },
      ),
    );
  }
}

class _PreInformCard extends StatelessWidget {
  final PreInform preinform;
  final VoidCallback onCancel;
  final VoidCallback? onViewLiveStatus; // 🔥 NEW

  const _PreInformCard({
    required this.preinform,
    required this.onCancel,
    this.onViewLiveStatus,
  });

  Color _getStatusColor() {
    switch (preinform.status) {
      case 'pending':
        return Colors.orange;
      case 'noted':
        return Colors.blue;
      case 'completed':
        return Colors.green;
      case 'cancelled':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  IconData _getStatusIcon() {
    switch (preinform.status) {
      case 'pending':
        return Icons.pending;
      case 'noted':
        return Icons.check_circle_outline;
      case 'completed':
        return Icons.check_circle;
      case 'cancelled':
        return Icons.cancel;
      default:
        return Icons.info;
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateFormat = DateFormat('MMM dd, yyyy');
    final isPending = preinform.status == 'pending';
    final isFuture = preinform.dateOfTravel.isAfter(DateTime.now());

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
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
                    color: _getStatusColor().withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        _getStatusIcon(),
                        size: 16,
                        color: _getStatusColor(),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        preinform.statusText,
                        style: TextStyle(
                          color: _getStatusColor(),
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                if (isPending && isFuture)
                  IconButton(
                    icon: const Icon(Icons.cancel, color: Colors.red),
                    onPressed: onCancel,
                    tooltip: 'Cancel',
                  ),
              ],
            ),
            const SizedBox(height: 12),

            // Route Name
            Text(
              preinform.routeName,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),

            // Date
            Row(
              children: [
                const Icon(Icons.calendar_today, size: 16),
                const SizedBox(width: 8),
                Text(
                  dateFormat.format(preinform.dateOfTravel),
                  style: const TextStyle(fontSize: 14),
                ),
              ],
            ),
            const SizedBox(height: 6),

            // Time
            Row(
              children: [
                const Icon(Icons.access_time, size: 16),
                const SizedBox(width: 8),
                Text(
                  preinform.desiredTime,
                  style: const TextStyle(fontSize: 14),
                ),
              ],
            ),
            const SizedBox(height: 6),

            // Stop
            Row(
              children: [
                const Icon(Icons.location_on, size: 16),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    preinform.stopName,
                    style: const TextStyle(fontSize: 14),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),

            // Passengers
            Row(
              children: [
                const Icon(Icons.people, size: 16),
                const SizedBox(width: 8),
                Text(
                  '${preinform.passengerCount} passenger${preinform.passengerCount > 1 ? 's' : ''}',
                  style: const TextStyle(fontSize: 14),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Created At
            Text(
              'Created ${_formatCreatedAt(preinform.createdAt)}',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey[600],
              ),
            ),

            const SizedBox(height: 8),

            // 🔥 NEW: view live status button
            if (onViewLiveStatus != null)
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: onViewLiveStatus,
                  icon: const Icon(Icons.remove_red_eye),
                  label: const Text('View live crowd & buses'),
                ),
              ),
          ],
        ),
      ),
    );
  }

  String _formatCreatedAt(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date);

    if (difference.inDays > 0) {
      return '${difference.inDays} day${difference.inDays > 1 ? 's' : ''} ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours} hour${difference.inHours > 1 ? 's' : ''} ago';
    } else if (difference.inMinutes > 0) {
      return '${difference.inMinutes} minute${difference.inMinutes > 1 ? 's' : ''} ago';
    } else {
      return 'Just now';
    }
  }
}

/// 🔥 Shared bottom sheet UI for live status
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
