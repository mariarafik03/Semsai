import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

class WhatIfSimulatorScreen extends StatefulWidget {
  final Map<String, dynamic> result;

  const WhatIfSimulatorScreen({super.key, required this.result});

  @override
  State<WhatIfSimulatorScreen> createState() => _WhatIfSimulatorScreenState();
}

class _WhatIfSimulatorScreenState extends State<WhatIfSimulatorScreen> {
  double _downPaymentPct = 20;
  double _installmentYears = 5;
  String _sellTiming = 'Hold';
  double _newUnitPrice = 2000000;

  double _toNum(dynamic v) {
    if (v == null) return 0;
    if (v is num) return v.toDouble();
    return double.tryParse(v.toString()) ?? 0;
  }

  String _formatNum(double n) {
    if (n >= 1000000) return '${(n / 1000000).toStringAsFixed(1)}M';
    if (n >= 1000) return '${(n / 1000).toStringAsFixed(0)}K';
    return n.toStringAsFixed(0);
  }

  @override
  Widget build(BuildContext context) {
    final metrics = widget.result['metrics'] as Map<String, dynamic>? ?? {};
    final input = widget.result['inputSnapshot'] as Map<String, dynamic>? ?? {};
    final freeCashflow = _toNum(metrics['freeCashflow']);
    final currentDti = _toNum(metrics['dti']) * 100;
    final netIncome = _toNum(input['netMonthlyIncome']);
    final maxRatio = _toNum(input['maxInstallmentRatio']);
    final currentInstallments = _toNum(metrics['totalInstallments']);

    // Simulate
    final downPayment = _newUnitPrice * (_downPaymentPct / 100);
    final financed = _newUnitPrice - downPayment;
    final months = _installmentYears * 12;
    // Simple interest @ 27.25% annual
    final monthlyRate = 0.2725 / 12;
    final newMonthlyInstallment = months > 0
        ? financed * monthlyRate / (1 - (1 / (1 + monthlyRate).clamp(0.001, double.infinity)))
        : 0.0;
    final simInstallment = months > 0
        ? (financed * (monthlyRate * _pow(1 + monthlyRate, months.toInt())) /
            (_pow(1 + monthlyRate, months.toInt()) - 1))
        : 0.0;

    final newTotalInstallments = currentInstallments + simInstallment;
    final newDti = netIncome > 0 ? (newTotalInstallments / netIncome) * 100 : 0;
    final newFreeCashflow = freeCashflow - simInstallment;
    final isDtiSafe = newDti < (maxRatio * 100);
    final isCashflowPositive = newFreeCashflow > 0;

    String riskLevel;
    Color riskColor;
    if (isDtiSafe && isCashflowPositive && newFreeCashflow > 3000) {
      riskLevel = 'Low Risk';
      riskColor = const Color(0xFF22C55E);
    } else if (isDtiSafe && isCashflowPositive) {
      riskLevel = 'Medium Risk';
      riskColor = const Color(0xFFF97316);
    } else {
      riskLevel = 'High Risk';
      riskColor = const Color(0xFFEF4444);
    }

    return Scaffold(
      backgroundColor: const Color(0xFF020617),
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(context),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  const Text(
                    'What if you buy a new unit?',
                    style: TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Adjust parameters to simulate the impact on your portfolio',
                    style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                  ),
                  const SizedBox(height: 24),

                  // Unit Price
                  _buildSliderCard(
                    label: 'Unit Price',
                    value: _newUnitPrice,
                    min: 500000,
                    max: 20000000,
                    displayValue: '${_formatNum(_newUnitPrice)} EGP',
                    onChanged: (v) => setState(() => _newUnitPrice = v),
                    divisions: 39,
                  ),
                  const SizedBox(height: 14),

                  // Down Payment
                  _buildSliderCard(
                    label: 'Down Payment',
                    value: _downPaymentPct,
                    min: 0,
                    max: 100,
                    displayValue: '${_downPaymentPct.toStringAsFixed(0)}%',
                    subtitle: '${_formatNum(downPayment)} EGP',
                    onChanged: (v) => setState(() => _downPaymentPct = v),
                    divisions: 20,
                  ),
                  const SizedBox(height: 14),

                  // Installment Duration
                  _buildSliderCard(
                    label: 'Installment Duration',
                    value: _installmentYears,
                    min: 1,
                    max: 10,
                    displayValue: '${_installmentYears.toStringAsFixed(0)} years',
                    subtitle: '${months.toStringAsFixed(0)} months',
                    onChanged: (v) => setState(() => _installmentYears = v),
                    divisions: 9,
                  ),
                  const SizedBox(height: 14),

                  // Sell Timing
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F172A),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: const Color(0xFF1E293B)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Strategy',
                          style: TextStyle(
                            color: Color(0xFF94A3B8),
                            fontSize: 13,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Row(
                          children: ['Hold', 'Flip', 'Rent'].map((option) {
                            final selected = _sellTiming == option;
                            return Expanded(
                              child: GestureDetector(
                                onTap: () =>
                                    setState(() => _sellTiming = option),
                                child: Container(
                                  margin: const EdgeInsets.symmetric(
                                      horizontal: 4),
                                  padding: const EdgeInsets.symmetric(
                                      vertical: 10),
                                  decoration: BoxDecoration(
                                    color: selected
                                        ? AppColors.gold.withValues(alpha: 0.15)
                                        : const Color(0xFF1E293B),
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(
                                      color: selected
                                          ? AppColors.gold
                                          : const Color(0xFF334155),
                                    ),
                                  ),
                                  alignment: Alignment.center,
                                  child: Text(
                                    option,
                                    style: TextStyle(
                                      color: selected
                                          ? AppColors.gold
                                          : const Color(0xFF94A3B8),
                                      fontSize: 13,
                                      fontWeight: selected
                                          ? FontWeight.w600
                                          : FontWeight.w400,
                                    ),
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Results
                  const Text(
                    'Simulation Results',
                    style: TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Risk Badge
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F172A),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(
                        color: riskColor.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.shield_outlined,
                                color: riskColor, size: 22),
                            const SizedBox(width: 8),
                            Text(
                              riskLevel,
                              style: TextStyle(
                                color: riskColor,
                                fontSize: 20,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        _buildResultRow(
                          'New Monthly Installment',
                          '${_formatNum(simInstallment)} EGP/mo',
                        ),
                        _buildResultRow(
                          'Total Monthly Burden',
                          '${_formatNum(newTotalInstallments)} EGP/mo',
                        ),
                        _buildResultRow(
                          'New DTI',
                          '${newDti.toStringAsFixed(1)}%',
                          valueColor: isDtiSafe
                              ? const Color(0xFF22C55E)
                              : const Color(0xFFEF4444),
                        ),
                        _buildResultRow(
                          'Remaining Cashflow',
                          '${_formatNum(newFreeCashflow)} EGP/mo',
                          valueColor: isCashflowPositive
                              ? const Color(0xFF22C55E)
                              : const Color(0xFFEF4444),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  double _pow(double base, int exp) {
    double result = 1;
    for (int i = 0; i < exp; i++) {
      result *= base;
    }
    return result;
  }

  Widget _buildSliderCard({
    required String label,
    required double value,
    required double min,
    required double max,
    required String displayValue,
    String? subtitle,
    required ValueChanged<double> onChanged,
    int? divisions,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                label,
                style: const TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 13,
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    displayValue,
                    style: const TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  if (subtitle != null)
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: Color(0xFF64748B),
                        fontSize: 11,
                      ),
                    ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          SliderTheme(
            data: SliderThemeData(
              activeTrackColor: AppColors.gold,
              inactiveTrackColor: const Color(0xFF1E293B),
              thumbColor: AppColors.gold,
              overlayColor: AppColors.gold.withValues(alpha: 0.15),
              trackHeight: 4,
              thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8),
            ),
            child: Slider(
              value: value,
              min: min,
              max: max,
              divisions: divisions,
              onChanged: onChanged,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResultRow(String label, String value, {Color? valueColor}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
          ),
          Text(
            value,
            style: TextStyle(
              color: valueColor ?? const Color(0xFFE2E8F0),
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 14),
      decoration: const BoxDecoration(
        color: Color(0xFF0F172A),
        border: Border(
          bottom: BorderSide(color: Color(0xFF1E293B), width: 0.5),
        ),
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF1E293B),
                border: Border.all(color: const Color(0xFF334155)),
              ),
              child: const Icon(Icons.arrow_back_ios_new,
                  color: Color(0xFFE2E8F0), size: 16),
            ),
          ),
          const SizedBox(width: 14),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              color: const Color(0xFF94A3B8).withValues(alpha: 0.12),
            ),
            child: const Icon(Icons.tune_rounded,
                color: Color(0xFF94A3B8), size: 20),
          ),
          const SizedBox(width: 12),
          const Text(
            'What-If Simulator',
            style: TextStyle(
              color: Color(0xFFE2E8F0),
              fontSize: 17,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
