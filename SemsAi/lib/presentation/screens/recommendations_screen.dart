import 'package:flutter/material.dart';
import 'package:SemsAi/data/services/conversation_service.dart';

class RecommendationsScreen extends StatefulWidget {
  final Map<String, dynamic> finalState;

  const RecommendationsScreen({super.key, required this.finalState});

  @override
  State<RecommendationsScreen> createState() => _RecommendationsScreenState();
}

class _RecommendationsScreenState extends State<RecommendationsScreen> {
  late Future<List<dynamic>> _recommendationsFuture;

  @override
  void initState() {
    super.initState();
    _recommendationsFuture = ConversationService.getRecommendations(
      widget.finalState,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Recommendations')),
      body: FutureBuilder<List<dynamic>>(
        future: _recommendationsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          }

          final items = snapshot.data ?? [];
          if (items.isEmpty) {
            return const Center(
              child: Text('No recommendations found matching your criteria.'),
            );
          }

          return ListView.builder(
            itemCount: items.length,
            itemBuilder: (context, index) {
              final item = items[index];
              final unit = item['unit'] ?? {};
              final compound = item['compound'] ?? {};
              final developer = item['developer'] ?? {};
              final payment = item['payment'] ?? {};

              return Card(
                margin: const EdgeInsets.all(8.0),
                child: ListTile(
                  title: Text(
                    '${unit['type'] ?? 'Unit'} in ${compound['name'] ?? 'Unknown Compound'}',
                  ),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Location: ${compound['location'] ?? 'Unknown'}'),
                      Text('Developer: ${developer['dev_name'] ?? 'Unknown'}'),
                      const SizedBox(height: 4),
                      Text(
                        'Price: ${payment['down_payment'] != null ? "${payment['down_payment']} EGP" : "Contact for price"}',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                      if (payment['year_installment'] != null ||
                          payment['monthly_installment'] != null)
                        Text(
                          'Monthly: ${payment['monthly_installment']} / ${payment['year_installment']} Years',
                        ),
                    ],
                  ),
                  isThreeLine: true,
                ),
              );
            },
          );
        },
      ),
    );
  }
}
