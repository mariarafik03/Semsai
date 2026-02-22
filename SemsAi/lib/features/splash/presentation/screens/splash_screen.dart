import 'package:flutter/material.dart';
import 'dart:async';
import 'dart:math';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/auth_background.dart';

class SplashScreen extends StatefulWidget {
  final Widget nextScreen;
  const SplashScreen({super.key, required this.nextScreen});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late AnimationController _glowController;
  late AnimationController _iconController;
  late AnimationController _textController;
  late AnimationController _dotsController;

  late Animation<double> _glowScale;
  late Animation<double> _iconScale;

  static const Color _gold = AppColors.gold;
  static const Color _accent = AppColors.accent;

  @override
  void initState() {
    super.initState();

    _glowController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    );
    _glowScale = Tween<double>(
      begin: 0,
      end: 2,
    ).animate(CurvedAnimation(parent: _glowController, curve: Curves.easeOut));

    _iconController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    _iconScale = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _iconController, curve: Curves.elasticOut),
    );

    _textController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    );

    _dotsController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    );

    _glowController.forward();
    Future.delayed(
      const Duration(milliseconds: 300),
      () => _iconController.forward(),
    );
    Future.delayed(
      const Duration(milliseconds: 500),
      () => _textController.forward(),
    );
    Future.delayed(
      const Duration(milliseconds: 1500),
      () => _dotsController.repeat(),
    );

    Timer(const Duration(milliseconds: 3200), () {
      if (mounted) {
        Navigator.of(context).pushReplacement(
          PageRouteBuilder(
            pageBuilder: (_, __, ___) => widget.nextScreen,
            transitionDuration: const Duration(milliseconds: 600),
            transitionsBuilder: (_, anim, __, child) =>
                FadeTransition(opacity: anim, child: child),
          ),
        );
      }
    });
  }

  @override
  void dispose() {
    _glowController.dispose();
    _iconController.dispose();
    _textController.dispose();
    _dotsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const letters = ['S', 'e', 'm', 's', 'a', 'i'];
    return AuthBackground(
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Glow orb
          AnimatedBuilder(
            animation: _glowScale,
            builder: (_, __) => Transform.scale(
              scale: _glowScale.value,
              child: Container(
                width: 200,
                height: 200,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: _gold.withValues(alpha: 0.15),
                      blurRadius: 100,
                      spreadRadius: 50,
                    ),
                    BoxShadow(
                      color: _accent.withValues(alpha: 0.06),
                      blurRadius: 120,
                      spreadRadius: 60,
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Main content
          Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Logo icon with gradient
              ScaleTransition(
                scale: _iconScale,
                child: Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: _gold.withValues(alpha: 0.2),
                        blurRadius: 40,
                        spreadRadius: 10,
                      ),
                    ],
                  ),
                  child: ShaderMask(
                    shaderCallback: (bounds) => const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [_gold, _accent],
                    ).createShader(bounds),
                    child: const Icon(
                      Icons.apartment_rounded,
                      size: 56,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Animated letters
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(letters.length, (i) {
                  return AnimatedBuilder(
                    animation: _textController,
                    builder: (_, __) {
                      final delay = 0.1 + i * 0.08;
                      final progress = ((_textController.value - delay) / 0.3)
                          .clamp(0.0, 1.0);
                      return Transform.translate(
                        offset: Offset(
                          0,
                          30 * (1 - Curves.easeOut.transform(progress)),
                        ),
                        child: Opacity(
                          opacity: progress,
                          child: ShaderMask(
                            shaderCallback: (bounds) => LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [_gold, _gold.withValues(alpha: 0.8)],
                            ).createShader(bounds),
                            child: Text(
                              letters[i],
                              style: TextStyle(
                                fontSize: 48,
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                                letterSpacing: 2,
                                shadows: [
                                  Shadow(
                                    color: _gold.withValues(alpha: 0.5),
                                    blurRadius: 30,
                                  ),
                                  Shadow(
                                    color: _gold.withValues(alpha: 0.2),
                                    blurRadius: 60,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      );
                    },
                  );
                }),
              ),
              const SizedBox(height: 16),

              // Subtitle
              AnimatedBuilder(
                animation: _textController,
                builder: (_, __) {
                  final progress = ((_textController.value - 0.6) / 0.4).clamp(
                    0.0,
                    1.0,
                  );
                  return Opacity(
                    opacity: progress,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          width: 20,
                          height: 1,
                          color: _gold.withValues(alpha: 0.3 * progress),
                        ),
                        const SizedBox(width: 10),
                        Text(
                          AppStrings.tagLine,
                          style: TextStyle(
                            fontSize: 10,
                            color: _accent.withValues(alpha: 0.6 * progress),
                            letterSpacing: 3,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Container(
                          width: 20,
                          height: 1,
                          color: _gold.withValues(alpha: 0.3 * progress),
                        ),
                      ],
                    ),
                  );
                },
              ),
              const SizedBox(height: 48),

              // Loading dots
              AnimatedBuilder(
                animation: _dotsController,
                builder: (_, __) => Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(3, (i) {
                    final delay = i * 0.2;
                    final value = ((_dotsController.value - delay) % 1.0).clamp(
                      0.0,
                      1.0,
                    );
                    final scale = 0.8 + 0.4 * sin(value * pi);
                    final opacity = 0.3 + 0.7 * sin(value * pi);
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: Transform.scale(
                        scale: scale,
                        child: Opacity(
                          opacity: opacity,
                          child: Container(
                            width: 8,
                            height: 8,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: LinearGradient(
                                colors: [_gold, _accent.withValues(alpha: 0.6)],
                              ),
                            ),
                          ),
                        ),
                      ),
                    );
                  }),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
