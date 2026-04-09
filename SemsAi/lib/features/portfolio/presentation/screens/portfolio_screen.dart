import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/networking/api_client.dart';
import 'package:SemsAi/features/portfolio/presentation/screens/portfolio_summary_screen.dart';

class PortfolioScreen extends StatefulWidget {
  const PortfolioScreen({super.key});

  @override
  State<PortfolioScreen> createState() => _PortfolioScreenState();
}

class _PortfolioScreenState extends State<PortfolioScreen> {
  final _formKey = GlobalKey<FormState>();

  final _incomeController = TextEditingController();
  final _expensesController = TextEditingController();
  final _cashController = TextEditingController();
  final _ratioController = TextEditingController(text: '0.4');

  String _incomeType = 'salary';
  String _riskProfile = 'moderate';
  bool _creditAccess = false;
  bool _isLoading = false;
  String? _error;

  final List<_UnitInput> _units = [const _UnitInput()];

  @override
  void dispose() {
    _incomeController.dispose();
    _expensesController.dispose();
    _cashController.dispose();
    _ratioController.dispose();
    super.dispose();
  }

  Future<void> _analyze() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final payload = {
      'netMonthlyIncome': double.parse(_incomeController.text.trim()),
      'incomeType': _incomeType,
      'monthlyFixedExpenses': double.parse(_expensesController.text.trim()),
      'availableCash': double.parse(_cashController.text.trim()),
      'creditAccess': _creditAccess,
      'riskProfile': _riskProfile,
      'maxInstallmentRatio': double.parse(_ratioController.text.trim()),
      'units': _units
          .map(
            (u) => {
              'monthlyInstallment': u.installment,
              'remainingBalance': u.remainingBalance,
              'marketValue': u.marketValue,
            },
          )
          .toList(),
    };

    try {
      final res = await ApiClient.post('/portfolio/analyze', payload);
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      if (res.statusCode >= 200 && res.statusCode < 300) {
        if (!mounted) return;
        final unitsPayload = _units
            .map(
              (u) => {
                'monthlyInstallment': u.installment,
                'remainingBalance': u.remainingBalance,
                'marketValue': u.marketValue,
              },
            )
            .toList();

        await Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) =>
                PortfolioSummaryScreen(result: body, units: unitsPayload),
          ),
        );
      } else {
        setState(() => _error = body['error']?.toString() ?? 'Request failed');
      }
    } catch (e) {
      setState(() => _error = 'Network error: $e');
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  void _addUnit() => setState(() => _units.add(const _UnitInput()));

  void _removeUnit(int index) {
    if (_units.length == 1) return;
    setState(() => _units.removeAt(index));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        backgroundColor: AppColors.cardBg,
        title: const Text(
          'Portfolio',
          style: TextStyle(color: AppColors.textPrimary),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _SectionCard(
            title: 'Investor Profile',
            child: Form(
              key: _formKey,
              child: Column(
                children: [
                  _NumberField(
                    controller: _incomeController,
                    label: 'Net Monthly Income',
                  ),
                  const SizedBox(height: 10),
                  _NumberField(
                    controller: _expensesController,
                    label: 'Monthly Fixed Expenses',
                  ),
                  const SizedBox(height: 10),
                  _NumberField(
                    controller: _cashController,
                    label: 'Available Cash',
                  ),
                  const SizedBox(height: 10),
                  _NumberField(
                    controller: _ratioController,
                    label: 'Max Installment Ratio (0-1)',
                  ),
                  const SizedBox(height: 10),
                  _DropdownField<String>(
                    value: _incomeType,
                    label: 'Income Type',
                    items: const ['salary', 'freelance'],
                    onChanged: (v) => setState(() => _incomeType = v),
                  ),
                  const SizedBox(height: 10),
                  _DropdownField<String>(
                    value: _riskProfile,
                    label: 'Risk Profile',
                    items: const ['conservative', 'moderate', 'aggressive'],
                    onChanged: (v) => setState(() => _riskProfile = v),
                  ),
                  const SizedBox(height: 10),
                  SwitchListTile(
                    value: _creditAccess,
                    onChanged: (v) => setState(() => _creditAccess = v),
                    title: const Text(
                      'Credit Access',
                      style: TextStyle(color: AppColors.textPrimary),
                    ),
                    activeColor: AppColors.gold,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          _SectionCard(
            title: 'Units',
            child: Column(
              children: [
                for (int i = 0; i < _units.length; i++) ...[
                  _UnitCard(
                    index: i + 1,
                    onChanged: (u) => _units[i] = u,
                    onRemove: () => _removeUnit(i),
                    canRemove: _units.length > 1,
                  ),
                  const SizedBox(height: 10),
                ],
                OutlinedButton.icon(
                  onPressed: _addUnit,
                  icon: const Icon(Icons.add, color: AppColors.gold),
                  label: const Text(
                    'Add Unit',
                    style: TextStyle(color: AppColors.gold),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 48,
            child: ElevatedButton(
              onPressed: _isLoading ? null : _analyze,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.gold,
                foregroundColor: AppColors.bg,
              ),
              child: _isLoading
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Analyze Portfolio'),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Colors.redAccent)),
          ],
        ],
      ),
    );
  }
}

class _UnitCard extends StatefulWidget {
  final int index;
  final bool canRemove;
  final VoidCallback onRemove;
  final ValueChanged<_UnitInput> onChanged;

  const _UnitCard({
    required this.index,
    required this.canRemove,
    required this.onRemove,
    required this.onChanged,
  });

  @override
  State<_UnitCard> createState() => _UnitCardState();
}

class _UnitCardState extends State<_UnitCard> {
  final _installment = TextEditingController();
  final _balance = TextEditingController();
  final _market = TextEditingController();

  @override
  void dispose() {
    _installment.dispose();
    _balance.dispose();
    _market.dispose();
    super.dispose();
  }

  void _emit() {
    widget.onChanged(
      _UnitInput(
        installment: double.tryParse(_installment.text.trim()) ?? 0,
        remainingBalance: double.tryParse(_balance.text.trim()) ?? 0,
        marketValue: double.tryParse(_market.text.trim()) ?? 0,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.bg.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'Unit ${widget.index}',
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              if (widget.canRemove)
                IconButton(
                  onPressed: widget.onRemove,
                  icon: const Icon(
                    Icons.delete_outline,
                    color: Colors.redAccent,
                  ),
                ),
            ],
          ),
          _NumberField(
            controller: _installment,
            label: 'Monthly Installment',
            onChanged: (_) => _emit(),
          ),
          const SizedBox(height: 8),
          _NumberField(
            controller: _balance,
            label: 'Remaining Balance',
            onChanged: (_) => _emit(),
          ),
          const SizedBox(height: 8),
          _NumberField(
            controller: _market,
            label: 'Market Value',
            onChanged: (_) => _emit(),
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  final String title;
  final Widget child;
  const _SectionCard({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: AppColors.goldLight,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          child,
        ],
      ),
    );
  }
}

class _NumberField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final ValueChanged<String>? onChanged;
  const _NumberField({
    required this.controller,
    required this.label,
    this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      onChanged: onChanged,
      validator: (v) {
        final text = (v ?? '').trim();
        if (text.isEmpty) return 'Required';
        final n = double.tryParse(text);
        if (n == null) return 'Invalid number';
        if (n < 0) return 'Must be >= 0';
        return null;
      },
      style: const TextStyle(color: AppColors.textPrimary),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: AppColors.textMuted),
        filled: true,
        fillColor: AppColors.bg.withValues(alpha: 0.25),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.border),
        ),
      ),
    );
  }
}

class _DropdownField<T> extends StatelessWidget {
  final T value;
  final String label;
  final List<T> items;
  final ValueChanged<T> onChanged;

  const _DropdownField({
    required this.value,
    required this.label,
    required this.items,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<T>(
      value: value,
      items: items
          .map((item) => DropdownMenuItem<T>(value: item, child: Text('$item')))
          .toList(),
      onChanged: (v) {
        if (v != null) onChanged(v);
      },
      dropdownColor: AppColors.cardBg,
      style: const TextStyle(color: AppColors.textPrimary),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: AppColors.textMuted),
        filled: true,
        fillColor: AppColors.bg.withValues(alpha: 0.25),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.border),
        ),
      ),
    );
  }
}

class _UnitInput {
  final double installment;
  final double remainingBalance;
  final double marketValue;

  const _UnitInput({
    this.installment = 0,
    this.remainingBalance = 0,
    this.marketValue = 0,
  });
}
