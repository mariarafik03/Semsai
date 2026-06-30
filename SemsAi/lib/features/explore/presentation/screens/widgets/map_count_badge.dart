import 'dart:ui';
import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class MapCountBadge extends StatelessWidget {
  const MapCountBadge({super.key, required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 8, sigmaY: 8),
        child: Container(
          padding: EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: context.appColors.bg.withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: context.appColors.border.withValues(alpha: 0.4)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.location_on_rounded, color: AppColors.gold, size: 13),
              SizedBox(width: 4),
              Text(
                '$count compounds',
                style: TextStyle(
                  color: context.appColors.textPrimary,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
