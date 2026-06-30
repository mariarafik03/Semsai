import 'package:flutter/material.dart';
import 'package:SemsAi/core/theme/app_themes.dart';

/// Static fallback colors (dark theme defaults) kept for
/// any edge-case widget that doesn't have a BuildContext available.
class AppColors {
  AppColors._();

  // ── Brand / accent ─────────────────────────────────────────────────
  static const Color gold       = Color(0xFFD4A44A);
  static const Color accent     = Color(0xFF2EC4F6);
  static const Color goldLight  = Color(0xFFE8C675);
  static const Color goldLighter= Color(0xFFF5E6B8);

  // ── Dark-mode defaults (used by widgets without context) ────────────
  static const Color bg           = Color(0xFF0A0E1A);
  static const Color cardBg       = Color(0xFF0F1528);
  static const Color border       = Color(0xFF1A2035);
  static const Color textPrimary  = Color(0xFFE8DCC8);
  static const Color textMuted    = Color(0xFF6B7280);
  static const Color buildingColor= Color(0xFF111627);
  static const Color darkGray     = Color(0xFF374151);

  // ── Helper: get the theme-aware palette from context ────────────────
  /// Use this in every build() method:
  ///   final c = AppColors.of(context);
  ///   color: c.bg
  static AppColorExtension of(BuildContext context) =>
      context.appColors;

  // ── Shared palette (same in both themes) ───────────────────────────
  static const List<Color> areaPalette = [
    gold,
    Color(0xFF4CAF50),
    accent,
    Color(0xFFE040FB),
    Color(0xFFFF7043),
    Color(0xFF42A5F5),
    Color(0xFFAB47BC),
    Color(0xFF66BB6A),
    Color(0xFFFFCA28),
    Color(0xFFEF5350),
  ];
}
