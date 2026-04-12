import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/features/listings/presentation/screens/listings_screen.dart';
import 'package:SemsAi/features/explore/presentation/screens/explore_screen.dart';
import 'package:SemsAi/features/favorite/presentation/screens/favourite_screen.dart';
import 'package:SemsAi/features/chat/presentation/screens/agent_chat_screen.dart';
import 'package:SemsAi/features/profile/presentation/screens/profile_screen.dart';
import 'package:SemsAi/features/portfolio/presentation/screens/portfolio_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  int _currentIndex = 0;

  final _listingsKey = GlobalKey<ListingsScreenState>();
  final _exploreKey = GlobalKey<ExploreScreenState>();

  late final AnimationController _fabSlideCtrl;
  late final AnimationController _pulseCtrl;
  bool _fabExpanded = true; // starts expanded with label visible

  late final List<Widget> _screens = [
    ListingsScreen(key: _listingsKey),
    ExploreScreen(key: _exploreKey),
    PortfolioScreen(),
    FavouriteScreen(),
    ProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();

    _fabSlideCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );

    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat(reverse: true);

    // Slide in from right edge after delay
    Future.delayed(const Duration(milliseconds: 1200), () {
      if (mounted) _fabSlideCtrl.forward();
    });

    // Auto-collapse to icon-only after 6 seconds
    Future.delayed(const Duration(milliseconds: 30000), () {
      if (mounted) setState(() => _fabExpanded = false);
    });
  }

  @override
  void dispose() {
    _fabSlideCtrl.dispose();
    _pulseCtrl.dispose();
    super.dispose();
  }

  void _openChat() {
    Navigator.push(
      context,
      PageRouteBuilder(
        transitionDuration: const Duration(milliseconds: 350),
        reverseTransitionDuration: const Duration(milliseconds: 300),
        pageBuilder: (_, __, ___) => AgentChatScreen(),
        transitionsBuilder: (_, anim, __, child) {
          return SlideTransition(
            position: Tween<Offset>(begin: const Offset(1, 0), end: Offset.zero)
                .animate(
                  CurvedAnimation(parent: anim, curve: Curves.easeOutCubic),
                ),
            child: child,
          );
        },
      ),
    );
  }

  // ─── Nav Items ────────────────────────────────────────
  static const _navItems = <_NavItemData>[
    _NavItemData(Icons.home_outlined, Icons.home_rounded, 'Home'),
    _NavItemData(
      Icons.compass_calibration_outlined,
      Icons.compass_calibration,
      'Explore',
    ),
    _NavItemData(
      Icons.pie_chart_outline_rounded,
      Icons.pie_chart_rounded,
      'Portfolio',
    ),
    _NavItemData(
      Icons.favorite_border_rounded,
      Icons.favorite_rounded,
      'Saved',
    ),
    _NavItemData(Icons.person_outline_rounded, Icons.person_rounded, 'Profile'),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Stack(
        children: [
          IndexedStack(index: _currentIndex, children: _screens),

          // ── Floating AI Pill ──
          _buildAiFab(),
        ],
      ),
      bottomNavigationBar: _buildBottomNav(),
    );
  }

  // ─── AI Floating Pill (Draggable) ────────────────────────
  double _fabX = 12; // distance from right
  double _fabY = 100; // distance from bottom

  Widget _buildAiFab() {
    return _AnimatedListenable(
      listenable: Listenable.merge([_fabSlideCtrl, _pulseCtrl]),
      builder: (context, child) {
        final slideProgress = Curves.elasticOut.transform(
          _fabSlideCtrl.value.clamp(0.0, 1.0),
        );
        final xOffset = 140.0 * (1 - slideProgress);
        final glowAlpha = 0.15 + (_pulseCtrl.value * 0.1);

        return Positioned(
          right: -xOffset + _fabX,
          bottom: _fabY,
          child: GestureDetector(
            onTap: _openChat,
            onPanUpdate: (details) {
              setState(() {
                _fabX -= details.delta.dx;
                _fabY -= details.delta.dy;
                // Clamp to screen bounds
                final size = MediaQuery.of(context).size;
                _fabX = _fabX.clamp(0.0, size.width - 80);
                _fabY = _fabY.clamp(20.0, size.height - 180);
              });
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 400),
              curve: Curves.easeOutCubic,
              padding: EdgeInsets.fromLTRB(
                _fabExpanded ? 14 : 12,
                _fabExpanded ? 10 : 12,
                _fabExpanded ? 8 : 12,
                _fabExpanded ? 10 : 12,
              ),
              decoration: BoxDecoration(
                color: const Color(0xFF0F172A).withValues(alpha: 0.92),
                borderRadius: BorderRadius.circular(_fabExpanded ? 24 : 28),
                border: Border.all(
                  color: AppColors.gold.withValues(alpha: 0.35),
                  width: 1,
                ),
                boxShadow: [
                  BoxShadow(
                    color: AppColors.gold.withValues(alpha: glowAlpha),
                    blurRadius: 18,
                    spreadRadius: 1,
                    offset: const Offset(0, 3),
                  ),
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.4),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Label
                  AnimatedSize(
                    duration: const Duration(milliseconds: 400),
                    curve: Curves.easeOutCubic,
                    child: _fabExpanded
                        ? Padding(
                            padding: const EdgeInsets.only(right: 10),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Need help?',
                                  style: TextStyle(
                                    color: AppColors.gold,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                                const SizedBox(height: 1),
                                Text(
                                  'Ask our AI assistant',
                                  style: TextStyle(
                                    color: const Color(0xFF94A3B8),
                                    fontSize: 11,
                                  ),
                                ),
                              ],
                            ),
                          )
                        : const SizedBox.shrink(),
                  ),
                  // Icon
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [AppColors.gold, AppColors.goldLight],
                      ),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.auto_awesome_rounded,
                      color: Color(0xFF0A0E1A),
                      size: 20,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  // ─── Bottom Nav ────────────────────────────────────────
  Widget _buildBottomNav() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        border: Border(
          top: BorderSide(
            color: AppColors.border.withValues(alpha: 0.4),
            width: 0.5,
          ),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        child: SizedBox(
          height: 60,
          child: Row(
            children: List.generate(_navItems.length, (i) {
              final item = _navItems[i];
              final selected = _currentIndex == i;
              return Expanded(
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () {
                    setState(() => _currentIndex = i);
                    if (i == 0) {
                      _listingsKey.currentState?.refreshDefaultRegion();
                    }
                    if (i == 1) {
                      _exploreKey.currentState?.refreshDefaultRegion();
                    }
                  },
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Active indicator dot
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          height: 3,
                          width: selected ? 20 : 0,
                          margin: const EdgeInsets.only(bottom: 6),
                        ),
                        Icon(
                          selected ? item.activeIcon : item.icon,
                          color: selected
                              ? AppColors.gold
                              : AppColors.textMuted.withValues(alpha: 0.65),
                          size: 26,
                        ),
                        const SizedBox(height: 3),
                        Text(
                          item.label,
                          style: TextStyle(
                            color: selected
                                ? AppColors.gold
                                : AppColors.textMuted.withValues(alpha: 0.65),
                            fontSize: 11,
                            fontWeight: selected
                                ? FontWeight.w600
                                : FontWeight.w400,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}

class _NavItemData {
  final IconData icon;
  final IconData activeIcon;
  final String label;
  const _NavItemData(this.icon, this.activeIcon, this.label);
}

class _AnimatedListenable extends AnimatedWidget {
  const _AnimatedListenable({
    required super.listenable,
    required this.builder,
    this.child,
  });

  final Widget Function(BuildContext context, Widget? child) builder;
  final Widget? child;

  @override
  Widget build(BuildContext context) => builder(context, child);
}
