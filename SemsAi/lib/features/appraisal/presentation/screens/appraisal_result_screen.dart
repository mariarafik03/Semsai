import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/theme/app_themes.dart';

class AppraisalResultScreen extends StatefulWidget {
  final Map<String, dynamic> result;
  final Map<String, dynamic> inputFeatures;

  const AppraisalResultScreen({
    super.key,
    required this.result,
    required this.inputFeatures,
  });

  @override
  State<AppraisalResultScreen> createState() => _AppraisalResultScreenState();
}

class _AppraisalResultScreenState extends State<AppraisalResultScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _entranceCtrl;

  // Offer comparison
  final List<Map<String, dynamic>> _offers = [];
  final _offerLabelCtrl = TextEditingController();
  final _offerPriceCtrl = TextEditingController();

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
    _offerLabelCtrl.dispose();
    _offerPriceCtrl.dispose();
    super.dispose();
  }

  double get _area => (widget.inputFeatures['area'] as num?)?.toDouble() ?? 1;
  double get _finalPrice => (widget.result['final_price'] as num?)?.toDouble() ?? 0;
  double get _mlPrice => (widget.result['model_price'] as num?)?.toDouble() ?? 0;
  double get _webPrice => (widget.result['avg_price'] as num?)?.toDouble() ?? 0;
  bool get _lowConfidence => widget.result['low_confidence'] == true;
  bool get _fallbackUsed => widget.result['fallback_used'] == true;
  List<dynamic> get _sources => widget.result['sources'] as List<dynamic>? ?? [];

  String get _blendLabel {
    if (_webPrice <= 0) return 'ML Only';
    if (_lowConfidence) return '40% Web / 60% ML';
    if (_fallbackUsed) return '60% Web / 40% ML';
    return '70% Web / 30% ML';
  }

  String _formatPrice(double price) {
    if (price >= 1e6) return '${(price / 1e6).toStringAsFixed(2)}M';
    if (price >= 1e3) return '${(price / 1e3).toStringAsFixed(0)}K';
    return price.toStringAsFixed(0);
  }

  String _formatNumber(double n) {
    final str = n.toStringAsFixed(0);
    final buf = StringBuffer();
    for (int i = 0; i < str.length; i++) {
      if (i > 0 && (str.length - i) % 3 == 0) buf.write(',');
      buf.write(str[i]);
    }
    return buf.toString();
  }

  void _addOffer() {
    final label = _offerLabelCtrl.text.trim();
    final price = double.tryParse(_offerPriceCtrl.text.trim());
    if (label.isEmpty || price == null || price <= 0) return;
    setState(() {
      _offers.add({'label': label, 'price': price});
      _offerLabelCtrl.clear();
      _offerPriceCtrl.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appColors.bg,
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
                    const SizedBox(height: 12),
                    _buildFinalPriceCard(),
                    const SizedBox(height: 16),
                    _buildComparisonCards(),
                    const SizedBox(height: 16),
                    _buildConfidenceBadge(),
                    const SizedBox(height: 16),
                    if (_sources.isNotEmpty) ...[
                      _buildSourcesSection(),
                      const SizedBox(height: 16),
                    ],
                    _buildOfferComparison(),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

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
              width: 36, height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: context.appColors.border,
              ),
              child: Icon(Icons.arrow_back_ios_new,
                  color: context.appColors.textPrimary, size: 16),
            ),
          ),
          const SizedBox(width: 14),
          Container(
            width: 40, height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(colors: [
                AppColors.gold, AppColors.gold.withValues(alpha: 0.6)
              ]),
            ),
            child: const Icon(Icons.assessment_rounded,
                color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Appraisal Report',
                    style: TextStyle(
                        color: context.appColors.textPrimary,
                        fontSize: 17, fontWeight: FontWeight.w600)),
                Text(
                    '${widget.inputFeatures['compound']} · ${_area.toStringAsFixed(0)} sqm',
                    style: TextStyle(
                        color: context.appColors.textMuted, fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ─── Final Price Hero Card ─────────────────────────────
  Widget _buildFinalPriceCard() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [
            AppColors.gold.withValues(alpha: 0.15),
            context.appColors.cardBg,
          ],
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.gold.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Text('ESTIMATED MARKET VALUE',
              style: TextStyle(
                  color: AppColors.gold, fontSize: 11,
                  fontWeight: FontWeight.w700, letterSpacing: 2)),
          const SizedBox(height: 12),
          Text('${_formatNumber(_finalPrice)} EGP',
              style: TextStyle(
                  color: context.appColors.textPrimary,
                  fontSize: 28, fontWeight: FontWeight.bold)),
          const SizedBox(height: 6),
          Text('${_formatNumber(_finalPrice / _area)} EGP/sqm',
              style: TextStyle(
                  color: context.appColors.textMuted, fontSize: 14)),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.gold.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text('Blend: $_blendLabel',
                style: TextStyle(
                    color: AppColors.gold, fontSize: 12,
                    fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }

  // ─── Side-by-Side Comparison ───────────────────────────
  Widget _buildComparisonCards() {
    return Row(
      children: [
        Expanded(child: _buildPriceCard(
          emoji: '🧠', title: 'ML Model',
          price: _mlPrice, ppm: _mlPrice / _area,
          color: const Color(0xFF3B82F6),
        )),
        const SizedBox(width: 12),
        Expanded(child: _buildPriceCard(
          emoji: '🌐', title: 'Nawy Market',
          price: _webPrice, ppm: _webPrice > 0 ? _webPrice / _area : 0,
          color: const Color(0xFF22C55E),
          noData: _webPrice <= 0,
        )),
      ],
    );
  }

  Widget _buildPriceCard({
    required String emoji, required String title,
    required double price, required double ppm,
    required Color color, bool noData = false,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.appColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: context.appColors.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(emoji, style: const TextStyle(fontSize: 18)),
          const SizedBox(width: 6),
          Text(title, style: TextStyle(
              color: context.appColors.textMuted, fontSize: 12,
              fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 10),
        Text(noData ? 'No data' : '${_formatPrice(price)} EGP',
            style: TextStyle(
                color: noData ? context.appColors.textMuted : context.appColors.textPrimary,
                fontSize: 18, fontWeight: FontWeight.bold)),
        if (!noData) ...[
          const SizedBox(height: 4),
          Text('${_formatNumber(ppm)} /sqm',
              style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w500)),
        ],
      ]),
    );
  }

  // ─── Confidence Badge ──────────────────────────────────
  Widget _buildConfidenceBadge() {
    final isHigh = !_lowConfidence && _webPrice > 0;
    final color = isHigh ? const Color(0xFF22C55E) : const Color(0xFFF97316);
    final label = isHigh ? 'HIGH CONFIDENCE' : 'LOW CONFIDENCE';
    final explanation = isHigh
        ? 'Multiple comparable listings found. Appraisal is reliable.'
        : _webPrice <= 0
            ? 'No web listings found. Using ML model prediction only.'
            : 'Few or inconsistent listings. ML model weight increased.';

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(label, style: TextStyle(
              color: color, fontSize: 11, fontWeight: FontWeight.w700)),
        ),
        const SizedBox(width: 12),
        Expanded(child: Text(explanation,
            style: TextStyle(color: context.appColors.textMuted, fontSize: 12))),
      ]),
    );
  }

  // ─── Sources ───────────────────────────────────────────
  Widget _buildSourcesSection() {
    final unique = _sources.toSet().toList();
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.appColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: context.appColors.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.link_rounded, color: AppColors.gold, size: 18),
          const SizedBox(width: 8),
          Text('Nawy Sources (${unique.length})',
              style: TextStyle(
                  color: context.appColors.textPrimary, fontSize: 14,
                  fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 12),
        ...unique.take(5).map((src) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: GestureDetector(
            onTap: () => _copyUrl(context, src.toString()),
            child: Text(
              _shortenUrl(src.toString()),
              style: TextStyle(
                  color: context.appColors.accent, fontSize: 12,
                  decoration: TextDecoration.underline),
              maxLines: 1, overflow: TextOverflow.ellipsis,
            ),
          ),
        )),
      ]),
    );
  }

  String _shortenUrl(String url) {
    return url.replaceAll('https://www.nawy.com', '').replaceAll('https://nawy.com', '');
  }

  void _copyUrl(BuildContext ctx, String url) {
    Clipboard.setData(ClipboardData(text: url));
    ScaffoldMessenger.of(ctx).showSnackBar(
      SnackBar(content: Text('Link copied!'), duration: const Duration(seconds: 1)),
    );
  }

  // ─── Offer Comparison ─────────────────────────────────
  Widget _buildOfferComparison() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: context.appColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: context.appColors.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.compare_arrows_rounded, color: AppColors.gold, size: 18),
          const SizedBox(width: 8),
          Text('Compare with Offers',
              style: TextStyle(
                  color: context.appColors.textPrimary, fontSize: 14,
                  fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 14),

        // Add offer form
        Row(children: [
          Expanded(
            flex: 3,
            child: TextField(
              controller: _offerLabelCtrl,
              style: TextStyle(color: context.appColors.textPrimary, fontSize: 13),
              decoration: _offerInputDeco('Offer label'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 2,
            child: TextField(
              controller: _offerPriceCtrl,
              keyboardType: TextInputType.number,
              style: TextStyle(color: context.appColors.textPrimary, fontSize: 13),
              decoration: _offerInputDeco('Price (EGP)'),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _offers.length < 10 ? _addOffer : null,
            child: Container(
              width: 36, height: 36,
              decoration: BoxDecoration(
                color: AppColors.gold,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(Icons.add, color: context.appColors.bg, size: 18),
            ),
          ),
        ]),

        if (_offers.isNotEmpty) ...[
          const SizedBox(height: 16),
          ..._offers.asMap().entries.map((e) => _buildOfferRow(e.key, e.value)),
          const SizedBox(height: 12),
          _buildBestOfferSummary(),
        ],
      ]),
    );
  }

  InputDecoration _offerInputDeco(String hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: TextStyle(color: context.appColors.textMuted, fontSize: 12),
      filled: true, fillColor: context.appColors.bg,
      contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: context.appColors.border)),
      enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: context.appColors.border)),
    );
  }

  Widget _buildOfferRow(int idx, Map<String, dynamic> offer) {
    final price = (offer['price'] as num).toDouble();
    final ppm = price / _area;
    final diff = price - _finalPrice;
    final pct = _finalPrice > 0 ? (diff / _finalPrice * 100) : 0.0;

    String verdict;
    Color vColor;
    String emoji;
    if (pct < -10) {
      verdict = 'Good Deal'; vColor = const Color(0xFF22C55E); emoji = '🟢';
    } else if (pct <= 10) {
      verdict = 'Fair Price'; vColor = const Color(0xFFF59E0B); emoji = '🟡';
    } else {
      verdict = 'Overpriced'; vColor = const Color(0xFFEF4444); emoji = '🔴';
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: context.appColors.bg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: context.appColors.border),
      ),
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Text(offer['label'], style: TextStyle(
                  color: context.appColors.textPrimary, fontSize: 13,
                  fontWeight: FontWeight.w600)),
              const Spacer(),
              GestureDetector(
                onTap: () => setState(() => _offers.removeAt(idx)),
                child: Icon(Icons.close, color: context.appColors.textMuted, size: 16),
              ),
            ]),
            const SizedBox(height: 6),
            Row(children: [
              Text('${_formatNumber(price)} EGP', style: TextStyle(
                  color: context.appColors.textPrimary, fontSize: 14,
                  fontWeight: FontWeight.bold)),
              const SizedBox(width: 8),
              Text('${_formatNumber(ppm)} /sqm', style: TextStyle(
                  color: context.appColors.textMuted, fontSize: 11)),
            ]),
            const SizedBox(height: 6),
            Row(children: [
              Text('$emoji $verdict', style: TextStyle(
                  color: vColor, fontSize: 12, fontWeight: FontWeight.w600)),
              const SizedBox(width: 8),
              Text('${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}% vs appraisal',
                  style: TextStyle(color: context.appColors.textMuted, fontSize: 11)),
            ]),
          ]),
        ),
      ]),
    );
  }

  Widget _buildBestOfferSummary() {
    if (_offers.isEmpty) return const SizedBox.shrink();
    final best = _offers.reduce((a, b) =>
        (a['price'] as num) < (b['price'] as num) ? a : b);
    final price = (best['price'] as num).toDouble();
    final pct = _finalPrice > 0 ? ((price - _finalPrice) / _finalPrice * 100) : 0.0;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.gold.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.gold.withValues(alpha: 0.2)),
      ),
      child: Row(children: [
        const Text('🏆', style: TextStyle(fontSize: 18)),
        const SizedBox(width: 10),
        Expanded(child: Text(
          'Best offer: "${best['label']}" at ${_formatNumber(price)} EGP '
          '(${pct.abs().toStringAsFixed(1)}% ${pct < 0 ? 'below' : 'above'} market)',
          style: TextStyle(color: AppColors.gold, fontSize: 12, fontWeight: FontWeight.w500),
        )),
      ]),
    );
  }
}
