import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/core/widgets/app_cached_image.dart';
import 'package:SemsAi/core/widgets/tap_scale.dart';
import 'package:SemsAi/features/explore/data/models/compound_model.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/tag_overlay.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/mini_icon.dart';

class PropertiesPanel extends StatelessWidget {
  const PropertiesPanel({
    super.key,
    required this.areaName,
    required this.compounds,
    required this.areaColorMap,
    required this.onCardTap,
  });

  final String areaName;
  final List<Compound> compounds;
  final Map<String, Color> areaColorMap;
  final ValueChanged<Compound> onCardTap;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(22)),
        border: const Border(top: BorderSide(color: AppColors.border)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 16,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.gold.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 8),
            child: Row(
              children: [
                const Icon(
                  Icons.location_on_outlined,
                  color: AppColors.gold,
                  size: 18,
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    areaName,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w700,
                      fontSize: 15,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  '· ${compounds.length} Compounds',
                  style: const TextStyle(
                    color: AppColors.textMuted,
                    fontSize: 13,
                  ),
                ),
                const Spacer(),
                const Icon(
                  Icons.keyboard_arrow_up_rounded,
                  color: AppColors.textMuted,
                  size: 22,
                ),
              ],
            ),
          ),
          Expanded(
            child: compounds.isEmpty
                ? const Center(
                    child: Text(
                      AppStrings.noProperties,
                      style:
                          TextStyle(color: AppColors.textMuted, fontSize: 13),
                    ),
                  )
                : ListView.builder(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                    itemCount: compounds.length,
                    itemBuilder: (_, i) => RepaintBoundary(
                      child: _PropertyCard(
                        compound: compounds[i],
                        areaColorMap: areaColorMap,
                        onTap: () => onCardTap(compounds[i]),
                      ),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

// ── Property Card ──────────────────────────────────────────────

class _PropertyCard extends StatelessWidget {
  const _PropertyCard({
    required this.compound,
    required this.areaColorMap,
    required this.onTap,
  });

  final Compound compound;
  final Map<String, Color> areaColorMap;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final hasImage = compound.imageUrls.isNotEmpty;

    return TapScale(
      onTap: onTap,
      child: Container(
        width: 190,
        margin: const EdgeInsets.only(right: 12),
        decoration: BoxDecoration(
          color: AppColors.bg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: AppColors.border.withValues(alpha: 0.6),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.15),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Stack(
                fit: StackFit.expand,
                children: [
                  ClipRRect(
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(14),
                    ),
                    child: hasImage
                        ? AppCachedImage(
                            imageUrl: compound.imageUrls.first,
                            fit: BoxFit.cover,
                            memCacheWidth: 300,
                          )
                        : _placeholder(),
                  ),
                  Positioned(
                    bottom: 0,
                    left: 0,
                    right: 0,
                    height: 36,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            Colors.transparent,
                            Colors.black.withValues(alpha: 0.5),
                          ],
                        ),
                      ),
                    ),
                  ),
                  if (compound.location != null)
                    Positioned(
                      top: 8,
                      left: 8,
                      child: TagOverlay(
                        text: compound.location!,
                        color: areaColorMap[compound.location],
                      ),
                    ),
                  if (compound.developerName != null &&
                      compound.developerName!.isNotEmpty)
                    Positioned(
                      bottom: 6,
                      left: 8,
                      child: TagOverlay(
                        text: compound.developerName!.length > 14
                            ? compound.developerName!.substring(0, 14)
                            : compound.developerName!,
                        color: AppColors.darkGray,
                      ),
                    ),
                  Positioned(
                    top: 8,
                    right: 8,
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        MiniIcon(Icons.favorite_border_rounded),
                        const SizedBox(width: 4),
                        MiniIcon(Icons.ios_share_rounded),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    compound.name,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (compound.startPrice != null) ...[
                    const SizedBox(height: 3),
                    Text(
                      'EGP ${_fmtPrice(compound.startPrice!)}',
                      style: TextStyle(
                        color: AppColors.gold.withValues(alpha: 0.9),
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
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

  static String _fmtPrice(double p) {
    if (p >= 1000000) {
      return 'EGP ${(p / 1000000).toStringAsFixed(p % 1000000 == 0 ? 0 : 1)}M';
    }
    if (p >= 1000) return 'EGP ${(p / 1000).toStringAsFixed(0)}K';
    return 'EGP ${p.toStringAsFixed(0)}';
  }

  static Widget _placeholder() {
    return Container(
      color: AppColors.bg,
      child: Center(
        child: Icon(
          Icons.apartment_rounded,
          color: AppColors.gold.withValues(alpha: 0.15),
          size: 36,
        ),
      ),
    );
  }
}
