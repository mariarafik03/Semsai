import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/core/widgets/shimmer_loading.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class ExploreLoadingView extends StatelessWidget {
  const ExploreLoadingView({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            Shimmer(
              child: Container(
                height: 46,
                margin: const EdgeInsets.fromLTRB(12, 6, 12, 2),
                decoration: BoxDecoration(
                  color: context.appColors.cardBg,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: context.appColors.border),
                ),
              ),
            ),
            SizedBox(
              height: 44,
              child: Shimmer(
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  children: List.generate(
                    5,
                    (_) => Container(
                      width: 80,
                      margin: const EdgeInsets.only(right: 8),
                      decoration: BoxDecoration(
                        color: context.appColors.border.withValues(alpha: 0.3),
                        borderRadius: BorderRadius.circular(20),
                      ),
                    ),
                  ),
                ),
              ),
            ),
            Expanded(
              flex: 55,
              child: Container(
                color: context.appColors.bg,
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircularProgressIndicator(
                        color: AppColors.gold,
                        strokeWidth: 2.5,
                      ),
                      SizedBox(height: 14),
                      Text(
                        AppStrings.loadingProperties,
                        style: TextStyle(
                          color: context.appColors.textMuted,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            Expanded(
              flex: 45,
              child: Container(
                decoration: BoxDecoration(
                  color: context.appColors.cardBg,
                  borderRadius: BorderRadius.vertical(top: Radius.circular(22)),
                ),
                child: Column(
                  children: [
                    Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: Container(
                        width: 36,
                        height: 4,
                        decoration: BoxDecoration(
                          color: AppColors.gold.withValues(alpha: 0.3),
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                    ),
                    Expanded(
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        padding: EdgeInsets.fromLTRB(16, 16, 16, 12),
                        children: List.generate(
                          4,
                          (_) => PropertyCardSkeleton(),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
