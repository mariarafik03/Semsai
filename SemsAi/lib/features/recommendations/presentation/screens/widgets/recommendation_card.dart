import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/widgets/app_cached_image.dart';
import 'package:SemsAi/features/recommendations/presentation/screens/compound_detail_screen.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/explore/presentation/screens/unit_detail_screen.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class RecommendationCard extends StatefulWidget {
  final Map<String, dynamic> data;
  final int rank;
  final double entranceDelay;
  final AnimationController parentCtrl;

  const RecommendationCard({
    super.key,
    required this.data,
    required this.rank,
    required this.entranceDelay,
    required this.parentCtrl,
  });

  @override
  State<RecommendationCard> createState() => _RecommendationCardState();
}

class _RecommendationCardState extends State<RecommendationCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _fadeSlide;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _fadeSlide = CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic);

    Future.delayed(
      Duration(milliseconds: (300 + widget.entranceDelay * 1000).toInt()),
      () {
        if (mounted) _ctrl.forward();
      },
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fadeSlide,
      child: SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(0, 0.2),
          end: Offset.zero,
        ).animate(_fadeSlide),
        child: GestureDetector(
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => CompoundDetailScreen(compound: widget.data),
              ),
            );
          },
          child: _buildCard(),
        ),
      ),
    );
  }

  Widget _buildCard() {
    final name = widget.data['name'] as String? ?? 'Unknown';
    final location = widget.data['location'] as String? ?? '';
    final imageUrl = widget.data['image_url'] as String? ?? '';
    final confidence = widget.data['confidence'] as num? ?? 0.0;
    final purpose = widget.data['purpose_used'] as String? ?? '';
    final reasons = (widget.data['reasons'] as List<dynamic>?) ?? [];
    final units = (widget.data['units'] as List<dynamic>?) ?? [];
    final minPrice = widget.data['min_unit_price'];

    final medal = widget.rank == 1
        ? '🥇'
        : widget.rank == 2
        ? '🥈'
        : '🥉';

    final confidencePercent = (confidence * 100).toInt();
    final confColor = confidencePercent >= 70
        ? const Color(0xFF4CAF50)
        : confidencePercent >= 50
        ? AppColors.gold
        : const Color(0xFFEF5350);

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: context.appColors.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: widget.rank == 1
              ? AppColors.gold.withValues(alpha: 0.4)
              : context.appColors.border,
        ),
        boxShadow: [
          if (widget.rank == 1)
            BoxShadow(
              color: AppColors.gold.withValues(alpha: 0.1),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Image + Rank Badge ──
          if (imageUrl.isNotEmpty)
            Stack(
              children: [
                ClipRRect(
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(16),
                  ),
                  child: SizedBox(
                    height: 160,
                    width: double.infinity,
                    child: AppCachedImage(
                      imageUrl: imageUrl,
                      fit: BoxFit.cover,
                    ),
                  ),
                ),
                // Gradient overlay
                Positioned.fill(
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      borderRadius: const BorderRadius.vertical(
                        top: Radius.circular(16),
                      ),
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [
                          Colors.transparent,
                          context.appColors.cardBg.withValues(alpha: 0.8),
                        ],
                      ),
                    ),
                  ),
                ),
                // Rank badge
                Positioned(
                  top: 12,
                  left: 12,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: context.appColors.bg.withValues(alpha: 0.85),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: AppColors.gold.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Text(
                      '$medal #${widget.rank}',
                      style: const TextStyle(fontSize: 14),
                    ),
                  ),
                ),
                // Confidence badge
                Positioned(
                  top: 12,
                  right: 12,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: confColor.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: confColor.withValues(alpha: 0.4),
                      ),
                    ),
                    child: Text(
                      '$confidencePercent% match',
                      style: TextStyle(
                        color: confColor,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ],
            )
          else
            // No image — just rank badge
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: context.appColors.bg,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: AppColors.gold.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Text(
                      '$medal #${widget.rank}',
                      style: const TextStyle(fontSize: 14),
                    ),
                  ),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: confColor.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: confColor.withValues(alpha: 0.4),
                      ),
                    ),
                    child: Text(
                      '$confidencePercent% match',
                      style: TextStyle(
                        color: confColor,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // ── Content ──
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Name
                Text(
                  name,
                  style: TextStyle(
                    color: context.appColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (location.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(
                        Icons.location_on_outlined,
                        color: AppColors.gold.withValues(alpha: 0.7),
                        size: 14,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        location,
                        style: TextStyle(
                          color: context.appColors.textMuted,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ],

                if (purpose.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.gold.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      purpose == 'end_user'
                          ? 'For Living'
                          : purpose == 'investment'
                          ? 'For Investment'
                          : 'For Business',
                      style: TextStyle(
                        color: AppColors.gold,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],

                // Reasons
                if (reasons.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  ...reasons
                      .take(4)
                      .map(
                        (r) => Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                margin: const EdgeInsets.only(top: 5),
                                width: 5,
                                height: 5,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: AppColors.gold.withValues(alpha: 0.6),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  r.toString(),
                                  style: TextStyle(
                                    color: context.appColors.textMuted,
                                    fontSize: 13,
                                    height: 1.3,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                ],

                // Starting price
                if (minPrice != null) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1A2332),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: context.appColors.border),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.payments_outlined,
                          color: AppColors.gold,
                          size: 14,
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'From ${_formatPrice(minPrice)}',
                          style: TextStyle(
                            color: AppColors.gold,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],

                // Units
                if (units.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Icon(
                        Icons.apartment_rounded,
                        color: AppColors.gold.withValues(alpha: 0.7),
                        size: 14,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        'Available Units',
                        style: TextStyle(
                          color: context.appColors.textPrimary,
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ...units.take(3).map((u) {
                    final unit = Map<String, dynamic>.from(u as Map);
                    return _buildUnitRow(unit);
                  }),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatPrice(dynamic value) {
    try {
      final num = double.parse(value.toString());
      if (num >= 1000000) {
        return '${(num / 1000000).toStringAsFixed(1)}M EGP';
      } else if (num >= 1000) {
        return '${(num / 1000).toStringAsFixed(0)}K EGP';
      }
      return '${num.toStringAsFixed(0)} EGP';
    } catch (_) {
      return 'N/A';
    }
  }

  Widget _buildUnitRow(Map<String, dynamic> unit) {
    final type = (unit['type'] as String?) ?? '';
    final price = unit['price'];
    final area = unit['area'];
    final beds = unit['bedrooms'];
    final baths = unit['bathrooms'];

    return GestureDetector(
      onTap: () {
        final unitModel = CompoundUnit.fromJson(unit);
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => UnitDetailScreen(unit: unitModel),
          ),
        );
      },
      child: Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: context.appColors.bg.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: context.appColors.border.withValues(alpha: 0.5)),
      ),
      child: Row(
        children: [
          // Type icon
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: AppColors.gold.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Icon(
              type.toLowerCase().contains('villa')
                  ? Icons.villa_outlined
                  : Icons.apartment_outlined,
              color: AppColors.gold,
              size: 14,
            ),
          ),
          const SizedBox(width: 10),
          // Details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  price != null ? _formatPrice(price) : 'Price N/A',
                  style: TextStyle(
                    color: context.appColors.textPrimary,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    if (type.isNotEmpty) _unitDetail(Icons.home_outlined, type),
                    if (area != null) ...[
                      if (type.isNotEmpty) const SizedBox(width: 10),
                      _unitDetail(Icons.square_foot, '${area}m²'),
                    ],
                    if (beds != null) ...[
                      const SizedBox(width: 10),
                      _unitDetail(Icons.bed_outlined, '$beds bed'),
                    ],
                    if (baths != null) ...[
                      const SizedBox(width: 10),
                      _unitDetail(Icons.bathtub_outlined, '$baths bath'),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
      ),
    );
  }

  Widget _unitDetail(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 11, color: context.appColors.textMuted),
        const SizedBox(width: 3),
        Text(
          text,
          style: TextStyle(color: context.appColors.textMuted, fontSize: 11),
        ),
      ],
    );
  }
}
