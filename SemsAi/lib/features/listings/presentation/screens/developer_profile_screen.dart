import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/utils/price_formatter.dart';
import 'package:SemsAi/core/widgets/app_loading_indicator.dart';
import 'package:SemsAi/core/widgets/app_error_widget.dart';
import 'package:SemsAi/features/listings/data/models/developer_model.dart';
import 'package:SemsAi/features/listings/data/repo/developer_service.dart';

class DeveloperProfileScreen extends StatefulWidget {
  final String developerName;

  const DeveloperProfileScreen({super.key, required this.developerName});

  @override
  State<DeveloperProfileScreen> createState() => _DeveloperProfileScreenState();
}

class _DeveloperProfileScreenState extends State<DeveloperProfileScreen>
    with SingleTickerProviderStateMixin {
  Developer? _developer;
  bool _loading = true;
  String? _error;
  late final AnimationController _animCtrl;
  late final Animation<double> _fadeAnim;

  @override
  void initState() {
    super.initState();
    _animCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );
    _fadeAnim = CurvedAnimation(parent: _animCtrl, curve: Curves.easeOut);
    _loadDeveloper();
  }

  @override
  void dispose() {
    _animCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadDeveloper() async {
    try {
      final dev = await DeveloperService.getDeveloperByName(
        widget.developerName,
      );
      if (mounted) {
        setState(() {
          _developer = dev;
          _loading = false;
        });
        _animCtrl.forward();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'Could not load developer info';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: _loading
          ? const AppLoadingCenter()
          : _error != null
          ? AppErrorWidget(
              message: _error!,
              onRetry: () {
                setState(() {
                  _loading = true;
                  _error = null;
                });
                _loadDeveloper();
              },
            )
          : FadeTransition(opacity: _fadeAnim, child: _buildContent()),
    );
  }

  Widget _buildContent() {
    final dev = _developer!;
    return CustomScrollView(
      physics: const BouncingScrollPhysics(),
      slivers: [
        _buildAppBar(dev),
        SliverToBoxAdapter(child: _buildHeader(dev)),
        SliverToBoxAdapter(child: _buildStatsGrid(dev)),
        if (dev.areas.isNotEmpty)
          SliverToBoxAdapter(child: _buildAreasSection(dev)),
        if (dev.compoundNames.isNotEmpty)
          SliverToBoxAdapter(child: _buildCompoundsSection(dev)),
        if (dev.description != null && dev.description!.trim().isNotEmpty)
          SliverToBoxAdapter(child: _buildAboutSection(dev)),
        if (_hasReviews(dev))
          SliverToBoxAdapter(child: _buildReviewsSection(dev)),
        const SliverToBoxAdapter(child: SizedBox(height: 60)),
      ],
    );
  }

  // ─── APP BAR ──────────────────────────────────────────────────

  Widget _buildAppBar(Developer dev) {
    return SliverAppBar(
      pinned: true,
      expandedHeight: 0,
      backgroundColor: AppColors.bg.withValues(alpha: 0.95),
      surfaceTintColor: Colors.transparent,
      leading: GestureDetector(
        onTap: () => Navigator.of(context).pop(),
        child: Container(
          margin: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppColors.cardBg,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.border),
          ),
          child: const Icon(
            Icons.arrow_back_ios_new_rounded,
            color: AppColors.textPrimary,
            size: 18,
          ),
        ),
      ),
      title: const Text(
        'Developer Profile',
        style: TextStyle(
          color: AppColors.textPrimary,
          fontSize: 17,
          fontWeight: FontWeight.w700,
        ),
      ),
      centerTitle: true,
    );
  }

  // ─── HEADER ───────────────────────────────────────────────────

  Widget _buildHeader(Developer dev) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Column(
        children: [
          // Logo / Avatar
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppColors.gold, AppColors.goldLight],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: AppColors.gold.withValues(alpha: 0.3),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: dev.logoUrl != null && dev.logoUrl!.isNotEmpty
                ? ClipRRect(
                    borderRadius: BorderRadius.circular(20),
                    child: Image.network(
                      dev.logoUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _logoFallback(dev),
                    ),
                  )
                : _logoFallback(dev),
          ),
          const SizedBox(height: 14),
          // Name
          Text(
            dev.devName,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 22,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          // Class badge + rating
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (dev.developerClass != null &&
                  dev.developerClass!.isNotEmpty) ...[
                _classBadge(dev.developerClass!),
                const SizedBox(width: 10),
              ],
              if (dev.rating > 0) ...[
                Icon(Icons.star_rounded, color: AppColors.gold, size: 18),
                const SizedBox(width: 3),
                Text(
                  dev.rating.toStringAsFixed(1),
                  style: const TextStyle(
                    color: AppColors.gold,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 6),
          // Price range
          if (dev.priceMin != null) ...[
            Text(
              'Starting from ${PriceFormatter.format(dev.priceMin)}',
              style: TextStyle(
                color: AppColors.textMuted.withValues(alpha: 0.8),
                fontSize: 13,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _logoFallback(Developer dev) {
    return Center(
      child: Text(
        dev.devName.isNotEmpty ? dev.devName[0].toUpperCase() : 'D',
        style: const TextStyle(
          color: AppColors.bg,
          fontSize: 32,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }

  Widget _classBadge(String cls) {
    Color badgeColor;
    switch (cls.toUpperCase()) {
      case 'A':
        badgeColor = const Color(0xFF4CAF50);
        break;
      case 'B':
        badgeColor = AppColors.accent;
        break;
      case 'C':
        badgeColor = AppColors.gold;
        break;
      default:
        badgeColor = AppColors.textMuted;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: badgeColor.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: badgeColor.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.verified_rounded, color: badgeColor, size: 14),
          const SizedBox(width: 4),
          Text(
            'Class $cls',
            style: TextStyle(
              color: badgeColor,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  // ─── FOUNDED YEAR EXTRACTION ───────────────────────────────────

  int? _getFoundedYear(Developer dev) {
    if (dev.yearsActive != null && dev.yearsActive! > 0) {
      return DateTime.now().year - dev.yearsActive!;
    }
    return _extractFoundedYear(dev.description);
  }

  static int? _extractFoundedYear(String? description) {
    if (description == null || description.isEmpty) return null;
    final text = description.toLowerCase();
    final currentYear = DateTime.now().year;
    final patterns = [
      RegExp(
        r'(?:founded|established|launched|started|began|incorporated|created)\s+(?:(?:its\s+)?\w+\s+)*?in\s+(\d{4})',
      ),
      RegExp(
        r'(?:founded|established|launched|started|began|incorporated|created)\s+in\s+(\d{4})',
      ),
      RegExp(r'(?:since|from)\s+(\d{4})'),
      RegExp(
        r'in\s+(\d{4})\s*,?\s*[\w\s]{1,60}(?:launched|started|began|founded|established|entered)',
      ),
    ];
    int? earliestYear;
    for (final pattern in patterns) {
      for (final match in pattern.allMatches(text)) {
        final yearStr = match.group(1);
        if (yearStr != null) {
          final year = int.tryParse(yearStr);
          if (year != null && year >= 1950 && year <= currentYear) {
            if (earliestYear == null || year < earliestYear) {
              earliestYear = year;
            }
          }
        }
      }
    }
    return earliestYear;
  }

  // ─── STATS GRID ───────────────────────────────────────────────

  Widget _buildStatsGrid(Developer dev) {
    final foundedYear = _getFoundedYear(dev);
    final yearsActive = foundedYear != null
        ? DateTime.now().year - foundedYear
        : null;

    final stats = <_StatItem>[
      if (foundedYear != null && yearsActive != null && yearsActive > 0)
        _StatItem(
          Icons.calendar_today_rounded,
          'Est. $foundedYear',
          '$yearsActive Years',
        ),
      if (dev.totalProjects > 0)
        _StatItem(
          Icons.apartment_rounded,
          '${dev.totalProjects}',
          'Total Projects',
        ),
      if (dev.compoundsCount != null && dev.compoundsCount! > 0)
        _StatItem(
          Icons.location_city_rounded,
          '${dev.compoundsCount}',
          'Compounds',
        ),
      if (dev.areas.isNotEmpty)
        _StatItem(Icons.map_outlined, '${dev.areas.length}', 'Areas'),
    ];

    if (stats.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.border.withValues(alpha: 0.6)),
        ),
        child: Row(
          children: stats.map((s) {
            return Expanded(
              child: Column(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.gold.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(s.icon, color: AppColors.gold, size: 20),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    s.value,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    s.label,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: AppColors.textMuted.withValues(alpha: 0.8),
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  // ─── AREAS ────────────────────────────────────────────────────

  Widget _buildAreasSection(Developer dev) {
    return _section(
      'Operating Areas',
      Icons.location_on_outlined,
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: dev.areas.map((area) {
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.accent.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: AppColors.accent.withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.place_outlined, color: AppColors.accent, size: 14),
                const SizedBox(width: 5),
                Text(
                  area,
                  style: const TextStyle(
                    color: AppColors.accent,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  // ─── COMPOUNDS ────────────────────────────────────────────────

  Widget _buildCompoundsSection(Developer dev) {
    return _section(
      'Compounds',
      Icons.location_city_outlined,
      child: Column(
        children: List.generate(dev.compoundNames.length, (i) {
          final name = dev.compoundNames[i];
          final isLast = i == dev.compoundNames.length - 1;
          return Column(
            children: [
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Row(
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: AppColors.gold.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Center(
                        child: Text(
                          '${i + 1}',
                          style: const TextStyle(
                            color: AppColors.gold,
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        name,
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    Icon(
                      Icons.chevron_right_rounded,
                      color: AppColors.textMuted.withValues(alpha: 0.5),
                      size: 20,
                    ),
                  ],
                ),
              ),
              if (!isLast)
                Divider(
                  height: 1,
                  color: AppColors.border.withValues(alpha: 0.5),
                ),
            ],
          );
        }),
      ),
    );
  }

  // ─── ABOUT ────────────────────────────────────────────────────

  Widget _buildAboutSection(Developer dev) {
    return _section(
      'About',
      Icons.info_outline_rounded,
      child: Text(
        dev.description!,
        style: const TextStyle(
          color: AppColors.textMuted,
          fontSize: 13,
          height: 1.7,
        ),
      ),
    );
  }

  // ─── REVIEWS ──────────────────────────────────────────────────

  bool _hasReviews(Developer dev) =>
      dev.googleReviewsScore > 0 || dev.facebookReviewsScore > 0;

  Widget _buildReviewsSection(Developer dev) {
    return _section(
      'Reviews',
      Icons.rate_review_outlined,
      child: Row(
        children: [
          if (dev.googleReviewsScore > 0)
            Expanded(
              child: _reviewCard(
                'Google',
                dev.googleReviewsScore,
                const Color(0xFF4285F4),
              ),
            ),
          if (dev.googleReviewsScore > 0 && dev.facebookReviewsScore > 0)
            const SizedBox(width: 12),
          if (dev.facebookReviewsScore > 0)
            Expanded(
              child: _reviewCard(
                'Facebook',
                dev.facebookReviewsScore,
                const Color(0xFF1877F2),
              ),
            ),
        ],
      ),
    );
  }

  Widget _reviewCard(String platform, double score, Color color) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Text(
            score.toStringAsFixed(1),
            style: TextStyle(
              color: color,
              fontSize: 24,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 2),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(5, (i) {
              return Icon(
                i < score.round()
                    ? Icons.star_rounded
                    : Icons.star_outline_rounded,
                color: color.withValues(alpha: i < score.round() ? 1 : 0.4),
                size: 14,
              );
            }),
          ),
          const SizedBox(height: 4),
          Text(
            platform,
            style: TextStyle(
              color: color.withValues(alpha: 0.8),
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  // ─── SECTION WRAPPER ──────────────────────────────────────────

  Widget _section(String title, IconData icon, {required Widget child}) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.border.withValues(alpha: 0.6)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: AppColors.gold.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon, color: AppColors.gold, size: 16),
                ),
                const SizedBox(width: 10),
                Text(
                  title,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            child,
          ],
        ),
      ),
    );
  }
}

class _StatItem {
  final IconData icon;
  final String value;
  final String label;
  const _StatItem(this.icon, this.value, this.label);
}
