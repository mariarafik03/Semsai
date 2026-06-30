import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppThemes {
  AppThemes._();

  // ─────────────────────────── DARK THEME ───────────────────────────
  static ThemeData get dark {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xFF0A0E1A),
      cardColor: const Color(0xFF0F1528),
      dividerColor: const Color(0xFF1A2035),
      primaryColor: const Color(0xFFD4A44A),
      textTheme: GoogleFonts.interTextTheme(ThemeData.dark().textTheme).apply(
        bodyColor: const Color(0xFFE8DCC8),
        displayColor: const Color(0xFFE8DCC8),
      ),
      colorScheme: const ColorScheme.dark(
        primary: Color(0xFFD4A44A),
        secondary: Color(0xFF2EC4F6),
        surface: Color(0xFF0F1528),
        onSurface: Color(0xFFE8DCC8),
        onPrimary: Color(0xFF0A0E1A),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFF0A0E1A),
        foregroundColor: Color(0xFFE8DCC8),
        elevation: 0,
      ),
      iconTheme: const IconThemeData(color: Color(0xFFE8DCC8)),
      extensions: const [AppColorExtension.dark],
    );
  }

  // ─────────────────────────── LIGHT THEME ──────────────────────────
  static ThemeData get light {
    return ThemeData(
      brightness: Brightness.light,
      scaffoldBackgroundColor: const Color(0xFFF5F5F0),
      cardColor: const Color(0xFFFFFFFF),
      dividerColor: const Color(0xFFE0DDD5),
      primaryColor: const Color(0xFFC49A35),
      textTheme: GoogleFonts.interTextTheme(ThemeData.light().textTheme).apply(
        bodyColor: const Color(0xFF1A1A2E),
        displayColor: const Color(0xFF1A1A2E),
      ),
      colorScheme: const ColorScheme.light(
        primary: Color(0xFFC49A35),
        secondary: Color(0xFF1A8FBF),
        surface: Color(0xFFFFFFFF),
        onSurface: Color(0xFF1A1A2E),
        onPrimary: Color(0xFFFFFFFF),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFFF5F5F0),
        foregroundColor: Color(0xFF1A1A2E),
        elevation: 0,
      ),
      iconTheme: const IconThemeData(color: Color(0xFF1A1A2E)),
      extensions: const [AppColorExtension.light],
    );
  }
}

// ─────────────────────── THEME EXTENSION ──────────────────────────────
// Gives access to custom colors like AppColors.bg anywhere via context.
class AppColorExtension extends ThemeExtension<AppColorExtension> {
  final Color bg;
  final Color cardBg;
  final Color border;
  final Color textPrimary;
  final Color textMuted;
  final Color gold;
  final Color goldLight;
  final Color goldLighter;
  final Color accent;
  final Color buildingColor;
  final Color darkGray;

  const AppColorExtension({
    required this.bg,
    required this.cardBg,
    required this.border,
    required this.textPrimary,
    required this.textMuted,
    required this.gold,
    required this.goldLight,
    required this.goldLighter,
    required this.accent,
    required this.buildingColor,
    required this.darkGray,
  });

  static const AppColorExtension dark = AppColorExtension(
    bg: Color(0xFF0A0E1A),
    cardBg: Color(0xFF0F1528),
    border: Color(0xFF1A2035),
    textPrimary: Color(0xFFE8DCC8),
    textMuted: Color(0xFF6B7280),
    gold: Color(0xFFD4A44A),
    goldLight: Color(0xFFE8C675),
    goldLighter: Color(0xFFF5E6B8),
    accent: Color(0xFF2EC4F6),
    buildingColor: Color(0xFF111627),
    darkGray: Color(0xFF374151),
  );

  static const AppColorExtension light = AppColorExtension(
    bg: Color(0xFFF5F5F0),
    cardBg: Color(0xFFFFFFFF),
    border: Color(0xFFE0DDD5),
    textPrimary: Color(0xFF1A1A2E),
    textMuted: Color(0xFF6B7280),
    gold: Color(0xFFC49A35),
    goldLight: Color(0xFFD4B050),
    goldLighter: Color(0xFFE8CC80),
    accent: Color(0xFF1A8FBF),
    buildingColor: Color(0xFFEEEEE8),
    darkGray: Color(0xFF9CA3AF),
  );

  @override
  AppColorExtension copyWith({
    Color? bg, Color? cardBg, Color? border, Color? textPrimary,
    Color? textMuted, Color? gold, Color? goldLight, Color? goldLighter,
    Color? accent, Color? buildingColor, Color? darkGray,
  }) {
    return AppColorExtension(
      bg: bg ?? this.bg,
      cardBg: cardBg ?? this.cardBg,
      border: border ?? this.border,
      textPrimary: textPrimary ?? this.textPrimary,
      textMuted: textMuted ?? this.textMuted,
      gold: gold ?? this.gold,
      goldLight: goldLight ?? this.goldLight,
      goldLighter: goldLighter ?? this.goldLighter,
      accent: accent ?? this.accent,
      buildingColor: buildingColor ?? this.buildingColor,
      darkGray: darkGray ?? this.darkGray,
    );
  }

  @override
  AppColorExtension lerp(AppColorExtension? other, double t) {
    if (other is! AppColorExtension) return this;
    return AppColorExtension(
      bg: Color.lerp(bg, other.bg, t)!,
      cardBg: Color.lerp(cardBg, other.cardBg, t)!,
      border: Color.lerp(border, other.border, t)!,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
      gold: Color.lerp(gold, other.gold, t)!,
      goldLight: Color.lerp(goldLight, other.goldLight, t)!,
      goldLighter: Color.lerp(goldLighter, other.goldLighter, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
      buildingColor: Color.lerp(buildingColor, other.buildingColor, t)!,
      darkGray: Color.lerp(darkGray, other.darkGray, t)!,
    );
  }
}

// ─── Handy extension to access colors without needing to cast ──────────
extension ThemeContextExt on BuildContext {
  AppColorExtension get appColors =>
      Theme.of(this).extension<AppColorExtension>()!;
}
