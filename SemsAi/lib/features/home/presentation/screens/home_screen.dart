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

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  void _goToChat() => setState(() => _currentIndex = 2);

  final _listingsKey = GlobalKey<ListingsScreenState>();
  final _exploreKey = GlobalKey<ExploreScreenState>();

  late final List<Widget> _screens = [
    ListingsScreen(key: _listingsKey, onNavigateToChat: _goToChat),
    ExploreScreen(key: _exploreKey),
    AgentChatScreen(),
    FavouriteScreen(),
    PortfolioScreen(),
    ProfileScreen(),
  ];

  Widget _buildNavItem(
    IconData icon,
    IconData activeIcon,
    String label,
    int index,
  ) {
    final bool isSelected = _currentIndex == index;
    return Expanded(
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () {
          setState(() => _currentIndex = index);
          if (index == 0) _listingsKey.currentState?.refreshDefaultRegion();
          if (index == 1) _exploreKey.currentState?.refreshDefaultRegion();
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                isSelected ? activeIcon : icon,
                color: isSelected ? AppColors.gold : AppColors.textMuted,
                size: 24,
              ),
              SizedBox(height: 4),
              Text(
                label,
                style: TextStyle(
                  color: isSelected ? AppColors.gold : AppColors.textMuted,
                  fontSize: isSelected ? 12 : 11,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bool isChatSelected = _currentIndex == 2;
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: IndexedStack(index: _currentIndex, children: _screens),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          border: Border(top: BorderSide(color: AppColors.border, width: 0.5)),
        ),
        child: SafeArea(
          child: SizedBox(
            height: 80,
            child: Row(
              children: [
                _buildNavItem(
                  Icons.grid_view_outlined,
                  Icons.grid_view_rounded,
                  'Listings',
                  0,
                ),
                _buildNavItem(
                  Icons.explore_outlined,
                  Icons.explore,
                  'Explore',
                  1,
                ),

                Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _currentIndex = 2),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Transform.translate(
                          offset: const Offset(0, -16),
                          child: Container(
                            width: 56,
                            height: 56,
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                                colors: isChatSelected
                                    ? [AppColors.gold, AppColors.goldLight]
                                    : [
                                        AppColors.gold.withValues(alpha: 0.85),
                                        AppColors.goldLight.withValues(
                                          alpha: 0.85,
                                        ),
                                      ],
                              ),
                              shape: BoxShape.circle,
                              boxShadow: [
                                BoxShadow(
                                  color: AppColors.gold.withValues(
                                    alpha: isChatSelected ? 0.5 : 0.3,
                                  ),
                                  blurRadius: isChatSelected ? 18 : 12,
                                  spreadRadius: isChatSelected ? 2 : 0,
                                  offset: const Offset(0, 4),
                                ),
                                BoxShadow(
                                  color: AppColors.gold.withValues(alpha: 0.15),
                                  blurRadius: 30,
                                  spreadRadius: 4,
                                ),
                              ],
                            ),
                            child: Icon(
                              isChatSelected
                                  ? Icons.smart_toy_rounded
                                  : Icons.smart_toy_outlined,
                              color: AppColors.bg,
                              size: 28,
                            ),
                          ),
                        ),
                        Transform.translate(
                          offset: const Offset(0, -12),
                          child: Text(
                            'AI Chat',
                            style: TextStyle(
                              color: isChatSelected
                                  ? AppColors.gold
                                  : AppColors.textMuted,
                              fontSize: isChatSelected ? 12 : 11,
                              fontWeight: isChatSelected
                                  ? FontWeight.w600
                                  : FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                _buildNavItem(
                  Icons.favorite_border,
                  Icons.favorite,
                  'Favorites',
                  3,
                ),
                _buildNavItem(
                  Icons.assessment_outlined,
                  Icons.assessment,
                  'Portfolio',
                  4,
                ),
                _buildNavItem(Icons.person_outline, Icons.person, 'Profile', 5),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
