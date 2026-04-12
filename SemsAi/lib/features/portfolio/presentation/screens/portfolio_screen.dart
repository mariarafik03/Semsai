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

class _PortfolioScreenState extends State<PortfolioScreen>
    with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  late final AnimationController _fadeCtrl;

  final _incomeController = TextEditingController();
  final _expensesController = TextEditingController();
  final _cashController = TextEditingController();
  final _ratioController = TextEditingController(text: '0.5');

  String _incomeType = 'salary';
  String _riskProfile = 'moderate';
  bool _creditAccess = false;
  bool _isLoading = false;
  String? _error;

  final List<_UnitInput> _units = [const _UnitInput()];

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..forward();
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
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
      backgroundColor: const Color(0xFF020617),
      body: SafeArea(
        child: FadeTransition(
          opacity: _fadeCtrl,
          child: Column(
            children: [
              _buildHeader(),
              Expanded(
                child: Form(
                  key: _formKey,
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                    children: [
                      const SizedBox(height: 8),
                      // ── Investor Profile Section
                      _buildSectionCard(
                        icon: Icons.person_outline_rounded,
                        title: 'Investor Profile',
                        subtitle: 'Your financial overview',
                        children: [
                          _buildTextField(
                            controller: _incomeController,
                            label: 'Net Monthly Income',
                            prefix: 'EGP',
                            icon: Icons.account_balance_wallet_outlined,
                          ),
                          const SizedBox(height: 14),
                          _buildTextField(
                            controller: _expensesController,
                            label: 'Monthly Fixed Expenses',
                            prefix: 'EGP',
                            icon: Icons.receipt_long_outlined,
                          ),
                          const SizedBox(height: 14),
                          _buildTextField(
                            controller: _cashController,
                            label: 'Available Cash',
                            prefix: 'EGP',
                            icon: Icons.savings_outlined,
                          ),
                          const SizedBox(height: 14),
                          _buildTextField(
                            controller: _ratioController,
                            label: 'Max Installment Ratio (0-1)',
                            icon: Icons.tune_rounded,
                          ),
                        ],
                      ),

                      const SizedBox(height: 16),

                      // ── Preferences Section
                      _buildSectionCard(
                        icon: Icons.tune_rounded,
                        title: 'Preferences',
                        subtitle: 'Risk and income settings',
                        children: [
                          _buildDropdown(
                            value: _incomeType,
                            label: 'Income Type',
                            icon: Icons.work_outline_rounded,
                            items: const ['salary', 'freelance'],
                            onChanged: (v) => setState(() => _incomeType = v),
                          ),
                          const SizedBox(height: 14),
                          _buildDropdown(
                            value: _riskProfile,
                            label: 'Risk Profile',
                            icon: Icons.shield_outlined,
                            items: const [
                              'conservative',
                              'moderate',
                              'aggressive',
                            ],
                            onChanged: (v) => setState(() => _riskProfile = v),
                          ),
                          const SizedBox(height: 14),
                          _buildToggle(
                            label: 'Credit Access',
                            subtitle: 'Do you have access to bank credit?',
                            value: _creditAccess,
                            onChanged: (v) => setState(() => _creditAccess = v),
                          ),
                        ],
                      ),

                      const SizedBox(height: 16),

                      // ── Units Section
                      _buildSectionCard(
                        icon: Icons.apartment_rounded,
                        title: 'Your Units',
                        subtitle:
                            '${_units.length} unit${_units.length > 1 ? "s" : ""} added',
                        children: [
                          for (int i = 0; i < _units.length; i++) ...[
                            _UnitCardWidget(
                              index: i + 1,
                              onChanged: (u) => _units[i] = u,
                              onRemove: () => _removeUnit(i),
                              canRemove: _units.length > 1,
                            ),
                            if (i < _units.length - 1)
                              const SizedBox(height: 12),
                          ],
                          const SizedBox(height: 14),
                          _buildAddUnitButton(),
                        ],
                      ),

                      const SizedBox(height: 24),

                      // ── Error
                      if (_error != null) ...[
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: const Color(
                              0xFF7F1D1D,
                            ).withValues(alpha: 0.3),
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(
                              color: const Color(
                                0xFFEF4444,
                              ).withValues(alpha: 0.4),
                            ),
                          ),
                          child: Row(
                            children: [
                              const Icon(
                                Icons.error_outline,
                                color: Color(0xFFEF4444),
                                size: 18,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  _error!,
                                  style: const TextStyle(
                                    color: Color(0xFFEF4444),
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],

                      // ── Analyze Button
                      _buildAnalyzeButton(),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Header ────────────────────────────────────────────
  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 14),
      decoration: const BoxDecoration(
        color: Color(0xFF0F172A),
        border: Border(
          bottom: BorderSide(color: Color(0xFF1E293B), width: 0.5),
        ),
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF1E293B),
                border: Border.all(color: const Color(0xFF334155)),
              ),
              child: const Icon(
                Icons.arrow_back_ios_new,
                color: Color(0xFFE2E8F0),
                size: 16,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: [AppColors.gold, AppColors.gold.withValues(alpha: 0.6)],
              ),
            ),
            child: const Icon(
              Icons.analytics_rounded,
              color: Colors.white,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Portfolio Analysis',
                  style: TextStyle(
                    color: Color(0xFFE2E8F0),
                    fontSize: 17,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  'Enter your financial details',
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ─── Section Card ──────────────────────────────────────
  Widget _buildSectionCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required List<Widget> children,
  }) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(8),
                  color: AppColors.gold.withValues(alpha: 0.12),
                ),
                child: Icon(icon, color: AppColors.gold, size: 18),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Color(0xFFE2E8F0),
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      color: Color(0xFF64748B),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 18),
          ...children,
        ],
      ),
    );
  }

  // ─── Text Field ────────────────────────────────────────
  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    String? prefix,
    IconData? icon,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      validator: (v) {
        final text = (v ?? '').trim();
        if (text.isEmpty) return 'Required';
        final n = double.tryParse(text);
        if (n == null) return 'Invalid number';
        if (n < 0) return 'Must be >= 0';
        return null;
      },
      style: const TextStyle(color: Color(0xFFE2E8F0), fontSize: 14),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Color(0xFF64748B), fontSize: 13),
        prefixIcon: icon != null
            ? Icon(icon, color: const Color(0xFF475569), size: 20)
            : null,
        suffixText: prefix,
        suffixStyle: TextStyle(
          color: AppColors.gold.withValues(alpha: 0.7),
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
        filled: true,
        fillColor: const Color(0xFF020617),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 14,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFF334155)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFF334155)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: AppColors.gold.withValues(alpha: 0.6)),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFFEF4444)),
        ),
      ),
    );
  }

  // ─── Dropdown ──────────────────────────────────────────
  Widget _buildDropdown({
    required String value,
    required String label,
    required IconData icon,
    required List<String> items,
    required ValueChanged<String> onChanged,
  }) {
    return DropdownButtonFormField<String>(
      value: value,
      items: items.map((item) {
        return DropdownMenuItem<String>(
          value: item,
          child: Text(
            item[0].toUpperCase() + item.substring(1),
            style: const TextStyle(color: Color(0xFFE2E8F0), fontSize: 14),
          ),
        );
      }).toList(),
      onChanged: (v) {
        if (v != null) onChanged(v);
      },
      dropdownColor: const Color(0xFF1E293B),
      icon: Icon(
        Icons.keyboard_arrow_down_rounded,
        color: const Color(0xFF64748B),
      ),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Color(0xFF64748B), fontSize: 13),
        prefixIcon: Icon(icon, color: const Color(0xFF475569), size: 20),
        filled: true,
        fillColor: const Color(0xFF020617),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 14,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFF334155)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFF334155)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: AppColors.gold.withValues(alpha: 0.6)),
        ),
      ),
    );
  }

  // ─── Toggle ────────────────────────────────────────────
  Widget _buildToggle({
    required String label,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF020617),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF334155)),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.credit_card_rounded,
            color: Color(0xFF475569),
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    color: Color(0xFFE2E8F0),
                    fontSize: 14,
                  ),
                ),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: Color(0xFF64748B),
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: AppColors.gold,
            activeTrackColor: AppColors.gold.withValues(alpha: 0.3),
            inactiveThumbColor: const Color(0xFF475569),
            inactiveTrackColor: const Color(0xFF1E293B),
          ),
        ],
      ),
    );
  }

  // ─── Add Unit Button ───────────────────────────────────
  Widget _buildAddUnitButton() {
    return GestureDetector(
      onTap: _addUnit,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: AppColors.gold.withValues(alpha: 0.3),
            style: BorderStyle.solid,
          ),
          color: AppColors.gold.withValues(alpha: 0.05),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.add_circle_outline_rounded,
              color: AppColors.gold,
              size: 18,
            ),
            const SizedBox(width: 8),
            Text(
              'Add Another Unit',
              style: TextStyle(
                color: AppColors.gold,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Analyze Button ────────────────────────────────────
  Widget _buildAnalyzeButton() {
    return GestureDetector(
      onTap: _isLoading ? null : _analyze,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        height: 52,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          gradient: LinearGradient(
            colors: _isLoading
                ? [
                    AppColors.gold.withValues(alpha: 0.4),
                    AppColors.gold.withValues(alpha: 0.2),
                  ]
                : [AppColors.gold, AppColors.gold.withValues(alpha: 0.8)],
          ),
          boxShadow: _isLoading
              ? []
              : [
                  BoxShadow(
                    color: AppColors.gold.withValues(alpha: 0.25),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
        ),
        child: Center(
          child: _isLoading
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.analytics_rounded,
                      color: Color(0xFF020617),
                      size: 20,
                    ),
                    SizedBox(width: 8),
                    Text(
                      'Analyze Portfolio',
                      style: TextStyle(
                        color: Color(0xFF020617),
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}

// ─── Unit Card Widget ──────────────────────────────────────
class _UnitCardWidget extends StatefulWidget {
  final int index;
  final bool canRemove;
  final VoidCallback onRemove;
  final ValueChanged<_UnitInput> onChanged;

  const _UnitCardWidget({
    required this.index,
    required this.canRemove,
    required this.onRemove,
    required this.onChanged,
  });

  @override
  State<_UnitCardWidget> createState() => _UnitCardWidgetState();
}

class _UnitCardWidgetState extends State<_UnitCardWidget> {
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

  InputDecoration _inputDeco(String label, IconData icon) {
    return InputDecoration(
      labelText: label,
      labelStyle: const TextStyle(color: Color(0xFF64748B), fontSize: 12),
      prefixIcon: Icon(icon, color: const Color(0xFF475569), size: 18),
      suffixText: 'EGP',
      suffixStyle: TextStyle(
        color: AppColors.gold.withValues(alpha: 0.6),
        fontSize: 11,
        fontWeight: FontWeight.w600,
      ),
      filled: true,
      fillColor: const Color(0xFF020617),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFF334155)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFF334155)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: AppColors.gold.withValues(alpha: 0.6)),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFFEF4444)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF020617).withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(6),
                  color: AppColors.gold.withValues(alpha: 0.12),
                ),
                child: Center(
                  child: Text(
                    '${widget.index}',
                    style: TextStyle(
                      color: AppColors.gold,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                'Unit ${widget.index}',
                style: const TextStyle(
                  color: Color(0xFFE2E8F0),
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              if (widget.canRemove)
                GestureDetector(
                  onTap: widget.onRemove,
                  child: Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(6),
                      color: const Color(0xFFEF4444).withValues(alpha: 0.12),
                    ),
                    child: const Icon(
                      Icons.close_rounded,
                      color: Color(0xFFEF4444),
                      size: 16,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _installment,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            onChanged: (_) => _emit(),
            validator: (v) {
              if ((v ?? '').trim().isEmpty) return 'Required';
              if (double.tryParse(v!.trim()) == null) return 'Invalid';
              return null;
            },
            style: const TextStyle(color: Color(0xFFE2E8F0), fontSize: 13),
            decoration: _inputDeco(
              'Monthly Installment',
              Icons.calendar_month_rounded,
            ),
          ),
          const SizedBox(height: 10),
          TextFormField(
            controller: _balance,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            onChanged: (_) => _emit(),
            validator: (v) {
              if ((v ?? '').trim().isEmpty) return 'Required';
              if (double.tryParse(v!.trim()) == null) return 'Invalid';
              return null;
            },
            style: const TextStyle(color: Color(0xFFE2E8F0), fontSize: 13),
            decoration: _inputDeco(
              'Remaining Balance',
              Icons.account_balance_rounded,
            ),
          ),
          const SizedBox(height: 10),
          TextFormField(
            controller: _market,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            onChanged: (_) => _emit(),
            validator: (v) {
              if ((v ?? '').trim().isEmpty) return 'Required';
              if (double.tryParse(v!.trim()) == null) return 'Invalid';
              return null;
            },
            style: const TextStyle(color: Color(0xFFE2E8F0), fontSize: 13),
            decoration: _inputDeco('Market Value', Icons.trending_up_rounded),
          ),
        ],
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
