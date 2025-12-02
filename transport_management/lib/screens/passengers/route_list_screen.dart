import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/app_provider.dart';
import '../../models/route_model.dart';
import '../../widgets/loading_widget.dart';
import 'route_detail_screen.dart';

class RouteListScreen extends StatefulWidget {
  const RouteListScreen({super.key});

  @override
  State<RouteListScreen> createState() => _RouteListScreenState();
}

class _RouteListScreenState extends State<RouteListScreen> {
  final _searchController = TextEditingController();
  final _startStopController = TextEditingController();
  final _endStopController = TextEditingController();

  String _searchQuery = '';
  bool _showFilters = false;
  bool _filterApplied = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<AppProvider>(context, listen: false).loadRoutes();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    _startStopController.dispose();
    _endStopController.dispose();
    super.dispose();
  }

  void _clearFilters() {
    setState(() {
      _searchController.clear();
      _startStopController.clear();
      _endStopController.clear();
      _searchQuery = '';
      _filterApplied = false;
    });
  }

  void _applyFilters() {
    if (_startStopController.text.isNotEmpty ||
        _endStopController.text.isNotEmpty) {
      setState(() {
        _filterApplied = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final appProvider = Provider.of<AppProvider>(context);

    return Column(
      children: [
        // Search and Filter Section
        Container(
          padding: const EdgeInsets.all(16.0),
          decoration: BoxDecoration(
            color: Colors.white,
            boxShadow: [
              BoxShadow(
                color: Colors.grey.withOpacity(0.1),
                blurRadius: 4,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            children: [
              // Quick Search
              TextField(
                controller: _searchController,
                onChanged: (value) {
                  setState(() => _searchQuery = value.toLowerCase());
                },
                decoration: InputDecoration(
                  hintText:
                      'Search by route number / name / stop...',
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (_searchQuery.isNotEmpty)
                        IconButton(
                          icon: const Icon(Icons.clear),
                          onPressed: () {
                            _searchController.clear();
                            setState(() => _searchQuery = '');
                          },
                        ),
                      IconButton(
                        icon: Icon(
                          _showFilters
                              ? Icons.filter_alt
                              : Icons.filter_alt_outlined,
                        ),
                        onPressed: () {
                          setState(() => _showFilters = !_showFilters);
                        },
                        tooltip: 'Search by stops',
                      ),
                    ],
                  ),
                  filled: true,
                  fillColor: Colors.grey[100],
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),

              // Advanced Filters: Start stop / End stop
              if (_showFilters) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.blue[50],
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.blue[200]!),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.filter_list,
                              size: 20, color: Colors.blue),
                          SizedBox(width: 8),
                          Text(
                            'Find buses between two stops',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: Colors.blue,
                              fontSize: 16,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),

                      // Start stop
                      TextField(
                        controller: _startStopController,
                        onChanged: (value) => setState(() {}),
                        decoration: InputDecoration(
                          labelText: 'From stop',
                          hintText: 'Enter starting stop name',
                          prefixIcon: const Icon(Icons.trip_origin,
                              color: Colors.green),
                          filled: true,
                          fillColor: Colors.white,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),

                      // End stop
                      TextField(
                        controller: _endStopController,
                        onChanged: (value) => setState(() {}),
                        decoration: InputDecoration(
                          labelText: 'To stop',
                          hintText: 'Enter destination stop name',
                          prefixIcon: const Icon(Icons.location_on,
                              color: Colors.red),
                          filled: true,
                          fillColor: Colors.white,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),

                      // Action Buttons
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: _clearFilters,
                              icon: const Icon(Icons.clear_all),
                              label: const Text('Clear'),
                              style: OutlinedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(
                                    vertical: 12),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: ElevatedButton.icon(
                              onPressed: _applyFilters,
                              icon: const Icon(Icons.search),
                              label: const Text('Find buses'),
                              style: ElevatedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(
                                    vertical: 12),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],

              // Filter Status Chip
              if (_filterApplied) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.green[100],
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.check_circle,
                          size: 16, color: Colors.green),
                      const SizedBox(width: 6),
                      Text(
                        'From: ${_startStopController.text.isNotEmpty ? _startStopController.text : "Any"}  '
                        '→  To: ${_endStopController.text.isNotEmpty ? _endStopController.text : "Any"}',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Colors.green,
                        ),
                      ),
                      const SizedBox(width: 6),
                      InkWell(
                        onTap: _clearFilters,
                        child: const Icon(Icons.close,
                            size: 16, color: Colors.green),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),

        // Route list
        Expanded(
          child: appProvider.isLoadingRoutes
              ? const LoadingWidget(message: 'Loading routes...')
              : appProvider.routes.isEmpty
                  ? const EmptyWidget(
                      message: 'No routes available',
                      icon: Icons.route,
                    )
                  : _buildRouteList(appProvider.routes),
        ),
      ],
    );
  }

  Widget _buildRouteList(List<BusRoute> routes) {
    // "Where is my bus?" – don’t show everything until user searches
    if (_searchQuery.isEmpty && !_filterApplied) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.directions_bus, size: 80, color: Colors.grey[400]),
              const SizedBox(height: 16),
              const Text(
                'Where is my bus?',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                'Enter your start and end stops, or type a\n'
                'route number / stop name in the search box.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey[600]),
              ),
            ],
          ),
        ),
      );
    }

    final filteredRoutes = _filterRoutes(routes);

    if (filteredRoutes.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.search_off, size: 80, color: Colors.grey[400]),
              const SizedBox(height: 16),
              const Text(
                'No buses found',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                _filterApplied
                    ? 'No route runs from this start stop to this end stop.\n'
                      'Try different stops or clear filters.'
                    : 'No route or stop matches this search.\n'
                      'Try a different bus number or stop name.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey[600]),
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: _clearFilters,
                icon: const Icon(Icons.clear),
                label: const Text('Clear Filters'),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () =>
          Provider.of<AppProvider>(context, listen: false).loadRoutes(),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: filteredRoutes.length,
        itemBuilder: (context, index) {
          final route = filteredRoutes[index];
          return _RouteCard(route: route);
        },
      ),
    );
  }

  /// Core filtering: text search + start/end stop logic
  List<BusRoute> _filterRoutes(List<BusRoute> routes) {
    return routes.where((route) {
      // 1) Quick search (route number / name / any stop)
      if (_searchQuery.isNotEmpty) {
        final stopMatch = route.stops.any(
          (s) => s.name.toLowerCase().contains(_searchQuery),
        );

        final matchesSearch =
            route.number.toLowerCase().contains(_searchQuery) ||
                route.name.toLowerCase().contains(_searchQuery) ||
                route.origin.toLowerCase().contains(_searchQuery) ||
                route.destination.toLowerCase().contains(_searchQuery) ||
                stopMatch;

        if (!matchesSearch) return false;
      }

      // 2) Start stop / End stop filter
      if (_filterApplied) {
        final startQuery = _startStopController.text.toLowerCase().trim();
        final endQuery = _endStopController.text.toLowerCase().trim();

        // Case: both start and end stop entered
        if (startQuery.isNotEmpty && endQuery.isNotEmpty) {
          final startIdx = _getStopIndexForStop(route, startQuery);
          final endIdx = _getStopIndexForStop(route, endQuery);

          // Must exist on this route and be in correct order
          if (startIdx < 0 || endIdx < 0) return false;
          if (startIdx >= endIdx) return false;
        }
        // Only start stop entered
        else if (startQuery.isNotEmpty) {
          if (!_routeHasStop(route, startQuery)) return false;
        }
        // Only end stop entered
        else if (endQuery.isNotEmpty) {
          if (!_routeHasStop(route, endQuery)) return false;
        }
      }

      return true;
    }).toList();
  }

  /// Check if a route has a given stop name (including origin/destination)
  bool _routeHasStop(BusRoute route, String stopName) {
    stopName = stopName.toLowerCase();

    if (route.origin.toLowerCase().contains(stopName)) return true;
    if (route.destination.toLowerCase().contains(stopName)) return true;

    for (var stop in route.stops) {
      if (stop.name.toLowerCase().contains(stopName)) return true;
    }

    return false;
  }

  /// Get "position" of a stop along the route.
  /// 0 -> origin, 1..N -> intermediate stops by sequence, last+1 -> destination.
  int _getStopIndexForStop(BusRoute route, String stopName) {
    stopName = stopName.toLowerCase();

    // Origin as stop index 0
    if (route.origin.toLowerCase().contains(stopName)) {
      return 0;
    }

    // Intermediate stops (use sequence as position)
    for (var stop in route.stops) {
      if (stop.name.toLowerCase().contains(stopName)) {
        return stop.sequence;
      }
    }

    // Destination as last index
    if (route.destination.toLowerCase().contains(stopName)) {
      return route.stops.isEmpty ? 1 : route.stops.length + 1;
    }

    return -1; // Not found on this route
  }
}

class _RouteCard extends StatelessWidget {
  final BusRoute route;

  const _RouteCard({required this.route});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: InkWell(
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => RouteDetailScreen(route: route),
            ),
          );
        },
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Route number and name
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
                      route.number,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      route.name,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const Icon(Icons.chevron_right),
                ],
              ),
              const SizedBox(height: 12),

              // Origin to Destination
              Row(
                children: [
                  const Icon(Icons.trip_origin,
                      size: 16, color: Colors.green),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      route.origin,
                      style: const TextStyle(fontSize: 14),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.location_on,
                      size: 16, color: Colors.red),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      route.destination,
                      style: const TextStyle(fontSize: 14),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Distance and Duration
              Row(
                children: [
                  _InfoChip(
                    icon: Icons.straighten,
                    label: route.distanceInfo,
                  ),
                  const SizedBox(width: 8),
                  _InfoChip(
                    icon: Icons.access_time,
                    label: route.durationInfo,
                  ),
                  const SizedBox(width: 8),
                  _InfoChip(
                    icon: Icons.stop_circle,
                    label: '${route.stops.length} stops',
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _InfoChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding:
          const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.grey[700]),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[700],
            ),
          ),
        ],
      ),
    );
  }
}
