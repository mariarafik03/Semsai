import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class ExploreErrorView extends StatelessWidget {
  const ExploreErrorView({super.key, required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appColors.bg,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.wifi_off_rounded,
              color: AppColors.gold.withValues(alpha: 0.5),
              size: 40,
            ),
            SizedBox(height: 12),
            Text(
              AppStrings.loadFailed,
              style: TextStyle(
                color: context.appColors.textPrimary,
                fontSize: 15,
                fontWeight: FontWeight.w600,
              ),
            ),
            SizedBox(height: 16),
            GestureDetector(
              onTap: onRetry,
              child: Container(
                padding: EdgeInsets.symmetric(horizontal: 24, vertical: 10),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [AppColors.gold, context.appColors.goldLight],
                  ),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  AppStrings.retry,
                  style: TextStyle(
                    color: context.appColors.bg,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
