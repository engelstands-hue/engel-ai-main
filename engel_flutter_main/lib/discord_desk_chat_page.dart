import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

/// Discord chat duplicated onto Engel AI Main.
///
/// The mouth row shows a live presence beside each icon. Desk manager is a
/// separate module that pops out from this page.
class EngelDiscordMouth {
  const EngelDiscordMouth({
    required this.name,
    required this.presence,
    required this.color,
    required this.mark,
  });

  final String name;
  final String presence;
  final Color color;
  final String mark;
}

const engelDiscordMouths = <EngelDiscordMouth>[
  EngelDiscordMouth(
    name: 'Engel AI Main',
    presence: 'Online',
    color: Color(0xff3d7ea6),
    mark: 'E',
  ),
  EngelDiscordMouth(
    name: 'Community',
    presence: 'Online',
    color: Color(0xff7a4ea3),
    mark: 'C',
  ),
  EngelDiscordMouth(
    name: 'Ops',
    presence: 'Online',
    color: Color(0xff2f6f86),
    mark: 'O',
  ),
  EngelDiscordMouth(
    name: 'Architect',
    presence: 'Online',
    color: Color(0xff8a5a2f),
    mark: 'A',
  ),
  EngelDiscordMouth(
    name: 'Memory',
    presence: 'Online',
    color: Color(0xff6a4a8a),
    mark: 'M',
  ),
  EngelDiscordMouth(
    name: 'Builder',
    presence: 'Online',
    color: Color(0xff8a3d3d),
    mark: 'B',
  ),
  EngelDiscordMouth(
    name: 'Proof',
    presence: 'Online',
    color: Color(0xff3d6a4a),
    mark: 'V',
  ),
  EngelDiscordMouth(
    name: 'Training',
    presence: 'Online',
    color: Color(0xff4a5a8a),
    mark: 'T',
  ),
  EngelDiscordMouth(
    name: 'Product',
    presence: 'Online',
    color: Color(0xff2f7d5a),
    mark: 'P',
  ),
  EngelDiscordMouth(
    name: 'Research',
    presence: 'Online',
    color: Color(0xff3a6ea5),
    mark: 'R',
  ),
  EngelDiscordMouth(
    name: 'Sales',
    presence: 'Online',
    color: Color(0xff1f8a78),
    mark: 'S',
  ),
  EngelDiscordMouth(
    name: 'Support',
    presence: 'Online',
    color: Color(0xff2a7a62),
    mark: 'U',
  ),
];

class EngelRoomLine {
  const EngelRoomLine({required this.author, required this.text});

  final String author;
  final String text;
}

class EngelDiscordChatPage extends StatefulWidget {
  const EngelDiscordChatPage({super.key, this.live = true});

  /// When false, the page stays on the quiet line and does not call the server.
  final bool live;

  @override
  State<EngelDiscordChatPage> createState() => _EngelDiscordChatPageState();
}

class _EngelDiscordChatPageState extends State<EngelDiscordChatPage> {
  List<EngelRoomLine> _lines = const [];
  Timer? _poll;
  HttpClient? _client;
  bool _pulling = false;
  bool _openingDesk = false;

  @override
  void initState() {
    super.initState();
    if (!widget.live) {
      return;
    }
    _client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 2)
      ..idleTimeout = const Duration(seconds: 5)
      ..maxConnectionsPerHost = 1;
    _pull();
    _poll = Timer.periodic(const Duration(seconds: 15), (_) => _pull());
  }

  @override
  void dispose() {
    _poll?.cancel();
    _client?.close(force: true);
    _client = null;
    super.dispose();
  }

  Future<void> _pull() async {
    if (_pulling || !mounted) {
      return;
    }
    final client = _client;
    if (client == null) {
      return;
    }
    _pulling = true;
    try {
      final request = await client.getUrl(
        Uri.parse('http://127.0.0.1:24680/discord/room'),
      );
      final response = await request.close().timeout(const Duration(seconds: 3));
      final raw = await response.transform(utf8.decoder).join();
      final decoded = jsonDecode(raw);
      if (decoded is! Map) {
        return;
      }
      final rows = decoded['lines'];
      if (rows is! List) {
        return;
      }
      final next = <EngelRoomLine>[];
      for (final row in rows) {
        if (row is! Map) {
          continue;
        }
        final text = '${row['text'] ?? ''}'.trim();
        if (text.isEmpty) {
          continue;
        }
        next.add(
          EngelRoomLine(
            author: '${row['author'] ?? 'unknown'}'.trim(),
            text: text,
          ),
        );
      }
      if (!mounted) {
        return;
      }
      setState(() => _lines = next);
    } catch (_) {
      // Keep the last good lines. A missed poll is not an empty room.
    } finally {
      _pulling = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Discord chat',
                  style: TextStyle(
                    color: Color(0xfff7f8fb),
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              FilledButton.icon(
                key: const Key('discord-desk-manager-button'),
                onPressed: detachDeskManager,
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Desk manager'),
              ),
            ],
          ),
          const SizedBox(height: 4),
          const Text(
            'Same mouths as Discord, on Engel AI Main. Presence sits beside each icon.',
            style: TextStyle(color: Color(0xff9aa3b2)),
          ),
          const SizedBox(height: 14),
          SizedBox(
            height: 92,
            child: ListView.separated(
              key: const Key('discord-mouth-row'),
              scrollDirection: Axis.horizontal,
              itemCount: engelDiscordMouths.length,
              separatorBuilder: (_, _) => const SizedBox(width: 12),
              itemBuilder: (context, index) {
                final mouth = engelDiscordMouths[index];
                return _MouthChip(mouth: mouth);
              },
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: const Color(0xC41e2533),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0x66ffffff)),
              ),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: _lines.isEmpty
                    ? const Text(
                        'The room is quiet. No desk is speaking.',
                        style: TextStyle(color: Color(0xfff7f8fb)),
                      )
                    : ListView.separated(
                        key: const Key('discord-room-lines'),
                        itemCount: _lines.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 8),
                        itemBuilder: (context, index) {
                          final line = _lines[index];
                          return Text(
                            '${line.author}: ${line.text}',
                            style: const TextStyle(color: Color(0xfff7f8fb)),
                          );
                        },
                      ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void detachDeskManager() {
    if (_openingDesk) {
      return;
    }
    _openingDesk = true;
    unawaited(_openDeskOnce());
  }

  Future<void> _openDeskOnce() async {
    try {
      if (Platform.isWindows) {
        final result = await Process.run('powershell', const [
          '-NoProfile',
          '-Command',
          "(Get-CimInstance Win32_Process -Filter \"Name='EngelAIMain.exe'\" | Where-Object { \$_.CommandLine -like '*--desk-manager*' } | Select-Object -First 1 -ExpandProperty ProcessId)",
        ]);
        if (result.stdout.toString().trim().isNotEmpty) {
          return;
        }
      }
      await Process.start(Platform.resolvedExecutable, const ['--desk-manager']);
    } catch (_) {
      // A failed pop-out must not leave the button stuck.
    } finally {
      _openingDesk = false;
    }
  }
}

class _MouthChip extends StatelessWidget {
  const _MouthChip({required this.mouth});

  final EngelDiscordMouth mouth;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 118,
      child: Column(
        children: [
          CircleAvatar(
            radius: 22,
            backgroundColor: mouth.color,
            child: Text(
              mouth.mark,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            mouth.presence,
            key: Key('discord-presence-${mouth.name}'),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Color(0xffd5dbe6),
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _DeskTune {
  const _DeskTune({
    required this.id,
    required this.name,
    required this.sentiment,
    required this.topic,
    required this.inactivity,
  });

  final String id;
  final String name;
  final double sentiment;
  final double topic;
  final double inactivity;
}

const _deskTunes = <_DeskTune>[
  _DeskTune(id: 'research', name: 'Research', sentiment: 0.75, topic: 0.86, inactivity: 0.11),
  _DeskTune(id: 'product', name: 'Product', sentiment: 0.75, topic: 0.83, inactivity: 0.11),
  _DeskTune(id: 'community', name: 'Community', sentiment: 0.70, topic: 0.70, inactivity: 0.11),
  _DeskTune(id: 'support', name: 'Support', sentiment: 0.80, topic: 0.84, inactivity: 0.20),
  _DeskTune(id: 'sales', name: 'Sales', sentiment: 0.72, topic: 0.80, inactivity: 0.11),
  _DeskTune(id: 'ops', name: 'Ops', sentiment: 0.74, topic: 0.88, inactivity: 0.11),
  _DeskTune(id: 'architect', name: 'Architect', sentiment: 0.55, topic: 0.80, inactivity: 0.20),
  _DeskTune(id: 'memory', name: 'Memory', sentiment: 0.60, topic: 0.70, inactivity: 0.20),
  _DeskTune(id: 'builder', name: 'Builder', sentiment: 0.50, topic: 0.85, inactivity: 0.15),
  _DeskTune(id: 'proof', name: 'Proof', sentiment: 0.45, topic: 0.90, inactivity: 0.15),
  _DeskTune(id: 'training', name: 'Training', sentiment: 0.50, topic: 0.75, inactivity: 0.20),
];

class _DeskScore {
  const _DeskScore({required this.score, required this.state, required this.margin});

  final double score;
  final String state;
  final double margin;
}

_DeskScore _scoreDesk({
  required _DeskTune desk,
  required double threshold,
  required double sentimentWeight,
  required double topicWeight,
}) {
  final inactivityWeight = (1 - sentimentWeight - topicWeight).clamp(0.0, 1.0);
  final scale = sentimentWeight + topicWeight + inactivityWeight;
  final combined = scale == 0
      ? 0.0
      : ((desk.sentiment * sentimentWeight) +
              (desk.topic * topicWeight) +
              (desk.inactivity * inactivityWeight)) /
          scale;
  final score = (combined * 1000).roundToDouble() / 10;
  final raw = ((score - threshold) * 10).roundToDouble() / 10;
  final state = raw >= 0 && desk.topic > 0 ? 'Activate' : 'Hold';
  return _DeskScore(score: score, state: state, margin: raw);
}

class _DeskManagerPopout extends StatefulWidget {
  const _DeskManagerPopout();

  @override
  State<_DeskManagerPopout> createState() => _DeskManagerPopoutState();
}

class _DeskManagerPopoutState extends State<_DeskManagerPopout> {
  String _deskId = 'product';
  double _threshold = 61;
  double _sentimentWeight = 0.20;
  double _topicWeight = 0.60;

  File get _settingsFile => File(
        '${File(Platform.resolvedExecutable).parent.path}${Platform.pathSeparator}desk_manager_settings.json',
      );

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    try {
      final file = _settingsFile;
      if (!file.existsSync()) return;
      final data = jsonDecode(file.readAsStringSync());
      if (data is! Map) return;
      final desk = data['desk'];
      if (desk is String && _deskTunes.any((row) => row.id == desk)) {
        _deskId = desk;
      }
      _threshold = (data['threshold'] as num?)?.toDouble() ?? _threshold;
      _sentimentWeight = (data['sentiment'] as num?)?.toDouble() ?? _sentimentWeight;
      _topicWeight = (data['topic'] as num?)?.toDouble() ?? _topicWeight;
      _keepWeights();
    } catch (_) {}
  }

  void _keepWeights() {
    _threshold = _threshold.clamp(40, 90);
    _topicWeight = _topicWeight.clamp(0.1, 0.8);
    _sentimentWeight = _sentimentWeight.clamp(0.0, (1 - _topicWeight).clamp(0.0, 0.8));
  }

  void _save() {
    _keepWeights();
    try {
      _settingsFile.writeAsStringSync(
        jsonEncode({
          'desk': _deskId,
          'threshold': _threshold,
          'sentiment': _sentimentWeight,
          'topic': _topicWeight,
        }),
      );
    } catch (_) {}
  }

  _DeskTune get _desk => _deskTunes.firstWhere((desk) => desk.id == _deskId);

  @override
  Widget build(BuildContext context) {
    final scored = _scoreDesk(
      desk: _desk,
      threshold: _threshold,
      sentimentWeight: _sentimentWeight,
      topicWeight: _topicWeight,
    );
    final margin = scored.margin;
    return DecoratedBox(
      key: const Key('discord-desk-manager-popout'),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: const Color(0x66ffaaaa)),
            gradient: const LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xB05c121c), Color(0xE01c060a)],
            ),
          ),
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Expanded(
                      child: Text(
                        'Desk manager',
                        style: TextStyle(
                          color: Color(0xfff6e8e8),
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
                const Text(
                  'Select a bot, then move the weights. The score follows that desk.',
                  style: TextStyle(color: Color(0xffc9a3a6)),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final desk in _deskTunes)
                      ChoiceChip(
                        key: Key('desk-select-${desk.id}'),
                        label: Text(desk.name),
                        selected: desk.id == _deskId,
                        onSelected: (_) => setState(() {
                          _deskId = desk.id;
                          _save();
                        }),
                        selectedColor: const Color(0xffb41c2a),
                        backgroundColor: const Color(0x663c0c12),
                        labelStyle: const TextStyle(color: Color(0xfff6e8e8)),
                        side: const BorderSide(color: Color(0x66ffaaaa)),
                      ),
                  ],
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    _GlassStat(
                      label: 'Initiative score',
                      value: scored.score.toStringAsFixed(1),
                    ),
                    _GlassStat(label: 'Evaluation state', value: scored.state),
                    _GlassStat(
                      label: 'Activation margin',
                      value: '${margin > 0 ? '+' : ''}${margin.toStringAsFixed(1)}',
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                _WeightSlider(
                  label: 'Activation threshold',
                  value: _threshold,
                  min: 40,
                  max: 90,
                  display: '${_threshold.round()}%',
                  onChanged: (value) => setState(() {
                    _threshold = value;
                    _save();
                  }),
                ),
                _WeightSlider(
                  label: 'Sentiment weight',
                  value: _sentimentWeight,
                  min: 0,
                  max: (1 - _topicWeight).clamp(0.0, 0.8),
                  display: _sentimentWeight.toStringAsFixed(2),
                  onChanged: (value) => setState(() {
                    _sentimentWeight = value;
                    _save();
                  }),
                ),
                _WeightSlider(
                  label: 'Topic relevance weight',
                  value: _topicWeight,
                  min: 0.1,
                  max: (1 - _sentimentWeight).clamp(0.1, 0.8),
                  display: _topicWeight.toStringAsFixed(2),
                  onChanged: (value) => setState(() {
                    _topicWeight = value;
                    _save();
                  }),
                ),
                Text(
                  'Inactivity weight ${(1 - _sentimentWeight - _topicWeight).clamp(0.0, 1.0).toStringAsFixed(2)}  ·  saved',
                  style: const TextStyle(color: Color(0xffc9a3a6)),
                ),
              ],
            ),
          ),
    );
  }
}

class EngelDeskManagerApp extends StatelessWidget {
  const EngelDeskManagerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        backgroundColor: Color(0xff1c060a),
        body: _DeskManagerPopout(),
      ),
    );
  }
}

class _WeightSlider extends StatelessWidget {
  const _WeightSlider({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.display,
    required this.onChanged,
  });

  final String label;
  final double value;
  final double min;
  final double max;
  final String display;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(label, style: const TextStyle(color: Color(0xffc9a3a6))),
            ),
            Text(display, style: const TextStyle(color: Color(0xfff6e8e8))),
          ],
        ),
        Slider(
          value: value.clamp(min, max),
          min: min,
          max: max,
          activeColor: const Color(0xffc81e3a),
          onChanged: onChanged,
        ),
      ],
    );
  }
}

class _GlassStat extends StatelessWidget {
  const _GlassStat({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 180,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0x6628080c),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0x33ffb4b4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Color(0xffc9a3a6), fontSize: 12)),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(
              color: Color(0xfff6e8e8),
              fontSize: 22,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}
