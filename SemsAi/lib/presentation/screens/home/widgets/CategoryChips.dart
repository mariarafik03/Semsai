import 'package:flutter/material.dart';
import 'package:SemsAi/core/colors.dart';

class Categorychips extends StatefulWidget {
  final Function(String) onCategorySelected;

  const Categorychips({required this.onCategorySelected, super.key});

  @override
  State<Categorychips> createState() => _CategorychipsState();
}

class _CategorychipsState extends State<Categorychips> {
  int _selectedCategory = 0;

  @override
  Widget build(BuildContext context) {
    List<String> categories = [
      'All',
      'House',
      'Chalet',
      'Apartment',
      'Villa',
      'Residence',
    ];

    return SizedBox(
      height: 50,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: categories.length,
        itemBuilder: (context, index) {
          bool isSelected = (index == _selectedCategory);
          return Padding(
            padding: const EdgeInsets.only(right: 10),
            child: ActionChip(
              label: Text(categories[index]),
              labelStyle: TextStyle(
                color: isSelected ? Colors.white : myColors.textGreyDark,
                fontWeight: FontWeight.bold,
              ),
              backgroundColor: isSelected
                  ? myColors.orangeColor
                  : myColors.lightgrayColor,
              onPressed: () {
                setState(() {
                  _selectedCategory = index;
                });
                widget.onCategorySelected(categories[index]);
              },
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
                side: BorderSide.none,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
            ),
          );
        },
      ),
    );
  }
}
