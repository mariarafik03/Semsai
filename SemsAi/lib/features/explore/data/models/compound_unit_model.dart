import 'package:equatable/equatable.dart';

/// A single payment plan attached to a unit
class PaymentPlan {
  final String? frequency;
  final int? years;
  final double? downPayment;
  final double? installmentAmount;
  final double? unitPrice;
  final String? currency;
  final bool isCash;

  const PaymentPlan({
    this.frequency,
    this.years,
    this.downPayment,
    this.installmentAmount,
    this.unitPrice,
    this.currency,
    this.isCash = false,
  });

  factory PaymentPlan.fromJson(Map<String, dynamic> json) {
    double? _d(dynamic v) {
      if (v == null) return null;
      if (v is num) return v.toDouble();
      if (v is String) return double.tryParse(v);
      return null;
    }

    int? _i(dynamic v) {
      if (v == null) return null;
      if (v is int) return v;
      if (v is num) return v.toInt();
      if (v is String) return int.tryParse(v);
      return null;
    }

    return PaymentPlan(
      frequency: json['frequency']?.toString(),
      years: _i(json['years']),
      downPayment: _d(json['down_payment']),
      installmentAmount: _d(json['single_installment_amount']),
      unitPrice: _d(json['unit_price']),
      currency: json['currency']?.toString(),
      isCash: json['is_cash'] == true,
    );
  }

  /// Down-payment as a percentage of unit price
  double? get downPaymentPercent {
    if (downPayment != null && unitPrice != null && unitPrice! > 0) {
      return (downPayment! / unitPrice!) * 100;
    }
    return null;
  }
}

class CompoundUnit extends Equatable {
  final String id;
  final String name;
  final String type;
  final double? price;
  final double? priceMin;
  final double? priceMax;
  final double? area;
  final double? areaMin;
  final double? areaMax;
  final int? bedrooms;
  final int? bathrooms;
  final String? finishing;
  final String? saleType;
  final String? deliveryYear;
  final String? compoundName;
  final String? developerName;
  final String? location;
  final String? description;
  final List<String> images;
  final List<PaymentPlan> paymentPlans;

  const CompoundUnit({
    required this.id,
    required this.name,
    required this.type,
    this.price,
    this.priceMin,
    this.priceMax,
    this.area,
    this.areaMin,
    this.areaMax,
    this.bedrooms,
    this.bathrooms,
    this.finishing,
    this.saleType,
    this.deliveryYear,
    this.compoundName,
    this.developerName,
    this.location,
    this.description,
    this.images = const [],
    this.paymentPlans = const [],
  });

  factory CompoundUnit.fromJson(Map<String, dynamic> json) {
    final plans = <PaymentPlan>[];
    if (json['payment_plans'] is List) {
      for (final p in json['payment_plans']) {
        if (p is Map<String, dynamic>) plans.add(PaymentPlan.fromJson(p));
      }
    }

    return CompoundUnit(
      id: json['_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      type: (json['property_type'] ?? json['unit_type'] ?? json['type'] ?? '')
          .toString(),
      price: _toDouble(json['price']),
      priceMin: _toDouble(json['price_min']),
      priceMax: _toDouble(json['price_max']),
      area: _toDouble(json['area']),
      areaMin: _toDouble(json['area_min']),
      areaMax: _toDouble(json['area_max']),
      bedrooms: _toInt(json['bedrooms']),
      bathrooms: _toInt(json['bathrooms']),
      finishing: json['finishing']?.toString(),
      saleType: json['sale_type']?.toString(),
      deliveryYear: json['delivery_year']?.toString(),
      compoundName: json['compound_name']?.toString(),
      developerName: json['developer_name']?.toString(),
      location: json['location']?.toString(),
      description: json['description']?.toString(),
      images:
          (json['images'] as List?)?.map((e) => e.toString()).toList() ??
          const [],
      paymentPlans: plans,
    );
  }

  static double? _toDouble(dynamic v) {
    if (v == null) return null;
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v);
    return null;
  }

  static int? _toInt(dynamic v) {
    if (v == null) return null;
    if (v is int) return v;
    if (v is num) return v.toInt();
    if (v is String) return int.tryParse(v);
    return null;
  }

  /// Best price: price > priceMin > priceMax
  double? get displayPrice => price ?? priceMin;

  /// Price range text
  String? get priceRangeText {
    if (priceMin != null && priceMax != null && priceMin != priceMax) {
      return 'Up to ${_short(priceMax!)} EGP';
    }
    return null;
  }

  /// Best area: area > areaMin
  double? get displayArea => area ?? areaMin;

  /// First non-cash payment plan
  PaymentPlan? get bestPlan {
    if (paymentPlans.isEmpty) return null;
    final nonCash = paymentPlans.where((p) => !p.isCash).toList();
    return nonCash.isNotEmpty ? nonCash.first : paymentPlans.first;
  }

  static String _short(double p) {
    if (p >= 1000000) {
      final v = p / 1000000;
      return '${v.toStringAsFixed(v == v.roundToDouble() ? 0 : 1)}M';
    }
    if (p >= 1000) return '${(p / 1000).toStringAsFixed(0)}K';
    return p.toStringAsFixed(0);
  }

  @override
  List<Object?> get props => [id, name, type];
}
