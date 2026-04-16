import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

class MarketContextScreen extends StatelessWidget {
  final Map<String, dynamic> result;

  const MarketContextScreen({super.key, required this.result});

  double _toNum(dynamic v) {
    if (v == null) return 0;
    if (v is num) return v.toDouble();
    return double.tryParse(v.toString()) ?? 0;
  }

  @override
  Widget build(BuildContext context) {
    final metrics = result['metrics'] as Map<String, dynamic>? ?? {};
    final dti = _toNum(metrics['dti']) * 100;
    final freeCashflow = _toNum(metrics['freeCashflow']);

    // Current Egypt market rates
    const interestRate = 27.25;
    const inflationRate = 24.1;
    const realRate = interestRate - inflationRate; // ~3.15%

    // Stance based on rates
    String stance;
    String stanceExplanation;
    Color stanceColor;
    IconData stanceIcon;

    if (interestRate > 25) {
      stance = 'Favor Cash Purchases';
      stanceExplanation =
          'With interest rates at $interestRate%, financing is expensive. If you have cash reserves, paying upfront gives a significant advantage. For installment buyers, negotiate shorter terms.';
      stanceColor = const Color(0xFFF97316);
      stanceIcon = Icons.account_balance_wallet_rounded;
    } else if (interestRate > 15) {
      stance = 'Mixed Approach';
      stanceExplanation =
          'Interest rates are moderate. Balance between cash and installments based on your cashflow capacity.';
      stanceColor = AppColors.gold;
      stanceIcon = Icons.balance_rounded;
    } else {
      stance = 'Leverage Friendly';
      stanceExplanation =
          'Low interest rates make financing attractive. Consider installment plans to preserve cash liquidity.';
      stanceColor = const Color(0xFF22C55E);
      stanceIcon = Icons.trending_up_rounded;
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
                    'Market Context',
                    style: TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Current economic conditions affecting your portfolio',
                    style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                  ),
                  const SizedBox(height: 24),

                  // Interest Rate Card
                  _buildRateCard(
                    icon: Icons.percent_rounded,
                    label: 'CBE Interest Rate',
                    value: '$interestRate%',
                    sublabel: 'Central Bank of Egypt',
                    color: const Color(0xFFF97316),
                  ),
                  const SizedBox(height: 12),

                  // Inflation Rate Card
                  _buildRateCard(
                    icon: Icons.trending_up_rounded,
                    label: 'Inflation Rate',
                    value: '$inflationRate%',
                    sublabel: 'Annual CPI YoY',
                    color: const Color(0xFFEF4444),
                  ),
                  const SizedBox(height: 12),

                  // Real Rate
                  _buildRateCard(
                    icon: Icons.calculate_outlined,
                    label: 'Real Interest Rate',
                    value: '${realRate.toStringAsFixed(2)}%',
                    sublabel: 'Interest − Inflation',
                    color: const Color(0xFF22C55E),
                  ),
                  const SizedBox(height: 24),

                  // Stance Card
                  Container(
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F172A),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(
                        color: stanceColor.withValues(alpha: 0.3),
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
                                color: stanceColor.withValues(alpha: 0.12),
                              ),
                              child:
                                  Icon(stanceIcon, color: stanceColor, size: 20),
                            ),
                            const SizedBox(width: 12),
                            const Text(
                              'Current Stance',
                              style: TextStyle(
                                color: Color(0xFF94A3B8),
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          stance,
                          style: TextStyle(
                            color: stanceColor,
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          stanceExplanation,
                          style: const TextStyle(
                            color: Color(0xFF94A3B8),
                            fontSize: 13,
                            height: 1.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Impact on your portfolio
                  const Text(
                    'Impact on Your Portfolio',
                    style: TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),

                  _buildImpactItem(
                    icon: Icons.payments_outlined,
                    title: 'Installment Costs',
                    description:
                        'High interest means your installments include a larger interest component. Existing fixed-rate plans are unaffected.',
                    color: const Color(0xFFF97316),
                  ),
                  const SizedBox(height: 10),

                  _buildImpactItem(
                    icon: Icons.home_work_outlined,
                    title: 'Property Values',
                    description:
                        'Real estate typically appreciates with inflation, preserving value. Your assets may appreciate ${inflationRate.toStringAsFixed(0)}%+ annually.',
                    color: const Color(0xFF22C55E),
                  ),
                  const SizedBox(height: 10),

                  _buildImpactItem(
                    icon: Icons.savings_outlined,
                    title: 'Cash Reserves',
                    description:
                        'Your cash loses ~${inflationRate.toStringAsFixed(0)}% purchasing power yearly. Consider CDs or investing excess cash.',
                    color: const Color(0xFFEF4444),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRateCard({
    required IconData icon,
    required String label,
    required String value,
    required String sublabel,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              color: color.withValues(alpha: 0.12),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label,
                    style: const TextStyle(
                        color: Color(0xFFE2E8F0), fontSize: 14)),
                Text(sublabel,
                    style: const TextStyle(
                        color: Color(0xFF64748B), fontSize: 11)),
              ],
            ),
          ),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 22,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildImpactItem({
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
              Icon(icon, color: color, size: 18),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(
                  color: color,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            description,
            style: const TextStyle(
              color: Color(0xFF94A3B8),
              fontSize: 13,
              height: 1.4,
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
            child: const Icon(Icons.bar_chart_rounded,
                color: Color(0xFF94A3B8), size: 20),
          ),
          const SizedBox(width: 12),
          const Text(
            'Market Context',
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
