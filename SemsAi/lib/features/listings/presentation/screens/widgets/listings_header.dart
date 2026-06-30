import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class ListingsHeader extends StatelessWidget {
  const ListingsHeader({
    super.key,
    required this.sortBy,
    required this.filtersOpen,
    required this.onSortChanged,
    required this.onToggleFilters,
  });

  final String sortBy;
  final bool filtersOpen;
  final ValueChanged<String> onSortChanged;
  final VoidCallback onToggleFilters;

  String _sortLabel(String key) {
    switch (key) {
      case 'newest':
        return 'Newest';
      case 'price_asc':
        return 'Price ↑';
      case 'price_desc':
        return 'Price ↓';
      case 'area_asc':
        return 'Area ↑';
      case 'area_desc':
        return 'Area ↓';
      default:
        return 'Newest';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
      child: Row(
        children: [
          Text(
            'Listings',
            style: TextStyle(
              color: context.appColors.textPrimary,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const Spacer(),
          // Sort dropdown
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: context.appColors.cardBg,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: context.appColors.border),
            ),
            child: PopupMenuButton<String>(
              onSelected: onSortChanged,
              color: context.appColors.cardBg,
              itemBuilder: (_) => [
                'newest',
                'price_asc',
                'price_desc',
                'area_asc',
                'area_desc',
              ]
                  .map(
                    (k) => PopupMenuItem(
                      value: k,
                      child: Text(
                        _sortLabel(k),
                        style: TextStyle(
                          color: k == sortBy
                              ? AppColors.gold
                              : context.appColors.textPrimary,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  )
                  .toList(),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _sortLabel(sortBy),
                    style: TextStyle(
                      color: context.appColors.textPrimary,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Icon(
                    Icons.keyboard_arrow_down,
                    color: context.appColors.textMuted,
                    size: 18,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 8),
          // Filter button
          GestureDetector(
            onTap: onToggleFilters,
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: filtersOpen ? AppColors.gold : context.appColors.cardBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: filtersOpen ? AppColors.gold : context.appColors.border,
                ),
              ),
              child: Icon(
                Icons.tune,
                color: filtersOpen ? context.appColors.bg : context.appColors.textPrimary,
                size: 18,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
