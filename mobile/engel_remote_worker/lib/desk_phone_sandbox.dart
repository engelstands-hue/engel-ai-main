import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// Desk working room on the phone. Discord is not installed here.
///
/// The shared seed is the Download folder (ADB can write it). The worker
/// then uses that folder when it is writable, otherwise the app's own
/// storage on this phone. The server copy is only a pointer.
class DeskPhoneSandbox {
  static const downloadRoot =
      '/storage/emulated/0/Download/EngelRemoteWorker/desks';

  static const desksForWorker = <String, List<String>>{
    'android_worker_alpha': <String>[
      'research',
      'product',
      'architect',
      'training',
    ],
    'android_worker_beta': <String>['support', 'ops', 'builder'],
    'android_worker_gamma': <String>['community', 'sales', 'memory', 'proof'],
  };

  static String? deskFromInstructions(String instructions) {
    final match = RegExp(
      r'Desk origin:.*\(([a-z]+)\)',
      caseSensitive: false,
    ).firstMatch(instructions);
    final desk = match?.group(1)?.trim().toLowerCase() ?? '';
    if (desk.isEmpty || desk == 'main') return null;
    return desk;
  }

  static Future<void> ensureForWorker(String workerId) async {
    for (final desk in desksForWorker[workerId] ?? const <String>[]) {
      await ensureDesk(desk, workerId);
    }
  }

  static Future<Directory> ensureDesk(String desk, String workerId) async {
    final name = desk.trim().toLowerCase();
    final room = await _writableRoom(name);
    for (final rel in <String>[
      'wiki',
      'sandbox/inbox',
      'sandbox/work',
      'sandbox/journal',
      'sandbox/collab',
    ]) {
      await Directory('${room.path}/$rel').create(recursive: true);
    }
    await _writeIfEmpty(
      File('${room.path}/sandbox/README.md'),
      '# $name sandbox\n\n'
          'This working room is on the phone. It is not Wiki One for Engel AI Main.\n'
          'Discord is not installed on this phone.\n'
          'Read wiki/ONE.md, inbox, work, and journal before you draft.\n'
          'Append journal/turns.jsonl after a draft.\n'
          'You cannot approve protected actions, start a training run, or apply a patch.\n',
    );
    await _writeIfEmpty(
      File('${room.path}/sandbox/work/OPEN.md'),
      '# Open work for $name\n\n'
          'No filed ask yet. New asks land in inbox/LAST_ASK.md.\n'
          'Write the draft result here. Do not leave the canned charter here.\n',
    );
    await _writeIfEmpty(
      File('${room.path}/wiki/ONE.md'),
      '# Engel $name second brain\n\n'
          'This file lives on the phone sandbox for $name.\n'
          'Worker: $workerId\n'
          'Authority: Josh > Guardian > Engel/runtime\n'
          'Speak as this desk. Do not speak as Engel AI Main.\n',
    );
    final charter = File('${room.path}/sandbox/CHARTER.json');
    if (!await charter.exists()) {
      await charter.writeAsString(
        '${jsonEncode(<String, Object>{'desk': name, 'worker_id': workerId, 'discord_on_phone': false})}\n',
      );
    }
    return room;
  }

  static Future<void> fileAsk(String desk, String prompt) async {
    final body = prompt.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (body.isEmpty) return;
    final room = await ensureDesk(desk, '');
    final clipped = body.length > 800 ? body.substring(0, 800) : body;
    await File('${room.path}/sandbox/inbox/LAST_ASK.md').writeAsString(
      '$clipped\n',
    );
  }

  static Future<void> note(String desk, String kind, String text) async {
    final body = text.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (body.isEmpty) return;
    final room = await ensureDesk(desk, '');
    final path = File('${room.path}/sandbox/journal/turns.jsonl');
    final clipped = body.length > 500 ? body.substring(0, 500) : body;
    final row = jsonEncode(<String, String>{
      'at': DateTime.now().toUtc().toIso8601String(),
      'desk': desk,
      'kind': kind,
      'text': clipped,
    });
    await path.writeAsString('$row\n', mode: FileMode.append);
  }

  static Future<String> brief(String desk) async {
    final room = await _writableRoom(desk.trim().toLowerCase());
    if (!await room.exists()) return '';
    final parts = <String>['phone sandbox: ${room.path}'];
    final ask = File('${room.path}/sandbox/inbox/LAST_ASK.md');
    final openWork = File('${room.path}/sandbox/work/OPEN.md');
    if (await ask.exists()) {
      parts.add('last ask: ${_clip(await ask.readAsString(), 220)}');
    }
    if (await openWork.exists()) {
      parts.add('open work: ${_clip(await openWork.readAsString(), 220)}');
    }
    final journal = File('${room.path}/sandbox/journal/turns.jsonl');
    if (await journal.exists()) {
      final lines = (await journal.readAsString())
          .split('\n')
          .where((line) => line.trim().isNotEmpty)
          .toList();
      if (lines.isNotEmpty) {
        parts.add('journal: ${_clip(lines.last, 240)}');
      }
    }
    final joined = parts.join(' | ');
    return joined.length > 900 ? joined.substring(0, 900) : joined;
  }

  static Future<Directory> _writableRoom(String desk) async {
    final download = Directory('$downloadRoot/$desk');
    final probe = File('${download.path}/sandbox/.write_probe');
    try {
      await Directory('${download.path}/sandbox').create(recursive: true);
      await probe.writeAsString('ok');
      try {
        await probe.delete();
      } catch (_) {}
      return download;
    } catch (_) {
      final support = await getApplicationSupportDirectory();
      return Directory('${support.path}/desk_sandboxes/$desk');
    }
  }

  static Future<void> _writeIfEmpty(File file, String text) async {
    if (await file.exists() && await file.length() > 0) return;
    await file.parent.create(recursive: true);
    await file.writeAsString(text);
  }

  static String _clip(String raw, int cap) {
    final text = raw.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (text.length <= cap) return text;
    return text.substring(0, cap);
  }
}
