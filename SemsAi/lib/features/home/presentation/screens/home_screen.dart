import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/features/listings/presentation/screens/listings_screen.dart';
import 'package:SemsAi/features/explore/presentation/screens/explore_screen.dart';
import 'package:SemsAi/features/favorite/presentation/screens/favourite_screen.dart';
import 'package:SemsAi/features/chat/presentation/screens/agent_chat_screen.dart';
import 'package:SemsAi/features/profile/presentation/screens/profile_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  void _goToChat() => setState(() => _currentIndex = 3);

  late final List<Widget> _screens = [
    ListingsScreen(onNavigateToChat: _goToChat),
    ExploreScreen(),
    FavouriteScreen(),
    AgentChatScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: IndexedStack(index: _currentIndex, children: _screens),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          border: Border(top: BorderSide(color: AppColors.border, width: 0.5)),
        ),
        child: NavigationBar(
          backgroundColor: Colors.transparent,
          surfaceTintColor: Colors.transparent,
          indicatorColor: AppColors.gold.withValues(alpha: 0.15),
          selectedIndex: _currentIndex,
          onDestinationSelected: (i) => setState(() => _currentIndex = i),
          labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
          overlayColor: WidgetStateProperty.all(Colors.transparent),
          labelTextStyle: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.selected)) {
              return TextStyle(
                color: AppColors.gold,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              );
            }
            return TextStyle(
              color: AppColors.textMuted,
              fontSize: 11,
              fontWeight: FontWeight.w500,
            );
          }),
          destinations: [
            NavigationDestination(
              icon: Icon(Icons.grid_view_outlined, color: AppColors.textMuted),
              selectedIcon: Icon(
                Icons.grid_view_rounded,
                color: AppColors.gold,
              ),
              label: 'Listings',
            ),
            NavigationDestination(
              icon: Icon(Icons.explore_outlined, color: AppColors.textMuted),
              selectedIcon: Icon(Icons.explore, color: AppColors.gold),
              label: 'Explore',
            ),
            NavigationDestination(
              icon: Icon(Icons.favorite_border, color: AppColors.textMuted),
              selectedIcon: Icon(Icons.favorite, color: AppColors.gold),
              label: 'Favorites',
            ),
            NavigationDestination(
              icon: Icon(Icons.chat_bubble_outline, color: AppColors.textMuted),
              selectedIcon: Icon(Icons.chat_bubble, color: AppColors.gold),
              label: 'AI Chat',
            ),
            NavigationDestination(
              icon: Icon(Icons.person_outline, color: AppColors.textMuted),
              selectedIcon: Icon(Icons.person, color: AppColors.gold),
              label: 'Profile',
            ),
          ],
        ),
      ),
    );
  }
}
