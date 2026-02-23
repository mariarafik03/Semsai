import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

/// Small colored tag overlay used on property cards.
class TagOverlay extends StatelessWidget {
  final String text;
  final Color? color;

  const TagOverlay({super.key, required this.text, this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: (color ?? AppColors.gold).withValues(alpha: 0.85),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
