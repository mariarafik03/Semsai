import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class DecisionHistoryScreen extends StatelessWidget {
  final Map<String, dynamic> result;
  final List<Map<String, dynamic>> units;

  const DecisionHistoryScreen({
    super.key,
    required this.result,
    required this.units,
  });

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
    final finalScore = _toNum(result['finalScore']);

    // Build timeline from existing units
    final timeline = <_TimelineEntry>[];

    // Portfolio created
    timeline.add(_TimelineEntry(
      icon: Icons.play_circle_outline_rounded,
      color: AppColors.gold,
      title: 'Portfolio Created',
      subtitle: 'Initial analysis with ${units.length} unit${units.length > 1 ? 's' : ''}',
      impact: '+${finalScore.toStringAsFixed(0)} pts',
      impactPositive: true,
    ));

    // Add each unit as a decision
    for (int i = 0; i < units.length; i++) {
      final u = units[i];
      final name = (u['name'] ?? 'Unit ${i + 1}').toString();
      final installment = _toNum(u['monthlyInstallment']);
      final remaining = _toNum(u['remainingBalance']);

      final isHeavy = installment > 30000;

      timeline.add(_TimelineEntry(
        icon: Icons.add_home_rounded,
        color: isHeavy ? const Color(0xFFF97316) : const Color(0xFF22C55E),
        title: 'Added $name',
        subtitle: '${_formatNum(installment)} EGP/mo • ${_formatNum(remaining)} EGP remaining',
        impact: isHeavy ? '-12 pts' : '+8 pts',
        impactPositive: !isHeavy,
      ));
    }

    // Current state
    timeline.add(_TimelineEntry(
      icon: Icons.assessment_rounded,
      color: const Color(0xFF3B82F6),
      title: 'Current Analysis',
      subtitle: 'Portfolio health score: ${finalScore.toStringAsFixed(0)}/100',
      impact: 'Now',
      impactPositive: true,
    ));

    return Scaffold(
      backgroundColor: context.appColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(context),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  Text(
                    'Your Decision Timeline',
                    style: TextStyle(
                      color: context.appColors.textPrimary,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Track how each decision impacted your portfolio health',
                    style: TextStyle(color: context.appColors.textMuted, fontSize: 13),
                  ),
                  const SizedBox(height: 24),

                  // Timeline
                  ...timeline.asMap().entries.map((entry) {
                    final idx = entry.key;
                    final item = entry.value;
                    final isLast = idx == timeline.length - 1;
                    return _buildTimelineItem(context, item, isLast);
                  }),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimelineItem(BuildContext context, _TimelineEntry item, bool isLast) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Timeline line + dot
          SizedBox(
            width: 40,
            child: Column(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: item.color.withValues(alpha: 0.15),
                    border: Border.all(
                      color: item.color.withValues(alpha: 0.4),
                    ),
                  ),
                  child: Icon(item.icon, color: item.color, size: 16),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 2,
                      color: context.appColors.border,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: context.appColors.cardBg,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: context.appColors.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          item.title,
                          style: TextStyle(
                            color: context.appColors.textPrimary,
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(6),
                          color: (item.impactPositive
                                  ? const Color(0xFF22C55E)
                                  : const Color(0xFFF97316))
                              .withValues(alpha: 0.12),
                        ),
                        child: Text(
                          item.impact,
                          style: TextStyle(
                            color: item.impactPositive
                                ? const Color(0xFF22C55E)
                                : const Color(0xFFF97316),
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    item.subtitle,
                    style: TextStyle(
                      color: context.appColors.textMuted,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 14),
      decoration: BoxDecoration(
        color: context.appColors.cardBg,
        border: Border(
          bottom: BorderSide(color: context.appColors.border, width: 0.5),
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
                color: context.appColors.border,
                border: Border.all(color: context.appColors.border),
              ),
              child: Icon(Icons.arrow_back_ios_new,
                  color: context.appColors.textPrimary, size: 16),
            ),
          ),
          const SizedBox(width: 14),
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              color: context.appColors.textMuted.withValues(alpha: 0.12),
            ),
            child: Icon(Icons.history_rounded,
                color: context.appColors.textMuted, size: 20),
          ),
          const SizedBox(width: 12),
          Text(
            'Decision History',
            style: TextStyle(
              color: context.appColors.textPrimary,
              fontSize: 17,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _TimelineEntry {
  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final String impact;
  final bool impactPositive;
  const _TimelineEntry({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.impact,
    required this.impactPositive,
  });
}
