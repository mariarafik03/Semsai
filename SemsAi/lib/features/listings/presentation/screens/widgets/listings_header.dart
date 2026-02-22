import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';

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
          const Text(
            'Listings',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const Spacer(),
          // Sort dropdown
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.cardBg,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.border),
            ),
            child: PopupMenuButton<String>(
              onSelected: onSortChanged,
              color: AppColors.cardBg,
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
                              : AppColors.textPrimary,
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
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(width: 4),
                  const Icon(
                    Icons.keyboard_arrow_down,
                    color: AppColors.textMuted,
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
                color: filtersOpen ? AppColors.gold : AppColors.cardBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: filtersOpen ? AppColors.gold : AppColors.border,
                ),
              ),
              child: Icon(
                Icons.tune,
                color: filtersOpen ? AppColors.bg : AppColors.textPrimary,
                size: 18,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
