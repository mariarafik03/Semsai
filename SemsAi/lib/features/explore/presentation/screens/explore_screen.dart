import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart' hide Path;

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/core/networking/api_constants.dart';
import 'package:SemsAi/features/explore/data/models/compound_model.dart';
import 'package:SemsAi/features/explore/data/repo/explore_service.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/circle_dot.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/area_chip.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/compound_sheet.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/explore_search_bar.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/map_count_badge.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/properties_panel.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/explore_loading.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/explore_error.dart';
import 'package:SemsAi/core/shared_pref/shared_pref_helper.dart';

class ExploreScreen extends StatefulWidget {
  const ExploreScreen({super.key});

  @override
  ExploreScreenState createState() => ExploreScreenState();
}

class ExploreScreenState extends State<ExploreScreen> {
  static const LatLng _cairoCenter = LatLng(30.0444, 31.2357);
  static const List<Color> _palette = AppColors.areaPalette;

  final MapController _mapController = MapController();

  // -- Data --
  List<Compound> _compounds = [];
  List<Compound> _filteredCompounds = [];
  List<Map<String, dynamic>> _areas = [];
  bool _loading = true;
  String? _errorMsg;

  // -- Selection --
  String? _selectedArea;
  Compound? _selectedCompound;
  final Map<String, Color> _areaColorMap = {};

  // -- Search --
  bool _searchOpen = false;
  final TextEditingController _searchCtrl = TextEditingController();
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _loadData();
    _searchCtrl.addListener(() {
      final q = _searchCtrl.text.trim().toLowerCase();
      if (q != _searchQuery) {
        setState(() {
          _searchQuery = q;
          _applyFilters();
        });
      }
    });
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  // -- Data loading --

  Future<void> _loadData() async {
    try {
      final compounds = await ExploreService.getMapCompounds();
      _compounds = compounds;
      _filteredCompounds = compounds;
      _deriveAreas();
      await _applyDefaultRegion();
      setState(() => _loading = false);
    } catch (e) {
      setState(() {
        _loading = false;
        _errorMsg = e.toString();
      });
    }
  }

  Future<void> _applyDefaultRegion() async {
    final region = await SharedPrefHelper.getDefaultRegion();
    if (region != 'No default') {
      final match = _areas.any((a) => a['name'] == region);
      if (match) {
        _selectedArea = region;
        _applyFilters();
      }
    } else {
      _selectedArea = null;
      _applyFilters();
    }
  }

  void refreshDefaultRegion() {
    _applyDefaultRegion().then((_) {
      if (mounted) {
        setState(() {});
        _fitBounds();
      }
    });
  }

  void _deriveAreas() {
    final map = <String, int>{};
    for (final c in _compounds) {
      if (c.location != null && c.location!.trim().isNotEmpty) {
        map[c.location!] = (map[c.location!] ?? 0) + 1;
      }
    }
    final sorted = map.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    _areas = sorted
        .take(15)
        .map((e) => {'name': e.key, 'count': e.value})
        .toList();

    for (int i = 0; i < _areas.length && i < _palette.length; i++) {
      _areaColorMap[_areas[i]['name'] as String] = _palette[i];
    }
  }

  // -- Area selection --

  void _selectArea(String? area) {
    setState(() {
      _selectedArea = area;
      _selectedCompound = null;
      _applyFilters();
      if (area == null && _searchQuery.isEmpty) {
        _mapController.move(_cairoCenter, 10);
      } else {
        _fitBounds();
      }
    });
  }

  void _applyFilters() {
    var list = _compounds.toList();
    if (_selectedArea != null) {
      list = list.where((c) => c.location == _selectedArea).toList();
    }
    if (_searchQuery.isNotEmpty) {
      list = list.where((c) {
        final name = c.name.toLowerCase();
        final loc = (c.location ?? '').toLowerCase();
        final dev = (c.developerName ?? '').toLowerCase();
        return name.contains(_searchQuery) ||
            loc.contains(_searchQuery) ||
            dev.contains(_searchQuery);
      }).toList();
    }
    _filteredCompounds = list;
  }

  void _fitBounds() {
    if (_filteredCompounds.isEmpty) return;
    if (_filteredCompounds.length == 1) {
      _mapController.move(
        LatLng(_filteredCompounds.first.lat, _filteredCompounds.first.lng),
        13,
      );
      return;
    }
    double minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
    for (final c in _filteredCompounds) {
      if (c.lat < minLat) minLat = c.lat;
      if (c.lat > maxLat) maxLat = c.lat;
      if (c.lng < minLng) minLng = c.lng;
      if (c.lng > maxLng) maxLng = c.lng;
    }
    _mapController.fitCamera(
      CameraFit.bounds(
        bounds: LatLngBounds(LatLng(minLat, minLng), LatLng(maxLat, maxLng)),
        padding: const EdgeInsets.all(50),
      ),
    );
  }

  Color _markerColor(Compound c) {
    return _areaColorMap[c.location] ?? AppColors.gold.withValues(alpha: 0.7);
  }

  // -- Interactions --

  void _onMarkerTap(Compound compound) {
    setState(() => _selectedCompound = compound);
    _mapController.move(LatLng(compound.lat, compound.lng), 14);
    _showCompoundSheet(compound);
  }

  void _onCardTap(Compound compound) {
    setState(() => _selectedCompound = compound);
    _mapController.move(LatLng(compound.lat, compound.lng), 14);
    _showCompoundSheet(compound);
  }

  void _showCompoundSheet(Compound compound) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => CompoundSheet(compound: compound),
    );
  }

  void _clearSearch() {
    _searchCtrl.clear();
    FocusScope.of(context).unfocus();
    setState(() {
      _searchOpen = false;
      _searchQuery = '';
      _applyFilters();
    });
  }

  // -- Build --

  @override
  Widget build(BuildContext context) {
    if (_loading) return const ExploreLoadingView();
    if (_errorMsg != null && _compounds.isEmpty) {
      return ExploreErrorView(
        onRetry: () {
          setState(() {
            _loading = true;
            _errorMsg = null;
          });
          _loadData();
        },
      );
    }

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            ExploreSearchBar(
              isOpen: _searchOpen,
              controller: _searchCtrl,
              query: _searchQuery,
              onClear: _clearSearch,
            ),
            _buildAreaChips(),
            Expanded(
              flex: 55,
              child: Stack(
                children: [
                  _buildMap(),
                  Positioned(
                    top: 8,
                    left: 12,
                    child: MapCountBadge(count: _filteredCompounds.length),
                  ),
                ],
              ),
            ),
            Expanded(
              flex: 45,
              child: PropertiesPanel(
                areaName: _selectedArea ?? AppStrings.allProperties,
                compounds: _filteredCompounds,
                areaColorMap: _areaColorMap,
                onCardTap: _onCardTap,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // -- Area Chips --

  Widget _buildAreaChips() {
    return SizedBox(
      height: 44,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        children: [
          AreaChip(
            label: AppStrings.allFilter,
            count: _compounds.length,
            isSelected: _selectedArea == null,
            onTap: () => _selectArea(null),
          ),
          ..._areas.map(
            (a) => Padding(
              padding: const EdgeInsets.only(left: 8),
              child: AreaChip(
                label: a['name'] as String,
                count: a['count'] as int,
                isSelected: _selectedArea == a['name'],
                color: _areaColorMap[a['name'] as String],
                onTap: () => _selectArea(a['name'] as String),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // -- Map --

  Widget _buildMap() {
    return ClipRRect(
      child: FlutterMap(
        mapController: _mapController,
        options: MapOptions(
          initialCenter: _cairoCenter,
          initialZoom: 10,
          backgroundColor: AppColors.bg,
          onTap: (_, __) => setState(() => _selectedCompound = null),
        ),
        children: [
          TileLayer(
            urlTemplate: ApiConstants.tileUrl,
            subdomains: const ['a', 'b', 'c', 'd'],
            userAgentPackageName: ApiConstants.userAgent,
          ),
          MarkerLayer(
            markers: _filteredCompounds.map((c) {
              final sel = _selectedCompound?.id == c.id;
              final color = _markerColor(c);
              return Marker(
                point: LatLng(c.lat, c.lng),
                width: sel ? 28 : 18,
                height: sel ? 28 : 18,
                child: GestureDetector(
                  onTap: () => _onMarkerTap(c),
                  child: CircleDot(color: color, isSelected: sel),
                ),
              );
            }).toList(),
          ),
          RichAttributionWidget(
            alignment: AttributionAlignment.bottomRight,
            attributions: [
              TextSourceAttribution(
                ApiConstants.mapAttribution,
                textStyle: TextStyle(
                  color: AppColors.textMuted.withValues(alpha: 0.4),
                  fontSize: 9,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
