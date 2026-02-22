import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/features/auth/data/repo/auth_service.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/auth_background.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/glass_card.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/shimmer_text.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/gradient_button.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/premium_input_decoration.dart';

class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _newPassController = TextEditingController();
  final _confirmPassController = TextEditingController();

  bool _isLoading = false;
  bool _showNewPassword = false;
  bool _showConfirmPassword = false;
  String? _errorMessage;
  bool _success = false;

  late AnimationController _fadeController;
  late AnimationController _logoController;

  static const Color _gold = AppColors.gold;
  static const Color _accent = AppColors.accent;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      vsync: this,
      duration: Duration(milliseconds: 1000),
    )..forward();
    _logoController = AnimationController(
      vsync: this,
      duration: Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _emailController.dispose();
    _newPassController.dispose();
    _confirmPassController.dispose();
    _fadeController.dispose();
    _logoController.dispose();
    super.dispose();
  }

  Future<void> _onResetPassword() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final result = await AuthService.resetPassword(
        _emailController.text.trim(),
        _newPassController.text.trim(),
      );

      if (!mounted) return;

      if (result['success'] == true) {
        setState(() {
          _success = true;
          _isLoading = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppStrings.passwordResetSuccess),
            backgroundColor: _gold.withValues(alpha: 0.9),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        );
        // Wait a moment then go back to login
        Future.delayed(Duration(seconds: 2), () {
          if (mounted) Navigator.pop(context);
        });
      } else {
        setState(() {
          _errorMessage = result['error'] as String?;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Connection error. Please try again.';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthBackground(
      child: SafeArea(
        child: FadeTransition(
          opacity: CurvedAnimation(
            parent: _fadeController,
            curve: Curves.easeOut,
          ),
          child: SlideTransition(
            position: Tween<Offset>(
              begin: const Offset(0, 0.08),
              end: Offset.zero,
            ).animate(
              CurvedAnimation(
                parent: _fadeController,
                curve: Curves.easeOut,
              ),
            ),
            child: Center(
              child: SingleChildScrollView(
                padding: EdgeInsets.symmetric(horizontal: 30),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    _buildLogo(),
                    SizedBox(height: 6),
                    ShimmerText(text: AppStrings.appName),
                    SizedBox(height: 6),
                    _buildTagLine(),
                    SizedBox(height: 44),
                    GlassCard(child: _buildForm()),
                    SizedBox(height: 44),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLogo() {
    return AnimatedBuilder(
      animation: _logoController,
      builder: (_, __) {
        final pulse = 0.8 + 0.2 * _logoController.value;
        return Container(
          padding: EdgeInsets.all(16),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: _gold.withValues(alpha: 0.15 * pulse),
                blurRadius: 40 * pulse,
                spreadRadius: 10 * pulse,
              ),
              BoxShadow(
                color: _accent.withValues(alpha: 0.08 * pulse),
                blurRadius: 60 * pulse,
                spreadRadius: 15 * pulse,
              ),
            ],
          ),
          child: ShaderMask(
            shaderCallback: (bounds) => const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [_gold, _accent],
            ).createShader(bounds),
            child: Icon(Icons.lock_reset_rounded, size: 48, color: Colors.white),
          ),
        );
      },
    );
  }

  Widget _buildTagLine() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Container(width: 20, height: 1, color: _gold.withValues(alpha: 0.3)),
        SizedBox(width: 10),
        Text(
          'PASSWORD RECOVERY',
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w500,
            color: _accent.withValues(alpha: 0.6),
            letterSpacing: 3,
          ),
        ),
        SizedBox(width: 10),
        Container(width: 20, height: 1, color: _gold.withValues(alpha: 0.3)),
      ],
    );
  }

  Widget _buildForm() {
    if (_success) {
      return _buildSuccessContent();
    }
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                AppStrings.forgotPasswordTitle,
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
              SizedBox(width: 8),
            ],
          ),
          SizedBox(height: 6),
          Text(
            AppStrings.forgotPasswordSubtitle,
            style: TextStyle(
              fontSize: 12,
              color: Colors.white.withValues(alpha: 0.5),
            ),
          ),
          SizedBox(height: 28),

          // Error message
          if (_errorMessage != null)
            Container(
              margin: EdgeInsets.only(bottom: 18),
              padding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: Colors.red.withValues(alpha: 0.2),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.error_outline,
                    color: Colors.redAccent.withValues(alpha: 0.8),
                    size: 18,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _errorMessage!,
                      style: TextStyle(
                        color: Colors.redAccent.withValues(alpha: 0.9),
                        fontSize: 13,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // Email
          TextFormField(
            controller: _emailController,
            style: TextStyle(color: Colors.white, fontSize: 14),
            decoration: premiumInputDecoration(
              AppStrings.emailHint,
              Icons.mail_outline,
            ),
            validator: (v) =>
                v == null || !v.contains('@') ? AppStrings.emailError : null,
            enabled: !_isLoading,
            keyboardType: TextInputType.emailAddress,
          ),
          const SizedBox(height: 14),

          // New Password
          TextFormField(
            controller: _newPassController,
            style: TextStyle(color: Colors.white, fontSize: 14),
            obscureText: !_showNewPassword,
            decoration: premiumInputDecoration(
              AppStrings.newPasswordHint,
              Icons.lock_outline,
              suffix: IconButton(
                icon: Icon(
                  _showNewPassword
                      ? Icons.visibility_off_rounded
                      : Icons.visibility_rounded,
                  color: _gold.withValues(alpha: 0.4),
                  size: 20,
                ),
                onPressed: () =>
                    setState(() => _showNewPassword = !_showNewPassword),
              ),
            ),
            validator: (v) {
              if (v == null || v.length < 6) {
                return AppStrings.passwordMinLength;
              }
              return null;
            },
            enabled: !_isLoading,
          ),
          const SizedBox(height: 14),

          // Confirm Password
          TextFormField(
            controller: _confirmPassController,
            style: TextStyle(color: Colors.white, fontSize: 14),
            obscureText: !_showConfirmPassword,
            decoration: premiumInputDecoration(
              AppStrings.confirmPasswordHint,
              Icons.lock_outline,
              suffix: IconButton(
                icon: Icon(
                  _showConfirmPassword
                      ? Icons.visibility_off_rounded
                      : Icons.visibility_rounded,
                  color: _gold.withValues(alpha: 0.4),
                  size: 20,
                ),
                onPressed: () => setState(
                    () => _showConfirmPassword = !_showConfirmPassword),
              ),
            ),
            validator: (v) {
              if (v != _newPassController.text) {
                return AppStrings.confirmPasswordError;
              }
              return null;
            },
            enabled: !_isLoading,
          ),
          SizedBox(height: 28),

          // Reset Button
          GradientButton(
            onPressed: _onResetPassword,
            isLoading: _isLoading,
            text: AppStrings.resetPassword,
          ),
          SizedBox(height: 24),

          // Back to login
          Center(
            child: GestureDetector(
              onTap: () => Navigator.pop(context),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.arrow_back_ios_rounded,
                    size: 14,
                    color: _accent.withValues(alpha: 0.6),
                  ),
                  SizedBox(width: 4),
                  ShaderMask(
                    shaderCallback: (bounds) => LinearGradient(
                      colors: [_gold, _accent],
                    ).createShader(bounds),
                    child: Text(
                      AppStrings.backToLogin,
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSuccessContent() {
    return Column(
      children: [
        Container(
          padding: EdgeInsets.all(20),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: _gold.withValues(alpha: 0.1),
          ),
          child: Icon(
            Icons.check_circle_outline_rounded,
            color: _gold,
            size: 56,
          ),
        ),
        SizedBox(height: 24),
        Text(
          'Password Updated!',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
        SizedBox(height: 10),
        Text(
          AppStrings.passwordResetSuccess,
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 13,
            color: Colors.white.withValues(alpha: 0.5),
          ),
        ),
        SizedBox(height: 28),
        GradientButton(
          onPressed: () => Navigator.pop(context),
          text: AppStrings.backToLogin,
        ),
      ],
    );
  }
}
