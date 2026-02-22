import 'dart:async';
import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/listings/data/repo/listings_service.dart';
import 'package:SemsAi/core/widgets/shimmer_loading.dart';
import 'package:SemsAi/features/listings/presentation/screens/widgets/staggered_card.dart';
import 'package:SemsAi/features/listings/presentation/screens/widgets/listings_header.dart';
import 'package:SemsAi/features/listings/presentation/screens/widgets/listings_search_bar.dart';
import 'package:SemsAi/features/listings/presentation/screens/widgets/listings_filter_panel.dart';
import 'package:SemsAi/features/listings/presentation/screens/widgets/listing_unit_card.dart';
import 'package:SemsAi/features/listings/presentation/screens/widgets/ai_prompt_banner.dart';

class ListingsScreen extends StatefulWidget {
  const ListingsScreen({super.key, this.onNavigateToChat});

  final VoidCallback? onNavigateToChat;

  @override
  State<ListingsScreen> createState() => _ListingsScreenState();
}

class _ListingsScreenState extends State<ListingsScreen> {
  // -- Data --
  final List<CompoundUnit> _units = [];
  int _page = 1;
  int _totalPages = 1;
  int _total = 0;
  bool _loading = true;
  bool _loadingMore = false;
  bool _hasError = false;
  bool _bannerDismissed = false;

  // -- Filters --
  List<RegionFilter> _regions = [];
  List<String> _types = [];
  String? _selectedRegion;
  String? _selectedType;
  int? _selectedBedrooms;
  double _minPrice = 0;
  double _maxPrice = 50000000;
  String _sortBy = 'newest';
  bool _filtersOpen = false;
  String _searchQuery = '';

  static const double _priceFloor = 0;
  static const double _priceCeil = 50000000;

  final ScrollController _scrollController = ScrollController();
  final TextEditingController _searchController = TextEditingController();
  Timer? _searchDebounce;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _loadFilters();
    _loadListings();
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _searchController.dispose();
    _searchDebounce?.cancel();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
            _scrollController.position.maxScrollExtent - 300 &&
        !_loadingMore &&
        _page < _totalPages) {
      _loadMore();
    }
  }

  Future<void> _loadFilters() async {
    try {
      final filters = await ListingsService.getFilters();
      if (mounted) {
        setState(() {
          _regions = filters.regions;
          _types = filters.types;
        });
      }
    } catch (e) {
      debugPrint('Load filters error: $e');
    }
  }

  Future<void> _loadListings({bool reset = true}) async {
    if (reset) {
      setState(() {
        _page = 1;
        _loading = true;
        _hasError = false;
        _units.clear();
      });
    }
    try {
      final res = await ListingsService.getListings(
        page: _page,
        region: _selectedRegion,
        type: _selectedType,
        bedrooms: _selectedBedrooms,
        minPrice: _minPrice > 0 ? _minPrice : null,
        maxPrice: _maxPrice < _priceCeil ? _maxPrice : null,
        search: _searchQuery.isNotEmpty ? _searchQuery : null,
        sort: _sortBy,
      );
      if (mounted) {
        setState(() {
          _units.addAll(res.units);
          _total = res.total;
          _totalPages = res.totalPages;
          _loading = false;
          _loadingMore = false;
        });
      }
    } catch (e) {
      debugPrint('Load listings error: $e');
      if (mounted) {
        setState(() {
          _loading = false;
          _loadingMore = false;
          _hasError = true;
        });
      }
    }
  }

  Future<void> _loadMore() async {
    setState(() {
      _page++;
      _loadingMore = true;
    });
    await _loadListings(reset: false);
  }

  void _applyFilters() {
    setState(() => _filtersOpen = false);
    _loadListings();
  }

  void _resetFilters() {
    setState(() {
      _selectedRegion = null;
      _selectedType = null;
      _selectedBedrooms = null;
      _minPrice = _priceFloor;
      _maxPrice = _priceCeil;
      _searchQuery = '';
      _searchController.clear();
    });
    _loadListings();
  }

  void _onSearchChanged(String query) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 500), () {
      _searchQuery = query;
      _loadListings();
    });
  }

  // -- Helpers --

  String _formatPrice(double? p) {
    if (p == null) return AppStrings.contactForPrice;
    if (p >= 1000000) {
      final v = p / 1000000;
      return '${v.toStringAsFixed(v == v.roundToDouble() ? 0 : 1)}M EGP';
    }
    if (p >= 1000) return '${(p / 1000).toStringAsFixed(0)}K EGP';
    return '${p.toStringAsFixed(0)} EGP';
  }

  bool get _hasActiveFilters =>
      _selectedRegion != null ||
      _selectedType != null ||
      _selectedBedrooms != null ||
      _minPrice > 0 ||
      _maxPrice < _priceCeil ||
      _searchQuery.isNotEmpty;

  String _formatCount(int n) {
    if (n >= 1000) return '${(n / 1000).toStringAsFixed(1)}k';
    return '$n';
  }

  // -- Build --

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            ListingsHeader(
              sortBy: _sortBy,
              filtersOpen: _filtersOpen,
              onSortChanged: (v) {
                setState(() => _sortBy = v);
                _loadListings();
              },
              onToggleFilters: () =>
                  setState(() => _filtersOpen = !_filtersOpen),
            ),
            ListingsSearchBar(
              controller: _searchController,
              onChanged: _onSearchChanged,
              onClear: () {
                _searchController.clear();
                _searchQuery = '';
                _loadListings();
              },
            ),
            AnimatedCrossFade(
              firstChild: const SizedBox.shrink(),
              secondChild: ListingsFilterPanel(
                regions: _regions,
                types: _types,
                selectedRegion: _selectedRegion,
                selectedType: _selectedType,
                selectedBedrooms: _selectedBedrooms,
                minPrice: _minPrice,
                maxPrice: _maxPrice,
                priceFloor: _priceFloor,
                priceCeil: _priceCeil,
                formatPrice: _formatPrice,
                onRegionChanged: (v) => setState(() => _selectedRegion = v),
                onTypeChanged: (v) => setState(() => _selectedType = v),
                onBedroomsChanged: (v) =>
                    setState(() => _selectedBedrooms = v),
                onPriceRangeChanged: (v) => setState(() {
                  _minPrice = v.start;
                  _maxPrice = v.end;
                }),
                onReset: _resetFilters,
                onApply: _applyFilters,
              ),
              crossFadeState: _filtersOpen
                  ? CrossFadeState.showSecond
                  : CrossFadeState.showFirst,
              duration: const Duration(milliseconds: 300),
              sizeCurve: Curves.easeInOut,
            ),
            _buildResultsBar(),
            Expanded(
              child: Stack(
                children: [
                  _buildBody(),
                  if (widget.onNavigateToChat != null && !_bannerDismissed)
                    Positioned(
                      left: 0,
                      right: 0,
                      bottom: 0,
                      child: AiPromptBanner(
                        onTap: widget.onNavigateToChat!,
                        onDismiss: () =>
                            setState(() => _bannerDismissed = true),
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

  // -- Results bar --

  Widget _buildResultsBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 6),
      child: Row(
        children: [
          Text(
            _loading ? 'Loading...' : '${_formatCount(_total)} properties',
            style: const TextStyle(color: AppColors.textMuted, fontSize: 13),
          ),
          const Spacer(),
          if (_hasActiveFilters)
            GestureDetector(
              onTap: _resetFilters,
              child: const Text(
                'Clear filters',
                style: TextStyle(
                  color: AppColors.gold,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
        ],
      ),
    );
  }

  // -- Body --

  Widget _buildBody() {
    if (_loading) return _buildSkeletonGrid();
    if (_hasError) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              color: AppColors.textMuted,
              size: 48,
            ),
            const SizedBox(height: 12),
            Text(
              AppStrings.loadFailed,
              style: const TextStyle(color: AppColors.textMuted),
            ),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: _loadListings,
              style:
                  ElevatedButton.styleFrom(backgroundColor: AppColors.gold),
              child: Text(
                AppStrings.retry,
                style: TextStyle(color: AppColors.bg),
              ),
            ),
          ],
        ),
      );
    }
    if (_units.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.search_off,
              color: AppColors.textMuted,
              size: 48,
            ),
            const SizedBox(height: 12),
            Text(
              AppStrings.noUnitsFound,
              style: const TextStyle(color: AppColors.textMuted),
            ),
            if (_hasActiveFilters) ...[
              const SizedBox(height: 12),
              TextButton(
                onPressed: _resetFilters,
                child: const Text(
                  'Reset filters',
                  style: TextStyle(color: AppColors.gold),
                ),
              ),
            ],
          ],
        ),
      );
    }

    return GridView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 80),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 0.58,
      ),
      itemCount: _units.length + (_loadingMore ? 2 : 0),
      itemBuilder: (context, i) {
        if (i >= _units.length) return const ListingCardSkeleton();
        return StaggeredCard(
          index: i,
          child: RepaintBoundary(child: ListingUnitCard(unit: _units[i])),
        );
      },
    );
  }

  Widget _buildSkeletonGrid() {
    return GridView.builder(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 80),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 0.58,
      ),
      itemCount: 6,
      itemBuilder: (_, __) => const ListingCardSkeleton(),
    );
  }
}