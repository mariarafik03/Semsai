import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/features/comparison/presentation/cubit/comparison_cubit.dart';
import 'package:SemsAi/features/comparison/presentation/cubit/comparison_state.dart';
import 'package:SemsAi/features/comparison/presentation/screens/comparison_screen.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


/// Floating bottom bar that shows how many units are selected for comparison
/// and allows the user to open the comparison screen.
class ComparisonBottomBar extends StatelessWidget {
  const ComparisonBottomBar({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<ComparisonCubit, ComparisonState>(
      builder: (context, state) {
        if (state.count == 0) return const SizedBox.shrink();
        return _Bar(state: state);
      },
    );
  }
}

class _Bar extends StatefulWidget {
  final ComparisonState state;
  const _Bar({required this.state});

  @override
  State<_Bar> createState() => _BarState();
}

class _BarState extends State<_Bar> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<Offset> _slide;
  late final Animation<double> _fade;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 350),
    );
    _slide = Tween(
      begin: const Offset(0, 1),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic));
    _fade = CurvedAnimation(parent: _ctrl, curve: Curves.easeIn);
    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    return SlideTransition(
      position: _slide,
      child: FadeTransition(
        opacity: _fade,
        child: Container(
          margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF141A2E), Color(0xFF1A2240)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.gold.withValues(alpha: 0.35)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.4),
                blurRadius: 20,
                offset: const Offset(0, 8),
              ),
              BoxShadow(
                color: AppColors.gold.withValues(alpha: 0.08),
                blurRadius: 30,
                spreadRadius: 2,
              ),
            ],
          ),
          child: Row(
            children: [
              // Avatars / thumbnails
              _buildThumbnails(state),
              const SizedBox(width: 12),
              // Info
              Expanded(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${state.count} of 3 selected',
                      style: TextStyle(
                        color: context.appColors.textPrimary,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      state.canCompare
                          ? 'Tap compare to view'
                          : 'Select at least 2',
                      style: TextStyle(
                        color: context.appColors.textMuted.withValues(alpha: 0.8),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
              // Clear button
              GestureDetector(
                onTap: () => context.read<ComparisonCubit>().clear(),
                child: Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.06),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    Icons.close_rounded,
                    color: context.appColors.textMuted,
                    size: 18,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Compare button
              GestureDetector(
                onTap: state.canCompare
                    ? () => Navigator.of(context).push(
                        PageRouteBuilder(
                          transitionDuration: const Duration(milliseconds: 400),
                          reverseTransitionDuration: const Duration(
                            milliseconds: 300,
                          ),
                          pageBuilder: (_, __, ___) => const ComparisonScreen(),
                          transitionsBuilder: (_, anim, __, child) {
                            return SlideTransition(
                              position:
                                  Tween(
                                    begin: const Offset(0, 1),
                                    end: Offset.zero,
                                  ).animate(
                                    CurvedAnimation(
                                      parent: anim,
                                      curve: Curves.easeOutCubic,
                                    ),
                                  ),
                              child: child,
                            );
                          },
                        ),
                      )
                    : null,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 250),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 10,
                  ),
                  decoration: BoxDecoration(
                    gradient: state.canCompare
                        ? LinearGradient(
                            colors: [AppColors.gold, context.appColors.goldLight],
                          )
                        : null,
                    color: state.canCompare
                        ? null
                        : context.appColors.textMuted.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: state.canCompare
                        ? [
                            BoxShadow(
                              color: AppColors.gold.withValues(alpha: 0.35),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ]
                        : null,
                  ),
                  child: Text(
                    'Compare',
                    style: TextStyle(
                      color: state.canCompare
                          ? context.appColors.bg
                          : context.appColors.textMuted,
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildThumbnails(ComparisonState state) {
    return SizedBox(
      width: 52,
      height: 36,
      child: Stack(
        clipBehavior: Clip.none,
        children: List.generate(state.count, (i) {
          final unit = state.units[i];
          final image = unit.images.isNotEmpty ? unit.images.first : null;
          return Positioned(
            left: i * 14.0,
            child: Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.gold, width: 1.5),
                image: image != null
                    ? DecorationImage(
                        image: NetworkImage(image),
                        fit: BoxFit.cover,
                      )
                    : null,
                color: image == null ? context.appColors.border : null,
              ),
              child: image == null
                  ? Icon(
                      Icons.home_outlined,
                      size: 14,
                      color: context.appColors.textMuted,
                    )
                  : null,
            ),
          );
        }),
      ),
    );
  }
}
