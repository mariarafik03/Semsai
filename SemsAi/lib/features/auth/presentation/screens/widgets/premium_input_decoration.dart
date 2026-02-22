import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

/// Premium input decoration for auth forms.
InputDecoration premiumInputDecoration(
  String hint,
  IconData icon, {
  Widget? suffix,
}) {
  const gold = AppColors.gold;
  return InputDecoration(
    hintText: hint,
    hintStyle: TextStyle(
      color: Colors.white.withValues(alpha: 0.5),
      fontSize: 14,
      fontWeight: FontWeight.w300,
    ),
    prefixIcon: ShaderMask(
      shaderCallback: (bounds) => LinearGradient(
        colors: [AppColors.gold, AppColors.accent],
      ).createShader(bounds),
      child: Icon(icon, color: Colors.white, size: 20),
    ),
    suffixIcon: suffix,
    filled: true,
    fillColor: Colors.white.withValues(alpha: 0.04),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: BorderSide(color: gold.withValues(alpha: 0.08)),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: BorderSide(color: gold.withValues(alpha: 0.08)),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: BorderSide(color: gold.withValues(alpha: 0.5), width: 1.5),
    ),
    errorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: BorderSide(color: Colors.red.withValues(alpha: 0.4)),
    ),
    focusedErrorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: BorderSide(
        color: Colors.red.withValues(alpha: 0.6),
        width: 1.5,
      ),
    ),
    contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 16),
  );
}
