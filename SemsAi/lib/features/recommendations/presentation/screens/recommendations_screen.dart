import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/features/recommendations/presentation/screens/widgets/recommendation_card.dart';

class RecommendationsScreen extends StatefulWidget {
  final Map<String, dynamic> results;
  final String sessionId;

  const RecommendationsScreen({
    super.key,
    required this.results,
    required this.sessionId,
  });

  @override
  State<RecommendationsScreen> createState() => _RecommendationsScreenState();
}

class _RecommendationsScreenState extends State<RecommendationsScreen>
    with TickerProviderStateMixin {
  late final AnimationController _entranceCtrl;

  @override
  void initState() {
    super.initState();
    _entranceCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..forward();
  }

  @override
  void dispose() {
    _entranceCtrl.dispose();
    super.dispose();
  }

  // Compute compound list from top_compounds (new) or best_compound (old)
  List<Map<String, dynamic>> get _topCompounds {
    // New format: top_compounds with units per compound
    final topList = widget.results['top_compounds'] as List<dynamic>?;
    if (topList != null && topList.isNotEmpty) {
      return topList.map((item) {
        final c = Map<String, dynamic>.from(item as Map);
        return {
          'compound_name': c['compound_name'] ?? 'Unknown',
          'compound_id': c['compound_id'] ?? '',
          'location': c['location'] ?? widget.results['location'] ?? '',
          'score': c['score'] ?? 0.0,
          'reasons': c['reasons'] ?? [],
          'min_unit_price': c['min_unit_price'],
          'units': c['units'] ?? [],
        };
      }).toList();
    }

    // Fallback: old single best_compound format
    final bestCompound =
        widget.results['best_compound'] as Map<String, dynamic>?;
    if (bestCompound == null ||
        bestCompound.isEmpty ||
        bestCompound['status'] == 'no_compound_found') {
      return [];
    }

    return [
      {
        'compound_name': bestCompound['compound_name'] ?? 'Unknown',
        'location':
            bestCompound['location'] ?? widget.results['location'] ?? '',
        'score': bestCompound['score'],
        'reasons': bestCompound['reasons'] ?? [],
        'min_unit_price': bestCompound['min_unit_price'],
        'units': widget.results['top_units'] ?? [],
      },
    ];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: _topCompounds.isEmpty
                  ? _buildEmpty()
                  : _buildResultsList(),
            ),
            _buildBottomBar(),
          ],
        ),
      ),
    );
  }

  // ─── Header ─────────────────────────────────

  Widget _buildHeader() {
    return FadeTransition(
      opacity: _entranceCtrl,
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          border: const Border(
            bottom: BorderSide(color: AppColors.border, width: 0.5),
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
                  color: AppColors.bg,
                  border: Border.all(color: AppColors.border),
                ),
                child: const Icon(
                  Icons.arrow_back_ios_new,
                  color: AppColors.textPrimary,
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
              child: const Icon(
                Icons.auto_awesome,
                color: Colors.white,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'AI Recommendations',
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 17,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    'Top ${_topCompounds.length} matches for you',
                    style: TextStyle(
                      color: AppColors.gold.withValues(alpha: 0.8),
                      fontSize: 12,
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

  Widget _buildResultsList() {
    final compounds = _topCompounds;
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      itemCount: compounds.length,
      itemBuilder: (context, index) {
        final item = compounds[index];
        final delay = index * 0.15;
        return RecommendationCard(
          data: {
            'name': item['compound_name'] ?? 'Unknown',
            'location': item['location'] ?? '',
            'confidence': (item['score'] as num?) ?? 0.0,
            'reasons': item['reasons'] ?? [],
            'min_unit_price': item['min_unit_price'],
            'units': item['units'] ?? [],
          },
          rank: index + 1,
          entranceDelay: delay,
          parentCtrl: _entranceCtrl,
        );
      },
    );
  }

  // ─── Empty ──────────────────────────────────

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.search_off_rounded,
            color: AppColors.textMuted.withValues(alpha: 0.4),
            size: 64,
          ),
          const SizedBox(height: 16),
          const Text(
            AppStrings.noRecommendations,
            style: TextStyle(color: AppColors.textMuted, fontSize: 15),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  // ─── Bottom Bar ─────────────────────────────

  Widget _buildBottomBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        border: const Border(
          top: BorderSide(color: AppColors.border, width: 0.5),
        ),
      ),
      child: SizedBox(
        width: double.infinity,
        height: 48,
        child: ElevatedButton(
          onPressed: () => Navigator.pop(context),
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.gold.withValues(alpha: 0.15),
            foregroundColor: AppColors.gold,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: AppColors.gold.withValues(alpha: 0.3)),
            ),
            elevation: 0,
          ),
          child: const Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.refresh_rounded, size: 18),
              SizedBox(width: 8),
              Text(
                'Start New Search',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
