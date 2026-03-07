import 'package:SemsAi/core/widgets/tap_scale.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/explore/presentation/screens/unit_detail_screen.dart';
import 'package:SemsAi/features/favorite/presentation/cubit/favorite_cubit.dart';
import 'package:SemsAi/features/favorite/presentation/cubit/favorite_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/utils/price_formatter.dart';
import 'package:SemsAi/core/utils/app_snackbar.dart';
import 'package:SemsAi/core/widgets/app_loading_indicator.dart';

class ListingUnitCard extends StatelessWidget {
  Widget _buildImage(String? image, String heroTag, String? regionTag) {
    return ClipRRect(
      borderRadius: const BorderRadius.only(
        topLeft: Radius.circular(14),
        topRight: Radius.circular(14),
      ),
      child: image != null
          ? Hero(
              tag: heroTag,
              child: Image.network(
                image,
                height: 120,
                width: double.infinity,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) => Container(
                  height: 120,
                  color: Colors.grey[200],
                  child: const Icon(Icons.image, size: 40, color: Colors.grey),
                ),
              ),
            )
          : Container(
              height: 120,
              color: Colors.grey[200],
              child: const Icon(Icons.image, size: 40, color: Colors.grey),
            ),
    );
  }

  const ListingUnitCard({
    super.key,
    required this.unit,
    this.compareSelected = false,
    this.onCompareToggle,
    this.compareDisabled = false,
  });

  final CompoundUnit unit;
  final bool compareSelected;
  final VoidCallback? onCompareToggle;
  final bool compareDisabled;

  // ── Helpers ──

  // Removed: Use PriceFormatter.format instead.

  String _bestPaymentSummary() {
    final plan = unit.bestPlan;
    if (plan == null) return '';
    final parts = <String>[];
    final dp = plan.downPaymentPercent;
    if (dp != null) parts.add('${dp.round()}% DP');
    if (plan.years != null && plan.years! > 0) parts.add('${plan.years}yr');
    if (plan.isCash) parts.add('Cash');
    if (unit.paymentPlans.length > 1) {
      parts.add('+${unit.paymentPlans.length - 1} more');
    }
    return parts.join(' · ');
  }

  static String? _extractRegion(String? location) {
    if (location == null || location.isEmpty) return null;
    final parts = location.split(',').map((p) => p.trim()).toList();
    if (parts.length >= 2) return parts[parts.length - 2];
    return parts.first;
  }

  @override
  Widget build(BuildContext context) {
    final image = unit.images.isNotEmpty ? unit.images.first : null;
    final payment = _bestPaymentSummary();
    final regionTag = _extractRegion(unit.location);
    final heroTag = 'unit_img_${unit.id}';

    return Stack(
      children: [
        TapScale(
          onTap: () => Navigator.of(context).push(
            PageRouteBuilder(
              transitionDuration: const Duration(milliseconds: 400),
              reverseTransitionDuration: const Duration(milliseconds: 350),
              pageBuilder: (_, __, ___) => UnitDetailScreen(unit: unit),
              transitionsBuilder: (_, anim, __, child) {
                return FadeTransition(opacity: anim, child: child);
              },
            ),
          ),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            decoration: BoxDecoration(
              color: compareSelected
                  ? AppColors.gold.withOpacity(0.08)
                  : AppColors.cardBg,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: compareSelected
                    ? AppColors.gold
                    : AppColors.border.withValues(alpha: 0.6),
                width: compareSelected ? 2 : 1,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.2),
                  blurRadius: 8,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildImage(image, heroTag, regionTag),
                _buildInfo(payment),
              ],
            ),
          ),
        ),
        // Tags row
        Positioned(
          bottom: 6,
          left: 6,
          right: 6,
          child: Row(
            children: [
              if (regionTag != null)
                Flexible(child: _tag(regionTag, AppColors.gold)),
              if (regionTag != null) const SizedBox(width: 6),
              Flexible(child: _tag(unit.type, AppColors.accent)),
            ],
          ),
        ),
        // Compare toggle
        if (onCompareToggle != null)
          Positioned(
            top: 6,
            left: 6,
            child: GestureDetector(
              onTap: onCompareToggle,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: compareSelected
                      ? AppColors.gold
                      : Colors.black.withValues(alpha: 0.45),
                  borderRadius: BorderRadius.circular(7),
                  border: compareSelected
                      ? Border.all(color: AppColors.goldLight, width: 1)
                      : null,
                ),
                child: Icon(
                  compareSelected
                      ? Icons.compare_arrows_rounded
                      : Icons.compare_arrows_outlined,
                  color: compareSelected ? AppColors.bg : Colors.white,
                  size: 15,
                ),
              ),
            ),
          ),
        // Heart icon
        Positioned(
          top: 6,
          right: 6,
          child: BlocBuilder<FavoriteCubit, FavoriteState>(
            builder: (context, favState) {
              final isFav =
                  favState is FavoriteLoaded && favState.isFavorite(unit.id);
              return GestureDetector(
                onTap: () {
                  context.read<FavoriteCubit>().toggleFavorite(unit);
                },
                child: Container(
                  padding: const EdgeInsets.all(5),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.35),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    isFav
                        ? Icons.favorite_rounded
                        : Icons.favorite_border_rounded,
                    color: isFav ? Colors.redAccent : Colors.white,
                    size: 15,
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildInfo(String payment) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Compound name
            Text(
              unit.compoundName ?? unit.name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 2),
            // Developer
            Text(
              unit.developerName ?? '',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
            ),
            const Spacer(),
            // Specs row
            Row(
              children: [
                if (unit.bedrooms != null)
                  _spec(Icons.bed_outlined, '${unit.bedrooms}'),
                if (unit.bathrooms != null) ...[
                  const SizedBox(width: 8),
                  _spec(Icons.bathtub_outlined, '${unit.bathrooms}'),
                ],
                if (unit.displayArea != null) ...[
                  const SizedBox(width: 8),
                  _spec(Icons.straighten, '${unit.displayArea!.round()} m²'),
                ],
              ],
            ),
            const SizedBox(height: 6),
            // Price
            Text(
              PriceFormatter.format(unit.displayPrice),
              style: const TextStyle(
                color: AppColors.gold,
                fontSize: 14,
                fontWeight: FontWeight.bold,
              ),
            ),
            // Payment plan summary
            if (payment.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  payment,
                  style: const TextStyle(
                    color: AppColors.textMuted,
                    fontSize: 11,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _tag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.85),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          color: color == AppColors.gold ? AppColors.bg : Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _spec(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: AppColors.textMuted, size: 13),
        const SizedBox(width: 2),
        Text(
          text,
          style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
        ),
      ],
    );
  }
}
