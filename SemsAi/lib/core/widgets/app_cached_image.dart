import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';

/// Shared cached image with shimmer placeholder and smooth fade-in.
class AppCachedImage extends StatelessWidget {
  final String? imageUrl;
  final double? width;
  final double? height;
  final BoxFit fit;
  final BorderRadius? borderRadius;
  final int? memCacheWidth;

  const AppCachedImage({
    super.key,
    this.imageUrl,
    this.width,
    this.height,
    this.fit = BoxFit.cover,
    this.borderRadius,
    this.memCacheWidth,
  });

  @override
  Widget build(BuildContext context) {
    if (imageUrl == null || imageUrl!.isEmpty) return _placeholder();

    final image = CachedNetworkImage(
      imageUrl: imageUrl ?? "No image for this unit",
      width: width,
      height: height,
      fit: fit,
      memCacheWidth: memCacheWidth ?? 400,
      fadeInDuration: Duration(milliseconds: 300),
      fadeOutDuration: Duration(milliseconds: 150),
      placeholder: (_, __) => _shimmerPlaceholder(),
      errorWidget: (_, __, ___) => _placeholder(),
    );

    if (borderRadius != null) {
      return ClipRRect(borderRadius: borderRadius!, child: image);
    }
    return image;
  }

  Widget _placeholder() {
    return Container(
      width: width,
      height: height,
      color: AppColors.buildingColor,
      child: Center(
        child: Icon(
          Icons.apartment_rounded,
          color: AppColors.gold.withValues(alpha: 0.15),
          size: 32,
        ),
      ),
    );
  }

  Widget _shimmerPlaceholder() {
    return _ShimmerRect(width: width, height: height);
  }
}

class _ShimmerRect extends StatefulWidget {
  final double? width;
  final double? height;
  const _ShimmerRect({this.width, this.height});

  @override
  State<_ShimmerRect> createState() => _ShimmerRectState();
}

class _ShimmerRectState extends State<_ShimmerRect>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: Duration(milliseconds: 1400),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment(-1.5 + 3.0 * _ctrl.value, 0),
              end: Alignment(-1.5 + 3.0 * _ctrl.value + 1.5, 0),
              colors: [
                AppColors.buildingColor,
                Color(0xFF182030),
                AppColors.buildingColor,
              ],
            ),
          ),
          child: Center(
            child: Icon(
              Icons.apartment_rounded,
              color: AppColors.gold.withValues(alpha: 0.8),
              size: 28,
            ),
          ),
        );
      },
    );
  }
}
