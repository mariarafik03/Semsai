import 'package:flutter/material.dart';

/// Small circular icon button (e.g. heart, share).
class MiniIcon extends StatelessWidget {
  final IconData icon;

  const MiniIcon(this.icon, {super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 26,
      height: 26,
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.4),
        shape: BoxShape.circle,
      ),
      child: Icon(icon, color: Colors.white, size: 14),
    );
  }
}
