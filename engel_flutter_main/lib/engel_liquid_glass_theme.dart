import 'package:flutter/material.dart';

/// Liquid Glass operator tokens for Engel AI Main.
///
/// Clear glass — translucent tint + light rim, no frosted blur.
class EngelLiquidGlass {
  EngelLiquidGlass._();

  static const Color backdrop = Color(0xff0a0d12);
  static const Color backdropMid = Color(0xff12161f);
  static const Color backdropEdge = Color(0xff1a2030);
  /// Clear tint — light enough to show art, dark enough for text.
  static const Color surface = Color(0xB0161b24);
  static const Color surfaceSolid = Color(0xff161b24);
  /// Content plates (Status cards, lists) — readable over bright art.
  static const Color surfaceElevated = Color(0xC41e2533);
  static const Color rim = Color(0x66ffffff);
  static const Color rimStrong = Color(0x99c8d2e0);
  static const Color textPrimary = Color(0xfff7f8fb);
  static const Color textSecondary = Color(0xffd5dbe6);
  static const Color textMuted = Color(0xff9aa3b2);
  static const Color accent = Color(0xff7ec8d8);
  static const Color accentStrong = Color(0xffa8dde8);
  static const Color accentOn = Color(0xff0a0d12);
  static const Color warn = Color(0xffe0b35a);
  static const Color ok = Color(0xff6bcf9a);
  static const Color bad = Color(0xffe07a84);
  static const double radius = 16;
  static const double radiusSm = 12;

  static ThemeData theme() {
    final scheme = ColorScheme.dark(
      primary: accent,
      onPrimary: accentOn,
      secondary: accentStrong,
      onSecondary: accentOn,
      surface: surfaceSolid,
      onSurface: textPrimary,
      error: bad,
      onError: accentOn,
    );
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: backdrop,
      fontFamily: 'Segoe UI',
      visualDensity: VisualDensity.standard,
      materialTapTargetSize: MaterialTapTargetSize.padded,
      textTheme: const TextTheme(
        headlineSmall: TextStyle(
          fontSize: 22,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.4,
          color: textPrimary,
        ),
        titleLarge: TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w700,
          color: textPrimary,
        ),
        bodyMedium: TextStyle(
          fontSize: 14.5,
          fontWeight: FontWeight.w500,
          color: textSecondary,
        ),
        labelMedium: TextStyle(
          fontSize: 12.5,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.2,
          color: textMuted,
        ),
      ),
      iconButtonTheme: const IconButtonThemeData(
        style: ButtonStyle(minimumSize: WidgetStatePropertyAll(Size(44, 44))),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceElevated,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusSm),
          borderSide: const BorderSide(color: rim, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusSm),
          borderSide: const BorderSide(color: accent, width: 1.5),
        ),
        hintStyle: const TextStyle(color: textMuted),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: surfaceElevated,
          foregroundColor: accentStrong,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusSm),
            side: const BorderSide(color: rim),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: accentOn,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusSm),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          backgroundColor: surfaceElevated,
          side: const BorderSide(color: rimStrong),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusSm),
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: surfaceElevated,
        selectedColor: accent,
        labelStyle: const TextStyle(
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
        secondaryLabelStyle: const TextStyle(color: accentOn),
        side: const BorderSide(color: rim),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusSm),
        ),
      ),
    );
  }

  static BoxDecoration shellDecoration({double opacity = 0.42}) {
    return BoxDecoration(
      color: surfaceSolid.withValues(alpha: opacity.clamp(0.28, 0.58)),
      borderRadius: BorderRadius.circular(radius),
      border: Border.all(color: rim),
    );
  }

  static const LinearGradient quietBackdrop = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [backdrop, backdropMid, backdropEdge, backdrop],
    stops: [0.0, 0.4, 0.75, 1.0],
  );
}

/// Clear glass panel — readable dark tint + rim, no BackdropFilter frost.
class EngelGlassPanel extends StatelessWidget {
  const EngelGlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: EngelLiquidGlass.surfaceElevated,
        borderRadius: BorderRadius.circular(EngelLiquidGlass.radiusSm),
        border: Border.all(color: EngelLiquidGlass.rimStrong),
      ),
      child: DefaultTextStyle.merge(
        style: const TextStyle(
          color: EngelLiquidGlass.textPrimary,
          shadows: [
            Shadow(
              color: Color(0x99000000),
              blurRadius: 6,
              offset: Offset(0, 1),
            ),
          ],
        ),
        child: child,
      ),
    );
  }
}
