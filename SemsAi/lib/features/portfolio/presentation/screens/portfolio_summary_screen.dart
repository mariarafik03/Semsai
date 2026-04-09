import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

class PortfolioSummaryScreen extends StatelessWidget {
  final Map<String, dynamic> result;
  final List<Map<String, dynamic>> units;

  const PortfolioSummaryScreen({
    super.key,
    required this.result,
    required this.units,
  });

  @override
  Widget build(BuildContext context) {
    final metrics = (result['metrics'] as Map<String, dynamic>? ?? {});
    final scores = (result['scores'] as Map<String, dynamic>? ?? {});
    final finalScore = _toNum(result['finalScore']);
    final healthBand = (result['healthBand'] ?? 'watch').toString();

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        backgroundColor: AppColors.cardBg,
        title: const Text(
          'Your Portfolio',
          style: TextStyle(color: AppColors.textPrimary),
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              'SEMSAI',
              style: TextStyle(
                color: AppColors.gold,
                fontSize: 12,
                fontWeight: FontWeight.w600,
                letterSpacing: 2,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Portfolio Overview',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            _healthCard(finalScore, healthBand, scores),
            const SizedBox(height: 12),
            _monthlyBurdenCard(metrics),
            const SizedBox(height: 18),
            Text(
              '${units.length} Units',
              style: const TextStyle(color: AppColors.textMuted, fontSize: 14),
            ),
            const SizedBox(height: 10),
            ...units.asMap().entries.map((entry) {
              final i = entry.key;
              final unit = entry.value;
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _unitCard(i + 1, unit),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _healthCard(
    double finalScore,
    String healthBand,
    Map<String, dynamic> scores,
  ) {
    final cashflow = _toNum(scores['cashflowScore']);
    final risk = _toNum(scores['riskScore']);
    final liquidity = _toNum(scores['liquidityScore']);
    final flexibility = _toNum(scores['flexibilityScore']);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 58,
                height: 58,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.gold, width: 3),
                ),
                alignment: Alignment.center,
                child: Text(
                  finalScore.toStringAsFixed(0),
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Portfolio Health',
                    style: TextStyle(color: AppColors.textMuted, fontSize: 13),
                  ),
                  Text(
                    _bandLabel(healthBand),
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),
          _metricBar('Cashflow', cashflow, AppColors.gold),
          const SizedBox(height: 10),
          _metricBar('Risk', risk, Colors.orangeAccent),
          const SizedBox(height: 10),
          _metricBar('Liquidity', liquidity, AppColors.accent),
          const SizedBox(height: 10),
          _metricBar('Flexibility', flexibility, Colors.greenAccent),
        ],
      ),
    );
  }

  Widget _metricBar(String label, double value, Color color) {
    final clamped = value.clamp(0, 100);
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: const TextStyle(color: AppColors.textMuted, fontSize: 14),
            ),
            Text(
              '${clamped.toStringAsFixed(0)}/100',
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 14,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(5),
          child: LinearProgressIndicator(
            value: clamped / 100,
            minHeight: 6,
            backgroundColor: AppColors.border,
            valueColor: AlwaysStoppedAnimation<Color>(color),
          ),
        ),
      ],
    );
  }

  Widget _monthlyBurdenCard(Map<String, dynamic> metrics) {
    final monthlyBurden = _toNum(metrics['totalInstallments']);
    final freeCashflow = _toNum(metrics['freeCashflow']);
    final dti = _toNum(metrics['dti']) * 100;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Monthly burden',
            style: TextStyle(color: AppColors.textMuted, fontSize: 13),
          ),
          const SizedBox(height: 4),
          Text(
            '${_formatNumber(monthlyBurden)} EGP',
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 22,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Free cashflow: ${_formatNumber(freeCashflow)} EGP • DTI: ${dti.toStringAsFixed(1)}%',
            style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _unitCard(int index, Map<String, dynamic> unit) {
    final installment = _toNum(unit['monthlyInstallment']);
    final remaining = _toNum(unit['remainingBalance']);
    final marketValue = _toNum(unit['marketValue']);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Unit $index',
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Monthly: ${_formatNumber(installment)} EGP',
            style: const TextStyle(color: AppColors.textPrimary),
          ),
          Text(
            'Remaining: ${_formatNumber(remaining)} EGP',
            style: const TextStyle(color: AppColors.textPrimary),
          ),
          Text(
            'Market Value: ${_formatNumber(marketValue)} EGP',
            style: const TextStyle(color: AppColors.textPrimary),
          ),
        ],
      ),
    );
  }

  static double _toNum(dynamic value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? 0;
  }

  static String _bandLabel(String band) {
    switch (band) {
      case 'healthy':
        return 'Healthy';
      case 'watch':
        return 'Moderate';
      default:
        return 'Risky';
    }
  }

  static String _formatNumber(double value) {
    final rounded = value.round().toString();
    return rounded.replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (m) => '${m[1]},',
    );
  }
}
