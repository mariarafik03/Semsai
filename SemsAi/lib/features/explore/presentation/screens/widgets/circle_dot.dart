import 'package:flutter/material.dart';

/// Pulsing circle dot used as a map marker.
class CircleDot extends StatefulWidget {
  final Color color;
  final bool isSelected;

  const CircleDot({super.key, required this.color, required this.isSelected});

  @override
  State<CircleDot> createState() => _CircleDotState();
}

class _CircleDotState extends State<CircleDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _pulse;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );
    _pulse = Tween<double>(
      begin: 1.0,
      end: 1.5,
    ).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
    if (widget.isSelected) _ctrl.repeat(reverse: true);
  }

  @override
  void didUpdateWidget(covariant CircleDot old) {
    super.didUpdateWidget(old);
    if (widget.isSelected && !old.isSelected) {
      _ctrl.repeat(reverse: true);
    } else if (!widget.isSelected && old.isSelected) {
      _ctrl.stop();
      _ctrl.reset();
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulse,
      builder: (_, child) {
        return Stack(
          alignment: Alignment.center,
          children: [
            if (widget.isSelected)
              Container(
                width: 28 * _pulse.value,
                height: 28 * _pulse.value,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: widget.color.withValues(
                    alpha: 0.15 * (2.0 - _pulse.value),
                  ),
                ),
              ),
            Container(
              width: widget.isSelected ? 18 : 12,
              height: widget.isSelected ? 18 : 12,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: widget.color.withValues(
                  alpha: widget.isSelected ? 0.95 : 0.75,
                ),
                border: Border.all(
                  color: Colors.white.withValues(
                    alpha: widget.isSelected ? 0.85 : 0.4,
                  ),
                  width: widget.isSelected ? 2.5 : 1.5,
                ),
                boxShadow: [
                  BoxShadow(
                    color: widget.color.withValues(
                      alpha: widget.isSelected ? 0.5 : 0.25,
                    ),
                    blurRadius: widget.isSelected ? 12 : 6,
                    spreadRadius: widget.isSelected ? 2 : 0,
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}
