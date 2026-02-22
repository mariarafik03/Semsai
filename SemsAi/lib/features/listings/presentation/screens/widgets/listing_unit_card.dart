import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/widgets/app_cached_image.dart';
import 'package:SemsAi/core/widgets/tap_scale.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/explore/presentation/screens/unit_detail_screen.dart';

class ListingUnitCard extends StatelessWidget {
  const ListingUnitCard({super.key, required this.unit});

  final CompoundUnit unit;

  // ── Helpers ──

  static String formatPrice(double? p) {
    if (p == null) return 'Contact for price';
    if (p >= 1000000) {
      final v = p / 1000000;
      return '${v.toStringAsFixed(v == v.roundToDouble() ? 0 : 1)}M EGP';
    }
    if (p >= 1000) return '${(p / 1000).toStringAsFixed(0)}K EGP';
    return '${p.toStringAsFixed(0)} EGP';
  }

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

    return TapScale(
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
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.border.withValues(alpha: 0.6)),
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
    );
  }

  Widget _buildImage(String? image, String heroTag, String? regionTag) {
    return ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
      child: Stack(
        children: [
          AspectRatio(
            aspectRatio: 1.4,
            child: Hero(
              tag: heroTag,
              child: AppCachedImage(
                imageUrl: image,
                fit: BoxFit.cover,
                memCacheWidth: 300,
              ),
            ),
          ),
          // Bottom gradient
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            height: 40,
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Colors.transparent,
                    Colors.black.withValues(alpha: 0.55),
                  ],
                ),
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
          // Heart icon
          Positioned(
            top: 6,
            right: 6,
            child: Container(
              padding: const EdgeInsets.all(5),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.35),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(
                Icons.favorite_border_rounded,
                color: Colors.white,
                size: 15,
              ),
            ),
          ),
        ],
      ),
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
              style: const TextStyle(
                color: AppColors.textMuted,
                fontSize: 11,
              ),
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
                  _spec(
                    Icons.straighten,
                    '${unit.displayArea!.round()} m²',
                  ),
                ],
              ],
            ),
            const SizedBox(height: 6),
            // Price
            Text(
              formatPrice(unit.displayPrice),
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
