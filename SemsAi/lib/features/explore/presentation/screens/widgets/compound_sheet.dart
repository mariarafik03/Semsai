import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/features/explore/data/models/compound_model.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/explore/data/repo/explore_service.dart';
import 'package:SemsAi/features/explore/presentation/screens/unit_detail_screen.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


/// Modal bottom sheet showing compound details + units list.
class CompoundSheet extends StatefulWidget {
  final Compound compound;

  const CompoundSheet({super.key, required this.compound});

  @override
  State<CompoundSheet> createState() => _CompoundSheetState();
}

class _CompoundSheetState extends State<CompoundSheet> {
  static const _gold = AppColors.gold;
  static const _accent = AppColors.accent;
  Color get _cardBg => context.appColors.cardBg;
  Color get _border => context.appColors.border;
  Color get _textMuted => context.appColors.textMuted;

  List<CompoundUnit>? _units;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadUnits();
  }

  Future<void> _loadUnits() async {
    try {
      final units = await ExploreService.getCompoundUnits(widget.compound.id);
      if (mounted) {
        setState(() {
          _units = units;
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.compound;
    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.55,
      ),
      decoration: BoxDecoration(
        color: _cardBg,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        border: Border.all(color: _border),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: EdgeInsets.only(top: 12),
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: _gold.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          // Header
          Padding(
            padding: EdgeInsets.fromLTRB(20, 14, 12, 0),
            child: Row(
              children: [
                ShaderMask(
                  shaderCallback: (b) =>
                      LinearGradient(colors: [_gold, _accent]).createShader(b),
                  child: Icon(
                    Icons.location_on_rounded,
                    color: Colors.white,
                    size: 24,
                  ),
                ),
                SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        c.name,
                        style: const TextStyle(
                          color: _gold,
                          fontWeight: FontWeight.w700,
                          fontSize: 16,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (c.location != null || c.developerName != null)
                        Text(
                          [
                            c.location,
                            c.developerName,
                          ].where((s) => s != null && s.isNotEmpty).join(' · '),
                          style: TextStyle(
                            color: _textMuted,
                            fontSize: 12,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                    ],
                  ),
                ),
                IconButton(
                  icon: Icon(
                    Icons.close_rounded,
                    color: _textMuted,
                    size: 22,
                  ),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),

          // Info
          if (c.startPrice != null || c.unitCount != null)
            Padding(
              padding: EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Row(
                children: [
                  if (c.unitCount != null)
                    _infoChip(Icons.grid_view_rounded, '${c.unitCount} units'),
                  if (c.startPrice != null) ...[
                    SizedBox(width: 10),
                    _infoChip(
                      Icons.payments_outlined,
                      _fmtPrice(c.startPrice!),
                      gold: true,
                    ),
                  ],
                ],
              ),
            ),

          Divider(color: _border, height: 1),

          // Units
          if (_loading)
            const Padding(
              padding: EdgeInsets.all(32),
              child: CircularProgressIndicator(strokeWidth: 2, color: _gold),
            )
          else if (_units == null || _units!.isEmpty)
            Padding(
              padding: EdgeInsets.all(32),
              child: Text(
                AppStrings.noUnitsFound,
                style: TextStyle(color: _textMuted, fontSize: 14),
              ),
            )
          else
            Flexible(
              child: ListView.separated(
                padding: EdgeInsets.fromLTRB(16, 12, 16, 24),
                shrinkWrap: true,
                itemCount: _units!.length,
                separatorBuilder: (_, __) => SizedBox(height: 8),
                itemBuilder: (_, i) => UnitRow(unit: _units![i]),
              ),
            ),
        ],
      ),
    );
  }

  Widget _infoChip(IconData icon, String text, {bool gold = false}) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: gold
            ? _gold.withValues(alpha: 0.12)
            : Colors.white.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: gold ? _gold.withValues(alpha: 0.25) : _border,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: gold ? _gold : _textMuted),
          SizedBox(width: 5),
          Text(
            text,
            style: TextStyle(
              color: gold ? _gold : _textMuted,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  String _fmtPrice(double p) {
    if (p >= 1000000) {
      return 'From EGP ${(p / 1000000).toStringAsFixed(p % 1000000 == 0 ? 0 : 1)}M';
    }
    if (p >= 1000) return 'From EGP ${(p / 1000).toStringAsFixed(0)}K';
    return 'From EGP ${p.toStringAsFixed(0)}';
  }
}

class UnitRow extends StatelessWidget {
  final CompoundUnit unit;

  const UnitRow({super.key, required this.unit});

  static const _gold = AppColors.gold;
  static const _accent = AppColors.accent;


  @override
  Widget build(BuildContext context) {
    final _border = context.appColors.border;
    final _textPrimary = context.appColors.textPrimary;
    final _textMuted = context.appColors.textMuted;
    return GestureDetector(
      onTap: () {
        Navigator.of(
          context,
        ).push(MaterialPageRoute(builder: (_) => UnitDetailScreen(unit: unit)));
      },
      child: Container(
        padding: EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.03),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _border.withValues(alpha: 0.5)),
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: SizedBox(
                width: 60,
                height: 60,
                child: unit.images.isNotEmpty
                    ? Image.network(
                        unit.images.first,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _thumb(),
                      )
                    : _thumb(),
              ),
            ),
            SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          unit.type.isNotEmpty ? unit.type : unit.name,
                          style: TextStyle(
                            color: _textPrimary,
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (unit.saleType != null)
                        Container(
                          padding: EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color:
                                (unit.saleType == AppStrings.resale
                                        ? _accent
                                        : _gold)
                                    .withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            unit.saleType!,
                            style: TextStyle(
                              color: unit.saleType == AppStrings.resale
                                  ? _accent
                                  : _gold,
                              fontSize: 9,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                    ],
                  ),
                  SizedBox(height: 4),
                  Wrap(
                    spacing: 8,
                    children: [
                      if (unit.displayArea != null)
                        _info(context, '${unit.displayArea!.toInt()}m²'),
                      if (unit.bedrooms != null) _info(context, '${unit.bedrooms}bd'),
                      if (unit.bathrooms != null) _info(context, '${unit.bathrooms}ba'),
                      if (unit.finishing != null) _info(context, unit.finishing!),
                    ],
                  ),
                  if (unit.displayPrice != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      'EGP ${_fmtPrice(unit.displayPrice!)}',
                      style: TextStyle(
                        color: _gold,
                        fontWeight: FontWeight.w700,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _thumb() {
    return Container(
      color: Color(0xFF0A0E1A),
      child: Center(
        child: Icon(
          Icons.apartment_rounded,
          color: AppColors.gold.withValues(alpha: 0.2),
          size: 24,
        ),
      ),
    );
  }

  Widget _info(BuildContext context, String text) {
    return Text(text, style: TextStyle(color: context.appColors.textMuted, fontSize: 11));
  }

  String _fmtPrice(double p) {
    if (p >= 1000000) {
      final val = p / 1000000;
      return '${val.toStringAsFixed(val == val.roundToDouble() ? 0 : 1)}M';
    }
    return p
        .toStringAsFixed(0)
        .replaceAllMapped(
          RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
          (m) => '${m[1]},',
        );
  }
}
