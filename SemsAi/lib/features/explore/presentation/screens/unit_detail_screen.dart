import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/features/explore/data/models/compound_unit_model.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/unit_image_gallery.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/unit_payment_plans.dart';
import 'package:SemsAi/features/explore/presentation/screens/widgets/unit_detail_info.dart';
import 'package:SemsAi/features/listings/presentation/screens/developer_profile_screen.dart';

class UnitDetailScreen extends StatelessWidget {
  final CompoundUnit unit;

  const UnitDetailScreen({super.key, required this.unit});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(child: UnitImageGallery(images: unit.images)),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  UnitTitleRow(unit: unit),
                  const SizedBox(height: 16),
                  UnitPriceSection(
                    price: unit.displayPrice,
                    rangeText: unit.priceRangeText,
                  ),
                  const SizedBox(height: 20),
                  UnitSpecsRow(unit: unit),
                  const SizedBox(height: 20),

                  if (unit.developerName != null &&
                      unit.developerName!.isNotEmpty)
                    GestureDetector(
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => DeveloperProfileScreen(
                            developerName: unit.developerName!,
                          ),
                        ),
                      ),
                      child: UnitInfoCard(
                        icon: Icons.business_rounded,
                        label: AppStrings.developer,
                        value: unit.developerName!,
                        trailing: const Icon(
                          Icons.arrow_forward_ios_rounded,
                          color: AppColors.gold,
                          size: 14,
                        ),
                      ),
                    ),

                  if (unit.paymentPlans.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    UnitPaymentPlans(plans: unit.paymentPlans),
                  ],

                  if (unit.deliveryYear != null) ...[
                    const SizedBox(height: 12),
                    UnitInfoCard(
                      icon: Icons.calendar_today_rounded,
                      label: AppStrings.expectedDelivery,
                      value: int.tryParse(unit.deliveryYear!) != null
                          ? '${unit.deliveryYear}'
                          : unit.deliveryYear!,
                    ),
                  ],

                  if (unit.finishing != null || unit.saleType != null) ...[
                    const SizedBox(height: 12),
                    UnitExtraDetails(
                      finishing: unit.finishing,
                      saleType: unit.saleType,
                    ),
                  ],

                  if (unit.description != null &&
                      unit.description!.trim().isNotEmpty) ...[
                    const SizedBox(height: 24),
                    const Text(
                      AppStrings.about,
                      style: TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      unit.description!,
                      style: const TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 14,
                        height: 1.6,
                      ),
                    ),
                  ],

                  const SizedBox(height: 40),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}