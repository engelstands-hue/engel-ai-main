import 'package:flutter/material.dart';

/// Sleek sexy anime HUD theme — polished glam accents on night graphite.
class NewTechTheme {
  const NewTechTheme({
    required this.accent,
    required this.accentSoft,
    required this.textureAsset,
    required this.avatarOpenAsset,
    required this.avatarBlinkAsset,
    required this.avatarEyesAsset,
    required this.label,
  });

  final Color accent;
  final Color accentSoft;
  final String textureAsset;
  final String avatarOpenAsset;
  final String avatarBlinkAsset;
  final String avatarEyesAsset;
  final String label;

  String get avatarAsset => avatarOpenAsset;

  static const bg = Color(0xFF0A0C10);
  static const surface = Color(0xFF12161C);
  static const surface2 = Color(0xFF181E25);
  static const border = Color(0xFF2A323C);
  static const text = Color(0xFFE8EDF2);
  static const muted = Color(0xFF8A96A2);
  static const danger = Color(0xFFD65A5A);
  static const warn = Color(0xFFD2A24A);
  static const ok = Color(0xFF3CB98A);

  static NewTechTheme forWorker(String workerId) {
    switch (workerId) {
      case 'android_worker_beta':
        return const NewTechTheme(
          accent: Color(0xFFB48AD6),
          accentSoft: Color(0x33B48AD6),
          textureAsset: 'assets/worker_texture_beta.png',
          avatarOpenAsset: 'assets/avatar_beta_open.png',
          avatarBlinkAsset: 'assets/avatar_beta_blink.png',
          avatarEyesAsset: 'assets/avatar_beta_eyes.png',
          label: 'Beta',
        );
      case 'android_worker_gamma':
        return const NewTechTheme(
          accent: Color(0xFF6ECFBA),
          accentSoft: Color(0x336ECFBA),
          textureAsset: 'assets/worker_texture_gamma.png',
          avatarOpenAsset: 'assets/avatar_gamma_open.png',
          avatarBlinkAsset: 'assets/avatar_gamma_blink.png',
          avatarEyesAsset: 'assets/avatar_gamma_eyes.png',
          label: 'Gamma',
        );
      case 'android_worker_alpha':
      default:
        return const NewTechTheme(
          accent: Color(0xFFE39AB8),
          accentSoft: Color(0x33E39AB8),
          textureAsset: 'assets/worker_texture_alpha.png',
          avatarOpenAsset: 'assets/avatar_alpha_open.png',
          avatarBlinkAsset: 'assets/avatar_alpha_blink.png',
          avatarEyesAsset: 'assets/avatar_alpha_eyes.png',
          label: 'Alpha',
        );
    }
  }
}

class SoftPanel extends StatelessWidget {
  const SoftPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(14),
    this.accent,
  });

  final Widget child;
  final EdgeInsets padding;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final edge = accent ?? NewTechTheme.border;
    return Container(
      decoration: BoxDecoration(
        color: NewTechTheme.surface.withValues(alpha: 0.88),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: edge.withValues(alpha: 0.55)),
      ),
      padding: padding,
      child: child,
    );
  }
}

class QuietLabel extends StatelessWidget {
  const QuietLabel(this.text, {super.key, this.color});

  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: TextStyle(
        color: color ?? NewTechTheme.muted,
        fontSize: 11,
        letterSpacing: 1.4,
        fontWeight: FontWeight.w600,
        fontFamily: 'Segoe UI',
        fontFamilyFallback: const ['Roboto', 'sans-serif'],
      ),
    );
  }
}
