import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/utils/price_formatter.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/comparison/presentation/cubit/comparison_cubit.dart';
import 'package:SemsAi/features/comparison/presentation/cubit/comparison_state.dart';

class ComparisonScreen extends StatefulWidget {
  const ComparisonScreen({super.key});

  @override
  State<ComparisonScreen> createState() => _ComparisonScreenState();
}

class _ComparisonScreenState extends State<ComparisonScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animCtrl;
  late final Animation<double> _fadeAnim;

  @override
  void initState() {
    super.initState();
    _animCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _fadeAnim = CurvedAnimation(parent: _animCtrl, curve: Curves.easeOutCubic);
    _animCtrl.forward();
  }

  @override
  void dispose() {
    _animCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<ComparisonCubit, ComparisonState>(
      builder: (context, state) {
        if (state.units.length < 2) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted && Navigator.of(context).canPop()) {
              Navigator.of(context).pop();
            }
          });
          return const SizedBox.shrink();
        }

        return Scaffold(
          backgroundColor: AppColors.bg,
          body: FadeTransition(
            opacity: _fadeAnim,
            child: CustomScrollView(
              physics: const BouncingScrollPhysics(),
              slivers: [
                _buildAppBar(state),
                SliverToBoxAdapter(child: _buildImageCards(state)),
                SliverToBoxAdapter(child: const SizedBox(height: 8)),
                SliverToBoxAdapter(
                  child: _buildSection(
                    'Price',
                    Icons.monetization_on_outlined,
                    state,
                    _priceRow,
                  ),
                ),
                SliverToBoxAdapter(
                  child: _buildSection(
                    'Area & Layout',
                    Icons.straighten_rounded,
                    state,
                    _areaRow,
                  ),
                ),
                SliverToBoxAdapter(
                  child: _buildSection(
                    'Location',
                    Icons.location_on_outlined,
                    state,
                    _locationRow,
                  ),
                ),
                SliverToBoxAdapter(
                  child: _buildSection(
                    'Developer & Details',
                    Icons.business_rounded,
                    state,
                    _developerRow,
                  ),
                ),
                SliverToBoxAdapter(
                  child: _buildSection(
                    'Payment Plans',
                    Icons.credit_card_outlined,
                    state,
                    _paymentRow,
                  ),
                ),
                const SliverToBoxAdapter(child: SizedBox(height: 100)),
              ],
            ),
          ),
        );
      },
    );
  }

  // ─────────────────────────── APP BAR ────────────────────────────

  Widget _buildAppBar(ComparisonState state) {
    return SliverAppBar(
      pinned: true,
      backgroundColor: AppColors.bg.withValues(alpha: 0.95),
      surfaceTintColor: Colors.transparent,
      leading: GestureDetector(
        onTap: () => Navigator.of(context).pop(),
        child: Container(
          margin: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppColors.cardBg,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.border),
          ),
          child: const Icon(
            Icons.arrow_back_ios_new_rounded,
            color: AppColors.textPrimary,
            size: 18,
          ),
        ),
      ),
      title: Column(
        children: [
          const Text(
            'Property Comparison',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 17,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            'Comparing ${state.count} properties',
            style: TextStyle(
              color: AppColors.textMuted.withValues(alpha: 0.8),
              fontSize: 12,
              fontWeight: FontWeight.w400,
            ),
          ),
        ],
      ),
      centerTitle: true,
      actions: [
        GestureDetector(
          onTap: () {
            context.read<ComparisonCubit>().clear();
            Navigator.of(context).pop();
          },
          child: Container(
            margin: const EdgeInsets.all(8),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.redAccent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: Colors.redAccent.withValues(alpha: 0.3),
              ),
            ),
            child: const Text(
              'Clear',
              style: TextStyle(
                color: Colors.redAccent,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ],
    );
  }

  // ────────────────────── IMAGE HEADER CARDS ───────────────────────

  Widget _buildImageCards(ComparisonState state) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      child: Row(
        children: List.generate(state.count, (i) {
          final unit = state.units[i];
          return Expanded(
            child: Padding(
              padding: EdgeInsets.only(
                left: i == 0 ? 0 : 4,
                right: i == state.count - 1 ? 0 : 4,
              ),
              child: _UnitHeaderCard(
                unit: unit,
                color: _columnColor(i),
                onRemove: () {
                  context.read<ComparisonCubit>().remove(unit.id);
                },
              ),
            ),
          );
        }),
      ),
    );
  }

  // ──────────────────── COMPARISON SECTIONS ────────────────────────

  Widget _buildSection(
    String title,
    IconData icon,
    ComparisonState state,
    List<_CompRow> Function(ComparisonState) rowBuilder,
  ) {
    final rows = rowBuilder(state);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.border.withValues(alpha: 0.6)),
        ),
        child: Column(
          children: [
            // Section header
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    AppColors.gold.withValues(alpha: 0.08),
                    Colors.transparent,
                  ],
                ),
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(16),
                ),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AppColors.gold.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(icon, color: AppColors.gold, size: 16),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    title,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
            // Rows
            ...List.generate(rows.length, (i) {
              final row = rows[i];
              final isLast = i == rows.length - 1;
              return _buildComparisonRow(row, state.count, isLast, i);
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildComparisonRow(_CompRow row, int count, bool isLast, int index) {
    // Find the best value for highlighting
    final bestIdx = row.bestIndex;

    return Container(
      decoration: BoxDecoration(
        color: index.isEven
            ? Colors.transparent
            : Colors.white.withValues(alpha: 0.015),
        borderRadius: isLast
            ? const BorderRadius.vertical(bottom: Radius.circular(16))
            : BorderRadius.zero,
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            child: Row(
              children: [
                SizedBox(
                  width: 80,
                  child: Text(
                    row.label,
                    style: TextStyle(
                      color: AppColors.textMuted.withValues(alpha: 0.9),
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
                ...List.generate(count, (ci) {
                  final isBest = bestIdx == ci;
                  return Expanded(
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 8,
                      ),
                      margin: EdgeInsets.only(
                        left: ci == 0 ? 0 : 3,
                        right: ci == count - 1 ? 0 : 3,
                      ),
                      decoration: BoxDecoration(
                        color: isBest
                            ? AppColors.gold.withValues(alpha: 0.08)
                            : Colors.transparent,
                        borderRadius: BorderRadius.circular(8),
                        border: isBest
                            ? Border.all(
                                color: AppColors.gold.withValues(alpha: 0.25),
                              )
                            : null,
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (isBest) ...[
                            Icon(
                              Icons.emoji_events_rounded,
                              color: AppColors.gold,
                              size: 12,
                            ),
                            const SizedBox(width: 3),
                          ],
                          Flexible(
                            child: Text(
                              row.values[ci],
                              style: TextStyle(
                                color: isBest
                                    ? AppColors.gold
                                    : AppColors.textPrimary,
                                fontSize: 12,
                                fontWeight: isBest
                                    ? FontWeight.w700
                                    : FontWeight.w500,
                              ),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                }),
              ],
            ),
          ),
          if (!isLast)
            Divider(
              height: 1,
              color: AppColors.border.withValues(alpha: 0.4),
              indent: 16,
              endIndent: 16,
            ),
        ],
      ),
    );
  }

  // ──────────────────── ROW DATA BUILDERS ──────────────────────────

  List<_CompRow> _priceRow(ComparisonState s) {
    final units = s.units;
    // Find lowest price for highlighting
    final prices = units.map((u) => u.displayPrice).toList();
    int? lowestIdx;
    double? lowest;
    for (int i = 0; i < prices.length; i++) {
      if (prices[i] != null && (lowest == null || prices[i]! < lowest)) {
        lowest = prices[i];
        lowestIdx = i;
      }
    }

    return [
      _CompRow(
        label: 'Total Price',
        values: units
            .map((u) => PriceFormatter.format(u.displayPrice))
            .toList(),
        bestIndex: lowestIdx,
      ),
      _CompRow(
        label: 'Price/m²',
        values: units.map((u) {
          final price = u.displayPrice;
          final area = u.displayArea;
          if (price != null && area != null && area > 0) {
            return PriceFormatter.format(price / area);
          }
          return '—';
        }).toList(),
        bestIndex: _findLowestIndex(
          units.map((u) {
            final p = u.displayPrice;
            final a = u.displayArea;
            return (p != null && a != null && a > 0) ? p / a : null;
          }).toList(),
        ),
      ),
      _CompRow(
        label: 'Price Range',
        values: units.map((u) => u.priceRangeText ?? '—').toList(),
      ),
    ];
  }

  List<_CompRow> _areaRow(ComparisonState s) {
    final units = s.units;
    return [
      _CompRow(
        label: 'Area',
        values: units.map((u) {
          final a = u.displayArea;
          return a != null ? '${a.round()} m²' : '—';
        }).toList(),
        bestIndex: _findHighestIndex(units.map((u) => u.displayArea).toList()),
      ),
      _CompRow(
        label: 'Bedrooms',
        values: units.map((u) => u.bedrooms?.toString() ?? '—').toList(),
        bestIndex: _findHighestIndex(
          units.map((u) => u.bedrooms?.toDouble()).toList(),
        ),
      ),
      _CompRow(
        label: 'Bathrooms',
        values: units.map((u) => u.bathrooms?.toString() ?? '—').toList(),
      ),
      _CompRow(label: 'Type', values: units.map((u) => u.type).toList()),
      _CompRow(
        label: 'Finishing',
        values: units.map((u) => u.finishing ?? '—').toList(),
      ),
    ];
  }

  List<_CompRow> _locationRow(ComparisonState s) {
    final units = s.units;
    return [
      _CompRow(
        label: 'Location',
        values: units.map((u) => u.location ?? '—').toList(),
      ),
      _CompRow(
        label: 'Compound',
        values: units.map((u) => u.compoundName ?? '—').toList(),
      ),
    ];
  }

  List<_CompRow> _developerRow(ComparisonState s) {
    return [
      _CompRow(
        label: 'Developer',
        values: s.units.map((u) => u.developerName ?? '—').toList(),
      ),
      _CompRow(
        label: 'Delivery',
        values: s.units.map((u) => u.deliveryYear ?? '—').toList(),
      ),
      _CompRow(
        label: 'Sale Type',
        values: s.units.map((u) => u.saleType ?? '—').toList(),
      ),
    ];
  }

  List<_CompRow> _amenitiesRow(ComparisonState s) {
    final units = s.units;
    return [
      _CompRow(
        label: 'Bedrooms',
        values: units
            .map((u) => u.bedrooms != null ? '${u.bedrooms} BR' : '—')
            .toList(),
      ),
      _CompRow(
        label: 'Bathrooms',
        values: units
            .map((u) => u.bathrooms != null ? '${u.bathrooms} BA' : '—')
            .toList(),
      ),
      _CompRow(
        label: 'Finishing',
        values: units.map((u) => u.finishing ?? '—').toList(),
      ),
      _CompRow(label: 'Type', values: units.map((u) => u.type).toList()),
    ];
  }

  List<_CompRow> _paymentRow(ComparisonState s) {
    final units = s.units;
    return [
      _CompRow(
        label: 'Down Payment',
        values: units.map((u) {
          final plan = u.bestPlan;
          if (plan == null) return '—';
          final dp = plan.downPaymentPercent;
          if (dp != null) return '${dp.round()}%';
          if (plan.downPayment != null) {
            return PriceFormatter.format(plan.downPayment);
          }
          return '—';
        }).toList(),
        bestIndex: _findLowestIndex(
          units.map((u) {
            return u.bestPlan?.downPaymentPercent;
          }).toList(),
        ),
      ),
      _CompRow(
        label: 'Installment',
        values: units.map((u) {
          final plan = u.bestPlan;
          if (plan?.installmentAmount == null) return '—';
          return PriceFormatter.format(plan!.installmentAmount);
        }).toList(),
        bestIndex: _findLowestIndex(
          units.map((u) {
            return u.bestPlan?.installmentAmount;
          }).toList(),
        ),
      ),
      _CompRow(
        label: 'Duration',
        values: units.map((u) {
          final plan = u.bestPlan;
          if (plan?.years == null) return '—';
          return '${plan!.years} years';
        }).toList(),
        bestIndex: _findHighestIndex(
          units.map((u) {
            return u.bestPlan?.years?.toDouble();
          }).toList(),
        ),
      ),
      _CompRow(
        label: 'Plans Count',
        values: units
            .map(
              (u) =>
                  '${u.paymentPlans.length} plan${u.paymentPlans.length != 1 ? 's' : ''}',
            )
            .toList(),
        bestIndex: _findHighestIndex(
          units.map((u) => u.paymentPlans.length.toDouble()).toList(),
        ),
      ),
    ];
  }

  // ────────────────────── HELPERS ──────────────────────────────────

  int? _findLowestIndex(List<double?> values) {
    int? bestIdx;
    double? best;
    for (int i = 0; i < values.length; i++) {
      if (values[i] != null && (best == null || values[i]! < best)) {
        best = values[i];
        bestIdx = i;
      }
    }
    return bestIdx;
  }

  int? _findHighestIndex(List<double?> values) {
    int? bestIdx;
    double? best;
    for (int i = 0; i < values.length; i++) {
      if (values[i] != null && (best == null || values[i]! > best)) {
        best = values[i];
        bestIdx = i;
      }
    }
    return bestIdx;
  }

  Color _columnColor(int index) {
    const colors = [AppColors.gold, AppColors.accent, Color(0xFF4CAF50)];
    return colors[index % colors.length];
  }
}

// ═══════════════════════════════════════════════════════════════════
// SUPPORTING WIDGETS
// ═══════════════════════════════════════════════════════════════════

class _CompRow {
  final String label;
  final List<String> values;
  final int? bestIndex;

  const _CompRow({required this.label, required this.values, this.bestIndex});
}

class _UnitHeaderCard extends StatelessWidget {
  final CompoundUnit unit;
  final Color color;
  final VoidCallback onRemove;

  const _UnitHeaderCard({
    required this.unit,
    required this.color,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final image = unit.images.isNotEmpty ? unit.images.first : null;
    return Container(
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.4)),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.1),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          // Image
          Stack(
            children: [
              ClipRRect(
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(13),
                ),
                child: image != null
                    ? Image.network(
                        image,
                        height: 90,
                        width: double.infinity,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _placeholder(),
                      )
                    : _placeholder(),
              ),
              // Color indicator bar
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                child: Container(
                  height: 3,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [color, color.withValues(alpha: 0.3)],
                    ),
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(13),
                    ),
                  ),
                ),
              ),
              // Remove button
              Positioned(
                top: 6,
                right: 6,
                child: GestureDetector(
                  onTap: onRemove,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Icon(
                      Icons.close_rounded,
                      color: Colors.white,
                      size: 14,
                    ),
                  ),
                ),
              ),
            ],
          ),
          // Info
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 8, 8, 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  unit.compoundName ?? unit.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  unit.developerName ?? '',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: color.withValues(alpha: 0.9),
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  PriceFormatter.format(unit.displayPrice),
                  style: TextStyle(
                    color: color,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _placeholder() {
    return Container(
      height: 90,
      width: double.infinity,
      color: AppColors.border,
      child: const Icon(
        Icons.home_outlined,
        color: AppColors.textMuted,
        size: 28,
      ),
    );
  }
}
