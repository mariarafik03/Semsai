import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

class AiInsightScreen extends StatelessWidget {
  final Map<String, dynamic> result;

  const AiInsightScreen({super.key, required this.result});

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
    final metrics = result['metrics'] as Map<String, dynamic>? ?? {};
    final scores = result['scores'] as Map<String, dynamic>? ?? {};
    final input = result['inputSnapshot'] as Map<String, dynamic>? ?? {};
    final healthBand = (result['healthBand'] ?? 'watch').toString();
    final finalScore = _toNum(result['finalScore']);
    final dti = _toNum(metrics['dti']) * 100;
    final freeCashflow = _toNum(metrics['freeCashflow']);
    final runwayMonths = _toNum(metrics['runwayMonths']);
    final cashflowScore = _toNum(scores['cashflowScore']);
    final riskScore = _toNum(scores['riskScore']);
    final liquidityScore = _toNum(scores['liquidityScore']);

    // Generate dynamic recommendations
    final recommendations = <_Recommendation>[];

    if (dti > 40) {
      recommendations.add(_Recommendation(
        icon: Icons.warning_amber_rounded,
        color: const Color(0xFFEF4444),
        title: 'High Debt-to-Income Ratio',
        description:
            'Your DTI is ${dti.toStringAsFixed(1)}%. Consider paying off existing installments before adding new commitments.',
        action: 'Reduce monthly obligations',
      ));
    }

    if (freeCashflow < 0) {
      recommendations.add(_Recommendation(
        icon: Icons.trending_down_rounded,
        color: const Color(0xFFEF4444),
        title: 'Negative Free Cashflow',
        description:
            'Your expenses + installments exceed your income by ${_formatNum(freeCashflow.abs())} EGP/month. This is unsustainable.',
        action: 'Increase income or reduce expenses',
      ));
    } else if (freeCashflow < 5000) {
      recommendations.add(_Recommendation(
        icon: Icons.info_outline_rounded,
        color: const Color(0xFFF97316),
        title: 'Low Free Cashflow',
        description:
            'You have ${_formatNum(freeCashflow)} EGP/month after obligations. Build an emergency buffer before new investments.',
        action: 'Target 3-6 months expenses saved',
      ));
    }

    if (runwayMonths < 3) {
      recommendations.add(_Recommendation(
        icon: Icons.savings_outlined,
        color: const Color(0xFFF97316),
        title: 'Low Liquidity Runway',
        description:
            'Your cash reserves cover only ${runwayMonths.toStringAsFixed(1)} months. Aim for 6+ months.',
        action: 'Build emergency fund',
      ));
    }

    if (riskScore < 40) {
      recommendations.add(_Recommendation(
        icon: Icons.shield_outlined,
        color: const Color(0xFFEF4444),
        title: 'High Risk Exposure',
        description:
            'Your portfolio risk score is ${riskScore.toStringAsFixed(0)}/100. You\'re close to your maximum installment capacity.',
        action: 'Avoid new commitments',
      ));
    }

    if (cashflowScore > 70 && riskScore > 60 && liquidityScore > 50) {
      recommendations.add(_Recommendation(
        icon: Icons.check_circle_outline_rounded,
        color: const Color(0xFF22C55E),
        title: 'Good Position for Investment',
        description:
            'Your financial health is solid. You can consider a new property within your free cashflow range.',
        action: 'View recommended units below',
      ));
    }

    // Summary recommendation
    String summaryTitle;
    String summaryText;
    Color summaryColor;

    if (healthBand == 'healthy') {
      summaryTitle = 'Expand Cautiously';
      summaryText =
          'Your portfolio health score of ${finalScore.toStringAsFixed(0)} is strong. You have room to add 1-2 more units if installments stay under your DTI limit.';
      summaryColor = const Color(0xFF22C55E);
    } else if (healthBand == 'watch') {
      summaryTitle = 'Hold & Optimize';
      summaryText =
          'Your score of ${finalScore.toStringAsFixed(0)} is moderate. Focus on reducing existing obligations or increasing income before adding new units.';
      summaryColor = const Color(0xFFF97316);
    } else {
      summaryTitle = 'Consolidate First';
      summaryText =
          'Your score of ${finalScore.toStringAsFixed(0)} indicates high risk. Prioritize paying down existing installments and building cash reserves.';
      summaryColor = const Color(0xFFEF4444);
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
                  // Summary Card
                  Container(
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F172A),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(
                        color: summaryColor.withValues(alpha: 0.3),
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
                                color: summaryColor.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Icon(Icons.auto_awesome_rounded,
                                  color: summaryColor, size: 20),
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'AI Recommendation',
                              style: TextStyle(
                                color: const Color(0xFF94A3B8),
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 14),
                        Text(
                          summaryTitle,
                          style: TextStyle(
                            color: summaryColor,
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          summaryText,
                          style: const TextStyle(
                            color: Color(0xFF94A3B8),
                            fontSize: 13,
                            height: 1.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Detailed Recommendations
                  const Text(
                    'Key Findings',
                    style: TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),
                  ...recommendations.map((r) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _buildRecommendationCard(r),
                      )),

                  if (recommendations.isEmpty)
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: const Color(0xFF0F172A),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: const Color(0xFF22C55E).withValues(alpha: 0.3),
                        ),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.check_circle_rounded,
                              color: Color(0xFF22C55E), size: 24),
                          SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'No critical issues found. Your portfolio is in good shape!',
                              style: TextStyle(
                                  color: Color(0xFF94A3B8), fontSize: 13),
                            ),
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
              color: AppColors.gold.withValues(alpha: 0.12),
            ),
            child: Icon(Icons.auto_awesome_rounded,
                color: AppColors.gold, size: 20),
          ),
          const SizedBox(width: 12),
          const Text(
            'AI Insight',
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

  Widget _buildRecommendationCard(_Recommendation r) {
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
            children: [
              Icon(r.icon, color: r.color, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  r.title,
                  style: TextStyle(
                    color: r.color,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            r.description,
            style: const TextStyle(
              color: Color(0xFF94A3B8),
              fontSize: 13,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: r.color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              '→ ${r.action}',
              style: TextStyle(
                color: r.color,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Recommendation {
  final IconData icon;
  final Color color;
  final String title;
  final String description;
  final String action;
  const _Recommendation({
    required this.icon,
    required this.color,
    required this.title,
    required this.description,
    required this.action,
  });
}
