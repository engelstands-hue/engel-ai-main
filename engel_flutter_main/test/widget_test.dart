import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:engel_flutter_main/device_status.dart';
import 'package:engel_flutter_main/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// Opens a page by its id.
///
/// After the 2026-07-28 window consolidation a page may be a TAB inside an
/// owning window instead of its own sidebar entry. This helper keeps every
/// existing call site honest: it opens the owner and then selects the tab, so
/// the assertions below still prove the page is reachable and renders.
Future<void> tapSideSection(WidgetTester tester, String sectionId) async {
  final resolved = sectionRouteAliases[sectionId] ?? sectionId;
  await _tapSidebarEntry(tester, resolved);
}

Future<void> _tapSidebarEntry(WidgetTester tester, String sectionId) async {
  if (find.byKey(const Key('section-search')).evaluate().isEmpty) {
    final menuButton = find.byKey(const Key('open-navigation-menu'));
    expect(menuButton, findsOneWidget);
    await tester.tap(menuButton);
    await tester.pump();
  }
  await tester.enterText(find.byKey(const Key('section-search')), sectionId);
  await tester.pump();
  final owner = referenceOnlySectionIds.contains(sectionId)
      ? advancedVaultSectionId
      : (sectionMergeOwner[sectionId] ?? sectionId);
  final finder = find.byKey(Key('section-$owner'));
  await tester.scrollUntilVisible(
    finder,
    260,
    scrollable: find
        .descendant(
          of: find.byKey(const Key('section-list')),
          matching: find.byType(Scrollable),
        )
        .first,
  );
  await tester.ensureVisible(finder);
  await tester.pump();
  await tester.tap(finder);
  await tester.pump();
}

DeviceVisibilityInfo deviceVisibilityFixture({
  EngelDeviceReadiness subEngel = EngelDeviceReadiness.offline,
  EngelDeviceReadiness phones = EngelDeviceReadiness.ready,
  int phoneCount = 3,
}) {
  EngelDeviceStatus status(EngelDeviceReadiness readiness) => EngelDeviceStatus(
    readiness: readiness,
    observedAtUtc: readiness == EngelDeviceReadiness.unknown
        ? null
        : DateTime.utc(2026, 8, 1, 20),
    age: readiness == EngelDeviceReadiness.unknown ? null : Duration.zero,
  );
  return DeviceVisibilityInfo(
    lanExists: true,
    linkStatus: 'connected',
    receiver: 'running',
    pairedPhone: phoneCount == 0 ? '' : 'fixture phone',
    androidWorkers: const [],
    nodeReady: subEngel == EngelDeviceReadiness.ready
        ? 'ready'
        : 'needs connection',
    phoneWorkers: List<VisibleDeviceWorker>.generate(
      phoneCount,
      (index) => VisibleDeviceWorker(
        id: 'phone-${index + 1}',
        name: 'Phone ${index + 1}',
        address: '192.0.2.${70 + index}',
        detail: 'test fixture',
        status: status(phones),
      ),
      growable: false,
    ),
    subEngelWorker: VisibleDeviceWorker(
      id: 'sub-engel-node',
      name: 'Sub-Engel',
      address: '198.51.100.227',
      detail: 'test fixture',
      status: status(subEngel),
    ),
    busProof: '',
    modified: DateTime.utc(2026, 8, 1, 20),
  );
}

class RecordingProcessRunner {
  final calls = <({String executable, List<String> arguments})>[];

  Future<ProcessResult> call(
    String executable,
    List<String> arguments, {
    String? workingDirectory,
    Map<String, String>? environment,
  }) async {
    calls.add((executable: executable, arguments: List.of(arguments)));
    return ProcessResult(
      calls.length,
      0,
      jsonEncode({
        'ok': true,
        'fake_ui_audit': true,
        'executable': executable,
        'arguments': arguments,
        'working_directory': workingDirectory,
      }),
      '',
    );
  }
}

class ScriptedProcessRunner {
  final calls =
      <
        ({
          String executable,
          List<String> arguments,
          String? workingDirectory,
          Map<String, String>? environment,
        })
      >[];
  final scripts = <Future<ProcessResult> Function()>[];

  Future<ProcessResult> call(
    String executable,
    List<String> arguments, {
    String? workingDirectory,
    Map<String, String>? environment,
  }) {
    calls.add((
      executable: executable,
      arguments: List<String>.from(arguments),
      workingDirectory: workingDirectory,
      environment: environment == null
          ? null
          : Map<String, String>.from(environment),
    ));
    if (scripts.isEmpty) {
      throw StateError('Unexpected process call: $executable $arguments');
    }
    return scripts.removeAt(0)();
  }
}

File writeFreshEightHourCurriculaIndex(Directory fixtures) {
  const templateRoot =
      r'D:\b.WorkSpace\Engel App\memory\training\engel_main\templates';
  const slots = <({String id, String title, String detail, String template})>[
    (
      id: 'capabilities',
      title: 'Engel Capabilities',
      detail:
          'Eight new artifact-grounded capability audits: governance, agent dispatch, Code Forge, devices, Meeting Room, MIPL, self-model, and real-training handoff.',
      template: '$templateRoot\\ENGEL_TEMPLATE_CAPABILITIES.json',
    ),
    (
      id: 'math_school',
      title: 'Math School',
      detail:
          'Eighty new declared problems with independent ground truth: every prompt is exactly decidable by the bounded symbolic grader.',
      template: '$templateRoot\\ENGEL_TEMPLATE_MATH_SCHOOL.json',
    ),
    (
      id: 'self_build',
      title: 'Self Build',
      detail: 'Eight unused self-build hours.',
      template: '$templateRoot\\ENGEL_TEMPLATE_SELF_BUILD.json',
    ),
    (
      id: 'construction',
      title: 'Construction',
      detail: 'Eight unused construction hours.',
      template: '$templateRoot\\ENGEL_TEMPLATE_CONSTRUCTION.json',
    ),
    (
      id: 'chat_communication',
      title: 'Chat Communication',
      detail: 'Eight unused communication hours.',
      template: '$templateRoot\\ENGEL_TEMPLATE_CHAT_COMMUNICATION.json',
    ),
  ];
  final index = File(
    '${fixtures.path}${Platform.pathSeparator}curricula_index.json',
  );
  index.writeAsStringSync(
    jsonEncode({
      'active_id': 'capabilities',
      'all_curricula_ready': true,
      'curricula': [
        for (var offset = 0; offset < slots.length; offset++)
          {
            'id': slots[offset].id,
            'title': slots[offset].title,
            'detail': slots[offset].detail,
            'template_path': slots[offset].template,
            'topic_count': 8,
            'prompt_count': 80,
            'maximum_hours': 8,
            'novel_hours_available': 8,
            'novel_complete_cycle_count': 8,
            'novel_hours_start_cycle': 1,
            'novelty_ready': true,
            'novelty_fully_ready': true,
            'novelty_status': 'READY',
            'topics': List<String>.generate(8, (index) => 'Hour ${index + 1}'),
            'active': offset == 0,
          },
      ],
    }),
  );
  return index;
}

class RecordingTrainingProcessStarter {
  RecordingTrainingProcessStarter({
    this.stopTreeResult = true,
    this.stopTreeError,
  });

  final exitCode = Completer<int>();
  final calls =
      <
        ({String executable, List<String> arguments, String? workingDirectory})
      >[];
  var stopTreeCalls = 0;
  final bool stopTreeResult;
  final Object? stopTreeError;

  Future<EngelTrainingProcessHandle> call(
    String executable,
    List<String> arguments, {
    String? workingDirectory,
  }) async {
    calls.add((
      executable: executable,
      arguments: List<String>.from(arguments),
      workingDirectory: workingDirectory,
    ));
    return EngelTrainingProcessHandle(
      pid: 4242,
      exitCode: exitCode.future,
      stopTree: () async {
        stopTreeCalls++;
        if (stopTreeError != null) throw stopTreeError!;
        return stopTreeResult;
      },
    );
  }
}

Future<void> pumpAction(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 25));
}

Future<Map<String, dynamic>> waitForJsonFile(
  WidgetTester tester,
  File file, {
  VoidCallback? trigger,
  bool Function(Map<String, dynamic> payload)? until,
  int attempts = 50,
}) async {
  final payload = await tester.runAsync<Map<String, dynamic>?>(() async {
    trigger?.call();
    for (var attempt = 0; attempt < attempts; attempt++) {
      if (file.existsSync()) {
        try {
          final decoded = jsonDecode(file.readAsStringSync());
          if (decoded is Map) {
            final result = Map<String, dynamic>.from(decoded);
            if (until == null || until(result)) return result;
          }
        } on FormatException {
          // An asynchronous write may be between truncate and flush. Retry.
        }
      }
      await Future<void>.delayed(const Duration(milliseconds: 10));
    }
    return null;
  });
  if (payload != null) return payload;
  throw TestFailure('Timed out waiting for valid JSON at ${file.path}.');
}

Future<void> pumpUntil(
  WidgetTester tester,
  bool Function() condition, {
  String reason = 'The expected UI state did not appear.',
  int attempts = 50,
}) async {
  for (var attempt = 0; attempt < attempts; attempt++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 10)),
    );
    await tester.pump();
    if (condition()) return;
  }
  fail(reason);
}

Future<void> ensureTextVisible(WidgetTester tester, String text) async {
  final finder = find.text(text);
  for (var i = 0; i < 16 && finder.evaluate().isEmpty; i++) {
    final scrollables = find.byType(Scrollable);
    if (scrollables.evaluate().isEmpty) break;
    await tester.drag(scrollables.last, const Offset(0, -480));
    await tester.pump();
  }
  await tester.ensureVisible(finder.first);
  await tester.pump();
}

bool focusIsInside(Finder target) {
  final focusedContext = FocusManager.instance.primaryFocus?.context;
  if (focusedContext == null) return false;
  final targetElements = target.evaluate().toSet();
  if (targetElements.contains(focusedContext)) return true;
  var found = false;
  focusedContext.visitAncestorElements((ancestor) {
    if (targetElements.contains(ancestor)) {
      found = true;
      return false;
    }
    return true;
  });
  return found;
}

Future<void> activateWithKeyboard(
  WidgetTester tester,
  Finder target, {
  int maxTabs = 80,
}) async {
  await tester.ensureVisible(target);
  await tester.pump();
  for (var index = 0; index < maxTabs && !focusIsInside(target); index++) {
    await tester.sendKeyEvent(LogicalKeyboardKey.tab);
    await tester.pump();
  }
  expect(
    focusIsInside(target),
    isTrue,
    reason: 'Keyboard focus never reached the requested control.',
  );
  await tester.sendKeyEvent(LogicalKeyboardKey.enter);
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 360));
}

/// A throwaway directory for model-training receipt fixtures.
///
/// It lives under the repo runtime temp root instead of [Directory.systemTemp]
/// because this workspace must never write to C:, and the system temp folder is
/// on C: for the operator running these tests.
Directory createModelTrainingFixtureDirectory() {
  final root = Directory(
    r'D:\b.WorkSpace\Engel App\runtime\temp\ui_widget_tests',
  )..createSync(recursive: true);
  return root.createTempSync('model-training-');
}

const modelTrainingRuntimeContractFixture = '''
schema=engel_training_cycle_runtime_contract_v1
termination_grace_seconds=300
whole_cycle.slm=28800
whole_cycle.llm=46800
whole_cycle.slm_llm=57600
slm.dataset=1200
slm.train=2400
slm.verify=900
llm.dataset=2400
llm.preflight=300
llm.train_and_evaluate=21600
''';

const shortModelTrainingRuntimeContractFixture = '''
schema=engel_training_cycle_runtime_contract_v1
termination_grace_seconds=1
whole_cycle.slm=3
whole_cycle.llm=3
whole_cycle.slm_llm=6
slm.dataset=1
slm.train=1
slm.verify=1
llm.dataset=1
llm.preflight=1
llm.train_and_evaluate=1
''';

File writeModelTrainingRuntimeContract(
  Directory directory, {
  String contents = modelTrainingRuntimeContractFixture,
}) => File(
  '${directory.path}${Platform.pathSeparator}'
  'engel_training_cycle_runtime_contract.contract',
)..writeAsStringSync(contents);

Future<void> startSlmModelTrainingFixture(
  WidgetTester tester,
  RecordingTrainingProcessStarter starter, {
  String contractContents = modelTrainingRuntimeContractFixture,
}) async {
  final fixtures = createModelTrainingFixtureDirectory();
  addTearDown(() {
    if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
  });
  final separator = Platform.pathSeparator;
  final scriptFile = File(
    '${fixtures.path}${separator}run_engel_real_training_cycle.py',
  )..writeAsStringSync('"""Training-cycle fixture."""\n');
  writeModelTrainingRuntimeContract(fixtures, contents: contractContents);

  await tester.pumpWidget(
    EngelMainApp(
      enableStartupTasks: false,
      enableTrainingRunStatusPolling: false,
      trainingProcessStarter: starter.call,
      uiPreferencesPath: '',
      realTrainingCycleScriptPath: scriptFile.path,
      realTrainingCycleReceiptPath:
          '${fixtures.path}${separator}absent_cycle.json',
      promptTrainingPackReceiptPath:
          '${fixtures.path}${separator}absent_pack.json',
      slmRosterMirrorPath: '${fixtures.path}${separator}absent_roster.json',
    ),
  );
  await tester.pump();
  await tapSideSection(tester, 'training');
  await pumpUntil(
    tester,
    () => find.text('Receipts read just now').evaluate().isNotEmpty,
    reason: 'The model-training fixture receipts were never read from disk.',
    attempts: 200,
  );
  tester
      .widget<CheckboxListTile>(find.byKey(const Key('training-target-llm')))
      .onChanged!(false);
  await tester.pump();
  final runCycle = find.byKey(const Key('model-training-run-cycle'));
  await tester.ensureVisible(runCycle);
  await tester.tap(runCycle);
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const Key('confirm-model-training')));
  await pumpUntil(tester, () => starter.calls.isNotEmpty);
}

String promptFilePathFrom(List<String> arguments) {
  final promptFileArg = arguments.singleWhere(
    (argument) => argument.startsWith('--prompt-file='),
  );
  return promptFileArg.substring('--prompt-file='.length);
}

Map<String, dynamic> connectionDoctorV2Receipt({
  required bool ok,
  required String overallState,
  required bool chatOnline,
  required bool meetingRoomOnline,
  required bool officeOnline,
  String mode = 'check',
  String? status,
  String? diagnosis,
  String? repairOutcome,
  String receiptPath = r'D:\test\connection-doctor.json',
}) {
  Map<String, dynamic> service(bool online, String name) => {
    'state': online ? 'ready' : 'unavailable',
    'ok': online,
    'tcp_ok': online,
    'health_ok': online,
    'status': online ? '$name ready' : '$name unavailable',
  };
  final resolvedRepairOutcome =
      repairOutcome ??
      (mode == 'fix' ? (ok ? 'succeeded' : 'failed') : 'not_requested');

  return {
    'schema': 'engel_connection_loop_doctor_v2',
    'schema_version': 2,
    'ok': ok,
    'overall_state': overallState,
    'services': {
      'chat': service(chatOnline, 'chat'),
      'meeting_room': service(meetingRoomOnline, 'meeting room'),
      'office': service(officeOnline, 'office'),
    },
    'status':
        status ??
        (ok
            ? 'Chat, Meeting Room, and Office are ready'
            : 'connection services partially available'),
    'diagnosis':
        diagnosis ??
        (ok
            ? 'All checked connection services are healthy'
            : 'One or more checked services are unavailable'),
    'mode': mode,
    'checks': [
      {
        'name': 'local_chat_health',
        'ok': chatOnline,
        'status': chatOnline ? 'ready' : 'offline',
        'details': <String, dynamic>{},
      },
      {
        'name': 'local_meeting_room_health',
        'ok': meetingRoomOnline,
        'status': meetingRoomOnline ? 'ready' : 'offline',
        'details': <String, dynamic>{},
      },
      {
        'name': 'local_office_tcp',
        'ok': officeOnline,
        'status': officeOnline ? 'ready' : 'offline',
        'details': <String, dynamic>{},
      },
    ],
    'actions': <dynamic>[],
    'repair': {
      'requested': mode == 'fix',
      'attempted': mode == 'fix' && resolvedRepairOutcome != 'not_needed',
      'outcome': resolvedRepairOutcome,
      'chat_restored': mode == 'fix' && resolvedRepairOutcome == 'succeeded',
      'remote_server_changes_attempted': false,
    },
    'report_writes': {
      'performed': true,
      'count': 2,
      'scope': 'diagnostic report files',
    },
    'ssd_only': true,
    'vault_used': false,
    'storage_mutation_performed': true,
    'secrets_read': false,
    'receipt_path': receiptPath,
  };
}

ProcessResult connectionDoctorProcessResult(
  Map<String, dynamic> receipt, {
  required int exitCode,
  String stderr = '',
}) {
  return ProcessResult(700, exitCode, jsonEncode(receipt), stderr);
}

Future<void> openConnectionHelp(
  WidgetTester tester,
  ScriptedProcessRunner runner, {
  bool serverOnline = true,
}) async {
  await tester.pumpWidget(
    EngelMainApp(
      enableStartupTasks: false,
      processRunner: runner.call,
      serverHealthProbe: () async => serverOnline,
    ),
  );
  await tester.pump();
  await tester.pump();
  await tapSideSection(tester, 'connection_doctor');
  expect(find.byKey(const Key('connection-doctor-page')), findsOneWidget);
}

void expectConnectionDoctorAnnouncement(WidgetTester tester, String label) {
  final data = tester
      .getSemantics(
        find.byKey(const Key('connection-doctor-status-announcement')),
      )
      .getSemanticsData();
  expect(data.label, label);
  expect(data.flagsCollection.isLiveRegion, isTrue);
}

void expectAccessibleButton(
  WidgetTester tester,
  String key,
  String label, {
  required bool enabled,
}) {
  final finder = find.byKey(Key(key));
  final data = tester.getSemantics(finder).getSemanticsData();
  expect(data.label, label);
  expect(data.flagsCollection.isButton, isTrue);
  expect(data.hasAction(ui.SemanticsAction.tap), enabled);
  expect(tester.getSize(finder).height, greaterThanOrEqualTo(48));
}

void main() {
  test('model training runtime contract covers every requested lane', () {
    final slm = parseEngelTrainingCycleRuntimeBudget(
      modelTrainingRuntimeContractFixture,
      'slm',
    );
    final llm = parseEngelTrainingCycleRuntimeBudget(
      modelTrainingRuntimeContractFixture,
      'llm',
    );
    final both = parseEngelTrainingCycleRuntimeBudget(
      modelTrainingRuntimeContractFixture,
      ' LLM, slm,llm ',
    );

    expect(normalizeEngelModelTrainingTargets(' LLM, slm,llm '), 'slm,llm');
    expect(slm.wholeCycleDeadline, const Duration(seconds: 28800));
    expect(llm.wholeCycleDeadline, const Duration(seconds: 46800));
    expect(both.wholeCycleDeadline, const Duration(seconds: 57600));
    expect(slm.terminationGrace, const Duration(seconds: 300));
    expect(slm.clientDeadline, const Duration(seconds: 29100));
    expect(llm.clientDeadline, const Duration(seconds: 47100));
    expect(both.clientDeadline, const Duration(seconds: 57900));
    expect(slm.clientDeadline, greaterThan(const Duration(minutes: 45)));
    expect(llm.clientDeadline, greaterThan(const Duration(hours: 4)));
    expect(both.clientDeadline, greaterThan(llm.clientDeadline));
    expect(
      () => normalizeEngelModelTrainingTargets('slm,gpu'),
      throwsFormatException,
    );
  });

  test('model training runtime contract fails closed when malformed', () {
    expect(
      () => parseEngelTrainingCycleRuntimeDeadline(
        'schema=wrong\ntermination_grace_seconds=1\n',
        'slm,llm',
      ),
      throwsFormatException,
    );
    expect(
      () => parseEngelTrainingCycleRuntimeDeadline(
        modelTrainingRuntimeContractFixture.replaceFirst(
          'llm.train_and_evaluate=21600',
          'llm.train_and_evaluate=0',
        ),
        'llm',
      ),
      throwsFormatException,
    );
  });

  test(
    'Engel chat text sanitizer preserves valid emoji and repairs broken text',
    () {
      final brokenLowSurrogate = String.fromCharCodes([
        0x62,
        0x61,
        0x64,
        0x20,
        0xDC9D,
        0x20,
        0x64,
        0x6F,
        0x6E,
        0x65,
      ]);

      final repaired = cleanEngelChatTextForWorker(
        'Build proof 🚀\n$brokenLowSurrogate',
      );

      expect(repaired, contains('Build proof 🚀'));
      expect(repaired, contains('bad � done'));
      expect(repaired.codeUnits, isNot(contains(0xDC9D)));
      expect(() => utf8.encode(repaired), returnsNormally);
    },
  );

  test('all Rust command references resolve to registered commands', () {
    final source = File('lib/main.dart').readAsStringSync();
    final registered = RegExp(
      r"RustCommand\(\s*'([^']+)'",
      dotAll: true,
    ).allMatches(source).map((match) => match.group(1)!).toSet();
    final referenced = <String>{};
    for (final pattern in [
      RegExp(r"firstWhere\(\(c\) => c\.key == '([^']+)'"),
      RegExp(r"_commandByKey\('([^']+)'\)"),
      RegExp(r"commands\['([^']+)'\]!"),
      RegExp(
        r"_closeDialogAndRunRust\(\s*[^,]+,\s*'[^']+',\s*'([^']+)'",
        dotAll: true,
      ),
    ]) {
      referenced.addAll(
        pattern.allMatches(source).map((match) => match.group(1)!),
      );
    }
    final missing = referenced.difference(registered).toList()..sort();
    expect(missing, isEmpty);
    expect(registered, hasLength(391));
  });

  test('standalone connection inventory is copied into Engel Main', () {
    expect(engelStandaloneChannels.map((c) => c.name), [
      'Telegram',
      'Discord',
      'iMessage',
    ]);
    expect(engelStandaloneIntegrations, hasLength(118));
    expect(
      engelStandaloneIntegrations.map((i) => i.slug),
      containsAll(['airtable', 'gmail', 'discord', 'supabase', 'zoom']),
    );
    expect(standaloneIntegrationSlugAliases['google_drive'], 'googledrive');
    expect(standaloneIntegrationSlugAliases['google_sheets'], 'googlesheets');
  });

  test('model catalog exposes broad built-in and future registry lanes', () {
    final ids = engelModelCatalog.map((m) => m.id).toList();
    expect(ids.length, greaterThanOrEqualTo(120));
    expect(ids.toSet(), hasLength(ids.length));
    expect(
      engelModelCatalog.map((m) => m.name),
      containsAll([
        'OpenRouter Auto',
        'GPT-5.5 Max',
        'Claude Opus Latest',
        'Gemini Latest',
        'Grok Build 0.1',
        'Mistral Large 3',
        'Command A',
        'Llama 3.3 70B Versatile',
        'Sonar Deep Research',
        'Any Local GGUF',
        'Sub-Engel Local Best',
      ]),
    );
  });

  test(
    'Meeting Room readiness uses visible workers instead of server jargon',
    () {
      expect(
        parseMeetingRoomVisibleParticipantCount({
          'participant_counts': {'total_visible': 4},
          'participants': const [],
        }),
        4,
      );
      expect(
        parseMeetingRoomVisibleParticipantCount({
          'participants': [
            {'status': 'live'},
            {'status': 'offline'},
            {'status': 'live'},
          ],
        }),
        2,
      );
      expect(
        parseMeetingRoomVisibleParticipantCount({
          'participant_counts': {'total_visible': -1},
        }),
        isNull,
      );

      const ready = MeetingRoomServerInfo(
        ok: true,
        status: 'running',
        url: 'local',
        endpoints: [],
        serverRoot: 'local',
        error: '',
        visibleParticipantCount: 4,
      );
      expect(meetingRoomReadinessLabel(ready), '4 workers connected');
      expect(
        meetingRoomReadinessDetail(ready),
        contains('go to 4 connected workers'),
      );
      expect(
        meetingRoomConfirmationTitle(ready),
        'Send this task to 4 connected workers?',
      );
      expect(
        meetingRoomConfirmationDetail(ready),
        contains('currently sees 4 connected workers'),
      );

      const noWorkers = MeetingRoomServerInfo(
        ok: true,
        status: 'running',
        url: 'local',
        endpoints: [],
        serverRoot: 'local',
        error: '',
        visibleParticipantCount: 0,
      );
      expect(meetingRoomReadinessLabel(noWorkers), 'No workers connected');
      expect(meetingRoomReadinessDetail(noWorkers), contains('Keep the draft'));
    },
  );

  testWidgets('Engel Main shell renders', (WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableDeviceStatusScan: false,
      ),
    );
    await tester.pump();

    expect(find.text('Engel'), findsWidgets);
    expect(find.byKey(const Key('section-search')), findsOneWidget);
    expect(find.byKey(const Key('section-search-count')), findsNothing);
    expect(find.text('Chat'), findsWidgets);
    expect(find.text('Status'), findsWidgets);
    expect(find.text('Settings'), findsOneWidget);
    expect(find.text('Advanced'), findsWidgets);
    expect(find.byKey(const Key('section-advanced_vault')), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-thread')), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-composer')), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-input')), findsOneWidget);
    expect(find.byKey(const Key('mac-global-search')), findsNothing);

    await tapSideSection(tester, 'status_console');
    expect(find.text('Connection, phones, and proof — one place.'), findsOneWidget);
    expect(find.byKey(const Key('status-repair-connection')), findsOneWidget);

    await tapSideSection(tester, 'chat_runtime');

    expect(find.byKey(const Key('engel-chat-thread')), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-composer')), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-input')), findsOneWidget);
    expect(find.byKey(const ValueKey('mac-chat-bubble-intro')), findsOneWidget);
    expect(find.byKey(const ValueKey('mac-chat-bubble-empty')), findsNothing);
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed,
      isNull,
    );

    await tester.enterText(
      find.byKey(const Key('engel-chat-input')),
      'route phone evidence to verifier',
    );
    await tester.pump();

    expect(find.text('route phone evidence to verifier'), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed,
      isNotNull,
    );

    await tester.enterText(find.byKey(const Key('section-search')), 'proof');
    await tester.pump();

    expect(find.byKey(const Key('section-proof')), findsOneWidget);
    expect(find.byKey(const Key('section-launch_center')), findsNothing);
    expect(find.byKey(const Key('section-search-count')), findsNothing);
    expect(
      find.text('Tests, screenshots, hashes, process proof'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('clear-section-search')));
    await tester.pump();

    expect(find.byKey(const Key('section-search-count')), findsNothing);
    expect(find.byKey(const Key('section-launch_center')), findsNothing);

    await tester.enterText(
      find.byKey(const Key('section-search')),
      'lan_gateway',
    );
    await tester.pump();

    expect(find.byKey(const Key('section-device_visibility')), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('section-search')),
      'connection help',
    );
    await tester.pump();
    expect(find.byKey(const Key('section-device_visibility')), findsOneWidget);
  });

  testWidgets('chat recovery announces a delayed initial connection check', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final initialProbe = Completer<bool>();
    var probeCount = 0;

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        serverHealthProbe: () {
          probeCount += 1;
          return initialProbe.future;
        },
      ),
    );
    await tester.pump();

    expect(probeCount, 1);
    expect(find.text('Checking chat'), findsOneWidget);
    expect(find.byKey(const Key('chat-connection-recovery')), findsOneWidget);
    expect(find.text('Checking chat connection'), findsOneWidget);
    expect(
      find.text(
        'Checking Engel chat and Meeting Room. '
        'Local files and tools stay available.',
      ),
      findsOneWidget,
    );

    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    final statusData = tester
        .getSemantics(find.byKey(const Key('main-server-status-semantics')))
        .getSemanticsData();
    expect(statusData.label, 'Engel chat status: Checking chat');
    expect(statusData.hint, 'Activate for connection status and actions.');
    expect(statusData.flagsCollection.isLiveRegion, isTrue);
    expect(statusData.flagsCollection.isButton, isTrue);
    expect(statusData.hasAction(ui.SemanticsAction.tap), isTrue);

    final recoveryData = tester
        .getSemantics(
          find.byKey(const Key('chat-connection-recovery-announcement')),
        )
        .getSemanticsData();
    expect(
      recoveryData.label,
      'Checking Engel chat connection. '
      'Local files and tools remain available.',
    );
    expect(recoveryData.flagsCollection.isLiveRegion, isTrue);

    final retryFinder = find.byKey(const Key('chat-connection-retry'));
    final retryData = tester.getSemantics(retryFinder).getSemanticsData();
    expect(retryData.label, 'Checking…');
    expect(retryData.flagsCollection.isButton, isTrue);
    expect(retryData.hasAction(ui.SemanticsAction.tap), isFalse);
    expect(tester.getSize(retryFinder).height, greaterThanOrEqualTo(48));

    final doctorFinder = find.byKey(const Key('chat-connection-doctor'));
    final doctorData = tester.getSemantics(doctorFinder).getSemanticsData();
    expect(doctorData.label, 'Connection help');
    expect(doctorData.flagsCollection.isButton, isTrue);
    expect(doctorData.hasAction(ui.SemanticsAction.tap), isTrue);
    expect(tester.getSize(doctorFinder).height, greaterThanOrEqualTo(48));

    initialProbe.complete(false);
    await tester.pump();
    await tester.pump();
    expect(find.text('Chat unavailable'), findsNWidgets(2));
    semanticsHandle.dispose();
  });

  testWidgets('initial offline state explains impact and recovery actions', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        serverHealthProbe: () async => false,
      ),
    );
    await tester.pump();
    await tester.pump();

    expect(find.text('Chat unavailable'), findsNWidgets(2));
    final statusFinder = find.byKey(const Key('main-server-status'));
    expect(tester.getSize(statusFinder).height, greaterThanOrEqualTo(44));
    expect(
      tester.getSize(statusFinder).width,
      lessThan(200),
      reason: 'The status badge must not consume the top bar.',
    );
    expect(
      find.text(
        'Engel chat is not responding. '
        'Files, notes, settings, and local tools still work.',
      ),
      findsOneWidget,
    );

    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    final statusData = tester
        .getSemantics(find.byKey(const Key('main-server-status-semantics')))
        .getSemanticsData();
    expect(statusData.label, 'Engel chat status: Chat unavailable');
    expect(statusData.hint, 'Activate for connection status and actions.');
    expect(statusData.flagsCollection.isLiveRegion, isTrue);
    expect(statusData.flagsCollection.isButton, isTrue);
    expect(statusData.hasAction(ui.SemanticsAction.tap), isTrue);

    final recoveryData = tester
        .getSemantics(
          find.byKey(const Key('chat-connection-recovery-announcement')),
        )
        .getSemanticsData();
    expect(
      recoveryData.label,
      'Engel chat is unavailable. '
      'Files, notes, settings, and local tools still work.',
    );
    expect(recoveryData.flagsCollection.isLiveRegion, isTrue);

    final retryFinder = find.byKey(const Key('chat-connection-retry'));
    final retryData = tester.getSemantics(retryFinder).getSemanticsData();
    expect(retryData.label, 'Try again');
    expect(retryData.flagsCollection.isButton, isTrue);
    expect(retryData.hasAction(ui.SemanticsAction.tap), isTrue);
    expect(tester.getSize(retryFinder).height, greaterThanOrEqualTo(48));

    final doctorFinder = find.byKey(const Key('chat-connection-doctor'));
    final doctorData = tester.getSemantics(doctorFinder).getSemanticsData();
    expect(doctorData.label, 'Connection help');
    expect(doctorData.flagsCollection.isButton, isTrue);
    expect(doctorData.hasAction(ui.SemanticsAction.tap), isTrue);
    expect(tester.getSize(doctorFinder).height, greaterThanOrEqualTo(48));
    semanticsHandle.dispose();
  });

  testWidgets('chat status explains readiness before offering actions', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();
    var probeCount = 0;

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        processRunner: runner.call,
        serverHealthProbe: () async {
          probeCount += 1;
          return true;
        },
      ),
    );
    await tester.pump();
    await tester.pump();

    expect(probeCount, 1);
    expect(find.text('Chat ready'), findsOneWidget);
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('main-server-status')),
    );
    await tester.pump();

    expect(
      find.byKey(const Key('chat-connection-status-dialog')),
      findsOneWidget,
    );
    expect(find.text('Chat is ready'), findsOneWidget);
    expect(
      find.text(
        'Engel Chat answered the latest connection check. '
        'You can ask questions and start tasks.',
      ),
      findsOneWidget,
    );
    expect(find.text('Check again'), findsOneWidget);
    expect(probeCount, 1, reason: 'Opening status must not run a new check.');
    expect(runner.calls, isEmpty);

    final helpFinder = find.byKey(const Key('chat-connection-status-help'));
    expect(tester.getSize(helpFinder).height, greaterThanOrEqualTo(48));
    await activateWithKeyboard(tester, helpFinder);
    await tester.pump();

    expect(find.byKey(const Key('connection-doctor-page')), findsOneWidget);
    expect(runner.calls, isEmpty);
  });

  testWidgets('chat status runs a new check only after explicit retry', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    var probeCount = 0;

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        serverHealthProbe: () async {
          probeCount += 1;
          return probeCount > 1;
        },
      ),
    );
    await tester.pump();
    await tester.pump();

    expect(probeCount, 1);
    expect(find.text('Chat unavailable'), findsNWidgets(2));
    await tester.tap(find.byKey(const Key('main-server-status')));
    await tester.pump();

    expect(find.text('Chat is unavailable'), findsOneWidget);
    expect(find.text('Try again'), findsNWidgets(2));
    expect(probeCount, 1, reason: 'Opening status must not run a new check.');

    final checkFinder = find.byKey(const Key('chat-connection-status-check'));
    expect(tester.getSize(checkFinder).height, greaterThanOrEqualTo(48));
    await tester.tap(checkFinder);
    await tester.pump();
    await tester.pump();

    expect(probeCount, 2);
    expect(
      find.byKey(const Key('chat-connection-status-dialog')),
      findsNothing,
    );
    expect(find.text('Chat ready'), findsOneWidget);
  });

  testWidgets('keyboard retry runs one guarded probe and reaches chat ready', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final retryProbe = Completer<bool>();
    var probeCount = 0;

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        serverHealthProbe: () {
          probeCount += 1;
          if (probeCount == 1) return Future<bool>.value(false);
          return retryProbe.future;
        },
      ),
    );
    await tester.pump();
    await tester.pump();
    expect(probeCount, 1);
    expect(find.text('Chat unavailable'), findsNWidgets(2));

    final retryFinder = find.byKey(const Key('chat-connection-retry'));
    await activateWithKeyboard(tester, retryFinder);

    expect(probeCount, 2);
    expect(find.text('Checking chat'), findsOneWidget);
    expect(
      tester
          .getSemantics(retryFinder)
          .getSemanticsData()
          .hasAction(ui.SemanticsAction.tap),
      isFalse,
    );

    await activateWithKeyboard(
      tester,
      find.byKey(const Key('main-server-status')),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(
      find.byKey(const Key('chat-connection-status-dialog')),
      findsOneWidget,
    );
    final dialogCheck = find.byKey(const Key('chat-connection-status-check'));
    expect(
      tester
          .getSemantics(dialogCheck)
          .getSemanticsData()
          .hasAction(ui.SemanticsAction.tap),
      isFalse,
    );
    expect(
      probeCount,
      2,
      reason: 'Checking state must not start a duplicate health probe.',
    );
    await tester.tap(find.byKey(const Key('chat-connection-status-close')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    retryProbe.complete(true);
    await tester.pump();
    await tester.pump();

    expect(probeCount, 2);
    expect(find.text('Chat ready'), findsOneWidget);
    expect(find.byKey(const Key('chat-connection-recovery')), findsNothing);
    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    final readyData = tester
        .getSemantics(find.byKey(const Key('main-server-status-semantics')))
        .getSemanticsData();
    expect(readyData.label, 'Engel chat status: Chat ready');
    expect(readyData.hint, 'Activate for connection status and actions.');
    expect(readyData.flagsCollection.isLiveRegion, isTrue);
    expect(readyData.flagsCollection.isButton, isTrue);
    expect(readyData.hasAction(ui.SemanticsAction.tap), isTrue);
    semanticsHandle.dispose();
  });

  testWidgets('failed retry restores offline recovery without another probe', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final retryProbe = Completer<bool>();
    var probeCount = 0;

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        serverHealthProbe: () {
          probeCount += 1;
          if (probeCount == 1) return Future<bool>.value(false);
          return retryProbe.future;
        },
      ),
    );
    await tester.pump();
    await tester.pump();

    final retryFinder = find.byKey(const Key('chat-connection-retry'));
    await tester.tap(retryFinder);
    await tester.pump();
    expect(probeCount, 2);
    expect(find.text('Checking chat'), findsOneWidget);

    retryProbe.complete(false);
    await tester.pump();
    await tester.pump();

    expect(probeCount, 2);
    expect(find.text('Chat unavailable'), findsNWidgets(2));
    expect(find.text('Try again'), findsOneWidget);
    expect(
      tester
          .getSemantics(retryFinder)
          .getSemanticsData()
          .hasAction(ui.SemanticsAction.tap),
      isTrue,
    );
  });

  testWidgets('connection help uses safe navigation without process calls', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        processRunner: runner.call,
        serverHealthProbe: () async => false,
      ),
    );
    await tester.pump();
    await tester.pump();
    expect(runner.calls, isEmpty);

    await activateWithKeyboard(
      tester,
      find.byKey(const Key('chat-connection-doctor')),
    );

    expect(find.text('Connection help'), findsWidgets);
    expect(find.text('Check connection'), findsOneWidget);
    expect(runner.calls, isEmpty);
  });

  testWidgets('Connection help idle state is accessible with details hidden', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();

    await openConnectionHelp(tester, runner);

    expect(find.text('Connection help'), findsOneWidget);
    expect(
      tester
          .widget<Text>(find.byKey(const Key('connection-doctor-status-title')))
          .data,
      'Ready to check',
    );
    expect(
      tester
          .widget<Text>(
            find.byKey(const Key('connection-doctor-status-detail')),
          )
          .data,
      'Run a connection check to verify Chat and Meeting Room.',
    );
    expect(
      find.byKey(const Key('connection-doctor-technical-details')),
      findsNothing,
    );
    expect(find.text(engelMainServerChatHealthUrl), findsNothing);
    expect(find.text(meetingRoomServerHealthUrl), findsNothing);
    expect(find.textContaining('ssh root@192.0.2.50'), findsNothing);
    expect(runner.calls, isEmpty);

    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    expectConnectionDoctorAnnouncement(
      tester,
      'Ready to check. '
      'Run a connection check to verify Chat and Meeting Room.',
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-check',
      'Check connection',
      enabled: true,
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-fix',
      'Repair connection',
      enabled: true,
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-technical-details-toggle',
      'Show technical details',
      enabled: true,
    );
    semanticsHandle.dispose();
  });

  testWidgets(
    'Connection help keyboard check guards duplicates and announces success',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1500, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final runner = ScriptedProcessRunner();
      final pendingResult = Completer<ProcessResult>();
      runner.scripts.add(() => pendingResult.future);

      await openConnectionHelp(tester, runner);
      final semanticsHandle = tester.ensureSemantics();
      await tester.pump();
      final checkFinder = find.byKey(const Key('connection-doctor-check'));
      final fixFinder = find.byKey(const Key('connection-doctor-fix'));

      await activateWithKeyboard(tester, checkFinder);

      expect(runner.calls, hasLength(1));
      final call = runner.calls.single;
      expect(call.executable, 'powershell.exe');
      expect(call.arguments, [
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        connectionLoopDoctorLauncherPath,
        '-Json',
      ]);
      expect(call.workingDirectory, appRoot);
      expect(call.environment?['ENGEL_APP_ROOT'], appRoot);
      expect(call.environment?['TEMP'], engelTempRoot);
      expect(call.environment?['TMP'], engelTempRoot);
      expect(call.environment?['TMPDIR'], engelTempRoot);
      expect(
        tester
            .widget<Text>(
              find.byKey(const Key('connection-doctor-status-title')),
            )
            .data,
        'Checking connection…',
      );
      expect(
        tester
            .widget<Text>(
              find.byKey(const Key('connection-doctor-status-detail')),
            )
            .data,
        'Engel is checking Chat and Meeting Room. '
        'No connection changes are being made.',
      );
      expectConnectionDoctorAnnouncement(
        tester,
        'Checking connection… '
        'Engel is checking Chat and Meeting Room. '
        'No connection changes are being made.',
      );
      expectAccessibleButton(
        tester,
        'connection-doctor-check',
        'Checking…',
        enabled: false,
      );
      expectAccessibleButton(
        tester,
        'connection-doctor-fix',
        'Repair connection',
        enabled: false,
      );

      await tester.tap(checkFinder, warnIfMissed: false);
      await tester.tap(fixFinder, warnIfMissed: false);
      await tester.pump();
      expect(
        runner.calls,
        hasLength(1),
        reason: 'A pending connection check must guard duplicate runs.',
      );

      pendingResult.complete(
        connectionDoctorProcessResult(
          connectionDoctorV2Receipt(
            ok: true,
            overallState: 'ready',
            chatOnline: true,
            meetingRoomOnline: true,
            officeOnline: true,
          ),
          exitCode: 0,
        ),
      );
      await tester.pump();
      await tester.pump();

      expect(
        tester
            .widget<Text>(
              find.byKey(const Key('connection-doctor-status-title')),
            )
            .data,
        'Chat and Meeting Room are connected',
      );
      expect(
        tester
            .widget<Text>(
              find.byKey(const Key('connection-doctor-status-detail')),
            )
            .data,
        'Chat and Meeting Room are ready. No repair is needed.',
      );
      expectConnectionDoctorAnnouncement(
        tester,
        'Chat and Meeting Room are connected. '
        'Chat and Meeting Room are ready. No repair is needed.',
      );
      expect(find.text('3 of 3 technical checks passed.'), findsOneWidget);
      expectAccessibleButton(
        tester,
        'connection-doctor-check',
        'Check again',
        enabled: true,
      );
      expectAccessibleButton(
        tester,
        'connection-doctor-go-chat',
        'Go to Chat',
        enabled: true,
      );
      expect(find.byKey(const Key('connection-doctor-fix')), findsNothing);

      final chatStatus = tester
          .getSemantics(find.byKey(const Key('connection-doctor-chat-status')))
          .getSemanticsData();
      expect(
        chatStatus.label,
        'Chat status: Ready. Questions and conversations with Engel',
      );
      final meetingStatus = tester
          .getSemantics(
            find.byKey(const Key('connection-doctor-meeting-room-status')),
          )
          .getSemanticsData();
      expect(
        meetingStatus.label,
        'Meeting Room status: Ready. '
        'Shared agent work and live room status',
      );
      semanticsHandle.dispose();
    },
  );

  testWidgets('Connection help honors explicit false over process exit zero', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();
    runner.scripts.add(
      () async => connectionDoctorProcessResult(
        connectionDoctorV2Receipt(
          ok: false,
          overallState: 'partial',
          chatOnline: true,
          meetingRoomOnline: false,
          officeOnline: true,
          status: 'connection services partially available',
          diagnosis: 'Meeting Room did not answer',
        ),
        exitCode: 0,
      ),
    );

    await openConnectionHelp(tester, runner);
    await tester.tap(find.byKey(const Key('connection-doctor-check')));
    await tester.pump();
    await tester.pump();

    expect(runner.calls, hasLength(1));
    expect(
      tester
          .widget<Text>(find.byKey(const Key('connection-doctor-status-title')))
          .data,
      'Part of Engel is connected',
    );
    expect(
      tester
          .widget<Text>(
            find.byKey(const Key('connection-doctor-status-detail')),
          )
          .data,
      'Chat is ready, but Meeting Room is unavailable. '
      'No connection changes were made.',
    );
    expect(find.text('2 of 3 technical checks passed.'), findsOneWidget);
    expect(find.text('Chat and Meeting Room are connected'), findsNothing);
    expect(
      find.byKey(const Key('connection-doctor-technical-details')),
      findsNothing,
    );

    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    expectConnectionDoctorAnnouncement(
      tester,
      'Part of Engel is connected. '
      'Chat is ready, but Meeting Room is unavailable. '
      'No connection changes were made.',
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-fix',
      'Repair connection',
      enabled: true,
    );
    semanticsHandle.dispose();
  });

  testWidgets('Connection help treats malformed output as a failure', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();
    runner.scripts.add(
      () async =>
          ProcessResult(701, 0, 'not a connection receipt', 'malformed output'),
    );

    await openConnectionHelp(tester, runner);
    await tester.tap(find.byKey(const Key('connection-doctor-check')));
    await tester.pump();
    await tester.pump();

    expect(
      tester
          .widget<Text>(find.byKey(const Key('connection-doctor-status-title')))
          .data,
      'Connection check could not finish',
    );
    expect(
      tester
          .widget<Text>(
            find.byKey(const Key('connection-doctor-status-detail')),
          )
          .data,
      'The tool returned unreadable results. '
      'No connection changes were made.',
    );
    expect(find.textContaining('not a connection receipt'), findsNothing);
    expect(
      find.byKey(const Key('connection-doctor-technical-details')),
      findsNothing,
    );

    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    expectConnectionDoctorAnnouncement(
      tester,
      'Connection check could not finish. '
      'The tool returned unreadable results. '
      'No connection changes were made.',
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-check',
      'Check again',
      enabled: true,
    );
    semanticsHandle.dispose();
  });

  testWidgets('Connection help announces a thrown runner failure', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();
    runner.scripts.add(() async {
      throw StateError('simulated connection failure');
    });

    await openConnectionHelp(tester, runner);
    await tester.tap(find.byKey(const Key('connection-doctor-check')));
    await tester.pump();
    await tester.pump();

    expect(runner.calls, hasLength(1));
    expect(
      tester
          .widget<Text>(find.byKey(const Key('connection-doctor-status-title')))
          .data,
      'Connection check could not finish',
    );
    expect(
      tester
          .widget<Text>(
            find.byKey(const Key('connection-doctor-status-detail')),
          )
          .data,
      'The connection check could not finish. '
      'No connection changes were made.',
    );
    expect(find.textContaining('simulated connection failure'), findsNothing);

    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    expectConnectionDoctorAnnouncement(
      tester,
      'Connection check could not finish. '
      'The connection check could not finish. '
      'No connection changes were made.',
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-check',
      'Check again',
      enabled: true,
    );
    semanticsHandle.dispose();
  });

  testWidgets('Connection help repair cancels safely then runs confirmed Fix', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();
    final pendingResult = Completer<ProcessResult>();
    runner.scripts.add(() => pendingResult.future);

    await openConnectionHelp(tester, runner);
    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    final fixFinder = find.byKey(const Key('connection-doctor-fix'));

    await activateWithKeyboard(tester, fixFinder);

    expect(
      find.byKey(const Key('connection-doctor-repair-dialog')),
      findsOneWidget,
    );
    expect(find.text('Repair connection?'), findsOneWidget);
    expect(
      find.text(
        'This starts EngelChatLinkSvc and the local SSH tunnel, then checks '
        'Chat and Meeting Room again. It will not start providers or training.',
      ),
      findsOneWidget,
    );
    expect(runner.calls, isEmpty);
    final cancelFinder = find.byKey(
      const Key('connection-doctor-repair-cancel'),
    );
    final confirmFinder = find.byKey(
      const Key('connection-doctor-repair-confirm'),
    );
    expect(tester.getSize(cancelFinder).height, greaterThanOrEqualTo(48));
    expect(tester.getSize(confirmFinder).height, greaterThanOrEqualTo(48));
    expect(focusIsInside(cancelFinder), isTrue);

    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 360));
    expect(
      find.byKey(const Key('connection-doctor-repair-dialog')),
      findsNothing,
    );
    expect(runner.calls, isEmpty);

    await activateWithKeyboard(tester, fixFinder);
    await activateWithKeyboard(tester, confirmFinder);

    expect(runner.calls, hasLength(1));
    expect(runner.calls.single.executable, 'powershell.exe');
    expect(runner.calls.single.arguments, [
      '-NoProfile',
      '-ExecutionPolicy',
      'Bypass',
      '-File',
      connectionLoopDoctorLauncherPath,
      '-Json',
      '-Fix',
    ]);
    expect(
      tester
          .widget<Text>(find.byKey(const Key('connection-doctor-status-title')))
          .data,
      'Repairing connection…',
    );
    expect(
      tester
          .widget<Text>(
            find.byKey(const Key('connection-doctor-status-detail')),
          )
          .data,
      'Engel is starting its connection task and local SSH tunnel, then '
      'checking Chat and Meeting Room again. '
      'This repair does not start providers or training.',
    );
    expectConnectionDoctorAnnouncement(
      tester,
      'Repairing connection… '
      'Engel is starting its connection task and local SSH tunnel, then '
      'checking Chat and Meeting Room again. '
      'This repair does not start providers or training.',
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-check',
      'Check again',
      enabled: false,
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-fix',
      'Repairing…',
      enabled: false,
    );

    pendingResult.complete(
      connectionDoctorProcessResult(
        connectionDoctorV2Receipt(
          ok: true,
          overallState: 'ready',
          chatOnline: true,
          meetingRoomOnline: true,
          officeOnline: true,
          mode: 'fix',
        ),
        exitCode: 0,
      ),
    );
    await tester.pump();
    await tester.pump();

    expect(
      tester
          .widget<Text>(find.byKey(const Key('connection-doctor-status-title')))
          .data,
      'Connection repaired',
    );
    expect(
      tester
          .widget<Text>(
            find.byKey(const Key('connection-doctor-status-detail')),
          )
          .data,
      'Chat and Meeting Room are ready again.',
    );
    expectConnectionDoctorAnnouncement(
      tester,
      'Connection repaired. Chat and Meeting Room are ready again.',
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-go-chat',
      'Go to Chat',
      enabled: true,
    );
    semanticsHandle.dispose();
  });

  testWidgets(
    'Connection help routes guided Fix outcomes to the advanced doctor',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1500, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final scenarios = <({String overallState, String title, String summary})>[
        (
          overallState: 'setup_required',
          title: 'One-time setup is needed',
          summary:
              'The secure server connection needs one-time setup before '
              'Chat and Meeting Room can connect. Open the advanced doctor '
              'for guided setup.',
        ),
        (
          overallState: 'server_unreachable',
          title: 'Engel server is unavailable',
          summary:
              'The Engel server cannot be reached right now. Open the '
              'advanced doctor for guided server checks; your local files '
              'and tools still work.',
        ),
      ];

      for (final scenario in scenarios) {
        final runner = ScriptedProcessRunner();
        runner.scripts.add(
          () async => connectionDoctorProcessResult(
            connectionDoctorV2Receipt(
              ok: false,
              overallState: scenario.overallState,
              chatOnline: false,
              meetingRoomOnline: false,
              officeOnline: false,
              mode: 'fix',
            ),
            exitCode: 3,
          ),
        );

        await openConnectionHelp(tester, runner);
        await tester.tap(find.byKey(const Key('connection-doctor-fix')));
        await tester.pump();
        await tester.tap(
          find.byKey(const Key('connection-doctor-repair-confirm')),
        );
        await tester.pump();
        await tester.pump();

        expect(runner.calls, hasLength(1), reason: scenario.overallState);
        expect(
          runner.calls.single.arguments,
          contains('-Fix'),
          reason: scenario.overallState,
        );
        expect(
          tester
              .widget<Text>(
                find.byKey(const Key('connection-doctor-status-title')),
              )
              .data,
          scenario.title,
          reason: scenario.overallState,
        );
        expect(
          tester
              .widget<Text>(
                find.byKey(const Key('connection-doctor-status-detail')),
              )
              .data,
          scenario.summary,
          reason: scenario.overallState,
        );
        expectAccessibleButton(
          tester,
          'connection-doctor-open-app-primary',
          'Open advanced doctor',
          enabled: true,
        );
        expect(
          find.byKey(const Key('connection-doctor-fix')),
          findsNothing,
          reason: scenario.overallState,
        );
        expect(
          find.text('Try repair again'),
          findsNothing,
          reason: scenario.overallState,
        );

        final semanticsHandle = tester.ensureSemantics();
        await tester.pump();
        expectConnectionDoctorAnnouncement(
          tester,
          '${scenario.title}. ${scenario.summary}',
        );
        semanticsHandle.dispose();
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump();
      }
    },
  );

  testWidgets('Connection help exposes an advanced doctor launch failure', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();
    runner.scripts
      ..add(
        () async => connectionDoctorProcessResult(
          connectionDoctorV2Receipt(
            ok: false,
            overallState: 'setup_required',
            chatOnline: false,
            meetingRoomOnline: false,
            officeOnline: false,
          ),
          exitCode: 3,
        ),
      )
      ..add(
        () async => ProcessResult(
          703,
          9,
          '',
          'simulated advanced doctor launch failure',
        ),
      );

    await openConnectionHelp(tester, runner);
    await tester.tap(find.byKey(const Key('connection-doctor-check')));
    await tester.pump();
    await tester.pump();

    expect(
      tester
          .widget<Text>(find.byKey(const Key('connection-doctor-status-title')))
          .data,
      'One-time setup is needed',
    );
    final advancedDoctorFinder = find.byKey(
      const Key('connection-doctor-open-app-primary'),
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-open-app-primary',
      'Open advanced doctor',
      enabled: true,
    );
    final semanticsHandle = tester.ensureSemantics();
    await tester.ensureVisible(advancedDoctorFinder);
    await tester.pump();
    await tester.tap(advancedDoctorFinder);
    await tester.pump();
    await tester.pump();

    expect(runner.calls, hasLength(2));
    expect(runner.calls[1].arguments, [
      '-NoProfile',
      '-ExecutionPolicy',
      'Bypass',
      '-File',
      connectionLoopDoctorLauncherPath,
      '-App',
    ]);
    expect(
      runner.calls.where((call) => call.arguments.contains('-Fix')),
      isEmpty,
    );
    expect(
      find.byKey(const Key('connection-doctor-repair-dialog')),
      findsNothing,
    );
    expect(
      find.byKey(const Key('connection-doctor-action-message')),
      findsOneWidget,
    );
    const actionMessage =
        'The advanced doctor could not open. '
        'Technical details include the error.';
    expect(find.text(actionMessage), findsOneWidget);
    final announcement = tester
        .getSemantics(
          find.byKey(const Key('connection-doctor-status-announcement')),
        )
        .getSemanticsData();
    expect(announcement.label, contains(actionMessage));
    expect(announcement.flagsCollection.isLiveRegion, isTrue);

    final detailsToggle = find.byKey(
      const Key('connection-doctor-technical-details-toggle'),
    );
    await tester.ensureVisible(detailsToggle);
    await tester.pump();
    await tester.tap(detailsToggle);
    await tester.pump();

    expect(
      find.byKey(const Key('connection-doctor-technical-details')),
      findsOneWidget,
    );
    expect(find.textContaining('Advanced doctor open error:'), findsOneWidget);
    expect(
      find.textContaining('simulated advanced doctor launch failure'),
      findsOneWidget,
    );
    semanticsHandle.dispose();
  });

  testWidgets('Connection help keeps an Office-only partial fix connected', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();
    runner.scripts.add(
      () async => connectionDoctorProcessResult(
        connectionDoctorV2Receipt(
          ok: true,
          overallState: 'partial',
          chatOnline: true,
          meetingRoomOnline: true,
          officeOnline: false,
          mode: 'fix',
          repairOutcome: 'not_needed',
          status: 'connection services partially available',
          diagnosis: 'Office preview did not answer',
        ),
        exitCode: 0,
      ),
    );

    await openConnectionHelp(tester, runner);
    await tester.tap(find.byKey(const Key('connection-doctor-fix')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('connection-doctor-repair-confirm')));
    await tester.pump();
    await tester.pump();

    expect(runner.calls, hasLength(1));
    expect(runner.calls.single.arguments, contains('-Fix'));
    expect(
      tester
          .widget<Text>(find.byKey(const Key('connection-doctor-status-title')))
          .data,
      'Chat and Meeting Room are connected',
    );
    expect(
      tester
          .widget<Text>(
            find.byKey(const Key('connection-doctor-status-detail')),
          )
          .data,
      'Chat and Meeting Room are ready. '
      'Office preview is unavailable. No repair is needed.',
    );
    expect(
      find.textContaining('Office preview is unavailable'),
      findsOneWidget,
    );
    expect(find.text('Connection repaired'), findsNothing);
    expect(find.text('2 of 3 technical checks passed.'), findsOneWidget);
    expect(find.byKey(const Key('connection-doctor-fix')), findsNothing);

    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    expectConnectionDoctorAnnouncement(
      tester,
      'Chat and Meeting Room are connected. '
      'Chat and Meeting Room are ready. '
      'Office preview is unavailable. No repair is needed.',
    );
    expectAccessibleButton(
      tester,
      'connection-doctor-go-chat',
      'Go to Chat',
      enabled: true,
    );
    semanticsHandle.dispose();
  });

  testWidgets(
    'Connection help clears prior success after a malformed recheck',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1500, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final runner = ScriptedProcessRunner();
      const firstReceiptPath = r'D:\test\first-success.json';
      runner.scripts
        ..add(
          () async => connectionDoctorProcessResult(
            connectionDoctorV2Receipt(
              ok: true,
              overallState: 'ready',
              chatOnline: true,
              meetingRoomOnline: true,
              officeOnline: true,
              receiptPath: firstReceiptPath,
            ),
            exitCode: 0,
          ),
        )
        ..add(
          () async => ProcessResult(
            702,
            0,
            'not a connection receipt',
            'malformed output',
          ),
        );

      await openConnectionHelp(tester, runner);
      final checkFinder = find.byKey(const Key('connection-doctor-check'));
      await tester.tap(checkFinder);
      await tester.pump();
      await tester.pump();

      expect(find.text('3 of 3 technical checks passed.'), findsOneWidget);
      await tester.tap(
        find.byKey(const Key('connection-doctor-technical-details-toggle')),
      );
      await tester.pump();
      expect(find.text(firstReceiptPath), findsOneWidget);

      await tester.tap(checkFinder);
      await tester.pump();
      await tester.pump();

      expect(runner.calls, hasLength(2));
      expect(
        tester
            .widget<Text>(
              find.byKey(const Key('connection-doctor-status-title')),
            )
            .data,
        'Connection check could not finish',
      );
      expect(
        tester
            .widget<Text>(
              find.byKey(const Key('connection-doctor-status-detail')),
            )
            .data,
        'The tool returned unreadable results. '
        'No connection changes were made.',
      );
      expect(
        find.byKey(const Key('connection-doctor-check-count')),
        findsNothing,
      );
      expect(find.text('3 of 3 technical checks passed.'), findsNothing);
      expect(find.text(firstReceiptPath), findsNothing);
      expect(find.text(connectionLoopDoctorReportDir), findsOneWidget);
      expect(find.text('Chat and Meeting Room are connected'), findsNothing);

      final semanticsHandle = tester.ensureSemantics();
      await tester.pump();
      final chatStatus = tester
          .getSemantics(find.byKey(const Key('connection-doctor-chat-status')))
          .getSemanticsData();
      expect(
        chatStatus.label,
        'Chat status: Not checked. Questions and conversations with Engel',
      );
      final meetingStatus = tester
          .getSemantics(
            find.byKey(const Key('connection-doctor-meeting-room-status')),
          )
          .getSemanticsData();
      expect(
        meetingStatus.label,
        'Meeting Room status: Not checked. '
        'Shared agent work and live room status',
      );
      expectConnectionDoctorAnnouncement(
        tester,
        'Connection check could not finish. '
        'The tool returned unreadable results. '
        'No connection changes were made.',
      );
      semanticsHandle.dispose();
    },
  );

  testWidgets(
    'Connection help technical details expand and collapse from keyboard',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1500, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final runner = ScriptedProcessRunner();
      const receiptPath = r'D:\test\connection-doctor-partial.json';
      runner.scripts.add(
        () async => connectionDoctorProcessResult(
          connectionDoctorV2Receipt(
            ok: false,
            overallState: 'partial',
            chatOnline: false,
            meetingRoomOnline: true,
            officeOnline: false,
            status: 'connection services partially available',
            diagnosis: 'Chat did not answer',
            receiptPath: receiptPath,
          ),
          exitCode: 2,
        ),
      );

      await openConnectionHelp(tester, runner);
      await tester.tap(find.byKey(const Key('connection-doctor-check')));
      await tester.pump();
      await tester.pump();

      final detailsFinder = find.byKey(
        const Key('connection-doctor-technical-details'),
      );
      final toggleFinder = find.byKey(
        const Key('connection-doctor-technical-details-toggle'),
      );
      expect(detailsFinder, findsNothing);
      expect(find.text(engelMainServerChatHealthUrl), findsNothing);
      expect(find.text(meetingRoomServerHealthUrl), findsNothing);

      final semanticsHandle = tester.ensureSemantics();
      await tester.pump();
      expectAccessibleButton(
        tester,
        'connection-doctor-technical-details-toggle',
        'Show technical details',
        enabled: true,
      );

      await activateWithKeyboard(tester, toggleFinder);

      expect(detailsFinder, findsOneWidget);
      expect(find.text('Chat endpoint'), findsOneWidget);
      expect(find.text(engelMainServerChatHealthUrl), findsOneWidget);
      expect(find.text('Meeting Room endpoint'), findsOneWidget);
      expect(find.text(meetingRoomServerHealthUrl), findsOneWidget);
      expect(find.text('Server route'), findsOneWidget);
      expect(find.text('ssh root@192.0.2.50 -p 24622'), findsOneWidget);
      expect(find.textContaining('Receipt summary:'), findsOneWidget);
      expect(find.textContaining('"overall_state": "partial"'), findsOneWidget);
      expect(find.textContaining('"diagnostic_report_writes"'), findsOneWidget);
      expect(find.text(receiptPath), findsOneWidget);
      expectAccessibleButton(
        tester,
        'connection-doctor-technical-details-toggle',
        'Hide technical details',
        enabled: true,
      );
      expectAccessibleButton(
        tester,
        'connection-doctor-open-reports',
        'Open reports',
        enabled: true,
      );
      expectAccessibleButton(
        tester,
        'connection-doctor-open-app',
        'Open advanced doctor',
        enabled: true,
      );
      expect(runner.calls, hasLength(1));

      await activateWithKeyboard(tester, toggleFinder);

      expect(detailsFinder, findsNothing);
      expect(runner.calls, hasLength(1));
      semanticsHandle.dispose();
    },
  );

  testWidgets(
    'Connection help has no overflow at 1000x760 and 200 percent text',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 760));
      tester.platformDispatcher.textScaleFactorTestValue = 2.0;
      addTearDown(() {
        tester.binding.setSurfaceSize(null);
        tester.platformDispatcher.textScaleFactorTestValue = 1.0;
      });
      final runner = ScriptedProcessRunner();
      runner.scripts.add(
        () async => connectionDoctorProcessResult(
          connectionDoctorV2Receipt(
            ok: false,
            overallState: 'partial',
            chatOnline: false,
            meetingRoomOnline: true,
            officeOnline: false,
            status: 'connection services partially available',
            diagnosis: 'Chat did not answer',
          ),
          exitCode: 2,
        ),
      );

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          processRunner: runner.call,
          serverHealthProbe: () async => false,
        ),
      );
      await tester.pump();
      await tester.pump();
      await activateWithKeyboard(
        tester,
        find.byKey(const Key('chat-connection-doctor')),
      );

      expect(find.byKey(const Key('connection-doctor-page')), findsOneWidget);
      expect(tester.takeException(), isNull);
      final checkFinder = find.byKey(const Key('connection-doctor-check'));
      await tester.ensureVisible(checkFinder);
      await tester.pump();
      expect(tester.getSize(checkFinder).height, greaterThanOrEqualTo(48));
      expect(tester.getTopLeft(checkFinder).dy, greaterThanOrEqualTo(0));
      expect(tester.getBottomRight(checkFinder).dy, lessThanOrEqualTo(760));

      await tester.tap(checkFinder);
      await tester.pump();
      await tester.pump();

      expect(
        tester
            .widget<Text>(
              find.byKey(const Key('connection-doctor-status-title')),
            )
            .data,
        'Part of Engel is connected',
      );
      expect(tester.takeException(), isNull);
      final fixFinder = find.byKey(const Key('connection-doctor-fix'));
      await tester.ensureVisible(fixFinder);
      await tester.pump();
      expect(tester.getSize(fixFinder).height, greaterThanOrEqualTo(48));

      await tester.tap(fixFinder);
      await tester.pump();
      expect(
        find.byKey(const Key('connection-doctor-repair-dialog')),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      final cancelFinder = find.byKey(
        const Key('connection-doctor-repair-cancel'),
      );
      await tester.ensureVisible(cancelFinder);
      await tester.pump();
      expect(tester.getSize(cancelFinder).height, greaterThanOrEqualTo(48));
      await tester.tap(cancelFinder);
      await tester.pump();

      final toggleFinder = find.byKey(
        const Key('connection-doctor-technical-details-toggle'),
      );
      await tester.ensureVisible(toggleFinder);
      await tester.pump();
      expect(tester.getSize(toggleFinder).height, greaterThanOrEqualTo(48));
      await tester.tap(toggleFinder);
      await tester.pump();

      final detailsFinder = find.byKey(
        const Key('connection-doctor-technical-details'),
      );
      expect(detailsFinder, findsOneWidget);
      await tester.ensureVisible(detailsFinder);
      await tester.pump();
      expect(
        tester
            .getSize(find.byKey(const Key('connection-doctor-open-reports')))
            .height,
        greaterThanOrEqualTo(48),
      );
      expect(
        tester
            .getSize(find.byKey(const Key('connection-doctor-open-app')))
            .height,
        greaterThanOrEqualTo(48),
      );
      expect(tester.takeException(), isNull);
      expect(runner.calls, hasLength(1));
    },
  );

  testWidgets(
    'chat recovery has no overflow at 1000x760 and 200 percent text',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 760));
      tester.platformDispatcher.textScaleFactorTestValue = 2.0;
      addTearDown(() {
        tester.binding.setSurfaceSize(null);
        tester.platformDispatcher.textScaleFactorTestValue = 1.0;
      });
      final initialProbe = Completer<bool>();

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          serverHealthProbe: () => initialProbe.future,
        ),
      );
      await tester.pump();

      final recoveryFinder = find.byKey(const Key('chat-connection-recovery'));
      final retryFinder = find.byKey(const Key('chat-connection-retry'));
      final doctorFinder = find.byKey(const Key('chat-connection-doctor'));
      expect(find.text('Checking'), findsOneWidget);
      expect(recoveryFinder, findsOneWidget);
      expect(tester.getSize(retryFinder).height, greaterThanOrEqualTo(48));
      expect(tester.getSize(doctorFinder).height, greaterThanOrEqualTo(48));
      expect(tester.getRect(recoveryFinder).left, greaterThanOrEqualTo(0));
      expect(tester.getRect(recoveryFinder).right, lessThanOrEqualTo(1000));
      expect(tester.takeException(), isNull);

      await activateWithKeyboard(
        tester,
        find.byKey(const Key('main-server-status')),
      );
      await tester.pump();
      final statusDialog = find.byKey(
        const Key('chat-connection-status-dialog'),
      );
      expect(statusDialog, findsOneWidget);
      expect(find.text('Checking Chat'), findsOneWidget);
      final dialogRect = tester.getRect(statusDialog);
      expect(dialogRect.left, greaterThanOrEqualTo(0));
      expect(dialogRect.top, greaterThanOrEqualTo(0));
      expect(dialogRect.right, lessThanOrEqualTo(1000));
      expect(dialogRect.bottom, lessThanOrEqualTo(760));
      expect(
        tester
            .getSemantics(find.byKey(const Key('chat-connection-status-check')))
            .getSemanticsData()
            .hasAction(ui.SemanticsAction.tap),
        isFalse,
      );
      expect(tester.takeException(), isNull);
      await tester.tap(find.byKey(const Key('chat-connection-status-close')));
      await tester.pump(const Duration(milliseconds: 300));

      initialProbe.complete(false);
      await tester.pump();
      await tester.pump();

      expect(find.text('Unavailable'), findsOneWidget);
      expect(find.text('Chat unavailable'), findsOneWidget);
      expect(find.text('Try again'), findsOneWidget);
      expect(tester.getSize(retryFinder).height, greaterThanOrEqualTo(48));
      expect(tester.getSize(doctorFinder).height, greaterThanOrEqualTo(48));
      expect(tester.getRect(recoveryFinder).bottom, lessThanOrEqualTo(760));
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('offline chat submit preserves the draft and starts no runner', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();
    const draft = 'Keep this offline request ready to send.';

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        processRunner: runner.call,
        serverHealthProbe: () async => false,
      ),
    );
    await tester.pump();
    await tester.pump();
    await tapSideSection(tester, 'chat_runtime');

    final inputFinder = find.byKey(const Key('engel-chat-input'));
    final sendFinder = find.byKey(const Key('engel-chat-send'));
    await tester.enterText(inputFinder, draft);
    await tester.pump();
    expect(tester.widget<TextField>(inputFinder).controller?.text, draft);
    expect(tester.widget<FilledButton>(sendFinder).onPressed, isNotNull);

    await tester.tap(sendFinder);
    await tester.pump();

    expect(runner.calls, isEmpty);
    expect(tester.widget<TextField>(inputFinder).controller?.text, draft);
    expect(
      find.byKey(const ValueKey('mac-chat-bubble-thread-0')),
      findsNothing,
    );
    expect(
      find.text('Engel chat is unavailable. Your message is saved here.'),
      findsOneWidget,
    );
  });

  testWidgets(
    'unrelated work explains the wait, preserves drafts, and guards sends',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1600, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final processRunner = ScriptedProcessRunner();
      final pendingWork = Completer<ProcessResult>();
      processRunner.scripts.add(() => pendingWork.future);
      final chatCalls = <List<String>>[];
      const busyMessage =
          'Engel is finishing another task. Your message is saved here. '
          'Send will be available when it finishes.';
      const homeDraft = 'Keep this Home request while the check finishes.';
      const chatDraft = 'Keep this Chat request while the check finishes.';

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          processRunner: processRunner.call,
          localChatRunner:
              (executable, arguments, {workingDirectory, environment}) async {
                chatCalls.add(List<String>.from(arguments));
                return ProcessResult(
                  808,
                  0,
                  jsonEncode({
                    'ok': true,
                    'status': 'ok',
                    'assistant_reply':
                        'Busy-state draft sent after completion.',
                  }),
                  '',
                );
              },
          serverHealthProbe: () async => true,
          uiPreferencesPath: '',
        ),
      );
      await tester.pump();
      await tester.pump();
      await tapSideSection(tester, 'connection_doctor');
      await tester.tap(find.byKey(const Key('connection-doctor-check')));
      await tester.pump();

      expect(processRunner.calls, hasLength(1));
      await tapSideSection(tester, 'main');
      final homeNotice = find.byKey(const Key('home-other-work-notice'));
      expect(homeNotice, findsOneWidget);
      final homeSemantics = tester.widget<Semantics>(homeNotice);
      expect(homeSemantics.properties.liveRegion, isTrue);
      expect(homeSemantics.properties.label, busyMessage);

      final homeInput = find.byKey(const Key('home-chat-input'));
      await tester.enterText(homeInput, homeDraft);
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await tester.pump();

      expect(processRunner.calls, hasLength(1));
      expect(chatCalls, isEmpty);
      expect(tester.widget<TextField>(homeInput).controller?.text, homeDraft);

      await tapSideSection(tester, 'training');
      final trainingNotice = find.byKey(const Key('training-work-notice'));
      expect(trainingNotice, findsOneWidget);
      final trainingSemantics = tester.widget<Semantics>(trainingNotice);
      expect(trainingSemantics.properties.liveRegion, isTrue);
      expect(
        trainingSemantics.properties.label,
        contains('Your Training choices are saved'),
      );
      expect(
        tester
            .widget<Slider>(find.byKey(const Key('training-hours-slider')))
            .onChanged,
        isNull,
      );
      expect(
        tester
            .widget<FilledButton>(
              find.byKey(const Key('hour-training-control')),
            )
            .onPressed,
        isNull,
      );

      await tapSideSection(tester, 'chat_runtime');
      final chatNotice = find.byKey(const Key('chat-other-work-notice'));
      expect(chatNotice, findsOneWidget);
      final chatSemantics = tester.widget<Semantics>(chatNotice);
      expect(chatSemantics.properties.liveRegion, isTrue);
      expect(chatSemantics.properties.label, busyMessage);

      final chatInput = find.byKey(const Key('engel-chat-input'));
      await tester.enterText(chatInput, chatDraft);
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pump();

      expect(processRunner.calls, hasLength(1));
      expect(chatCalls, isEmpty);
      expect(tester.widget<TextField>(chatInput).controller?.text, chatDraft);
      expect(
        find.byKey(const ValueKey('mac-chat-bubble-thread-0')),
        findsNothing,
      );

      pendingWork.complete(
        connectionDoctorProcessResult(
          connectionDoctorV2Receipt(
            ok: true,
            overallState: 'ready',
            chatOnline: true,
            meetingRoomOnline: true,
            officeOnline: true,
          ),
          exitCode: 0,
        ),
      );
      await tester.pump();
      await tester.pump();

      expect(chatNotice, findsNothing);
      final sendFinder = find.byKey(const Key('engel-chat-send'));
      expect(tester.widget<FilledButton>(sendFinder).onPressed, isNotNull);
      await tester.tap(sendFinder);
      await tester.pumpAndSettle();

      expect(processRunner.calls, hasLength(1));
      expect(chatCalls, hasLength(1));
      expect(find.text(chatDraft), findsOneWidget);
      expect(
        find.textContaining('Busy-state draft sent after completion.'),
        findsWidgets,
      );

      await tapSideSection(tester, 'main');
      expect(homeNotice, findsNothing);
      expect(tester.widget<TextField>(homeInput).controller?.text, homeDraft);
      final homeChatReadiness = find.byKey(const Key('home-chat-readiness'));
      expect(
        find.descendant(of: homeChatReadiness, matching: find.text('ready')),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: homeChatReadiness,
          matching: find.text('connection ready'),
        ),
        findsNothing,
      );
    },
  );

  testWidgets('navigation is compact and search opens the exact subtool', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableDeviceStatusScan: false,
      ),
    );
    await tester.pump();

    for (final id in const [
      'chat_runtime',
      'status_console',
      'settings',
      'advanced_vault',
    ]) {
      expect(find.byKey(Key('section-$id')), findsOneWidget, reason: id);
    }
    for (final id in const [
      'main',
      'tasks',
      'local_llm',
      'training',
      'device_visibility',
      'agents',
      'goals',
      'command_center',
      'proof',
      'memory_guard',
      'build_pipeline',
    ]) {
      expect(find.byKey(Key('section-$id')), findsNothing, reason: id);
    }
    expect(find.byKey(const Key('toggle-advanced-navigation')), findsNothing);
    expect(find.text('Advanced tools'), findsNothing);

    await tester.tap(find.byKey(const Key('section-advanced_vault')));
    await tester.pumpAndSettle();
    expect(find.text('Advanced tools'), findsOneWidget);
    expect(
      find.textContaining('Reference items are not live controls'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('advanced-device_visibility')), findsOneWidget);
    expect(find.byKey(const Key('advanced-tasks')), findsOneWidget);
    expect(find.byKey(const Key('section-tab-agent_loops')), findsNothing);
    expect(find.byKey(const Key('section-tab-nmap_recon')), findsNothing);
    expect(find.byKey(const Key('section-tab-ai_terms')), findsNothing);

    await tester.enterText(find.byKey(const Key('section-search')), '');
    await tester.pump();
    await tester.enterText(find.byKey(const Key('section-search')), 'rag_lab');
    await tester.pump();
    await tester.tap(find.byKey(const Key('section-training')));
    await tester.pump();
    expect(find.text('RAG VISUAL LAB'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('section-search')), 'accounts');
    await tester.pump();
    await tester.tap(find.byKey(const Key('section-settings')));
    await tester.pump();
    expect(find.text('Engel Accounts and Connectors'), findsOneWidget);
    expect(find.byKey(const Key('section-tab-accounts')), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('section-search')),
      'product_surface',
    );
    await tester.pump();
    expect(find.byKey(const Key('section-settings')), findsOneWidget);
    expect(find.byKey(const Key('section-proof')), findsNothing);
    await tester.tap(find.byKey(const Key('section-settings')));
    await tester.pump();
    expect(find.text('Settings'), findsWidgets);
  });

  testWidgets('sidebar search exposes Connection Help and Enter opens it', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        processRunner: runner.call,
        serverHealthProbe: () async => true,
      ),
    );
    await tester.pump();
    await tester.pump();
    final semanticsHandle = tester.ensureSemantics();
    final searchFinder = find.byKey(const Key('section-search'));

    await tester.enterText(searchFinder, 'connection help');
    await tester.pump();

    expect(find.text('Connection Help'), findsOneWidget);
    expect(find.text('in Devices'), findsOneWidget);
    final searchResult = find.byKey(const Key('section-device_visibility'));
    final searchResultData = tester
        .getSemantics(searchResult)
        .getSemanticsData();
    expect(searchResultData.label, contains('Connection Help'));
    expect(searchResultData.label, contains('in Devices'));
    expect(searchResultData.label, contains('search result'));
    expect(searchResultData.flagsCollection.isButton, isTrue);

    await tester.testTextInput.receiveAction(TextInputAction.go);
    await tester.pump();
    await tester.pump();

    expect(find.byKey(const Key('connection-doctor-page')), findsOneWidget);
    expect(find.text('Connection help'), findsWidgets);
    expect(runner.calls, isEmpty);
    semanticsHandle.dispose();
  });

  testWidgets('Tasks explains Meeting Room readiness without server jargon', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableMeetingRoomStartup: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'tasks');

    expect(
      find.byKey(const Key('tasks-meeting-room-readiness')),
      findsOneWidget,
    );
    expect(find.text('Meeting Room needs connection'), findsOneWidget);
    expect(
      find.text(
        'You can keep drafting. Connect Meeting Room before you send work.',
      ),
      findsOneWidget,
    );
    expect(find.text('Connect Meeting Room'), findsOneWidget);
    expect(find.text('Server Online'), findsNothing);
    expect(find.text('Start Server'), findsNothing);
    expect(find.text('Refresh'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Tasks confirmation cancels safely then dispatches the preserved draft',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1500, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      const draft = 'Audit the worker status and return a concise report.';
      final chatPrompts = <String>[];

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          serverHealthProbe: () async => true,
          localChatRunner:
              (executable, arguments, {workingDirectory, environment}) async {
                chatPrompts.add(
                  File(promptFilePathFrom(arguments)).readAsStringSync(),
                );
                return ProcessResult(
                  chatPrompts.length,
                  0,
                  '{"assistant_reply":"task dispatched"}',
                  '',
                );
              },
        ),
      );
      await tester.pump();
      await tester.pump();
      await tapSideSection(tester, 'tasks');
      final taskInput = find.byKey(const Key('meeting-order-input'));
      final reviewButton = find.byKey(const Key('send-meeting-order'));

      await tester.enterText(taskInput, draft);
      await tester.pump();
      await tester.tap(reviewButton);
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('meeting-task-confirmation')),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: find.byKey(const Key('meeting-task-confirmation')),
          matching: find.textContaining(draft),
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining('could not confirm the current worker count'),
        findsOneWidget,
      );
      expect(chatPrompts, isEmpty);

      await tester.tap(find.byKey(const Key('meeting-task-cancel')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('meeting-task-confirmation')), findsNothing);
      expect(tester.widget<TextField>(taskInput).controller?.text, draft);
      expect(chatPrompts, isEmpty);

      await tester.tap(reviewButton);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('meeting-task-confirm')));
      await tester.pumpAndSettle();

      expect(chatPrompts, hasLength(1));
      expect(chatPrompts.single, contains(draft));
      expect(chatPrompts.single.toLowerCase(), contains('meeting room'));
      expect(find.byKey(const Key('engel-chat-thread')), findsOneWidget);
    },
  );

  testWidgets('Agents backend repair cancel makes no process call', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        processRunner: runner.call,
        serverHealthProbe: () async => true,
      ),
    );
    await tester.pump();
    await tester.pump();
    await tapSideSection(tester, 'agents');

    expect(find.byKey(const Key('agents-repair-backend')), findsNothing);
    await tester.tap(find.byKey(const Key('agents-more-tools')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('agents-repair-backend')));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('backend-autofix-confirmation')),
      findsOneWidget,
    );
    expect(find.text('Run backend repair agents?'), findsOneWidget);
    expect(runner.calls, isEmpty);

    await tester.tap(find.byKey(const Key('cancel-backend-autofix')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('backend-autofix-confirmation')), findsNothing);
    expect(runner.calls, isEmpty);
  });

  testWidgets(
    'Devices and System connection actions navigate without process calls',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1800, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final runner = RecordingProcessRunner();

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableDeviceStatusScan: false,
          deviceVisibilityOverride: deviceVisibilityFixture(),
          processRunner: runner.call,
          serverHealthProbe: () async => true,
        ),
      );
      await tester.pump();
      await tester.pump();

      await tapSideSection(tester, 'device_visibility');
      expect(find.text('1 worker needs attention'), findsOneWidget);
      expect(find.text('Open guided connection help'), findsOneWidget);
      await tester.tap(find.byKey(const Key('device-recommended-action')));
      await tester.pump();
      expect(find.byKey(const Key('connection-doctor-page')), findsOneWidget);
      expect(runner.calls, isEmpty);

      await tapSideSection(tester, 'command_center');
      await ensureTextVisible(tester, 'Connection help');
      await tester.tap(find.text('Connection help'));
      await tester.pump();
      expect(find.byKey(const Key('connection-doctor-page')), findsOneWidget);
      expect(runner.calls, isEmpty);

      await tapSideSection(tester, 'command_center');
      await ensureTextVisible(tester, 'System checks');
      await tester.tap(find.byKey(const Key('command-center-system-checks')));
      await tester.pump();
      expect(find.text('Check Engel safely'), findsOneWidget);
      expect(find.byKey(const Key('proof-recommended-check')), findsOneWidget);
      expect(runner.calls, isEmpty);
    },
  );

  testWidgets('Chat header stays limited after showing all tools', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        serverHealthProbe: () async => true,
      ),
    );
    await tester.pump();
    await tester.pump();
    await tapSideSection(tester, 'chat_runtime');

    void expectSimpleChatHeader() {
      expect(find.byKey(const Key('chat-new-chat')), findsOneWidget);
      expect(find.byKey(const Key('chat-talk')), findsOneWidget);
      expect(find.byKey(const Key('chat-tools-button')), findsOneWidget);
    }

    expectSimpleChatHeader();
    await tester.tap(find.byKey(const Key('section-advanced_vault')));
    await tester.pumpAndSettle();

    expect(find.textContaining('Reference items are not live controls'), findsOneWidget);
    expect(find.byKey(const Key('advanced-device_visibility')), findsOneWidget);
  });

  testWidgets('home quick controls perform real navigation and setup', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tester.enterText(find.byKey(const Key('section-search')), 'accounts');
    await tester.pump();
    await tester.testTextInput.receiveAction(TextInputAction.go);
    await tester.pump();
    expect(find.text('Engel Accounts and Connectors'), findsOneWidget);

    await tapSideSection(tester, 'main');
    await tester.tap(find.text('New note'));
    await tester.pump();
    expect(find.text('Project Ideas'), findsWidgets);
    expect(find.textContaining('New Note'), findsWidgets);

    await tapSideSection(tester, 'main');
    await tester.tap(find.byKey(const Key('home-wiki-one-shortcut')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byKey(const Key('wiki-one-title')), findsOneWidget);
    expect(find.byKey(const Key('wiki-one-body')), findsOneWidget);
    expect(find.byKey(const Key('wiki-one-subtitle')), findsOneWidget);
    expect(find.textContaining('Canonical second brain'), findsWidgets);

    await tapSideSection(tester, 'main');
    await tester.tap(find.text('Worker task'));
    await tester.pump();
    expect(find.text('Tasks'), findsWidgets);
    expect(find.text('Create a task'), findsOneWidget);
    expect(find.text('Advanced task tools'), findsOneWidget);
    expect(find.text('Backend Auto-Fix Agents'), findsNothing);
    await tester.tap(find.byKey(const Key('tasks-advanced-tools')));
    await tester.pump();
    expect(find.text('Backend Auto-Fix Agents'), findsOneWidget);
  });

  testWidgets('Home keeps unique actions and all shortcuts above the fold', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 860));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableDeviceStatusScan: false,
        serverHealthProbe: () async => true,
      ),
    );
    await tester.pump();
    await tester.pump();

    expect(find.byKey(const Key('mac-global-search')), findsNothing);
    expect(find.text('New chat'), findsNothing);
    expect(find.byKey(const Key('home-do-task')), findsOneWidget);
    expect(find.byKey(const Key('home-new-note')), findsOneWidget);
    expect(find.byKey(const Key('home-worker-task')), findsOneWidget);
    expect(find.byKey(const Key('home-chat-readiness')), findsOneWidget);
    expect(find.byKey(const Key('home-meeting-room-shortcut')), findsOneWidget);
    expect(
      find.byKey(const Key('home-worker-results-shortcut')),
      findsOneWidget,
    );
    final modelsShortcut = find.byKey(const Key('home-models-shortcut'));
    expect(modelsShortcut, findsOneWidget);
    expect(tester.getRect(modelsShortcut).top, greaterThanOrEqualTo(0));
    expect(tester.getRect(modelsShortcut).bottom, lessThanOrEqualTo(860));
    expect(tester.takeException(), isNull);
  });

  testWidgets('Home actions and shortcuts stay reachable at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableDeviceStatusScan: false,
        serverHealthProbe: () async => true,
      ),
    );
    await tester.pump();
    await tester.pump();

    expect(find.byKey(const Key('mac-global-search')), findsNothing);
    for (final key in const [
      Key('home-do-task'),
      Key('home-new-note'),
      Key('home-worker-task'),
      Key('home-chat-readiness'),
      Key('home-meeting-room-shortcut'),
      Key('home-worker-results-shortcut'),
      Key('home-models-shortcut'),
    ]) {
      final control = find.byKey(key);
      expect(control, findsOneWidget);
      await tester.ensureVisible(control);
      await tester.pump();
      final rect = tester.getRect(control);
      expect(rect.bottom, lessThanOrEqualTo(760));
      expect(rect.top, greaterThanOrEqualTo(0));
      expect(tester.takeException(), isNull);
    }
  });

  testWidgets('launch center shows canonical Engel ownership', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'launch_center');

    expect(find.text('Launch & app checks'), findsOneWidget);
    expect(find.text('App files'), findsOneWidget);
    expect(find.text('Which app opens'), findsOneWidget);
    expect(find.text('Compiled Release Identity'), findsOneWidget);
    expect(
      find.textContaining('Desktop shortcuts matching canonical:'),
      findsOneWidget,
    );
    expect(find.textContaining('Flutter UI payload:'), findsOneWidget);
    expect(find.textContaining('Requested dist legacy exe:'), findsWidgets);
    expect(find.textContaining('Build release executable:'), findsOneWidget);
    expect(
      find.textContaining('Desktop Engel Main shortcut ->'),
      findsOneWidget,
    );
    expect(find.text('Desktop Shortcut Targets'), findsOneWidget);
    expect(find.text('Engel shell'), findsOneWidget);
    expect(find.text('Verify the app'), findsOneWidget);
    expect(find.text('Verify included parts'), findsNothing);
    await tester.tap(find.byKey(const Key('launch-more-checks')));
    await tester.pumpAndSettle();
    expect(find.text('Verify included parts'), findsOneWidget);
  });

  testWidgets('launch center actions use six matching real commands', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'launch_center');
    await tester.tap(find.byKey(const Key('launch-more-checks')));
    await tester.pumpAndSettle();

    const actions = <String, List<String>>{
      'launch-ui-status': ['ui-shell', 'status'],
      'launch-ui-verify': ['ui-shell', 'verify'],
      'launch-workspace-verify': ['workspace-inventory', 'verify-all-parts'],
      'launch-legacy-verify': ['legacy-status', 'verify'],
      'launch-gateway-status': ['engel-agent', 'gateway-status'],
      'launch-parts-verify': ['workspace-inventory', 'verify-engel-parts'],
    };
    for (final action in actions.entries) {
      final finder = find.byKey(Key(action.key));
      expect(finder, findsOneWidget);
      await tester.tap(finder);
      await pumpAction(tester);
    }

    expect(
      runner.calls.map((call) => call.arguments).toList(),
      actions.values.toList(),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('device visibility exposes only live worker actions', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableDeviceStatusScan: false,
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'device_visibility');

    expect(find.text('Devices & Workers'), findsWidgets);
    expect(find.text('Check your device connections'), findsOneWidget);
    expect(find.text('Check connections'), findsOneWidget);
    expect(find.text('More device tools'), findsOneWidget);
    expect(find.text('Device map'), findsNothing);
    expect(find.text('Assign specific workers'), findsNothing);
    expect(find.text('Sub-Engel technical tools'), findsNothing);
    await tester.tap(find.byKey(const Key('device-more-tools')));
    await tester.pump();
    expect(find.text('Device map'), findsOneWidget);
    expect(find.text('Assign specific workers'), findsOneWidget);
    expect(find.text('Sub-Engel technical tools'), findsOneWidget);
    expect(find.text('Live connections'), findsOneWidget);
    expect(find.text('Phone workers'), findsOneWidget);
    expect(find.text('0 of 1 ready'), findsOneWidget);
    expect(find.text('Status has not been checked yet'), findsOneWidget);
    expect(find.text('Main device link - needs repair'), findsOneWidget);
    expect(
      find.text('Phones - Not checked - open Connection help'),
      findsOneWidget,
    );
    expect(
      find.text('Sub-Engel - Not checked - Last seen not available'),
      findsOneWidget,
    );
    expect(find.text('Phones — none checked.'), findsOneWidget);
    expect(
      find.text('Workers — 0 of 1 ready · 1 not checked.'),
      findsOneWidget,
    );
    expect(find.textContaining('registered'), findsNothing);
    expect(find.textContaining('last seen'), findsNothing);
    expect(find.textContaining('auto_apply='), findsNothing);
    expect(find.textContaining('127.0.0.1'), findsNothing);
    expect(find.textContaining('H action file:'), findsNothing);
    expect(find.textContaining('W network-logon audit:'), findsNothing);
    expect(find.text('Connection Evidence Matrix'), findsNothing);
    expect(find.text('Results'), findsNothing);
  });

  testWidgets(
    'Devices recommends worker tasks only when every worker is ready',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1600, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final runner = RecordingProcessRunner();

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableDeviceStatusScan: false,
          deviceVisibilityOverride: deviceVisibilityFixture(
            subEngel: EngelDeviceReadiness.ready,
          ),
          processRunner: runner.call,
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'device_visibility');

      expect(find.text('All 4 workers are ready'), findsOneWidget);
      expect(find.text('Send a worker task'), findsOneWidget);
      await tester.tap(find.byKey(const Key('device-recommended-action')));
      await tester.pump();

      expect(find.text('Engel Worker Dispatch'), findsOneWidget);
      expect(runner.calls, isEmpty);
    },
  );

  testWidgets('Devices advanced tools open by keyboard at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        deviceVisibilityOverride: deviceVisibilityFixture(),
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'device_visibility');

    expect(find.text('1 worker needs attention'), findsOneWidget);
    expect(find.byKey(const Key('device-swarm-map')), findsNothing);
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('device-more-tools')),
    );

    expect(find.byKey(const Key('device-swarm-map')), findsOneWidget);
    expect(find.byKey(const Key('device-worker-assignments')), findsOneWidget);
    expect(find.byKey(const Key('device-sub-engel-tools')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('device-sub-engel-tools')));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('retired settings hub resolves to Settings', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'settings_hub');

    expect(find.text('Settings'), findsWidgets);
    expect(find.text('Engel Settings Hub'), findsNothing);
    expect(find.text('Imported settings merged'), findsNothing);
  });

  testWidgets('AI terms tab renders all twelve animated concept cards', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'ai_terms');

    expect(find.text('12 AI TERMS'), findsOneWidget);
    expect(find.text('ALL IN MOTION.  ALL IN ONE PLACE.'), findsOneWidget);

    // Every card: numbered badge, title, and subtitle.
    const titles = <String, String>{
      '01': 'LLM',
      '02': 'HALLUCINATION',
      '03': 'TOKEN',
      '04': 'TRAIN vs INFER',
      '05': 'FINE-TUNING',
      '06': 'RLHF',
      '07': 'DISTILLATION',
      '08': 'RAG',
      '09': 'CHAIN OF THOUGHT',
      '10': 'WEIGHTS',
      '11': 'VALIDATION LOSS',
      '12': 'CODING AGENT',
    };
    titles.forEach((number, title) {
      expect(
        find.byKey(Key('ai-term-$number')),
        findsOneWidget,
        reason: number,
      );
      expect(find.text(number), findsWidgets, reason: number);
      expect(find.text(title), findsWidgets, reason: title);
    });
    expect(find.text('predict next token'), findsOneWidget);
    expect(find.text('confident ≠ correct'), findsOneWidget);
    expect(find.text('plan · act · test'), findsOneWidget);
    expect(find.text('MODEL RUNTIME'), findsOneWidget);
    expect(find.text('DEFINITION'), findsOneWidget);
    expect(find.text('IN ENGEL AI MAIN'), findsOneWidget);
    expect(find.text('VERIFY / WATCH'), findsOneWidget);
    expect(find.text('RELATED CONCEPTS'), findsOneWidget);
    expect(find.textContaining('probabilistic language'), findsOneWidget);
    expect(find.text('Open Models'), findsOneWidget);

    // The glyphs are painted, and the shared ticker keeps them moving.
    expect(find.byType(CustomPaint), findsWidgets);
    await tester.pump(const Duration(milliseconds: 400));
    expect(tester.takeException(), isNull);
  });

  testWidgets('Nmap recon tab renders eight NSE cards and the evasion panel', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'nmap_recon');

    expect(find.text('NMAP RECON'), findsOneWidget);
    // Authorized-use framing must be present, not optional.
    expect(find.textContaining('Authorized use only'), findsOneWidget);

    const names = <String, String>{
      '01': '-sC',
      '02': '--script vuln',
      '03': 'http-enum',
      '04': 'smb-os-discovery',
      '05': 'ftp-anon',
      '06': 'vulners',
      '07': 'dns-brute',
      '08': 'smb-vuln-ms17-010',
    };
    names.forEach((number, name) {
      expect(find.text('$number / 08'), findsOneWidget, reason: number);
      expect(find.text(name), findsWidgets, reason: name);
    });
    expect(find.text('★ BEST'), findsOneWidget);
    expect(find.textContaining(r'nmap -sC 192.168.1.10'), findsOneWidget);

    // Evasion panel: all seven flags, framed as testing your own defenses.
    expect(find.text('FIREWALL / IDS EVASION'), findsOneWidget);
    for (final flag in [
      '-f',
      '-D',
      '-S',
      '--spoof-mac',
      '-g',
      '--data-length',
      '--badsum',
    ]) {
      expect(find.text(flag), findsWidgets, reason: flag);
    }
    expect(find.text('Test on Swarm 3D'), findsOneWidget);

    expect(find.byType(CustomPaint), findsWidgets);
    await tester.pump(const Duration(milliseconds: 400));
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'AI terms inspector explains boundaries and opens real surfaces',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1900, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
      await tester.pump();

      await tapSideSection(tester, 'ai_terms');

      await tester.tap(find.byKey(const Key('ai-term-04')));
      await tester.pump(const Duration(milliseconds: 240));
      expect(find.text('MODEL LIFECYCLE'), findsOneWidget);
      expect(
        find.textContaining('Persistent memory and RAG can affect an answer'),
        findsOneWidget,
      );
      expect(find.textContaining('requires a new artifact'), findsOneWidget);
      expect(find.text('Open Training'), findsOneWidget);

      await tester.tap(find.byKey(const Key('ai-term-08')));
      await tester.pump(const Duration(milliseconds: 240));
      expect(find.text('INFERENCE RETRIEVAL'), findsOneWidget);
      expect(
        find.textContaining('Retrieval is not weight training'),
        findsOneWidget,
      );
      expect(find.text('Open Memory'), findsOneWidget);

      await tester.ensureVisible(find.byKey(const Key('ai-term-open-08')));
      await tester.tap(find.byKey(const Key('ai-term-open-08')));
      await tester.pump();
      expect(find.byKey(const Key('memory-page-title')), findsOneWidget);
      expect(find.text('Review proposed memories'), findsWidgets);
    },
  );

  testWidgets('AI terms wide related concept is a semantic keyboard button', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();
    await tapSideSection(tester, 'ai_terms');

    final relatedFinder = find.byKey(const Key('ai-term-related-01-08'));
    expect(relatedFinder, findsOneWidget);
    expect(tester.getSize(relatedFinder).height, greaterThanOrEqualTo(48));
    final announcementFinder = find.byKey(
      const Key('ai-term-inspector-announcement'),
    );
    expect(announcementFinder, findsOneWidget);
    expect(
      tester.widget<Semantics>(announcementFinder).properties.liveRegion,
      isTrue,
    );

    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();
    final relatedData = tester.getSemantics(relatedFinder).getSemanticsData();
    expect(relatedData.label, 'View related AI term 08: RAG');
    expect(relatedData.flagsCollection.isButton, isTrue);
    expect(relatedData.hasAction(ui.SemanticsAction.tap), isTrue);

    await activateWithKeyboard(tester, relatedFinder);

    expect(find.byKey(const Key('ai-term-detail-08')), findsOneWidget);
    expect(
      find.descendant(of: announcementFinder, matching: find.text('RAG')),
      findsOneWidget,
    );
    expect(find.text('INFERENCE RETRIEVAL'), findsOneWidget);
    expect(find.text('Open Memory'), findsOneWidget);
    semanticsHandle.dispose();
  });

  testWidgets(
    'AI terms compact selection and related navigation reveal inspector',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 760));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
      await tester.pump();
      await tapSideSection(tester, 'ai_terms');

      final ragCard = find.byKey(const Key('ai-term-08'));
      await tester.ensureVisible(ragCard);
      await tester.pump();
      await tester.tap(ragCard);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 16));
      await tester.pump(const Duration(milliseconds: 300));

      final ragDetail = find.byKey(const Key('ai-term-detail-08'));
      expect(ragDetail, findsOneWidget);
      expect(tester.getTopLeft(ragDetail).dy, inInclusiveRange(0.0, 759.0));

      final trainingRelated = find.byKey(const Key('ai-term-related-08-04'));
      await tester.ensureVisible(trainingRelated);
      await tester.pump();
      await tester.tap(trainingRelated);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 16));
      await tester.pump(const Duration(milliseconds: 300));

      final trainingDetail = find.byKey(const Key('ai-term-detail-04'));
      expect(trainingDetail, findsOneWidget);
      expect(
        tester.getTopLeft(trainingDetail).dy,
        inInclusiveRange(0.0, 759.0),
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('AI terms remain reachable at 200 percent text scale', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1024, 768));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();
    await tapSideSection(tester, 'ai_terms');

    for (var number = 1; number <= 12; number++) {
      final card = find.byKey(
        Key('ai-term-${number.toString().padLeft(2, '0')}'),
      );
      expect(card, findsOneWidget);
      await tester.ensureVisible(card);
      await tester.pump();
      expect(tester.takeException(), isNull, reason: 'AI term $number');
    }

    final codingAgentCard = find.byKey(const Key('ai-term-12'));
    await tester.tap(codingAgentCard);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 600));
    expect(find.byKey(const Key('ai-term-detail-12')), findsOneWidget);

    for (final label in const [
      'DEFINITION',
      'IN ENGEL AI MAIN',
      'VERIFY / WATCH',
      'RELATED CONCEPTS',
    ]) {
      final section = find.text(label);
      expect(section, findsOneWidget);
      await tester.ensureVisible(section);
      await tester.pump();
      expect(tester.takeException(), isNull, reason: label);
    }

    final openBuild = find.byKey(const Key('ai-term-open-12'));
    await tester.ensureVisible(openBuild);
    await tester.pump();
    expect(
      find.descendant(of: openBuild, matching: find.text('Open Build')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'AI terms wide layout has no overflow at 200 percent text scale',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1900, 1100));
      tester.platformDispatcher.textScaleFactorTestValue = 2.0;
      addTearDown(() {
        tester.binding.setSurfaceSize(null);
        tester.platformDispatcher.textScaleFactorTestValue = 1.0;
      });

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
      await tester.pump();
      await tapSideSection(tester, 'ai_terms');

      expect(find.byKey(const Key('ai-term-detail-01')), findsOneWidget);
      expect(find.byKey(const Key('ai-term-01')), findsOneWidget);
      expect(find.byKey(const Key('ai-term-12')), findsOneWidget);
      await tester.ensureVisible(find.byKey(const Key('ai-term-12')));
      await tester.pump();
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('AI terms honor reduced-motion preference', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.accessibilityFeaturesTestValue =
          const FakeAccessibilityFeatures();
    });

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();
    await tapSideSection(tester, 'ai_terms');

    final motionMode = tester.widget<TickerMode>(
      find.byKey(const Key('ai-terms-motion')),
    );
    expect(motionMode.enabled, isFalse);
    final glyphBuilder = find
        .descendant(
          of: find.byKey(const Key('ai-term-01')),
          matching: find.byType(AnimatedBuilder),
        )
        .first;
    final animation = tester.widget<AnimatedBuilder>(glyphBuilder).animation;
    expect(animation, isA<Animation<double>>());
    final reducedMotionAnimation = animation as Animation<double>;
    expect(reducedMotionAnimation.value, 0);
    if (reducedMotionAnimation is AnimationController) {
      expect(reducedMotionAnimation.isAnimating, isFalse);
    }

    await tester.pump(const Duration(seconds: 7));

    expect(reducedMotionAnimation.value, 0);
    expect(tester.takeException(), isNull);
  });

  testWidgets('AI term actions use current destination names', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();
    await tapSideSection(tester, 'ai_terms');

    const destinationLabels = <String, String>{
      '01': 'Open Models',
      '02': 'Open Proof',
      '03': 'Open Models',
      '04': 'Open Training',
      '05': 'Open Training',
      '06': 'Open Training',
      '07': 'Open Training',
      '08': 'Open Memory',
      '09': 'Open Proof',
      '10': 'Open Models',
      '11': 'Open Proof',
      '12': 'Open Build',
    };
    for (final entry in destinationLabels.entries) {
      final card = find.byKey(Key('ai-term-${entry.key}'));
      await tester.ensureVisible(card);
      await tester.pump();
      await tester.tap(card);
      await tester.pump(const Duration(milliseconds: 220));

      final action = find.byKey(Key('ai-term-open-${entry.key}'));
      expect(action, findsOneWidget, reason: entry.key);
      expect(
        find.descendant(of: action, matching: find.text(entry.value)),
        findsOneWidget,
        reason: entry.key,
      );
    }

    expect(find.text('Open Model Runtime'), findsNothing);
    expect(find.text('Open Expert Builder'), findsNothing);
    expect(find.text('Open Proof Console'), findsNothing);
    expect(find.text('Open Memory Guard'), findsNothing);
  });

  testWidgets('Mac settings modal exposes actionable setup tabs', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'settings');

    expect(find.text('Connections and API keys'), findsOneWidget);
    expect(find.text('Memory'), findsOneWidget);
    expect(find.text('Review saved context'), findsOneWidget);

    await tester.tap(find.byKey(const Key('settings-connections')));
    await tester.pumpAndSettle();

    expect(find.text('Connect an account'), findsOneWidget);
    expect(find.text('Engel Portal'), findsOneWidget);
    expect(find.text('Engel AI Main · NVIDIA NIM'), findsOneWidget);
    expect(find.text('OpenAI OAuth (ChatGPT)'), findsOneWidget);
    expect(find.text('xAI Grok'), findsOneWidget);

    await tester.tap(find.text('API keys'));
    await tester.pump();
    expect(find.text('NVIDIA NIM'), findsOneWidget);
    expect(find.text('OpenRouter'), findsOneWidget);
    expect(find.text('Anthropic'), findsOneWidget);
    expect(find.text('DashScope (Qwen)'), findsOneWidget);
    expect(find.text('Verify'), findsWidgets);

    await tester.tap(find.text('Workspace'));
    await tester.pump();
    expect(find.text('Workspace verify'), findsOneWidget);
    expect(find.text('Runtime readiness'), findsOneWidget);
    expect(find.text('Shared bus'), findsOneWidget);

    await tester.tap(find.text('Voice'));
    await tester.pump();
    expect(find.text('Voice search'), findsOneWidget);
    expect(find.text('Screen search'), findsOneWidget);
    expect(find.textContaining('This setup page is available'), findsNothing);

    await tester.tap(find.text('About'));
    await tester.pump();
    expect(find.text('Verify current release'), findsOneWidget);
    expect(find.text('Release manifest'), findsOneWidget);
  });

  testWidgets(
    'Settings keeps one safe model route and everyday choices above the fold',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1500, 860));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
      await tester.pump();
      await tapSideSection(tester, 'settings');

      expect(find.text('Everyday settings'), findsOneWidget);
      for (final key in const [
        Key('settings-models'),
        Key('settings-appearance'),
        Key('settings-connections'),
        Key('settings-memory'),
        Key('settings-devices'),
      ]) {
        expect(find.byKey(key), findsOneWidget);
      }
      expect(find.text('Thinking'), findsNothing);
      expect(find.text('Effort'), findsNothing);
      expect(find.text('Rescan'), findsNothing);
      expect(find.byKey(const Key('settings-tool-approvals')), findsNothing);
      expect(find.byKey(const Key('settings-system-tools')), findsNothing);

      final advancedToggle = find.byKey(const Key('settings-advanced-toggle'));
      expect(tester.getBottomRight(advancedToggle).dy, lessThanOrEqualTo(860));
      await tester.tap(advancedToggle);
      await tester.pump();
      expect(find.byKey(const Key('settings-tool-approvals')), findsOneWidget);
      expect(find.byKey(const Key('settings-system-tools')), findsOneWidget);

      await tapSideSection(tester, 'settings');
      await tester.tap(find.byKey(const Key('settings-models')));
      await tester.pump();
      expect(find.text('Choose models'), findsOneWidget);
      expect(
        find.textContaining('Open a choice, review it, then choose Apply'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'Settings choices remain readable and reachable at 200 percent text',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 760));
      tester.platformDispatcher.textScaleFactorTestValue = 2.0;
      addTearDown(() {
        tester.binding.setSurfaceSize(null);
        tester.platformDispatcher.textScaleFactorTestValue = 1.0;
      });

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
      await tester.pump();
      await tapSideSection(tester, 'settings');

      for (final key in const [
        Key('settings-models'),
        Key('settings-appearance'),
        Key('settings-connections'),
        Key('settings-memory'),
        Key('settings-devices'),
        Key('settings-advanced-toggle'),
      ]) {
        final control = find.byKey(key);
        await tester.ensureVisible(control);
        await tester.pump();
        expect(control, findsOneWidget);
        expect(tester.getSize(control).height, greaterThanOrEqualTo(48));
        expect(tester.takeException(), isNull, reason: key.toString());
      }

      final advancedToggle = find.byKey(const Key('settings-advanced-toggle'));
      await tester.tap(advancedToggle);
      await tester.pump();
      for (final key in const [
        Key('settings-tool-approvals'),
        Key('settings-system-tools'),
      ]) {
        final control = find.byKey(key);
        await tester.ensureVisible(control);
        await tester.pump();
        expect(tester.getSize(control).height, greaterThanOrEqualTo(64));
        expect(tester.takeException(), isNull, reason: key.toString());
      }
    },
  );

  testWidgets('all side navigation buttons select a functional surface', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    const sectionIds = [
      'main',
      'chat_runtime',
      'notes',
      'tasks',
      'local_llm',
      'code_languages',
      'settings',
      'device_swarm_3d',
      'launch_center',
      'mesh',
      'free_models',
      'model_runtime',
      'mobile_models',
      'cosmos',
      'meeting',
      'overlay_center',
      'device_visibility',
      'command_center',
      'route_matrix',
      'product_surface',
      'merge_ledger',
      'proof',
      'lan_gateway',
      'architect_planner',
      'agents',
      'worker_dispatch',
      'accounts',
      'research',
      'browser_queen',
      'expert_builder',
      'memory_guard',
      'skills',
      'tool_library',
      'agent_toolchain',
      'tool_gates',
      'artifacts',
      'cron',
      'messaging',
      'profiles',
      'sub_engel_link',
      'shared_bus',
      'runtime_workspace',
      'build_pipeline',
      'terminal_files',
      'sandbox_lab',
      'files',
      'settings_hub',
      'control',
    ];

    for (final sectionId in sectionIds) {
      await tapSideSection(tester, sectionId);
      expect(tester.takeException(), isNull, reason: sectionId);
      expect(
        find.byKey(const Key('section-search')),
        findsOneWidget,
        reason: sectionId,
      );
    }
  });

  testWidgets('device swarm 3D is actionable from settings and side nav', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'settings');
    expect(find.text('Devices and workers'), findsOneWidget);
    await tester.tap(find.byKey(const Key('settings-devices')));
    await tester.pump();

    expect(find.text('Engel Device Swarm 3D'), findsOneWidget);
    expect(find.text('Add Device'), findsOneWidget);
    expect(find.text('Find & Add Devices'), findsOneWidget);
    expect(find.text('Run identity audit'), findsOneWidget);
    expect(find.text('Scan network'), findsOneWidget);
    expect(find.text('ADB + LAN'), findsNothing);
    await tester.tap(find.byKey(const Key('swarm-discovery-more')));
    await tester.pumpAndSettle();
    expect(find.text('ADB + LAN'), findsOneWidget);
    expect(find.text('Start phone receiver'), findsOneWidget);
    expect(find.text('Android workers'), findsOneWidget);
    expect(find.text('IP / route'), findsOneWidget);
    expect(find.text('Class'), findsOneWidget);
    expect(find.text('Physical'), findsOneWidget);
    expect(find.text('Identity'), findsOneWidget);
    expect(find.text('Location'), findsOneWidget);
    expect(find.text('MAC'), findsOneWidget);
    expect(find.text('Evidence'), findsOneWidget);
    expect(find.text('Add selected'), findsOneWidget);
    expect(find.text('Unassigned LAN devices'), findsOneWidget);
    expect(find.text('Identify'), findsOneWidget);
    expect(find.text('Device Roster'), findsNothing);
    expect(find.text('Swarm Health'), findsNothing);
    expect(find.text('Swarm Source Inputs'), findsNothing);
    expect(find.text('Real Output'), findsNothing);
    expect(find.text('Open Device Surface'), findsNothing);
    expect(find.text('Open Device Visibility'), findsNothing);
    expect(
      find.text('drag orbit / tap node / double-click reset'),
      findsOneWidget,
    );

    await tapSideSection(tester, 'device_swarm_3d');
    expect(find.text('Engel Device Swarm 3D'), findsOneWidget);
    expect(find.text('Refresh devices'), findsOneWidget);
    expect(find.text('Scan network'), findsOneWidget);
    expect(find.text('Device Roster'), findsNothing);
    expect(find.text('Device status'), findsNothing);
    await tester.tap(find.byKey(const Key('swarm-more-tools')));
    await tester.pumpAndSettle();
    expect(find.text('Device status'), findsOneWidget);
  });

  testWidgets('settings dialog click-through covers every option tab', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final runner = RecordingProcessRunner();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'settings');
    await tester.tap(find.byKey(const Key('settings-connections')));
    await tester.pumpAndSettle();

    final tabExpectations = <String, String>{
      'Model': 'Edit Models',
      'Chat': 'New chat',
      'Appearance': 'Appearance preferences',
      'Workspace': 'Open workspace roots',
      'Safety': 'Tool approvals',
      'Memory & Context': 'Save current note',
      'Voice': 'Live chat trace',
      'Advanced': 'System tools',
      'Providers': 'Connect an account',
      'Accounts': 'OpenAI OAuth (ChatGPT)',
      'API keys': 'OpenRouter',
      'Gateway': 'Start Meeting Room server',
      'Tools & Keys': 'Tool library',
      'MCP': 'MCP and tools',
      'Archived Chats': 'Clear current chat',
      'About': 'Verify current release',
    };

    for (final entry in tabExpectations.entries) {
      await tester.tap(find.text(entry.key).last);
      await tester.pump();
      expect(find.text(entry.value), findsWidgets, reason: entry.key);
      expect(find.textContaining('This setup page is available'), findsNothing);
    }

    await tester.tap(find.text('Appearance').last);
    await tester.pump();
    await tester.tap(
      find.ancestor(
        of: find.text('UI diagnostics'),
        matching: find.byType(OutlinedButton),
      ),
    );
    await pumpAction(tester);

    expect(runner.calls, isNotEmpty);
    expect(runner.calls.last.arguments, contains('ui-shell'));
    expect(find.byKey(const Key('build-page-title')), findsOneWidget);
    expect(find.textContaining('fake_ui_audit'), findsOneWidget);
  });

  testWidgets('model picker and edit model controls are selectable', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'local_llm');
    await tester.tap(find.byKey(const Key('chat-model-picker-button')));
    await tester.pumpAndSettle();

    expect(find.text('Choose a chat model'), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('model-picker-search')),
      'Grok Build',
    );
    await tester.pump();

    expect(find.text('Grok Build 0.1'), findsWidgets);
    final modelRow = find
        .ancestor(
          of: find.text('Grok Build 0.1').first,
          matching: find.byType(InkWell),
        )
        .first;
    expect(tester.getSize(modelRow).height, greaterThanOrEqualTo(48));
    await tester.tap(find.byKey(const Key('model-picker-edit-models')));
    await tester.pumpAndSettle();

    expect(find.text('Models'), findsWidgets);
    expect(find.textContaining('models /'), findsOneWidget);
    await tester.tap(find.text('Reload registry'));
    await pumpAction(tester);
    await tester.tap(find.text('Write external model registry...'));
    await pumpAction(tester);
    await tester.tap(find.text('Add provider...'));
    await tester.pumpAndSettle();
    expect(find.text('Connect an account'), findsOneWidget);
  });

  testWidgets(
    'model choices require Apply and Cancel preserves the current model',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1600, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      String? savedConfig;
      const configPath = r'Z:\engel-model-router-widget-test.json';

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          enableDeviceStatusScan: false,
          uiPreferencesPath: '',
          modelRouterConfigPath: configPath,
          modelRouterConfigWriter: (path, contents) async {
            expect(path, configPath);
            savedConfig = contents;
          },
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'local_llm');

      await tester.tap(find.byKey(const Key('chat-model-picker-button')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('model-picker-search')),
        'Grok Build',
      );
      await tester.pump();
      await tester.tap(
        find.byKey(const Key('model-picker-option-grok-build-0-1')),
      );
      await tester.pump();
      expect(find.byKey(const Key('model-picker-dialog')), findsOneWidget);
      expect(find.byKey(const Key('model-picker-pending')), findsOneWidget);
      expect(savedConfig, isNull);

      await tester.tap(find.byKey(const Key('model-picker-cancel')));
      await tester.pumpAndSettle();
      expect(find.text('Chat: Auto Best'), findsWidgets);
      expect(savedConfig, isNull);

      await tester.tap(find.byKey(const Key('chat-model-picker-button')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('model-picker-search')),
        'Grok Build',
      );
      await tester.pump();
      await tester.tap(
        find.byKey(const Key('model-picker-option-grok-build-0-1')),
      );
      await tester.pump();
      final applyButton = find.byKey(const Key('model-picker-apply'));
      expect(tester.widget<FilledButton>(applyButton).onPressed, isNotNull);
      await tester.tap(applyButton);
      await tester.pump();
      await pumpUntil(
        tester,
        () => savedConfig != null,
        reason: 'Applied model choices were not passed to persistence.',
      );
      await pumpUntil(
        tester,
        () => find.text('Chat: Grok Build 0.1').evaluate().isNotEmpty,
        reason: 'Applied model choice did not update the Models UI.',
      );

      expect(find.text('Chat: Grok Build 0.1'), findsWidgets);
      expect(
        find.textContaining('Applied: Grok Build 0.1 for chat'),
        findsOneWidget,
      );
      final saved = jsonDecode(savedConfig!) as Map;
      expect(saved['selected_model_id'], 'grok-build-0-1');
    },
  );

  testWidgets('model picker Escape cancels an unapplied choice', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
        modelRouterConfigPath: r'Z:\engel-model-escape-widget-test.json',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'local_llm');
    final pickerButton = find.byKey(const Key('chat-model-picker-button'));
    await tester.ensureVisible(pickerButton);
    await tester.pump();
    await tester.tap(pickerButton);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('model-picker-search')),
      'Grok Build',
    );
    await tester.pump();
    await tester.tap(
      find.byKey(const Key('model-picker-option-grok-build-0-1')),
    );
    await tester.pump();

    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('model-picker-dialog')), findsNothing);
    expect(find.text('Chat: Auto Best'), findsWidgets);
  });

  testWidgets('failed model Apply keeps the previous model and explains why', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
        modelRouterConfigPath: r'Z:\engel-model-failure-widget-test.json',
        modelRouterConfigWriter: (path, contents) async {
          throw const FileSystemException('read-only test location');
        },
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'local_llm');
    await tester.tap(find.byKey(const Key('chat-model-picker-button')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('model-picker-search')),
      'Grok Build',
    );
    await tester.pump();
    await tester.tap(
      find.byKey(const Key('model-picker-option-grok-build-0-1')),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('model-picker-apply')));
    await pumpUntil(
      tester,
      () => find
          .text(
            'Could not apply model choices. Your previous choices are still active.',
          )
          .evaluate()
          .isNotEmpty,
      reason: 'A failed model save did not surface recovery guidance.',
    );

    expect(find.text('Chat: Auto Best'), findsWidgets);
    expect(find.text('Chat: Grok Build 0.1'), findsNothing);
  });

  testWidgets('model picker stacks and remains usable at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
        modelRouterConfigPath: r'Z:\engel-model-scale-widget-test.json',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'local_llm');
    final pickerButton = find.byKey(const Key('chat-model-picker-button'));
    await tester.ensureVisible(pickerButton);
    await tester.pump();
    await tester.tap(pickerButton);
    await tester.pumpAndSettle();

    final options = find.byKey(const Key('model-picker-options'));
    final optionsScroll = find.byKey(const Key('model-picker-options-scroll'));
    final modelList = find.byKey(const Key('model-picker-list'));
    expect(options, findsOneWidget);
    expect(optionsScroll, findsOneWidget);
    expect(modelList, findsOneWidget);
    expect(
      tester.getBottomLeft(optionsScroll).dy,
      lessThanOrEqualTo(tester.getTopLeft(modelList).dy),
    );
    expect(find.byKey(const Key('model-picker-cancel')), findsOneWidget);
    expect(find.byKey(const Key('model-picker-apply')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('core action buttons dispatch through real callbacks', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final runner = RecordingProcessRunner();
    String meetingChatPrompt = '';
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        // Meeting Room "Review and send" dispatches through the worker chat
        // lane (the proven fleet fan-out), not a rust submit. Stub the chat
        // runner so the test can assert the confirmed task reaches it.
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              try {
                meetingChatPrompt = File(
                  promptFilePathFrom(arguments),
                ).readAsStringSync();
              } catch (_) {}
              return ProcessResult(
                0,
                0,
                '{"assistant_reply":"dispatched"}',
                '',
              );
            },
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'local_llm');
    await tester.tap(find.byKey(const Key('models-advanced-tools')));
    await tester.pump();
    await tester.tap(
      find.ancestor(
        of: find.text('Check Runtime'),
        matching: find.byType(ActionChip),
      ),
    );
    await pumpAction(tester);
    expect(runner.calls.last.arguments, contains('local-llm'));
    expect(runner.calls.last.executable, contains('engel-ai-rs.exe'));

    await tapSideSection(tester, 'meeting');
    await tester.enterText(
      find.byType(TextField).last,
      'audit meeting room order button',
    );
    await tester.pump();
    await tester.tap(find.text('Review and send'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('meeting-task-confirmation')), findsOneWidget);
    await tester.tap(find.byKey(const Key('meeting-task-confirm')));
    await pumpAction(tester);
    // The confirmed task dispatches to the fleet through the worker chat lane;
    // the meeting-dispatch trigger prefix reaches the chat runner instead of a
    // rust native-submit.
    expect(meetingChatPrompt, contains('audit meeting room order button'));
    expect(meetingChatPrompt.toLowerCase(), contains('meeting room'));

    await tapSideSection(tester, 'tasks');
    await tester.tap(find.byKey(const Key('tasks-advanced-tools')));
    await tester.pump();
    await tester.enterText(
      find.byKey(const Key('tasks-sub-engel-order-input')),
      'audit sub-engel work order button',
    );
    await tester.pump();
    final sendWorkButton = find.byKey(const Key('tasks-write-sub-engel-order'));
    expect(tester.widget<FilledButton>(sendWorkButton).onPressed, isNotNull);
  });

  testWidgets('retired core catalog resolves to Command Center', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'mesh');

    expect(find.text('Command Center'), findsWidgets);
    expect(find.text('System checks'), findsOneWidget);
    expect(find.byKey(const Key('advanced-command-search')), findsOneWidget);
    expect(find.text('Results for Command Center'), findsOneWidget);
    expect(find.text('No result on Command Center yet.'), findsOneWidget);
    expect(find.text('Engel Core Runtime'), findsNothing);
    expect(find.text('RunPod Gate'), findsNothing);
  });

  testWidgets('retired model runtime resolves to Models', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'model_runtime');
    await tester.tap(find.byKey(const Key('models-advanced-tools')));
    await tester.pump();

    expect(find.text('Models'), findsWidgets);
    expect(find.text('Check Runtime'), findsOneWidget);
    expect(find.text('Run diagnostics'), findsOneWidget);
    expect(find.text('Verify Runtime'), findsOneWidget);
    expect(find.text('Engel Model Runtime'), findsNothing);
    expect(find.text('Model Intake'), findsNothing);
    expect(find.text('AirLLM Generate Plan'), findsNothing);
  });

  testWidgets('Models page exposes real runtime actions', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'local_llm');

    expect(find.text('Choose models'), findsOneWidget);
    expect(find.text('Runtime'), findsNothing);
    expect(find.text('Check Runtime'), findsNothing);
    expect(find.text('Run diagnostics'), findsNothing);
    expect(find.text('Verify Runtime'), findsNothing);
    await tester.tap(find.byKey(const Key('models-advanced-tools')));
    await tester.pump();
    expect(find.text('Runtime'), findsOneWidget);
    expect(find.text('Check Runtime'), findsOneWidget);
    expect(find.text('Run diagnostics'), findsOneWidget);
    expect(find.text('Repair Runtime'), findsNothing);
    expect(find.text('Verify Runtime'), findsOneWidget);
    expect(find.text('LLM Dashboard'), findsNothing);
    expect(find.text('GPU Info'), findsNothing);
    expect(find.text('llama.cpp Verify'), findsNothing);
  });

  testWidgets('Training page exposes real prompt training actions', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'training');

    expect(find.text('Training'), findsWidgets);
    expect(find.text('Prompt Training'), findsOneWidget);
    expect(find.text('Prepare Files'), findsOneWidget);
    expect(find.text('Test 3 Prompts'), findsOneWidget);
    expect(find.text('Refresh Status'), findsOneWidget);
    expect(find.text('Sync Training Assets'), findsNothing);
    expect(find.text('Smoke Through Chat'), findsNothing);
    expect(find.text('Refresh'), findsNothing);
    expect(find.text('Review 1-hour Prompt Training'), findsOneWidget);
    expect(find.byKey(const Key('hour-training-control')), findsOneWidget);
    expect(find.text('Prompt library'), findsOneWidget);
    expect(
      find.text('80 scheduled prompts across 8 hourly topics'),
      findsOneWidget,
    );
    expect(find.text('up to 10 prompts each hour'), findsNothing);
    expect(find.textContaining('22 tools'), findsNothing);
    expect(
      find.text('Files ready — all required assets present'),
      findsOneWidget,
    );
    expect(find.textContaining('scripts /'), findsNothing);
    expect(find.byKey(const Key('training-compact-status')), findsOneWidget);
    expect(find.text('Training files'), findsOneWidget);
    expect(find.text('Open prompt folder'), findsNothing);
    await tester.ensureVisible(find.byKey(const Key('training-files-tools')));
    await tester.tap(find.byKey(const Key('training-files-tools')));
    await tester.pumpAndSettle();
    expect(find.text('Open prompt folder'), findsOneWidget);
    expect(find.text('Open prompt template'), findsOneWidget);
    expect(find.textContaining(r'memory\training\engel_main'), findsNothing);
  });

  testWidgets('Training names missing files instead of showing only a count', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-missing-assets-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final manifest = File(
      '${fixtures.path}${Platform.pathSeparator}training_assets_manifest.json',
    );
    manifest.writeAsStringSync(
      jsonEncode({
        'ok': false,
        'template_prompt_count': 10,
        'template_hourly_cycle_count': 8,
        'template_maximum_prompt_count': 80,
        'missing': [
          r'D:\training\ENGEL_SYSTEM.md',
          r'D:\training\route_guard.py',
          r'D:\training\worker_policy.json',
        ],
      }),
    );

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
        trainingAssetsManifestPathOverride: manifest.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find
          .byKey(const Key('training-missing-assets'))
          .evaluate()
          .isNotEmpty,
      reason: 'The missing Training file notice did not appear.',
    );

    expect(find.text('3 required Training files are missing'), findsOneWidget);
    expect(find.text('- ENGEL_SYSTEM.md'), findsOneWidget);
    expect(find.text('- route_guard.py'), findsOneWidget);
    expect(find.text('- worker_policy.json'), findsOneWidget);
    expect(find.textContaining('Choose Prepare Files below'), findsOneWidget);
    expect(find.byKey(const Key('training-prepare-files')), findsOneWidget);
  });

  testWidgets(
    'Goals window renders meters and the month planner from the plan',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1400, 1000));
      final fixtures = Directory.systemTemp.createTempSync('engel-goal-plan-');
      addTearDown(() {
        if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
      });
      final plan = File(
        '${fixtures.path}${Platform.pathSeparator}ENGEL_GOAL_PLAN.json',
      );
      plan.writeAsStringSync(
        jsonEncode({
          'schema': 'engel_goal_plan_v1',
          'generated_at_utc': '2026-08-10T12:00:00+00:00',
          'goal_count': 2,
          'goals': {
            'ship_goal_calendar_1234abcd': {
              'slug': 'ship_goal_calendar_1234abcd',
              'goal': 'ship the goal calendar',
              'status': 'running',
              'rounds_spent': 10,
              'progress_percent': 40,
              'progress_state': 'in_progress',
              'progress_basis': 'estimate from 10/25 rounds',
              'operator_start_date': '2026-08-03',
              'operator_due_date': '2026-08-28',
              'projected_finish_date': '2026-08-15',
              'projected_finish_basis': '15 rounds left at 2.0h/round observed',
              'projected_finish_projectable': true,
            },
            'morning_health_sweep_5678efab': {
              'slug': 'morning_health_sweep_5678efab',
              'goal': 'morning health sweep',
              'status': 'done',
              'rounds_spent': 4,
              'progress_percent': 100,
              'progress_state': 'done',
              'progress_basis': 'goal record reports status=done, ok=true',
              'operator_start_date': '',
              'operator_due_date': '',
              'projected_finish_date': '2026-08-09',
              'projected_finish_basis': 'already done',
              'projected_finish_projectable': false,
            },
          },
        }),
      );

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableDeviceStatusScan: false,
          uiPreferencesPath: '',
          goalPlanPath: plan.path,
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'goals');
      await pumpUntil(
        tester,
        () => find
            .byKey(const Key('goal-meter-ship_goal_calendar_1234abcd'))
            .evaluate()
            .isNotEmpty,
        reason: 'The goal meter did not appear.',
      );

      expect(
        find.descendant(
          of: find.byKey(const Key('goal-meter-ship_goal_calendar_1234abcd')),
          matching: find.text('ship the goal calendar'),
        ),
        findsOneWidget,
      );
      expect(find.text('In progress · 40%'), findsOneWidget);
      expect(find.text('Done · 100%'), findsOneWidget);
      expect(
        find.textContaining('starts 2026-08-03'),
        findsOneWidget,
        reason: 'operator start date renders on the meter',
      );
      expect(
        find.textContaining('Engel projects 2026-08-15'),
        findsOneWidget,
        reason: "Engel's projected finish renders on the meter",
      );
      expect(find.byKey(const Key('goals-month-grid')), findsOneWidget);
      expect(find.byKey(const Key('goals-month-label')), findsOneWidget);
      expect(find.textContaining('Plan generated 2026-08-10'), findsOneWidget);
    },
  );

  testWidgets('Agent Loops draws the harness, goal loop, and rule diagrams', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableDeviceStatusScan: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'agent_loops');

    final tab = find.byKey(const Key('section-tab-agent_loops'));
    expect(tab, findsOneWidget);
    await tester.tap(tab);
    await tester.pumpAndSettle();

    // The figures are painted, not images: a CustomPaint carrying a painter.
    for (final id in const [
      'agent-loops-harness-diagram',
      'agent-loops-loop-diagram',
    ]) {
      final finder = find.byKey(Key(id));
      expect(finder, findsOneWidget, reason: id);
      expect(tester.widget<CustomPaint>(finder).painter, isNotNull, reason: id);
    }

    // Every production rule carries its own drawn spark. pumpAndSettle above
    // paints the whole scroll child, so a painter that threw would fail here.
    for (var rule = 1; rule <= 12; rule++) {
      final finder = find.byKey(Key('agent-loops-rule-spark-$rule'));
      expect(finder, findsOneWidget, reason: 'rule $rule spark');
      expect(
        tester.widget<CustomPaint>(finder).painter,
        isNotNull,
        reason: 'rule $rule painter',
      );
    }

    expect(find.text('Agent Loops'), findsWidgets);
  });

  testWidgets(
    'Failed Training explains local-only proof and reviews before retry',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 760));
      tester.platformDispatcher.textScaleFactorTestValue = 2.0;
      addTearDown(() {
        tester.binding.setSurfaceSize(null);
        tester.platformDispatcher.textScaleFactorTestValue = 1.0;
      });
      final fixtures = Directory.systemTemp.createTempSync(
        'engel-training-failed-receipt-',
      );
      addTearDown(() {
        if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
      });
      final sentinel = File(
        '${fixtures.path}${Platform.pathSeparator}active.json',
      );
      final session = File(
        '${fixtures.path}${Platform.pathSeparator}session.json',
      );
      sentinel.writeAsStringSync(
        jsonEncode({
          'schema': 'engel_ui_local_only_training_active_v1',
          'status': 'FAILED',
          'expires_at_epoch': 0,
        }),
      );
      session.writeAsStringSync(
        jsonEncode({
          'summary': {'prompts_completed': 18, 'prompts_requested': 20},
          'blockers': [
            'strict local-only run contains a turn not verified as local LLM only',
          ],
        }),
      );
      final starter = RecordingTrainingProcessStarter();

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          trainingProcessStarter: starter.call,
          uiPreferencesPath: '',
          trainingActiveSentinelPathOverride: sentinel.path,
          trainingSessionReceiptPathOverride: session.path,
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'training');
      final refresh = tester
          .widget<OutlinedButton>(
            find.byKey(const Key('training-refresh-status')),
          )
          .onPressed;
      expect(refresh, isNotNull);
      refresh!();
      await pumpUntil(
        tester,
        () => find
            .byKey(const Key('training-compact-status-detail'))
            .evaluate()
            .isNotEmpty,
        reason: 'The failed Training detail did not appear.',
      );

      expect(find.textContaining('18 of 20 complete'), findsOneWidget);
      expect(
        tester
            .widget<Text>(
              find.byKey(const Key('training-compact-status-detail')),
            )
            .data,
        contains(
          'One completed prompt did not include the required proof that it '
          'used only Engel\'s local model.',
        ),
      );
      expect(find.textContaining('strict local-only run'), findsNothing);
      expect(find.byKey(const Key('training-recovery-state')), findsOneWidget);
      expect(tester.takeException(), isNull);
      final retry = find.byKey(const Key('training-recovery-try-again'));
      expect(find.text('Review and try again'), findsOneWidget);
      await tester.ensureVisible(retry);
      await tester.tap(retry);
      await tester.pumpAndSettle();

      expect(find.text('Start one-hour training?'), findsOneWidget);
      expect(starter.calls, isEmpty);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(starter.calls, isEmpty);
    },
  );

  testWidgets(
    'Completed Training reports missing and excluded prompts honestly',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1400, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final fixtures = Directory.systemTemp.createTempSync(
        'engel-training-partial-receipt-',
      );
      addTearDown(() {
        if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
      });
      final logLine =
          '${jsonEncode({'event': 'flutter_paced_wait', 'run_id': 'partial-run-1', 'completed_prompts': 30, 'status': 'PASS'})}\n';
      final utf16LeLog = <int>[0xff, 0xfe];
      for (final codeUnit in logLine.codeUnits) {
        utf16LeLog
          ..add(codeUnit & 0xff)
          ..add((codeUnit >> 8) & 0xff);
      }
      final log = File('${fixtures.path}${Platform.pathSeparator}run.jsonl')
        ..writeAsBytesSync(utf16LeLog);
      final sentinel =
          File('${fixtures.path}${Platform.pathSeparator}active.json')
            ..writeAsStringSync(
              jsonEncode({
                'schema': 'engel_ui_local_only_training_active_v1',
                'run_id': 'partial-run-1',
                'status': 'COMPLETE',
                'requested_prompts': 30,
                'log': log.path,
                'expires_at_epoch': 0,
              }),
            );
      final session =
          File('${fixtures.path}${Platform.pathSeparator}session.json')
            ..writeAsStringSync(
              jsonEncode({
                'run_id': 'partial-run-1',
                'status': 'PASS',
                'summary': {
                  'prompts_requested': 30,
                  'prompts_completed': 28,
                  'training_pack_rows': 28,
                  'training_pack_admitted': 18,
                },
                'blockers': <String>[],
              }),
            );

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          uiPreferencesPath: '',
          trainingActiveSentinelPathOverride: sentinel.path,
          trainingSessionReceiptPathOverride: session.path,
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'training');
      tester
          .widget<OutlinedButton>(
            find.byKey(const Key('training-refresh-status')),
          )
          .onPressed!();
      await pumpUntil(
        tester,
        () => find
            .text('Last training completed with exclusions')
            .evaluate()
            .isNotEmpty,
      );

      expect(find.textContaining('28 / 30 prompts'), findsOneWidget);
      expect(find.textContaining('18 admitted and 10 excluded'), findsWidgets);
      expect(find.textContaining('completed successfully'), findsNothing);
    },
  );

  testWidgets('Training page exposes every curriculum and lets one be chosen', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-fresh-catalog-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final indexFile = writeFreshEightHourCurriculaIndex(fixtures);

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
        trainingCurriculaIndexPathOverride: indexFile.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    // The curriculum index is read asynchronously after the manifest scan.
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }

    expect(find.byKey(const Key('training-curriculum-picker')), findsOneWidget);
    // The operator contract is five stable identities. Fresh generated material
    // replaces a spent canonical slot; it must never appear as a sixth tile.
    final pickerIndex =
        jsonDecode(indexFile.readAsStringSync()) as Map<String, dynamic>;
    final curricula = (pickerIndex['curricula'] as List)
        .cast<Map<String, dynamic>>();
    expect(curricula, hasLength(5));
    expect(curricula.map((entry) => entry['id']).toList(), const [
      'capabilities',
      'math_school',
      'self_build',
      'construction',
      'chat_communication',
    ]);
    expect(
      curricula.every(
        (entry) =>
            entry['novelty_ready'] == true &&
            entry['novel_hours_available'] == 8 &&
            entry['prompt_count'] == 80,
      ),
      isTrue,
      reason: 'all five slots must hold one fresh eight-hour set',
    );
    for (final entry in curricula) {
      expect(
        find.byKey(Key('training-curriculum-tile-${entry['id']}')),
        findsOneWidget,
        reason: 'curriculum ${entry['id']} chip should render',
      );
    }
    // The active curriculum is selected by default and shows its detail.
    expect(find.text('DEFAULT'), findsOneWidget);
    expect(
      find.textContaining('Eight new artifact-grounded capability audits'),
      findsOneWidget,
    );

    // Choosing another curriculum updates the shown detail.
    await tester.tap(
      find.byKey(const Key('training-curriculum-tile-math_school')),
    );
    await tester.pump();
    expect(find.textContaining('Eighty new declared problems'), findsOneWidget);
    expect(
      find.textContaining('Eight new artifact-grounded capability audits'),
      findsNothing,
    );
  });

  testWidgets('Exhausted curriculum is visible but cannot be selected or run', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-exhausted-curriculum-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final index =
        File('${fixtures.path}${Platform.pathSeparator}curricula_index.json')
          ..writeAsStringSync(
            jsonEncode({
              'active_id': 'capabilities',
              'curricula': [
                {
                  'id': 'capabilities',
                  'title': 'Engel Capabilities',
                  'detail': 'Already used material.',
                  'template_path': '${fixtures.path}\\used.json',
                  'topic_count': 8,
                  'prompt_count': 80,
                  'maximum_hours': 8,
                  'novel_hours_available': 0,
                  'novelty_ready': false,
                  'novelty_status': 'EXHAUSTED',
                  'topics': List<String>.generate(8, (index) => 'Used $index'),
                  'active': true,
                },
                {
                  'id': 'math_school',
                  'title': 'Math School',
                  'detail': 'Eight unused renewal hours.',
                  'template_path': '${fixtures.path}\\ready.json',
                  'topic_count': 8,
                  'prompt_count': 80,
                  'maximum_hours': 8,
                  'novel_hours_available': 8,
                  'novelty_ready': true,
                  'novelty_status': 'READY',
                  'topics': List<String>.generate(8, (index) => 'New $index'),
                  'active': false,
                },
              ],
            }),
          );

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
        trainingCurriculaIndexPathOverride: index.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find
          .byKey(const Key('training-curriculum-tile-math_school'))
          .evaluate()
          .isNotEmpty,
    );

    // (2026-08-11) Spent material is no longer offered as a choice: a chip that
    // cannot start is a dead end that also pushed Start below the fold. It is
    // still named, so the picker never hides that the curriculum exists.
    expect(
      find.byKey(const Key('training-curriculum-tile-capabilities')),
      findsNothing,
      reason: 'a curriculum with no unused material is not offered',
    );
    expect(find.text('USED'), findsNothing);
    final outOfMaterial = find.byKey(
      const Key('training-curricula-out-of-material'),
    );
    expect(outOfMaterial, findsOneWidget);
    expect(
      tester.widget<Text>(outOfMaterial).data,
      contains('Engel Capabilities'),
      reason: 'the spent curriculum is named, not hidden',
    );
    expect(
      tester.widget<Text>(outOfMaterial).data,
      contains('Prepare Files'),
      reason: 'the operator is told how to renew it',
    );
    expect(find.textContaining('1 of 2 ready'), findsOneWidget);
    expect(find.text('Eight unused renewal hours.'), findsOneWidget);
  });

  testWidgets('Each canonical curriculum offers eight novel hours', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-eight-hour-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final indexFile = writeFreshEightHourCurriculaIndex(fixtures);

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
        trainingCurriculaIndexPathOverride: indexFile.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    // Wait on a curriculum that still has material: spent ones are no longer
    // rendered as chips, so waiting for chat_communication would never settle.
    await pumpUntil(
      tester,
      () => find
          .byKey(const Key('training-curriculum-tile-math_school'))
          .evaluate()
          .isNotEmpty,
    );

    final hoursFinder = find.byKey(const Key('training-hours-slider'));
    final index =
        jsonDecode(indexFile.readAsStringSync()) as Map<String, dynamic>;
    final curricula = (index['curricula'] as List).cast<Map<String, dynamic>>();
    expect(curricula, hasLength(5));
    expect(curricula.map((entry) => entry['id']).toList(), const [
      'capabilities',
      'math_school',
      'self_build',
      'construction',
      'chat_communication',
    ]);
    for (final curriculum in curricula) {
      final id = '${curriculum['id']}';
      expect(curriculum['maximum_hours'], 8, reason: '$id renewal material');
      expect(curriculum['prompt_count'], 80, reason: '$id prompt count');
      expect(curriculum['novelty_ready'], isTrue, reason: '$id ready');
      expect(
        curriculum['novelty_fully_ready'],
        isTrue,
        reason: '$id fully ready',
      );
      expect(curriculum['novel_hours_available'], 8, reason: '$id novel hours');

      final tile = find.byKey(Key('training-curriculum-tile-$id'));
      await tester.ensureVisible(tile);
      await tester.tap(tile);
      await tester.pump();
      final slider = tester.widget<Slider>(hoursFinder);
      expect(slider.max, 8, reason: '$id offers all eight novel hours');
      expect(slider.divisions, 7);
    }
  });

  testWidgets('Training start and status are visible without scrolling', (
    WidgetTester tester,
  ) async {
    const viewport = Size(1500, 860);
    await tester.binding.setSurfaceSize(viewport);
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');

    for (final key in const [
      Key('training-compact-status'),
      Key('hour-training-control'),
      Key('training-apply-models'),
    ]) {
      final rect = tester.getRect(find.byKey(key));
      expect(rect.top, greaterThanOrEqualTo(0), reason: '$key top');
      expect(
        rect.bottom,
        lessThanOrEqualTo(viewport.height),
        reason: '$key bottom',
      );
    }
  });

  testWidgets('one Training test reports pending and completion in place', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();
    final pending = Completer<ProcessResult>();
    runner.scripts.add(() => pending.future);

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        processRunner: runner.call,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');

    final testOne = tester
        .widget<OutlinedButton>(find.byKey(const Key('training-test-one')))
        .onPressed;
    expect(testOne, isNotNull);
    testOne!();
    await pumpUntil(
      tester,
      () => runner.calls.isNotEmpty,
      reason: 'The one-Training test did not reach the process runner.',
    );

    expect(runner.calls, hasLength(1));
    expect(find.text('Testing 3 local prompts'), findsWidgets);
    expect(find.byKey(const Key('training-work-notice')), findsOneWidget);
    expect(
      tester
          .widget<OutlinedButton>(find.byKey(const Key('training-test-one')))
          .onPressed,
      isNull,
    );

    pending.complete(ProcessResult(901, 0, '{"ok":true}', ''));
    await pumpUntil(
      tester,
      () => find.text('Three-prompt test passed').evaluate().isNotEmpty,
      reason: 'The completed one-Training result did not appear.',
    );

    expect(find.text('Three-prompt test passed'), findsWidgets);
    expect(find.byKey(const Key('training-work-notice')), findsNothing);
  });

  testWidgets('one Training test uses the selected curriculum and targets', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();
    runner.scripts.add(() async => ProcessResult(902, 0, '{"ok":true}', ''));
    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-one-test-curriculum-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final indexFile = writeFreshEightHourCurriculaIndex(fixtures);

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        processRunner: runner.call,
        uiPreferencesPath: '',
        trainingCurriculaIndexPathOverride: indexFile.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find
          .byKey(const Key('training-curriculum-tile-math_school'))
          .evaluate()
          .isNotEmpty,
    );
    await tester.tap(
      find.byKey(const Key('training-curriculum-tile-math_school')),
    );
    await tester.pump();

    tester
        .widget<OutlinedButton>(find.byKey(const Key('training-test-one')))
        .onPressed!();
    await pumpUntil(tester, () => runner.calls.isNotEmpty);
    final args = runner.calls.single.arguments;
    expect(
      args[args.indexOf('--template') + 1],
      contains('ENGEL_TEMPLATE_MATH_SCHOOL.json'),
    );
    expect(args[args.indexOf('--training-targets') + 1], 'slm,llm');
    expect(args[args.indexOf('--training-level') + 1], 'expert');
    expect(args[args.indexOf('--trainings-per-hour') + 1], '6');
    expect(args, containsAll(['--local-only', '--fresh-chat']));
  });

  testWidgets('Training choices save and reload across app recreation', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final tempDirectory = Directory.systemTemp.createTempSync(
      'engel-training-preferences-',
    );
    addTearDown(() async {
      if (tempDirectory.existsSync()) {
        await tempDirectory.delete(recursive: true);
      }
    });
    final preferencesFile = File(
      '${tempDirectory.path}${Platform.pathSeparator}ui_preferences.json',
    );
    final indexFile = writeFreshEightHourCurriculaIndex(tempDirectory);

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: preferencesFile.path,
        trainingCurriculaIndexPathOverride: indexFile.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find
          .byKey(const Key('training-curriculum-tile-math_school'))
          .evaluate()
          .isNotEmpty,
    );
    final mathCurriculum = find.byKey(
      const Key('training-curriculum-tile-math_school'),
    );
    await waitForJsonFile(
      tester,
      preferencesFile,
      trigger: () async {
        await tester.tap(mathCurriculum);
        await tester.pump();
      },
      until: (payload) => payload['training_curriculum_id'] == 'math_school',
    );

    final hoursFinder = find.byKey(const Key('training-hours-slider'));
    final levelFinder = find.byKey(const Key('training-level-slider'));
    final frequencyFinder = find.byKey(const Key('training-frequency-slider'));
    final llmTargetFinder = find.byKey(const Key('training-target-llm'));

    tester.widget<Slider>(hoursFinder).onChanged!(8);
    await tester.pump();
    final saveHours = tester.widget<Slider>(hoursFinder).onChangeEnd!;
    await waitForJsonFile(
      tester,
      preferencesFile,
      trigger: () => saveHours(8),
      until: (payload) => payload['training_hours'] == 8,
    );

    tester.widget<Slider>(levelFinder).onChanged!(3);
    await tester.pump();
    final saveLevel = tester.widget<Slider>(levelFinder).onChangeEnd!;
    await waitForJsonFile(
      tester,
      preferencesFile,
      trigger: () => saveLevel(3),
      until: (payload) => payload['training_level'] == 'fellow',
    );

    tester.widget<Slider>(frequencyFinder).onChanged!(3);
    await tester.pump();
    final saveFrequency = tester.widget<Slider>(frequencyFinder).onChangeEnd!;
    final saved = await waitForJsonFile(
      tester,
      preferencesFile,
      trigger: () => saveFrequency(3),
      until: (payload) => payload['trainings_per_hour'] == 3,
    );
    await tester.ensureVisible(llmTargetFinder);
    final targetSaved = await waitForJsonFile(
      tester,
      preferencesFile,
      trigger: () =>
          tester.widget<CheckboxListTile>(llmTargetFinder).onChanged!(false),
      until: (payload) => payload['train_llm_target'] == false,
    );
    await tester.pump();
    expect(tester.widget<CheckboxListTile>(llmTargetFinder).value, isFalse);
    expect(targetSaved['schema'], 'engel_main_ui_preferences_v3');
    expect(saved['training_hours'], 8);
    expect(saved['training_level'], 'fellow');
    expect(saved['trainings_per_hour'], 3);
    expect(targetSaved['train_slm_target'], isTrue);
    expect(targetSaved['train_llm_target'], isFalse);
    expect(targetSaved['training_curriculum_id'], 'math_school');

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: preferencesFile.path,
        trainingCurriculaIndexPathOverride: indexFile.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () {
        final hours = find.byKey(const Key('training-hours-slider'));
        if (hours.evaluate().isEmpty) return false;
        return tester.widget<Slider>(hours).value == 8;
      },
      reason: 'Saved Training choices were not loaded after app recreation.',
    );

    expect(tester.widget<Slider>(hoursFinder).value, 8);
    expect(tester.widget<Slider>(levelFinder).value, 3);
    expect(tester.widget<Slider>(frequencyFinder).value, 3);
    expect(find.text('Review 8-hour Prompt Training'), findsOneWidget);
    expect(find.text('Fellow'), findsWidgets);
    expect(find.text('3 per hour'), findsOneWidget);
    expect(find.text('SLM roster'), findsWidgets);
    expect(find.textContaining('Eighty new declared problems'), findsOneWidget);
  });

  testWidgets(
    'saved training hours clamp to remaining novel hours without crashing',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1600, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final fixtures = Directory.systemTemp.createTempSync(
        'engel-training-hours-clamp-',
      );
      addTearDown(() {
        try {
          if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
        } catch (_) {}
      });
      File(
        '${fixtures.path}${Platform.pathSeparator}chat.json',
      ).writeAsStringSync('{}');
      final index =
          File(
            '${fixtures.path}${Platform.pathSeparator}curricula_index.json',
          )..writeAsStringSync(
            jsonEncode({
              'active_id': 'chat_communication',
              'curricula': [
                {
                  'id': 'chat_communication',
                  'title': 'Chat Communication',
                  'detail': 'One remaining novel hour.',
                  'template_path':
                      '${fixtures.path}${Platform.pathSeparator}chat.json',
                  'topic_count': 8,
                  'prompt_count': 80,
                  'maximum_hours': 8,
                  'novel_hours_available': 1,
                  'novelty_ready': true,
                  'novelty_fully_ready': false,
                  'novelty_status': 'PARTIAL',
                  'topics': List<String>.generate(8, (index) => 'Hour $index'),
                  'active': true,
                },
              ],
            }),
          );
      final preferencesFile =
          File('${fixtures.path}${Platform.pathSeparator}ui_preferences.json')
            ..writeAsStringSync(
              jsonEncode({
                'schema': 'engel_main_ui_preferences_v3',
                'training_hours': 7,
                'training_curriculum_id': 'chat_communication',
              }),
            );

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          uiPreferencesPath: preferencesFile.path,
          trainingCurriculaIndexPathOverride: index.path,
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'training');
      await pumpUntil(
        tester,
        () => find
            .byKey(const Key('training-hours-slider'))
            .evaluate()
            .isNotEmpty,
      );

      final hoursSlider = tester.widget<Slider>(
        find.byKey(const Key('training-hours-slider')),
      );
      expect(hoursSlider.max, 1);
      expect(hoursSlider.value, 1);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('legacy and invalid Training preferences keep safe defaults', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final tempDirectory = Directory.systemTemp.createTempSync(
      'engel-training-defaults-',
    );
    addTearDown(() async {
      if (tempDirectory.existsSync()) {
        await tempDirectory.delete(recursive: true);
      }
    });
    final preferencesFile = File(
      '${tempDirectory.path}${Platform.pathSeparator}ui_preferences.json',
    );

    preferencesFile.writeAsStringSync(
      jsonEncode({
        'schema': 'engel_main_ui_preferences_v1',
        'background_visibility': 1,
        'simple_navigation': false,
        'interface_text_scale': 1,
      }),
    );
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: preferencesFile.path,
      ),
    );
    await tester.pump();
    await pumpUntil(
      tester,
      () => find.byKey(const Key('section-chat_runtime')).evaluate().isNotEmpty,
      reason: 'The legacy preference file was not loaded.',
    );
    await tapSideSection(tester, 'training');

    Finder hoursFinder = find.byKey(const Key('training-hours-slider'));
    Finder levelFinder = find.byKey(const Key('training-level-slider'));
    Finder frequencyFinder = find.byKey(const Key('training-frequency-slider'));
    expect(tester.widget<Slider>(hoursFinder).value, 1);
    // Ladder raised 2026-08-08: Expert (index 0) is the floor and the safe default.
    expect(tester.widget<Slider>(levelFinder).value, 0);
    expect(tester.widget<Slider>(frequencyFinder).value, 6);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    preferencesFile.writeAsStringSync(
      jsonEncode({
        'schema': 'engel_main_ui_preferences_v2',
        'training_hours': 2.5,
        'training_level': 'master',
        'trainings_per_hour': 11,
        'simple_navigation': false,
      }),
    );
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: preferencesFile.path,
      ),
    );
    await tester.pump();
    await pumpUntil(
      tester,
      () => find.byKey(const Key('section-chat_runtime')).evaluate().isNotEmpty,
      reason: 'The invalid Training preference fixture was not loaded.',
    );
    await tapSideSection(tester, 'training');

    hoursFinder = find.byKey(const Key('training-hours-slider'));
    levelFinder = find.byKey(const Key('training-level-slider'));
    frequencyFinder = find.byKey(const Key('training-frequency-slider'));
    expect(tester.widget<Slider>(hoursFinder).value, 1);
    // Ladder raised 2026-08-08: Expert (index 0) is the floor and the safe default.
    expect(tester.widget<Slider>(levelFinder).value, 0);
    expect(tester.widget<Slider>(frequencyFinder).value, 6);
  });

  testWidgets(
    'Training duration, depth, and trainings per hour are independent',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1600, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      final starter = RecordingTrainingProcessStarter();
      final fixtures = Directory.systemTemp.createTempSync(
        'engel-training-independent-sliders-',
      );
      addTearDown(() {
        if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
      });
      final indexFile = writeFreshEightHourCurriculaIndex(fixtures);
      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          trainingProcessStarter: starter.call,
          uiPreferencesPath: '',
          trainingCurriculaIndexPathOverride: indexFile.path,
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'training');

      final hoursFinder = find.byKey(const Key('training-hours-slider'));
      final levelFinder = find.byKey(const Key('training-level-slider'));
      final frequencyFinder = find.byKey(
        const Key('training-frequency-slider'),
      );
      expect(hoursFinder, findsOneWidget);
      expect(levelFinder, findsOneWidget);
      expect(frequencyFinder, findsOneWidget);

      final hoursSlider = tester.widget<Slider>(hoursFinder);
      expect(hoursSlider.min, 1);
      expect(hoursSlider.max, 8);
      expect(hoursSlider.divisions, 7);

      final levelSlider = tester.widget<Slider>(levelFinder);
      expect(levelSlider.min, 0);
      expect(levelSlider.max, 3);
      expect(levelSlider.divisions, 3);

      final frequencySlider = tester.widget<Slider>(frequencyFinder);
      expect(frequencySlider.min, 1);
      expect(frequencySlider.max, 10);
      expect(frequencySlider.divisions, 9);
      expect(frequencySlider.value, 6);

      levelSlider.onChanged!(3);
      await tester.pump();
      tester.widget<Slider>(frequencyFinder).onChanged!(3);
      await tester.pump();

      expect(tester.widget<Slider>(hoursFinder).value, 1);
      expect(tester.widget<Slider>(levelFinder).value, 3);
      expect(tester.widget<Slider>(frequencyFinder).value, 3);
      expect(find.text('Fellow'), findsWidgets);
      expect(find.text('3 per hour'), findsOneWidget);
      expect(find.text('Review 1-hour Prompt Training'), findsOneWidget);
      expect(
        tester
            .widget<Text>(find.byKey(const Key('training-level-description')))
            .data,
        isNot(contains('per hour')),
      );

      final startFinder = find.byKey(const Key('hour-training-control'));
      await tester.ensureVisible(startFinder);
      await tester.tap(startFinder);
      await tester.pumpAndSettle();

      expect(find.text('Start one-hour training?'), findsOneWidget);
      final dialog = find.byType(AlertDialog);
      expect(
        find.descendant(
          of: dialog,
          matching: find.textContaining('Training level: Fellow'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: dialog,
          matching: find.textContaining('Trainings per hour: 3'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: dialog,
          matching: find.textContaining('Full plan: 3 prompts'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: dialog,
          matching: find.textContaining(
            'Later prompts run about one every 20 minutes',
          ),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: dialog,
          matching: find.textContaining('local-only'),
        ),
        findsOneWidget,
      );

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      tester.widget<Slider>(hoursFinder).onChanged!(8);
      await tester.pump();
      expect(find.text('Review 8-hour Prompt Training'), findsOneWidget);

      await tester.ensureVisible(startFinder);
      await tester.tap(startFinder);
      await tester.pumpAndSettle();

      expect(find.text('Start 8-hour training?'), findsOneWidget);
      final eightHourDialog = find.byType(AlertDialog);
      expect(
        find.descendant(
          of: eightHourDialog,
          matching: find.textContaining('480 minutes'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: eightHourDialog,
          matching: find.textContaining('Trainings per hour: 3'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: eightHourDialog,
          matching: find.textContaining('Full plan: 24 prompts'),
        ),
        findsOneWidget,
      );

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(starter.calls, isEmpty);
    },
  );

  testWidgets('Training plan summary stays visible and updates immediately', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-plan-summary-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final indexFile = writeFreshEightHourCurriculaIndex(fixtures);
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
        trainingCurriculaIndexPathOverride: indexFile.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');

    final summaryFinder = find.byKey(const Key('training-plan-summary'));
    expect(summaryFinder, findsOneWidget);
    expect(
      find.text(
        '6 trainings over 1 hour · Expert depth · '
        'about one every 10 minutes',
      ),
      findsOneWidget,
    );

    tester
        .widget<Slider>(find.byKey(const Key('training-hours-slider')))
        .onChanged!(8);
    await tester.pump();
    tester
        .widget<Slider>(find.byKey(const Key('training-level-slider')))
        .onChanged!(3);
    await tester.pump();
    tester
        .widget<Slider>(find.byKey(const Key('training-frequency-slider')))
        .onChanged!(3);
    await tester.pump();

    expect(summaryFinder, findsOneWidget);
    expect(
      find.text(
        '24 trainings over 8 hours · Fellow depth · '
        'about one every 20 minutes',
      ),
      findsOneWidget,
    );
  });

  testWidgets('Training sliders expose human-readable semantic values', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');

    final hoursFinder = find.byKey(const Key('training-hours-slider'));
    final levelFinder = find.byKey(const Key('training-level-slider'));
    final frequencyFinder = find.byKey(const Key('training-frequency-slider'));
    final hoursSlider = tester.widget<Slider>(hoursFinder);
    final levelSlider = tester.widget<Slider>(levelFinder);
    final frequencySlider = tester.widget<Slider>(frequencyFinder);

    expect(hoursSlider.semanticFormatterCallback, isNotNull);
    expect(hoursSlider.semanticFormatterCallback!(1), '1 hour');
    expect(hoursSlider.semanticFormatterCallback!(8), '8 hours');

    expect(levelSlider.semanticFormatterCallback, isNotNull);
    expect(
      levelSlider.semanticFormatterCallback!(0),
      'Expert. Deep synthesis, tradeoffs, and adversarial verification',
    );
    expect(
      levelSlider.semanticFormatterCallback!(1),
      'Principal. Cross-system design: second-order effects, blast radius, rollback',
    );
    expect(
      levelSlider.semanticFormatterCallback!(3),
      'Fellow. First-principles derivation that leaves a reusable invariant',
    );

    expect(frequencySlider.semanticFormatterCallback, isNotNull);
    expect(
      frequencySlider.semanticFormatterCallback!(1),
      '1 training per hour',
    );
    expect(
      frequencySlider.semanticFormatterCallback!(3),
      '3 trainings per hour',
    );

    final semanticsHandle = tester.ensureSemantics();
    await tester.pump();

    // The raised ladder puts the default (Expert) at the slider minimum, where the
    // decrease semantic action does not exist. Step to Principal so both directions
    // stay asserted below.
    tester.widget<Slider>(levelFinder).onChanged!(1);
    await tester.pump();

    final hoursNode = tester.getSemantics(
      find.byKey(const Key('training-hours-semantics')),
    );
    final hoursData = hoursNode.getSemanticsData();
    expect(hoursData.label, 'Training duration');
    expect(hoursData.value, '1 hour');
    expect(hoursData.increasedValue, '2 hours');
    expect(hoursData.flagsCollection.isSlider, isTrue);
    expect(hoursData.hasAction(ui.SemanticsAction.increase), isTrue);

    final levelNode = tester.getSemantics(
      find.byKey(const Key('training-level-semantics')),
    );
    final levelData = levelNode.getSemanticsData();
    expect(levelData.label, 'Training level');
    expect(
      levelData.value,
      'Principal. Cross-system design: second-order effects, blast radius, rollback',
    );
    expect(
      levelData.increasedValue,
      'Distinguished. Adversarial self-refutation: strongest counter-case, falsification',
    );
    expect(
      levelData.decreasedValue,
      'Expert. Deep synthesis, tradeoffs, and adversarial verification',
    );
    expect(levelData.flagsCollection.isSlider, isTrue);
    expect(levelData.hasAction(ui.SemanticsAction.increase), isTrue);
    expect(levelData.hasAction(ui.SemanticsAction.decrease), isTrue);

    final frequencyNode = tester.getSemantics(
      find.byKey(const Key('training-frequency-semantics')),
    );
    final frequencyData = frequencyNode.getSemanticsData();
    expect(frequencyData.label, 'Trainings per hour');
    expect(frequencyData.value, '6 trainings per hour');
    expect(frequencyData.increasedValue, '7 trainings per hour');
    expect(frequencyData.decreasedValue, '5 trainings per hour');
    expect(frequencyData.flagsCollection.isSlider, isTrue);
    expect(frequencyData.hasAction(ui.SemanticsAction.increase), isTrue);
    expect(frequencyData.hasAction(ui.SemanticsAction.decrease), isTrue);

    tester.semantics.increase(
      find.semantics.byPredicate(
        (node) => node.id == levelNode.id,
        describeMatch: (_) => 'the merged Training level semantics node',
      ),
    );
    await tester.pump();
    expect(
      tester.widget<Text>(find.byKey(const Key('training-level-value'))).data,
      'Distinguished',
    );
    expect(
      tester
          .getSemantics(find.byKey(const Key('training-level-semantics')))
          .getSemanticsData()
          .value,
      'Distinguished. Adversarial self-refutation: strongest counter-case, falsification',
    );
    semanticsHandle.dispose();
  });

  testWidgets('Training status and detail form a semantic live region', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');

    final announcementFinder = find.byKey(
      const Key('training-status-announcement'),
    );
    expect(announcementFinder, findsOneWidget);
    final announcement = tester.widget<Semantics>(announcementFinder);
    expect(announcement.properties.liveRegion, isTrue);
    expect(announcement.container, isTrue);
    expect(
      announcement.properties.label,
      allOf(
        contains('No training is running'),
        contains('Choose a duration, training level, and trainings per hour.'),
      ),
    );
  });

  testWidgets('Training launch passes independent depth and frequency once', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-owned-stop-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final sentinel = File(
      '${fixtures.path}${Platform.pathSeparator}active.json',
    );
    final lifecycle = File(
      '${fixtures.path}${Platform.pathSeparator}lifecycle.json',
    );
    final indexFile = writeFreshEightHourCurriculaIndex(fixtures);

    final starter = RecordingTrainingProcessStarter();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        trainingProcessStarter: starter.call,
        uiPreferencesPath: '',
        trainingActiveSentinelPathOverride: sentinel.path,
        trainingCurriculaIndexPathOverride: indexFile.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');

    tester
        .widget<Slider>(find.byKey(const Key('training-level-slider')))
        .onChanged!(3);
    await tester.pump();
    tester
        .widget<Slider>(find.byKey(const Key('training-frequency-slider')))
        .onChanged!(3);
    await tester.pump();

    final trainingControl = find.byKey(const Key('hour-training-control'));
    await tester.ensureVisible(trainingControl);
    await tester.tap(trainingControl);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-hour-training')));
    await tester.pumpAndSettle();

    expect(starter.calls, hasLength(1));
    final call = starter.calls.single;
    expect(call.executable, 'powershell.exe');
    expect(
      call.arguments.where((argument) => argument == '-Hours'),
      hasLength(1),
    );
    expect(call.arguments[call.arguments.indexOf('-Hours') + 1], '1');
    expect(
      call.arguments.where((argument) => argument == '-TrainingLevel'),
      hasLength(1),
    );
    expect(
      call.arguments[call.arguments.indexOf('-TrainingLevel') + 1],
      'fellow',
    );
    expect(
      call.arguments.where((argument) => argument == '-TrainingTargets'),
      hasLength(1),
    );
    expect(
      call.arguments[call.arguments.indexOf('-TrainingTargets') + 1],
      'slm,llm',
    );
    expect(
      call.arguments.where((argument) => argument == '-TrainingsPerHour'),
      hasLength(1),
    );
    expect(
      call.arguments[call.arguments.indexOf('-TrainingsPerHour') + 1],
      '3',
    );
    expect(
      call.arguments.where((argument) => argument == '-StartIndex'),
      hasLength(1),
    );
    expect(call.arguments[call.arguments.indexOf('-StartIndex') + 1], '1');
    expect(
      call.arguments.where((argument) => argument == '-TemplateCycle'),
      hasLength(1),
    );
    expect(call.arguments[call.arguments.indexOf('-TemplateCycle') + 1], '1');
    expect(find.text('Stop training'), findsOneWidget);

    lifecycle.writeAsStringSync(
      jsonEncode({'status': 'RUNNING', 'events': <Object?>[]}),
    );
    sentinel.writeAsStringSync(
      jsonEncode({
        'schema': 'engel_ui_local_only_training_active_v2',
        'status': 'RUNNING',
        'run_id': 'owned-stop-run',
        'launcher_pid': 4242,
        'runner_pid': 4243,
        'log': '${fixtures.path}${Platform.pathSeparator}owned.log',
        'lifecycle_receipt': lifecycle.path,
        'expires_at_epoch': DateTime.now().millisecondsSinceEpoch / 1000 + 3600,
      }),
    );

    await tester.ensureVisible(trainingControl);
    await tester.tap(trainingControl);
    await pumpAction(tester);

    expect(starter.calls, hasLength(1));
    expect(starter.stopTreeCalls, 1);
    final stoppedSentinel = jsonDecode(sentinel.readAsStringSync());
    final stoppedLifecycle = jsonDecode(lifecycle.readAsStringSync());
    expect(stoppedSentinel['status'], 'STOPPED');
    expect(stoppedSentinel['stopped_by_ui'], isTrue);
    expect(stoppedSentinel['runner_pid'], 4243);
    expect(stoppedLifecycle['status'], 'STOPPED');
    expect(
      (stoppedLifecycle['events'] as List).last['event'],
      'ui_stop_confirmed',
    );

    starter.exitCode.complete(0);
    await pumpAction(tester);
  });

  testWidgets(
    'Partial curriculum preview and launch share the exact rotated topic plan',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1600, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final fixtures = Directory.systemTemp.createTempSync(
        'engel-training-topic-consent-',
      );
      addTearDown(() {
        if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
      });
      final template = File(
        '${fixtures.path}${Platform.pathSeparator}partial_template.json',
      )..writeAsStringSync('{}');
      final index =
          File(
            '${fixtures.path}${Platform.pathSeparator}curricula_index.json',
          )..writeAsStringSync(
            jsonEncode({
              'active_id': 'construction',
              'curricula': [
                {
                  'id': 'construction',
                  'title': 'Construction Coordination',
                  'detail': 'Three consecutive fresh hours wrap after cycle 8.',
                  'template_path': template.path,
                  'topic_count': 8,
                  'prompt_count': 80,
                  'maximum_hours': 8,
                  'novel_hours_available': 3,
                  'novel_complete_cycle_count': 3,
                  'novel_hours_start_cycle': 7,
                  'novelty_ready': true,
                  'novelty_fully_ready': false,
                  'novelty_status': 'PARTIAL',
                  'topics': List<String>.generate(
                    8,
                    (offset) => 'Cycle ${offset + 1}',
                  ),
                  'active': true,
                },
              ],
            }),
          );
      final starter = RecordingTrainingProcessStarter();
      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          trainingProcessStarter: starter.call,
          uiPreferencesPath: '',
          trainingCurriculaIndexPathOverride: index.path,
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'training');
      await pumpUntil(
        tester,
        () => find
            .byKey(const Key('training-curriculum-tile-construction'))
            .evaluate()
            .isNotEmpty,
      );
      tester
          .widget<Slider>(find.byKey(const Key('training-hours-slider')))
          .onChanged!(3);
      await tester.pump();

      final control = find.byKey(const Key('hour-training-control'));
      await tester.ensureVisible(control);
      await tester.tap(control);
      await tester.pumpAndSettle();

      expect(find.textContaining('1. Cycle 7'), findsOneWidget);
      expect(find.textContaining('2. Cycle 8'), findsOneWidget);
      expect(find.textContaining('3. Cycle 1'), findsOneWidget);
      expect(find.textContaining('Cycle 2'), findsNothing);
      await tester.tap(find.byKey(const Key('confirm-hour-training')));
      await tester.pumpAndSettle();

      expect(starter.calls, hasLength(1));
      final call = starter.calls.single;
      expect(call.arguments[call.arguments.indexOf('-Hours') + 1], '3');
      expect(call.arguments[call.arguments.indexOf('-TemplateCycle') + 1], '7');
      expect(
        call.arguments[call.arguments.indexOf('-Template') + 1],
        template.path,
      );
      starter.exitCode.complete(0);
      await pumpAction(tester);
    },
  );

  testWidgets('Malformed partial start cycle fails closed before launch', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-invalid-topic-cycle-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final template = File(
      '${fixtures.path}${Platform.pathSeparator}partial_template.json',
    )..writeAsStringSync('{}');
    final index =
        File('${fixtures.path}${Platform.pathSeparator}curricula_index.json')
          ..writeAsStringSync(
            jsonEncode({
              'active_id': 'construction',
              'curricula': [
                {
                  'id': 'construction',
                  'title': 'Construction Coordination',
                  'template_path': template.path,
                  'topic_count': 8,
                  'prompt_count': 80,
                  'maximum_hours': 8,
                  'novel_hours_available': 3,
                  'novel_complete_cycle_count': 3,
                  'novel_hours_start_cycle': 0,
                  'novelty_ready': true,
                  'novelty_fully_ready': false,
                  'topics': List<String>.generate(
                    8,
                    (offset) => 'Cycle ${offset + 1}',
                  ),
                },
              ],
            }),
          );
    final starter = RecordingTrainingProcessStarter();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        trainingProcessStarter: starter.call,
        uiPreferencesPath: '',
        trainingCurriculaIndexPathOverride: index.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find
          .byKey(const Key('training-curriculum-tile-construction'))
          .evaluate()
          .isNotEmpty,
    );

    final control = find.byKey(const Key('hour-training-control'));
    await tester.ensureVisible(control);
    await tester.tap(control);
    await pumpAction(tester);

    expect(find.byKey(const Key('confirm-hour-training')), findsNothing);
    expect(
      find.textContaining(
        'does not provide a valid fresh-material start cycle',
      ),
      findsWidgets,
    );
    expect(starter.calls, isEmpty);
  });

  testWidgets('Failed training offers recovery without automatic restart', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final starter = RecordingTrainingProcessStarter();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        trainingProcessStarter: starter.call,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');

    final trainingControl = find.byKey(const Key('hour-training-control'));
    await tester.ensureVisible(trainingControl);
    await tester.tap(trainingControl);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-hour-training')));
    await tester.pumpAndSettle();
    expect(starter.calls, hasLength(1));

    starter.exitCode.complete(9);
    await pumpAction(tester);

    expect(find.text('Last training failed'), findsOneWidget);
    expect(find.byKey(const Key('training-recovery-state')), findsOneWidget);
    expect(find.byKey(const Key('training-recovery-open-log')), findsOneWidget);
    final tryAgain = find.byKey(const Key('training-recovery-try-again'));
    expect(tryAgain, findsOneWidget);

    await tester.ensureVisible(tryAgain);
    await tester.tap(tryAgain);
    await tester.pumpAndSettle();

    expect(find.text('Start one-hour training?'), findsOneWidget);
    expect(starter.calls, hasLength(1));
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(starter.calls, hasLength(1));
  });

  testWidgets('Failed paced training skips write-ahead-reserved prompts', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-resume-receipt-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final sentinel = File(
      '${fixtures.path}${Platform.pathSeparator}active.json',
    );
    final session = File(
      '${fixtures.path}${Platform.pathSeparator}session.json',
    );
    // Keep this recovery contract independent of whatever material the
    // developer checkout has consumed. The production index is novelty-aware
    // and may legitimately have fewer than five fresh hours remaining; this
    // fixture specifically exercises the write-ahead resume math for a valid
    // five-hour plan.
    final indexFile = writeFreshEightHourCurriculaIndex(fixtures);
    final reservations = Directory(
      '${fixtures.path}${Platform.pathSeparator}prompt_use_reservations',
    )..createSync();
    Map<String, dynamic> writeReservation(int position, String digit) {
      final reservationId = List.filled(64, digit).join();
      final path = File(
        '${reservations.path}${Platform.pathSeparator}'
        'ENGEL_PROMPT_USE_RESERVATION_$reservationId.json',
      );
      final payload = <String, dynamic>{
        'schema': 'engel_prompt_use_reservation_v1',
        'reservation_id': reservationId,
        'run_id': 'resume-run-1',
        'prompt_position': position,
        'base_prompt': 'Reserved prompt $position',
        'base_prompt_sha256': List.filled(64, digit).join(),
        'base_prompt_hash_canonicalization':
            'unicode_nfkc_casefold_collapsed_whitespace_v1',
        'history_snapshot_sha256': List.filled(64, 'a').join(),
        'history_pack_snapshot_sha256': List.filled(64, 'b').join(),
        'history_reservation_snapshot_sha256': List.filled(64, 'c').join(),
        'planned_prompt_set_sha256': List.filled(64, 'd').join(),
        'created_at_utc': '2026-08-09T12:00:00Z',
        'prompt_run_claim': {
          'run_id': 'resume-run-1',
          'owner_pid': 4243,
          'claim_path': '${fixtures.path}\\prompt_run.lock',
        },
      };
      path.writeAsStringSync(jsonEncode(payload));
      return {...payload, 'path': path.path, 'immutable': true};
    }

    final sessionReservations = <int, Map<String, dynamic>>{
      31: writeReservation(31, '1'),
      32: writeReservation(32, '2'),
    };
    // Exact crash window: the write-ahead reservation was published, but the
    // process died before prompt 33 could be appended to prompt_results.
    writeReservation(33, '3');
    sentinel.writeAsStringSync(
      jsonEncode({
        'status': 'FAILED',
        'expires_at_epoch': 0,
        'requested_prompts': 50,
        'log': '',
      }),
    );
    final promptResults = List<Map<String, dynamic>>.generate(32, (offset) {
      final index = offset + 1;
      final result = <String, dynamic>{
        'prompt_index': index,
        'status': const {1, 21, 31, 32}.contains(index) ? 'FAIL' : 'DONE',
      };
      if (const {31, 32}.contains(index)) {
        result['prompt_use_reservation'] = sessionReservations[index];
      }
      return result;
    });
    session.writeAsStringSync(
      jsonEncode({
        'run_id': 'resume-run-1',
        'status': 'FAIL',
        'start_index': 1,
        'scheduled_hours': 5,
        'training_level': 'expert',
        'training_targets': 'slm,llm',
        'trainings_per_hour': 10,
        'template_path':
            '$trainingCanonicalRoot\\templates\\ENGEL_TEMPLATE_CAPABILITIES.json',
        'template_cycle': 1,
        'prompt_results': promptResults,
        'summary': {
          'prompts_completed': 28,
          'prompts_requested': 50,
          'training_pack_rows': 30,
          'training_pack_admitted': 15,
        },
        'blockers': [
          'stopped after 2 consecutive delivery failures (chat pipeline not completing)',
        ],
      }),
    );
    final starter = RecordingTrainingProcessStarter();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        trainingProcessStarter: starter.call,
        uiPreferencesPath: '',
        trainingActiveSentinelPathOverride: sentinel.path,
        trainingSessionReceiptPathOverride: session.path,
        trainingPromptReservationsPathOverride: reservations.path,
        trainingCurriculaIndexPathOverride: indexFile.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    final refresh = tester
        .widget<OutlinedButton>(
          find.byKey(const Key('training-refresh-status')),
        )
        .onPressed;
    expect(refresh, isNotNull);
    refresh!();
    await pumpUntil(
      tester,
      () => find
          .byKey(const Key('training-recovery-resume'))
          .evaluate()
          .isNotEmpty,
      reason: 'The safe continuation action did not appear.',
    );

    expect(find.textContaining('28 of 50 complete'), findsOneWidget);
    expect(find.text('Resume 17 prompts'), findsOneWidget);
    expect(
      find.textContaining('prompt 34, the first unused prompt'),
      findsWidgets,
    );
    final resume = find.byKey(const Key('training-recovery-resume'));
    await tester.ensureVisible(resume);
    await tester.tap(resume);
    await tester.pumpAndSettle();

    expect(find.text('Resume 5-hour training?'), findsOneWidget);
    expect(find.textContaining('Resume point: prompt 34'), findsOneWidget);
    expect(find.textContaining('Prompts remaining: 17'), findsOneWidget);
    expect(
      find.textContaining(
        'keep this PC awake and unlocked for up to 102 minutes',
      ),
      findsOneWidget,
    );
    expect(
      find.textContaining('prior receipts and pack stay preserved'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('confirm-hour-training')));
    await tester.pumpAndSettle();

    expect(starter.calls, hasLength(1));
    final call = starter.calls.single;
    expect(call.arguments[call.arguments.indexOf('-Hours') + 1], '5');
    expect(
      call.arguments[call.arguments.indexOf('-TrainingLevel') + 1],
      'expert',
    );
    expect(
      call.arguments[call.arguments.indexOf('-TrainingsPerHour') + 1],
      '10',
    );
    expect(call.arguments[call.arguments.indexOf('-StartIndex') + 1], '34');
    expect(call.arguments[call.arguments.indexOf('-TemplateCycle') + 1], '1');
    starter.exitCode.complete(0);
    await pumpAction(tester);
  });

  testWidgets('Fully reserved failed plan requires new material', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = Directory.systemTemp.createTempSync(
      'engel-training-reserved-plan-closed-',
    );
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final sentinel =
        File('${fixtures.path}${Platform.pathSeparator}active.json')
          ..writeAsStringSync(
            jsonEncode({
              'status': 'FAILED',
              'expires_at_epoch': 0,
              'requested_prompts': 10,
              'log': '',
            }),
          );
    final session = File(
      '${fixtures.path}${Platform.pathSeparator}session.json',
    );
    final reservations = Directory(
      '${fixtures.path}${Platform.pathSeparator}prompt_use_reservations',
    )..createSync();
    Map<String, dynamic> writeReservation(int position, String digit) {
      final reservationId = List.filled(64, digit).join();
      final path = File(
        '${reservations.path}${Platform.pathSeparator}'
        'ENGEL_PROMPT_USE_RESERVATION_$reservationId.json',
      );
      final payload = <String, dynamic>{
        'schema': 'engel_prompt_use_reservation_v1',
        'reservation_id': reservationId,
        'run_id': 'consumed-run-1',
        'prompt_position': position,
        'base_prompt': 'Reserved prompt $position',
        'base_prompt_sha256': List.filled(64, digit).join(),
        'base_prompt_hash_canonicalization':
            'unicode_nfkc_casefold_collapsed_whitespace_v1',
        'history_snapshot_sha256': List.filled(64, 'a').join(),
        'history_pack_snapshot_sha256': List.filled(64, 'b').join(),
        'history_reservation_snapshot_sha256': List.filled(64, 'c').join(),
        'planned_prompt_set_sha256': List.filled(64, 'd').join(),
        'created_at_utc': '2026-08-09T12:00:00Z',
        'prompt_run_claim': {
          'run_id': 'consumed-run-1',
          'owner_pid': 4243,
          'claim_path': '${fixtures.path}\\prompt_run.lock',
        },
      };
      path.writeAsStringSync(jsonEncode(payload));
      return {...payload, 'path': path.path, 'immutable': true};
    }

    final sessionReservations = <int, Map<String, dynamic>>{
      9: writeReservation(9, '9'),
      10: writeReservation(10, 'e'),
    };
    final promptResults = List<Map<String, dynamic>>.generate(10, (offset) {
      final index = offset + 1;
      final result = <String, dynamic>{
        'prompt_index': index,
        'status': index >= 9 ? 'FAIL' : 'DONE',
      };
      if (index >= 9) {
        result['prompt_use_reservation'] = sessionReservations[index];
      }
      return result;
    });
    session.writeAsStringSync(
      jsonEncode({
        'run_id': 'consumed-run-1',
        'status': 'FAIL',
        'start_index': 1,
        'scheduled_hours': 1,
        'training_level': 'expert',
        'training_targets': 'slm,llm',
        'trainings_per_hour': 10,
        'template_path':
            '$trainingCanonicalRoot\\templates\\ENGEL_TEMPLATE_CAPABILITIES.json',
        'prompt_results': promptResults,
        'summary': {
          'prompts_completed': 8,
          'prompts_requested': 10,
          'training_pack_rows': 8,
          'training_pack_admitted': 8,
        },
        'blockers': [
          'stopped after 2 consecutive delivery failures (chat pipeline not completing)',
        ],
      }),
    );

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
        trainingActiveSentinelPathOverride: sentinel.path,
        trainingSessionReceiptPathOverride: session.path,
        trainingPromptReservationsPathOverride: reservations.path,
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    tester
        .widget<OutlinedButton>(
          find.byKey(const Key('training-refresh-status')),
        )
        .onPressed!();
    await pumpUntil(
      tester,
      () => find.text('Prepare new material').evaluate().isNotEmpty,
      reason: 'Consumed plan did not require fresh material.',
    );

    expect(
      find.textContaining('consumed every remaining prompt'),
      findsWidgets,
    );
    expect(find.byKey(const Key('training-recovery-resume')), findsNothing);
    expect(find.byKey(const Key('training-recovery-try-again')), findsNothing);
    expect(
      find.byKey(const Key('training-recovery-prepare-new')),
      findsOneWidget,
    );
  });

  testWidgets('Training model target selector supports SLM, LLM, and both', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');

    final slm = find.byKey(const Key('training-target-slm'));
    final llm = find.byKey(const Key('training-target-llm'));
    expect(tester.widget<CheckboxListTile>(slm).value, isTrue);
    expect(tester.widget<CheckboxListTile>(llm).value, isTrue);
    expect(find.text('SLM roster + local LLM adapter'), findsWidgets);

    tester.widget<CheckboxListTile>(llm).onChanged!(false);
    await tester.pump();
    expect(tester.widget<CheckboxListTile>(slm).value, isTrue);
    expect(tester.widget<CheckboxListTile>(llm).value, isFalse);

    // The window must not permit a plan with no actual trainer behind it.
    tester.widget<CheckboxListTile>(slm).onChanged!(false);
    await tester.pump();
    expect(tester.widget<CheckboxListTile>(slm).value, isTrue);
    expect(
      find.text('Keep at least one trainable model selected.'),
      findsOneWidget,
    );

    tester.widget<CheckboxListTile>(llm).onChanged!(true);
    await tester.pump();
    tester.widget<CheckboxListTile>(slm).onChanged!(false);
    await tester.pump();
    expect(tester.widget<CheckboxListTile>(slm).value, isFalse);
    expect(tester.widget<CheckboxListTile>(llm).value, isTrue);
    expect(find.text('Local LLM adapter'), findsWidgets);
  });

  testWidgets(
    'Training targets and model actions remain usable at 200 percent text',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 760));
      tester.platformDispatcher.textScaleFactorTestValue = 2.0;
      addTearDown(() {
        tester.binding.setSurfaceSize(null);
        tester.platformDispatcher.textScaleFactorTestValue = 1.0;
      });

      await tester.pumpWidget(
        const EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          uiPreferencesPath: '',
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'training');

      for (final key in const [
        Key('training-model-targets'),
        Key('training-target-slm'),
        Key('training-target-llm'),
        Key('hour-training-control'),
        Key('training-apply-models'),
        Key('model-training-run-cycle'),
      ]) {
        final finder = find.byKey(key);
        expect(finder, findsOneWidget);
        await tester.ensureVisible(finder);
        await tester.pump();
        expect(tester.takeException(), isNull, reason: '$key overflowed');
      }
    },
  );

  testWidgets('Model Training panel is honest before any cycle has run', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = createModelTrainingFixtureDirectory();
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final separator = Platform.pathSeparator;

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
        realTrainingCycleScriptPath:
            '${fixtures.path}${separator}absent_orchestrator.py',
        realTrainingCycleReceiptPath:
            '${fixtures.path}${separator}absent_cycle.json',
        promptTrainingPackReceiptPath:
            '${fixtures.path}${separator}absent_pack.json',
        slmRosterMirrorPath: '${fixtures.path}${separator}absent_roster.json',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find.text('Receipts read just now').evaluate().isNotEmpty,
      reason: 'The model-training receipts were never read from disk.',
    );

    expect(find.byKey(const Key('model-training-panel')), findsOneWidget);
    expect(find.text('Model Training'), findsOneWidget);
    expect(find.byKey(const Key('model-training-empty')), findsOneWidget);
    expect(
      find.textContaining(
        'No training cycle has run yet — prompt training practices, this is '
        'what turns it into model training.',
      ),
      findsOneWidget,
    );
    // A missing receipt must never be rendered as a confident zero.
    expect(find.text('No pack receipt yet'), findsOneWidget);
    expect(find.text('No cycle receipt yet'), findsOneWidget);
    expect(find.text('SLM roster · no training result yet'), findsOneWidget);
    expect(find.text('2 collecting · 4 not trained'), findsOneWidget);
    for (final task in const [
      'intent_router',
      'route_governor',
      'style_checks',
      'reply_grader',
      'train_admit',
      'failure_triage',
    ]) {
      expect(
        find.byKey(Key('model-training-slm-$task')),
        findsOneWidget,
        reason: '$task disappeared from the canonical SLM roster',
      );
    }
    expect(
      find.text(
        'Route Governor · collecting real data · not trained in this run',
      ),
      findsOneWidget,
    );
    expect(
      find.text(
        'Failure Triage · collecting real data · not trained in this run',
      ),
      findsOneWidget,
    );
    expect(
      find.text('No manual fallback or canary commands recorded yet.'),
      findsNothing,
    );
    expect(find.byKey(const Key('model-training-run-cycle')), findsOneWidget);
    expect(find.byKey(const Key('model-training-refresh')), findsOneWidget);
    expect(find.byKey(const Key('model-training-cycle-status')), findsNothing);
    expect(find.byKey(const Key('model-training-cycle-blocker')), findsNothing);
    // The LLM lane is available, but raw operator commands stay out of the
    // primary workflow until the advanced disclosure is opened.
    expect(
      find.text('Local LLM approval and advanced commands'),
      findsOneWidget,
    );
    await tester.ensureVisible(
      find.byKey(const Key('model-training-advanced-commands')),
    );
    await tester.tap(find.byKey(const Key('model-training-advanced-commands')));
    await tester.pumpAndSettle();
    expect(
      find.text('No manual fallback or canary commands recorded yet.'),
      findsOneWidget,
    );
    expect(find.text('Run LoRA training'), findsNothing);
    expect(find.text('Start LoRA'), findsNothing);
  });

  testWidgets('Model Training panel reports the numbers the cycle recorded', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = createModelTrainingFixtureDirectory();
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final separator = Platform.pathSeparator;
    final nowUtc = DateTime.now().toUtc().toIso8601String();

    final cycleFile = File('${fixtures.path}${separator}cycle.json')
      ..writeAsStringSync(
        jsonEncode({
          'schema': 'engel_real_training_cycle_v1',
          'run_id': 'cycle-fixture-1',
          'started_at_utc': nowUtc,
          'finished_at_utc': nowUtc,
          'status': 'PARTIAL',
          'dry_run': false,
          'targets': ['slm', 'llm'],
          'steps': [
            {
              'step': 'push_packs',
              'ok': true,
              'detail': '2 packs',
              'seconds': 4,
            },
            {
              'step': 'build_dataset',
              'ok': true,
              'detail': 'built',
              'seconds': 61,
            },
            {
              'step': 'train_slm',
              'ok': false,
              'detail': 'one below gate',
              'seconds': 402,
            },
          ],
          'packs': {'files': 2, 'rows': 30, 'admitted': 22, 'pushed': 2},
          'dataset': {
            'built_at_utc': nowUtc,
            'train': 1204,
            'val': 134,
            'prompt_training_rows': 22,
            'dataset_dir': '/opt/engel/datasets/engel_sft',
          },
          'slm': {
            'tasks': {
              'intent_router': {
                'ok': true,
                'macro_f1': 0.918,
                'baseline': 0.914,
                'lift': 0.069,
                'rows': 4095,
                'status': 'trained and met the gate',
              },
              'reply_grader': {
                'ok': false,
                'macro_f1': 0.714,
                'baseline': 0.748,
                'lift': 0.023,
                'rows': 2383,
                'status': 'trained but BELOW the gate',
              },
              'train_admit': {
                'ok': false,
                'macro_f1': null,
                'baseline': null,
                'lift': null,
                'rows': null,
                'class_counts': {'admit': 15, 'reject': 5},
                'min_per_class': 40,
                'status':
                    'not enough classes with sufficient examples to train',
              },
            },
            'mirrored': [
              '/opt/engel/models-active/slm/engel_slm_intent_router.joblib',
            ],
          },
          'llm': {
            'ok': true,
            'new_adapter_trained': true,
            'new_adapter_path':
                '/opt/engel/llm_training/proof_runs/demo/out/adapter',
            'validation_loss_delta': -0.125,
            'auto_deployed': false,
            'preflight': {'ok': true},
          },
          'lora_next_steps': [
            'Stage the aligned dataset on CT246 and wait for the approval phrase',
          ],
          'blockers': ['reply_grader stayed below the macro-F1 gate'],
        }),
      );
    File('${fixtures.path}${separator}pack.json').writeAsStringSync(
      jsonEncode({
        'schema': 'engel_prompt_training_pack_v1',
        'run_id': 'pack-fixture-1',
        'created_at_utc': nowUtc,
        'pack_path':
            '${fixtures.path}${separator}ENGEL_PROMPT_TRAINING_PACK_pack-fixture-1.jsonl',
        'session_receipt': '${fixtures.path}${separator}session.json',
        'discipline': 'communication',
        'curriculum_template': 'ENGEL_TEMPLATE_CHAT_COMMUNICATION.json',
        'training_level': 'medium',
        'rows': 30,
        'admitted': 22,
        'rejected': 8,
        'by_discipline': {'communication': 30},
        'by_status': {'DONE': 30},
        'ct_pack_dir': '/opt/engel/memory/training/packs',
      }),
    );
    File(
      '${fixtures.path}${separator}ENGEL_PROMPT_TRAINING_PACK_pack-fixture-1.jsonl',
    ).writeAsStringSync(
      [
        jsonEncode({'status': 'DONE', 'admit': true}),
        jsonEncode({'status': 'DONE', 'admit': true}),
        jsonEncode({'status': 'DONE', 'admit': false}),
        jsonEncode({'status': 'FAILED', 'admit': false}),
      ].join('\n'),
    );

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
        realTrainingCycleScriptPath:
            '${fixtures.path}${separator}absent_orchestrator.py',
        realTrainingCycleReceiptPath: cycleFile.path,
        promptTrainingPackReceiptPath: '${fixtures.path}${separator}pack.json',
        slmRosterMirrorPath: '${fixtures.path}${separator}absent_roster.json',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find.text('Receipts read just now').evaluate().isNotEmpty,
      reason: 'The model-training receipts were never read from disk.',
    );

    expect(find.byKey(const Key('model-training-empty')), findsNothing);
    expect(
      find.text('Latest model results: PARTIAL · cycle finished just now'),
      findsOneWidget,
    );
    expect(
      find.text('First blocker: reply_grader stayed below the macro-F1 gate'),
      findsOneWidget,
    );
    expect(
      find.text('Last session: 30 answers captured, 22 admitted for training'),
      findsOneWidget,
    );
    expect(
      find.text('3 completed answers · 2 admitted / 1 rejected · 1 pack files'),
      findsOneWidget,
    );
    expect(
      find.textContaining(
        'Training Admission still needs 38 admitted and 39 rejected examples',
      ),
      findsOneWidget,
    );
    expect(
      find.text('1204 train · 134 validation · 22 prompt-training · just now'),
      findsOneWidget,
    );
    expect(find.text('SLM roster · latest cycle'), findsOneWidget);
    expect(
      find.text('1 ready · 2 need data · 2 collecting · 1 not trained'),
      findsOneWidget,
    );
    expect(find.text('SLM roster + Local LLM adapter'), findsOneWidget);
    expect(
      find.text('Selected now · trained and evaluated · not deployed'),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('model-training-llm-adapter-path')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('model-training-slm-intent_router')),
      findsOneWidget,
    );
    // The lift, not the raw baseline, sits next to macro-F1: the baseline is a
    // majority-class accuracy, so printing it beside an F1 made a head that beat
    // its baseline read as worse than guessing.
    expect(
      find.text(
        'Intent Router · met the gate · macro-F1 0.918 · +0.069 over baseline · '
        '4095 rows',
      ),
      findsOneWidget,
    );
    expect(
      find.text(
        'Reply Grader · below the gate · macro-F1 0.714 · +0.023 over baseline · '
        '2383 rows',
      ),
      findsOneWidget,
    );
    expect(
      find.text(
        'Training Admission · 15 admit / 5 reject · needs 40 of each · no score yet',
      ),
      findsOneWidget,
    );
    expect(
      find.text(
        'Next: review at least 60 more answers — 25 admitted and 35 rejected.',
      ),
      findsOneWidget,
    );
    await tester.ensureVisible(
      find.byKey(const Key('model-training-advanced-commands')),
    );
    await tester.tap(find.byKey(const Key('model-training-advanced-commands')));
    await tester.pumpAndSettle();
    expect(
      find.text(
        '- Stage the aligned dataset on CT246 and wait for the approval phrase',
      ),
      findsOneWidget,
    );
  });

  testWidgets('Model Training falls back to the roster mirror with no cycle', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = createModelTrainingFixtureDirectory();
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final separator = Platform.pathSeparator;

    File('${fixtures.path}${separator}roster.json').writeAsStringSync(
      jsonEncode({
        'schema': 'engel_slm_training_report_v1',
        'generated_at_utc': DateTime.now().toUtc().toIso8601String(),
        'root': '/opt/engel',
        'trained_ok': ['intent_router'],
        'below_gate': ['reply_grader'],
        'results': [
          {
            'task': 'intent_router',
            'ok': true,
            'status': 'trained and met the gate',
            'train_rows': 3071,
            'metrics': {
              'macro_f1': 0.9179,
              'majority_baseline_accuracy': 0.9141,
            },
          },
          {
            'task': 'reply_grader',
            'ok': false,
            'status': 'trained but BELOW the gate',
            'train_rows': 1787,
            'metrics': {
              'macro_f1': 0.714,
              'majority_baseline_accuracy': 0.7483,
            },
          },
        ],
      }),
    );

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
        realTrainingCycleScriptPath:
            '${fixtures.path}${separator}absent_orchestrator.py',
        realTrainingCycleReceiptPath:
            '${fixtures.path}${separator}absent_cycle.json',
        promptTrainingPackReceiptPath:
            '${fixtures.path}${separator}absent_pack.json',
        slmRosterMirrorPath: '${fixtures.path}${separator}roster.json',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find.text('Receipts read just now').evaluate().isNotEmpty,
      reason: 'The model-training receipts were never read from disk.',
    );

    // No cycle has run, so the empty state stays up even though the older ROG
    // mirror can still say what the roster looked like last time.
    expect(find.byKey(const Key('model-training-empty')), findsOneWidget);
    expect(find.text('SLM roster · last local receipt'), findsOneWidget);
    expect(
      find.text('1 ready · 1 needs data · 2 collecting · 2 not trained'),
      findsOneWidget,
    );
    expect(
      find.text(
        'Intent Router · met the gate · macro-F1 0.918 · baseline 0.914 · '
        '3071 rows',
      ),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('model-training-slm-reply_grader')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('model-training-slm-route_governor')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('model-training-slm-failure_triage')),
      findsOneWidget,
    );
  });

  testWidgets(
    'Model Training reconciles an older PASS receipt with below-gate evidence',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1600, 1200));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final fixtures = createModelTrainingFixtureDirectory();
      addTearDown(() {
        if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
      });
      final separator = Platform.pathSeparator;
      final nowUtc = DateTime.now().toUtc().toIso8601String();

      final cycleFile = File('${fixtures.path}${separator}cycle.json')
        ..writeAsStringSync(
          jsonEncode({
            'schema': 'engel_real_training_cycle_v1',
            'run_id': 'legacy-pass-with-below-gate-head',
            'started_at_utc': nowUtc,
            'finished_at_utc': nowUtc,
            'status': 'PASS',
            'dry_run': false,
            'dataset': {
              'built_at_utc': nowUtc,
              'train': 1463,
              'val': 33,
              'prompt_training_rows': 15,
            },
            'slm': {
              'tasks': {
                'train_admit': {
                  'ok': false,
                  'macro_f1': null,
                  'status':
                      'not enough classes with sufficient examples to train',
                },
              },
            },
            'blockers': <String>[],
          }),
        );
      final mirrorFile = File('${fixtures.path}${separator}roster.json')
        ..writeAsStringSync(
          jsonEncode({
            'schema': 'engel_slm_training_report_v1',
            'generated_at_utc': nowUtc,
            'trained_ok': <String>[],
            'below_gate': ['train_admit'],
            'results': [
              {
                'task': 'train_admit',
                'ok': false,
                'status':
                    'not enough classes with sufficient examples to train',
                'class_counts': {'admit': 15, 'reject': 5},
                'min_per_class': 40,
              },
            ],
          }),
        );

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          uiPreferencesPath: '',
          realTrainingCycleScriptPath:
              '${fixtures.path}${separator}absent_orchestrator.py',
          realTrainingCycleReceiptPath: cycleFile.path,
          promptTrainingPackReceiptPath:
              '${fixtures.path}${separator}absent_pack.json',
          slmRosterMirrorPath: mirrorFile.path,
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'training');
      await pumpUntil(
        tester,
        () => find.text('Receipts read just now').evaluate().isNotEmpty,
        reason: 'The model-training receipts were never read from disk.',
      );

      expect(
        find.text('Latest model results: PARTIAL · cycle finished just now'),
        findsOneWidget,
      );
      expect(
        find.text(
          'The older receipt says PASS, but Training Admission needs more evidence.',
        ),
        findsOneWidget,
      );
      expect(find.text('SLM roster · older receipt format'), findsOneWidget);
      expect(find.text('SLM roster · latest cycle'), findsOneWidget);
      expect(
        find.text('1 needs data · 2 collecting · 3 not trained'),
        findsOneWidget,
      );
      expect(
        find.text(
          'Training Admission · 15 admit / 5 reject · needs 40 of each · no score yet',
        ),
        findsOneWidget,
      );
      expect(
        find.text(
          'Next: review at least 60 more answers — 25 admitted and 35 rejected.',
        ),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('model-training-cycle-blocker')),
        findsNothing,
      );
    },
  );

  testWidgets('Model Training run-cycle button runs the real orchestrator', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = createModelTrainingFixtureDirectory();
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final separator = Platform.pathSeparator;
    final scriptFile =
        File('${fixtures.path}${separator}run_engel_real_training_cycle.py')
          ..writeAsStringSync(
            '"""Stand-in for the real training-cycle orchestrator."""\n',
          );
    writeModelTrainingRuntimeContract(fixtures);
    final cycleFile = File('${fixtures.path}${separator}cycle.json');
    final starter = RecordingTrainingProcessStarter();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        trainingProcessStarter: starter.call,
        uiPreferencesPath: '',
        realTrainingCycleScriptPath: scriptFile.path,
        realTrainingCycleReceiptPath: cycleFile.path,
        promptTrainingPackReceiptPath:
            '${fixtures.path}${separator}absent_pack.json',
        slmRosterMirrorPath: '${fixtures.path}${separator}absent_roster.json',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find.text('Receipts read just now').evaluate().isNotEmpty,
      reason: 'The model-training receipts were never read from disk.',
    );

    final runCycle = find.byKey(const Key('model-training-run-cycle'));
    await tester.ensureVisible(runCycle);
    await tester.pump();
    await tester.tap(runCycle);
    await tester.pumpAndSettle();

    expect(find.text('Train selected models?'), findsOneWidget);
    expect(starter.calls, isEmpty);
    final approvalInput = find.byKey(
      const Key('model-training-approval-input'),
    );
    expect(approvalInput, findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('confirm-model-training')))
          .onPressed,
      isNull,
    );
    await tester.enterText(approvalInput, engelLocalLlmTrainingApprovalPhrase);
    await tester.pump();
    await tester.tap(find.byKey(const Key('confirm-model-training')));
    await pumpUntil(
      tester,
      () => starter.calls.isNotEmpty,
      reason: 'The run-cycle button never reached the process starter.',
    );

    expect(starter.calls, hasLength(1));
    final call = starter.calls.single;
    expect(
      call.executable.toLowerCase(),
      anyOf(endsWith('python.exe'), endsWith('python')),
    );
    expect(call.arguments, [
      scriptFile.path,
      '--all',
      '--targets',
      'slm,llm',
      '--llm-approval',
      engelLocalLlmTrainingApprovalPhrase,
      '--summary',
    ]);
    expect(call.workingDirectory, appRoot);
    expect(find.text('Training cycle running…'), findsOneWidget);
    expect(tester.widget<FilledButton>(runCycle).onPressed, isNull);
    expect(
      find.textContaining('Training cycle running (PID 4242)'),
      findsOneWidget,
    );

    // The orchestrator writes its receipt and then exits. The panel must report
    // the receipt, not the exit code alone.
    cycleFile.writeAsStringSync(
      jsonEncode({
        'schema': 'engel_real_training_cycle_v1',
        'run_id': 'cycle-fixture-2',
        'started_at_utc': DateTime.now().toUtc().toIso8601String(),
        'finished_at_utc': DateTime.now().toUtc().toIso8601String(),
        'status': 'PASS',
        'dry_run': false,
        'steps': [
          {'step': 'push_packs', 'ok': true, 'detail': '1 pack', 'seconds': 3},
          {
            'step': 'build_dataset',
            'ok': true,
            'detail': 'built',
            'seconds': 44,
          },
          {
            'step': 'train_slm',
            'ok': true,
            'detail': 'all gates met',
            'seconds': 380,
          },
        ],
        'packs': {'files': 1, 'rows': 12, 'admitted': 9, 'pushed': 1},
        'dataset': {
          'built_at_utc': DateTime.now().toUtc().toIso8601String(),
          'train': 900,
          'val': 100,
          'prompt_training_rows': 9,
          'dataset_dir': '/opt/engel/datasets/engel_sft',
        },
        'slm': {'tasks': <String, dynamic>{}, 'mirrored': <String>[]},
        'lora_next_steps': <String>[],
        'blockers': <String>[],
      }),
    );
    starter.exitCode.complete(0);
    await pumpUntil(
      tester,
      () => find.textContaining('Training cycle PASS').evaluate().isNotEmpty,
      reason: 'The finished training-cycle result never appeared.',
    );

    expect(find.textContaining('3 of 3 steps ok'), findsOneWidget);
    expect(
      find.text('Latest model results: PASS · cycle finished just now'),
      findsOneWidget,
    );
    // The pack line reads the pack receipt, never the cycle's aggregate, so a
    // missing pack receipt stays honest even after a passing cycle.
    expect(find.text('No pack receipt yet'), findsOneWidget);
    expect(
      find.text('900 train · 100 validation · 9 prompt-training · just now'),
      findsOneWidget,
    );
    expect(tester.widget<FilledButton>(runCycle).onPressed, isNotNull);
    expect(starter.stopTreeCalls, 0);
  });

  testWidgets('SLM-only model training needs no LLM approval phrase', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = createModelTrainingFixtureDirectory();
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final separator = Platform.pathSeparator;
    final scriptFile = File(
      '${fixtures.path}${separator}run_engel_real_training_cycle.py',
    )..writeAsStringSync('"""Training-cycle fixture."""\n');
    writeModelTrainingRuntimeContract(fixtures);
    final starter = RecordingTrainingProcessStarter();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        trainingProcessStarter: starter.call,
        uiPreferencesPath: '',
        realTrainingCycleScriptPath: scriptFile.path,
        realTrainingCycleReceiptPath:
            '${fixtures.path}${separator}absent_cycle.json',
        promptTrainingPackReceiptPath:
            '${fixtures.path}${separator}absent_pack.json',
        slmRosterMirrorPath: '${fixtures.path}${separator}absent_roster.json',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find.text('Receipts read just now').evaluate().isNotEmpty,
    );

    final llmTarget = find.byKey(const Key('training-target-llm'));
    tester.widget<CheckboxListTile>(llmTarget).onChanged!(false);
    await tester.pump();
    final runCycle = find.byKey(const Key('model-training-run-cycle'));
    await tester.ensureVisible(runCycle);
    await tester.tap(runCycle);
    await tester.pumpAndSettle();

    expect(find.text('Train selected models?'), findsOneWidget);
    expect(
      find.byKey(const Key('model-training-approval-input')),
      findsNothing,
    );
    final confirm = find.byKey(const Key('confirm-model-training'));
    expect(tester.widget<FilledButton>(confirm).onPressed, isNotNull);
    await tester.tap(confirm);
    await pumpUntil(tester, () => starter.calls.isNotEmpty);

    expect(starter.calls.single.arguments, [
      scriptFile.path,
      '--all',
      '--targets',
      'slm',
      '--summary',
    ]);
    expect(starter.stopTreeCalls, 0);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    expect(
      starter.stopTreeCalls,
      1,
      reason:
          'Disposing Engel must stop its owned model-training process tree.',
    );
    starter.exitCode.complete(1);
    await tester.pump();
  });

  testWidgets('Model Training refuses a missing runtime contract', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final fixtures = createModelTrainingFixtureDirectory();
    addTearDown(() {
      if (fixtures.existsSync()) fixtures.deleteSync(recursive: true);
    });
    final separator = Platform.pathSeparator;
    final scriptFile = File(
      '${fixtures.path}${separator}run_engel_real_training_cycle.py',
    )..writeAsStringSync('# model-cycle fixture\n');
    final starter = RecordingTrainingProcessStarter();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        trainingProcessStarter: starter.call,
        uiPreferencesPath: '',
        realTrainingCycleScriptPath: scriptFile.path,
        realTrainingCycleReceiptPath:
            '${fixtures.path}${separator}absent_cycle.json',
        promptTrainingPackReceiptPath:
            '${fixtures.path}${separator}absent_pack.json',
        slmRosterMirrorPath: '${fixtures.path}${separator}absent_roster.json',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'training');
    await pumpUntil(
      tester,
      () => find.text('Receipts read just now').evaluate().isNotEmpty,
    );

    tester
        .widget<CheckboxListTile>(find.byKey(const Key('training-target-llm')))
        .onChanged!(false);
    await tester.pump();
    final runCycle = find.byKey(const Key('model-training-run-cycle'));
    await tester.ensureVisible(runCycle);
    await tester.tap(runCycle);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-model-training')));
    await pumpUntil(
      tester,
      () => find
          .textContaining(
            'Model training was refused before launch because its runtime safety contract',
          )
          .evaluate()
          .isNotEmpty,
      reason: 'The missing runtime contract refusal never reached the UI.',
    );

    expect(starter.calls, isEmpty);
    expect(
      find.textContaining(
        'Model training was refused before launch because its runtime safety contract',
      ),
      findsOneWidget,
    );
  });

  testWidgets('Model Training confirms process exit after its deadline', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final starter = RecordingTrainingProcessStarter();
    await startSlmModelTrainingFixture(
      tester,
      starter,
      contractContents: shortModelTrainingRuntimeContractFixture,
    );

    await tester.pump(const Duration(seconds: 4));
    await tester.pump();
    expect(starter.stopTreeCalls, 1);
    expect(
      find.textContaining('Stopping owned process tree PID 4242'),
      findsOneWidget,
    );

    starter.exitCode.complete(137);
    await pumpUntil(
      tester,
      () => find
          .textContaining('exited after the process-tree stop')
          .evaluate()
          .isNotEmpty,
      reason: 'The deadline stop was claimed before process exit was observed.',
    );
  });

  testWidgets('Model Training keeps controls locked when stop is unconfirmed', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final starter = RecordingTrainingProcessStarter(stopTreeResult: false);
    await startSlmModelTrainingFixture(
      tester,
      starter,
      contractContents: shortModelTrainingRuntimeContractFixture,
    );

    await tester.pump(const Duration(seconds: 4));
    await tester.pump();
    expect(starter.stopTreeCalls, 1);
    expect(
      find.textContaining('Windows did not confirm a stop request'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const Key('model-training-run-cycle')),
          )
          .onPressed,
      isNull,
    );
  });

  testWidgets('Model Training surfaces a process-tree stop exception', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final starter = RecordingTrainingProcessStarter(
      stopTreeError: StateError('fixture stop failure'),
    );
    await startSlmModelTrainingFixture(
      tester,
      starter,
      contractContents: shortModelTrainingRuntimeContractFixture,
    );

    await tester.pump(const Duration(seconds: 4));
    await tester.pump();
    expect(starter.stopTreeCalls, 1);
    expect(
      find.textContaining('Stop error: Bad state: fixture stop failure'),
      findsOneWidget,
    );
  });

  testWidgets('Model Training refuses to claim a stop without process exit', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final starter = RecordingTrainingProcessStarter();
    await startSlmModelTrainingFixture(
      tester,
      starter,
      contractContents: shortModelTrainingRuntimeContractFixture,
    );

    await tester.pump(const Duration(seconds: 4));
    await tester.pump();
    expect(starter.stopTreeCalls, 1);
    await tester.pump(const Duration(seconds: 1));
    await tester.pump();
    expect(
      find.textContaining('did not exit within the reviewed termination grace'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<FilledButton>(
            find.byKey(const Key('model-training-run-cycle')),
          )
          .onPressed,
      isNull,
    );
  });

  testWidgets('Workspace storage separates common and technical checks', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'files');

    expect(find.text('Workspace storage'), findsOneWidget);
    expect(find.text('Check workspace'), findsOneWidget);
    expect(find.text('Rescan models'), findsOneWidget);
    expect(find.text('Open 3D room'), findsOneWidget);
    expect(find.text('Check runtime readiness'), findsNothing);
    await tester.tap(find.byKey(const Key('storage-more-checks')));
    await tester.pumpAndSettle();
    expect(find.text('Check runtime readiness'), findsOneWidget);
    expect(find.text('Check server storage'), findsOneWidget);
    expect(find.text('Show archive paths'), findsOneWidget);
    expect(find.text('Verify archive boundary'), findsOneWidget);
  });

  testWidgets('retired vision gallery section is not active navigation', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tester.enterText(find.byKey(const Key('section-search')), 'vision');
    await tester.pump();

    expect(find.byKey(const Key('section-vision_gallery')), findsNothing);
    expect(find.text('Engel Vision Tools'), findsNothing);
  });

  testWidgets('retired source gallery is not exposed in active navigation', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tester.enterText(find.byKey(const Key('section-search')), 'gallery');
    await tester.pump();

    expect(find.byKey(const Key('section-gallery')), findsNothing);
    expect(find.byKey(const Key('section-vision_gallery')), findsNothing);
  });

  testWidgets('retired reverse source pages are not active tabs', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tester.enterText(find.byKey(const Key('section-search')), 'source');
    await tester.pump();

    expect(find.textContaining('Retired source reference'), findsNothing);
  });

  testWidgets('retired mobile model catalog resolves to Devices', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'mobile_models');

    expect(find.text('Devices & Workers'), findsWidgets);
    expect(find.text('More device tools'), findsOneWidget);
    expect(find.text('Engel Mobile Models and Workers'), findsNothing);
    expect(find.text('Mobile Install Gate'), findsNothing);
  });

  testWidgets('retired free-model catalog resolves to Models', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'free_models');
    await tester.tap(find.byKey(const Key('models-advanced-tools')));
    await tester.pump();

    expect(find.text('Models'), findsWidgets);
    expect(find.text('Choose models'), findsOneWidget);
    expect(find.text('Local Files'), findsOneWidget);
    expect(find.text('Free / Local LLM Models'), findsNothing);
    expect(find.text('Model Source Evidence Matrix'), findsNothing);
    expect(find.text('Check Runtime'), findsOneWidget);
    expect(find.text('Verify Runtime'), findsOneWidget);
    expect(find.text('Agentic Free Model Routing Matrix'), findsNothing);
    expect(find.text('RunPod Gate'), findsNothing);
  });

  testWidgets('surface finder opens channel workbench', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'messaging');

    expect(find.byKey(const Key('messaging-page')), findsOneWidget);
    expect(find.text('Chat with Engel'), findsOneWidget);
    expect(find.text('Meeting Room'), findsOneWidget);
    expect(find.text('Check phone connection'), findsOneWidget);
    expect(find.text('Check shared workspace'), findsOneWidget);
    expect(find.text('More messaging tools'), findsOneWidget);
    expect(find.byKey(const Key('messaging-pairing')), findsNothing);
    expect(find.text('Imported Messaging Reference'), findsNothing);
  });

  testWidgets('messaging checks use the matching live routes', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'messaging');

    await tester.tap(find.byKey(const Key('messaging-phone-status')));
    await pumpAction(tester);
    await tester.tap(find.byKey(const Key('messaging-shared-status')));
    await pumpAction(tester);
    await tester.tap(find.byKey(const Key('messaging-more-tools')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(
      find.byKey(const Key('messaging-recent-shared')),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('messaging-recent-shared')));
    await pumpAction(tester);

    expect(runner.calls.map((call) => call.arguments).toList(), [
      ['lan-link', 'status'],
      ['shared-room', 'status'],
      ['shared-room', 'tail'],
    ]);
    expect(tester.takeException(), isNull);
  });

  testWidgets('surface finder opens chat runtime workbench', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'chat_runtime');

    expect(find.text('Chat with Engel'), findsOneWidget);
    expect(
      find.text('Hello Joshua,\nhow can Engel assist you today?'),
      findsOneWidget,
    );
    expect(find.byKey(const ValueKey('mac-chat-bubble-empty')), findsNothing);
    expect(find.byKey(const Key('engel-chat-thread')), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-composer')), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-input')), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-send')), findsOneWidget);
    expect(find.textContaining('Sent to Engel Meeting Room'), findsNothing);
    expect(
      find.textContaining('Meeting Room native order intake'),
      findsNothing,
    );
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed,
      isNull,
    );

    await tester.enterText(
      find.byKey(const Key('engel-chat-input')),
      'help me summarize the current task',
    );
    await tester.pump();

    expect(find.text('help me summarize the current task'), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('home prompt opens Chat and sends the request', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final calls = <List<String>>[];
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              calls.add(List<String>.from(arguments));
              return ProcessResult(
                201,
                0,
                jsonEncode({
                  'ok': true,
                  'status': 'ok',
                  'assistant_reply': 'Here is the concise Engel answer.',
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();

    await tester.enterText(
      find.byKey(const Key('home-chat-input')),
      'Summarize my current task.',
    );
    await tester.tap(find.byKey(const Key('home-chat-send')));
    await tester.pumpAndSettle();

    expect(calls, hasLength(1));
    expect(find.text('Chat with Engel'), findsOneWidget);
    expect(find.text('Summarize my current task.'), findsOneWidget);
    expect(
      find.textContaining('Here is the concise Engel answer.'),
      findsWidgets,
    );
  });

  testWidgets('guided agent work preserves Home text for review before send', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final calls = <List<String>>[];
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              calls.add(List<String>.from(arguments));
              return ProcessResult(301, 0, '{}', '');
            },
      ),
    );
    await tester.pump();

    const goal = 'Check models and storage, then summarize any problems.';
    await tester.enterText(find.byKey(const Key('home-chat-input')), goal);
    await tester.tap(find.text('Do a task'));
    await tester.pumpAndSettle();

    expect(find.text('Give Engel a goal'), findsOneWidget);
    expect(
      tester
          .widget<EditableText>(
            find.descendant(
              of: find.byKey(const Key('agent-work-goal-input')),
              matching: find.byType(EditableText),
            ),
          )
          .controller
          .text,
      goal,
    );
    expect(
      find.text(
        'Nothing runs yet. You will review the request in Chat before sending it.',
      ),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('agent-work-review')));
    await tester.pumpAndSettle();

    expect(find.text('Chat with Engel'), findsOneWidget);
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('engel-chat-input')))
          .controller!
          .text,
      goal,
    );
    expect(find.byKey(const Key('agent-work-review-banner')), findsOneWidget);
    expect(find.text('Task ready to start'), findsOneWidget);
    expect(find.text('Start task'), findsOneWidget);
    expect(find.textContaining('engel work'), findsNothing);
    expect(calls, isEmpty, reason: 'Reviewing a goal must never auto-send it.');
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed,
      isNotNull,
    );
  });

  testWidgets('guided task keeps routing command behind the plain UI', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    String? submittedPrompt;
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              submittedPrompt = File(
                promptFilePathFrom(arguments),
              ).readAsStringSync();
              return ProcessResult(
                302,
                0,
                jsonEncode({
                  'ok': true,
                  'status': 'EXECUTION_PASSED_OUTPUT_UNTRUSTED',
                  'final_decision': 'The task finished with proof.',
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();

    const goal = 'Check model status and summarize problems.';
    await tester.enterText(find.byKey(const Key('home-chat-input')), goal);
    await tester.tap(find.text('Do a task'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('agent-work-review')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Start task'));
    await tester.pump();
    await tester.tap(find.text('Start task'));
    await tester.pumpAndSettle();

    expect(submittedPrompt, 'engel work $goal');
    expect(find.text('Task: $goal'), findsOneWidget);
    expect(find.textContaining('engel work'), findsNothing);
    expect(find.textContaining('The task finished with proof.'), findsWidgets);
  });

  testWidgets('guided task shows plain progress, completion, and proof', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final completer = Completer<ProcessResult>();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) {
              return completer.future;
            },
      ),
    );
    await tester.pump();

    const goal = 'Check models and report their status.';
    const receiptPath =
        r'D:\b.WorkSpace\Engel App\reports\engel_agent_kernel\TASK_PROOF.json';
    await tester.enterText(find.byKey(const Key('home-chat-input')), goal);
    await tester.tap(find.text('Do a task'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('agent-work-review')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Start task'));
    await tester.pump();

    expect(find.byKey(const Key('agent-task-status-card')), findsOneWidget);
    expect(find.text('Engel is working on your task'), findsOneWidget);
    expect(find.byKey(const Key('agent-task-progress')), findsOneWidget);
    expect(find.text('Engel runtime'), findsNothing);

    completer.complete(
      ProcessResult(
        304,
        0,
        jsonEncode({
          'ok': true,
          'readable_output_captured': true,
          'assistant_reply':
              'Engel Agent Kernel\n\nGoal: $goal\nStatus: done\nSelected: direct -- read-only route\n\nLanes:\n- [OK] direct: model status ready\n\nReceipt: $receiptPath',
        }),
        '',
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Task completed'), findsOneWidget);
    expect(find.text('Result: done'), findsOneWidget);
    expect(find.byKey(const Key('agent-task-progress')), findsNothing);
    expect(find.byKey(const Key('agent-task-proof')), findsOneWidget);

    await tester.tap(find.byKey(const Key('agent-task-proof')));
    await tester.pumpAndSettle();
    expect(find.text('Task proof'), findsOneWidget);
    expect(find.textContaining(receiptPath), findsWidgets);
    await tester.tap(find.text('Done'));
    await tester.pumpAndSettle();
  });

  testWidgets('guided task failure preserves the goal for reviewed retry', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final calls = <List<String>>[];
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              calls.add(List<String>.from(arguments));
              return ProcessResult(
                305,
                0,
                jsonEncode({
                  'ok': true,
                  'readable_output_captured': true,
                  'assistant_reply':
                      'Engel Agent Kernel\n\nStatus: 0/1 lanes done -- needs attention\n\nReceipt: D:\\proof\\needs-attention.json',
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();

    const goal = 'Check storage and summarize any problem.';
    await tester.enterText(find.byKey(const Key('home-chat-input')), goal);
    await tester.tap(find.text('Do a task'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('agent-work-review')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Start task'));
    await tester.pumpAndSettle();

    expect(calls, hasLength(1));
    expect(find.text('Task needs attention'), findsOneWidget);
    expect(find.byKey(const Key('agent-task-retry')), findsOneWidget);

    await tester.tap(find.byKey(const Key('agent-task-retry')));
    await tester.pumpAndSettle();

    expect(calls, hasLength(1), reason: 'Retry must return to review first.');
    expect(find.text('Task ready to start'), findsOneWidget);
    expect(find.text('Start task'), findsOneWidget);
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('engel-chat-input')))
          .controller!
          .text,
      goal,
    );
  });

  testWidgets('stopped guided task ignores a late reply and offers review', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final completer = Completer<ProcessResult>();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) {
              return completer.future;
            },
      ),
    );
    await tester.pump();

    const goal = 'Check models, then summarize the result.';
    await tester.enterText(find.byKey(const Key('home-chat-input')), goal);
    await tester.tap(find.text('Do a task'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('agent-work-review')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Start task'));
    await tester.pump();
    await tester.tap(find.byKey(const Key('engel-chat-stop')));
    await tester.pump();

    expect(find.text('Task stopped'), findsOneWidget);
    expect(find.byKey(const Key('agent-task-retry')), findsOneWidget);

    completer.complete(
      ProcessResult(
        307,
        0,
        jsonEncode({
          'ok': true,
          'readable_output_captured': true,
          'assistant_reply': 'This late reply must be ignored.',
        }),
        '',
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Task stopped'), findsOneWidget);
    expect(find.textContaining('late reply'), findsNothing);
    await tester.tap(find.byKey(const Key('agent-task-retry')));
    await tester.pumpAndSettle();
    expect(find.text('Task ready to start'), findsOneWidget);
  });

  testWidgets('guided task can become a normal chat without losing text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    String? submittedPrompt;
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              submittedPrompt = File(
                promptFilePathFrom(arguments),
              ).readAsStringSync();
              return ProcessResult(
                303,
                0,
                jsonEncode({
                  'ok': true,
                  'status': 'EXECUTION_PASSED_OUTPUT_UNTRUSTED',
                  'final_decision': 'Normal chat reply.',
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();

    const goal = 'Explain the model status.';
    await tester.enterText(find.byKey(const Key('home-chat-input')), goal);
    await tester.tap(find.text('Do a task'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('agent-work-review')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('agent-work-use-as-chat')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('agent-work-review-banner')), findsNothing);
    expect(find.text('Start task'), findsNothing);
    expect(find.text('Send'), findsOneWidget);
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('engel-chat-input')))
          .controller!
          .text,
      goal,
    );

    await tester.tap(find.text('Send'));
    await tester.pumpAndSettle();
    expect(submittedPrompt, goal);
  });

  testWidgets('guided task review remains usable at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    const goal = 'Check the current system status.';
    await tester.enterText(find.byKey(const Key('home-chat-input')), goal);
    await tester.ensureVisible(find.text('Do a task'));
    await tester.tap(find.text('Do a task'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('agent-work-review')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('agent-work-review-banner')), findsOneWidget);
    expect(find.text('Task ready to start'), findsOneWidget);
    expect(find.text('Start task'), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-input')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('guided task result and proof remain usable at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              return ProcessResult(
                306,
                0,
                jsonEncode({
                  'ok': true,
                  'readable_output_captured': true,
                  'assistant_reply':
                      'Engel Agent Kernel\n\nStatus: done\n\nReceipt: D:\\proof\\large-text.json',
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();

    await tester.enterText(
      find.byKey(const Key('home-chat-input')),
      'Check the system status.',
    );
    await tester.ensureVisible(find.text('Do a task'));
    await tester.tap(find.text('Do a task'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('agent-work-review')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Start task'));
    await tester.pump();
    await tester.tap(find.text('Start task'));
    await tester.pumpAndSettle();

    expect(find.text('Task completed'), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('agent-task-proof')));
    expect(find.byKey(const Key('agent-task-proof')), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.byKey(const Key('agent-task-proof')));
    await tester.pumpAndSettle();
    expect(find.text('Task proof'), findsOneWidget);
    expect(find.byKey(const Key('agent-task-proof-path')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('cancelling guided agent work leaves the Home draft unchanged', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    const draft = 'Keep this unfinished request.';
    await tester.enterText(find.byKey(const Key('home-chat-input')), draft);
    await tester.tap(find.text('Do a task'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(
      tester
          .widget<TextField>(find.byKey(const Key('home-chat-input')))
          .controller!
          .text,
      draft,
    );
    expect(find.text('Welcome back, Joshua.'), findsOneWidget);
  });

  testWidgets('new chat protects an existing conversation', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              return ProcessResult(
                202,
                0,
                jsonEncode({
                  'ok': true,
                  'status': 'ok',
                  'assistant_reply': 'Conversation content to preserve.',
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'chat_runtime');

    await tester.tap(find.byKey(const Key('chat-new-chat')));
    await tester.pump();
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('engel-chat-input')))
          .focusNode
          ?.hasFocus,
      isTrue,
    );

    await tester.enterText(
      find.byKey(const Key('engel-chat-input')),
      'Keep this request.',
    );
    await tester.tap(find.byKey(const Key('engel-chat-send')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('chat-new-chat')));
    await tester.pumpAndSettle();

    expect(find.text('Start a new chat?'), findsOneWidget);
    expect(find.byKey(const Key('confirm-new-chat')), findsOneWidget);
    await tester.tap(find.text('Keep this chat'));
    await tester.pumpAndSettle();
    expect(find.text('Keep this request.'), findsOneWidget);
  });

  testWidgets(
    'chat provider route applies once and only the final reply announces',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1600, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final providerCalls = <String>[];
      var replyNumber = 0;

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          serverHealthProbe: () async => true,
          localChatRunner:
              (executable, arguments, {workingDirectory, environment}) async {
                providerCalls.add(
                  environment?['ENGEL_UI_PROVIDER_CHOICE'] ?? 'missing',
                );
                replyNumber += 1;
                return ProcessResult(
                  300 + replyNumber,
                  0,
                  jsonEncode({
                    'ok': true,
                    'status': 'ok',
                    'assistant_reply': 'Reply $replyNumber.',
                  }),
                  '',
                );
              },
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'chat_runtime');

      expect(find.byKey(const Key('engel-chat-provider')), findsNothing);
      await tester.tap(find.byKey(const Key('chat-tools-button')));
      await tester.pumpAndSettle();
      final provider = find.byKey(const Key('engel-chat-provider'));
      tester.widget<DropdownButton<String>>(provider).onChanged!('anthropic');
      await tester.pump();
      expect(
        tester.widget<DropdownButton<String>>(provider).value,
        'anthropic',
      );
      await tester.tap(find.text('Close'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('engel-chat-input')),
        'Use Claude for this message.',
      );
      await tester.pump();
      final firstSend = tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed;
      expect(firstSend, isNotNull);
      firstSend!();
      await tester.pump();
      await tester.pumpAndSettle();

      expect(providerCalls, ['anthropic']);
      expect(find.byKey(const Key('engel-chat-provider')), findsNothing);
      await tester.tap(find.byKey(const Key('chat-tools-button')));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<DropdownButton<String>>(
              find.byKey(const Key('engel-chat-provider')),
            )
            .value,
        'auto',
      );
      await tester.tap(find.text('Close'));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('engel-chat-input')),
        'Use the normal route now.',
      );
      await tester.pump();
      final secondSend = tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed;
      expect(secondSend, isNotNull);
      secondSend!();
      await tester.pump();
      await tester.pumpAndSettle();

      expect(providerCalls, ['anthropic', 'auto']);
      expect(
        tester
            .widget<Semantics>(
              find.byKey(const ValueKey('mac-chat-semantics-thread-1')),
            )
            .properties
            .liveRegion,
        isFalse,
      );
      expect(
        tester
            .widget<Semantics>(
              find.byKey(const ValueKey('mac-chat-semantics-thread-3')),
            )
            .properties
            .liveRegion,
        isTrue,
      );
    },
  );

  testWidgets('simple Chat keeps diagnostics in a tools dialog', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();
    await tapSideSection(tester, 'chat_runtime');

    expect(find.byKey(const Key('chat-tools-button')), findsOneWidget);
    expect(find.text('Choose chat model'), findsNothing);
    expect(find.text('Check connection'), findsNothing);

    await activateWithKeyboard(
      tester,
      find.byKey(const Key('chat-tools-button')),
    );

    expect(find.text('Model and context'), findsOneWidget);
    expect(find.text('Route for next message'), findsOneWidget);
    expect(find.text('Automatic (recommended)'), findsOneWidget);
    expect(
      find.text(
        'This choice applies once and returns to Automatic after sending.',
      ),
      findsOneWidget,
    );
    expect(find.text('Choose chat model'), findsOneWidget);
    expect(find.text('Connection and diagnostics'), findsOneWidget);
    expect(find.text('Check connection'), findsOneWidget);
  });

  testWidgets('long-running actions require confirmation', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final runner = RecordingProcessRunner();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'training');
    await tester.tap(find.byKey(const Key('hour-training-control')));
    await tester.pumpAndSettle();
    expect(find.text('Start one-hour training?'), findsOneWidget);
    expect(find.byKey(const Key('confirm-hour-training')), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    await tapSideSection(tester, 'tasks');
    await tester.tap(find.byKey(const Key('tasks-advanced-tools')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Backend Auto-Fix Agents'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Backend Auto-Fix Agents'));
    await tester.pumpAndSettle();
    expect(find.text('Run backend repair agents?'), findsOneWidget);
    expect(find.byKey(const Key('confirm-backend-autofix')), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(runner.calls, isEmpty);
  });

  testWidgets(
    'accessibility controls support 200 percent in a compact window',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1024, 768));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
      await tester.pump();
      await tapSideSection(tester, 'appearance_settings');

      expect(
        find.byKey(const Key('simple-navigation-setting')),
        findsOneWidget,
      );
      final sliderFinder = find.byKey(const Key('interface-text-scale'));
      expect(sliderFinder, findsOneWidget);
      tester.widget<Slider>(sliderFinder).onChanged!(2);
      await tester.pumpAndSettle();

      expect(find.text('200%'), findsOneWidget);
      expect(find.byKey(const Key('open-navigation-menu')), findsOneWidget);
      expect(
        find.byKey(const Key('persistent-navigation-panel')),
        findsNothing,
      );

      await tapSideSection(tester, 'chat_runtime');
      expect(find.byKey(const Key('engel-chat-composer')), findsOneWidget);
    },
  );

  testWidgets('large-text navigation opens, dismisses, and handles Escape', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();

    expect(find.byKey(const Key('persistent-navigation-panel')), findsNothing);
    await tester.tap(find.byKey(const Key('open-navigation-menu')));
    await tester.pump();
    expect(find.byKey(const Key('compact-navigation-panel')), findsOneWidget);
    expect(find.byKey(const Key('section-search')), findsOneWidget);

    await tester.enterText(find.byKey(const Key('section-search')), 'proof');
    await tester.pump();
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pump();
    expect(find.byKey(const Key('compact-navigation-panel')), findsOneWidget);
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('section-search')))
          .controller!
          .text,
      isEmpty,
    );

    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pump();
    expect(find.byKey(const Key('compact-navigation-panel')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('200 percent text persists and can be reset safely', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1200, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final tempDirectory = Directory.systemTemp.createTempSync(
      'engel-interface-scale-',
    );
    addTearDown(() async {
      for (var attempt = 0; attempt < 10; attempt++) {
        if (!tempDirectory.existsSync()) return;
        try {
          await tempDirectory.delete(recursive: true);
          return;
        } on FileSystemException {
          await Future<void>.delayed(const Duration(milliseconds: 50));
        }
      }
      if (tempDirectory.existsSync()) {
        await tempDirectory.delete(recursive: true);
      }
    });
    final preferencesFile = File(
      '${tempDirectory.path}${Platform.pathSeparator}ui_preferences.json',
    );

    Widget testApp() => EngelMainApp(
      enableStartupTasks: false,
      enableTrainingRunStatusPolling: false,
      enableDeviceStatusScan: false,
      uiPreferencesPath: preferencesFile.path,
    );

    await tester.pumpWidget(testApp());
    await tester.pump();
    await tapSideSection(tester, 'appearance_settings');
    var sliderFinder = find.byKey(const Key('interface-text-scale'));
    tester.widget<Slider>(sliderFinder).onChanged!(2);
    await tester.pump();
    sliderFinder = find.byKey(const Key('interface-text-scale'));
    tester.widget<Slider>(sliderFinder).onChangeEnd!(2);
    await pumpUntil(tester, () {
      if (!preferencesFile.existsSync()) return false;
      try {
        final saved = jsonDecode(preferencesFile.readAsStringSync()) as Map;
        return saved['interface_text_scale'] == 2;
      } on FormatException {
        return false;
      }
    }, reason: 'The 200 percent interface preference was not saved.');

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    await tester.pumpWidget(testApp());
    await pumpUntil(
      tester,
      () => find.byKey(const Key('open-navigation-menu')).evaluate().isNotEmpty,
      reason: 'The saved 200 percent preference was not restored.',
    );
    await tapSideSection(tester, 'appearance_settings');
    sliderFinder = find.byKey(const Key('interface-text-scale'));
    expect(tester.widget<Slider>(sliderFinder).value, 2);
    expect(find.text('200%'), findsOneWidget);

    final resetFinder = find.byKey(const Key('reset-interface-text-scale'));
    await tester.ensureVisible(resetFinder);
    await tester.pump();
    await tester.tap(resetFinder);
    await pumpUntil(
      tester,
      () {
        try {
          final saved = jsonDecode(preferencesFile.readAsStringSync()) as Map;
          return saved['interface_text_scale'] == 1;
        } on FormatException {
          return false;
        }
      },
      reason: 'Reset did not restore the 100 percent interface preference.',
    );
    expect(find.text('100%'), findsOneWidget);
    expect(
      find.byKey(const Key('persistent-navigation-panel')),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 200)),
    );
  });

  testWidgets('workbenches stack and remain reachable at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    const routes = <(String, String, String)>[
      ('command_center', 'Command Center', 'Chat with Engel'),
      ('device_visibility', 'Devices & Workers', 'More device tools'),
      ('agents', 'Agents', 'Meeting Room'),
      ('memory_guard', 'Memory', 'More memory tools'),
      ('build_pipeline', 'Build', 'Plan a build in Chat'),
    ];
    for (final route in routes) {
      await tapSideSection(tester, route.$1);
      await tester.pump();
      expect(
        find.byKey(const Key('adaptive-workbench-scroll')),
        findsOneWidget,
        reason: route.$1,
      );
      expect(find.text(route.$2), findsWidgets, reason: route.$1);
      expect(find.text(route.$3), findsOneWidget, reason: route.$1);
      expect(tester.takeException(), isNull, reason: route.$1);
    }
  });

  testWidgets('chat composer exposes file and folder context controls', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();
    await tapSideSection(tester, 'chat_runtime');

    expect(find.byKey(const Key('engel-chat-attach')), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-folder-context')), findsOneWidget);
    expect(find.text('Attach'), findsOneWidget);
    expect(find.text('Folder'), findsOneWidget);
    expect(find.byKey(const Key('engel-chat-provider')), findsNothing);
  });

  testWidgets(
    'chat composer and tools remain usable at 200 percent in a compact window',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 760));
      tester.platformDispatcher.textScaleFactorTestValue = 2.0;
      addTearDown(() {
        tester.binding.setSurfaceSize(null);
        tester.platformDispatcher.textScaleFactorTestValue = 1.0;
      });

      await tester.pumpWidget(
        const EngelMainApp(
          enableStartupTasks: false,
          enableTrainingRunStatusPolling: false,
          enableDeviceStatusScan: false,
          uiPreferencesPath: '',
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'chat_runtime');

      expect(find.byKey(const Key('engel-chat-composer')), findsOneWidget);
      expect(find.text('Attach'), findsOneWidget);
      expect(find.text('Folder'), findsOneWidget);
      expect(find.byKey(const Key('engel-chat-provider')), findsNothing);
      expect(tester.takeException(), isNull);

      await tester.tap(find.byKey(const Key('chat-tools-button')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('chat-provider-route-setting')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('engel-chat-provider')), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'chat Send suppresses duplicate runs and preserves hyphen prompts',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1800, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      final calls = <List<String>>[];
      final completer = Completer<ProcessResult>();

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          localChatRunner:
              (executable, arguments, {workingDirectory, environment}) {
                calls.add([...arguments]);
                return completer.future;
              },
        ),
      );
      await tester.pump();

      await tapSideSection(tester, 'chat_runtime');

      await tester.enterText(
        find.byKey(const Key('engel-chat-input')),
        '--help',
      );
      await tester.pump();
      final send = tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed;
      expect(send, isNotNull);
      send!();
      send();
      await tester.pump();

      expect(calls, hasLength(1));
      expect(
        calls.single.first,
        contains('run_engel_ui_chat_meeting_room_llm.py'),
      );
      final promptFilePath = promptFilePathFrom(calls.single);
      final promptFileText = File(promptFilePath).readAsStringSync();
      expect(promptFileText, contains('--help'));
      expect(promptFileText, isNot(contains('Engel code capability context:')));
      expect(promptFileText, isNot(contains('Operator request follows:')));
      expect(promptFileText, isNot(contains('COMPLETE EXPERT MASTERY')));
      // While a chat run is live the Send button is replaced by Stop.
      expect(find.byKey(const Key('engel-chat-send')), findsNothing);
      expect(find.byKey(const Key('engel-chat-stop')), findsOneWidget);
      expect(
        find.textContaining('Engel is working on your message.'),
        findsOneWidget,
      );
      expect(
        find.textContaining('I will say when this is done or if it failed.'),
        findsOneWidget,
      );
      expect(find.textContaining('Prompt file:'), findsNothing);
      expect(find.textContaining('Backend script:'), findsNothing);

      completer.complete(
        ProcessResult(
          77,
          0,
          jsonEncode({
            'ok': true,
            'status': 'EXECUTION_PASSED_OUTPUT_UNTRUSTED',
            'final_decision': 'Fake local reply',
          }),
          '',
        ),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('Fake local reply'), findsWidgets);
      expect(find.text('--help'), findsOneWidget);
    },
  );

  testWidgets('chat adds code context only to direct software work', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final promptFiles = <String>[];
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              promptFiles.add(promptFilePathFrom(arguments));
              return ProcessResult(
                78,
                0,
                jsonEncode({
                  'ok': true,
                  'status': 'ok',
                  'assistant_reply': 'Test reply',
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'chat_runtime');

    for (final prompt in [
      'Write a brief client update in English and then Spanish.',
      'Ask Gamma to classify a short drafting note.',
      'Have all three phone workers and Sub-Engel check in.',
      'Are you the same Engel I talk to in the desktop app?',
      'If I ask for a real app, what proof should you show after building it?',
      'A wall-panel shop drawing confirms the module widths and grid lines. What safe drafting work can I complete now?',
    ]) {
      await tester.enterText(find.byKey(const Key('engel-chat-input')), prompt);
      await tester.pump();
      final send = tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed;
      expect(send, isNotNull);
      send!();
      await tester.pumpAndSettle();
    }

    expect(promptFiles, hasLength(6));
    for (final path in promptFiles) {
      final text = File(path).readAsStringSync();
      expect(text, isNot(contains('Engel code capability context:')));
      expect(text, isNot(contains('Operator request follows:')));
    }

    await tester.enterText(
      find.byKey(const Key('engel-chat-input')),
      'Build a small app that checks shop drawing dimensions.',
    );
    await tester.pump();
    tester
        .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
        .onPressed!();
    await tester.pumpAndSettle();

    expect(promptFiles, hasLength(7));
    final buildPrompt = File(promptFiles.last).readAsStringSync();
    expect(buildPrompt, contains('Engel code capability context:'));
    expect(buildPrompt, contains('Operator request follows:'));
  });

  testWidgets('chat Send uses Engel standalone chat reply JSON', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              return ProcessResult(
                80,
                0,
                jsonEncode({
                  'ok': true,
                  'status': 'EXECUTION_PASSED_OUTPUT_UNTRUSTED',
                  'readable_output_captured': true,
                  'receipt': {
                    'assistant_reply': 'Hello from Engel standalone chat LLM.',
                    'readable_output_captured': true,
                  },
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'chat_runtime');

    await tester.enterText(find.byKey(const Key('engel-chat-input')), 'hello');
    await tester.pump();
    final send = tester
        .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
        .onPressed;
    expect(send, isNotNull);
    send!();
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Hello from Engel standalone chat LLM.'),
      findsWidgets,
    );
  });

  testWidgets(
    'verified build receipt opens right-side preview and proof panel',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1800, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          localChatRunner:
              (executable, arguments, {workingDirectory, environment}) async {
                return ProcessResult(
                  88,
                  0,
                  jsonEncode({
                    'ok': true,
                    'status': 'app build lifecycle verified',
                    'assistant_reply': 'The verified build is ready.',
                    'receipt': {
                      'ok': true,
                      'build_verified': true,
                      'build_size': 'large',
                      'action': {'kind': 'app_build', 'language': 'web'},
                      'build_preview': {
                        'kind': 'web',
                        'title': 'Drafting Portal',
                        'workspace_path':
                            '/opt/engel/workspaces/drafting_portal',
                        'entry_file': 'index.html',
                        'files': ['README.md', 'index.html', 'app.js'],
                        'url': '/build-preview/drafting_portal/index.html',
                        'source_url':
                            '/build-preview/drafting_portal/index.html',
                        'run_output': '',
                      },
                      'build_package': {
                        'path':
                            '/opt/engel/packages/builds/drafting_portal.zip',
                        'download_url': '/build-package/drafting_portal.zip',
                        'sha256': 'abc123',
                      },
                      'build_review': {
                        'provider': {'summary': 'Reviewed and ready.'},
                      },
                      'build_lifecycle': [
                        {
                          'stage': 'generate',
                          'status': 'passed',
                          'detail': 'generated files',
                        },
                        {
                          'stage': 'package',
                          'status': 'passed',
                          'detail': 'package ready',
                        },
                        {
                          'stage': 'open_proof',
                          'status': 'ready',
                          'detail': 'preview ready',
                        },
                      ],
                    },
                  }),
                  '',
                );
              },
        ),
      );
      await tester.pump();
      await tapSideSection(tester, 'chat_runtime');
      await tester.enterText(
        find.byKey(const Key('engel-chat-input')),
        'Build me a large drafting portal web app.',
      );
      await tester.pump();
      final send = tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed;
      expect(send, isNotNull);
      send!();
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('engel-build-preview-panel')),
        findsOneWidget,
      );
      expect(find.text('Drafting Portal'), findsOneWidget);
      expect(find.text('large web - verified'), findsOneWidget);
      expect(
        find.byKey(const Key('engel-build-preview-open-browser')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('engel-build-preview-package')),
        findsOneWidget,
      );

      await tester.tap(find.text('Files'));
      await tester.pumpAndSettle();
      expect(find.text('index.html'), findsOneWidget);
      expect(find.text('app.js'), findsOneWidget);

      await tester.tap(find.text('Proof'));
      await tester.pumpAndSettle();
      expect(find.text('generate - passed'), findsOneWidget);
      expect(find.text('open_proof - ready'), findsOneWidget);
      expect(find.textContaining('Reviewed and ready.'), findsOneWidget);
      expect(find.textContaining('abc123'), findsOneWidget);

      await tester.tap(find.byKey(const Key('engel-build-preview-close')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('engel-build-preview-panel')), findsNothing);
    },
  );

  testWidgets('chat Send can create a Mission Control artifact through the UI', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    var capturedArguments = <String>[];
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner: (executable, arguments, {workingDirectory, environment}) async {
          capturedArguments = List<String>.from(arguments);
          final promptFileText = File(
            promptFilePathFrom(arguments),
          ).readAsStringSync();
          expect(promptFileText, contains('Mission Control job'));
          expect(promptFileText, contains('ui_mission_control_demo'));
          return ProcessResult(
            85,
            0,
            jsonEncode({
              'ok': true,
              'status': 'Mission Control job completed',
              'readable_output_captured': true,
              'selected_provider': 'mission_control',
              'assistant_output_text':
                  'Mission Control created ui_mission_control_demo. Final receipt: /mnt/ssd-ai/engel-control/jobs/completed/test/final_receipt.md',
              'visible_reply':
                  'Mission Control created ui_mission_control_demo. Final receipt: /mnt/ssd-ai/engel-control/jobs/completed/test/final_receipt.md',
              'assistant_reply':
                  'Mission Control created ui_mission_control_demo. Final receipt: /mnt/ssd-ai/engel-control/jobs/completed/test/final_receipt.md',
              'named_artifact':
                  '/mnt/ssd-ai/engel-control/jobs/completed/test/artifacts/ui_mission_control_demo.json',
            }),
            '',
          );
        },
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'chat_runtime');

    const prompt =
        'Engel, create a Mission Control job: make a worker heartbeat proof artifact named ui_mission_control_demo, verify it, and tell me the final receipt path.';
    await tester.enterText(find.byKey(const Key('engel-chat-input')), prompt);
    await tester.pump();
    final send = tester
        .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
        .onPressed;
    expect(send, isNotNull);
    await tester.runAsync(() async {
      send!();
      await Future<void>.delayed(const Duration(milliseconds: 100));
    });
    await tester.pump();

    final replyFinder = find.textContaining(
      'Mission Control created ui_mission_control_demo',
    );
    for (var i = 0; i < 20 && replyFinder.evaluate().isEmpty; i++) {
      final thread = find.byKey(const Key('engel-chat-thread'));
      if (thread.evaluate().isNotEmpty) {
        await tester.drag(thread, const Offset(0, -700));
      }
      await tester.pump(const Duration(milliseconds: 100));
    }

    expect(capturedArguments, contains('--max-tokens=6000'));
    expect(replyFinder, findsWidgets);
    expect(find.textContaining('Engel Error'), findsNothing);
  });

  testWidgets('chat Send shows local LLM answer before Meeting Room proof', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    const naturalReply = 'Yes, I can hear you from Engel AI Main local chat.';
    const proofReply =
        'Done. I routed this through the Agent Meeting Room and got real station output back.';
    var capturedArguments = <String>[];

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              capturedArguments = List<String>.from(arguments);
              return ProcessResult(
                81,
                0,
                jsonEncode({
                  'ok': true,
                  'status':
                      'chat replied through local LLM and Agent Meeting Room',
                  'readable_output_captured': true,
                  'assistant_reply': proofReply,
                  'assistant_output_text': naturalReply,
                  'local_llm_reply': naturalReply,
                  'meeting_room_reply': proofReply,
                  'meeting_room_station_results': [
                    'Android Phone Alpha Agent: Returned',
                    'Verifier Agent: Assigned',
                  ],
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'chat_runtime');

    await tester.enterText(find.byKey(const Key('engel-chat-input')), 'hello');
    await tester.pump();
    final send = tester
        .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
        .onPressed;
    expect(send, isNotNull);
    send!();
    await tester.pumpAndSettle();

    expect(
      capturedArguments,
      contains('--timeout=$engelLocalChatTimeoutSeconds'),
    );
    expect(capturedArguments, contains('--max-tokens=640'));
    final operatorBubble = find.byKey(
      const ValueKey('mac-chat-bubble-thread-0'),
    );
    expect(
      find.descendant(
        of: operatorBubble,
        matching: find.textContaining('hello'),
      ),
      findsOneWidget,
    );
    final engelAiBubbles = find.byKey(
      const ValueKey('mac-chat-bubble-thread-1'),
    );
    expect(
      find.descendant(
        of: engelAiBubbles,
        matching: find.textContaining(naturalReply),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: engelAiBubbles,
        matching: find.textContaining(proofReply),
      ),
      findsNothing,
    );
    expect(find.textContaining('Meeting Room proof:'), findsNothing);
  });
  testWidgets('chat Send reports missing assistant output clearly', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              return ProcessResult(
                79,
                0,
                'Loading model...\nBuild: test\nModel metadata\nExiting...',
                '',
              );
            },
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'chat_runtime');

    await tester.enterText(find.byKey(const Key('engel-chat-input')), 'hello');
    await tester.pump();
    final send = tester
        .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
        .onPressed;
    expect(send, isNotNull);
    send!();
    await tester.pumpAndSettle();

    expect(
      find.textContaining('no readable assistant answer was captured'),
      findsWidgets,
    );
  });
  testWidgets('chat Send shows ok false JSON as Engel Error', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              return ProcessResult(
                78,
                0,
                jsonEncode({
                  'ok': false,
                  'status': 'REJECTED',
                  'reason': 'Prompt rejected by bounded local chat gate',
                }),
                '',
              );
            },
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'chat_runtime');

    await tester.enterText(
      find.byKey(const Key('engel-chat-input')),
      'blocked',
    );
    await tester.pump();
    final send = tester
        .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
        .onPressed;
    expect(send, isNotNull);
    send!();
    await tester.pumpAndSettle();

    expect(
      find.textContaining('Prompt rejected by bounded local chat gate'),
      findsWidgets,
    );
  });

  testWidgets('chat Send accepts readable soft-failure bridge replies', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    const readableReply =
        'That is Engel answering through the hidden browser chat lane.';
    final chatResult = Completer<ProcessResult>();
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              return chatResult.future;
            },
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'chat_runtime');

    await tester.enterText(
      find.byKey(const Key('engel-chat-input')),
      'what is this?',
    );
    await tester.pump();
    final send = tester
        .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
        .onPressed;
    expect(send, isNotNull);
    send!();
    await tester.pump();

    expect(
      find.byKey(const ValueKey('mac-chat-status-thread-1')),
      findsOneWidget,
    );
    expect(
      find.textContaining('Engel is working on your message.'),
      findsOneWidget,
    );
    expect(
      find.textContaining('I will say when this is done or if it failed.'),
      findsOneWidget,
    );
    expect(find.textContaining('Prompt file:'), findsNothing);
    expect(find.textContaining('Backend script:'), findsNothing);
    expect(find.byTooltip('COT / background data'), findsNothing);

    chatResult.complete(
      ProcessResult(
        82,
        0,
        jsonEncode({
          'ok': false,
          'status': 'chat route incomplete',
          'readable_output_captured': true,
          'assistant_reply': readableReply,
          'assistant_output_text': readableReply,
          'local_llm_reply': readableReply,
          'visible_thinking_summary':
              'Engel Thinking:\n- I treated this as normal conversation.\n- I saved this exchange into persistent Engel memory.',
        }),
        '',
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining(readableReply), findsWidgets);
    expect(
      find.byKey(const ValueKey('mac-chat-status-thread-1')),
      findsNothing,
    );
    expect(find.textContaining('Prompt file:'), findsNothing);
    expect(find.textContaining('Backend script:'), findsNothing);
    expect(find.textContaining('Engel Thinking:'), findsNothing);
    expect(find.textContaining('persistent Engel memory'), findsNothing);
    expect(find.textContaining('chat route incomplete'), findsNothing);
    expect(find.textContaining('did not return a usable reply'), findsNothing);
    expect(find.byTooltip('COT / background data'), findsNothing);
  });

  testWidgets('chat Send keeps frustrated normal chat on compact fast lane', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    const reply = 'I see the chat break. I will keep this answer direct.';
    final chatResult = Completer<ProcessResult>();
    var capturedArguments = <String>[];
    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        localChatRunner:
            (executable, arguments, {workingDirectory, environment}) async {
              capturedArguments = List<String>.from(arguments);
              return chatResult.future;
            },
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'chat_runtime');

    await tester.enterText(
      find.byKey(const Key('engel-chat-input')),
      'I am frustrated this keeps breaking; answer plain.',
    );
    await tester.pump();
    final send = tester
        .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
        .onPressed;
    expect(send, isNotNull);
    send!();
    await tester.pump();

    expect(capturedArguments, contains('--max-tokens=640'));
    expect(
      find.textContaining('Route: normal chat lane first'),
      findsOneWidget,
    );
    expect(find.textContaining('creation/device classifier'), findsNothing);

    chatResult.complete(
      ProcessResult(
        83,
        0,
        'warming upgraded bridge\n${jsonEncode({'ok': true, 'status': 'chat replied', 'readable_output_captured': true, 'visible_reply': reply})}\nbridge done',
        '',
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining(reply), findsWidgets);
    expect(find.textContaining('warming upgraded bridge'), findsNothing);
  });

  testWidgets(
    'chat Send shows readable nested reply despite soft-failure exit',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1800, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      const reply = 'Readable nested answer from the upgraded chat bridge.';
      await tester.pumpWidget(
        EngelMainApp(
          enableStartupTasks: false,
          localChatRunner:
              (executable, arguments, {workingDirectory, environment}) async {
                return ProcessResult(
                  84,
                  1,
                  jsonEncode({
                    'ok': false,
                    'status': 'chat route soft failure',
                    'readable_output_captured': true,
                    'choices': [
                      {
                        'message': {'content': reply},
                      },
                    ],
                  }),
                  '',
                );
              },
        ),
      );
      await tester.pump();

      await tapSideSection(tester, 'chat_runtime');

      await tester.enterText(
        find.byKey(const Key('engel-chat-input')),
        'answer this without breaking',
      );
      await tester.pump();
      final send = tester
          .widget<FilledButton>(find.byKey(const Key('engel-chat-send')))
          .onPressed;
      expect(send, isNotNull);
      send!();
      await tester.pumpAndSettle();

      expect(find.textContaining(reply), findsWidgets);
      expect(find.textContaining('chat route soft failure'), findsNothing);
      expect(find.textContaining('Engel Error'), findsNothing);
    },
  );
  testWidgets('static voice and source sections are retired from active nav', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    expect(find.byKey(const Key('section-voice_screen')), findsNothing);
    expect(find.textContaining('Retired source reference'), findsNothing);
    expect(find.byKey(const Key('section-gallery')), findsNothing);

    await tapSideSection(tester, 'chat_runtime');

    expect(find.byKey(const Key('engel-chat-input')), findsOneWidget);
  });

  testWidgets('retired overlay catalog resolves to Settings', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'overlay_center');

    expect(find.text('Settings'), findsWidgets);
    expect(find.text('Engel Overlay Center'), findsNothing);
    expect(find.text('Overlay Search'), findsNothing);
    expect(find.text('Gateway Start Plan'), findsNothing);
  });

  testWidgets('surface finder opens command center workbench', (
    WidgetTester tester,
  ) async {
    // Taller surface than the pre-consolidation 1000px: the owning window now
    // carries a tab strip, so the lazily-built rows below need the room to be
    // constructed in the test viewport.
    await tester.binding.setSurfaceSize(const Size(1900, 1120));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'command_center');

    expect(find.text('Command Center'), findsWidgets);
    expect(find.text('Chat with Engel'), findsOneWidget);
    expect(find.text('Connection help'), findsOneWidget);
    expect(find.text('System checks'), findsOneWidget);
    expect(find.text('Check Workers'), findsOneWidget);
    expect(find.byKey(const Key('advanced-command-search')), findsOneWidget);
    expect(find.text('Session Search'), findsNothing);
    expect(find.text('Imported Command Center Reference'), findsNothing);
  });

  testWidgets('System Intent tab explains the auditable HIPL MIPL round trip', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1500, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'command_center');

    final intentTab = find.byKey(const Key('section-tab-intent_bridge'));
    expect(intentTab, findsOneWidget);
    await tester.tap(intentTab);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('intent-bridge-page')), findsOneWidget);
    expect(
      find.text('Human intent in, verified comprehension out.'),
      findsOneWidget,
    );
    expect(find.text('1 · HIPL expression'), findsOneWidget);
    expect(find.text('2 · Lifted intent'), findsOneWidget);
    expect(find.text('3 · MIPL IR'), findsOneWidget);
    expect(find.text('4 · Comprehension'), findsOneWidget);
    expect(find.text('MIPL v2 low-resource + agent packets'), findsOneWidget);
    expect(
      find.textContaining('maximum 32 packets and 32 KB per handoff'),
      findsOneWidget,
    );
    expect(
      find.textContaining('Intent classification is not approval.'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('intent-bridge-open-chat')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('artifacts section opens understandable proof files', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'artifacts');

    expect(find.byKey(const Key('artifacts-page')), findsOneWidget);
    expect(find.text('Proof files'), findsOneWidget);
    expect(find.text('Screenshot Evidence'), findsOneWidget);
    expect(find.text('Check workspace'), findsOneWidget);
    expect(find.text('Imported Artifacts Reference'), findsNothing);
  });

  testWidgets('retired cron catalog resolves to Tasks', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'cron');

    expect(find.text('Tasks'), findsWidgets);
    expect(find.text('Create a task'), findsOneWidget);
    expect(find.text('Cron and Worker Jobs'), findsNothing);
  });

  testWidgets('skills section opens toolsets workbench', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'skills');

    expect(find.byKey(const Key('skills-page')), findsOneWidget);
    expect(find.text('See Engel skills'), findsOneWidget);
    expect(find.text('Check skill readiness'), findsOneWidget);
    expect(find.text('Task-agent skill catalog'), findsOneWidget);
    expect(find.text('Manage tools'), findsOneWidget);
    expect(find.text('AI model skills'), findsOneWidget);
    expect(find.text('More skill tools'), findsOneWidget);
    expect(find.byKey(const Key('skills-feature-map')), findsNothing);
    expect(find.text('Imported Skills Reference'), findsNothing);
    expect(find.text('Legacy Skills Route'), findsNothing);
  });

  testWidgets('skill review and checks use real capability routes', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'skills');

    await tester.tap(find.byKey(const Key('skills-see-available')));
    await pumpAction(tester);
    await tester.tap(find.byKey(const Key('skills-readiness')));
    await pumpAction(tester);
    await tester.tap(find.byKey(const Key('skills-more-tools')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('skills-feature-map')));
    await pumpAction(tester);

    expect(runner.calls.map((call) => call.arguments).toList(), [
      ['route-details', 'engel.engel_agent.toolsets'],
      ['runtime-readiness', 'verify'],
      ['feature-inventory', 'json'],
    ]);
    expect(tester.takeException(), isNull);
  });

  testWidgets('task-agent skill catalog uses the bounded local MIPL module', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'skills');

    await tester.tap(find.byKey(const Key('skills-mipl-agent-catalog')));
    await pumpAction(tester);

    expect(runner.calls, hasLength(1));
    expect(runner.calls.single.executable, runtimePythonExe);
    expect(runner.calls.single.arguments, [miplAgentWorkScriptPath, 'skills']);
    expect(tester.takeException(), isNull);
  });

  testWidgets('tool library section opens app roots and tool proof workbench', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'tool_library');

    expect(find.byKey(const Key('tools-page')), findsOneWidget);
    expect(find.text('See available tools'), findsOneWidget);
    expect(find.text('Check tool readiness'), findsOneWidget);
    expect(find.text('Open Skills'), findsOneWidget);
    expect(find.byKey(const Key('tool-route-finder')), findsOneWidget);
    expect(find.byKey(const Key('tool-route-search')), findsOneWidget);
    expect(find.text('Find a tool'), findsOneWidget);
    expect(find.text('How to search'), findsOneWidget);
    expect(find.text('More tool controls'), findsOneWidget);
    expect(find.byKey(const Key('tools-wsl')), findsNothing);

    await tester.enterText(find.byKey(const Key('tool-route-search')), 'wsl');
    await tester.pump();

    expect(find.textContaining('matches'), findsWidgets);
    expect(find.text('WSL tools'), findsOneWidget);
    expect(find.text('All Rust Tool Surface'), findsNothing);
    expect(find.text('Rust Command Catalog Coverage'), findsNothing);
    expect(find.text('Engel Tool Route Ownership Matrix'), findsNothing);
  });

  testWidgets('tool inventory and readiness use guarded Rust routes', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'tool_library');

    await tester.tap(find.byKey(const Key('tools-see-available')));
    await pumpAction(tester);
    await tester.tap(find.byKey(const Key('tools-check-readiness')));
    await pumpAction(tester);
    await tester.tap(find.byKey(const Key('tools-more-controls')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('tools-native-list')));
    await pumpAction(tester);
    await tester.tap(find.byKey(const Key('tools-wsl')));
    await pumpAction(tester);

    expect(runner.calls.map((call) => call.arguments).toList(), [
      ['bundled-tools', 'list'],
      ['bundled-tools', 'verify'],
      ['minor-tools', 'list'],
      ['runtime-workspaces', 'wsl-tools'],
    ]);
    expect(tester.takeException(), isNull);
  });

  testWidgets('agent capability tabs remain usable at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'skills');
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('skills-more-tools')),
    );
    await tester.ensureVisible(find.byKey(const Key('skills-agent-roster')));
    await tester.pump();
    expect(tester.takeException(), isNull);

    await tapSideSection(tester, 'tool_library');
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('tools-more-controls')),
    );
    await tester.ensureVisible(find.byKey(const Key('tools-open-3d-room')));
    await tester.pump();
    expect(tester.takeException(), isNull);

    await tapSideSection(tester, 'messaging');
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('messaging-more-tools')),
    );
    await tester.ensureVisible(
      find.byKey(const Key('messaging-recent-shared')),
    );
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('retired agent toolchain resolves to Agents', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'agent_toolchain');

    expect(find.text('Agents'), findsWidgets);
    expect(find.text('Meeting Room'), findsOneWidget);
    expect(find.text('Give Engel a goal'), findsOneWidget);
    expect(find.text('More agent tools'), findsOneWidget);
    expect(find.text('Engel Imported Agent Toolchain'), findsNothing);
    expect(find.text('Jarvis Status'), findsNothing);
  });

  testWidgets('retired tool-gate page resolves to Tools', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'tool_gates');

    expect(find.byKey(const Key('tools-page')), findsOneWidget);
    expect(find.text('See available tools'), findsOneWidget);
    expect(find.text('Engel Tool Gates'), findsNothing);
    expect(find.text('Jarvis install'), findsNothing);
  });

  testWidgets('retired LAN catalog resolves to Connection help', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'lan_gateway');

    expect(find.text('Connection help'), findsWidgets);
    expect(find.text('Check connection'), findsOneWidget);
    expect(find.text('Repair connection'), findsOneWidget);
    expect(find.text('Engel LAN Gateway'), findsNothing);
    expect(find.text('Receive Start Gate'), findsNothing);
  });

  testWidgets('retired architect catalog resolves to Tasks', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'architect_planner');

    expect(find.text('Tasks'), findsWidgets);
    expect(find.text('Create a task'), findsOneWidget);
    expect(find.text('Engel Architect Planner'), findsNothing);
    expect(find.text('Agentic Architect Contract'), findsNothing);
  });

  testWidgets('agents section opens Engel agents workbench', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'agents');

    expect(find.text('Agents'), findsWidgets);
    expect(find.text('Meeting Room'), findsOneWidget);
    expect(find.text('Give Engel a goal'), findsOneWidget);
    expect(find.text('Create a task agent'), findsOneWidget);
    expect(find.text('View connected agents'), findsOneWidget);
    expect(find.text('Prepared agent tasks'), findsOneWidget);
    expect(find.text('More agent tools'), findsOneWidget);
    expect(find.text('Assign work to specific workers'), findsNothing);
    expect(find.text('Repair backend agents'), findsNothing);
    expect(find.text('Engel Agents Workbench'), findsNothing);
  });

  testWidgets('Agents everyday actions review first and stay inside Engel', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        processRunner: runner.call,
        serverHealthProbe: () async => true,
      ),
    );
    await tester.pump();
    await tester.pump();
    await tapSideSection(tester, 'agents');

    await tester.tap(find.byKey(const Key('agents-give-goal')));
    await tester.pumpAndSettle();
    expect(find.text('Give Engel a goal'), findsWidgets);
    expect(
      find.text(
        'Nothing runs yet. You will review the request in Chat before sending it.',
      ),
      findsOneWidget,
    );
    expect(runner.calls, isEmpty);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('agents-meeting-room')));
    await tester.pump();
    expect(find.byKey(const Key('meeting-page')), findsOneWidget);
    expect(find.byKey(const Key('meeting-order-input')), findsOneWidget);
    expect(runner.calls, isEmpty);
  });

  testWidgets('Agents can create a bounded MIPL draft with selected skills', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'agents');

    await tester.tap(find.byKey(const Key('agents-create-mipl-agent')));
    await tester.pumpAndSettle();
    expect(find.text('Create a task agent'), findsWidgets);
    expect(
      find.textContaining('Engel creates a draft work packet first'),
      findsOneWidget,
    );
    await tester.enterText(
      find.byKey(const Key('mipl-agent-name-input')),
      'Training Review Agent',
    );
    await tester.enterText(
      find.byKey(const Key('mipl-agent-task-input')),
      'Review the latest training receipts and return evidence for operator review.',
    );
    await tester.tap(find.byKey(const Key('mipl-agent-create-draft')));
    await tester.pumpAndSettle();

    expect(runner.calls, hasLength(1));
    final args = runner.calls.single.arguments;
    expect(args.take(2).toList(), [miplAgentWorkScriptPath, 'create']);
    expect(args, containsAll(['--name', 'Training Review Agent']));
    expect(args, contains('repository_research'));
    expect(args, contains('reporting'));
    expect(args, contains('--summary'));
    expect(tester.takeException(), isNull);
  });

  testWidgets('Agents advanced tools open by keyboard at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'agents');

    expect(find.byKey(const Key('agents-give-goal')), findsOneWidget);
    expect(find.byKey(const Key('agents-meeting-room')), findsOneWidget);
    expect(find.byKey(const Key('agents-repair-backend')), findsNothing);
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('agents-more-tools')),
    );

    expect(find.byKey(const Key('agents-dispatch-work')), findsOneWidget);
    expect(find.byKey(const Key('agents-repair-backend')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('agents-repair-backend')));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('operator navigation hides old cluster surfaces', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    expect(find.byKey(const Key('section-cluster')), findsNothing);
    expect(find.byKey(const Key('section-colony_hive')), findsNothing);
    expect(find.text('Cluster Ops'), findsNothing);
    expect(find.text('Colony Hive'), findsNothing);

    await tester.enterText(find.byKey(const Key('section-search')), 'cluster');
    await tester.pump();

    expect(find.byKey(const Key('section-cluster')), findsNothing);
    expect(find.byKey(const Key('section-colony_hive')), findsNothing);
  });

  testWidgets(
    'worker dispatch shows common actions and confirms real work orders',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1900, 1100));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
      await tester.pump();

      await tapSideSection(tester, 'worker_dispatch');

      expect(find.text('Engel Worker Dispatch'), findsOneWidget);
      expect(find.text('Assignment status'), findsOneWidget);
      expect(find.text('Prepared jobs'), findsOneWidget);
      expect(find.text('Returned work status'), findsOneWidget);
      expect(find.text('Communication coordinator'), findsNothing);
      await tester.tap(find.byKey(const Key('dispatch-more-tools')));
      await tester.pumpAndSettle();
      expect(find.text('Communication coordinator'), findsOneWidget);
      expect(find.text('Claim next job'), findsOneWidget);
      expect(find.text('Worker safety'), findsOneWidget);
      expect(find.byKey(const Key('dispatch-draft-router')), findsOneWidget);
      expect(find.byKey(const Key('dispatch-draft-input')), findsOneWidget);
      expect(find.text('Dispatch Draft Classification'), findsOneWidget);
      expect(find.textContaining('SUB_ENGEL_WORK_ORDERS'), findsOneWidget);
      expect(find.textContaining('Draft status: empty'), findsOneWidget);
      expect(
        find.byKey(const Key('write-sub-engel-work-order')),
        findsOneWidget,
      );
      expect(find.text('Review work order'), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('dispatch-draft-input')),
        'send phone screenshot evidence to verifier',
      );
      await tester.pump();

      expect(
        find.textContaining('Recommended lane: Phone / Android worker lane'),
        findsOneWidget,
      );
      final routeGate = tester.widget<Text>(
        find.byKey(const Key('dispatch-route-gate')),
      );
      expect(
        routeGate.data,
        contains('android_workers_push_jobs + lan_link_status'),
      );
      await tester.tap(find.byKey(const Key('write-sub-engel-work-order')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('sub-engel-order-confirmation')),
        findsOneWidget,
      );
      await tester.tap(find.byKey(const Key('sub-engel-order-cancel')));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('sub-engel-order-confirmation')),
        findsNothing,
      );
    },
  );

  testWidgets('surface finder opens profile workbench', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'profiles');

    expect(find.byKey(const Key('profiles-page')), findsOneWidget);
    expect(find.text('Everyday profile controls'), findsOneWidget);
    expect(find.text('Engel on this PC'), findsOneWidget);
    expect(find.text('People & Meeting Room'), findsOneWidget);
    expect(find.text('AI model profiles'), findsOneWidget);
    expect(find.text('Advanced profile tools'), findsOneWidget);
    expect(find.byKey(const Key('profiles-latest-order')), findsNothing);
    expect(find.text('Imported Profiles Reference'), findsNothing);
  });

  testWidgets('profile advanced tools run their matching commands', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'profiles');

    await tester.tap(find.byKey(const Key('profiles-advanced')));
    await tester.pumpAndSettle();

    final actions = <Key, List<String>>{
      const Key('profiles-latest-order'): ['meeting-room', 'latest-order'],
      const Key('profiles-shared-status'): ['shared-room', 'status'],
      const Key('profiles-shared-messages'): ['shared-room', 'tail'],
      const Key('profiles-feature-inventory'): ['feature-inventory', 'json'],
      const Key('profiles-workspace-check'): [
        'workspace-inventory',
        'verify-all-parts',
      ],
    };

    for (final action in actions.entries) {
      final finder = find.byKey(action.key);
      expect(finder, findsOneWidget);
      await tester.ensureVisible(finder);
      await tester.pump();
      await tester.tap(finder);
      await pumpAction(tester);
    }

    expect(
      runner.calls.map((call) => call.arguments).toList(),
      actions.values.toList(),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('profiles remain usable at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'profiles');

    expect(find.byKey(const Key('profiles-this-pc')), findsOneWidget);
    expect(find.byKey(const Key('profiles-people')), findsOneWidget);
    expect(find.byKey(const Key('profiles-models')), findsOneWidget);
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('profiles-advanced')),
    );
    expect(find.byKey(const Key('profiles-latest-order')), findsOneWidget);
    expect(find.byKey(const Key('profiles-workspace-check')), findsOneWidget);
    await tester.ensureVisible(
      find.byKey(const Key('profiles-workspace-check')),
    );
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('surface finder opens common Sub-Engel actions', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'sub_engel_link');

    expect(find.text('Engel Sub-Engel Link'), findsOneWidget);
    expect(find.text('Check shared room'), findsOneWidget);
    expect(find.text('Refresh work queue'), findsOneWidget);
    expect(find.text('W Drive Network Blocker'), findsNothing);
  });

  testWidgets('drives section opens workspace roots workbench', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'files');

    expect(find.text('Workspace storage'), findsOneWidget);
    expect(find.text('Check workspace'), findsOneWidget);
    expect(find.text('Check server storage'), findsNothing);
    expect(find.text('Open 3D room'), findsOneWidget);
    await tester.tap(find.byKey(const Key('storage-more-checks')));
    await tester.pumpAndSettle();
    expect(find.text('Check server storage'), findsOneWidget);
    expect(find.text('Show archive paths'), findsOneWidget);
    expect(find.text('Verify archive boundary'), findsOneWidget);
    expect(find.byKey(const Key('required-root-gate')), findsOneWidget);
    expect(find.text('Required Root Gate Matrix'), findsOneWidget);
    expect(find.text('0/3 online'), findsOneWidget);
    expect(find.text('not checked'), findsOneWidget);
    expect(find.byKey(const Key('required-root-CT fast SSD')), findsOneWidget);
    expect(
      find.byKey(const Key('required-root-PowerEdge HDD archive')),
      findsOneWidget,
    );
    expect(find.text('Required Root Coverage'), findsOneWidget);
    expect(find.text('Required roots online: not checked yet'), findsOneWidget);
    expect(find.text('Live Root Check Routes'), findsOneWidget);
    expect(find.textContaining('NOT CHECKED CT fast SSD:'), findsWidgets);
    expect(find.textContaining('CT 246 health: run CT status'), findsOneWidget);
    expect(find.text('Agentic Drive Ownership Matrix'), findsOneWidget);
    expect(find.textContaining('CT fast SSD owner:'), findsOneWidget);
    expect(find.textContaining('PowerEdge HDD owner:'), findsOneWidget);
    expect(find.text('Server Runtime Storage'), findsOneWidget);
  });

  testWidgets('retired shared-bus matrix resolves to Devices', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'shared_bus');

    expect(find.text('Devices & Workers'), findsWidgets);
    expect(find.text('Live connections'), findsOneWidget);
    expect(find.text('Engel Shared Bus and W Drive'), findsNothing);
    expect(find.text('W Drive Blocker'), findsNothing);
  });

  testWidgets('retired runtime workspace resolves to Build', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'runtime_workspace');

    expect(find.byKey(const Key('build-page-title')), findsOneWidget);
    expect(find.text('Plan a build in Chat'), findsOneWidget);
    expect(find.text('Engel Runtime Workspace'), findsNothing);
    expect(find.text('WSL Distros'), findsNothing);
  });

  testWidgets('Build recommends a reviewed request before result tools', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'build_pipeline');

    expect(find.byKey(const Key('build-page-title')), findsOneWidget);
    expect(find.text('Recommended first'), findsOneWidget);
    expect(find.byKey(const Key('build-start-request')), findsOneWidget);
    expect(find.text('Plan a build in Chat'), findsOneWidget);
    expect(
      find.textContaining('Nothing builds until you review and send it'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('build-review-files')), findsOneWidget);
    expect(find.byKey(const Key('build-open-preview')), findsOneWidget);
    expect(find.byKey(const Key('build-more-tools')), findsOneWidget);
    expect(find.byKey(const Key('build-verify-release')), findsNothing);
    expect(find.text('Main Status'), findsNothing);
    expect(find.text('Install Gate'), findsNothing);
    expect(find.text('Release Regression Gate Matrix'), findsNothing);

    await tester.tap(find.byKey(const Key('build-more-tools')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('build-verify-release')), findsOneWidget);
    expect(find.text('Check packaged release'), findsOneWidget);
    expect(
      find.text('Verify the current app without changing it.'),
      findsOneWidget,
    );
  });

  testWidgets('Build request opens Chat for review without starting work', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'build_pipeline');

    expect(runner.calls, isEmpty);
    await tester.tap(find.byKey(const Key('build-start-request')));
    await tester.pump();

    expect(find.byKey(const Key('engel-chat-input')), findsOneWidget);
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('engel-chat-input')))
          .controller
          ?.text,
      'Build this with Engel. Create it, test it, package it, and show the working preview and proof.',
    );
    expect(runner.calls, isEmpty);
  });

  testWidgets('Build tools open by keyboard at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'build_pipeline');

    expect(find.byKey(const Key('build-start-request')), findsOneWidget);
    expect(find.byKey(const Key('build-verify-release')), findsNothing);
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('build-more-tools')),
    );

    expect(find.byKey(const Key('build-verify-release')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('build-verify-release')));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('terminal and files puts common actions before diagnostics', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'terminal_files');

    expect(find.text('Terminal & Files'), findsOneWidget);
    expect(find.text('Find files'), findsOneWidget);
    expect(find.text('Find receipts & logs'), findsOneWidget);
    expect(find.text('Find terminal routes'), findsNothing);
    await tester.tap(find.byKey(const Key('terminal-more-tools')));
    await tester.pumpAndSettle();
    expect(find.text('Find terminal routes'), findsOneWidget);
    expect(find.text('Find previews'), findsOneWidget);
    expect(find.text('Workspace Browser Roots'), findsOneWidget);
    expect(find.text('What this page includes'), findsOneWidget);
    expect(find.text('Imported Right Rail Merged Into Engel'), findsNothing);
  });

  testWidgets('code languages hides the full checklist until requested', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'code_languages');

    expect(find.text('Preferred coding languages'), findsOneWidget);
    expect(find.text('Where to use them'), findsOneWidget);
    expect(find.text('Open Chat'), findsOneWidget);
    expect(find.text('All coding languages'), findsOneWidget);
    expect(find.byType(CheckboxListTile), findsNothing);
    expect(find.text('Code Companion Workbench'), findsNothing);
    await tester.tap(find.byKey(const Key('languages-all-list')));
    await tester.pumpAndSettle();
    expect(find.byType(CheckboxListTile), findsWidgets);
  });

  testWidgets('sandbox lab section opens guarded sandbox workbench', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'sandbox_lab');

    expect(find.text('Sandbox'), findsWidgets);
    expect(find.text('Check sandbox status'), findsOneWidget);
    expect(find.text('Preview create plan'), findsNothing);
    await tester.tap(find.byKey(const Key('sandbox-more-tools')));
    await tester.pumpAndSettle();
    expect(find.text('Preview create plan'), findsOneWidget);
    expect(find.text('Preview delete plan'), findsOneWidget);
    expect(find.text('Sandbox Safety Contract'), findsOneWidget);
  });

  testWidgets('sub-engel link keeps technical controls under More tools', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'sub_engel_link');

    expect(find.text('Engel Sub-Engel Link'), findsOneWidget);
    expect(find.text('Refresh work queue'), findsOneWidget);
    expect(find.text('Check shared room'), findsOneWidget);
    expect(find.text('Open latest order'), findsOneWidget);
    expect(find.text('Open latest returned work'), findsOneWidget);
    expect(find.text('Live Shared Work Queue'), findsOneWidget);
    expect(find.text('W Drive Network Blocker'), findsNothing);
    await tester.tap(find.byKey(const Key('sub-engel-more-tools')));
    await tester.pumpAndSettle();
    expect(find.text('W Drive Network Blocker'), findsOneWidget);
    expect(find.text('Main Policy Audit'), findsOneWidget);
    expect(find.text('Device Link Verify'), findsOneWidget);
    expect(find.text('Phones LAN'), findsOneWidget);
    expect(find.text('Returned Sub-Engel Work'), findsWidgets);
    expect(find.text('Standalone Sub-Engel Zip'), findsOneWidget);
    expect(find.text('Standalone Sub-Engel Download'), findsOneWidget);
    expect(find.textContaining('Packaged CLI self-test'), findsOneWidget);
    expect(find.textContaining('receipt 3C1C4BFB'), findsOneWidget);
    expect(find.textContaining('Packaged lifecycle demo'), findsOneWidget);
    expect(find.textContaining('receipt E12457BF'), findsWidgets);
    expect(
      find.textContaining(
        '4CB483378B202C11DE2C2EA2E9BB0DA249B6E04701D12CD2F6D88ADAEA31A16A',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('Engel AI Sub-Engel'), findsWidgets);
    expect(find.textContaining('Qwen2.5-0.5B-Instruct'), findsWidgets);
    expect(
      find.textContaining('Standalone zip proof: 8A5D791E'),
      findsOneWidget,
    );
    expect(find.text('Main-Side W Drive Action'), findsOneWidget);
    expect(find.textContaining('Bus append state:'), findsOneWidget);
    expect(find.textContaining('Shared room live doc lines:'), findsOneWidget);
    expect(find.textContaining('Main work orders:'), findsOneWidget);
    expect(find.textContaining('Returned Sub-Engel files:'), findsOneWidget);
    await tester.drag(
      find.textContaining('Returned Sub-Engel files:'),
      const Offset(0, -140),
    );
    await tester.pump();
    expect(find.textContaining('Latest Main work order:'), findsOneWidget);
    expect(find.textContaining('Latest returned work:'), findsOneWidget);
    expect(find.textContaining('SUB_ENGEL_SENT_WORK'), findsWidgets);
  });

  testWidgets('retired control matrix resolves to Command Center', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'control');

    expect(find.text('Command Center'), findsWidgets);
    expect(find.text('Connection help'), findsOneWidget);
    expect(find.byKey(const Key('advanced-command-search')), findsOneWidget);
    expect(find.text('Engel Control Room'), findsNothing);
    expect(find.text('Visual System Integrity Matrix'), findsNothing);
  });

  testWidgets('accounts route opens connector workbench', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1500));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'accounts');

    expect(find.text('Engel Accounts and Connectors'), findsOneWidget);
    expect(find.text('Connector Manager'), findsOneWidget);
    expect(find.text('Connection Setup'), findsOneWidget);
    expect(
      find.text('${engelConnectorTargets.length} connectable'),
      findsOneWidget,
    );
    expect(find.text('Standalone Channels'), findsNothing);
    expect(find.text('Standalone Integrations'), findsNothing);
    expect(find.text('Real Output'), findsNothing);
    expect(find.text('Status'), findsOneWidget);
    expect(find.text('Providers'), findsOneWidget);
    expect(find.text('Verify'), findsOneWidget);
    expect(find.text('Gateway'), findsOneWidget);
    expect(find.text('Airtable'), findsOneWidget);
    expect(
      find.byKey(const Key('connector-row-channel-telegram')),
      findsOneWidget,
    );
    expect(find.byKey(const Key('connector-setup-panel')), findsOneWidget);
    expect(find.byKey(const Key('connector-receipt-text')), findsNothing);

    await tester.enterText(
      find.byKey(const Key('connector-search')),
      'airtable',
    );
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('connector-row-integration-airtable')),
      findsOneWidget,
    );
    await tester.tap(
      find.byKey(const Key('connector-connect-integration-airtable')),
    );
    await tester.pump();
    expect(find.text('Airtable'), findsWidgets);
    expect(find.byKey(const Key('connector-secret-input')), findsOneWidget);
    expect(find.byKey(const Key('connector-open-setup')), findsOneWidget);
    expect(find.byKey(const Key('connector-save-connection')), findsOneWidget);
    expect(find.byKey(const Key('connector-test-connection')), findsOneWidget);
    expect(find.text('Open setup'), findsWidgets);
    expect(find.text('Save token'), findsWidgets);
    expect(find.text('Test token'), findsWidgets);
    expect(find.byKey(const Key('connector-receipt-text')), findsNothing);

    await tester.tap(find.byKey(const Key('connector-open-engel-setup')));
    await tester.pumpAndSettle();
    expect(find.text('API keys'), findsWidgets);
    expect(find.text('OpenRouter'), findsWidgets);
    expect(
      find.byKey(const Key('provider-key-input-openrouter')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('provider-key-save-openrouter')),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('provider-key-verify-openrouter')),
      findsOneWidget,
    );
    await tester.tap(find.byIcon(Icons.close).last);
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('connector-stage-selected')));
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 300));
    });
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('connector-receipt-text')), findsNothing);

    expect(find.byKey(const Key('connector-show-receipt')), findsOneWidget);
    final receiptPath =
        '$standaloneConnectionRequestRoot\\integrations\\airtable.json';
    final receipt = File(receiptPath).readAsStringSync();
    expect(receipt, contains('engel_standalone_integration_setup_request_v1'));
    expect(receipt, contains('airtable'));
    await tester.enterText(
      find.byKey(const Key('connector-search')),
      'telegram',
    );
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const Key('connector-connect-channel-telegram')),
    );
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 300));
    });
    await tester.pump();
    expect(find.byKey(const Key('connector-receipt-text')), findsNothing);
    expect(find.byKey(const Key('connector-show-receipt')), findsOneWidget);
    final channelReceiptPath =
        '$standaloneConnectionRequestRoot\\channels\\telegram.json';
    final channelReceipt = File(channelReceiptPath).readAsStringSync();
    expect(
      channelReceipt,
      contains('engel_standalone_channel_setup_request_v1'),
    );
    expect(channelReceipt, contains('telegram'));
  });

  testWidgets('retired research catalog resolves to Memory', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1700, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'research');

    expect(find.byKey(const Key('memory-page-title')), findsOneWidget);
    expect(find.text('Review proposed memories'), findsWidgets);
    expect(find.text('Engel Research and Growth'), findsNothing);
    expect(find.text('Research Brain'), findsNothing);
  });

  testWidgets('retired browser catalog resolves to Chat', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'browser_queen');

    expect(find.byKey(const Key('engel-chat-input')), findsOneWidget);
    expect(find.text('Engel Browser Queen'), findsNothing);
    expect(find.text('Browser Queen Status'), findsNothing);
  });

  testWidgets('retired expert catalog resolves to Build', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'expert_builder');

    expect(find.byKey(const Key('build-page-title')), findsOneWidget);
    expect(find.text('Plan a build in Chat'), findsOneWidget);
    expect(find.text('Engel Expert Builder'), findsNothing);
    expect(find.text('Patch Gate'), findsNothing);
  });

  testWidgets('Memory recommends review before technical checks', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'memory_guard');

    expect(find.byKey(const Key('memory-page-title')), findsOneWidget);
    expect(find.text('Recommended first'), findsOneWidget);
    expect(find.byKey(const Key('memory-review')), findsOneWidget);
    expect(find.text('Review proposed memories'), findsWidgets);
    expect(
      find.textContaining(
        'nothing is approved, saved, or learned automatically',
      ),
      findsOneWidget,
    );
    expect(find.byKey(const Key('memory-more-tools')), findsOneWidget);
    expect(find.byKey(const Key('memory-verify')), findsNothing);
    expect(find.byKey(const Key('memory-learning-queue')), findsNothing);
    expect(find.byKey(const Key('memory-protection')), findsNothing);
    expect(find.text('CT246'), findsNothing);
    expect(find.text('Archive Status'), findsNothing);
    expect(find.text('Inventory Status'), findsNothing);

    await tester.tap(find.byKey(const Key('memory-more-tools')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('memory-verify')), findsOneWidget);
    expect(find.byKey(const Key('memory-learning-queue')), findsOneWidget);
    expect(find.byKey(const Key('memory-protection')), findsOneWidget);
    expect(find.text('Check saved memory'), findsOneWidget);
    expect(find.text('Check learning queue'), findsOneWidget);
    expect(find.text('Check memory protection'), findsOneWidget);
  });

  testWidgets('Memory review is explicit and read-only', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = RecordingProcessRunner();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'memory_guard');

    expect(runner.calls, isEmpty);
    await tester.tap(find.byKey(const Key('memory-review')));
    await pumpAction(tester);

    expect(runner.calls, hasLength(1));
    expect(runner.calls.single.arguments, [
      'memory-review',
      'candidate-review-dashboard',
    ]);
    expect(find.text('Results for Memory'), findsOneWidget);
    expect(find.textContaining('fake_ui_audit'), findsOneWidget);
  });

  testWidgets('Memory tools open by keyboard at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'memory_guard');

    expect(find.byKey(const Key('memory-review')), findsOneWidget);
    expect(find.byKey(const Key('memory-protection')), findsNothing);
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('memory-more-tools')),
    );

    expect(find.byKey(const Key('memory-verify')), findsOneWidget);
    expect(find.byKey(const Key('memory-learning-queue')), findsOneWidget);
    expect(find.byKey(const Key('memory-protection')), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('memory-protection')));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('retired route matrix resolves to concise Proof', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 2100));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'route_matrix');

    expect(find.text('Proof'), findsWidgets);
    expect(find.text('Check Engel safely'), findsOneWidget);
    expect(find.text('Run recommended check'), findsOneWidget);
    expect(find.text('More technical checks'), findsOneWidget);
    expect(find.text('Audit System'), findsNothing);
    expect(find.text('Run Full Verifier'), findsNothing);
    expect(find.text('System Verification'), findsNothing);
    expect(find.text('Check Engine'), findsNothing);
    expect(find.text('Route Catalog'), findsNothing);
    expect(find.text('Feature Inventory Report'), findsNothing);
    expect(find.text('Legacy Status Report'), findsNothing);
  });

  testWidgets('Proof recommends one check and explains technical checks', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1800));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'proof');

    expect(find.text('Proof'), findsWidgets);
    expect(find.text('Check Engel safely'), findsOneWidget);
    expect(find.text('Recommended first'), findsOneWidget);
    expect(find.byKey(const Key('proof-recommended-check')), findsOneWidget);
    expect(find.text('Run recommended check'), findsOneWidget);
    expect(find.byKey(const Key('proof-more-checks')), findsOneWidget);
    expect(find.text('Check proof files'), findsNothing);
    expect(find.text('Test command routing'), findsNothing);
    expect(find.text('View audit information'), findsNothing);

    await tester.tap(find.byKey(const Key('proof-more-checks')));
    await tester.pumpAndSettle();

    expect(find.text('Check proof files'), findsOneWidget);
    expect(find.text('Test command routing'), findsOneWidget);
    expect(find.text('View audit information'), findsOneWidget);
    expect(
      find.text(
        'Read what the audit route covers. This does not run an audit.',
      ),
      findsOneWidget,
    );
    expect(find.text('Audit System'), findsNothing);
    expect(find.text('Check Runtime'), findsNothing);
    expect(find.text('Run Full Verifier'), findsNothing);
    expect(find.text('Test Engine'), findsNothing);
    expect(find.text('Feature Inventory'), findsNothing);
    expect(find.text('Promotion Verifier'), findsNothing);
    expect(find.text('Workspace Report'), findsNothing);
  });

  testWidgets('Proof technical checks open by keyboard at 200 percent text', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });

    await tester.pumpWidget(
      const EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'proof');

    expect(find.byKey(const Key('proof-recommended-check')), findsOneWidget);
    await activateWithKeyboard(
      tester,
      find.byKey(const Key('proof-more-checks')),
    );

    expect(find.byKey(const Key('proof-check-files')), findsOneWidget);
    expect(find.byKey(const Key('proof-test-routing')), findsOneWidget);
    expect(
      find.byKey(const Key('proof-view-audit-information')),
      findsOneWidget,
    );
    await tester.ensureVisible(find.byKey(const Key('proof-test-routing')));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  testWidgets('Proof explains a failed check without implying a repair', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final runner = ScriptedProcessRunner();
    runner.scripts.add(
      () async =>
          ProcessResult(1, 1, '{"ok":false,"issues":["guard mismatch"]}', ''),
    );

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner: runner.call,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();
    await tapSideSection(tester, 'proof');
    await tester.tap(find.byKey(const Key('proof-recommended-check')));
    await pumpAction(tester);

    expect(find.text('Check needs attention'), findsOneWidget);
    expect(
      find.textContaining('completed and found a problem'),
      findsOneWidget,
    );
    expect(find.textContaining('Nothing was changed.'), findsOneWidget);
    expect(find.textContaining('guard mismatch'), findsOneWidget);
    expect(runner.calls, hasLength(1));
    expect(runner.calls.single.arguments, ['runtime-readiness', 'verify']);
    expect(
      tester
          .widget<Semantics>(find.byKey(const Key('proof-result-summary')))
          .properties
          .liveRegion,
      isTrue,
    );
  });

  testWidgets('results stay with their page and link back from another page', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 760));
    tester.platformDispatcher.textScaleFactorTestValue = 2.0;
    addTearDown(() {
      tester.binding.setSurfaceSize(null);
      tester.platformDispatcher.textScaleFactorTestValue = 1.0;
    });
    final pendingResult = Completer<ProcessResult>();

    await tester.pumpWidget(
      EngelMainApp(
        enableStartupTasks: false,
        enableTrainingRunStatusPolling: false,
        enableDeviceStatusScan: false,
        processRunner:
            (executable, arguments, {workingDirectory, environment}) =>
                pendingResult.future,
        rustExeOverride:
            r'D:\b.WorkSpace\Engel App\runtime\test\engel-ai-rs.exe',
        uiPreferencesPath: '',
      ),
    );
    await tester.pump();

    await tapSideSection(tester, 'proof');
    final recommendedCheck = find.byKey(const Key('proof-recommended-check'));
    await tester.ensureVisible(recommendedCheck);
    await tester.tap(recommendedCheck);
    await tester.pump();
    expect(find.text('Working in Proof'), findsOneWidget);

    await tapSideSection(tester, 'command_center');
    expect(find.text('Results for Command Center'), findsOneWidget);
    expect(find.text('No result on Command Center yet.'), findsOneWidget);
    expect(find.text('Engel is working in Proof.'), findsOneWidget);
    expect(find.byKey(const Key('output-open-active-work')), findsOneWidget);
    expect(find.textContaining('fake_ui_audit'), findsNothing);

    pendingResult.complete(
      ProcessResult(1, 0, '{"ok":true,"fake_ui_audit":true}', ''),
    );
    await pumpAction(tester);
    expect(find.text('The latest result is in Proof.'), findsOneWidget);
    expect(find.textContaining('fake_ui_audit'), findsNothing);

    final openLatest = find.byKey(const Key('output-open-latest-result'));
    await tester.ensureVisible(openLatest);
    await tester.tap(openLatest);
    await tester.pump();
    expect(find.text('Proof'), findsWidgets);
    expect(find.text('Results for Proof'), findsOneWidget);
    expect(find.text('Check passed'), findsOneWidget);
    expect(find.textContaining('Nothing was changed.'), findsOneWidget);
    expect(find.textContaining('fake_ui_audit'), findsOneWidget);

    final clearProofResult = find.byTooltip('Clear Proof result');
    await tester.ensureVisible(clearProofResult);
    await tester.tap(clearProofResult);
    await tester.pump();
    expect(find.text('No result on Proof yet.'), findsOneWidget);
    expect(find.byKey(const Key('proof-result-summary')), findsNothing);
    expect(find.textContaining('fake_ui_audit'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'retired product route resolves to Settings without stale cards',
    (WidgetTester tester) async {
      await tester.binding.setSurfaceSize(const Size(1900, 1200));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
      await tester.pump();

      await tapSideSection(tester, 'product_surface');

      expect(find.text('Connections and API keys'), findsOneWidget);
      expect(find.text('Engel Product Surface Hub'), findsNothing);
      expect(find.text('Welcome and Onboarding'), findsNothing);
      expect(
        find.text('Imported Product Routes Now Accounted For'),
        findsNothing,
      );
    },
  );

  testWidgets('retired merge ledger resolves to actionable Proof', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'merge_ledger');

    expect(find.text('Proof'), findsWidgets);
    expect(find.text('Check Engel safely'), findsOneWidget);
    expect(find.text('Run recommended check'), findsOneWidget);
    expect(find.text('Audit System'), findsNothing);
    expect(find.text('Run Full Verifier'), findsNothing);
    expect(find.text('Engel Merge Ledger'), findsNothing);
    expect(find.text('Section Coverage Matrix'), findsNothing);
  });

  testWidgets('surface finder opens the simplified Meeting Room', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'meeting');

    expect(find.byKey(const Key('meeting-page')), findsOneWidget);
    expect(find.text('Read latest order'), findsOneWidget);
    expect(find.byKey(const Key('meeting-order-input')), findsOneWidget);
    expect(find.byKey(const Key('send-meeting-order')), findsOneWidget);
    expect(
      find.text('Describe a task for the Meeting Room workers.'),
      findsOneWidget,
    );
    expect(find.text('Tauri Meeting Room Reference'), findsNothing);
    expect(find.byKey(const Key('meeting-verify-order-flow')), findsNothing);
    await tester.tap(find.byKey(const Key('meeting-advanced-tools')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('meeting-verify-order-flow')), findsOneWidget);
  });

  testWidgets('Tasks page shows the evidence-backed Live Work Events panel', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'tasks');
    await tester.pump();
    await tester.tap(find.byKey(const Key('tasks-advanced-tools')));
    await tester.pumpAndSettle();

    // The Meeting Room now renders REAL work state from receipts (the event
    // stream), not a heartbeat animation.
    expect(find.byKey(const Key('meeting-live-work-panel')), findsOneWidget);
    expect(find.byKey(const Key('meeting-live-work-status')), findsOneWidget);
    expect(find.byKey(const Key('meeting-live-work-refresh')), findsOneWidget);
    expect(find.text('Live Work Events'), findsOneWidget);
  });

  testWidgets('Tasks page shows the governed Self-Upgrade Loop panel', (
    WidgetTester tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1800, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
    await tester.pump();

    await tapSideSection(tester, 'tasks');
    await tester.pump();
    await tester.tap(find.byKey(const Key('tasks-advanced-tools')));
    await tester.pumpAndSettle();

    // The governed self-upgrade loop (cycles -> quorum -> apply -> post-deploy
    // gate -> lesson) plus provider pipes and self-model freshness are visible
    // as receipt-backed state in the UI (Conical goal: durable proof through
    // the Engel AI Main user interface).
    expect(find.byKey(const Key('self-upgrade-loop-panel')), findsOneWidget);
    expect(find.byKey(const Key('self-upgrade-loop-status')), findsOneWidget);
    expect(find.byKey(const Key('self-upgrade-loop-refresh')), findsOneWidget);
    expect(find.byKey(const Key('self-upgrade-request-input')), findsOneWidget);
    expect(find.byKey(const Key('self-upgrade-plan-local')), findsOneWidget);
    expect(find.byKey(const Key('self-upgrade-run-review')), findsOneWidget);
    expect(
      find.byKey(const Key('self-upgrade-apply-approved')),
      findsOneWidget,
    );
    expect(find.text('Self-Upgrade Loop (governed)'), findsOneWidget);
  });
}
