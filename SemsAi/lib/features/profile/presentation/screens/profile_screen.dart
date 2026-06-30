import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/core/theme/app_themes.dart';
import 'package:SemsAi/core/theme/theme_cubit.dart';
import 'package:SemsAi/core/routing/app_routes.dart';
import 'package:SemsAi/core/shared_pref/shared_pref_helper.dart';
import 'package:SemsAi/features/auth/presentation/cubit/auth_cubit.dart';
import 'package:SemsAi/features/auth/presentation/cubit/auth_state.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  String _selectedRegion = 'No default';

  static const List<String> _regions = [
    'No default',
    'Cairo',
    'New Cairo',
    '6th of October',
    'New Capital',
    'North Coast',
    'Ain Sokhna',
    'Sheikh Zayed',
  ];

  @override
  void initState() {
    super.initState();
    _loadSavedRegion();
  }

  Future<void> _loadSavedRegion() async {
    final region = await SharedPrefHelper.getDefaultRegion();
    if (mounted) setState(() => _selectedRegion = region);
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;

    return Scaffold(
      backgroundColor: colors.bg,
      body: SafeArea(
        child: BlocBuilder<AuthCubit, AuthState>(
          builder: (context, state) {
            final userName =
                state is AuthAuthenticated ? state.user.name : 'User';
            final userEmail =
                state is AuthAuthenticated ? state.user.email : '';

            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Profile',
                    style: TextStyle(
                      color: colors.textPrimary,
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 28),
                  _buildUserCard(userName, userEmail, colors),
                  const SizedBox(height: 16),
                  _buildThemeToggleCard(colors),
                  const SizedBox(height: 16),
                  _buildRegionCard(colors),
                  const Spacer(),
                  _buildSignOutButton(context, colors),
                  const SizedBox(height: 16),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildUserCard(
      String name, String email, AppColorExtension colors) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: colors.border, width: 0.5),
      ),
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: colors.gold.withValues(alpha: 0.15),
              border: Border.all(
                color: colors.gold.withValues(alpha: 0.4),
                width: 1.5,
              ),
            ),
            child: Icon(
              Icons.person_outline_rounded,
              color: colors.gold,
              size: 28,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: TextStyle(
                    color: colors.textPrimary,
                    fontSize: 17,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  email,
                  style: TextStyle(color: colors.textMuted, fontSize: 13),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildThemeToggleCard(AppColorExtension colors) {
    return BlocBuilder<ThemeCubit, ThemeMode>(
      builder: (context, themeMode) {
        final isDark = themeMode == ThemeMode.dark;

        return Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            color: colors.cardBg,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: colors.border, width: 0.5),
          ),
          child: Row(
            children: [
              // Icon
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: colors.gold.withValues(alpha: 0.12),
                ),
                child: Icon(
                  isDark
                      ? Icons.dark_mode_rounded
                      : Icons.light_mode_rounded,
                  color: colors.gold,
                  size: 20,
                ),
              ),
              const SizedBox(width: 14),
              // Label
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Appearance',
                      style: TextStyle(
                        color: colors.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      isDark ? 'Dark Mode' : 'Light Mode',
                      style: TextStyle(color: colors.textMuted, fontSize: 12),
                    ),
                  ],
                ),
              ),
              // Toggle switch
              Switch.adaptive(
                value: isDark,
                activeColor: colors.gold,
                activeTrackColor: colors.gold.withValues(alpha: 0.3),
                inactiveThumbColor: colors.textMuted,
                inactiveTrackColor: colors.border,
                onChanged: (_) =>
                    context.read<ThemeCubit>().toggleTheme(),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildRegionCard(AppColorExtension colors) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: colors.border, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.location_on_outlined, color: colors.gold, size: 20),
              const SizedBox(width: 8),
              Text(
                'Default Region',
                style: TextStyle(
                  color: colors.textPrimary,
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: colors.bg,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: colors.border, width: 0.5),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _selectedRegion,
                isExpanded: true,
                dropdownColor: colors.cardBg,
                icon: Icon(
                  Icons.keyboard_arrow_down_rounded,
                  color: colors.textMuted,
                ),
                style: TextStyle(color: colors.textPrimary, fontSize: 14),
                items: _regions.map((region) {
                  return DropdownMenuItem<String>(
                    value: region,
                    child: Text(
                      region,
                      style: TextStyle(
                        color: colors.textPrimary,
                        fontSize: 14,
                      ),
                    ),
                  );
                }).toList(),
                onChanged: (value) {
                  if (value != null) {
                    setState(() => _selectedRegion = value);
                    SharedPrefHelper.saveDefaultRegion(value);
                  }
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSignOutButton(
      BuildContext context, AppColorExtension colors) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton.icon(
        onPressed: () => _showSignOutDialog(context, colors),
        icon:
            const Icon(Icons.logout_rounded, color: Colors.white, size: 20),
        label: const Text(
          'Sign Out',
          style: TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFFDC2626),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          elevation: 0,
        ),
      ),
    );
  }

  void _showSignOutDialog(BuildContext context, AppColorExtension colors) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: colors.cardBg,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title:
            Text('Sign Out', style: TextStyle(color: colors.textPrimary)),
        content: Text(
          'Are you sure you want to sign out?',
          style: TextStyle(color: colors.textMuted),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child:
                Text('Cancel', style: TextStyle(color: colors.textMuted)),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              context.read<AuthCubit>().logout();
              Navigator.pushNamedAndRemoveUntil(
                context,
                AppRoutes.login,
                (route) => false,
              );
            },
            child: const Text(
              'Sign Out',
              style: TextStyle(color: Color(0xFFDC2626)),
            ),
          ),
        ],
      ),
    );
  }
}
