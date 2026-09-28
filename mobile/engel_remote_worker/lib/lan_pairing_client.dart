import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dart_style/dart_style.dart';
import 'package:diff_match_patch/diff_match_patch.dart';
import 'package:html/parser.dart' as html_parser;
import 'package:http/http.dart' as http;
import 'package:markdown/markdown.dart' as markdown;
import 'package:path_provider/path_provider.dart';

import 'conical_task_analyzer.dart';
import 'desk_phone_sandbox.dart';
import 'worker_capability_probe.dart';

class LanPairingClient {
  LanPairingClient({
    this.timeout = const Duration(seconds: 12),
    String? workerId,
    String? workerName,
    String? phoneModel,
  }) : workerId = workerId ?? _resolveWorkerId(),
       workerName = workerName ?? 'Android Worker',
       phoneModel = phoneModel ?? 'unknown device';

  final Duration timeout;
  final String workerId;
  final String workerName;
  final String phoneModel;

  // Per-phone worker_id is read from the app's external-app-scoped config
  // (writable by ADB without MANAGE_EXTERNAL_STORAGE). Defaults to
  // 'android_worker_alpha' for back-compat when the file is missing.
  static const String _identityConfigPath =
      '/storage/emulated/0/Android/data/com.example.engel_remote_worker/files/worker_identity.json';
  static const String _internalIdentityConfigPath =
      '/data/user/0/com.example.engel_remote_worker/files/worker_identity.json';
  static const String _defaultWorkerId = 'android_worker_alpha';
  static const Set<String> _allowedWorkerIds = <String>{
    'android_worker_alpha',
    'android_worker_beta',
    'android_worker_gamma',
  };

  static String _resolveWorkerId() {
    try {
      final file = File(_identityConfigPath).existsSync()
          ? File(_identityConfigPath)
          : File(_internalIdentityConfigPath);
      if (file.existsSync()) {
        final decoded = jsonDecode(file.readAsStringSync());
        if (decoded is Map<String, Object?>) {
          final id = decoded['worker_id'];
          if (id is String && _allowedWorkerIds.contains(id)) {
            return id;
          }
        }
      }
    } catch (_) {
      // fall through to default
    }
    return _defaultWorkerId;
  }

  Future<LanPairingResult> testHealth({
    required String host,
    required int port,
  }) async {
    return _request(method: 'GET', host: host, port: port, path: '/health');
  }

  Future<LanPairingResult> testPairing({
    required String host,
    required int port,
    required String pairingCode,
  }) async {
    return _request(
      method: 'POST',
      host: host,
      port: port,
      path: '/pair',
      body: <String, Object?>{
        'pairing_code': pairingCode,
        'worker_device': 'engel_remote_worker_flutter',
        'worker_id': workerId,
        'phone_model': phoneModel,
        'app_version': 'remote_worker_phase12_link_manager',
        'platform': Platform.operatingSystem,
        'current_mode': 'dedicated_engel_phone_foreground',
        'client_mode': 'local_draft_mode',
      },
    );
  }

  Future<LanPairingResult> workerStatus({
    required String host,
    required int port,
    required String pairingCode,
  }) async {
    return _request(
      method: 'GET',
      host: host,
      port: port,
      path: '/worker/status',
      queryParameters: _workerQuery(pairingCode),
    );
  }

  Future<LanPairingResult> nextAssignment({
    required String host,
    required int port,
    required String pairingCode,
  }) async {
    return _request(
      method: 'GET',
      host: host,
      port: port,
      path: '/worker/next-assignment',
      queryParameters: _workerQuery(pairingCode),
    );
  }

  Future<LanPairingResult> sendChat({
    required String host,
    required int port,
    required String pairingCode,
    required String message,
  }) async {
    return _request(
      method: 'POST',
      host: host,
      port: port,
      path: '/chat',
      body: <String, Object?>{
        'pairing_code': pairingCode,
        'worker_device': 'engel_remote_worker_flutter',
        'message': message,
      },
    );
  }

  Future<LanPairingResult> returnDraftResult({
    required String host,
    required int port,
    required String pairingCode,
    required Map<String, Object?> assignment,
  }) async {
    final cleanupBefore = await _cleanupWorkerJobCache();
    final packetId = assignment['packet_id']?.toString() ?? 'unknown';
    final title = assignment['title']?.toString() ?? 'Untitled assignment';
    final taskType = assignment['task_type']?.toString() ?? 'review_status';
    final instructions = assignment['instructions']?.toString() ?? '';
    final sourceSummary = assignment['source_summary']?.toString() ?? '';
    final capabilities = await const WorkerCapabilityProbe().collect(
      workerId: workerId,
      workerName: workerName,
      phoneModel: phoneModel,
    );
    final desk = DeskPhoneSandbox.deskFromInstructions(instructions);
    var sandboxBrief = '';
    if (desk != null) {
      await DeskPhoneSandbox.ensureDesk(desk, workerId);
      await DeskPhoneSandbox.fileAsk(desk, instructions);
      sandboxBrief = await DeskPhoneSandbox.brief(desk);
    }
    var draft = await _draftForAssignment(
      taskType: taskType,
      title: title,
      instructions: instructions,
      sourceSummary: sourceSummary,
      capabilities: capabilities,
    );
    if (desk != null) {
      if (sandboxBrief.isNotEmpty && !draft.contains('Phone sandbox:')) {
        draft = 'Phone sandbox: $sandboxBrief\n\n$draft';
      }
      await DeskPhoneSandbox.note(desk, taskType, draft);
    }
    try {
      return await _request(
        method: 'POST',
        host: host,
        port: port,
        path: '/worker/return-result',
        body: <String, Object?>{
          'pairing_code': pairingCode,
          'result_version': '1',
          'packet_id': packetId,
          'worker_device': 'engel_remote_worker_flutter',
          'worker_id': workerId,
          'trust_level': 'untrusted_until_engel_review',
          'result_type': '${taskType}_draft_result',
          'draft_text': draft,
          'device_capabilities': capabilities,
          'worker_cache_cleanup': <String, Object?>{
            'before_job_removed': cleanupBefore,
            'after_job_policy': 'run_after_result_return',
            'preserves': <String>[
              'worker_identity.json',
              'worker_connection.json',
              'Download/EngelRemoteWorker/desks',
            ],
          },
          'requires_review': true,
          'safe_to_auto_apply': false,
          'auto_generated': true,
        },
      );
    } finally {
      await _cleanupWorkerJobCache();
    }
  }

  Future<int> _cleanupWorkerJobCache() async {
    var removed = 0;
    try {
      final temp = await getTemporaryDirectory();
      removed += await _deleteChildrenWithPrefixes(temp, const <String>[
        'engel_worker_',
        'engel_remote_worker_',
        'flutter_engel_worker_',
      ]);
      removed += await _deleteDirectoryTreeIfPresent(
        Directory('${temp.path}/engel_worker_job_cache'),
      );
      removed += await _deleteDirectoryTreeIfPresent(
        Directory('${temp.path}/engel_worker_scratch'),
      );
      removed += await _deleteDirectoryTreeIfPresent(
        Directory('${temp.path}/engel_creation_artifacts'),
      );
    } catch (_) {
      // Cache cleanup should never block a worker result.
    }
    try {
      final support = await getApplicationSupportDirectory();
      removed += await _deleteDirectoryTreeIfPresent(
        Directory('${support.path}/engel_creation_artifacts'),
      );
      removed += await _deleteDirectoryTreeIfPresent(
        Directory('${support.path}/engel_job_cache'),
      );
      removed += await _deleteDirectoryTreeIfPresent(
        Directory('${support.path}/engel_worker_job_cache'),
      );
      removed += await _deleteDirectoryTreeIfPresent(
        Directory('${support.path}/engel_worker_scratch'),
      );
      removed += await _pruneDirectory(
        Directory('${support.path}/engel_capability_snapshots'),
        keepNewest: 3,
      );
    } catch (_) {
      // App support cleanup is best effort; identity/config are not touched.
    }
    return removed;
  }

  Future<int> _deleteChildrenWithPrefixes(
    Directory root,
    List<String> prefixes,
  ) async {
    if (!await root.exists()) return 0;
    var removed = 0;
    await for (final entity in root.list(followLinks: false)) {
      final segments = entity.uri.pathSegments
          .where((segment) => segment.isNotEmpty)
          .toList(growable: false);
      if (segments.isEmpty) continue;
      final name = segments.last;
      if (!prefixes.any((prefix) => name.startsWith(prefix))) continue;
      removed += await _deleteEntityTree(entity);
    }
    return removed;
  }

  Future<int> _deleteDirectoryTreeIfPresent(Directory directory) async {
    try {
      if (!await directory.exists()) return 0;
      return await _deleteEntityTree(directory);
    } catch (_) {
      return 0;
    }
  }

  Future<int> _deleteEntityTree(FileSystemEntity entity) async {
    var removed = 0;
    try {
      final type = await FileSystemEntity.type(entity.path, followLinks: false);
      if (type == FileSystemEntityType.directory) {
        final directory = Directory(entity.path);
        try {
          await for (final child in directory.list(followLinks: false)) {
            removed += await _deleteEntityTree(child);
          }
        } catch (_) {
          // Fall through to a recursive delete attempt below.
        }
        try {
          await directory.delete();
          removed += 1;
        } catch (_) {
          try {
            await directory.delete(recursive: true);
            removed += 1;
          } catch (_) {
            // Leave locked directories for the next job cleanup pass.
          }
        }
        return removed;
      }
      await entity.delete();
      return 1;
    } catch (_) {
      return removed;
    }
  }

  Future<int> _pruneDirectory(
    Directory directory, {
    required int keepNewest,
  }) async {
    try {
      if (!await directory.exists()) return 0;
      final entries = <FileSystemEntity>[];
      await for (final entity in directory.list(followLinks: false)) {
        entries.add(entity);
      }
      final dated = <({FileSystemEntity entity, DateTime changed})>[];
      for (final entity in entries) {
        try {
          dated.add((
            entity: entity,
            changed: await entity.stat().then((s) => s.modified),
          ));
        } catch (_) {
          dated.add((
            entity: entity,
            changed: DateTime.fromMillisecondsSinceEpoch(0),
          ));
        }
      }
      dated.sort((a, b) => b.changed.compareTo(a.changed));
      var removed = 0;
      for (final item in dated.skip(keepNewest)) {
        removed += await _deleteEntityTree(item.entity);
      }
      return removed;
    } catch (_) {
      return 0;
    }
  }

  Future<String> _draftForAssignment({
    required String taskType,
    required String title,
    required String instructions,
    required String sourceSummary,
    required Map<String, Object?> capabilities,
  }) async {
    final text = _bounded('$instructions\n\n$sourceSummary', 3600);
    final bullets = _summaryBullets(text);
    final flags = _riskFlags(text);
    if (ConicalTaskAnalyzer.supports(taskType)) {
      return ConicalTaskAnalyzer.analyze(
        taskType: taskType,
        title: title,
        assignmentText: text,
      );
    }
    if (taskType == 'draft_code_artifact' || taskType == 'code_draft') {
      return _codeDraftArtifact(
        title: title,
        text: text,
        flags: flags,
        capabilities: capabilities,
      );
    }
    if (taskType == 'web_research_brief') {
      return _webResearchBrief(
        title: title,
        text: text,
        flags: flags,
        capabilities: capabilities,
      );
    }
    if (taskType == 'draft_candidate_json') {
      return const JsonEncoder.withIndent('  ').convert(<String, Object?>{
        'candidate_type': 'android_remote_worker_candidate',
        'title': title,
        'summary_bullets': bullets,
        'device_capabilities': capabilities,
        'warning_flags': flags,
        'status': 'candidate_only',
        'trusted_memory_write': false,
        'source_mutation': false,
        'patch_apply': false,
        'human_review_required': true,
      });
    }
    if (taskType == 'format_report_draft') {
      return [
        '# Android Remote Worker Report Draft',
        '',
        'Status: UNTRUSTED / CANDIDATE_ONLY / HUMAN_REVIEW_REQUIRED',
        '',
        '## $title',
        '',
        ...bullets.map((line) => '- $line'),
        '',
        '## Warning Flags',
        if (flags.isEmpty) '- none' else ...flags.map((line) => '- $line'),
        '',
        '## Device Capability Snapshot',
        '```json',
        const JsonEncoder.withIndent('  ').convert(capabilities),
        '```',
      ].join('\n');
    }
    if (taskType == 'return_status' ||
        taskType == 'return_logs' ||
        taskType == 'return_receipt' ||
        title.toLowerCase().contains('capability')) {
      return const JsonEncoder.withIndent('  ').convert(<String, Object?>{
        'candidate_type': 'android_worker_capability_status',
        'title': title,
        'device_capabilities': capabilities,
        'warning_flags': flags,
        'status': 'candidate_only',
        'human_review_required': true,
        'safe_to_auto_apply': false,
      });
    }
    if (taskType == 'classify_file' ||
        taskType == 'classify_untrusted_content') {
      return const JsonEncoder.withIndent('  ').convert(<String, Object?>{
        'classification': _classificationFor(text),
        'line_count': text
            .split('\n')
            .where((line) => line.trim().isNotEmpty)
            .length,
        'word_count': RegExp(r'\S+').allMatches(text).length,
        'char_count': text.length,
        'device_capabilities': capabilities,
        'warning_flags': flags,
        'human_review_required': true,
      });
    }
    if (taskType == 'compare_summaries') {
      return [
        '# Candidate Summary Comparison',
        '',
        ...bullets.map((line) => '- $line'),
        '',
        'Warning flags: ${flags.isEmpty ? 'none' : flags.join(', ')}',
      ].join('\n');
    }
    return [
      '# Candidate Draft',
      '',
      'UNTRUSTED / CANDIDATE_ONLY / HUMAN_REVIEW_REQUIRED',
      '',
      'Task: $title',
      '',
      ...bullets.map((line) => '- $line'),
      '',
      'Warning flags: ${flags.isEmpty ? 'none' : flags.join(', ')}',
      '',
      'Device capability snapshot:',
      const JsonEncoder.withIndent('  ').convert(capabilities),
    ].join('\n');
  }

  String _codeDraftArtifact({
    required String title,
    required String text,
    required List<String> flags,
    required Map<String, Object?> capabilities,
  }) {
    final language = _inferCodeLanguage(text);
    final original = _extractOriginalCode(text);
    final candidate = _candidateCodeFor(language, text);
    final templateMatched = candidate.isNotEmpty;
    if (!templateMatched) {
      // Honest no-match: the phone has no template for this request and must
      // not fabricate an unrelated snippet as if it were the asked-for code.
      return const JsonEncoder.withIndent('  ').convert(<String, Object?>{
        'candidate_type': 'android_worker_code_artifact',
        'title': title,
        'language': language,
        'template_match': false,
        'draft_source': 'on_device_template_v1',
        'unsupported_reason':
            'Requested code is outside the on-device template set; route to '
            'a desktop/server code lane or extend the phone templates.',
        'candidate_code': '',
        'warning_flags': flags,
        'status': 'candidate_only',
        'executes_code': false,
        'writes_source': false,
        'safe_to_auto_apply': false,
        'human_review_required': true,
      });
    }
    final formatted = language == 'dart'
        ? _formatDart(candidate)
        : _normalizeCode(candidate);
    final differ = DiffMatchPatch()..diffTimeout = 0.4;
    final diffs = differ.diff(original, formatted, false);
    differ.diffCleanupSemantic(diffs);
    final patch = patchToText(patchMake(original, b: formatted));
    final note = [
      '# Candidate Code Artifact',
      '',
      'Language: $language',
      '',
      '```$language',
      formatted,
      '```',
      '',
      'Status: candidate-only; review required before use.',
    ].join('\n');
    return const JsonEncoder.withIndent('  ').convert(<String, Object?>{
      'candidate_type': 'android_worker_code_artifact',
      'title': title,
      'language': language,
      'template_match': true,
      'draft_source': 'on_device_template_v1',
      'candidate_code': formatted,
      'markdown_preview_html': markdown.markdownToHtml(note),
      'diff_summary': diffs
          .map(
            (item) => <String, Object?>{
              'op': item.operation,
              'text': _bounded(item.text, 320),
            },
          )
          .toList(growable: false),
      'patch_text': _bounded(patch, 2400),
      'device_capabilities': capabilities,
      'warning_flags': flags,
      'status': 'candidate_only',
      'executes_code': false,
      'writes_source': false,
      'safe_to_auto_apply': false,
      'human_review_required': true,
    });
  }

  Future<String> _webResearchBrief({
    required String title,
    required String text,
    required List<String> flags,
    required Map<String, Object?> capabilities,
  }) async {
    final query = _searchQueryFor(title, text);
    final uri = Uri.https('html.duckduckgo.com', '/html/', <String, String>{
      'q': query,
    });
    final fetchedAt = DateTime.now().toUtc().toIso8601String();
    final results = <Map<String, Object?>>[];
    String? error;
    try {
      final response = await http
          .get(
            uri,
            headers: const <String, String>{
              'accept': 'text/html',
              'user-agent': 'EngelRemoteWorker/1.0 candidate-only research',
            },
          )
          .timeout(timeout);
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final document = html_parser.parse(response.body);
        for (final result in document.querySelectorAll('.result').take(5)) {
          final link = result.querySelector('a.result__a');
          final snippet = result.querySelector('.result__snippet');
          final titleText = link?.text.trim();
          final href = _normalizeDuckDuckGoUrl(link?.attributes['href']);
          if (titleText == null || titleText.isEmpty || href == null) {
            continue;
          }
          results.add(<String, Object?>{
            'title': _bounded(titleText, 180),
            'url': _bounded(href, 360),
            'snippet': _bounded(snippet?.text.trim() ?? '', 320),
          });
        }
      } else {
        error = 'search_http_${response.statusCode}';
      }
    } catch (caught) {
      error = '$caught';
    }
    if (results.isEmpty) {
      results.addAll(_pubPackageHints('$query $text'));
    }
    final briefMarkdown = [
      '# Candidate Web Research Brief',
      '',
      'Query: $query',
      '',
      if (results.isEmpty)
        '- No search results returned.'
      else
        ...results.map(
          (item) => '- ${item['title']} (${item['url']}): ${item['snippet']}',
        ),
      '',
      'Status: candidate-only; links and claims require Engel review.',
    ].join('\n');
    return const JsonEncoder.withIndent('  ').convert(<String, Object?>{
      'candidate_type': 'android_worker_web_research_brief',
      'title': title,
      'query': query,
      'fetched_at_utc': fetchedAt,
      'search_endpoint': 'https://html.duckduckgo.com/html/',
      'results': results,
      'error': error,
      'markdown_preview_html': markdown.markdownToHtml(briefMarkdown),
      'device_capabilities': capabilities,
      'warning_flags': flags,
      'status': 'candidate_only',
      'raw_page_saved': false,
      'provider_call': false,
      'safe_to_auto_apply': false,
      'human_review_required': true,
    });
  }

  String _inferCodeLanguage(String text) {
    final low = text.toLowerCase();
    if (low.contains('python') || low.contains('.py')) return 'python';
    if (low.contains('javascript') || low.contains('typescript')) {
      return 'javascript';
    }
    if (low.contains('powershell') || low.contains('ps1')) return 'powershell';
    if (low.contains('dart') || low.contains('flutter')) return 'dart';
    return 'python';
  }

  // The on-device code templates only genuinely cover these request shapes.
  // Anything else must be reported as template_match:false rather than
  // shipping an unrelated stub that pretends to be the requested code.
  static const _templateKeywords = [
    'normalize_device_record',
    'device record',
    'parse_int',
    'parse int',
    'clamppercent',
    'clamp percent',
    'summarize',
    'summary',
  ];

  bool _matchesTemplateKeyword(String low) =>
      _templateKeywords.any(low.contains);

  String _candidateCodeFor(String language, String text) {
    final low = text.toLowerCase();
    if (!_matchesTemplateKeyword(low)) return '';
    if (language == 'dart') {
      if (low.contains('normalize_device_record') ||
          low.contains('device record')) {
        return "Map<String, Object?> normalizeDeviceRecord(Map<Object?, Object?> record) {\n  final connectivity = record['connectivity'];\n  final bestFor = record['best_for'];\n  return <String, Object?>{\n    'worker_id': record['worker_id']?.toString() ?? '',\n    'model': record['model']?.toString() ?? record['configured_phone_model']?.toString() ?? '',\n    'wifi_ready': connectivity is Map && connectivity['wifi_or_lan_ready'] == true,\n    'best_for_count': bestFor is List ? bestFor.length : 0,\n  };\n}\n";
      }
      if (low.contains('parse_int') || low.contains('parse int')) {
        return "int parseIntCandidate(Object? value, {int defaultValue = 0}) {\n  if (value is int) return value;\n  return int.tryParse(value?.toString().trim() ?? '') ?? defaultValue;\n}\n";
      }
      if (low.contains('clamppercent') || low.contains('clamp percent')) {
        return 'int clampPercent(num value) {\n  if (value.isNaN) return 0;\n  return value.clamp(0, 100).round();\n}\n';
      }
      return 'String summarizeCandidate(String input) {\n  final trimmed = input.trim();\n  if (trimmed.length <= 220) return trimmed;\n  return "\${trimmed.substring(0, 220)}...";\n}\n';
    }
    if (language == 'javascript') {
      if (low.contains('normalize_device_record') ||
          low.contains('device record')) {
        return 'export function normalizeDeviceRecord(record = {}) {\n  const connectivity = record.connectivity ?? {};\n  const bestFor = Array.isArray(record.best_for) ? record.best_for : [];\n  return {\n    worker_id: String(record.worker_id ?? ""),\n    model: String(record.model ?? record.configured_phone_model ?? ""),\n    wifi_ready: connectivity.wifi_or_lan_ready === true,\n    best_for_count: bestFor.length,\n  };\n}\n';
      }
      if (low.contains('parse_int') || low.contains('parse int')) {
        return 'export function parseIntCandidate(value, defaultValue = 0) {\n  const parsed = Number.parseInt(String(value ?? "").trim(), 10);\n  return Number.isNaN(parsed) ? defaultValue : parsed;\n}\n';
      }
      return 'export function clampPercent(value) {\n  const number = Number(value);\n  if (!Number.isFinite(number)) return 0;\n  return Math.round(Math.min(100, Math.max(0, number)));\n}\n';
    }
    if (language == 'powershell') {
      if (low.contains('parse_int') || low.contains('parse int')) {
        return r'''function Parse-IntCandidate {
    param($Value, [int]$DefaultValue = 0)
    $parsed = 0
    if ([int]::TryParse([string]$Value, [ref]$parsed)) { return $parsed }
    return $DefaultValue
}
''';
      }
      return r'''function Clamp-Percent {
    param([double]$Value)
    if ([double]::IsNaN($Value)) { return 0 }
    return [Math]::Round([Math]::Min(100, [Math]::Max(0, $Value)))
}
''';
    }
    if (low.contains('normalize_device_record') ||
        low.contains('device record')) {
      return 'def normalize_device_record(record):\n    """Return a compact, reviewable device capability summary."""\n    if not isinstance(record, dict):\n        record = {}\n    connectivity = record.get("connectivity") or {}\n    best_for = record.get("best_for") or []\n    return {\n        "worker_id": str(record.get("worker_id") or ""),\n        "model": str(record.get("model") or record.get("configured_phone_model") or ""),\n        "wifi_ready": bool(connectivity.get("wifi_or_lan_ready")) if isinstance(connectivity, dict) else False,\n        "best_for_count": len(best_for) if isinstance(best_for, list) else 0,\n    }\n';
    }
    if (low.contains('parse_int') || low.contains('parse int')) {
      return 'def parse_int(value, default=0):\n    """Return value as int, or default when parsing fails."""\n    try:\n        return int(str(value).strip())\n    except (TypeError, ValueError):\n        return default\n';
    }
    return 'def clamp_percent(value):\n    """Return value rounded into the inclusive 0..100 range."""\n    try:\n        number = float(value)\n    except (TypeError, ValueError):\n        return 0\n    if number != number:\n        return 0\n    return round(min(100, max(0, number)))\n';
  }

  String _extractOriginalCode(String text) {
    final match = RegExp(
      r'```[a-zA-Z0-9_+-]*\s*([\s\S]*?)```',
    ).firstMatch(text);
    if (match == null) return '';
    return match.group(1)?.trimRight() ?? '';
  }

  String _formatDart(String code) {
    try {
      final formatter = DartFormatter(
        languageVersion: DartFormatter.latestLanguageVersion,
      );
      return formatter.format(code).trimRight();
    } catch (_) {
      return _normalizeCode(code);
    }
  }

  String _normalizeCode(String code) {
    return code.replaceAll('\r\n', '\n').trimRight();
  }

  String _searchQueryFor(String title, String text) {
    final usefulText = text.contains(':')
        ? text.split(':').skip(1).join(' ')
        : text;
    final baseText = usefulText.trim().isNotEmpty ? usefulText : title;
    final combined = baseText
        .replaceAll(RegExp(r'[`*_#>\[\]{}()]'), ' ')
        .replaceAll(RegExp(r'\b\d{6,}\b'), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
    final stopWords = <String>{
      'alpha',
      'beta',
      'bounded',
      'code',
      'draft',
      'engel',
      'for',
      'from',
      'helper',
      'online',
      'only',
      'phone',
      'phones',
      'plugin',
      'plugins',
      'recheck',
      'result',
      'results',
      'return',
      'search',
      'test',
      'that',
      'the',
      'worker',
      'workers',
    };
    final words = combined
        .split(' ')
        .map((word) => word.replaceAll(RegExp(r'[^A-Za-z0-9_+-]'), ''))
        .where((word) => word.length > 2)
        .where((word) => !stopWords.contains(word.toLowerCase()))
        .take(14)
        .join(' ');
    final combinedLow = combined.toLowerCase();
    if (words.isEmpty) return 'site:pub.dev/packages Flutter Dart';
    if (combinedLow.contains('dart') ||
        combinedLow.contains('flutter') ||
        combinedLow.contains('pub.dev')) {
      return 'site:pub.dev/packages $words Flutter Dart';
    }
    if (combinedLow.contains('package')) return 'site:pub.dev/packages $words';
    return words;
  }

  String? _normalizeDuckDuckGoUrl(String? href) {
    if (href == null || href.trim().isEmpty) return href;
    try {
      final uri = Uri.parse(href);
      final uddg = uri.queryParameters['uddg'];
      if (uddg != null && uddg.isNotEmpty) return uddg;
    } catch (_) {
      return href;
    }
    return href;
  }

  List<Map<String, Object?>> _pubPackageHints(String text) {
    final low = text.toLowerCase();
    const packageNames = <String>[
      'archive',
      'battery_plus',
      'connectivity_plus',
      'crypto',
      'csv',
      'dart_style',
      'device_info_plus',
      'diff_match_patch',
      'graphs',
      'html',
      'html_unescape',
      'http',
      'image',
      'markdown',
      'multicast_dns',
      'package_info_plus',
      'path_provider',
      'pdf',
      'sensors_plus',
      'wakelock_plus',
      'yaml',
    ];
    return packageNames
        .where(
          (name) =>
              low.contains(name.toLowerCase().replaceAll('_', ' ')) ||
              low.contains(name.toLowerCase()),
        )
        .take(8)
        .map(
          (name) => <String, Object?>{
            'title': '$name | Dart package',
            'url': 'https://pub.dev/packages/$name',
            'snippet':
                'Direct pub.dev package hint generated after bounded search returned no results.',
          },
        )
        .toList(growable: false);
  }

  List<String> _summaryBullets(String text) {
    final lines = text
        .split(RegExp(r'[\r\n]+'))
        .map((line) => line.trim())
        .where((line) => line.isNotEmpty)
        .take(8)
        .map((line) => _bounded(line, 220))
        .toList(growable: false);
    if (lines.isNotEmpty) return lines;
    return <String>['No readable assignment text was provided.'];
  }

  String _classificationFor(String text) {
    final low = text.toLowerCase();
    if (low.contains('receipt') || low.contains('log')) {
      return 'receipt_or_log';
    }
    if (low.contains('contract') || low.contains('safety')) {
      return 'contract_or_policy';
    }
    if (low.contains('candidate') || low.contains('json')) {
      return 'candidate_output';
    }
    if (low.contains('report') || low.contains('pdf')) {
      return 'report_or_artifact';
    }
    return 'text_reference';
  }

  List<String> _riskFlags(String text) {
    final low = text.toLowerCase();
    final flags = <String>[];
    for (final needle in <String>[
      'execute',
      'shell',
      'install',
      'download',
      'token',
      'secret',
      'password',
      'apply patch',
      'trusted memory',
      'provider',
      'browser',
    ]) {
      if (low.contains(needle)) {
        flags.add('flagged_${needle.replaceAll(' ', '_')}');
      }
    }
    return flags;
  }

  String _bounded(String text, int limit) {
    final cleaned = text.replaceAll('\r', ' ').trim();
    if (cleaned.length <= limit) return cleaned;
    return '${cleaned.substring(0, limit)}...';
  }

  Future<LanPairingResult> _request({
    required String method,
    required String host,
    required int port,
    required String path,
    Map<String, String>? queryParameters,
    Map<String, Object?>? body,
  }) async {
    final trimmedHost = host.trim();
    if (trimmedHost.isEmpty) {
      return const LanPairingResult.failure('PC host is required.');
    }
    if (port < 1 || port > 65535) {
      return const LanPairingResult.failure(
        'Port must be between 1 and 65535.',
      );
    }

    final client = HttpClient()..connectionTimeout = timeout;
    try {
      final uri = Uri(
        scheme: 'http',
        host: trimmedHost,
        port: port,
        path: path,
        queryParameters: queryParameters,
      );
      final request = await client.openUrl(method, uri).timeout(timeout);
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      if (body != null) {
        final bytes = utf8.encode(jsonEncode(body));
        request.headers.set(HttpHeaders.contentTypeHeader, 'application/json');
        request.headers.contentLength = bytes.length;
        request.add(bytes);
      }
      final response = await request.close().timeout(timeout);
      final responseText = await utf8.decoder
          .bind(response)
          .join()
          .timeout(timeout);
      final decoded = _decodeJsonObject(responseText);
      if (decoded == null) {
        return LanPairingResult(
          ok: false,
          statusCode: response.statusCode,
          message: 'Receiver returned non-JSON status data.',
          jsonText: responseText,
          decodedJson: null,
        );
      }
      return LanPairingResult(
        ok: response.statusCode >= 200 && response.statusCode < 300,
        statusCode: response.statusCode,
        message: _messageFor(path, response.statusCode, decoded),
        jsonText: const JsonEncoder.withIndent('  ').convert(decoded),
        decodedJson: decoded,
      );
    } on TimeoutException {
      return const LanPairingResult.failure('Unable to reach receiver.');
    } on SocketException {
      return const LanPairingResult.failure('Unable to reach receiver.');
    } on HttpException catch (error) {
      return LanPairingResult.failure(
        'Receiver request failed: ${error.message}',
      );
    } on FormatException catch (error) {
      return LanPairingResult.failure(
        'Receiver address is invalid: ${error.message}',
      );
    } finally {
      client.close(force: true);
    }
  }

  Map<String, String> _workerQuery(String pairingCode) {
    return <String, String>{
      'pairing_code': pairingCode,
      'worker_device': 'engel_remote_worker_flutter',
      'worker_id': workerId,
      'phone_model': phoneModel,
      'app_version': 'remote_worker_phase12_link_manager',
      'platform': Platform.operatingSystem,
      'current_mode': 'dedicated_engel_phone_foreground',
    };
  }

  Map<String, Object?>? _decodeJsonObject(String text) {
    try {
      final decoded = jsonDecode(text);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
    } on FormatException {
      return null;
    }
    return null;
  }

  String _messageFor(
    String path,
    int statusCode,
    Map<String, Object?> decoded,
  ) {
    if (path == '/health' && statusCode >= 200 && statusCode < 300) {
      return 'Receiver reachable - pairing/status only.';
    }
    if (path == '/pair' &&
        statusCode >= 200 &&
        statusCode < 300 &&
        decoded['paired'] == true) {
      return 'Paired as dedicated Engel Remote Worker - Engel controls phone worker mode; phone does not control Engel.';
    }
    if (path == '/worker/status' && statusCode >= 200 && statusCode < 300) {
      return 'Worker protocol reachable - Engel controlled phone link remains bounded.';
    }
    if (path == '/worker/next-assignment' &&
        statusCode >= 200 &&
        statusCode < 300) {
      if (decoded['status'] == 'no_work') {
        return 'No approved Communication Queen work available.';
      }
      if (decoded['status'] == 'assignment_ready') {
        return 'Approved assignment received - untrusted result required.';
      }
      return 'Assignment check completed.';
    }
    if (path == '/worker/return-result' &&
        statusCode >= 200 &&
        statusCode < 300 &&
        decoded['accepted'] == true) {
      return 'Untrusted result returned for Engel review.';
    }
    if (path == '/worker/return-result' &&
        decoded['status'] == 'duplicate_return_rejected') {
      return 'Duplicate return rejected - review-only, not applied.';
    }
    final error = decoded['error'];
    if (error is String && error.isNotEmpty) {
      return error;
    }
    return 'Receiver returned HTTP $statusCode.';
  }
}

class LanPairingResult {
  const LanPairingResult({
    required this.ok,
    required this.statusCode,
    required this.message,
    this.jsonText,
    this.decodedJson,
  });

  const LanPairingResult.failure(this.message)
    : ok = false,
      statusCode = null,
      jsonText = null,
      decodedJson = null;

  final bool ok;
  final int? statusCode;
  final String message;
  final String? jsonText;
  final Map<String, Object?>? decodedJson;
}
