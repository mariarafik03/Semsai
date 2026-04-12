import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/networking/api_client.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/explore/presentation/screens/unit_detail_screen.dart';

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
      final input = widget.result['inputSnapshot'] as Map<String, dynamic>? ?? {};
      final freeCashflow = _toNum(metrics['freeCashflow']);
      final availableCash = _toNum(input['availableCash']);

      // Use available cash as budget, or estimate from free cashflow
      final budget = availableCash > 0 ? availableCash : (freeCashflow > 0 ? freeCashflow * 60 : 0);

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

                    // ── Monthly Burden Card
                    _buildMonthlyBurdenCard(metrics),
                    const SizedBox(height: 20),

                    // ── Action Cards Grid
                    _buildActionCardsGrid(),
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
                colors: [
                  AppColors.gold,
                  AppColors.gold.withValues(alpha: 0.6),
                ],
              ),
            ),
            child: const Icon(Icons.assessment_rounded,
                color: Colors.white, size: 20),
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
                  style: TextStyle(
                    color: Color(0xFF94A3B8),
                    fontSize: 12,
                  ),
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
      double finalScore, String healthBand, Map<String, dynamic> scores) {
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
                  border: Border.all(
                    color: _bandColor(healthBand),
                    width: 3.5,
                  ),
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
                    style: TextStyle(
                      color: Color(0xFF94A3B8),
                      fontSize: 13,
                    ),
                  ),
                  Text(
                    _bandLabel(healthBand),
                    style: TextStyle(
                      color: _bandColor(healthBand),
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    '↑ 6 from last decision',
                    style: TextStyle(
                      color: const Color(0xFF22C55E),
                      fontSize: 12,
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
          Row(
            children: [
              Icon(Icons.info_outline_rounded,
                  color: AppColors.gold.withValues(alpha: 0.7), size: 16),
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
    final freeCashflow = _toNum(metrics['freeCashflow']);
    final dti = _toNum(metrics['dti']) * 100;

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
                  color: const Color(0xFFF97316).withValues(alpha: 0.12),
                ),
                child: const Icon(Icons.trending_down_rounded,
                    color: Color(0xFFF97316), size: 18),
              ),
              const SizedBox(width: 10),
              const Text(
                'Monthly Burden',
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
          const SizedBox(height: 6),
          Row(
            children: [
              _buildInfoChip(
                  'Free cashflow', '${_formatNumber(freeCashflow)} EGP'),
              const SizedBox(width: 12),
              _buildInfoChip('DTI', '${dti.toStringAsFixed(1)}%'),
            ],
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
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildActionCard(
                icon: Icons.tune_rounded,
                title: 'What-If Simulator',
                subtitle: 'Simulate scenarios',
                color: const Color(0xFF94A3B8),
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
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildActionCard(
                icon: Icons.bar_chart_rounded,
                title: 'Market Context',
                subtitle: 'Interest & inflation',
                color: const Color(0xFF94A3B8),
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
  }) {
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
            style: const TextStyle(
              color: Color(0xFF64748B),
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  // ─── Unit Card ─────────────────────────────────────────
  Widget _buildUnitCard(int index, Map<String, dynamic> unit) {
    final installment = _toNum(unit['monthlyInstallment']);
    final remaining = _toNum(unit['remainingBalance']);
    final marketValue = _toNum(unit['marketValue']);

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
          Row(
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(6),
                  color: AppColors.gold.withValues(alpha: 0.12),
                ),
                child: Center(
                  child: Text(
                    '$index',
                    style: TextStyle(
                      color: AppColors.gold,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                'Unit $index',
                style: const TextStyle(
                  color: Color(0xFFE2E8F0),
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _buildUnitRow(Icons.calendar_month_rounded, 'Monthly',
              '${_formatNumber(installment)} EGP'),
          const SizedBox(height: 8),
          _buildUnitRow(Icons.account_balance_rounded, 'Remaining',
              '${_formatNumber(remaining)} EGP'),
          const SizedBox(height: 8),
          _buildUnitRow(Icons.trending_up_rounded, 'Market Value',
              '${_formatNumber(marketValue)} EGP'),
        ],
      ),
    );
  }

  Widget _buildUnitRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, color: const Color(0xFF475569), size: 16),
        const SizedBox(width: 8),
        Text(
          label,
          style:
              const TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
        ),
        const Spacer(),
        Text(
          value,
          style: const TextStyle(
            color: Color(0xFFE2E8F0),
            fontSize: 13,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
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
              child: const Icon(Icons.recommend_rounded,
                  color: Color(0xFF22C55E), size: 18),
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
                  Icon(Icons.search_off_rounded,
                      color: Color(0xFF475569), size: 36),
                  SizedBox(height: 10),
                  Text(
                    'No matching units found',
                    style: TextStyle(
                        color: Color(0xFF94A3B8), fontSize: 14),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Try adjusting your budget or preferences',
                    style: TextStyle(
                        color: Color(0xFF64748B), fontSize: 12),
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
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
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
                const Icon(Icons.location_on_outlined,
                    color: Color(0xFF64748B), size: 14),
                const SizedBox(width: 4),
                Text(
                  location,
                  style: const TextStyle(
                      color: Color(0xFF94A3B8), fontSize: 12),
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
                    const Text('Price',
                        style: TextStyle(
                            color: Color(0xFF64748B), fontSize: 11)),
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
                      const Text('Area',
                          style: TextStyle(
                              color: Color(0xFF64748B), fontSize: 11)),
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
                      const Text('Beds',
                          style: TextStyle(
                              color: Color(0xFF64748B), fontSize: 11)),
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
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(4),
                color: const Color(0xFF1E293B),
              ),
              child: Text(
                saleType,
                style: const TextStyle(
                    color: Color(0xFF94A3B8), fontSize: 11),
              ),
            ),
          ],
        ],
      ),
    ),
    );
  }
}
