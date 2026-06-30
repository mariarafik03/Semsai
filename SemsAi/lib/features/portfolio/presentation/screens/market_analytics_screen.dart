import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/networking/api_client.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class MarketAnalyticsScreen extends StatefulWidget {
  const MarketAnalyticsScreen({super.key});

  @override
  State<MarketAnalyticsScreen> createState() => _MarketAnalyticsScreenState();
}

class _MarketAnalyticsScreenState extends State<MarketAnalyticsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabCtrl;
  bool _loading = true;
  String? _error;

  // Data
  List<dynamic> _areas = [];
  List<dynamic> _developers = [];
  List<dynamic> _propertyTypes = [];
  Map<String, dynamic> _summary = {};

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
    _fetchData();
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  Future<void> _fetchData() async {
    try {
      final response = await ApiClient.get('/api/market-analytics');
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body);
        if (json['success'] == true) {
          setState(() {
            _areas = json['data']['areas'] ?? [];
            _developers = json['data']['developers'] ?? [];
            _propertyTypes = json['data']['property_types'] ?? [];
            _summary = json['data']['summary'] ?? {};
            _loading = false;
          });
          return;
        }
      }
      setState(() {
        _error = 'Failed to load data';
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Connection error: $e';
        _loading = false;
      });
    }
  }

  String _formatNumber(num value) {
    if (value >= 1000000) return '${(value / 1000000).toStringAsFixed(1)}M';
    if (value >= 1000) return '${(value / 1000).toStringAsFixed(0)}K';
    return value.round().toString();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            if (_loading)
              const Expanded(
                child: Center(
                  child: CircularProgressIndicator(color: Color(0xFFD4A44A)),
                ),
              )
            else if (_error != null)
              Expanded(
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.error_outline,
                          color: Color(0xFFEF4444), size: 48),
                      const SizedBox(height: 12),
                      Text(_error!,
                          style: TextStyle(color: context.appColors.textMuted)),
                      const SizedBox(height: 16),
                      TextButton(
                        onPressed: () {
                          setState(() {
                            _loading = true;
                            _error = null;
                          });
                          _fetchData();
                        },
                        child: const Text('Retry',
                            style: TextStyle(color: Color(0xFFD4A44A))),
                      ),
                    ],
                  ),
                ),
              )
            else
              Expanded(
                child: Column(
                  children: [
                    _buildSummaryRow(),
                    _buildTabBar(),
                    Expanded(
                      child: TabBarView(
                        controller: _tabCtrl,
                        children: [
                          _buildAreasTab(),
                          _buildDevelopersTab(),
                          _buildTypesTab(),
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

  // ─── Header ───────────────────────────────────────────
  Widget _buildHeader() {
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
              gradient: LinearGradient(
                colors: [
                  AppColors.gold.withValues(alpha: 0.2),
                  AppColors.gold.withValues(alpha: 0.05),
                ],
              ),
            ),
            child: Icon(Icons.analytics_rounded,
                color: AppColors.gold, size: 20),
          ),
          const SizedBox(width: 12),
          Text(
            'Market Analytics',
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

  // ─── Summary Row ──────────────────────────────────────
  Widget _buildSummaryRow() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          _buildSummaryChip(
            icon: Icons.home_rounded,
            label: 'Units',
            value: _formatNumber(_summary['total_units'] ?? 0),
            color: AppColors.gold,
          ),
          const SizedBox(width: 8),
          _buildSummaryChip(
            icon: Icons.location_on_rounded,
            label: 'Areas',
            value: '${_summary['total_areas'] ?? 0}',
            color: const Color(0xFF3B82F6),
          ),
          const SizedBox(width: 8),
          _buildSummaryChip(
            icon: Icons.business_rounded,
            label: 'Developers',
            value: '${_summary['total_developers'] ?? 0}',
            color: const Color(0xFF22C55E),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryChip({
    required IconData icon,
    required String label,
    required String value,
    required Color color,
  }) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 10),
        decoration: BoxDecoration(
          color: context.appColors.cardBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(height: 6),
            Text(
              value,
              style: TextStyle(
                color: color,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(
                    color: context.appColors.textMuted, fontSize: 11)),
          ],
        ),
      ),
    );
  }

  // ─── Tab Bar ──────────────────────────────────────────
  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: context.appColors.cardBg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: TabBar(
        controller: _tabCtrl,
        indicator: BoxDecoration(
          color: AppColors.gold.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.gold.withValues(alpha: 0.3)),
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        labelColor: AppColors.gold,
        unselectedLabelColor: context.appColors.textMuted,
        labelStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        dividerColor: Colors.transparent,
        tabs: const [
          Tab(text: '📍 Areas'),
          Tab(text: '🏗️ Developers'),
          Tab(text: '🏠 Types'),
        ],
      ),
    );
  }

  // ─── Areas Tab ────────────────────────────────────────
  Widget _buildAreasTab() {
    if (_areas.isEmpty) {
      return Center(
        child: Text('No area data available',
            style: TextStyle(color: context.appColors.textMuted)),
      );
    }

    final maxPrice = _areas.isNotEmpty
        ? (_areas[0]['avg_price_per_sqm'] as num).toDouble()
        : 1.0;

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _areas.length + 1,
      itemBuilder: (ctx, i) {
        if (i == 0) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Price per m² by Area',
                  style: TextStyle(
                    color: context.appColors.textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Average ${_formatNumber(_summary['overall_avg_price_per_sqm'] ?? 0)} EGP/m² across all areas',
                  style: TextStyle(
                      color: context.appColors.textMuted, fontSize: 12),
                ),
              ],
            ),
          );
        }

        final area = _areas[i - 1];
        final avgPsqm = (area['avg_price_per_sqm'] as num).toDouble();
        final fraction = (avgPsqm / maxPrice).clamp(0.0, 1.0);
        final rank = i;
        final isTop3 = rank <= 3;

        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: context.appColors.cardBg,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isTop3
                  ? AppColors.gold.withValues(alpha: 0.2)
                  : context.appColors.border,
            ),
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
                      shape: BoxShape.circle,
                      color: isTop3
                          ? AppColors.gold.withValues(alpha: 0.15)
                          : context.appColors.border,
                    ),
                    child: Center(
                      child: Text(
                        '#$rank',
                        style: TextStyle(
                          color: isTop3
                              ? AppColors.gold
                              : context.appColors.textMuted,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      area['location'] ?? 'Unknown',
                      style: TextStyle(
                        color: context.appColors.textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  Text(
                    '${_formatNumber(avgPsqm)} EGP/m²',
                    style: TextStyle(
                      color: isTop3 ? AppColors.gold : context.appColors.textMuted,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              // Progress bar
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: Stack(
                  children: [
                    Container(
                      height: 6,
                      decoration: BoxDecoration(
                        color: context.appColors.border,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    FractionallySizedBox(
                      widthFactor: fraction,
                      child: Container(
                        height: 6,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(4),
                          gradient: LinearGradient(
                            colors: isTop3
                                ? [
                                    AppColors.gold.withValues(alpha: 0.6),
                                    AppColors.gold
                                  ]
                                : [
                                    const Color(0xFF3B82F6)
                                        .withValues(alpha: 0.5),
                                    const Color(0xFF3B82F6)
                                  ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  _buildTag('${area['unit_count']} units',
                      context.appColors.textMuted),
                  const SizedBox(width: 8),
                  _buildTag('${area['compound_count']} compounds',
                      context.appColors.textMuted),
                  const Spacer(),
                  Text(
                    'Avg ${_formatNumber((area['avg_price'] as num).toDouble())} EGP',
                    style: TextStyle(
                        color: context.appColors.border, fontSize: 11),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  // ─── Developers Tab ───────────────────────────────────
  Widget _buildDevelopersTab() {
    if (_developers.isEmpty) {
      return Center(
        child: Text('No developer data available',
            style: TextStyle(color: context.appColors.textMuted)),
      );
    }

    final maxPrice = _developers.isNotEmpty
        ? (_developers[0]['avg_price_per_sqm'] as num).toDouble()
        : 1.0;

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _developers.length + 1,
      itemBuilder: (ctx, i) {
        if (i == 0) {
          return Padding(
            padding: EdgeInsets.only(bottom: 16),
            child: Text(
              'Developer Price Ranking',
              style: TextStyle(
                color: context.appColors.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          );
        }

        final dev = _developers[i - 1];
        final avgPsqm = (dev['avg_price_per_sqm'] as num).toDouble();
        final fraction = (avgPsqm / maxPrice).clamp(0.0, 1.0);
        final devClass = dev['developer_class'] ?? 'Unknown';
        final classColor = _getClassColor(devClass);

        return Container(
          margin: const EdgeInsets.only(bottom: 10),
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
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(8),
                      color: classColor.withValues(alpha: 0.12),
                    ),
                    child: Center(
                      child: Text(
                        (dev['name'] ?? 'D')[0].toUpperCase(),
                        style: TextStyle(
                          color: classColor,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          dev['name'] ?? 'Unknown',
                          style: TextStyle(
                            color: context.appColors.textPrimary,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Row(
                          children: [
                            if (devClass.isNotEmpty)
                              _buildTag('Class $devClass', classColor),
                            if (devClass.isNotEmpty) const SizedBox(width: 6),
                            if ((dev['rating'] as num?) != null &&
                                (dev['rating'] as num) > 0)
                              Row(
                                children: [
                                  const Icon(Icons.star_rounded,
                                      color: Color(0xFFFBBF24), size: 12),
                                  const SizedBox(width: 2),
                                  Text(
                                    (dev['rating'] as num)
                                        .toStringAsFixed(1),
                                    style: const TextStyle(
                                        color: Color(0xFFFBBF24),
                                        fontSize: 11),
                                  ),
                                ],
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '${_formatNumber(avgPsqm)}',
                        style: TextStyle(
                          color: AppColors.gold,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text('EGP/m²',
                          style: TextStyle(
                              color: context.appColors.textMuted, fontSize: 10)),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 10),
              // Bar
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: Stack(
                  children: [
                    Container(height: 5, color: context.appColors.border),
                    FractionallySizedBox(
                      widthFactor: fraction,
                      child: Container(
                        height: 5,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(4),
                          color: classColor.withValues(alpha: 0.7),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  _buildTag('${dev['unit_count']} units',
                      context.appColors.textMuted),
                  const SizedBox(width: 6),
                  _buildTag('${dev['compound_count']} compounds',
                      context.appColors.textMuted),
                  const Spacer(),
                  if ((dev['locations'] as List?)?.isNotEmpty == true)
                    Text(
                      (dev['locations'] as List).take(2).join(', '),
                      style: TextStyle(
                          color: context.appColors.border, fontSize: 10),
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  // ─── Types Tab ────────────────────────────────────────
  Widget _buildTypesTab() {
    if (_propertyTypes.isEmpty) {
      return Center(
        child: Text('No type data available',
            style: TextStyle(color: context.appColors.textMuted)),
      );
    }

    final totalCount =
        _propertyTypes.fold<int>(0, (s, t) => s + ((t['count'] as num?) ?? 0).toInt());

    final colors = [
      AppColors.gold,
      const Color(0xFF3B82F6),
      const Color(0xFF22C55E),
      const Color(0xFFF97316),
      const Color(0xFFEF4444),
      const Color(0xFF8B5CF6),
      const Color(0xFF06B6D4),
      const Color(0xFFEC4899),
    ];

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _propertyTypes.length + 1,
      itemBuilder: (ctx, i) {
        if (i == 0) {
          return Padding(
            padding: EdgeInsets.only(bottom: 16),
            child: Text(
              'Property Type Distribution',
              style: TextStyle(
                color: context.appColors.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          );
        }

        final type = _propertyTypes[i - 1];
        final count = (type['count'] as num?) ?? 0;
        final pct = totalCount > 0 ? (count / totalCount * 100) : 0.0;
        final color = colors[(i - 1) % colors.length];

        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: context.appColors.cardBg,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: context.appColors.border),
          ),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  color: color.withValues(alpha: 0.12),
                ),
                child: Center(
                  child: Text(
                    '${pct.toStringAsFixed(0)}%',
                    style: TextStyle(
                      color: color,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _resolveTypeName(type['type']),
                      style: TextStyle(
                        color: context.appColors.textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Text(
                          '$count units',
                          style: TextStyle(
                              color: context.appColors.textMuted, fontSize: 11),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          'Avg ${_formatNumber((type['avg_area'] as num?)?.toDouble() ?? 0)} m²',
                          style: TextStyle(
                              color: context.appColors.textMuted, fontSize: 11),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    _formatNumber(
                        (type['avg_price_per_sqm'] as num?)?.toDouble() ?? 0),
                    style: TextStyle(
                      color: color,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text('EGP/m²',
                      style:
                          TextStyle(color: context.appColors.textMuted, fontSize: 10)),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  // ─── Helpers ──────────────────────────────────────────
  Widget _buildTag(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(4),
        color: color.withValues(alpha: 0.1),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w500),
      ),
    );
  }

  String _resolveTypeName(dynamic value) {
    if (value == null) return 'Other';
    if (value is String) return value;
    if (value is Map) return (value['name'] ?? 'Other').toString();
    return value.toString();
  }

  Color _getClassColor(String devClass) {
    switch (devClass.toLowerCase()) {
      case 'a':
        return AppColors.gold;
      case 'b':
        return const Color(0xFF3B82F6);
      case 'c':
        return const Color(0xFF22C55E);
      default:
        return context.appColors.textMuted;
    }
  }
}
