import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/widgets/app_cached_image.dart';
import 'package:SemsAi/core/widgets/app_loading_indicator.dart';
import 'package:SemsAi/core/widgets/app_error_widget.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/explore/presentation/screens/unit_detail_screen.dart';
import 'package:SemsAi/features/favorite/presentation/cubit/favorite_cubit.dart';
import 'package:SemsAi/features/listings/data/repo/listings_service.dart';
import 'package:SemsAi/features/listings/data/repo/listings_service.dart'
    show RegionFilter;
import 'package:SemsAi/features/favorite/presentation/cubit/favorite_state.dart';
import 'package:SemsAi/features/listings/presentation/screens/widgets/listings_search_bar.dart';
import 'package:SemsAi/features/listings/presentation/screens/widgets/listings_filter_panel.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class FavouriteScreen extends StatelessWidget {
  const FavouriteScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return _FavouriteScreenBody();
  }
}

class _FavouriteScreenBody extends StatefulWidget {
  @override
  State<_FavouriteScreenBody> createState() => _FavouriteScreenBodyState();
}

class _FavouriteScreenBodyState extends State<_FavouriteScreenBody> {
  // Filters
  List<RegionFilter> _regions = [];
  List<String> _types = [];
  String? _selectedRegion;
  String? _selectedType;
  int? _selectedBedrooms;
  double _minPrice = 0;
  double _maxPrice = 50000000;
  bool _filtersOpen = false;
  String _searchQuery = '';
  final TextEditingController _searchController = TextEditingController();

  static const double _priceFloor = 0;
  static const double _priceCeil = 50000000;

  @override
  void initState() {
    super.initState();
    _loadFilters();
  }

  Future<void> _loadFilters() async {
    try {
      final filters = await ListingsService.getFilters();
      setState(() {
        _regions = filters.regions;
        _types = filters.types;
      });
    } catch (e) {
      debugPrint('Favorite filters error: $e');
    }
  }

  void _onSearchChanged(String query) {
    setState(() => _searchQuery = query);
  }

  void _onToggleFilters() {
    setState(() => _filtersOpen = !_filtersOpen);
  }

  void _onRegionChanged(String? region) {
    setState(() => _selectedRegion = region);
  }

  void _onTypeChanged(String? type) {
    setState(() => _selectedType = type);
  }

  void _onBedroomsChanged(int? bedrooms) {
    setState(() => _selectedBedrooms = bedrooms);
  }

  void _onPriceRangeChanged(RangeValues values) {
    setState(() {
      _minPrice = values.start;
      _maxPrice = values.end;
    });
  }

  void _onResetFilters() {
    setState(() {
      _selectedRegion = null;
      _selectedType = null;
      _selectedBedrooms = null;
      _minPrice = _priceFloor;
      _maxPrice = _priceCeil;
      _searchQuery = '';
      _searchController.clear();
    });
  }

  List<CompoundUnit> _applyFilters(List<CompoundUnit> units) {
    return units.where((u) {
      final matchesRegion =
          _selectedRegion == null ||
          u.location?.contains(_selectedRegion!) == true;
      final matchesType = _selectedType == null || u.type == _selectedType;
      final matchesBedrooms =
          _selectedBedrooms == null || u.bedrooms == _selectedBedrooms;
      final price = u.displayPrice ?? 0;
      final matchesPrice = price >= _minPrice && price <= _maxPrice;
      final matchesSearch =
          _searchQuery.isEmpty ||
          u.name.toLowerCase().contains(_searchQuery.toLowerCase()) ||
          (u.location != null &&
              u.location!.toLowerCase().contains(_searchQuery.toLowerCase()));
      return matchesRegion &&
          matchesType &&
          matchesBedrooms &&
          matchesPrice &&
          matchesSearch;
    }).toList();
  }

  String _sortBy = 'newest';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: context.appColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            // Listings-style Header
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 8),
              child: Row(
                children: [
                  const Icon(
                    Icons.favorite_rounded,
                    color: Colors.redAccent,
                    size: 26,
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'My Favorites',
                    style: TextStyle(
                      color: context.appColors.textPrimary,
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const Spacer(),
                  // Sort dropdown
                  DropdownButton<String>(
                    value: _sortBy,
                    dropdownColor: context.appColors.cardBg,
                    underline: const SizedBox.shrink(),
                    style: TextStyle(
                      color: context.appColors.textPrimary,
                      fontSize: 14,
                    ),
                    icon: Icon(
                      Icons.keyboard_arrow_down_rounded,
                      color: context.appColors.textMuted,
                      size: 20,
                    ),
                    items: const [
                      DropdownMenuItem(value: 'newest', child: Text('Newest')),
                      DropdownMenuItem(
                        value: 'price_low',
                        child: Text('Price (Low)'),
                      ),
                      DropdownMenuItem(
                        value: 'price_high',
                        child: Text('Price (High)'),
                      ),
                    ],
                    onChanged: (v) => setState(() => _sortBy = v ?? 'newest'),
                  ),
                  const SizedBox(width: 8),
                  // Filter icon button
                  IconButton(
                    icon: Icon(
                      _filtersOpen
                          ? Icons.filter_alt
                          : Icons.filter_alt_outlined,
                      color: AppColors.gold,
                    ),
                    onPressed: _onToggleFilters,
                  ),
                ],
              ),
            ),
            ListingsSearchBar(
              controller: _searchController,
              onChanged: _onSearchChanged,
              onClear: _onResetFilters,
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
                onRegionChanged: _onRegionChanged,
                onTypeChanged: _onTypeChanged,
                onBedroomsChanged: _onBedroomsChanged,
                onPriceRangeChanged: _onPriceRangeChanged,
                onReset: _onResetFilters,
                onApply: _onToggleFilters,
              ),
              crossFadeState: _filtersOpen
                  ? CrossFadeState.showSecond
                  : CrossFadeState.showFirst,
              duration: const Duration(milliseconds: 300),
              sizeCurve: Curves.easeInOut,
            ),
            // Body
            Expanded(
              child: BlocBuilder<FavoriteCubit, FavoriteState>(
                builder: (context, state) {
                  if (state is FavoriteLoading) {
                    return const AppLoadingCenter();
                  }
                  if (state is FavoriteLoaded) {
                    var filtered = _applyFilters(state.favorites);
                    if (_sortBy == 'price_low') {
                      filtered.sort(
                        (a, b) => (a.displayPrice ?? 0).compareTo(
                          b.displayPrice ?? 0,
                        ),
                      );
                    } else if (_sortBy == 'price_high') {
                      filtered.sort(
                        (a, b) => (b.displayPrice ?? 0).compareTo(
                          a.displayPrice ?? 0,
                        ),
                      );
                    } else {
                      filtered.sort((a, b) => b.id.compareTo(a.id)); // newest
                    }
                    if (filtered.isEmpty) return _emptyState();
                    return _buildList(context, filtered);
                  }
                  if (state is FavoriteError) {
                    return AppErrorWidget(
                      message: 'Error: ${state.message}',
                      onRetry: () =>
                          context.read<FavoriteCubit>().loadFavorites(),
                    );
                  }
                  return _emptyState();
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  bool _hasActiveFilters() {
    return _selectedRegion != null ||
        _selectedType != null ||
        _selectedBedrooms != null ||
        _minPrice > _priceFloor ||
        _maxPrice < _priceCeil ||
        _searchQuery.isNotEmpty;
  }

  Widget _emptyState() {
    return Center(
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 90,
              height: 90,
              decoration: BoxDecoration(
                color: context.appColors.cardBg,
                shape: BoxShape.circle,
                border: Border.all(color: context.appColors.border, width: 1.5),
              ),
              child: Icon(
                Icons.favorite_border_rounded,
                size: 42,
                color: context.appColors.textMuted,
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'No favorites yet',
              style: TextStyle(
                color: context.appColors.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Padding(
              padding: EdgeInsets.symmetric(horizontal: 50),
              child: Text(
                'Tap the heart icon on any listing to save it here',
                textAlign: TextAlign.center,
                style: TextStyle(color: context.appColors.textMuted, fontSize: 14),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── List ──

  Widget _buildList(BuildContext context, List<CompoundUnit> favorites) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      itemCount: favorites.length,
      itemBuilder: (context, index) {
        final unit = favorites[index];
        return _FavoriteCard(
          unit: unit,
          onDelete: () {
            context.read<FavoriteCubit>().removeFavorite(unit.id);
          },
        );
      },
    );
  }
}

// ── Card widget ──

class _FavoriteCard extends StatelessWidget {
  const _FavoriteCard({required this.unit, required this.onDelete});
  final CompoundUnit unit;
  final VoidCallback onDelete;

  // Removed: Use PriceFormatter.format instead.

  @override
  Widget build(BuildContext context) {
    final image = unit.images.isNotEmpty ? unit.images.first : null;

    return GestureDetector(
      onTap: () => Navigator.of(context).push(
        PageRouteBuilder(
          transitionDuration: const Duration(milliseconds: 400),
          reverseTransitionDuration: const Duration(milliseconds: 350),
          pageBuilder: (_, __, ___) => UnitDetailScreen(unit: unit),
          transitionsBuilder: (_, anim, __, child) =>
              FadeTransition(opacity: anim, child: child),
        ),
      ),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: context.appColors.cardBg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: context.appColors.border.withValues(alpha: 0.6)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 8,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Row(
          children: [
            // Thumbnail
            ClipRRect(
              borderRadius: const BorderRadius.horizontal(
                left: Radius.circular(14),
              ),
              child: SizedBox(
                width: 110,
                height: 110,
                child: AppCachedImage(
                  imageUrl: image,
                  fit: BoxFit.cover,
                  memCacheWidth: 220,
                ),
              ),
            ),
            // Info
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 10, 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      unit.compoundName ?? unit.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: context.appColors.textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (unit.developerName != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        unit.developerName!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: context.appColors.textMuted,
                          fontSize: 12,
                        ),
                      ),
                    ],
                    const SizedBox(height: 6),
                    // Specs
                    Row(
                      children: [
                        if (unit.bedrooms != null)
                          _spec(context, Icons.bed_outlined, '${unit.bedrooms}'),
                        if (unit.bathrooms != null) ...[
                          const SizedBox(width: 10),
                          _spec(context, Icons.bathtub_outlined, '${unit.bathrooms}'),
                        ],
                        if (unit.displayArea != null) ...[
                          const SizedBox(width: 10),
                          _spec(context,
                            Icons.straighten,
                            '${unit.displayArea!.round()} m²',
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 6),
                    // Price + type tag
                    Row(
                      children: [
                        Text(
                          unit.displayPrice.toString(),
                          style: const TextStyle(
                            color: AppColors.gold,
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.accent.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            unit.type,
                            style: const TextStyle(
                              color: AppColors.accent,
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            // Delete button
            GestureDetector(
              onTap: onDelete,
              child: Padding(
                padding: const EdgeInsets.only(right: 10),
                child: Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    color: Colors.redAccent.withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.delete_outline_rounded,
                    color: Colors.redAccent,
                    size: 18,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _spec(BuildContext context, IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: context.appColors.textMuted, size: 13),
        const SizedBox(width: 3),
        Text(
          text,
          style: TextStyle(color: context.appColors.textMuted, fontSize: 11),
        ),
      ],
    );
  }
}
