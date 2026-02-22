import 'package:flutter/material.dart';
import 'dart:math';
import 'dart:ui';
import 'package:SemsAi/core/constants/app_colors.dart';

/// Glassmorphism Card for auth screens.
class GlassCard extends StatefulWidget {
  final Widget child;
  const GlassCard({super.key, required this.child});

  @override
  State<GlassCard> createState() => _GlassCardState();
}

class _GlassCardState extends State<GlassCard>
    with SingleTickerProviderStateMixin {
  late AnimationController _borderCtrl;

  static const Color gold = AppColors.gold;
  static const Color accent = AppColors.accent;

  @override
  void initState() {
    super.initState();
    _borderCtrl = AnimationController(
      vsync: this,
      duration: Duration(seconds: 4),
    )..repeat();
  }

  @override
  void dispose() {
    _borderCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _borderCtrl,
      builder: (_, __) {
        return Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(25),
            gradient: SweepGradient(
              center: Alignment.center,
              startAngle: _borderCtrl.value * 2 * pi,
              colors: [
                gold.withValues(alpha: 0.3),
                accent.withValues(alpha: 0.15),
                gold.withValues(alpha: 0.05),
                accent.withValues(alpha: 0.15),
                gold.withValues(alpha: 0.3),
              ],
            ),
          ),
          child: Container(
            margin: EdgeInsets.all(2.5),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20.5),
              color: AppColors.cardBg.withValues(alpha: 0.85),
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(22.5),
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
                child: Container(
                  padding: EdgeInsets.all(28),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(22.5),
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        Colors.white.withValues(alpha: 0.06),
                        Colors.white.withValues(alpha: 0.02),
                      ],
                    ),
                  ),
                  child: widget.child,
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
