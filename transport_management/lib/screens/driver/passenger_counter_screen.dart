import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/schedule_model.dart';
import '../../services/api_service.dart';

class PassengerCounterScreen extends StatefulWidget {
  const PassengerCounterScreen({super.key});

  @override
  State<PassengerCounterScreen> createState() => _PassengerCounterScreenState();
}

class _PassengerCounterScreenState extends State<PassengerCounterScreen> {
  int _currentCount = 0;
  int _busCapacity = 40;

  Schedule? _activeSchedule;
  bool _isLoading = true;
  bool _isSyncing = false;
  String? _error;

  final List<Map<String, dynamic>> _history = [];

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
      final schedules = await ApiService.getDriverSchedules();

      if (schedules.isEmpty) {
        setState(() {
          _isLoading = false;
          _error = 'No schedules assigned to you.';
        });
        return;
      }

      final now = DateTime.now();
      final todaySchedules = schedules.where((s) {
        return s.date.year == now.year &&
            s.date.month == now.month &&
            s.date.day == now.day;
      }).toList();

      if (todaySchedules.isEmpty) {
        setState(() {
          _isLoading = false;
          _error = 'No schedule found for today.';
        });
        return;
      }

      final active = todaySchedules.first;

      setState(() {
        _activeSchedule = active;
        _busCapacity = active.totalSeats;
        _currentCount = active.livePassengers;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _isLoading = false;
        _error = 'Failed to load schedule: $e';
      });
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
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 64, color: Colors.red),
              const SizedBox(height: 16),
              Text(_error!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 16)),
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

    final occupancyRate = _busCapacity == 0 ? 0 : (_currentCount / _busCapacity * 100).toInt();
    final availableSeats = _busCapacity - _currentCount;

    Color getOccupancyColor() {
      if (occupancyRate >= 90) return Colors.red;
      if (occupancyRate >= 70) return Colors.orange;
      return Colors.green;
    }

    final schedule = _activeSchedule;
    final dateFormat = DateFormat('MMM dd, yyyy');

    return Column(
      children: [
        // Schedule Info Banner
        if (schedule != null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.blueGrey.shade50,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.blueGrey.shade200),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Route ${schedule.route.number}: ${schedule.route.name}',
                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                ),
                const SizedBox(height: 4),
                Text(
                  '${dateFormat.format(schedule.date)} • ${schedule.departureTime} - ${schedule.arrivalTime}',
                  style: TextStyle(fontSize: 12, color: Colors.grey[700]),
                ),
                const SizedBox(height: 4),
                Text(
                  'Bus: ${schedule.bus.numberPlate} • Capacity: $_busCapacity',
                  style: TextStyle(fontSize: 12, color: Colors.grey[700]),
                ),
                if (_isSyncing) ...[
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        'Syncing with server...',
                        style: TextStyle(fontSize: 12, color: Colors.blue[700]),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),

        // Counter Display - Made scrollable to prevent overflow
        Expanded(
          child: SingleChildScrollView(
            child: Container(
              margin: const EdgeInsets.all(16),
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Theme.of(context).primaryColor.withOpacity(0.8),
                    Theme.of(context).primaryColor,
                  ],
                ),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: Theme.of(context).primaryColor.withOpacity(0.3),
                    blurRadius: 20,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Current Passengers',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    '$_currentCount',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 100,
                      fontWeight: FontWeight.bold,
                      height: 1,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'of $_busCapacity seats',
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 30),
                  Column(
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: LinearProgressIndicator(
                          value: _busCapacity == 0 ? 0 : _currentCount / _busCapacity,
                          backgroundColor: Colors.white30,
                          valueColor: AlwaysStoppedAnimation<Color>(getOccupancyColor()),
                          minHeight: 12,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '$occupancyRate% Full',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      '$availableSeats seats available',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),

        // Control Buttons
        Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _currentCount > 0 && !_isSyncing
                          ? () => _removePassengers(1)
                          : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 20),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Column(
                        children: [
                          Icon(Icons.remove, size: 32),
                          SizedBox(height: 4),
                          Text('Remove 1', style: TextStyle(fontSize: 12)),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _currentCount < _busCapacity && !_isSyncing
                          ? () => _addPassengers(1)
                          : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.green,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 20),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Column(
                        children: [
                          Icon(Icons.add, size: 32),
                          SizedBox(height: 4),
                          Text('Add 1', style: TextStyle(fontSize: 12)),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _currentCount >= 5 && !_isSyncing
                          ? () => _removePassengers(5)
                          : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.orange,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text('- 5', style: TextStyle(fontSize: 16)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton(
                      onPressed: !_isSyncing ? _resetCounter : null,
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text('Reset', style: TextStyle(fontSize: 16)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _currentCount <= _busCapacity - 5 && !_isSyncing
                          ? () => _addPassengers(5)
                          : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.blue,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text('+ 5', style: TextStyle(fontSize: 16)),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: _showHistory,
                icon: const Icon(Icons.history),
                label: const Text('View History'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  minimumSize: const Size(double.infinity, 0),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  void _addPassengers(int count) {
    if (_activeSchedule == null || _isSyncing) return;
    
    setState(() {
      _currentCount += count;
      if (_currentCount > _busCapacity) {
        _currentCount = _busCapacity;
      }
      _addToHistory('Added $count passenger${count > 1 ? 's' : ''}');
    });
    
    _syncWithBackend();
  }

  void _removePassengers(int count) {
    if (_activeSchedule == null || _isSyncing) return;
    
    setState(() {
      _currentCount -= count;
      if (_currentCount < 0) {
        _currentCount = 0;
      }
      _addToHistory('Removed $count passenger${count > 1 ? 's' : ''}');
    });
    
    _syncWithBackend();
  }

  Future<void> _syncWithBackend() async {
    if (_activeSchedule == null || _isSyncing) return;

    setState(() => _isSyncing = true);

    try {
      await ApiService.updatePassengerCount(
        scheduleId: _activeSchedule!.id,
        count: _currentCount,
      );
    } catch (e) {
      if (!mounted) return;
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to sync: $e'),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 3),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isSyncing = false);
      }
    }
  }

  void _resetCounter() {
    if (_activeSchedule == null || _isSyncing) return;

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reset Counter'),
        content: const Text('Reset passenger count to 0?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              setState(() {
                _currentCount = 0;
                _addToHistory('Counter reset');
              });
              Navigator.pop(context);
              _syncWithBackend();
            },
            child: const Text('Reset', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  void _addToHistory(String action) {
    _history.insert(0, {
      'action': action,
      'count': _currentCount,
      'time': DateTime.now(),
    });
  }

  void _showHistory() {
    showModalBottomSheet(
      context: context,
      builder: (context) => Container(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Passenger Count History',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const Divider(),
            Expanded(
              child: _history.isEmpty
                  ? const Center(child: Text('No history yet'))
                  : ListView.builder(
                      itemCount: _history.length,
                      itemBuilder: (context, index) {
                        final item = _history[index];
                        final time = item['time'] as DateTime;
                        final timeStr = '${time.hour.toString().padLeft(2, '0')}:'
                            '${time.minute.toString().padLeft(2, '0')}';
                        return ListTile(
                          leading: CircleAvatar(child: Text('${item['count']}')),
                          title: Text(item['action']),
                          trailing: Text(timeStr),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}