import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import 'driver_schedule_screen.dart';
import 'ticket_screen.dart';
import '../../services/api_service.dart';

class DriverHomeScreen extends StatefulWidget {
  const DriverHomeScreen({super.key});

  @override
  State<DriverHomeScreen> createState() => _DriverHomeScreenState();
}

class _DriverHomeScreenState extends State<DriverHomeScreen> {
  int _selectedIndex = 0;
  final GlobalKey<DriverScheduleScreenState> _scheduleKey = GlobalKey();

  // ── Spare mode state ──────────────────────────────────────────
  bool _hasSpareToday = false;
  bool _isSpareActive = false;
  bool _isSpareDispatched = false;
  String _spareStart = '';
  String _spareEnd = '';
  int _spareRemainingMin = 0;
  bool _isEnteringSpare = false;
  bool _isExitingSpare = false;

  @override
  void initState() {
    super.initState();
    _loadSpareStatus();
  }

  Future<void> _loadSpareStatus() async {
    try {
      final status = await ApiService.getSpareStatus();
      if (!mounted) return;
      setState(() {
        _hasSpareToday = status['has_spare'] ?? false;
        _isSpareActive = status['is_active'] ?? false;
        _isSpareDispatched = status['is_dispatched'] ?? false;
        _spareStart = status['spare_start'] ?? '';
        _spareEnd = status['spare_end'] ?? '';
        _spareRemainingMin = status['remaining_minutes'] ?? 0;
      });
    } catch (e) {
      print('Error loading spare status: $e');
    }
  }

  Future<void> _enterSpareMode() async {
    setState(() => _isEnteringSpare = true);

    try {
      final result = await ApiService.enterSpareMode();

      if (!mounted) return;
      setState(() {
        _isSpareActive = true;
        _spareRemainingMin = result['remaining_minutes'] ?? 0;
        _spareEnd = result['spare_end_time'] ?? _spareEnd;
        _isEnteringSpare = false;
      });

      _showSnack(
        '⚡ Spare mode activated! You are spare until $_spareEnd',
        Colors.orange,
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isEnteringSpare = false);
      _showSnack('Error: $e', Colors.red);
    }
  }

  Future<void> _exitSpareMode() async {
    setState(() => _isExitingSpare = true);

    try {
      await ApiService.exitSpareMode();

      if (!mounted) return;
      setState(() {
        _isSpareActive = false;
        _isExitingSpare = false;
      });

      _showSnack('Spare mode deactivated', Colors.green);
      
      // Reload status
      _loadSpareStatus();
    } catch (e) {
      if (!mounted) return;
      setState(() => _isExitingSpare = false);
      _showSnack('Error: $e', Colors.red);
    }
  }

  void _showSnack(String msg, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: color,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);

    final List<Widget> screens = [
      DriverScheduleScreen(key: _scheduleKey),
      const TicketScreen(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Driver Dashboard'),
        actions: [
          // ── Spare mode badge in app bar ──────────────────────
          if (_isSpareActive)
            Container(
              margin: const EdgeInsets.only(right: 8, top: 8, bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 10),
              decoration: BoxDecoration(
                color: Colors.orange,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                children: [
                  const Icon(Icons.electric_bolt, size: 14, color: Colors.white),
                  const SizedBox(width: 4),
                  Text(
                    'SPARE $_spareRemainingMin min',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          IconButton(
            icon: const Icon(Icons.person),
            onPressed: () => _showProfileDialog(context, authProvider),
          ),
        ],
      ),

      body: Column(
        children: [
          // ── SPARE BUS BANNER ─────────────────────────────────
          _SpareBusBanner(
            hasSpareToday: _hasSpareToday,
            isSpareActive: _isSpareActive,
            isSpareDispatched: _isSpareDispatched,
            spareStart: _spareStart,
            spareEnd: _spareEnd,
            remainingMinutes: _spareRemainingMin,
            isEntering: _isEnteringSpare,
            isExiting: _isExitingSpare,
            onEnterSpare: _enterSpareMode,
            onExitSpare: _exitSpareMode,
          ),

          // ── Main screen content ───────────────────────────────
          Expanded(
            child: IndexedStack(
              index: _selectedIndex,
              children: screens,
            ),
          ),
        ],
      ),

      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (i) => setState(() => _selectedIndex = i),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.schedule),
            label: 'My Schedule',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.people),
            label: 'Passenger Counter',
          ),
        ],
      ),
    );
  }

  void _showProfileDialog(BuildContext context, AuthProvider authProvider) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Profile'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              authProvider.user?.fullName ?? '',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(authProvider.user?.email ?? '',
                style: TextStyle(color: Colors.grey[600])),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.green[50],
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                'Driver',
                style: TextStyle(
                  color: Colors.green[700],
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close')),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              authProvider.logout();
            },
            child: const Text('Logout', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}

// ================================================================
// SPARE BUS BANNER WIDGET
// ================================================================

class _SpareBusBanner extends StatelessWidget {
  final bool hasSpareToday;
  final bool isSpareActive;
  final bool isSpareDispatched;
  final String spareStart;
  final String spareEnd;
  final int remainingMinutes;
  final bool isEntering;
  final bool isExiting;
  final VoidCallback onEnterSpare;
  final VoidCallback onExitSpare;

  const _SpareBusBanner({
    required this.hasSpareToday,
    required this.isSpareActive,
    required this.isSpareDispatched,
    required this.spareStart,
    required this.spareEnd,
    required this.remainingMinutes,
    required this.isEntering,
    required this.isExiting,
    required this.onEnterSpare,
    required this.onExitSpare,
  });

  @override
  Widget build(BuildContext context) {
    if (!hasSpareToday) return const SizedBox.shrink();

    // ── State 1: Dispatched ────────────────────────────────────
    if (isSpareDispatched) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        color: Colors.deepOrange[700],
        child: const Row(
          children: [
            Icon(Icons.electric_bolt, color: Colors.white, size: 18),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                '⚡ You are on SPARE DUTY - heading to assigned route',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                ),
              ),
            ),
          ],
        ),
      );
    }

    // ── State 2: Active (waiting for dispatch) WITH EXIT BUTTON ─────
    if (isSpareActive) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        color: Colors.orange[700],
        child: Row(
          children: [
            const Icon(Icons.electric_bolt, color: Colors.white, size: 18),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '⚡ SPARE MODE ACTIVE  •  $remainingMinutes min remaining  •  Ends: $spareEnd',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ),
            const SizedBox(width: 8),
            // Exit button
            TextButton.icon(
              onPressed: isExiting ? null : onExitSpare,
              style: TextButton.styleFrom(
                foregroundColor: Colors.white,
                backgroundColor: Colors.orange[900],
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                disabledBackgroundColor: Colors.orange[800],
              ),
              icon: isExiting
                  ? const SizedBox(
                      width: 12,
                      height: 12,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.close, size: 14),
              label: Text(
                isExiting ? 'Exiting...' : 'Exit',
                style: const TextStyle(fontSize: 12),
              ),
            ),
          ],
        ),
      );
    }

    // ── State 3: Not yet activated ─────────────────────────────
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.orange[50],
        border: Border(bottom: BorderSide(color: Colors.orange.shade200)),
      ),
      child: Row(
        children: [
          Icon(Icons.electric_bolt, color: Colors.orange[700], size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Your spare time: $spareStart - $spareEnd',
              style: TextStyle(
                color: Colors.orange[900],
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
            ),
          ),
          const SizedBox(width: 10),
          ElevatedButton.icon(
            onPressed: isEntering ? null : onEnterSpare,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange[700],
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
              disabledBackgroundColor: Colors.grey,
            ),
            icon: isEntering
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.electric_bolt, size: 14),
            label: Text(isEntering ? 'Activating...' : 'Enter Spare Mode'),
          ),
        ],
      ),
    );
  }
}