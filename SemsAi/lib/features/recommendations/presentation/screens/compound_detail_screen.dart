import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/utils/price_formatter.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/explore/presentation/screens/unit_detail_screen.dart';

class CompoundDetailScreen extends StatelessWidget {
  final Map<String, dynamic> compound;

  const CompoundDetailScreen({super.key, required this.compound});

  @override
  Widget build(BuildContext context) {
    final name = compound['compound_name'] ?? compound['name'] ?? 'Unknown';
    final location = compound['location'] ?? '';
    final score = compound['score'] as num? ?? 0.0;
    final minPrice = compound['min_unit_price'] ?? compound['min_price'];
    final reasons = (compound['reasons'] as List<dynamic>?) ?? [];
    final units = (compound['units'] as List<dynamic>?) ?? [];
    final confidencePercent = (score * 100).toInt();

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        slivers: [
          // ── App Bar ──
          SliverAppBar(
            backgroundColor: AppColors.cardBg,
            pinned: true,
            title: Text(
              name,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 17,
                fontWeight: FontWeight.w600,
              ),
            ),
            actions: [
              Container(
                margin: const EdgeInsets.only(right: 16),
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 5,
                ),
                decoration: BoxDecoration(
                  color: AppColors.gold.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: AppColors.gold.withValues(alpha: 0.3),
                  ),
                ),
                child: Text(
                  '$confidencePercent% match',
                  style: TextStyle(
                    color: AppColors.gold,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),

          // ── Compound Info Card ──
          SliverToBoxAdapter(
            child: Container(
              margin: const EdgeInsets.all(16),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.cardBg,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: AppColors.gold.withValues(alpha: 0.3),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Name + Location
                  Text(
                    name,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  if (location.toString().isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Icon(
                          Icons.location_on_outlined,
                          color: AppColors.gold.withValues(alpha: 0.7),
                          size: 15,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          location.toString(),
                          style: const TextStyle(
                            color: AppColors.textMuted,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ),
                  ],

                  // Price
                  if (minPrice != null) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.gold.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
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
                            'Starting from ${PriceFormatter.format(minPrice)}',
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

                  // Reasons
                  if (reasons.isNotEmpty) ...[
                    const SizedBox(height: 14),
                    const Text(
                      'Why this compound?',
                      style: TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    ...reasons
                        .take(5)
                        .map(
                          (r) => Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  margin: const EdgeInsets.only(top: 6),
                                  width: 5,
                                  height: 5,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: AppColors.gold.withValues(
                                      alpha: 0.6,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    r.toString(),
                                    style: const TextStyle(
                                      color: AppColors.textMuted,
                                      fontSize: 13,
                                      height: 1.4,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                  ],
                ],
              ),
            ),
          ),

          // ── Units Header ──
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 10),
              child: Row(
                children: [
                  Icon(
                    Icons.apartment_rounded,
                    color: AppColors.gold,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Available Units (${units.length})',
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),

          // ── Units List ──
          if (units.isEmpty)
            SliverToBoxAdapter(
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: AppColors.cardBg,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: [
                    Icon(
                      Icons.info_outline,
                      color: AppColors.textMuted.withValues(alpha: 0.4),
                      size: 36,
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      'No units found for this compound',
                      style: TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            SliverList(
              delegate: SliverChildBuilderDelegate((context, index) {
                final unit = Map<String, dynamic>.from(units[index] as Map);
                return _UnitCard(unit: unit, index: index);
              }, childCount: units.length),
            ),

          // bottom padding
          const SliverPadding(padding: EdgeInsets.only(bottom: 24)),
        ],
      ),
    );
  }

  // Removed: Use PriceFormatter.format instead.
}

// ── Unit Card Widget ──

class _UnitCard extends StatelessWidget {
  final Map<String, dynamic> unit;
  final int index;

  const _UnitCard({required this.unit, required this.index});

  @override
  Widget build(BuildContext context) {
    final type = (unit['type'] as String?) ?? '';
    final price = unit['price'];
    final area = unit['area'];
    final beds = unit['bedrooms'];
    final baths = unit['bathrooms'];
    final unitName = (unit['name'] as String?) ?? '';

    final isVilla = type.toLowerCase().contains('villa');

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
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          // Icon
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.gold.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              isVilla ? Icons.villa_outlined : Icons.apartment_outlined,
              color: AppColors.gold,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),

          // Details
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Type + name
                Text(
                  unitName.isNotEmpty
                      ? unitName
                      : (type.isNotEmpty ? type : 'Unit ${index + 1}'),
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 6),
                // Specs row
                Wrap(
                  spacing: 12,
                  runSpacing: 6,
                  children: [
                    if (type.isNotEmpty) _spec(Icons.home_outlined, type),
                    if (area != null) _spec(Icons.square_foot, '${area} m²'),
                    if (beds != null) _spec(Icons.bed_outlined, '$beds Beds'),
                    if (baths != null)
                      _spec(Icons.bathtub_outlined, '$baths Baths'),
                  ],
                ),
              ],
            ),
          ),

          // Price
          if (price != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.gold.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                PriceFormatter.format(price),
                style: const TextStyle(
                  color: AppColors.gold,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
        ],
      ),
    ),
    );
  }

  Widget _spec(IconData icon, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 12, color: AppColors.textMuted),
        const SizedBox(width: 4),
        Text(
          label,
          style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
        ),
      ],
    );
  }

  // Removed: Use PriceFormatter.format instead.
}
