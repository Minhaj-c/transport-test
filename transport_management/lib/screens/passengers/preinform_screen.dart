import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../models/route_model.dart';
import '../../models/stop_model.dart'; // ✅ for Stop
import '../../services/api_service.dart';
import '../../widgets/custom_button.dart';

class PreInformScreen extends StatefulWidget {
  final BusRoute route;

  const PreInformScreen({super.key, required this.route});

  @override
  State<PreInformScreen> createState() => _PreInformScreenState();
}

class _PreInformScreenState extends State<PreInformScreen> {
  final _formKey = GlobalKey<FormState>();

  DateTime? _selectedDate;
  TimeOfDay? _selectedTime;
  int? _selectedBoardingStopId;
  int? _selectedDropoffStopId;
  int _passengerCount = 1;
  bool _isLoading = false;

  // ---------- Helpers for stops ----------

  Stop? _getStopById(int id) {
    try {
      return widget.route.stops.firstWhere((s) => s.id == id);
    } catch (_) {
      return null;
    }
  }

  List<Stop> _getDropoffCandidates() {
    if (_selectedBoardingStopId == null) return [];

    final boarding = _getStopById(_selectedBoardingStopId!);
    if (boarding == null) return [];

    return widget.route.stops
        .where((s) => s.sequence > boarding.sequence)
        .toList();
  }

  // ---------- Pickers ----------

  Future<void> _selectDate() async {
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: DateTime.now(),
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 30)),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: ColorScheme.light(
              primary: Theme.of(context).primaryColor,
            ),
          ),
          child: child!,
        );
      },
    );

    if (picked != null) {
      setState(() => _selectedDate = picked);
    }
  }

  Future<void> _selectTime() async {
    final TimeOfDay? picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: ColorScheme.light(
              primary: Theme.of(context).primaryColor,
            ),
          ),
          child: child!,
        );
      },
    );

    if (picked != null) {
      setState(() => _selectedTime = picked);
    }
  }

  // ---------- Submit ----------

  Future<void> _submitPreInform() async {
    if (!_formKey.currentState!.validate()) return;

    if (_selectedDate == null) {
      _showError('Please select travel date');
      return;
    }

    if (_selectedTime == null) {
      _showError('Please select desired time');
      return;
    }

    if (_selectedBoardingStopId == null) {
      _showError('Please select boarding stop');
      return;
    }

    if (_selectedDropoffStopId == null) {
      _showError('Please select drop-off stop');
      return;
    }

    final boardingStop = _getStopById(_selectedBoardingStopId!);
    final dropoffStop = _getStopById(_selectedDropoffStopId!);

    if (boardingStop == null || dropoffStop == null) {
      _showError('Something went wrong with the selected stops');
      return;
    }

    if (dropoffStop.sequence <= boardingStop.sequence) {
      _showError('Drop-off stop must be AFTER your boarding stop');
      return;
    }

    setState(() => _isLoading = true);

    try {
      // ✅ DATE IN YYYY-MM-DD
      final dateStr = DateFormat('yyyy-MM-dd').format(_selectedDate!);

      // ✅ TIME IN HH:mm (24-hr)
      final timeStr = _selectedTime!.hour.toString().padLeft(2, '0') +
          ':' +
          _selectedTime!.minute.toString().padLeft(2, '0');

      await ApiService.createPreInform(
        routeId: widget.route.id,
        dateOfTravel: dateStr,
        desiredTime: timeStr,
        boardingStopId: _selectedBoardingStopId!,
        dropoffStopId: _selectedDropoffStopId!, // ✅ NEW
        passengerCount: _passengerCount,
      );

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('✅ Pre-inform submitted successfully!'),
          backgroundColor: Colors.green,
          duration: Duration(seconds: 2),
        ),
      );

      Future.delayed(const Duration(seconds: 1), () {
        if (mounted) Navigator.pop(context);
      });
    } catch (e) {
      _showError('Failed to submit: $e');
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
      ),
    );
  }

  // ---------- UI ----------

  @override
  Widget build(BuildContext context) {
    final boardingStop =
        _selectedBoardingStopId != null ? _getStopById(_selectedBoardingStopId!) : null;
    final dropoffStop =
        _selectedDropoffStopId != null ? _getStopById(_selectedDropoffStopId!) : null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Pre-Inform Your Journey'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Route Info Card
              Card(
                elevation: 2,
                color: Colors.blue.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: Theme.of(context).primaryColor,
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              widget.route.number,
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              widget.route.name,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          const Icon(Icons.trip_origin,
                              size: 16, color: Colors.green),
                          const SizedBox(width: 8),
                          Text(widget.route.origin),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.location_on,
                              size: 16, color: Colors.red),
                          const SizedBox(width: 8),
                          Text(widget.route.destination),
                        ],
                      ),
                      if (boardingStop != null && dropoffStop != null) ...[
                        const SizedBox(height: 12),
                        const Divider(),
                        const SizedBox(height: 8),
                        Text(
                          'Your journey: ${boardingStop.name} → ${dropoffStop.name}',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Date
              const Text(
                'Travel Date *',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              InkWell(
                onTap: _selectDate,
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: _selectedDate != null
                          ? Theme.of(context).primaryColor
                          : Colors.grey[300]!,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    color: Colors.grey[50],
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.calendar_today,
                        color: _selectedDate != null
                            ? Theme.of(context).primaryColor
                            : Colors.grey,
                      ),
                      const SizedBox(width: 12),
                      Text(
                        _selectedDate == null
                            ? 'Select date'
                            : DateFormat('EEEE, MMM dd, yyyy')
                                .format(_selectedDate!),
                        style: TextStyle(
                          fontSize: 16,
                          color: _selectedDate == null
                              ? Colors.grey[600]
                              : Colors.black87,
                          fontWeight: _selectedDate != null
                              ? FontWeight.w600
                              : FontWeight.normal,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Time
              const Text(
                'Desired Time *',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              InkWell(
                onTap: _selectTime,
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: _selectedTime != null
                          ? Theme.of(context).primaryColor
                          : Colors.grey[300]!,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    color: Colors.grey[50],
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.access_time,
                        color: _selectedTime != null
                            ? Theme.of(context).primaryColor
                            : Colors.grey,
                      ),
                      const SizedBox(width: 12),
                      Text(
                        _selectedTime == null
                            ? 'Select time'
                            : _selectedTime!.format(context),
                        style: TextStyle(
                          fontSize: 16,
                          color: _selectedTime == null
                              ? Colors.grey[600]
                              : Colors.black87,
                          fontWeight: _selectedTime != null
                              ? FontWeight.w600
                              : FontWeight.normal,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // Boarding Stop
              const Text(
                'Boarding Stop *',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),

              widget.route.stops.isEmpty
                  ? Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.orange[50],
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.orange),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.warning, color: Colors.orange),
                          SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'No stops available for this route',
                              style: TextStyle(color: Colors.orange),
                            ),
                          ),
                        ],
                      ),
                    )
                  : Container(
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: _selectedBoardingStopId != null
                              ? Theme.of(context).primaryColor
                              : Colors.grey[300]!,
                        ),
                        borderRadius: BorderRadius.circular(12),
                        color: Colors.grey[50],
                      ),
                      child: DropdownButtonHideUnderline(
                        child: ButtonTheme(
                          alignedDropdown: true,
                          child: DropdownButton<int>(
                            value: _selectedBoardingStopId,
                            hint: const Padding(
                              padding: EdgeInsets.symmetric(vertical: 12),
                              child: Text('Select boarding stop'),
                            ),
                            isExpanded: true,
                            icon: const Icon(Icons.arrow_drop_down),
                            borderRadius: BorderRadius.circular(12),
                            items: widget.route.stops.map((stop) {
                              final isFirst = stop.sequence == 1;
                              final isLast =
                                  stop.sequence == widget.route.stops.length;

                              return DropdownMenuItem<int>(
                                value: stop.id,
                                child: Padding(
                                  padding:
                                      const EdgeInsets.symmetric(vertical: 8),
                                  child: Row(
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
                                        ),
                                        child: Center(
                                          child: Text(
                                            '${stop.sequence}',
                                            style: const TextStyle(
                                              color: Colors.white,
                                              fontSize: 12,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 12),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              stop.name,
                                              style: const TextStyle(
                                                fontSize: 15,
                                                fontWeight: FontWeight.w500,
                                              ),
                                            ),
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
                                ),
                              );
                            }).toList(),
                            onChanged: (value) {
                              setState(() {
                                _selectedBoardingStopId = value;
                                // reset dropoff when boarding changes
                                _selectedDropoffStopId = null;
                              });
                            },
                          ),
                        ),
                      ),
                    ),
              const SizedBox(height: 20),

              // Dropoff Stop
              const Text(
                'Drop-off Stop *',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),

              if (widget.route.stops.isEmpty)
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.orange[50],
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.orange),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.warning, color: Colors.orange),
                      SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'No stops available for this route',
                          style: TextStyle(color: Colors.orange),
                        ),
                      ),
                    ],
                  ),
                )
              else if (_selectedBoardingStopId == null)
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.grey[100],
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey[300]!),
                  ),
                  child: const Text(
                    'Please select your boarding stop first.\n\nThen you can pick where you will get down.',
                    style: TextStyle(fontSize: 13),
                  ),
                )
              else
                _buildDropoffDropdown(),
              const SizedBox(height: 20),

              // Passenger Count
              const Text(
                'Number of Passengers',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey[300]!),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    IconButton(
                      onPressed: () {
                        if (_passengerCount > 1) {
                          setState(() => _passengerCount--);
                        }
                      },
                      icon: const Icon(Icons.remove_circle),
                      iconSize: 32,
                      color: _passengerCount > 1
                          ? Theme.of(context).primaryColor
                          : Colors.grey,
                    ),
                    Container(
                      width: 80,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      decoration: BoxDecoration(
                        color: Colors.blue.shade50,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '$_passengerCount',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                          color: Theme.of(context).primaryColor,
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () {
                        if (_passengerCount < 10) {
                          setState(() => _passengerCount++);
                        }
                      },
                      icon: const Icon(Icons.add_circle),
                      iconSize: 32,
                      color: _passengerCount < 10
                          ? Theme.of(context).primaryColor
                          : Colors.grey,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Info Note
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue[50],
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.blue[200]!),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.info_outline,
                        color: Colors.blue[700], size: 20),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'By telling us BOTH where you get in and where you get down, we can:\n'
                        '• Predict crowd at each stop\n'
                        '• Add spare buses early if needed\n'
                        '• Show other passengers which trips will be full',
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.blue[900],
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Submit Button
              CustomButton(
                text: 'Submit Pre-Inform',
                onPressed: widget.route.stops.isNotEmpty
                    ? _submitPreInform
                    : () {
                        _showError('No stops available for this route');
                      },
                isLoading: _isLoading,
                icon: Icons.check_circle,
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDropoffDropdown() {
    final dropoffStops = _getDropoffCandidates();

    if (dropoffStops.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.orange[50],
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.orange),
        ),
        child: const Text(
          'No later stops available after your boarding stop.\n'
          'Try choosing an earlier boarding stop.',
          style: TextStyle(color: Colors.orange),
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        border: Border.all(
          color: _selectedDropoffStopId != null
              ? Theme.of(context).primaryColor
              : Colors.grey[300]!,
        ),
        borderRadius: BorderRadius.circular(12),
        color: Colors.grey[50],
      ),
      child: DropdownButtonHideUnderline(
        child: ButtonTheme(
          alignedDropdown: true,
          child: DropdownButton<int>(
            value: _selectedDropoffStopId,
            hint: const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Text('Select drop-off stop'),
            ),
            isExpanded: true,
            icon: const Icon(Icons.arrow_drop_down),
            borderRadius: BorderRadius.circular(12),
            items: dropoffStops.map((stop) {
              return DropdownMenuItem<int>(
                value: stop.id,
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Row(
                    children: [
                      Container(
                        width: 24,
                        height: 24,
                        decoration: const BoxDecoration(
                          color: Colors.purple,
                          shape: BoxShape.circle,
                        ),
                        child: Center(
                          child: Text(
                            '${stop.sequence}',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              stop.name,
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
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
                ),
              );
            }).toList(),
            onChanged: (value) {
              setState(() => _selectedDropoffStopId = value);
            },
          ),
        ),
      ),
    );
  }
}
