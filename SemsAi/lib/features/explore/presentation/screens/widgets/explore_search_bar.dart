import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class ExploreSearchBar extends StatelessWidget {
  const ExploreSearchBar({
    super.key,
    required this.isOpen,
    required this.controller,
    required this.query,
    required this.onClear,
  });

  final bool isOpen;
  final TextEditingController controller;
  final String query;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: Duration(milliseconds: 250),
      height: isOpen ? 52 : 46,
      margin: EdgeInsets.fromLTRB(12, 6, 12, 2),
      padding: EdgeInsets.symmetric(horizontal: 14),
      decoration: BoxDecoration(
        color: context.appColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isOpen
              ? AppColors.gold.withValues(alpha: 0.4)
              : context.appColors.border,
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.search_rounded,
            color: isOpen ? AppColors.gold : context.appColors.textMuted,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: TextField(
              controller: controller,
              style: TextStyle(color: context.appColors.textPrimary, fontSize: 14),
              decoration: InputDecoration(
                hintText: AppStrings.searchHint,
                hintStyle: TextStyle(color: context.appColors.textMuted, fontSize: 13),
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.symmetric(vertical: 10),
              ),
            ),
          ),
          if (query.isNotEmpty)
            GestureDetector(
              onTap: onClear,
              child: Icon(
                Icons.close_rounded,
                color: context.appColors.textMuted,
                size: 18,
              ),
            ),
        ],
      ),
    );
  }
}
