import 'package:flutter/material.dart';

class Bromobanners extends StatefulWidget {
  const Bromobanners({super.key});

  @override
  State<Bromobanners> createState() => _BromobannersState();
}

class _BromobannersState extends State<Bromobanners> {
  @override
  Widget build(BuildContext context) {
    List<Map<String, String>> promos = [
      {
        'title': 'Summer Sale',
        'subtitle': 'Up to 30% off on selected stays',
        'image': 'assets/images/exterior_residence_sky_ad_4.jpg',
      },
      {
        'title': 'Family Getaways',
        'subtitle': 'Special offers for family stays',
        'image': 'assets/images/dianella_villa_v4_bo_islands.jpg',
      },
      {
        'title': 'Last Minute Deals',
        'subtitle': 'Book now and save big',
        'image': 'assets/images/ras_el_hekma_il_cazar.jpg',
      },
    ];
    return Container(
      height: 180,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        physics: AlwaysScrollableScrollPhysics(),
        itemCount: promos.length,
        itemBuilder: (context, index) {
          return Container(
            width: 300,
            margin: EdgeInsets.only(right: 16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              image: DecorationImage(
                image: AssetImage(promos[index]['image']!),
                fit: BoxFit.cover,
                colorFilter: ColorFilter.mode(
                  Colors.black.withOpacity(0.3),
                  BlendMode.darken,
                ),
              ),
            ),
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(
                    promos[index]['title']!,
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    promos[index]['subtitle']!,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.9),
                      fontSize: 16,
                    ),
                  ),
                  SizedBox(height: 10),
                  Container(
                    padding: EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.3),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: InkWell(
                      child: Icon(Icons.arrow_forward, color: Colors.white),
                      onTap: () {},
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
