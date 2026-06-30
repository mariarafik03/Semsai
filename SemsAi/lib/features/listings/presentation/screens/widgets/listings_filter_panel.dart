import 'package:SemsAi/core/utils/price_formatter.dart';
import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/features/listings/data/repo/listings_service.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


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
        color: context.appColors.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: context.appColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Region dropdown
          _filterLabel(context, 'Region'),
          const SizedBox(height: 6),
          _buildDropdown<String>(context, 
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
          _filterLabel(context, 'Property Type'),
          const SizedBox(height: 6),
          _buildDropdown<String>(context, 
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
          _filterLabel(context, 'Bedrooms'),
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
                          color: selected ? AppColors.gold : context.appColors.border,
                        ),
                      ),
                      child: Text(
                        b == null ? 'Any' : '$b+',
                        style: TextStyle(
                          color: selected
                              ? context.appColors.bg
                              : context.appColors.textPrimary,
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
            context,
            'Budget: ${PriceFormatter.format(minPrice)} – ${PriceFormatter.format(maxPrice)}',
          ),
          const SizedBox(height: 2),
          SliderTheme(
            data: SliderThemeData(
              activeTrackColor: AppColors.gold,
              inactiveTrackColor: context.appColors.border,
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
                    side: BorderSide(color: context.appColors.border),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  child: Text(
                    'Reset',
                    style: TextStyle(color: context.appColors.textPrimary),
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
                      color: context.appColors.bg,
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

  Widget _filterLabel(BuildContext context, String text) => Text(
    text,
    style: TextStyle(
      color: context.appColors.textMuted,
      fontSize: 12,
      fontWeight: FontWeight.w500,
    ),
  );

  Widget _buildDropdown<T>(BuildContext context, {
    required T? value,
    required String hint,
    required List<DropdownMenuItem<T>> items,
    required ValueChanged<T?> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: context.appColors.bg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: context.appColors.border),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T>(
          value: value,
          hint: Text(
            hint,
            style: TextStyle(color: context.appColors.textMuted, fontSize: 13),
          ),
          isExpanded: true,
          dropdownColor: context.appColors.cardBg,
          style: TextStyle(color: context.appColors.textPrimary, fontSize: 13),
          icon: Icon(
            Icons.keyboard_arrow_down,
            color: context.appColors.textMuted,
            size: 18,
          ),
          items: items,
          onChanged: onChanged,
        ),
      ),
    );
  }
}
