import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

class InflationCalculatorScreen extends StatefulWidget {
  final Map<String, dynamic> result;

  const InflationCalculatorScreen({super.key, required this.result});

  @override
  State<InflationCalculatorScreen> createState() =>
      _InflationCalculatorScreenState();
}

class _InflationCalculatorScreenState extends State<InflationCalculatorScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animCtrl;
  late final TextEditingController _priceController;

  double _years = 5;
  double _inflationRate = 24.1;
  double _propertyPrice = 0;

  @override
  void initState() {
    super.initState();
    _animCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..forward();

    // Pre-fill from portfolio data if available
    final metrics = widget.result['metrics'] as Map<String, dynamic>? ?? {};
    final totalAssets = _toNum(metrics['totalMarketValue']);
    _propertyPrice = totalAssets > 0 ? totalAssets : 3000000;
    _priceController =
        TextEditingController(text: _propertyPrice.round().toString());
  }

  @override
  void dispose() {
    _animCtrl.dispose();
    _priceController.dispose();
    super.dispose();
  }

  double _toNum(dynamic v) {
    if (v == null) return 0;
    if (v is num) return v.toDouble();
    return double.tryParse(v.toString()) ?? 0;
  }

  // ─── Calculations ─────────────────────────────────────
  double get _futureValue =>
      _propertyPrice * pow(1 + _inflationRate / 100, _years.round());

  double get _totalAppreciation =>
      _propertyPrice > 0 ? ((_futureValue - _propertyPrice) / _propertyPrice) * 100 : 0;

  double get _totalGain => _futureValue - _propertyPrice;

  List<double> get _yearlyValues {
    return List.generate(_years.round(), (i) {
      return _propertyPrice * pow(1 + _inflationRate / 100, i + 1);
    });
  }

  String _formatNumber(double value) {
    if (value >= 1000000) {
      return '${(value / 1000000).toStringAsFixed(1)}M';
    } else if (value >= 1000) {
      return '${(value / 1000).toStringAsFixed(0)}K';
    }
    return value.round().toString();
  }

  String _formatFullNumber(double value) {
    final rounded = value.round().toString();
    return rounded.replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (m) => '${m[1]},',
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF020617),
      body: SafeArea(
        child: FadeTransition(
          opacity: _animCtrl,
          child: Column(
            children: [
              _buildHeader(),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    const Text(
                      'Inflation Calculator',
                      style: TextStyle(
                        color: Color(0xFFE2E8F0),
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Estimate future property value based on inflation',
                      style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                    ),
                    const SizedBox(height: 24),

                    // ── Property Price Input
                    _buildPriceInput(),
                    const SizedBox(height: 20),

                    // ── Years Slider
                    _buildSliderCard(
                      icon: Icons.calendar_month_rounded,
                      label: 'Investment Period',
                      value: '${_years.round()} years',
                      slider: Slider(
                        value: _years,
                        min: 1,
                        max: 15,
                        divisions: 14,
                        activeColor: AppColors.gold,
                        inactiveColor: const Color(0xFF1E293B),
                        onChanged: (v) => setState(() => _years = v),
                      ),
                      sublabel: '1 — 15 years',
                    ),
                    const SizedBox(height: 12),

                    // ── Inflation Rate Slider
                    _buildSliderCard(
                      icon: Icons.trending_up_rounded,
                      label: 'Annual Inflation Rate',
                      value: '${_inflationRate.toStringAsFixed(1)}%',
                      slider: Slider(
                        value: _inflationRate,
                        min: 5,
                        max: 40,
                        divisions: 70,
                        activeColor: const Color(0xFFF97316),
                        inactiveColor: const Color(0xFF1E293B),
                        onChanged: (v) => setState(() => _inflationRate = v),
                      ),
                      sublabel: '5% — 40%',
                    ),
                    const SizedBox(height: 24),

                    // ── Results Summary
                    _buildResultsCard(),
                    const SizedBox(height: 20),

                    // ── Year-by-Year Projection
                    _buildProjectionBars(),
                    const SizedBox(height: 20),

                    // ── Key Insights
                    _buildInsightsSection(),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Header ───────────────────────────────────────────
  Widget _buildHeader() {
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
              gradient: LinearGradient(
                colors: [
                  const Color(0xFF22C55E).withValues(alpha: 0.2),
                  const Color(0xFF22C55E).withValues(alpha: 0.05),
                ],
              ),
            ),
            child: const Icon(Icons.calculate_rounded,
                color: Color(0xFF22C55E), size: 20),
          ),
          const SizedBox(width: 12),
          const Text(
            'Inflation Calculator',
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

  // ─── Price Input ──────────────────────────────────────
  Widget _buildPriceInput() {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  color: AppColors.gold.withValues(alpha: 0.12),
                ),
                child: Icon(Icons.home_rounded, color: AppColors.gold, size: 18),
              ),
              const SizedBox(width: 10),
              const Text(
                'Property Value',
                style: TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: const Color(0xFF020617),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF334155)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _priceController,
                    keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    style: const TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                    decoration: const InputDecoration(
                      border: InputBorder.none,
                      hintText: 'Enter price',
                      hintStyle: TextStyle(color: Color(0xFF475569)),
                    ),
                    onChanged: (v) {
                      setState(() {
                        _propertyPrice = double.tryParse(v) ?? 0;
                      });
                    },
                  ),
                ),
                const Text(
                  'EGP',
                  style: TextStyle(
                    color: Color(0xFF94A3B8),
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          if (_propertyPrice > 0) ...[
            const SizedBox(height: 8),
            Text(
              '≈ ${_formatFullNumber(_propertyPrice)} EGP',
              style: TextStyle(
                color: AppColors.gold.withValues(alpha: 0.7),
                fontSize: 12,
              ),
            ),
          ],
        ],
      ),
    );
  }

  // ─── Slider Card ──────────────────────────────────────
  Widget _buildSliderCard({
    required IconData icon,
    required String label,
    required String value,
    required Widget slider,
    required String sublabel,
  }) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Icon(icon, color: const Color(0xFF94A3B8), size: 18),
              const SizedBox(width: 8),
              Text(
                label,
                style: const TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(6),
                  color: AppColors.gold.withValues(alpha: 0.12),
                ),
                child: Text(
                  value,
                  style: TextStyle(
                    color: AppColors.gold,
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          slider,
          Text(
            sublabel,
            style: const TextStyle(color: Color(0xFF475569), fontSize: 11),
          ),
        ],
      ),
    );
  }

  // ─── Results Card ─────────────────────────────────────
  Widget _buildResultsCard() {
    if (_propertyPrice <= 0) {
      return Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: const Color(0xFF0F172A),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFF1E293B)),
        ),
        child: const Center(
          child: Text(
            'Enter a property value to see projections',
            style: TextStyle(color: Color(0xFF64748B), fontSize: 13),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: const Color(0xFF22C55E).withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(10),
                  color: const Color(0xFF22C55E).withValues(alpha: 0.12),
                ),
                child: const Icon(Icons.rocket_launch_rounded,
                    color: Color(0xFF22C55E), size: 20),
              ),
              const SizedBox(width: 12),
              const Text(
                'Projected Value',
                style: TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Future Value
          Text(
            '${_formatFullNumber(_futureValue)} EGP',
            style: const TextStyle(
              color: Color(0xFFE2E8F0),
              fontSize: 28,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'After ${_years.round()} year${_years.round() > 1 ? "s" : ""} at ${_inflationRate.toStringAsFixed(1)}% inflation',
            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
          ),
          const SizedBox(height: 20),

          // Metrics row
          Row(
            children: [
              Expanded(
                child: _buildMetric(
                  label: 'Total Gain',
                  value: '+${_formatFullNumber(_totalGain)} EGP',
                  color: const Color(0xFF22C55E),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMetric(
                  label: 'ROI',
                  value: '+${_totalAppreciation.toStringAsFixed(1)}%',
                  color: AppColors.gold,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildMetric(
                  label: 'Multiplier',
                  value: '${(_futureValue / _propertyPrice).toStringAsFixed(1)}x',
                  color: const Color(0xFF3B82F6),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetric({
    required String label,
    required String value,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        color: color.withValues(alpha: 0.08),
      ),
      child: Column(
        children: [
          Text(
            label,
            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 10),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.bold,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  // ─── Projection Bars ──────────────────────────────────
  Widget _buildProjectionBars() {
    if (_propertyPrice <= 0) return const SizedBox.shrink();

    final values = _yearlyValues;
    final double maxVal = values.isNotEmpty ? values.last : 1;

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.bar_chart_rounded,
                  color: Color(0xFF94A3B8), size: 18),
              SizedBox(width: 8),
              Text(
                'Year-by-Year Projection',
                style: TextStyle(
                  color: Color(0xFFE2E8F0),
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Starting value
          _buildBarRow(
            label: 'Today',
            value: _propertyPrice,
            maxVal: maxVal,
            color: const Color(0xFF475569),
            isFirst: true,
          ),
          const SizedBox(height: 6),

          // Year projections
          ...values.asMap().entries.map((entry) {
            final yearNum = entry.key + 1;
            final val = entry.value;
            final isLast = yearNum == values.length;
            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: _buildBarRow(
                label: 'Year $yearNum',
                value: val,
                maxVal: maxVal,
                color: isLast
                    ? const Color(0xFF22C55E)
                    : AppColors.gold.withValues(
                        alpha: 0.4 + (yearNum / values.length) * 0.6),
                isFirst: false,
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildBarRow({
    required String label,
    required double value,
    required double maxVal,
    required Color color,
    required bool isFirst,
  }) {
    final fraction = (value / maxVal).clamp(0.0, 1.0);
    return Row(
      children: [
        SizedBox(
          width: 50,
          child: Text(
            label,
            style: TextStyle(
              color: isFirst ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
              fontSize: 11,
              fontWeight: isFirst ? FontWeight.w600 : FontWeight.normal,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: LayoutBuilder(
            builder: (ctx, constraints) {
              return Stack(
                children: [
                  Container(
                    height: 22,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(4),
                      color: const Color(0xFF1E293B),
                    ),
                  ),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 500),
                    curve: Curves.easeOutCubic,
                    height: 22,
                    width: constraints.maxWidth * fraction,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(4),
                      gradient: LinearGradient(
                        colors: [
                          color.withValues(alpha: 0.7),
                          color,
                        ],
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 52,
          child: Text(
            _formatNumber(value),
            style: TextStyle(
              color: isFirst ? const Color(0xFF94A3B8) : const Color(0xFFE2E8F0),
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
            textAlign: TextAlign.right,
          ),
        ),
      ],
    );
  }

  // ─── Insights Section ─────────────────────────────────
  Widget _buildInsightsSection() {
    if (_propertyPrice <= 0) return const SizedBox.shrink();

    // Calculate real appreciation (vs cash)
    final cashAfterInflation =
        _propertyPrice / pow(1 + _inflationRate / 100, _years.round());
    final cashLoss = _propertyPrice - cashAfterInflation;

    // Annual compound growth
    final annualReturn = _inflationRate;

    // Break-even with bank deposit (27.25% interest)
    const bankRate = 27.25;
    final bankFuture = _propertyPrice * pow(1 + bankRate / 100, _years.round());
    final propertyBeatsBank = _futureValue > bankFuture;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Icon(Icons.lightbulb_outline_rounded,
                color: Color(0xFFE2E8F0), size: 18),
            SizedBox(width: 8),
            Text(
              'Key Insights',
              style: TextStyle(
                color: Color(0xFFE2E8F0),
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),

        _buildInsightCard(
          icon: Icons.shield_outlined,
          title: 'Inflation Hedge',
          description:
              'If you held ${_formatFullNumber(_propertyPrice)} EGP as cash, it would only buy what ${_formatFullNumber(cashAfterInflation)} EGP buys today — losing ${_formatFullNumber(cashLoss)} EGP in purchasing power.',
          color: const Color(0xFFF97316),
        ),
        const SizedBox(height: 10),

        _buildInsightCard(
          icon: Icons.trending_up_rounded,
          title: 'Compound Growth',
          description:
              'At ${annualReturn.toStringAsFixed(1)}% annual appreciation, your property doubles every ~${(72 / annualReturn).toStringAsFixed(1)} years (Rule of 72).',
          color: const Color(0xFF22C55E),
        ),
        const SizedBox(height: 10),

        _buildInsightCard(
          icon: Icons.account_balance_rounded,
          title: propertyBeatsBank
              ? 'Beats Bank Deposits'
              : 'Bank Deposits Better Short-Term',
          description: propertyBeatsBank
              ? 'Property appreciation (${_formatNumber(_futureValue)}) outperforms a bank deposit at $bankRate% (${_formatNumber(bankFuture)}) over ${_years.round()} years.'
              : 'A bank deposit at $bankRate% would yield ${_formatNumber(bankFuture)} vs property at ${_formatNumber(_futureValue)}. Consider shorter installments.',
          color: propertyBeatsBank
              ? const Color(0xFF22C55E)
              : const Color(0xFFEF4444),
        ),
      ],
    );
  }

  Widget _buildInsightCard({
    required IconData icon,
    required String title,
    required String description,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(5),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(6),
                  color: color.withValues(alpha: 0.12),
                ),
                child: Icon(icon, color: color, size: 16),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    color: color,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            description,
            style: const TextStyle(
              color: Color(0xFF94A3B8),
              fontSize: 13,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }
}
