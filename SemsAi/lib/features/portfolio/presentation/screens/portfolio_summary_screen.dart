import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/networking/api_client.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/explore/presentation/screens/unit_detail_screen.dart';
import 'package:SemsAi/features/portfolio/presentation/screens/ai_insight_screen.dart';
import 'package:SemsAi/features/portfolio/presentation/screens/whatif_simulator_screen.dart';
import 'package:SemsAi/features/portfolio/presentation/screens/decision_history_screen.dart';
import 'package:SemsAi/features/portfolio/presentation/screens/market_context_screen.dart';
import 'package:SemsAi/features/portfolio/presentation/screens/inflation_calculator_screen.dart';
import 'package:SemsAi/features/portfolio/presentation/screens/market_analytics_screen.dart';

class PortfolioSummaryScreen extends StatefulWidget {
  final Map<String, dynamic> result;
  final List<Map<String, dynamic>> units;

  const PortfolioSummaryScreen({
    super.key,
    required this.result,
    required this.units,
  });

  @override
  State<PortfolioSummaryScreen> createState() => _PortfolioSummaryScreenState();
}

class _PortfolioSummaryScreenState extends State<PortfolioSummaryScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _entranceCtrl;
  List<Map<String, dynamic>> _matchingUnits = [];
  bool _loadingUnits = true;
  bool _showCalculation = false;

  @override
  void initState() {
    super.initState();
    _entranceCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..forward();
    _fetchMatchingUnits();
  }

  @override
  void dispose() {
    _entranceCtrl.dispose();
    super.dispose();
  }

  Future<void> _fetchMatchingUnits() async {
    try {
      final metrics = widget.result['metrics'] as Map<String, dynamic>? ?? {};
      final input =
          widget.result['inputSnapshot'] as Map<String, dynamic>? ?? {};
      final freeCashflow = _toNum(metrics['freeCashflow']);
      final availableCash = _toNum(input['availableCash']);

      // Use available cash as budget, or estimate from free cashflow
      final budget = availableCash > 0
          ? availableCash
          : (freeCashflow > 0 ? freeCashflow * 60 : 0);

      final res = await ApiClient.post('/portfolio/matching-units', {
        'availableCash': budget,
        'freeCashflow': freeCashflow,
      });

      if (res.statusCode == 200) {
        final body = jsonDecode(res.body) as Map<String, dynamic>;
        final list = (body['units'] as List?) ?? [];
        if (mounted) {
          setState(() {
            _matchingUnits = list.cast<Map<String, dynamic>>();
            _loadingUnits = false;
          });
        }
      } else {
        if (mounted) setState(() => _loadingUnits = false);
      }
    } catch (e) {
      if (mounted) setState(() => _loadingUnits = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final metrics = (widget.result['metrics'] as Map<String, dynamic>? ?? {});
    final scores = (widget.result['scores'] as Map<String, dynamic>? ?? {});
    final finalScore = _toNum(widget.result['finalScore']);
    final healthBand = (widget.result['healthBand'] ?? 'watch').toString();

    return Scaffold(
      backgroundColor: const Color(0xFF020617),
      body: SafeArea(
        child: FadeTransition(
          opacity: _entranceCtrl,
          child: Column(
            children: [
              _buildHeader(),
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  children: [
                    const SizedBox(height: 8),
                    // SEMSAI branding
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
                      'Your Portfolio',
                      style: TextStyle(
                        color: Color(0xFFE2E8F0),
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 20),

                    // ── Health Card
                    _buildHealthCard(finalScore, healthBand, scores),
                    const SizedBox(height: 16),

                    // ── Action Cards Grid
                    _buildActionCardsGrid(),
                    const SizedBox(height: 16),

                    // ── Monthly Burden Card
                    _buildMonthlyBurdenCard(metrics),
                    const SizedBox(height: 20),

                    // ── Units Section
                    Text(
                      '${widget.units.length} Units',
                      style: const TextStyle(
                        color: Color(0xFF94A3B8),
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: 12),
                    ...widget.units.asMap().entries.map((entry) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _buildUnitCard(entry.key + 1, entry.value),
                      );
                    }),

                    const SizedBox(height: 24),

                    // ── Recommended Units from DB
                    _buildMatchingUnitsSection(),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Header ────────────────────────────────────────────
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
              child: const Icon(
                Icons.arrow_back_ios_new,
                color: Color(0xFFE2E8F0),
                size: 16,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: [AppColors.gold, AppColors.gold.withValues(alpha: 0.6)],
              ),
            ),
            child: const Icon(
              Icons.assessment_rounded,
              color: Colors.white,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Portfolio Overview',
                  style: TextStyle(
                    color: Color(0xFFE2E8F0),
                    fontSize: 17,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  'Your investment health',
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ─── Health Card ───────────────────────────────────────
  Widget _buildHealthCard(
    double finalScore,
    String healthBand,
    Map<String, dynamic> scores,
  ) {
    final cashflow = _toNum(scores['cashflowScore']);
    final risk = _toNum(scores['riskScore']);
    final liquidity = _toNum(scores['liquidityScore']);
    final flexibility = _toNum(scores['flexibilityScore']);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // Circular score
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: _bandColor(healthBand), width: 3.5),
                ),
                alignment: Alignment.center,
                child: Text(
                  finalScore.toStringAsFixed(0),
                  style: const TextStyle(
                    color: Color(0xFFE2E8F0),
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Portfolio Health',
                    style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                  ),
                  Text(
                    _bandLabel(healthBand),
                    style: TextStyle(
                      color: _bandColor(healthBand),
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 20),
          _buildMetricBar('Cashflow', cashflow, AppColors.gold),
          const SizedBox(height: 14),
          _buildMetricBar('Risk', risk, const Color(0xFFF97316)),
          const SizedBox(height: 14),
          _buildMetricBar('Liquidity', liquidity, AppColors.gold),
          const SizedBox(height: 14),
          _buildMetricBar('Flexibility', flexibility, const Color(0xFF22C55E)),
          const SizedBox(height: 16),

          // Expandable "How is this calculated?"
          GestureDetector(
            onTap: () => setState(() => _showCalculation = !_showCalculation),
            child: Row(
              children: [
                Icon(
                  _showCalculation
                      ? Icons.expand_less_rounded
                      : Icons.info_outline_rounded,
                  color: AppColors.gold.withValues(alpha: 0.7),
                  size: 16,
                ),
                const SizedBox(width: 6),
                Text(
                  'How is this calculated?',
                  style: TextStyle(
                    color: AppColors.gold.withValues(alpha: 0.7),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),

          // Expanded explanation
          AnimatedCrossFade(
            firstChild: const SizedBox.shrink(),
            secondChild: Padding(
              padding: const EdgeInsets.only(top: 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildExplanation(
                    'Cashflow (25%):',
                    'Ratio of your income to monthly obligations. Higher = better.',
                  ),
                  const SizedBox(height: 8),
                  _buildExplanation(
                    'Risk (25%):',
                    'Exposure to market volatility and payment defaults. Lower exposure = higher score.',
                  ),
                  const SizedBox(height: 8),
                  _buildExplanation(
                    'Liquidity (25%):',
                    'How quickly you can convert assets to cash without significant loss.',
                  ),
                  const SizedBox(height: 8),
                  _buildExplanation(
                    'Flexibility (25%):',
                    'Ability to adapt to changing market conditions or personal circumstances.',
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Assumptions: Interest rate at 27.25%, Inflation at 24.1%',
                    style: TextStyle(
                      color: const Color(0xFF64748B),
                      fontSize: 11,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ],
              ),
            ),
            crossFadeState: _showCalculation
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 300),
          ),
        ],
      ),
    );
  }

  Widget _buildExplanation(String title, String text) {
    return RichText(
      text: TextSpan(
        children: [
          TextSpan(
            text: title,
            style: const TextStyle(
              color: Color(0xFFE2E8F0),
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
          TextSpan(
            text: ' $text',
            style: const TextStyle(
              color: Color(0xFF94A3B8),
              fontSize: 13,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }

  // ─── Metric Bar ────────────────────────────────────────
  Widget _buildMetricBar(String label, double value, Color color) {
    final clamped = value.clamp(0.0, 100.0);
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 14),
            ),
            Text(
              '${clamped.toStringAsFixed(0)}/100',
              style: const TextStyle(
                color: Color(0xFFE2E8F0),
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: clamped / 100,
            minHeight: 6,
            backgroundColor: const Color(0xFF1E293B),
            valueColor: AlwaysStoppedAnimation<Color>(color),
          ),
        ),
      ],
    );
  }

  // ─── Monthly Burden Card ───────────────────────────────
  Widget _buildMonthlyBurdenCard(Map<String, dynamic> metrics) {
    final monthlyBurden = _toNum(metrics['totalInstallments']);
    final dti = _toNum(metrics['dti']) * 100;
    final healthBand = (widget.result['healthBand'] ?? 'watch').toString();

    String riskDesc;
    if (healthBand == 'healthy') {
      riskDesc =
          'Your current portfolio requires ${_formatNumber(monthlyBurden)} EGP/month and has low risk exposure.';
    } else if (healthBand == 'watch') {
      riskDesc =
          'Your current portfolio requires ${_formatNumber(monthlyBurden)} EGP/month and is moderately exposed to risk.';
    } else {
      riskDesc =
          'Your current portfolio requires ${_formatNumber(monthlyBurden)} EGP/month and is highly exposed to risk.';
    }

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
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  color: AppColors.gold.withValues(alpha: 0.12),
                ),
                child: Icon(
                  Icons.shield_outlined,
                  color: AppColors.gold,
                  size: 18,
                ),
              ),
              const SizedBox(width: 10),
              const Text(
                'Monthly burden',
                style: TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            '${_formatNumber(monthlyBurden)} EGP',
            style: const TextStyle(
              color: Color(0xFFE2E8F0),
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            riskDesc,
            style: const TextStyle(
              color: Color(0xFF94A3B8),
              fontSize: 12,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoChip(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(6),
        color: const Color(0xFF1E293B),
      ),
      child: Text(
        '$label: $value',
        style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
      ),
    );
  }

  // ─── Action Cards Grid ─────────────────────────────────
  Widget _buildActionCardsGrid() {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _buildActionCard(
                icon: Icons.psychology_rounded,
                title: 'AI Insight',
                subtitle: 'Actionable recommendations',
                color: AppColors.gold,
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => AiInsightScreen(result: widget.result),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildActionCard(
                icon: Icons.tune_rounded,
                title: 'What-If Simulator',
                subtitle: 'Simulate scenarios',
                color: const Color(0xFF94A3B8),
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        WhatIfSimulatorScreen(result: widget.result),
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _buildActionCard(
                icon: Icons.history_rounded,
                title: 'Decision History',
                subtitle: 'Review past decisions',
                color: const Color(0xFF94A3B8),
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => DecisionHistoryScreen(
                      result: widget.result,
                      units: widget.units,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildActionCard(
                icon: Icons.bar_chart_rounded,
                title: 'Market Context',
                subtitle: 'Interest & inflation',
                color: const Color(0xFF94A3B8),
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => MarketContextScreen(result: widget.result),
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _buildActionCard(
                icon: Icons.calculate_rounded,
                title: 'Inflation Calc',
                subtitle: 'Future value estimate',
                color: const Color(0xFF22C55E),
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        InflationCalculatorScreen(result: widget.result),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildActionCard(
                icon: Icons.analytics_rounded,
                title: 'Market Analytics',
                subtitle: 'Area & developer prices',
                color: const Color(0xFF3B82F6),
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const MarketAnalyticsScreen(),
                  ),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildActionCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
    VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF0F172A),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFF1E293B)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                color: color.withValues(alpha: 0.12),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(height: 12),
            Text(
              title,
              style: const TextStyle(
                color: Color(0xFFE2E8F0),
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              subtitle,
              style: const TextStyle(color: Color(0xFF64748B), fontSize: 11),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Unit Card (Lovable Design) ────────────────────────
  Widget _buildUnitCard(int index, Map<String, dynamic> unit) {
    final name = (unit['name'] ?? 'Unit $index').toString();
    final type = (unit['type'] ?? '').toString();
    final installment = _toNum(unit['monthlyInstallment']);
    final remaining = _toNum(unit['remainingBalance']);
    final marketValue = _toNum(unit['marketValue']);

    // Calculate risk band for this unit
    final dtiContribution = installment > 0
        ? installment / (installment + remaining * 0.01)
        : 0;
    String statusLabel;
    Color statusColor;
    String riskText;
    int riskDots;

    if (dtiContribution > 0.6 || installment > 35000) {
      statusLabel = 'Under pressure';
      statusColor = const Color(0xFFEF4444);
      riskText = 'High Risk';
      riskDots = 3;
    } else if (dtiContribution > 0.3 || installment > 20000) {
      statusLabel = 'Balanced';
      statusColor = const Color(0xFF22C55E);
      riskText = 'Medium Risk';
      riskDots = 2;
    } else {
      statusLabel = 'Flexible';
      statusColor = const Color(0xFF3B82F6);
      riskText = 'Low Risk';
      riskDots = 1;
    }

    // Estimate remaining months
    final remainingMonths = installment > 0
        ? (remaining / installment).round()
        : 0;
    // Total estimated months (rough)
    final totalMonths = installment > 0
        ? ((remaining + marketValue * 0.3) / installment).round()
        : 0;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Top row: name + status badge
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      style: const TextStyle(
                        color: Color(0xFFE2E8F0),
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (type.isNotEmpty)
                      Text(
                        type,
                        style: const TextStyle(
                          color: Color(0xFF64748B),
                          fontSize: 12,
                        ),
                      ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(6),
                  color: statusColor.withValues(alpha: 0.12),
                  border: Border.all(color: statusColor.withValues(alpha: 0.3)),
                ),
                child: Text(
                  statusLabel,
                  style: TextStyle(
                    color: statusColor,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),

          // Monthly + Remaining row
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'MONTHLY',
                      style: TextStyle(
                        color: Color(0xFF64748B),
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${_formatNumber(installment)} EGP',
                      style: const TextStyle(
                        color: Color(0xFFE2E8F0),
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'REMAINING',
                      style: TextStyle(
                        color: Color(0xFF64748B),
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '$remainingMonths/${totalMonths > 0 ? totalMonths : "—"} months',
                      style: const TextStyle(
                        color: Color(0xFFE2E8F0),
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Bottom: risk dots + Analyze
          Row(
            children: [
              // Risk dots
              Row(
                children: List.generate(3, (i) {
                  return Container(
                    width: 10,
                    height: 10,
                    margin: const EdgeInsets.only(right: 4),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: i < riskDots
                          ? statusColor
                          : const Color(0xFF1E293B),
                    ),
                  );
                }),
              ),
              const SizedBox(width: 8),
              Text(
                riskText,
                style: TextStyle(
                  color: statusColor,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const Spacer(),
              Text(
                'Analyze >',
                style: TextStyle(
                  color: AppColors.gold,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ─── Helpers ───────────────────────────────────────────
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

  static Color _bandColor(String band) {
    switch (band) {
      case 'healthy':
        return const Color(0xFF22C55E);
      case 'watch':
        return AppColors.gold;
      default:
        return const Color(0xFFEF4444);
    }
  }

  static String _formatNumber(double value) {
    final rounded = value.round().toString();
    return rounded.replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (m) => '${m[1]},',
    );
  }

  // ─── Matching Units Section ────────────────────────────
  Widget _buildMatchingUnitsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                color: const Color(0xFF22C55E).withValues(alpha: 0.12),
              ),
              child: const Icon(
                Icons.recommend_rounded,
                color: Color(0xFF22C55E),
                size: 18,
              ),
            ),
            const SizedBox(width: 10),
            const Text(
              'Recommended For You',
              style: TextStyle(
                color: Color(0xFFE2E8F0),
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        const Text(
          'Properties matching your financial profile',
          style: TextStyle(color: Color(0xFF64748B), fontSize: 12),
        ),
        const SizedBox(height: 14),
        if (_loadingUnits)
          Container(
            padding: const EdgeInsets.all(32),
            decoration: BoxDecoration(
              color: const Color(0xFF0F172A),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFF1E293B)),
            ),
            child: const Center(
              child: Column(
                children: [
                  SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Color(0xFFD4A44A),
                    ),
                  ),
                  SizedBox(height: 12),
                  Text(
                    'Finding matching units...',
                    style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                  ),
                ],
              ),
            ),
          )
        else if (_matchingUnits.isEmpty)
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: const Color(0xFF0F172A),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFF1E293B)),
            ),
            child: const Center(
              child: Column(
                children: [
                  Icon(
                    Icons.search_off_rounded,
                    color: Color(0xFF475569),
                    size: 36,
                  ),
                  SizedBox(height: 10),
                  Text(
                    'No matching units found',
                    style: TextStyle(color: Color(0xFF94A3B8), fontSize: 14),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Try adjusting your budget or preferences',
                    style: TextStyle(color: Color(0xFF64748B), fontSize: 12),
                  ),
                ],
              ),
            ),
          )
        else
          ...List.generate(_matchingUnits.length, (i) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _buildMatchingUnitCard(_matchingUnits[i]),
            );
          }),
      ],
    );
  }

  Widget _buildMatchingUnitCard(Map<String, dynamic> unit) {
    final name = (unit['compound_name'] ?? '').toString();
    final location = (unit['location'] ?? '').toString();
    final type = (unit['type'] ?? '').toString();
    final price = _toNum(unit['price']);
    final area = _toNum(unit['area']);
    final bedrooms = _toNum(unit['bedrooms']).toInt();
    final saleType = (unit['sale_type'] ?? '').toString();

    return GestureDetector(
      onTap: () {
        final compoundUnit = CompoundUnit.fromJson(unit);
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => UnitDetailScreen(unit: compoundUnit),
          ),
        );
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF0F172A),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFF1E293B)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top row: name + type badge
            Row(
              children: [
                Expanded(
                  child: Text(
                    name.isNotEmpty ? name : 'Unknown Compound',
                    style: const TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (type.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(6),
                      color: AppColors.gold.withValues(alpha: 0.12),
                    ),
                    child: Text(
                      type,
                      style: TextStyle(
                        color: AppColors.gold,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            // Location
            if (location.isNotEmpty)
              Row(
                children: [
                  const Icon(
                    Icons.location_on_outlined,
                    color: Color(0xFF64748B),
                    size: 14,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    location,
                    style: const TextStyle(
                      color: Color(0xFF94A3B8),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            const SizedBox(height: 12),
            // Details row
            Row(
              children: [
                // Price
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Price',
                        style: TextStyle(
                          color: Color(0xFF64748B),
                          fontSize: 11,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${_formatNumber(price)} EGP',
                        style: const TextStyle(
                          color: Color(0xFFE2E8F0),
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
                // Area
                if (area > 0)
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Area',
                          style: TextStyle(
                            color: Color(0xFF64748B),
                            fontSize: 11,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${area.toStringAsFixed(0)} m²',
                          style: const TextStyle(
                            color: Color(0xFFE2E8F0),
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                // Bedrooms
                if (bedrooms > 0)
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Beds',
                          style: TextStyle(
                            color: Color(0xFF64748B),
                            fontSize: 11,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '$bedrooms',
                          style: const TextStyle(
                            color: Color(0xFFE2E8F0),
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
            if (saleType.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(4),
                  color: const Color(0xFF1E293B),
                ),
                child: Text(
                  saleType,
                  style: const TextStyle(
                    color: Color(0xFF94A3B8),
                    fontSize: 11,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
