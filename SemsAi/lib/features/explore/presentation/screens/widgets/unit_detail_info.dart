import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/favorite/presentation/cubit/favorite_cubit.dart';
import 'package:SemsAi/features/favorite/presentation/cubit/favorite_state.dart';

// ── Title Row ──────────────────────────────────────────────────

class UnitTitleRow extends StatelessWidget {
  const UnitTitleRow({super.key, required this.unit});

  final CompoundUnit unit;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                unit.compoundName ?? unit.name,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 22,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (unit.location != null && unit.location!.isNotEmpty) ...[
                const SizedBox(height: 4),
                Row(
                  children: [
                    const Icon(
                      Icons.location_on_outlined,
                      color: AppColors.textMuted,
                      size: 15,
                    ),
                    const SizedBox(width: 3),
                    Flexible(
                      child: Text(
                        unit.location!,
                        style: const TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 14,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
        const SizedBox(width: 12),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            BlocBuilder<FavoriteCubit, FavoriteState>(
              builder: (context, favState) {
                final isFav =
                    favState is FavoriteLoaded && favState.isFavorite(unit.id);
                return GestureDetector(
                  onTap: () {
                    context.read<FavoriteCubit>().toggleFavorite(unit);
                  },
                  child: Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: AppColors.cardBg,
                      shape: BoxShape.circle,
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Icon(
                      isFav
                          ? Icons.favorite_rounded
                          : Icons.favorite_border_rounded,
                      color: isFav ? Colors.redAccent : AppColors.textMuted,
                      size: 18,
                    ),
                  ),
                );
              },
            ),
            const SizedBox(width: 8),
            _actionIcon(Icons.ios_share_rounded),
          ],
        ),
      ],
    );
  }

  Widget _actionIcon(IconData icon) {
    return Container(
      width: 38,
      height: 38,
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        shape: BoxShape.circle,
        border: Border.all(color: AppColors.border),
      ),
      child: Icon(icon, color: AppColors.textMuted, size: 18),
    );
  }
}

// ── Price Section ──────────────────────────────────────────────

class UnitPriceSection extends StatelessWidget {
  const UnitPriceSection({super.key, required this.price, this.rangeText});

  final double? price;
  final String? rangeText;

  @override
  Widget build(BuildContext context) {
    if (price == null) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          _fmtPriceFull(price!),
          style: const TextStyle(
            color: AppColors.gold,
            fontSize: 24,
            fontWeight: FontWeight.w800,
          ),
        ),
        if (rangeText != null) ...[
          const SizedBox(height: 2),
          Text(
            rangeText!,
            style: TextStyle(
              color: AppColors.textMuted.withValues(alpha: 0.8),
              fontSize: 13,
            ),
          ),
        ],
      ],
    );
  }

  static String _fmtPriceFull(double p) {
    if (p >= 1000000) {
      final v = p / 1000000;
      return '${v.toStringAsFixed(v == v.roundToDouble() ? 0 : 1)}M EGP';
    }
    if (p >= 1000) return '${(p / 1000).toStringAsFixed(0)}K EGP';
    return '${p.toStringAsFixed(0)} EGP';
  }
}

// ── Specs Row ──────────────────────────────────────────────────

class UnitSpecsRow extends StatelessWidget {
  const UnitSpecsRow({super.key, required this.unit});

  final CompoundUnit unit;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          if (unit.bedrooms != null)
            _item(Icons.bed_rounded, '${unit.bedrooms}', AppStrings.beds),
          if (unit.bathrooms != null)
            _item(
              Icons.bathtub_outlined,
              '${unit.bathrooms}',
              AppStrings.baths,
            ),
          if (unit.displayArea != null)
            _item(
              Icons.square_foot_rounded,
              '${unit.displayArea!.toInt()}m²',
              AppStrings.area,
            ),
          _item(
            Icons.home_work_rounded,
            unit.type.isNotEmpty ? _capitalize(unit.type) : '—',
            AppStrings.type,
          ),
        ],
      ),
    );
  }

  Widget _item(IconData icon, String value, String label) {
    return Expanded(
      child: Column(
        children: [
          Icon(icon, color: AppColors.textMuted, size: 20),
          const SizedBox(height: 6),
          Text(
            value,
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 15,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
          ),
        ],
      ),
    );
  }

  static String _capitalize(String s) {
    if (s.isEmpty) return s;
    return s
        .replaceAll('_', ' ')
        .split(' ')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }
}

// ── Info Card ──────────────────────────────────────────────────

class UnitInfoCard extends StatelessWidget {
  const UnitInfoCard({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppColors.gold, size: 22),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    color: AppColors.textMuted,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Extra Details ──────────────────────────────────────────────

class UnitExtraDetails extends StatelessWidget {
  const UnitExtraDetails({super.key, this.finishing, this.saleType});

  final String? finishing;
  final String? saleType;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Wrap(
        spacing: 24,
        runSpacing: 10,
        children: [
          if (finishing != null)
            _item(
              Icons.format_paint_rounded,
              AppStrings.finishing,
              _capitalize(finishing!),
            ),
          if (saleType != null)
            _item(
              Icons.sell_rounded,
              AppStrings.saleType,
              _capitalize(saleType!),
            ),
        ],
      ),
    );
  }

  Widget _item(IconData icon, String label, String value) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: AppColors.accent, size: 16),
        const SizedBox(width: 6),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: const TextStyle(color: AppColors.textMuted, fontSize: 10),
            ),
            Text(
              value,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ],
    );
  }

  static String _capitalize(String s) {
    if (s.isEmpty) return s;
    return s
        .replaceAll('_', ' ')
        .split(' ')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }
}
