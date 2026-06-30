import 'package:flutter/material.dart';
import 'package:SemsAi/core/constants/app_colors.dart';
import 'package:SemsAi/core/theme/app_themes.dart';


class ChatBubble extends StatefulWidget {
  final String text;
  final bool isUser;
  final int index;

  const ChatBubble({
    super.key,
    required this.text,
    required this.isUser,
    required this.index,
  });

  @override
  State<ChatBubble> createState() => _ChatBubbleState();
}

class _ChatBubbleState extends State<ChatBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController _anim;
  late final Animation<double> _fadeSlide;

  @override
  void initState() {
    super.initState();
    _anim = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    );
    _fadeSlide = CurvedAnimation(parent: _anim, curve: Curves.easeOutCubic);
    Future.delayed(Duration(milliseconds: 60 * (widget.index % 5)), () {
      if (mounted) _anim.forward();
    });
  }

  @override
  void dispose() {
    _anim.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fadeSlide,
      child: SlideTransition(
        position: Tween<Offset>(
          begin: Offset(widget.isUser ? 0.15 : -0.15, 0),
          end: Offset.zero,
        ).animate(_fadeSlide),
        child: Align(
          alignment: widget.isUser
              ? Alignment.centerRight
              : Alignment.centerLeft,
          child: Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.78,
            ),
            margin: EdgeInsets.only(
              top: 4,
              bottom: 4,
              left: widget.isUser ? 48 : 0,
              right: widget.isUser ? 0 : 48,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              gradient: widget.isUser
                  ? LinearGradient(
                      colors: [
                        AppColors.gold,
                        AppColors.gold.withValues(alpha: 0.85),
                      ],
                    )
                  : null,
              color: widget.isUser ? null : context.appColors.cardBg,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(18),
                topRight: const Radius.circular(18),
                bottomLeft: Radius.circular(widget.isUser ? 18 : 4),
                bottomRight: Radius.circular(widget.isUser ? 4 : 18),
              ),
              border: widget.isUser
                  ? null
                  : Border.all(color: context.appColors.border.withValues(alpha: 0.5)),
              boxShadow: [
                BoxShadow(
                  color: (widget.isUser ? AppColors.gold : Colors.black)
                      .withValues(alpha: 0.15),
                  blurRadius: 6,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Text(
              widget.text,
              style: TextStyle(
                color: widget.isUser ? Colors.white : context.appColors.textPrimary,
                fontSize: 15,
                height: 1.4,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
