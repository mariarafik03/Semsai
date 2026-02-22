import 'package:flutter/material.dart';

import 'package:SemsAi/core/constants/app_colors.dart';

class UnitImageGallery extends StatefulWidget {
  const UnitImageGallery({super.key, required this.images});

  final List<String> images;

  @override
  State<UnitImageGallery> createState() => _UnitImageGalleryState();
}

class _UnitImageGalleryState extends State<UnitImageGallery> {
  late final PageController _pageController;
  int _current = 0;

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final topPad = MediaQuery.of(context).padding.top;

    return SizedBox(
      height: 300 + topPad,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (widget.images.isNotEmpty)
            PageView.builder(
              controller: _pageController,
              itemCount: widget.images.length,
              onPageChanged: (i) => setState(() => _current = i),
              itemBuilder: (_, i) => Image.network(
                widget.images[i],
                fit: BoxFit.cover,
                loadingBuilder: (_, child, p) =>
                    p == null ? child : _placeholder(),
                errorBuilder: (_, __, ___) => _placeholder(),
              ),
            )
          else
            _placeholder(),
          // Top gradient
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            height: topPad + 60,
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Colors.black.withValues(alpha: 0.6),
                    Colors.transparent,
                  ],
                ),
              ),
            ),
          ),
          // Back button
          Positioned(
            top: topPad + 8,
            left: 16,
            child: GestureDetector(
              onTap: () => Navigator.pop(context),
              child: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppColors.bg.withValues(alpha: 0.7),
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: AppColors.border.withValues(alpha: 0.5),
                  ),
                ),
                child: const Icon(
                  Icons.arrow_back_rounded,
                  color: AppColors.textPrimary,
                  size: 20,
                ),
              ),
            ),
          ),
          // Page dots
          if (widget.images.length > 1)
            Positioned(
              bottom: 14,
              left: 0,
              right: 0,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                  widget.images.length > 5 ? 5 : widget.images.length,
                  (i) => AnimatedContainer(
                    duration: const Duration(milliseconds: 250),
                    margin: const EdgeInsets.symmetric(horizontal: 3),
                    width: _current == i ? 20 : 8,
                    height: 8,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(4),
                      color: _current == i
                          ? AppColors.gold
                          : Colors.white.withValues(alpha: 0.4),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _placeholder() {
    return Container(
      color: AppColors.cardBg,
      child: Center(
        child: Icon(
          Icons.apartment_rounded,
          color: AppColors.gold.withValues(alpha: 0.15),
          size: 64,
        ),
      ),
    );
  }
}
