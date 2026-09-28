part of 'main.dart';

// ============================================================================
// Engel Agent Loops diagrams
//
// Real vector graphics for the Agent Loops window: the harness diagram, the
// goal-loop ring, and one painted spark per production rule. Everything is
// drawn with Canvas primitives at a fixed logical size and scaled to the
// available width, so the art stays crisp at any window size and ships with
// no image assets (the app must stay self-contained and offline).
//
// Painters are static art: shouldRepaint is always false.
// ============================================================================

/// Builds one Agent Loops figure standalone, so a capture test can render the
/// exact painter the window uses. `name` is 'harness', 'loop', or `rule-N`.
Widget engelAgentLoopsFigure(String name) {
  if (name == 'harness') {
    return const _EngelDiagram(
      logical: Size(760, 290),
      painter: _HarnessDiagramPainter(),
      semanticLabel: 'Harness diagram',
    );
  }
  if (name == 'loop') {
    return const _EngelDiagram(
      logical: Size(760, 366),
      painter: _LoopDiagramPainter(),
      semanticLabel: 'Goal loop diagram',
    );
  }
  final rule = int.tryParse(name.replaceFirst('rule-', '')) ?? 1;
  return _EngelDiagram(
    logical: const Size(150, 56),
    painter: _RuleSparkPainter(rule),
    semanticLabel: 'Rule $rule diagram',
  );
}

const Color _inkBright = Color(0xffe8eef8);
const Color _inkDim = Color(0xff8b98a5);
const Color _inkTeal = Color(0xff58e6c8);
const Color _inkAmber = Color(0xffffc857);
const Color _inkViolet = Color(0xff8f7cff);
const Color _inkGreen = Color(0xff5fd68a);
const Color _inkRed = Color(0xffff7777);
const Color _inkPanel = Color(0xff11161f);

// ---------------------------------------------------------------- primitives

TextPainter _diagTp(
  String text, {
  required Color color,
  double size = 11,
  FontWeight weight = FontWeight.w600,
  bool italic = false,
  double width = double.infinity,
  TextAlign align = TextAlign.center,
}) {
  return TextPainter(
    text: TextSpan(
      text: text,
      style: TextStyle(
        color: color,
        fontSize: size,
        fontWeight: weight,
        fontStyle: italic ? FontStyle.italic : FontStyle.normal,
        height: 1.15,
      ),
    ),
    textAlign: align,
    textDirection: TextDirection.ltr,
  )..layout(maxWidth: width);
}

/// Paints [text] centred horizontally on [centerX] with its top at [top].
void _diagText(
  Canvas canvas,
  String text, {
  required double centerX,
  required double top,
  required Color color,
  double size = 11,
  FontWeight weight = FontWeight.w600,
  bool italic = false,
  double width = 220,
}) {
  final tp = _diagTp(
    text,
    color: color,
    size: size,
    weight: weight,
    italic: italic,
    width: width,
  );
  tp.paint(canvas, Offset(centerX - width / 2, top));
}

void _dashPath(Canvas canvas, Path path, Paint paint,
    {double dash = 6, double gap = 4.5}) {
  for (final metric in path.computeMetrics()) {
    double distance = 0;
    while (distance < metric.length) {
      final next = math.min(distance + dash, metric.length);
      canvas.drawPath(metric.extractPath(distance, next), paint);
      distance = next + gap;
    }
  }
}

void _diagBox(
  Canvas canvas,
  Rect rect, {
  required Color border,
  Color? fill,
  double radius = 9,
  double stroke = 1.5,
  bool dashed = false,
}) {
  final rrect = RRect.fromRectAndRadius(rect, Radius.circular(radius));
  if (fill != null) {
    canvas.drawRRect(rrect, Paint()..color = fill);
  }
  final paint = Paint()
    ..color = border
    ..style = PaintingStyle.stroke
    ..strokeWidth = stroke;
  if (dashed) {
    _dashPath(canvas, Path()..addRRect(rrect), paint);
  } else {
    canvas.drawRRect(rrect, paint);
  }
}

/// Title (+ optional subtitle) vertically centred inside [rect].
void _diagBoxLabel(
  Canvas canvas,
  Rect rect,
  String title, {
  String? sub,
  Color titleColor = _inkBright,
  Color subColor = _inkDim,
  double titleSize = 11.5,
  double subSize = 8.5,
}) {
  final width = rect.width - 8;
  final titleTp = _diagTp(
    title,
    color: titleColor,
    size: titleSize,
    weight: FontWeight.w700,
    width: width,
  );
  final subTp = (sub == null || sub.isEmpty)
      ? null
      : _diagTp(sub, color: subColor, size: subSize, width: width);
  final total = titleTp.height + (subTp == null ? 0 : subTp.height + 2);
  double y = rect.center.dy - total / 2;
  titleTp.paint(canvas, Offset(rect.left + 4, y));
  if (subTp != null) {
    y += titleTp.height + 2;
    subTp.paint(canvas, Offset(rect.left + 4, y));
  }
}

void _diagArrowHead(
  Canvas canvas,
  Offset from,
  Offset to,
  Color color,
  double size,
) {
  final angle = math.atan2(to.dy - from.dy, to.dx - from.dx);
  final path = Path()
    ..moveTo(to.dx, to.dy)
    ..lineTo(
      to.dx - size * math.cos(angle - 0.44),
      to.dy - size * math.sin(angle - 0.44),
    )
    ..lineTo(
      to.dx - size * math.cos(angle + 0.44),
      to.dy - size * math.sin(angle + 0.44),
    )
    ..close();
  canvas.drawPath(
    path,
    Paint()
      ..color = color
      ..style = PaintingStyle.fill,
  );
}

void _diagArrow(
  Canvas canvas,
  List<Offset> points, {
  required Color color,
  bool dashed = false,
  double stroke = 1.5,
  double head = 7,
}) {
  final paint = Paint()
    ..color = color
    ..style = PaintingStyle.stroke
    ..strokeWidth = stroke
    ..strokeCap = StrokeCap.round
    ..strokeJoin = StrokeJoin.round;
  final path = Path()..moveTo(points.first.dx, points.first.dy);
  for (final point in points.skip(1)) {
    path.lineTo(point.dx, point.dy);
  }
  if (dashed) {
    _dashPath(canvas, path, paint);
  } else {
    canvas.drawPath(path, paint);
  }
  _diagArrowHead(canvas, points[points.length - 2], points.last, color, head);
}

/// A childless CustomPaint that draws [painter] at [logical] size, scaled to
/// whatever width the layout gives it.
class _EngelDiagram extends StatelessWidget {
  const _EngelDiagram({
    required this.logical,
    required this.painter,
    required this.semanticLabel,
    this.diagramKey,
  });

  final Size logical;
  final CustomPainter painter;
  final String semanticLabel;
  final Key? diagramKey;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: semanticLabel,
      container: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: AspectRatio(
          aspectRatio: logical.width / logical.height,
          child: CustomPaint(
            key: diagramKey,
            painter: painter,
            size: Size.infinite,
          ),
        ),
      ),
    );
  }
}

abstract class _ScaledPainter extends CustomPainter {
  const _ScaledPainter(this.logical);

  final Size logical;

  void paintLogical(Canvas canvas);

  @override
  void paint(Canvas canvas, Size size) {
    final scale = size.width / logical.width;
    canvas.save();
    canvas.scale(scale);
    paintLogical(canvas);
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// ------------------------------------------------------------ harness figure

/// Four harness surfaces feeding one local core.
class _HarnessDiagramPainter extends _ScaledPainter {
  const _HarnessDiagramPainter() : super(const Size(760, 290));

  @override
  void paintLogical(Canvas canvas) {
    final core = Rect.fromCenter(
      center: const Offset(380, 145),
      width: 208,
      height: 66,
    );
    const boxes = <(Rect, String, String)>[
      (
        Rect.fromLTWH(26, 20, 218, 60),
        'System prompt',
        'role + voice, before any turn',
      ),
      (
        Rect.fromLTWH(516, 20, 218, 60),
        'Memory + receipts',
        'past work and what actually held',
      ),
      (
        Rect.fromLTWH(26, 210, 218, 60),
        'Tool routes',
        'the hands, each one gated',
      ),
      (
        Rect.fromLTWH(516, 210, 218, 60),
        'Retrieval + RAG',
        'the right context, never all of it',
      ),
    ];
    for (final entry in boxes) {
      _diagBox(canvas, entry.$1, border: _inkTeal.withValues(alpha: 0.55),
          fill: _inkPanel);
      _diagBoxLabel(
        canvas,
        entry.$1,
        entry.$2,
        sub: entry.$3,
        titleColor: _inkTeal,
      );
    }

    const arrows = <(Offset, Offset)>[
      (Offset(244, 50), Offset(316, 112)),
      (Offset(516, 50), Offset(444, 112)),
      (Offset(244, 240), Offset(316, 178)),
      (Offset(516, 240), Offset(444, 178)),
    ];
    for (final arrow in arrows) {
      _diagArrow(
        canvas,
        [arrow.$1, arrow.$2],
        color: _inkTeal.withValues(alpha: 0.7),
        stroke: 1.4,
      );
    }

    _diagBox(canvas, core,
        border: _inkBright.withValues(alpha: 0.85),
        fill: const Color(0xff1a2130),
        radius: 12,
        stroke: 1.8);
    _diagBoxLabel(
      canvas,
      core,
      'Engel core',
      sub: 'the local seat — one voice on every lane',
      titleColor: _inkBright,
      titleSize: 14,
      subSize: 9.5,
    );
    _diagText(
      canvas,
      'context in',
      centerX: 380,
      top: 96,
      color: _inkDim,
      size: 8.5,
      italic: true,
      width: 120,
    );
  }
}

// --------------------------------------------------------------- loop figure

/// The goal loop as a ring, with the completion predicate held outside it.
class _LoopDiagramPainter extends _ScaledPainter {
  const _LoopDiagramPainter() : super(const Size(760, 366));

  @override
  void paintLogical(Canvas canvas) {
    const center = Offset(215, 165);
    // Ring arcs run clockwise through the four diagonal gaps, outside the
    // node boxes (which sit on a 105 radius).
    const arcRadius = 118.0;
    const arcs = <(double, double)>[
      (-68, -22),
      (22, 68),
      (112, 158),
      (202, 248),
    ];
    for (final arc in arcs) {
      final start = arc.$1 * math.pi / 180;
      final end = arc.$2 * math.pi / 180;
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: arcRadius),
        start,
        end - start,
        false,
        Paint()
          ..color = _inkTeal.withValues(alpha: 0.65)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.6
          ..strokeCap = StrokeCap.round,
      );
      final tip = Offset(
        center.dx + arcRadius * math.cos(end),
        center.dy + arcRadius * math.sin(end),
      );
      final before = Offset(
        center.dx + arcRadius * math.cos(end - 0.06),
        center.dy + arcRadius * math.sin(end - 0.06),
      );
      _diagArrowHead(canvas, before, tip, _inkTeal.withValues(alpha: 0.85), 7);
    }

    const nodes = <(Offset, String, String)>[
      (Offset(215, 60), 'Plan', 'pick the next move'),
      (Offset(320, 165), 'Act', 'run the real work'),
      (Offset(215, 270), 'Measure', 'read state, not vibes'),
      (Offset(110, 165), 'Learn', 'admitted rows train'),
    ];
    for (final node in nodes) {
      final rect = Rect.fromCenter(
        center: node.$1,
        width: 132,
        height: 48,
      );
      _diagBox(canvas, rect,
          border: _inkTeal.withValues(alpha: 0.6), fill: _inkPanel);
      _diagBoxLabel(canvas, rect, node.$2, sub: node.$3, titleColor: _inkTeal);
    }
    // The ring's centre stays empty on purpose: the gap between the Learn and
    // Act nodes is only 80 logical px, and any caption wide enough to read
    // there overlapped both boxes. The stall limit and turn ceiling are stated
    // in the tile directly beneath this figure.

    // Measure hands off to a predicate the agent does not get to answer.
    const predicateCenter = Offset(560, 262);
    final predicate = Path()
      ..moveTo(predicateCenter.dx, predicateCenter.dy - 44)
      ..lineTo(predicateCenter.dx + 80, predicateCenter.dy)
      ..lineTo(predicateCenter.dx, predicateCenter.dy + 44)
      ..lineTo(predicateCenter.dx - 80, predicateCenter.dy)
      ..close();
    canvas.drawPath(predicate, Paint()..color = _inkPanel);
    canvas.drawPath(
      predicate,
      Paint()
        ..color = _inkAmber
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6,
    );
    _diagText(
      canvas,
      'predicate',
      centerX: 560,
      top: 250,
      color: _inkAmber,
      size: 11.5,
      weight: FontWeight.w700,
      width: 140,
    );
    _diagText(
      canvas,
      'state on disk',
      centerX: 560,
      top: 264,
      color: _inkDim,
      size: 8.5,
      width: 140,
    );
    _diagArrow(
      canvas,
      const [Offset(282, 268), Offset(476, 264)],
      color: _inkAmber.withValues(alpha: 0.8),
    );

    final done = Rect.fromCenter(
      center: const Offset(560, 120),
      width: 200,
      height: 56,
    );
    _diagBox(canvas, done,
        border: _inkGreen.withValues(alpha: 0.75), fill: _inkPanel);
    _diagBoxLabel(
      canvas,
      done,
      'Goal done + receipt',
      sub: 'written, never claimed',
      titleColor: _inkGreen,
    );
    _diagArrow(
      canvas,
      const [Offset(560, 216), Offset(560, 150)],
      color: _inkGreen.withValues(alpha: 0.85),
    );
    _diagText(
      canvas,
      'yes',
      centerX: 585,
      top: 176,
      color: _inkGreen,
      size: 9,
      width: 40,
    );

    _diagArrow(
      canvas,
      const [
        Offset(642, 262),
        Offset(714, 262),
        Offset(714, 28),
        Offset(215, 28),
        Offset(215, 34),
      ],
      color: _inkAmber.withValues(alpha: 0.75),
      dashed: true,
    );
    _diagText(
      canvas,
      'no — the loop keeps going',
      centerX: 420,
      top: 10,
      color: _inkAmber.withValues(alpha: 0.9),
      size: 9,
      italic: true,
      width: 300,
    );
    _diagText(
      canvas,
      "the model's own 'done' never ends the loop",
      centerX: 500,
      top: 326,
      color: _inkDim,
      size: 9,
      italic: true,
      width: 330,
    );
  }
}

// -------------------------------------------------------------- rule sparks

/// One painted micro-visual per production rule (logical 150 x 56).
class _RuleSparkPainter extends _ScaledPainter {
  const _RuleSparkPainter(this.rule) : super(const Size(150, 56));

  final int rule;

  Paint _stroke(Color color, [double width = 1.6]) => Paint()
    ..color = color
    ..style = PaintingStyle.stroke
    ..strokeWidth = width
    ..strokeCap = StrokeCap.round;

  Paint _fill(Color color) => Paint()..color = color;

  void _caption(Canvas canvas, String text, {Color color = _inkDim}) {
    _diagText(
      canvas,
      text,
      centerX: 75,
      top: 44,
      color: color,
      size: 8,
      weight: FontWeight.w600,
      width: 148,
    );
  }

  void _chip(Canvas canvas, Rect rect, String label, Color color,
      {bool dashed = false}) {
    _diagBox(canvas, rect,
        border: color, fill: _inkPanel, radius: 5, stroke: 1.2, dashed: dashed);
    _diagTp(label, color: color, size: 8, width: rect.width - 2).paint(
      canvas,
      Offset(rect.left + 1, rect.center.dy - 5),
    );
  }

  @override
  void paintLogical(Canvas canvas) {
    switch (rule) {
      case 1: // Latency — budget the wait, not the total.
        canvas.drawRRect(
          RRect.fromRectAndRadius(
              const Rect.fromLTWH(8, 18, 134, 9), const Radius.circular(4)),
          _fill(const Color(0xff1c2331)),
        );
        canvas.drawRect(const Rect.fromLTWH(8, 18, 34, 9), _fill(_inkViolet));
        canvas.drawRect(const Rect.fromLTWH(42, 18, 34, 9), _fill(_inkAmber));
        canvas.drawRect(const Rect.fromLTWH(76, 18, 52, 9), _fill(_inkGreen));
        canvas.drawLine(const Offset(112, 11), const Offset(112, 34),
            _stroke(_inkBright, 1.3));
        _diagText(canvas, 'p95',
            centerX: 112, top: 2, color: _inkBright, size: 7.5, width: 40);
        _caption(canvas, 'queue · first token · stream');
        break;
      case 2: // Caching — the cheapest call is the one you skip.
        _chip(canvas, const Rect.fromLTWH(6, 15, 32, 20), 'ask', _inkDim);
        _chip(canvas, const Rect.fromLTWH(56, 15, 38, 20), 'cache', _inkGreen);
        _chip(canvas, const Rect.fromLTWH(110, 15, 34, 20), 'model',
            _inkDim.withValues(alpha: 0.45),
            dashed: true);
        canvas.drawLine(
            const Offset(38, 25), const Offset(56, 25), _stroke(_inkGreen));
        _dashPath(
          canvas,
          Path()
            ..moveTo(94, 25)
            ..lineTo(110, 25),
          _stroke(_inkDim.withValues(alpha: 0.5), 1.2),
        );
        canvas.drawCircle(const Offset(50, 25), 2.6, _fill(_inkGreen));
        _caption(canvas, 'hit · skipped the model', color: _inkGreen);
        break;
      case 3: // Cost control — route by the ask.
        _chip(canvas, const Rect.fromLTWH(6, 16, 40, 20), 'router', _inkBright);
        _chip(canvas, const Rect.fromLTWH(100, 4, 44, 18), 'small', _inkGreen);
        _chip(canvas, const Rect.fromLTWH(100, 30, 44, 18), 'large', _inkRed);
        canvas.drawLine(const Offset(46, 26), const Offset(100, 13),
            _stroke(_inkGreen, 2.2));
        canvas.drawLine(const Offset(46, 26), const Offset(100, 39),
            _stroke(_inkRed.withValues(alpha: 0.6), 1.1));
        _caption(canvas, 'most asks do not need the big lane');
        break;
      case 4: // Retries — backoff plus jitter.
        for (final x in const [14.0, 48.0, 102.0]) {
          canvas.drawLine(
              Offset(x, 24), Offset(x, 38), _stroke(_inkAmber, 2.4));
        }
        canvas.drawArc(const Rect.fromLTWH(14, 12, 34, 24), math.pi, math.pi,
            false, _stroke(_inkAmber.withValues(alpha: 0.7), 1.2));
        canvas.drawArc(const Rect.fromLTWH(48, 6, 54, 30), math.pi, math.pi,
            false, _stroke(_inkAmber.withValues(alpha: 0.7), 1.2));
        _caption(canvas, 'backoff + jitter, bounded');
        break;
      case 5: // Fallbacks — a worse answer beats none.
        _chip(canvas, const Rect.fromLTWH(4, 14, 30, 20), 'you', _inkBright);
        _chip(canvas, const Rect.fromLTWH(106, 4, 40, 18), 'first', _inkRed);
        _chip(canvas, const Rect.fromLTWH(106, 30, 40, 18), 'backup', _inkGreen);
        canvas.drawLine(const Offset(34, 20), const Offset(106, 13),
            _stroke(_inkRed.withValues(alpha: 0.55), 1.2));
        canvas.drawLine(const Offset(66, 11), const Offset(78, 23),
            _stroke(_inkRed, 1.6));
        canvas.drawLine(const Offset(78, 11), const Offset(66, 23),
            _stroke(_inkRed, 1.6));
        canvas.drawLine(const Offset(34, 28), const Offset(106, 39),
            _stroke(_inkGreen, 1.8));
        _caption(canvas, 'plan B is decided before 3am');
        break;
      case 6: // Circuit breaker — stop calling a dead service.
        canvas.drawLine(
            const Offset(8, 26), const Offset(52, 26), _stroke(_inkBright, 1.5));
        canvas.drawLine(const Offset(52, 26), const Offset(74, 12),
            _stroke(_inkRed, 1.8));
        canvas.drawLine(const Offset(96, 26), const Offset(142, 26),
            _stroke(_inkDim.withValues(alpha: 0.4), 1.5));
        canvas.drawCircle(const Offset(52, 26), 3, _fill(_inkRed));
        canvas.drawCircle(const Offset(96, 26), 3,
            _fill(_inkDim.withValues(alpha: 0.5)));
        _diagText(canvas, 'OPEN',
            centerX: 74, top: 28, color: _inkRed, size: 7.5, width: 60);
        _caption(canvas, 'fail fast instead of piling up');
        break;
      case 7: // Validation — parse before you trust.
        _chip(canvas, const Rect.fromLTWH(8, 14, 86, 22), '{ "ok": true }',
            _inkGreen);
        canvas.drawPath(
          Path()
            ..moveTo(108, 26)
            ..lineTo(115, 33)
            ..lineTo(130, 15),
          _stroke(_inkGreen, 2.4),
        );
        _caption(canvas, 'schema-checked before use');
        break;
      case 8: // Evals — a golden set gates the release.
        for (var i = 0; i < 10; i++) {
          final rect = Rect.fromLTWH(8 + i * 13.6, 14, 11, 18);
          if (i < 6) {
            canvas.drawRRect(
              RRect.fromRectAndRadius(rect, const Radius.circular(2)),
              _fill(_inkGreen.withValues(alpha: 0.85)),
            );
          } else if (i == 6) {
            canvas.drawRRect(
              RRect.fromRectAndRadius(rect, const Radius.circular(2)),
              _fill(_inkRed),
            );
          } else {
            _diagBox(canvas, rect,
                border: _inkDim.withValues(alpha: 0.45),
                radius: 2,
                stroke: 1.1);
          }
        }
        _caption(canvas, 'one bad case stops the ship');
        break;
      case 9: // Guardrails — filter both directions.
        _chip(canvas, const Rect.fromLTWH(54, 12, 42, 24), 'Engel', _inkBright);
        _diagArrow(canvas, const [Offset(6, 24), Offset(52, 24)],
            color: _inkAmber, stroke: 1.4, head: 5);
        _diagArrow(canvas, const [Offset(98, 24), Offset(144, 24)],
            color: _inkAmber, stroke: 1.4, head: 5);
        for (final x in const [34.0, 116.0]) {
          for (final dy in const [-7.0, 0.0, 7.0]) {
            canvas.drawLine(
              Offset(x, 24 + dy - 3),
              Offset(x, 24 + dy + 3),
              _stroke(_inkAmber, 1.6),
            );
          }
        }
        _caption(canvas, 'filter in, filter out, every call');
        break;
      case 10: // Observability — traces, tokens, spend.
        const spans = <(double, double, double, Color)>[
          (8, 10, 46, _inkViolet),
          (22, 19, 30, _inkGreen),
          (34, 28, 74, Color(0xff5b9dff)),
          (66, 37, 22, _inkAmber),
        ];
        for (final span in spans) {
          canvas.drawRRect(
            RRect.fromRectAndRadius(
              Rect.fromLTWH(span.$1, span.$2, span.$3, 6),
              const Radius.circular(3),
            ),
            _fill(span.$4.withValues(alpha: 0.9)),
          );
        }
        _caption(canvas, 'every turn writes its own receipt');
        break;
      case 11: // Model versions — pin it, shadow the next one.
        _chip(canvas, const Rect.fromLTWH(4, 16, 44, 20), 'traffic', _inkBright);
        _chip(canvas, const Rect.fromLTWH(88, 4, 58, 18), 'v1 pinned', _inkGreen);
        _chip(canvas, const Rect.fromLTWH(88, 30, 58, 18), 'v2 shadow', _inkAmber,
            dashed: true);
        canvas.drawLine(
            const Offset(48, 26), const Offset(88, 13), _stroke(_inkGreen, 1.8));
        _dashPath(
          canvas,
          Path()
            ..moveTo(48, 26)
            ..lineTo(88, 39),
          _stroke(_inkAmber, 1.4),
        );
        _caption(canvas, "never let 'latest' pick itself");
        break;
      case 12: // Rollout — canary, compare, roll back.
        canvas.drawRRect(
          RRect.fromRectAndRadius(
              const Rect.fromLTWH(8, 14, 134, 10), const Radius.circular(5)),
          _fill(const Color(0xff1c2331)),
        );
        canvas.drawRRect(
          RRect.fromRectAndRadius(
              const Rect.fromLTWH(8, 14, 34, 10), const Radius.circular(5)),
          _fill(_inkViolet),
        );
        for (var i = 0; i < 4; i++) {
          final x = 42.0 + i * 33;
          canvas.drawCircle(
            Offset(x, 33),
            3.2,
            i == 0
                ? _fill(_inkViolet)
                : _fill(_inkDim.withValues(alpha: 0.45)),
          );
        }
        _caption(canvas, 'ship small, watch, then widen');
        break;
      default:
        break;
    }
  }
}
