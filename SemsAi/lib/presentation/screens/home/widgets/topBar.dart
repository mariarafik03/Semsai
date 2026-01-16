import 'package:flutter/material.dart';
import 'package:SemsAi/core/colors.dart';
import 'package:SemsAi/presentation/screens/home/widgets/LocationOptionsSheet.dart';

class Topbar extends StatelessWidget {
  const Topbar({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        InkWell(
          onTap: () {
            showModalBottomSheet(
              context: context,
              backgroundColor: Colors.transparent,
              shape: const RoundedRectangleBorder(
                borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
              ),
              builder: (context) {
                return LocationOptionsSheet();
              },
            );
          },
          borderRadius: BorderRadius.circular(20),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: myColors.lightgrayColor),
            ),
            child: Row(
              children: [
                Icon(Icons.location_on, color: myColors.orangeColor, size: 20),
                const SizedBox(width: 6),
                const Text(
                  'North Coast, Egypt',
                  style: TextStyle(color: Colors.black),
                ),
                const Icon(Icons.keyboard_arrow_down, color: Colors.grey),
              ],
            ),
          ),
        ),
        Spacer(),
      ],
    );
  }
}
