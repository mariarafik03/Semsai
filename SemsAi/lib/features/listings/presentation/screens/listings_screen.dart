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
import 'package:SemsAi/core/shared_pref/shared_pref_helper.dart';
import 'package:SemsAi/core/widgets/app_loading_indicator.dart';
import 'package:SemsAi/core/widgets/app_error_widget.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/features/comparison/presentation/cubit/comparison_cubit.dart';
import 'package:SemsAi/features/comparison/presentation/cubit/comparison_state.dart';
import 'package:SemsAi/features/comparison/presentation/widgets/comparison_bottom_bar.dart';
import 'package:SemsAi/core/utils/app_snackbar.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class ListingsScreen extends StatefulWidget {
  const ListingsScreen({super.key, this.onNavigateToChat});

  final VoidCallback? onNavigateToChat;

  @override
  ListingsScreenState createState() => ListingsScreenState();
}

class ListingsScreenState extends State<ListingsScreen> {
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
    _initFiltersAndLoad();
  }

  Future<void> _initFiltersAndLoad() async {
    await _loadFilters();
    await _applyDefaultRegionThenLoad();
  }

  Future<void> _applyDefaultRegionThenLoad() async {
    final region = await SharedPrefHelper.getDefaultRegion();
    if (region != 'No default' && mounted) {
      // Only set region if it actually exists in the loaded filter list
      final regionNames = _regions.map((r) => r.name).toSet();
      if (regionNames.contains(region)) {
        setState(() => _selectedRegion = region);
      } else {
        setState(() => _selectedRegion = null);
      }
    } else if (mounted) {
      setState(() => _selectedRegion = null);
    }
    _loadListings();
  }

  void refreshDefaultRegion() {
    _applyDefaultRegionThenLoad();
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
      backgroundColor: context.appColors.bg,
      resizeToAvoidBottomInset: false,
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
            Flexible(
              flex: 0,
              child: AnimatedCrossFade(
                firstChild: const SizedBox.shrink(),
                secondChild: SingleChildScrollView(
                  child: ListingsFilterPanel(
                    regions: _regions,
                    types: _types,
                    selectedRegion: _selectedRegion,
                    selectedType: _selectedType,
                    selectedBedrooms: _selectedBedrooms,
                    minPrice: _minPrice,
                    maxPrice: _maxPrice,
                    priceFloor: _priceFloor,
                    priceCeil: _priceCeil,
                    onRegionChanged: (v) => setState(() => _selectedRegion = v),
                    onTypeChanged: (v) => setState(() => _selectedType = v),
                    onBedroomsChanged: (v) => setState(() => _selectedBedrooms = v),
                    onPriceRangeChanged: (v) => setState(() {
                      _minPrice = v.start;
                      _maxPrice = v.end;
                    }),
                    onReset: _resetFilters,
                    onApply: _applyFilters,
                  ),
                ),
                crossFadeState: _filtersOpen
                    ? CrossFadeState.showSecond
                    : CrossFadeState.showFirst,
                duration: const Duration(milliseconds: 300),
                sizeCurve: Curves.easeInOut,
              ),
            ),
            _buildResultsBar(),
            Expanded(
              child: Stack(
                children: [
                  _buildBody(),
                  const Positioned(
                    left: 0,
                    right: 0,
                    bottom: 0,
                    child: ComparisonBottomBar(),
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
            style: TextStyle(color: context.appColors.textMuted, fontSize: 13),
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
    if (_loading) return const AppLoadingCenter();
    if (_hasError) {
      return AppErrorWidget(
        message: AppStrings.loadFailed,
        onRetry: _loadListings,
      );
    }
    if (_units.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off, color: context.appColors.textMuted, size: 48),
            const SizedBox(height: 12),
            Text(
              AppStrings.noUnitsFound,
              style: TextStyle(color: context.appColors.textMuted),
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
        final unit = _units[i];
        return StaggeredCard(
          index: i,
          child: RepaintBoundary(
            child: BlocBuilder<ComparisonCubit, ComparisonState>(
              builder: (context, compState) {
                final isSelected = compState.isSelected(unit.id);
                return ListingUnitCard(
                  unit: unit,
                  compareSelected: isSelected,
                  compareDisabled: compState.isFull && !isSelected,
                  onCompareToggle: () {
                    final cubit = context.read<ComparisonCubit>();
                    final ok = cubit.toggle(unit);
                    if (!ok) {
                      AppSnackBar.error(
                        context,
                        'You can compare up to 3 properties',
                      );
                    }
                  },
                );
              },
            ),
          ),
        );
      },
    );
  }
}
