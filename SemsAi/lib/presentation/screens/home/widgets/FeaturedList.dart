import 'package:flutter/material.dart';
import 'package:SemsAi/core/colors.dart';

class Featuredlist extends StatefulWidget {
  final String selectedCategory;

  const Featuredlist({required this.selectedCategory, super.key});

  @override
  State<Featuredlist> createState() => _FeaturedlistState();
}

class _FeaturedlistState extends State<Featuredlist> {
  List<Map<String, dynamic>> properties = [
    {
      'title': 'villa-bo-islands',
      'location': 'North Coast, Egypt',
      'price': '30M EGP',
      'rating': '4.5',
      'image':
          'assets/images/type--villa-type-2--bo-islands-north-coast-maximjpeg-1200x900.jpg',
      'tag': 'Villa',
      'isFav': false,
    },
    {
      'title': 'residence-eight-new-capital-sky',
      'location': 'New Capital, Egypt',
      'price': '15M EGP',
      'rating': '4.2',
      'image':
          'assets/images/exterior--residence-eight-new-capital-sky-ad-10jpeg-1200x900.jpg',
      'tag': 'Residence',
      'isFav': false,
    },
    {
      'title': 'apartment-cairo-alex-desert-rd-mountain-view',
      'location': 'New Giza, Egypt',
      'price': '10M EGP',
      'rating': '4.0',
      'image':
          'assets/images/mv-giza-plateau-gpl-cairo-alex-desert-rd-mountain-view-4jpg-1200x900.jpg',
      'tag': 'Apartment',
      'isFav': false,
    },
  ];

  @override
  Widget build(BuildContext context) {
    final filtered = widget.selectedCategory == "All"
        ? properties
        : properties
              .where(
                (p) =>
                    p['tag'].toLowerCase() ==
                    widget.selectedCategory.toLowerCase(),
              )
              .toList();
    return SizedBox(
      height: 380,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: filtered.length,
        itemBuilder: (context, index) {
          return _buildPropertyCard(filtered[index]);
        },
      ),
    );
  }

  Widget _buildPropertyCard(Map<String, dynamic> prop) {
    return GestureDetector(
      onTap: () {
        // will navigate to details page
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 260,
        margin: const EdgeInsets.only(right: 16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(22),
          boxShadow: [
            BoxShadow(
              color: Colors.grey.withOpacity(0.25),
              blurRadius: 10,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(22),
              ),
              child: Image.asset(
                prop['image'],
                height: 150,
                width: double.infinity,
                fit: BoxFit.cover,
              ),
            ),

            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Chip(
                        label: Text(
                          prop['tag'],
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        backgroundColor: myColors.orangeColor.withOpacity(0.9),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                      ),
                      GestureDetector(
                        onTap: () {
                          setState(() {
                            prop['isFav'] = !(prop['isFav'] ?? false);
                          });
                        },
                        child: Icon(
                          prop['isFav']
                              ? Icons.favorite
                              : Icons.favorite_border,
                          color: prop['isFav']
                              ? Colors.red
                              : myColors.orangeColor,
                          size: 26,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 15),

                  Text(
                    prop['title'].replaceAll('-', ' ').toUpperCase(),
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),

                  const SizedBox(height: 10),

                  Row(
                    children: [
                      const Icon(Icons.star, color: Colors.amber, size: 16),
                      const SizedBox(width: 4),
                      Text(
                        prop['rating'],
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(width: 66),
                      const Icon(
                        Icons.location_on,
                        color: Colors.grey,
                        size: 16,
                      ),
                      Expanded(
                        child: Text(
                          prop['location'],
                          style: TextStyle(
                            color: myColors.textGreyDark,
                            fontSize: 12,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 30),

                  Text(
                    prop['price'],
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 22,
                      color: Colors.black,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
