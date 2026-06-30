import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class AiPromptBanner extends StatefulWidget {
  const AiPromptBanner({super.key, required this.onTap, this.onDismiss});

  final VoidCallback onTap;
  final VoidCallback? onDismiss;

  @override
  State<AiPromptBanner> createState() => _AiPromptBannerState();
}

class _AiPromptBannerState extends State<AiPromptBanner>
    with TickerProviderStateMixin {
  late final AnimationController _entranceCtrl;
  late final AnimationController _pulseCtrl;
  late final Animation<Offset> _slideAnim;
  late final Animation<double> _fadeAnim;
  bool _dismissed = false;

  @override
  void initState() {
    super.initState();

    // slide up + fade in after a 2 second delay
    _entranceCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    );
    _slideAnim = Tween<Offset>(begin: const Offset(0, 1.2), end: Offset.zero)
        .animate(
          CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOutBack),
        );
    _fadeAnim = CurvedAnimation(parent: _entranceCtrl, curve: Curves.easeOut);

    // around the border and glow to draw attention
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);
    // start animations after a 10 s delay to avoid interrupting initial browsing
    Future.delayed(const Duration(milliseconds: 10000), () {
      if (mounted) _entranceCtrl.forward();
    });
  }

  @override
  void dispose() {
    _entranceCtrl.dispose();
    _pulseCtrl.dispose();
    super.dispose();
  }

  void _dismiss() {
    _entranceCtrl.reverse().then((_) {
      if (mounted) setState(() => _dismissed = true);
      widget.onDismiss?.call();
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_dismissed) return SizedBox.shrink();

    return SlideTransition(
      position: _slideAnim,
      child: FadeTransition(
        opacity: _fadeAnim,
        child: Padding(
          padding: EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: AnimatedBuilder(
            animation: _pulseCtrl,
            builder: (context, child) {
              final glow = 0.15 + (_pulseCtrl.value * 0.2);
              return Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.gold.withValues(alpha: glow),
                      blurRadius: 20 + (_pulseCtrl.value * 10),
                      spreadRadius: 1,
                    ),
                  ],
                ),
                child: child,
              );
            },
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: widget.onTap,
                borderRadius: BorderRadius.circular(16),
                splashColor: AppColors.gold.withValues(alpha: 0.2),
                child: Ink(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [Color(0xFF1A1F35), Color(0xFF151930)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: AppColors.gold.withValues(alpha: 0.35),
                      width: 1,
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(14, 12, 8, 12),
                    child: Row(
                      children: [
                        _AnimatedAiIcon(controller: _pulseCtrl),
                        SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                'Can\'t decide? 🤔',
                                style: TextStyle(
                                  color: AppColors.gold,
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              SizedBox(height: 2),
                              Text(
                                'Let our AI find the perfect property for you',
                                style: TextStyle(
                                  color: context.appColors.textMuted,
                                  fontSize: 12,
                                  height: 1.3,
                                ),
                              ),
                            ],
                          ),
                        ),
                        SizedBox(width: 4),
                        Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            GestureDetector(
                              onTap: _dismiss,
                              behavior: HitTestBehavior.opaque,
                              child: Padding(
                                padding: EdgeInsets.all(4),
                                child: Icon(
                                  Icons.close_rounded,
                                  color: context.appColors.textMuted.withValues(
                                    alpha: 0.5,
                                  ),
                                  size: 22,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _AnimatedAiIcon extends StatelessWidget {
  const _AnimatedAiIcon({required this.controller});

  final AnimationController controller;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, child) {
        final rotation = math.sin(controller.value * math.pi * 2) * 0.05;
        final scale = 1.0 + (controller.value * 0.08);
        return Transform.scale(
          scale: scale,
          child: Transform.rotate(angle: rotation, child: child),
        );
      },
      child: Container(
        width: 42,
        height: 42,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [AppColors.gold, context.appColors.goldLight],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: AppColors.gold.withValues(alpha: 0.3),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Icon(Icons.smart_toy_rounded, color: context.appColors.bg, size: 22),
      ),
    );
  }
}

class AnimatedBuilder extends AnimatedWidget {
  const AnimatedBuilder({
    super.key,
    required Animation<double> animation,
    required this.builder,
    this.child,
  }) : super(listenable: animation);

  final Widget Function(BuildContext context, Widget? child) builder;
  final Widget? child;

  @override
  Widget build(BuildContext context) => builder(context, child);
}
