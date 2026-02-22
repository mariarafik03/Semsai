import 'package:flutter/material.dart';
import 'dart:math';
import 'dart:ui';
import 'package:SemsAi/core/constants/app_colors.dart';

/// Shared premium animated background for auth screens.
class AuthBackground extends StatefulWidget {
  final Widget child;
  const AuthBackground({super.key, required this.child});

  @override
  State<AuthBackground> createState() => _AuthBackgroundState();
}

class _AuthBackgroundState extends State<AuthBackground>
    with TickerProviderStateMixin {
  static const Color gold = AppColors.gold;
  static const Color accent = AppColors.accent;
  static const Color bg = AppColors.bg;

  late AnimationController _orbController;
  late AnimationController _scanController;

  @override
  void initState() {
    super.initState();
    _orbController = AnimationController(
      vsync: this,
      duration: Duration(seconds: 10),
    )..repeat();
    _scanController = AnimationController(
      vsync: this,
      duration: Duration(seconds: 4),
    )..repeat();
  }

  @override
  void dispose() {
    _orbController.dispose();
    _scanController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    return Scaffold(
      backgroundColor: bg,
      body: Stack(
        children: [
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [AppColors.bg, AppColors.cardBg, AppColors.bg],
              ),
            ),
          ),

          // ── Animated gradient orbs (three large glowing circles that slowly move around)
          AnimatedBuilder(
            animation: _orbController,
            builder: (_, __) {
              final t = _orbController.value;
              return Stack(
                children: [
                  Positioned(
                    left: size.width * (0.15 + 0.15 * sin(t * 2 * pi)),
                    top: size.height * (0.1 + 0.08 * cos(t * 2 * pi)),
                    child: _GlowOrb(
                      radius: 120,
                      color: gold.withValues(alpha: 0.06),
                    ),
                  ),
                  Positioned(
                    right: size.width * (0.1 + 0.1 * cos(t * 2 * pi * 0.7)),
                    top: size.height * (0.25 + 0.1 * sin(t * 2 * pi * 0.7)),
                    child: _GlowOrb(
                      radius: 90,
                      color: accent.withValues(alpha: 0.04),
                    ),
                  ),
                  Positioned(
                    left: size.width * (0.4 + 0.2 * sin(t * 2 * pi * 0.5)),
                    bottom: size.height * (0.15 + 0.05 * cos(t * 2 * pi * 0.5)),
                    child: _GlowOrb(
                      radius: 100,
                      color: gold.withValues(alpha: 0.05),
                    ),
                  ),
                ],
              );
            },
          ),

          // ── Neural network nodes(stars in the sky)
          ...List.generate(
            20,
            (i) => _NeuralNode(index: i, gold: gold, accent: accent),
          ),

          // ── Scan line
          AnimatedBuilder(
            animation: _scanController,
            builder: (_, __) {
              return Positioned(
                left: 0,
                right: 0,
                top: size.height * _scanController.value,
                child: Container(
                  height: 1,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        Colors.transparent,
                        gold.withValues(alpha: 0.08),
                        accent.withValues(alpha: 0.06),
                        Colors.transparent,
                      ],
                    ),
                  ),
                ),
              );
            },
          ),

          // ── City skyline at bottom
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: CustomPaint(
              size: Size(size.width, 180),
              painter: _SkylinePainter(
                buildingColor: AppColors.buildingColor,
                windowColor: gold,
              ),
            ),
          ),

          // ── Skyline glow
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            height: 200,
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.bottomCenter,
                  end: Alignment.topCenter,
                  colors: [gold.withValues(alpha: 0.05), Colors.transparent],
                ),
              ),
            ),
          ),

          // ── Content
          widget.child,
        ],
      ),
    );
  }
}

// ─── Glow Orb ──────────────────────────────────────────────────

class _GlowOrb extends StatelessWidget {
  final double radius;
  final Color color;
  const _GlowOrb({required this.radius, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: radius * 2,
      height: radius * 2,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [color, color.withValues(alpha: 0.01)],
        ),
      ),
    );
  }
}

// ─── Neural Node (AI data point) ───────────────────────────────

class _NeuralNode extends StatefulWidget {
  final int index;
  final Color gold;
  final Color accent;
  const _NeuralNode({
    required this.index,
    required this.gold,
    required this.accent,
  });

  @override
  State<_NeuralNode> createState() => _NeuralNodeState();
}

class _NeuralNodeState extends State<_NeuralNode>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late double _x, _y, _size;
  late Color _color;

  @override
  void initState() {
    super.initState();
    final rng = Random(widget.index * 42);
    _x = rng.nextDouble();
    _y = rng.nextDouble() * 0.7;
    _size = 1.5 + rng.nextDouble() * 2.5;
    _color = rng.nextBool() ? widget.gold : widget.accent;
    _ctrl = AnimationController(
      vsync: this,
      duration: Duration(milliseconds: 2000 + rng.nextInt(3000)),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final sz = MediaQuery.of(context).size;
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        final opacity = 0.1 + 0.4 * _ctrl.value;
        return Positioned(
          left: _x * sz.width,
          top: _y * sz.height,
          child: Container(
            width: _size + _size * 0.3 * _ctrl.value,
            height: _size + _size * 0.3 * _ctrl.value,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _color.withValues(alpha: opacity),
              boxShadow: [
                BoxShadow(
                  color: _color.withValues(alpha: opacity * 0.5),
                  blurRadius: 8,
                  spreadRadius: 2,
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

// ─── City Skyline Painter ──────────────────────────────────────

class _SkylinePainter extends CustomPainter {
  final Color buildingColor;
  final Color windowColor;

  _SkylinePainter({required this.buildingColor, required this.windowColor});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = buildingColor;
    final windowPaint = Paint()..color = windowColor.withValues(alpha: 0.15);
    final rng = Random(99);

    final buildings = <List<double>>[
      [0.0, 0.08, 0.55],
      [0.06, 0.06, 0.40],
      [0.11, 0.09, 0.70],
      [0.18, 0.05, 0.35],
      [0.22, 0.07, 0.60],
      [0.28, 0.10, 0.85],
      [0.36, 0.06, 0.45],
      [0.41, 0.08, 0.65],
      [0.47, 0.05, 0.38],
      [0.51, 0.09, 0.75],
      [0.58, 0.06, 0.42],
      [0.63, 0.08, 0.58],
      [0.69, 0.07, 0.90],
      [0.75, 0.06, 0.48],
      [0.80, 0.09, 0.68],
      [0.87, 0.06, 0.40],
      [0.92, 0.08, 0.55],
    ];

    for (final b in buildings) {
      final x = b[0] * size.width;
      final w = b[1] * size.width;
      final h = b[2] * size.height;
      final rect = Rect.fromLTWH(x, size.height - h, w, h);

      canvas.drawRect(rect, paint);

      if (b[2] > 0.65) {
        final antennaX = x + w / 2;
        canvas.drawLine(
          Offset(antennaX, size.height - h),
          Offset(antennaX, size.height - h - 12),
          Paint()
            ..color = buildingColor
            ..strokeWidth = 1.5,
        );
      }

      const winSize = 2.0;
      const winGap = 5.0;
      for (
        double wy = size.height - h + 8;
        wy < size.height - 6;
        wy += winGap
      ) {
        for (double wx = x + 3; wx < x + w - 3; wx += winGap) {
          if (rng.nextDouble() > 0.4) {
            final lit = rng.nextDouble() > 0.6;
            canvas.drawRect(
              Rect.fromLTWH(wx, wy, winSize, winSize),
              lit
                  ? (Paint()
                      ..color = windowColor.withValues(
                        alpha: 0.3 + rng.nextDouble() * 0.3,
                      ))
                  : windowPaint,
            );
          }
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
