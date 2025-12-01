import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../models/route_model.dart';
import '../../models/schedule_model.dart';

class BusLiveScreen extends StatelessWidget {
  final Schedule schedule;
  final BusRoute route;

  const BusLiveScreen({
    super.key,
    required this.schedule,
    required this.route,
  });

  Color _occupancyColor() {
    final rate = schedule.occupancyRate;
    if (schedule.availableSeats == 0) return Colors.grey;
    if (rate >= 80) return Colors.red;
    if (rate >= 50) return Colors.orange;
    return Colors.green;
  }

  String _occupancyText() {
    final occupied = schedule.occupiedSeats;
    final total = schedule.totalSeats;
    final left = schedule.availableSeats;

    if (total == 0) return 'No seat info';
    if (left == 0) return 'FULL ($occupied / $total)';
    if (schedule.occupancyRate >= 80) {
      return 'Almost full – $left seat(s) left';
    }
    if (schedule.occupancyRate >= 50) {
      return 'Filling – $left seat(s) left';
    }
    return 'Comfortable – $left seat(s) left';
  }

  @override
  Widget build(BuildContext context) {
    final color = _occupancyColor();
    final dateFormat = DateFormat('EEE, MMM dd, yyyy');

    final currentSeq = schedule.currentStopSequence;
    final nextSeq = schedule.nextStopSequence;

    return Scaffold(
      appBar: AppBar(
        title: Text("${schedule.bus.numberPlate} • Route ${route.number}"),
      ),
      body: Column(
        children: [
          const SizedBox(height: 12),

          // Top card – seats + current/next stop
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: color, width: 2),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Seat status
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: color.withOpacity(0.1),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Icon(Icons.directions_bus, color: color),
                            ),
                            const SizedBox(width: 12),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  schedule.bus.numberPlate,
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                Text(
                                  dateFormat.format(schedule.date),
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.grey[600],
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              '${schedule.occupiedSeats} / ${schedule.totalSeats}',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: color,
                              ),
                            ),
                            Text(
                              _occupancyText(),
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey[700],
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Current / next stop info
                    Row(
                      children: [
                        const Icon(Icons.location_on, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            currentSeq == null
                                ? 'Bus has not started from origin yet.'
                                : 'Now at: ${schedule.currentStopName ?? "Stop #$currentSeq"} (Stop $currentSeq)',
                            style: const TextStyle(fontSize: 14),
                          ),
                        ),
                      ],
                    ),
                    if (nextSeq != null) ...[
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          const Icon(Icons.flag, size: 18),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              'Next: ${schedule.nextStopName ?? "Stop #$nextSeq"} (Stop $nextSeq)',
                              style: const TextStyle(fontSize: 14),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),

          const SizedBox(height: 12),

          // Timeline
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Card(
                elevation: 1,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Route progress',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Expanded(
                        child: ListView.builder(
                          itemCount: route.stops.length,
                          itemBuilder: (context, index) {
                            final stop = route.stops[index];
                            final seq = stop.sequence;

                            final bool isCurrent =
                                currentSeq != null && seq == currentSeq;
                            final bool isPast =
                                currentSeq != null && seq < currentSeq;
                            final bool isNext =
                                nextSeq != null && seq == nextSeq;

                            Color dotColor;
                            if (isCurrent) {
                              dotColor = Colors.blue;
                            } else if (isPast) {
                              dotColor = Colors.green;
                            } else if (isNext) {
                              dotColor = Colors.orange;
                            } else {
                              dotColor = Colors.grey;
                            }

                            return Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Timeline dot + line
                                Column(
                                  children: [
                                    Container(
                                      width: 20,
                                      height: 20,
                                      decoration: BoxDecoration(
                                        color: dotColor,
                                        shape: BoxShape.circle,
                                      ),
                                      child: Center(
                                        child: Text(
                                          '$seq',
                                          style: const TextStyle(
                                            fontSize: 10,
                                            color: Colors.white,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                    ),
                                    if (index != route.stops.length - 1)
                                      Container(
                                        width: 2,
                                        height: 32,
                                        color: Colors.grey[300],
                                      ),
                                  ],
                                ),
                                const SizedBox(width: 12),
                                // Stop info
                                Expanded(
                                  child: Container(
                                    margin:
                                        const EdgeInsets.only(bottom: 12),
                                    padding: const EdgeInsets.all(8),
                                    decoration: BoxDecoration(
                                      color: isCurrent
                                          ? Colors.blue.withOpacity(0.06)
                                          : Colors.grey[50],
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(
                                        color: isCurrent
                                            ? Colors.blue
                                            : Colors.grey[200]!,
                                      ),
                                    ),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Text(
                                              stop.name,
                                              style: const TextStyle(
                                                fontSize: 14,
                                                fontWeight: FontWeight.w600,
                                              ),
                                            ),
                                            if (isCurrent) ...[
                                              const SizedBox(width: 6),
                                              Container(
                                                padding:
                                                    const EdgeInsets.symmetric(
                                                  horizontal: 6,
                                                  vertical: 2,
                                                ),
                                                decoration: BoxDecoration(
                                                  color: Colors.blue[50],
                                                  borderRadius:
                                                      BorderRadius.circular(4),
                                                ),
                                                child: const Text(
                                                  'Current',
                                                  style: TextStyle(
                                                    fontSize: 10,
                                                    color: Colors.blue,
                                                  ),
                                                ),
                                              ),
                                            ] else if (isNext) ...[
                                              const SizedBox(width: 6),
                                              Container(
                                                padding:
                                                    const EdgeInsets.symmetric(
                                                  horizontal: 6,
                                                  vertical: 2,
                                                ),
                                                decoration: BoxDecoration(
                                                  color: Colors.orange[50],
                                                  borderRadius:
                                                      BorderRadius.circular(4),
                                                ),
                                                child: const Text(
                                                  'Next',
                                                  style: TextStyle(
                                                    fontSize: 10,
                                                    color: Colors.orange,
                                                  ),
                                                ),
                                              ),
                                            ],
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
                                ),
                              ],
                            );
                          },
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
  }
}
