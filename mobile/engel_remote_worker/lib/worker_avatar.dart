import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'new_tech_theme.dart';

/// Avatar mood driven by pairing / tasking / Discord-pipe state.
enum AvatarMood { idle, ready, tasking, discordPipe }

/// Live layered portrait: open/blink + eyes-only layer for Face light min.
class WorkerAvatarStage extends StatefulWidget {
  const WorkerAvatarStage({
    super.key,
    required this.theme,
    required this.mood,
    required this.breath,
    required this.onTap,
    this.faceLight = 0.62,
    this.size = 248,
  });

  final NewTechTheme theme;
  final AvatarMood mood;
  final Animation<double> breath;
  final VoidCallback onTap;

  /// 0.0 = eyes-only in the void · 1.0 = full sleek portrait.
  final double faceLight;
  final double size;

  /// Portrait visibility curve: crushed near 0, readable by mid, full at 1.
  static double portraitOpacity(double faceLight) {
    final t = faceLight.clamp(0.0, 1.0);
    if (t <= 0.08) return 0.0;
    if (t >= 0.55) return 1.0;
    // Ease from 0.08 → 0.55
    final u = (t - 0.08) / (0.55 - 0.08);
    return Curves.easeOutCubic.transform(u);
  }

  /// Eyes-only layer: full at darkest, fades as portrait returns.
  static double eyesOnlyOpacity(double faceLight) {
    final t = faceLight.clamp(0.0, 1.0);
    if (t <= 0.12) return 1.0;
    if (t >= 0.45) return 0.0;
    return 1.0 - ((t - 0.12) / (0.45 - 0.12));
  }

  /// Soft lift for mid/high Face light (portrait readable).
  static ColorFilter portraitFilter(double faceLight) {
    final t = faceLight.clamp(0.0, 1.0);
    final contrast = 0.95 + (t * 0.22);
    final bright = 4.0 + (t * 28.0);
    return ColorFilter.matrix(<double>[
      contrast, 0, 0, 0, bright,
      0, contrast, 0, 0, bright,
      0, 0, contrast, 0, bright,
      0, 0, 0, 1, 0,
    ]);
  }

  @override
  State<WorkerAvatarStage> createState() => _WorkerAvatarStageState();
}

class _WorkerAvatarStageState extends State<WorkerAvatarStage>
    with TickerProviderStateMixin {
  late final AnimationController _tap;
  late final AnimationController _blink;
  late final AnimationController _sway;
  late final Animation<double> _tapScale;
  Timer? _blinkTimer;
  final _rng = math.Random();
  bool _eyesClosed = false;

  @override
  void initState() {
    super.initState();
    _tap = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 420),
    );
    _tapScale = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.93), weight: 26),
      TweenSequenceItem(tween: Tween(begin: 0.93, end: 1.05), weight: 38),
      TweenSequenceItem(tween: Tween(begin: 1.05, end: 1.0), weight: 36),
    ]).animate(CurvedAnimation(parent: _tap, curve: Curves.easeOutCubic));

    _blink = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 140),
    )..addStatusListener((status) {
        if (status == AnimationStatus.completed) {
          setState(() => _eyesClosed = true);
          Future<void>.delayed(const Duration(milliseconds: 90), () {
            if (!mounted) return;
            _blink.reverse();
          });
        } else if (status == AnimationStatus.dismissed) {
          if (_eyesClosed) setState(() => _eyesClosed = false);
        }
      });

    _sway = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 5200),
    )..repeat(reverse: true);

    _scheduleBlink();
  }

  void _scheduleBlink() {
    _blinkTimer?.cancel();
    final waitMs = switch (widget.mood) {
      AvatarMood.tasking || AvatarMood.discordPipe =>
        1600 + _rng.nextInt(1400),
      AvatarMood.ready => 2800 + _rng.nextInt(2200),
      AvatarMood.idle => 3400 + _rng.nextInt(2800),
    };
    _blinkTimer = Timer(Duration(milliseconds: waitMs), () {
      if (!mounted) return;
      _blink.forward(from: 0);
      _scheduleBlink();
    });
  }

  @override
  void didUpdateWidget(covariant WorkerAvatarStage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.mood != widget.mood) {
      _scheduleBlink();
    }
  }

  @override
  void dispose() {
    _blinkTimer?.cancel();
    _tap.dispose();
    _blink.dispose();
    _sway.dispose();
    super.dispose();
  }

  void _handleTap() {
    HapticFeedback.lightImpact();
    _tap.forward(from: 0);
    _blink.forward(from: 0);
    widget.onTap();
  }

  Color get _moodColor {
    switch (widget.mood) {
      case AvatarMood.tasking:
      case AvatarMood.discordPipe:
        return widget.theme.accent;
      case AvatarMood.ready:
        return NewTechTheme.ok;
      case AvatarMood.idle:
        return NewTechTheme.muted;
    }
  }

  double get _glowStrength {
    switch (widget.mood) {
      case AvatarMood.tasking:
        return 0.12;
      case AvatarMood.discordPipe:
        return 0.14;
      case AvatarMood.ready:
        return 0.08;
      case AvatarMood.idle:
        return 0.04;
    }
  }

  @override
  Widget build(BuildContext context) {
    final size = widget.size;
    final portraitOp =
        WorkerAvatarStage.portraitOpacity(widget.faceLight);
    final eyesOp = WorkerAvatarStage.eyesOnlyOpacity(widget.faceLight);
    // While blinking at eyes-only: hide eye layer (eyes vanish briefly).
    final eyesVisible = eyesOp *
        (_eyesClosed
            ? (1.0 - Curves.easeInOut.transform(_blink.value))
            : 1.0);

    return AnimatedBuilder(
      animation: Listenable.merge([widget.breath, _tap, _sway, _blink]),
      builder: (context, _) {
        final breathe = 1.0 + (widget.breath.value * 0.018);
        final swayX = math.sin(_sway.value * math.pi * 2) * 2.8;
        final swayY = math.cos(_sway.value * math.pi * 2) * 1.4;
        final tilt = math.sin(_sway.value * math.pi * 2) * 0.014;
        final scale = breathe * _tapScale.value;
        final mood = _moodColor;
        final taskPulse = widget.mood == AvatarMood.tasking ||
            widget.mood == AvatarMood.discordPipe;

        return GestureDetector(
          onTap: _handleTap,
          child: SizedBox(
            width: size + 40,
            height: size + 40,
            child: Stack(
              alignment: Alignment.center,
              children: [
                Container(
                  width: size + 28,
                  height: size + 28,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: mood.withValues(
                          alpha: _glowStrength +
                              (taskPulse ? widget.breath.value * 0.08 : 0.02),
                        ),
                        blurRadius: taskPulse ? 36 : 22,
                        spreadRadius: taskPulse ? 4 : 1,
                      ),
                    ],
                  ),
                ),
                Transform.translate(
                  offset: Offset(swayX, swayY),
                  child: Transform.rotate(
                    angle: tilt,
                    child: Transform.scale(
                      scale: scale,
                      child: Container(
                        width: size,
                        height: size,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.black,
                          border: Border.all(
                            color: mood.withValues(alpha: 0.28),
                            width: 1.4,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.4),
                              blurRadius: 16,
                              offset: const Offset(0, 8),
                            ),
                          ],
                        ),
                        child: ClipOval(
                          child: Stack(
                            fit: StackFit.expand,
                            children: [
                              // Full sleek portrait — crushed to void at Face light 0%.
                              Opacity(
                                opacity: portraitOp,
                                child: ColorFiltered(
                                  colorFilter:
                                      WorkerAvatarStage.portraitFilter(
                                    widget.faceLight,
                                  ),
                                  child: Stack(
                                    fit: StackFit.expand,
                                    children: [
                                      Image.asset(
                                        widget.theme.avatarOpenAsset,
                                        fit: BoxFit.cover,
                                        gaplessPlayback: true,
                                        errorBuilder: (_, __, ___) =>
                                            ColoredBox(
                                          color: NewTechTheme.surface2,
                                          child: Center(
                                            child: Text(
                                              widget.theme.label[0],
                                              style: TextStyle(
                                                color: widget.theme.accent,
                                                fontSize: 64,
                                                fontWeight: FontWeight.w700,
                                              ),
                                            ),
                                          ),
                                        ),
                                      ),
                                      Opacity(
                                        opacity: _eyesClosed
                                            ? 1.0
                                            : Curves.easeInOut
                                                .transform(_blink.value)
                                                .clamp(0.0, 1.0),
                                        child: Image.asset(
                                          widget.theme.avatarBlinkAsset,
                                          fit: BoxFit.cover,
                                          gaplessPlayback: true,
                                          errorBuilder: (_, __, ___) =>
                                              const SizedBox.shrink(),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                              // Eyes-only layer — dominates at Face light min.
                              if (eyesVisible > 0.01)
                                Opacity(
                                  opacity: eyesVisible.clamp(0.0, 1.0),
                                  child: Image.asset(
                                    widget.theme.avatarEyesAsset,
                                    fit: BoxFit.cover,
                                    gaplessPlayback: true,
                                    errorBuilder: (_, __, ___) =>
                                        const SizedBox.shrink(),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

/// Thin HUD chrome chip — not a status card.
class HudChromeChip extends StatelessWidget {
  const HudChromeChip({
    super.key,
    required this.label,
    required this.value,
    this.accent,
  });

  final String label;
  final String value;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final color = accent ?? NewTechTheme.text;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: NewTechTheme.surface.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: NewTechTheme.border.withValues(alpha: 0.7)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label.toUpperCase(),
            style: const TextStyle(
              color: NewTechTheme.muted,
              fontSize: 9,
              letterSpacing: 1.1,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
