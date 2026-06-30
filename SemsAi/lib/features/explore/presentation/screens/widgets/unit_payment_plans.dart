import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class UnitPaymentPlans extends StatefulWidget {
  const UnitPaymentPlans({super.key, required this.plans});

  final List<PaymentPlan> plans;

  @override
  State<UnitPaymentPlans> createState() => _UnitPaymentPlansState();
}

class _UnitPaymentPlansState extends State<UnitPaymentPlans> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    final plans = widget.plans;
    if (_selectedIndex >= plans.length) _selectedIndex = 0;
    final selected = plans[_selectedIndex];

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.appColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: context.appColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.receipt_long_rounded,
                color: AppColors.gold,
                size: 20,
              ),
              const SizedBox(width: 10),
              Text(
                plans.length > 1
                    ? '${AppStrings.paymentPlan} (${plans.length} options)'
                    : AppStrings.paymentPlan,
                style: TextStyle(
                  color: context.appColors.textPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                ),
              ),
            ],
          ),
          if (plans.length > 1) ...[
            const SizedBox(height: 12),
            _buildPlanChips(plans),
          ],
          const SizedBox(height: 14),
          if (selected.frequency != null) _frequencyBadge(selected.frequency!),
          _buildStatsRow(selected),
          if (selected.downPayment != null || selected.unitPrice != null) ...[
            Divider(color: context.appColors.border, height: 24),
            if (selected.downPayment != null)
              _detailRow(
                'Down Payment Amount',
                _fmtPriceFull(selected.downPayment!),
              ),
            if (selected.unitPrice != null)
              _detailRow('Unit Price', _fmtPriceFull(selected.unitPrice!)),
            if (selected.isCash) _detailRow('Type', 'Cash Payment'),
          ],
        ],
      ),
    );
  }

  Widget _buildPlanChips(List<PaymentPlan> plans) {
    return SizedBox(
      height: 36,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: plans.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final isActive = i == _selectedIndex;
          return GestureDetector(
            onTap: () => setState(() => _selectedIndex = i),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: isActive ? AppColors.gold : Colors.transparent,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: isActive ? AppColors.gold : context.appColors.border,
                ),
              ),
              child: Text(
                _chipLabel(plans[i], i),
                style: TextStyle(
                  color: isActive ? context.appColors.bg : context.appColors.textPrimary,
                  fontSize: 12,
                  fontWeight: isActive ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _frequencyBadge(String frequency) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: AppColors.accent.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          _capitalize(frequency),
          style: const TextStyle(
            color: AppColors.accent,
            fontSize: 10,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }

  Widget _buildStatsRow(PaymentPlan plan) {
    return Row(
      children: [
        if (plan.downPaymentPercent != null)
          _stat(
            '${plan.downPaymentPercent!.toStringAsFixed(plan.downPaymentPercent! == plan.downPaymentPercent!.roundToDouble() ? 0 : 1)}%',
            AppStrings.downPayment,
            AppColors.gold,
          ),
        if (plan.years != null)
          _stat('${plan.years}', AppStrings.years, context.appColors.textPrimary),
        if (plan.installmentAmount != null)
          _stat(
            _fmtPriceShort(plan.installmentAmount!),
            _capitalize(plan.frequency ?? AppStrings.installment),
            context.appColors.textPrimary,
          ),
      ],
    );
  }

  Widget _stat(String value, String label, Color valueColor) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: TextStyle(
              color: valueColor,
              fontWeight: FontWeight.w800,
              fontSize: 18,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            style: TextStyle(color: context.appColors.textMuted, fontSize: 11),
          ),
        ],
      ),
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(color: context.appColors.textMuted, fontSize: 12),
          ),
          Text(
            value,
            style: TextStyle(
              color: context.appColors.textPrimary,
              fontWeight: FontWeight.w600,
              fontSize: 13,
            ),
          ),
        ],
      ),
    );
  }

  // ── Helpers ──

  String _chipLabel(PaymentPlan plan, int index) {
    if (plan.isCash) return 'Cash';
    final parts = <String>[];
    final dp = plan.downPaymentPercent;
    if (dp != null) parts.add('${dp.round()}% DP');
    if (plan.years != null && plan.years! > 0) parts.add('${plan.years}yr');
    if (parts.isNotEmpty) return parts.join(' · ');
    return 'Plan ${index + 1}';
  }

  static String _fmtPriceFull(double p) {
    if (p >= 1000000) {
      final v = p / 1000000;
      return '${v.toStringAsFixed(v == v.roundToDouble() ? 0 : 1)}M EGP';
    }
    if (p >= 1000) return '${(p / 1000).toStringAsFixed(0)}K EGP';
    return '${p.toStringAsFixed(0)} EGP';
  }

  static String _fmtPriceShort(double p) {
    if (p >= 1000000) return '${(p / 1000000).toStringAsFixed(1)}M EGP';
    if (p >= 1000) return '${(p / 1000).toStringAsFixed(0)}K EGP';
    return '${p.toStringAsFixed(0)} EGP';
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
