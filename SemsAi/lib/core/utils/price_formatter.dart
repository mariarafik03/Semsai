class PriceFormatter {
  PriceFormatter._();

  static String format(
    dynamic value, {
    String fallback = 'Contact for price',
    bool showCurrency = true,
  }) {
    if (value == null) return fallback;

    final double? parsed;
    if (value is num) {
      parsed = value.toDouble();
    } else {
      parsed = double.tryParse(value.toString());
    }

    if (parsed == null) return fallback;

    final suffix = showCurrency ? ' EGP' : '';

    if (parsed >= 1000000) {
      final v = parsed / 1000000;
      final text = v == v.roundToDouble()
          ? v.toStringAsFixed(0)
          : v.toStringAsFixed(1);
      return '$text\M$suffix';
    }
    if (parsed >= 1000) {
      return '${(parsed / 1000).toStringAsFixed(0)}K$suffix';
    }
    return '${parsed.toStringAsFixed(0)}$suffix';
  }
}
