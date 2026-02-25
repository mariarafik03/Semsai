import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

class AppLoadingIndicator extends StatelessWidget {
  const AppLoadingIndicator({
    super.key,
    this.size = 36,
    this.strokeWidth = 2.5,
    this.color = AppColors.gold,
  });

  final double size;
  final double strokeWidth;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CircularProgressIndicator(strokeWidth: strokeWidth, color: color),
    );
  }
}

class AppLoadingCenter extends StatelessWidget {
  const AppLoadingCenter({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(child: AppLoadingIndicator());
  }
}
