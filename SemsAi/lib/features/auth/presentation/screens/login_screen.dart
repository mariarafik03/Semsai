import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:SemsAi/features/auth/presentation/cubit/auth_cubit.dart';
import 'package:SemsAi/features/auth/presentation/cubit/auth_state.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/constants/app_strings.dart';
import 'package:SemsAi/core/routing/app_routes.dart';
import 'package:SemsAi/features/auth/presentation/screens/register_screen.dart';
import 'package:SemsAi/features/auth/presentation/screens/forgot_password_screen.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/auth_background.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/glass_card.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/shimmer_text.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/gradient_button.dart';
import 'package:SemsAi/features/auth/presentation/screens/widgets/premium_input_decoration.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passController = TextEditingController();
  bool _showPassword = false;

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
    _passController.dispose();
    _fadeController.dispose();
    _logoController.dispose();
    super.dispose();
  }

  void _onLogin() {
    if (!_formKey.currentState!.validate()) return;
    context.read<AuthCubit>().login(
      _emailController.text.trim().toLowerCase(),
      _passController.text.trim(),
    );
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
            position:
                Tween<Offset>(
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
            child: Icon(Icons.apartment_rounded, size: 48, color: Colors.white),
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
          AppStrings.tagLine,
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
    return BlocConsumer<AuthCubit, AuthState>(
      listener: (context, state) {
        if (state is AuthAuthenticated) {
          Navigator.pushReplacementNamed(context, AppRoutes.home);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Welcome ${state.user.name}'),
              backgroundColor: _gold.withValues(alpha: 0.9),
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          );
        } else if (state is AuthError) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(state.message),
              backgroundColor: Colors.red.withValues(alpha: 0.85),
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          );
        }
      },
      builder: (context, state) {
        final isLoading = state is AuthLoading;
        return Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    AppStrings.signIn,
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
                AppStrings.loginSubtitle,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.white.withValues(alpha: 0.5),
                ),
              ),
              SizedBox(height: 28),
              if (state is AuthError)
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
                          state.message,
                          style: TextStyle(
                            color: Colors.redAccent.withValues(alpha: 0.9),
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              TextFormField(
                controller: _emailController,
                style: TextStyle(color: Colors.white, fontSize: 14),
                decoration: premiumInputDecoration(
                  AppStrings.emailHint,
                  Icons.mail_outline,
                ),
                validator: (v) => v == null || !v.contains('@')
                    ? AppStrings.emailError
                    : null,
                enabled: !isLoading,
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _passController,
                style: TextStyle(color: Colors.white, fontSize: 14),
                obscureText: !_showPassword,
                decoration: premiumInputDecoration(
                  AppStrings.passwordHint,
                  Icons.lock_outline,
                  suffix: IconButton(
                    icon: Icon(
                      _showPassword
                          ? Icons.visibility_off_rounded
                          : Icons.visibility_rounded,
                      color: _gold.withValues(alpha: 0.4),
                      size: 20,
                    ),
                    onPressed: () =>
                        setState(() => _showPassword = !_showPassword),
                  ),
                ),
                validator: (v) {
                  if (v == null || v.length < 6) {
                    return AppStrings.passwordError;
                  }
                  return null;
                },
                enabled: !isLoading,
              ),
              SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () => Navigator.push(
                    context,
                    PageRouteBuilder(
                      pageBuilder: (_, __, ___) =>
                          const ForgotPasswordScreen(),
                      transitionsBuilder: (_, a, __, c) =>
                          FadeTransition(opacity: a, child: c),
                      transitionDuration: Duration(milliseconds: 400),
                    ),
                  ),
                  style: TextButton.styleFrom(
                    padding: EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                  ),
                  child: Text(
                    AppStrings.forgotPassword,
                    style: TextStyle(
                      color: _accent.withValues(alpha: 0.6),
                      fontSize: 12,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                ),
              ),
              SizedBox(height: 20),
              GradientButton(
                onPressed: _onLogin,
                isLoading: isLoading,
                text: AppStrings.signIn,
              ),
              SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    AppStrings.noAccount,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.4),
                      fontSize: 13,
                    ),
                  ),
                  GestureDetector(
                    onTap: () => Navigator.pushReplacement(
                      context,
                      PageRouteBuilder(
                        pageBuilder: (_, __, ___) => RegisterScreen(),
                        transitionsBuilder: (_, a, __, c) =>
                            FadeTransition(opacity: a, child: c),
                        transitionDuration: Duration(milliseconds: 400),
                      ),
                    ),
                    child: ShaderMask(
                      shaderCallback: (bounds) => LinearGradient(
                        colors: [_gold, _accent],
                      ).createShader(bounds),
                      child: Text(
                        AppStrings.signUp,
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}
