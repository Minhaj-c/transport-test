import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../models/schedule_model.dart';
import '../../models/stop_model.dart';
import '../../services/api_service.dart';

// Same key used by DriverScheduleScreen to persist the active schedule
const String _kActiveSchedId = 'bus_active_schedule_id';

class TicketScreen extends StatefulWidget {
  const TicketScreen({super.key});

  @override
  State<TicketScreen> createState() => _TicketScreenState();
}

class _TicketScreenState extends State<TicketScreen> {
  Schedule? _activeSchedule;
  bool _isLoading = true;
  bool _isIssuing = false;
  String? _error;

  Stop? _boardingStop;
  Stop? _dropoffStop;
  int _passengerCount = 1;

  String? _lastTicketInfo;
  int _totalPassengers = 0;

  @override
  void initState() {
    super.initState();
    _loadActiveSchedule();
  }

  Future<void> _loadActiveSchedule() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final prefs = await SharedPreferences.getInstance();
      final int? activeSchedId = prefs.getInt(_kActiveSchedId);

      final schedules = await ApiService.getDriverSchedules();
      final now = DateTime.now();

      final todaySchedules = schedules.where((s) =>
          s.date.year == now.year &&
          s.date.month == now.month &&
          s.date.day == now.day).toList();

      if (todaySchedules.isEmpty) {
        setState(() {
          _isLoading = false;
          _error = 'No schedule found for today.';
        });
        return;
      }

      // ✅ Find the running schedule
      // If stored schedule not found (completed + excluded from API),
      // load the next available schedule automatically
      Schedule active;
      if (activeSchedId != null) {
        final found = todaySchedules.where((s) => s.id == activeSchedId).toList();
        if (found.isNotEmpty) {
          active = found.first;
        } else {
          // Stored schedule was completed — load next one
          active = todaySchedules.first;
          await prefs.remove(_kActiveSchedId); // clear stale ID
        }
      } else {
        active = todaySchedules.first;
      }

      setState(() {
        _activeSchedule  = active;
        _totalPassengers = active.livePassengers;
        _isLoading       = false;
        _boardingStop    = null;
        _dropoffStop     = null;
        _passengerCount  = 1;
        _lastTicketInfo  = null;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to load schedule: $e';
      });
    }
  }

  List<Stop> get _stops => _activeSchedule?.route.stops ?? [];

  List<Stop> get _dropoffStops {
    final Stop? boarding = _boardingStop;
    if (boarding == null) return [];
    return _stops.where((Stop s) => s.sequence > boarding.sequence).toList();
  }

  bool get _isLastStop {
    if (_activeSchedule == null || _stops.isEmpty) return false;
    final int currentSeq = _activeSchedule!.currentStopSequence ?? 0;
    return currentSeq > 0 && currentSeq == _stops.last.sequence;
  }

  bool get _canIssue =>
      _boardingStop != null && _dropoffStop != null && !_isIssuing;

  void _resetForm() {
    setState(() {
      _boardingStop   = null;
      _dropoffStop    = null;
      _passengerCount = 1;
      _lastTicketInfo = null;
    });
  }

  Future<void> _resetPassengerCount() async {
    final Schedule? schedule = _activeSchedule;
    if (schedule == null) return;

    final bool? confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Reset Passenger Count'),
        content: const Text(
          'This will reset the current passenger count to 0. '
          'Use this only at the start of a new trip.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Reset',
                style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      await ApiService.updatePassengerCount(
        scheduleId: schedule.id,
        count: 0,
      );
      setState(() => _totalPassengers = 0);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Passenger count reset to 0'),
            backgroundColor: Colors.orange,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to reset: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _issueTicket() async {
    final Stop? boarding     = _boardingStop;
    final Stop? dropoff      = _dropoffStop;
    final Schedule? schedule = _activeSchedule;

    if (boarding == null || dropoff == null || schedule == null) return;

    setState(() => _isIssuing = true);

    try {
      final Map<String, dynamic> result = await ApiService.issueTicket(
        scheduleId: schedule.id,
        boardingStopId: boarding.id,
        dropoffStopId: dropoff.id,
        passengerCount: _passengerCount,
      );

      HapticFeedback.lightImpact();

      final Map<String, dynamic> scheduleData =
          result['schedule'] as Map<String, dynamic>;
      final int newPassengers = scheduleData['current_passengers'] as int;

      setState(() {
        _totalPassengers = newPassengers;
        _lastTicketInfo  =
            '$_passengerCount pax  •  ${boarding.name} → ${dropoff.name}';
        _boardingStop    = null;
        _dropoffStop     = null;
        _passengerCount  = 1;
        _isIssuing       = false;
      });
    } catch (e) {
      setState(() => _isIssuing = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Error: $e'),
          backgroundColor: Colors.red,
        ));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.event_busy, size: 64, color: Colors.grey),
              const SizedBox(height: 16),
              Text(_error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 16)),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: _loadActiveSchedule,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_isLastStop) {
      return _LastStopScreen(onNextSchedule: _loadActiveSchedule);
    }

    final Schedule schedule = _activeSchedule!;

    return RefreshIndicator(
      onRefresh: _loadActiveSchedule,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _ScheduleBar(
              schedule: schedule,
              totalPassengers: _totalPassengers,
              onReset: _resetPassengerCount,
            ),

            const SizedBox(height: 20),

            if (_lastTicketInfo != null)
              _LastTicketBadge(info: _lastTicketInfo!),
            if (_lastTicketInfo != null) const SizedBox(height: 16),

            _SectionLabel('Boarding Stop'),
            const SizedBox(height: 8),
            _StopDropdown(
              hint: 'Where are they getting on?',
              stops: _stops,
              selected: _boardingStop,
              enabled: true,
              onChanged: (Stop? stop) {
                setState(() {
                  _boardingStop = stop;
                  final Stop? dropoff = _dropoffStop;
                  if (dropoff != null &&
                      stop != null &&
                      dropoff.sequence <= stop.sequence) {
                    _dropoffStop = null;
                  }
                });
              },
            ),

            const SizedBox(height: 16),

            _SectionLabel('Dropoff Stop'),
            const SizedBox(height: 8),
            _StopDropdown(
              hint: _boardingStop == null
                  ? 'Select boarding stop first'
                  : 'Where are they getting off?',
              stops: _dropoffStops,
              selected: _dropoffStop,
              enabled: _boardingStop != null,
              onChanged: (Stop? stop) => setState(() => _dropoffStop = stop),
            ),

            const SizedBox(height: 20),

            _SectionLabel('Passengers'),
            const SizedBox(height: 8),
            _PassengerCounter(
              count: _passengerCount,
              onChanged: (int val) => setState(() => _passengerCount = val),
            ),

            const SizedBox(height: 28),

            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _canIssue ? _issueTicket : null,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green[700],
                  foregroundColor: Colors.white,
                  disabledBackgroundColor: Colors.grey[300],
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                  elevation: 0,
                ),
                child: _isIssuing
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(
                              Icons.confirmation_number_rounded, size: 22),
                          const SizedBox(width: 10),
                          Text(
                            _passengerCount == 1
                                ? 'Issue Ticket'
                                : 'Issue $_passengerCount Tickets',
                            style: const TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.3,
                            ),
                          ),
                        ],
                      ),
              ),
            ),

            const SizedBox(height: 12),

            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _resetForm,
                icon: const Icon(Icons.clear, size: 18),
                label: const Text('Clear Form'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
              ),
            ),

            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────
// SCHEDULE BAR
// ─────────────────────────────────────────────────────────────────

class _ScheduleBar extends StatelessWidget {
  final Schedule schedule;
  final int totalPassengers;
  final VoidCallback onReset;

  const _ScheduleBar({
    required this.schedule,
    required this.totalPassengers,
    required this.onReset,
  });

  @override
  Widget build(BuildContext context) {
    final int seats  = schedule.totalSeats;
    final double ratio =
        seats == 0 ? 0.0 : (totalPassengers / seats).clamp(0.0, 1.0);
    final int occupancy = (ratio * 100).toInt();

    final Color occColor = occupancy >= 85
        ? Colors.red
        : occupancy >= 65
            ? Colors.orange
            : Colors.green;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.blue[50],
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.blue[100]!),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.directions_bus, color: Colors.blue, size: 18),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Route ${schedule.route.number} — ${schedule.route.name}',
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                    color: Colors.black87,
                  ),
                ),
              ),
              IconButton(
                onPressed: onReset,
                icon: const Icon(Icons.restart_alt, size: 20),
                color: Colors.orange[700],
                tooltip: 'Reset passenger count',
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '${schedule.bus.numberPlate}  •  '
            '${schedule.departureTime} → ${schedule.arrivalTime}',
            style: TextStyle(fontSize: 12, color: Colors.grey[600]),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: ratio,
                    backgroundColor: Colors.blue[100],
                    valueColor: AlwaysStoppedAnimation<Color>(occColor),
                    minHeight: 8,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '$totalPassengers / $seats',
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                  color: occColor,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────
// STOP DROPDOWN
// ─────────────────────────────────────────────────────────────────

class _StopDropdown extends StatelessWidget {
  final String hint;
  final List<Stop> stops;
  final Stop? selected;
  final bool enabled;
  final void Function(Stop?) onChanged;

  const _StopDropdown({
    required this.hint,
    required this.stops,
    required this.selected,
    required this.enabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: enabled ? Colors.white : Colors.grey[100],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: enabled ? Colors.grey[300]! : Colors.grey[200]!,
        ),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<Stop>(
          value: selected,
          isExpanded: true,
          hint: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            child: Text(hint,
                style: TextStyle(color: Colors.grey[500], fontSize: 14)),
          ),
          icon: const Padding(
            padding: EdgeInsets.only(right: 12),
            child: Icon(Icons.keyboard_arrow_down, color: Colors.grey),
          ),
          borderRadius: BorderRadius.circular(12),
          onChanged: enabled ? onChanged : null,
          items: stops.map((Stop stop) {
            return DropdownMenuItem<Stop>(
              value: stop,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 11,
                      backgroundColor: Colors.blue[50],
                      child: Text(
                        '${stop.sequence}',
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: Colors.blue,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(stop.name,
                          style: const TextStyle(fontSize: 14),
                          overflow: TextOverflow.ellipsis),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────
// PASSENGER COUNTER
// ─────────────────────────────────────────────────────────────────

class _PassengerCounter extends StatelessWidget {
  final int count;
  final void Function(int) onChanged;

  const _PassengerCounter({required this.count, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[300]!),
      ),
      child: Row(
        children: [
          _CounterButton(
            icon: Icons.remove,
            onTap: count > 1 ? () => onChanged(count - 1) : null,
          ),
          Expanded(
            child: Column(
              children: [
                Text(
                  '$count',
                  style: const TextStyle(
                    fontSize: 36,
                    fontWeight: FontWeight.w800,
                    color: Colors.black87,
                  ),
                ),
                Text(
                  count == 1 ? 'passenger' : 'passengers',
                  style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                ),
              ],
            ),
          ),
          _CounterButton(
            icon: Icons.add,
            onTap: () => onChanged(count + 1),
          ),
        ],
      ),
    );
  }
}

class _CounterButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;

  const _CounterButton({required this.icon, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          color: onTap != null ? Colors.blue[50] : Colors.grey[100],
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(
          icon,
          color: onTap != null ? Colors.blue[700] : Colors.grey[400],
          size: 24,
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────
// LAST TICKET BADGE
// ─────────────────────────────────────────────────────────────────

class _LastTicketBadge extends StatelessWidget {
  final String info;
  const _LastTicketBadge({required this.info});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.green[50],
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.green[200]!),
      ),
      child: Row(
        children: [
          Icon(Icons.check_circle_rounded, color: Colors.green[700], size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Issued: $info',
              style: TextStyle(
                color: Colors.green[800],
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────
// LAST STOP SCREEN
// ─────────────────────────────────────────────────────────────────

class _LastStopScreen extends StatelessWidget {
  final VoidCallback onNextSchedule;
  const _LastStopScreen({required this.onNextSchedule});

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
                color: Colors.green[50],
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.flag_rounded, size: 64, color: Colors.green[700]),
            ),
            const SizedBox(height: 24),
            const Text(
              'Route Complete!',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w800,
                color: Colors.black87,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'All passengers have reached the last stop.\nTicket screen has been reset.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 14, color: Colors.grey[600]),
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: onNextSchedule,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blue,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                    horizontal: 28, vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              icon: const Icon(Icons.refresh_rounded),
              label: const Text(
                'Load Next Schedule',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────
// SECTION LABEL
// ─────────────────────────────────────────────────────────────────

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.w700,
        color: Colors.black54,
        letterSpacing: 0.5,
      ),
    );
  }
}