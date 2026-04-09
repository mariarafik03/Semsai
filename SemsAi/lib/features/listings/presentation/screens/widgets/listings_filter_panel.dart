import 'package:SemsAi/core/utils/price_formatter.dart';
import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/features/listings/data/repo/listings_service.dart';

class ListingsFilterPanel extends StatelessWidget {
  const ListingsFilterPanel({
    super.key,
    required this.regions,
    required this.types,
    required this.selectedRegion,
    required this.selectedType,
    required this.selectedBedrooms,
    required this.minPrice,
    required this.maxPrice,
    required this.priceFloor,
    required this.priceCeil,
    required this.onRegionChanged,
    required this.onTypeChanged,
    required this.onBedroomsChanged,
    required this.onPriceRangeChanged,
    required this.onReset,
    required this.onApply,
  });

  final List<RegionFilter> regions;
  final List<String> types;
  final String? selectedRegion;
  final String? selectedType;
  final int? selectedBedrooms;
  final double minPrice;
  final double maxPrice;
  final double priceFloor;
  final double priceCeil;
  final ValueChanged<String?> onRegionChanged;
  final ValueChanged<String?> onTypeChanged;
  final ValueChanged<int?> onBedroomsChanged;
  final ValueChanged<RangeValues> onPriceRangeChanged;
  final VoidCallback onReset;
  final VoidCallback onApply;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Region dropdown
          _filterLabel('Region'),
          const SizedBox(height: 6),
          _buildDropdown<String>(
            value: selectedRegion,
            hint: 'All Regions',
            items: regions
                .map(
                  (r) => DropdownMenuItem(
                    value: r.name,
                    child: Text(
                      '${r.name}',
                      style: const TextStyle(fontSize: 13),
                    ),
                  ),
                )
                .toList(),
            onChanged: onRegionChanged,
          ),

          const SizedBox(height: 14),

          // Type dropdown
          _filterLabel('Property Type'),
          const SizedBox(height: 6),
          _buildDropdown<String>(
            value: selectedType,
            hint: 'All Types',
            items: types
                .map(
                  (t) => DropdownMenuItem(
                    value: t,
                    child: Text(t, style: const TextStyle(fontSize: 13)),
                  ),
                )
                .toList(),
            onChanged: onTypeChanged,
          ),

          const SizedBox(height: 14),

          // Bedrooms row
          _filterLabel('Bedrooms'),
          const SizedBox(height: 6),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [null, 1, 2, 3, 4, 5].map((b) {
                final selected = selectedBedrooms == b;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: GestureDetector(
                    onTap: () => onBedroomsChanged(b),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      decoration: BoxDecoration(
                        color: selected ? AppColors.gold : Colors.transparent,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: selected ? AppColors.gold : AppColors.border,
                        ),
                      ),
                      child: Text(
                        b == null ? 'Any' : '$b+',
                        style: TextStyle(
                          color: selected
                              ? AppColors.bg
                              : AppColors.textPrimary,
                          fontSize: 13,
                          fontWeight: selected
                              ? FontWeight.w600
                              : FontWeight.normal,
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),

          const SizedBox(height: 14),

          // Budget range
          _filterLabel(
            'Budget: ${PriceFormatter.format(minPrice)} – ${PriceFormatter.format(maxPrice)}',
          ),
          const SizedBox(height: 2),
          SliderTheme(
            data: SliderThemeData(
              activeTrackColor: AppColors.gold,
              inactiveTrackColor: AppColors.border,
              thumbColor: AppColors.gold,
              overlayColor: AppColors.gold.withValues(alpha: 0.2),
              trackHeight: 3,
              rangeThumbShape: const RoundRangeSliderThumbShape(
                enabledThumbRadius: 7,
              ),
            ),
            child: RangeSlider(
              values: RangeValues(minPrice, maxPrice),
              min: priceFloor,
              max: priceCeil,
              divisions: 100,
              onChanged: onPriceRangeChanged,
            ),
          ),

          const SizedBox(height: 12),

          // Action row
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: onReset,
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: AppColors.border),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  child: const Text(
                    'Reset',
                    style: TextStyle(color: AppColors.textPrimary),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton(
                  onPressed: onApply,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.gold,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  child: Text(
                    'Apply',
                    style: TextStyle(
                      color: AppColors.bg,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _filterLabel(String text) => Text(
    text,
    style: const TextStyle(
      color: AppColors.textMuted,
      fontSize: 12,
      fontWeight: FontWeight.w500,
    ),
  );

  Widget _buildDropdown<T>({
    required T? value,
    required String hint,
    required List<DropdownMenuItem<T>> items,
    required ValueChanged<T?> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: AppColors.bg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T>(
          value: value,
          hint: Text(
            hint,
            style: const TextStyle(color: AppColors.textMuted, fontSize: 13),
          ),
          isExpanded: true,
          dropdownColor: AppColors.cardBg,
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
          icon: const Icon(
            Icons.keyboard_arrow_down,
            color: AppColors.textMuted,
            size: 18,
          ),
          items: items,
          onChanged: onChanged,
        ),
      ),
    );
  }
}
