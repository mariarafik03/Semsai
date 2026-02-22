import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

/// Animated shimmer text effect for branding.
class ShimmerText extends StatefulWidget {
  final String text;
  final double fontSize;
  final FontWeight fontWeight;
  final double letterSpacing;

  const ShimmerText({
    super.key,
    required this.text,
    this.fontSize = 34,
    this.fontWeight = FontWeight.w800,
    this.letterSpacing = 4,
  });

  @override
  State<ShimmerText> createState() => _ShimmerTextState();
}

class _ShimmerTextState extends State<ShimmerText>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        return ShaderMask(
          shaderCallback: (bounds) {
            return LinearGradient(
              begin: Alignment(-1.0 + 3.0 * _ctrl.value, 0),
              end: Alignment(0.0 + 3.0 * _ctrl.value, 0),
              colors: const [
                AppColors.gold,
                AppColors.goldLighter,
                AppColors.gold,
              ],
            ).createShader(bounds);
          },
          child: Text(
            widget.text,
            style: TextStyle(
              fontSize: widget.fontSize,
              fontWeight: widget.fontWeight,
              color: Colors.white,
              letterSpacing: widget.letterSpacing,
              shadows: [
                Shadow(
                  color: AppColors.gold.withValues(alpha: 0.5),
                  blurRadius: 30,
                ),
                Shadow(
                  color: AppColors.gold.withValues(alpha: 0.2),
                  blurRadius: 60,
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
