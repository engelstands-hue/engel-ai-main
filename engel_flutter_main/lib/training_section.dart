part of 'main.dart';

// ============================================================================
// Engel Training section
//
// Everything behind the Training window: the prompt-training run lifecycle
// (launch wrapper, sentinel, progress log, session receipt), the curriculum
// picker, model-training receipts, and the Training page widgets. The code
// lives in _EngelTrainingSection, an abstract superclass of the shell state;
// members the shell owns are declared abstract at the top of the class.
// ============================================================================

class EngelTrainingProcessHandle {
  const EngelTrainingProcessHandle({
    required this.pid,
    required this.exitCode,
    required this.stopTree,
  });

  final int pid;
  final Future<int> exitCode;
  final Future<bool> Function() stopTree;
}

typedef EngelTrainingProcessStarter =
    Future<EngelTrainingProcessHandle> Function(
      String executable,
      List<String> arguments, {
      String? workingDirectory,
    });

Future<EngelTrainingProcessHandle> defaultTrainingProcessStarter(
  String executable,
  List<String> arguments, {
  String? workingDirectory,
}) async {
  final process = await Process.start(
    executable,
    arguments,
    workingDirectory: workingDirectory,
    mode: ProcessStartMode.normal,
  );
  unawaited(process.stdout.drain<void>());
  unawaited(process.stderr.drain<void>());
  return EngelTrainingProcessHandle(
    pid: process.pid,
    exitCode: process.exitCode,
    stopTree: () async {
      if (!Platform.isWindows) return process.kill();
      try {
        final result = await Process.run('taskkill.exe', [
          '/PID',
          '${process.pid}',
          '/T',
          '/F',
        ]);
        if (result.exitCode == 0) return true;
        return process.kill();
      } catch (_) {
        return process.kill();
      }
    },
  );
}

class EngelTrainingCycleRuntimeBudget {
  const EngelTrainingCycleRuntimeBudget({
    required this.wholeCycleDeadline,
    required this.terminationGrace,
  });

  final Duration wholeCycleDeadline;
  final Duration terminationGrace;

  Duration get clientDeadline => wholeCycleDeadline + terminationGrace;
}

String normalizeEngelModelTrainingTargets(String value) {
  final targets = value
      .split(',')
      .map((item) => item.trim().toLowerCase())
      .where((item) => item.isNotEmpty)
      .toSet();
  if (targets.isEmpty ||
      targets.length > 2 ||
      targets.any((item) => item != 'slm' && item != 'llm')) {
    throw const FormatException('Model-training targets are invalid.');
  }
  return <String>[
    if (targets.contains('slm')) 'slm',
    if (targets.contains('llm')) 'llm',
  ].join(',');
}

EngelTrainingCycleRuntimeBudget parseEngelTrainingCycleRuntimeBudget(
  String contents,
  String trainingTargets,
) {
  const schema = 'engel_training_cycle_runtime_contract_v1';
  const expectedKeys = <String>{
    'schema',
    'termination_grace_seconds',
    'whole_cycle.slm',
    'whole_cycle.llm',
    'whole_cycle.slm_llm',
    'slm.dataset',
    'slm.train',
    'slm.verify',
    'llm.dataset',
    'llm.preflight',
    'llm.train_and_evaluate',
  };
  final values = <String, String>{};
  final lines = contents.split(RegExp(r'\r?\n'));
  for (var index = 0; index < lines.length; index++) {
    final line = lines[index].trim();
    if (line.isEmpty || line.startsWith('#')) continue;
    final separator = line.indexOf('=');
    if (separator <= 0 || separator == line.length - 1) {
      throw FormatException(
        'Malformed model-training runtime contract line ${index + 1}.',
      );
    }
    final key = line.substring(0, separator).trim();
    final value = line.substring(separator + 1).trim();
    if (key.isEmpty || value.isEmpty || values.containsKey(key)) {
      throw FormatException(
        'Invalid or duplicate model-training runtime key at line ${index + 1}.',
      );
    }
    values[key] = value;
  }
  if (values.length != expectedKeys.length ||
      !expectedKeys.every(values.containsKey) ||
      values['schema'] != schema) {
    throw const FormatException(
      'Model-training runtime contract keys or schema are invalid.',
    );
  }
  final canonicalTargets = normalizeEngelModelTrainingTargets(trainingTargets);
  final targets = canonicalTargets.split(',').toSet();
  int positiveSeconds(String key, {int maximum = 7 * 24 * 60 * 60}) {
    final parsed = int.tryParse(values[key] ?? '');
    if (parsed == null || parsed <= 0 || parsed > maximum) {
      throw FormatException('$key is outside its reviewed seconds range.');
    }
    return parsed;
  }

  final slmSteps =
      positiveSeconds('slm.dataset') +
      positiveSeconds('slm.train') +
      positiveSeconds('slm.verify');
  final llmSteps =
      positiveSeconds('llm.dataset') +
      positiveSeconds('llm.preflight') +
      positiveSeconds('llm.train_and_evaluate');
  final slmDeadline = positiveSeconds('whole_cycle.slm');
  final llmDeadline = positiveSeconds('whole_cycle.llm');
  final bothDeadline = positiveSeconds('whole_cycle.slm_llm');
  if (slmDeadline < slmSteps ||
      llmDeadline < llmSteps ||
      bothDeadline < slmSteps + llmSteps) {
    throw const FormatException(
      'Whole-cycle deadline is shorter than its bounded model steps.',
    );
  }
  final deadlineSeconds = targets.length == 2
      ? bothDeadline
      : targets.contains('slm')
      ? slmDeadline
      : llmDeadline;
  return EngelTrainingCycleRuntimeBudget(
    wholeCycleDeadline: Duration(seconds: deadlineSeconds),
    terminationGrace: Duration(
      seconds: positiveSeconds('termination_grace_seconds', maximum: 60 * 60),
    ),
  );
}

Duration parseEngelTrainingCycleRuntimeDeadline(
  String contents,
  String trainingTargets,
) {
  return parseEngelTrainingCycleRuntimeBudget(
    contents,
    trainingTargets,
  ).clientDeadline;
}

abstract class _EngelTrainingSection extends State<EngelMainShell> {
  // --- Shell contract: members owned by _EngelMainShellState that the ---
  // --- training section uses. The implementations stay in the shell.  ---
  abstract bool _running;
  abstract bool _chatRunning;
  abstract String _lastCommand;

  set _status(String value);

  set _output(String value);

  EngelProcessRunner get _processRunner;

  Future<void> _saveUiPreferences();

  Future<void> _revealFileInExplorer(String path);

  Future<File?> _findStandaloneChatPython();

  String _pretty(String text);

  Widget _macToolPanel({
    required String title,
    required IconData icon,
    required Widget child,
    Key? key,
  });

  Widget _macSettingLine({
    required String label,
    required String value,
    required IconData icon,
  });

  Widget _busyNotice(String keyName, String message);

  Widget _outputPanel();

  // --- Training state ---
  var _trainingAssetStatus = 'not synced';
  // The asset manifest has two kinds of truth: the shared file inventory and
  // per-curriculum provenance. A stale binding for one curriculum must not
  // make every other valid curriculum look missing, while a problem that names
  // the selected curriculum must still stop its launch.
  var _trainingManifestProblems = <String>[];
  var _trainingManifestSchemaOk = false;
  var _trainingManifestBindings = <Map<String, dynamic>>[];
  var _trainingPromptTemplateCount = 0;
  var _trainingHourlyCycleCount = 0;
  var _trainingMaximumPromptCount = 0;
  var _trainingMissingCount = 0;
  var _trainingMissingAssets = <String>[];
  var _trainingLastLog = '';
  // Curriculum picker: every template materialized by sync_engel_training_assets.py
  // (curricula_index.json). The selected curriculum drives the displayed counts and
  // is threaded into the launch via the wrapper's -Template param.
  var _trainingCurricula = <Map<String, dynamic>>[];
  var _selectedCurriculumId = '';
  var _preferredCurriculumId = '';
  var _selectedCurriculumTemplatePath = trainingMixedTemplatePath;
  // Ladder raised 2026-08-08 ("expert is the new low"): Expert is the floor and three
  // senior tiers sit above it. The slug sent to the runner is the lowercased label;
  // legacy saved levels (low/medium/high) resolve to index -1 downstream and clamp to
  // Expert, and the runner clamps them the same way.
  static const _trainingLevelLabels = <String>[
    'Expert',
    'Principal',
    'Distinguished',
    'Fellow',
  ];
  var _trainingHours = 1;
  var _trainingLevelIndex = 0;
  var _trainingsPerHour = 6;
  var _trainSlmTarget = true;
  var _trainLlmTarget = true;
  var _trainingConfirming = false;
  var _trainingStarting = false;
  var _trainingStopping = false;
  var _trainingRunActive = false;
  var _trainingRunIsPrevious = false;
  var _trainingRunNeedsRecovery = false;
  var _trainingRunStatus = 'No training is running';
  var _trainingRunDetail =
      'Choose a duration, training level, and trainings per hour.';
  var _trainingCompletedPrompts = 0;
  var _trainingRequestedPrompts = 0;
  var _trainingPackRows = 0;
  var _trainingPackAdmitted = 0;
  var _trainingPackRejected = 0;
  var _trainingResumeStartIndex = 0;
  var _trainingResumeRemainingPrompts = 0;
  var _trainingResumeHours = 0;
  var _trainingResumeLevel = '';
  var _trainingResumeTargets = '';
  var _trainingResumePerHour = 0;
  var _trainingResumeTemplatePath = '';
  var _trainingResumeTemplateCycle = 0;
  var _trainingResumeRequiresNewMaterial = false;
  int? _trainingSecondsToNextPrompt;
  int? _trainingSecondsRemaining;
  var _trainingRunStatusRefreshing = false;
  var _trainingRunStatusRefreshQueued = false;
  // The 3-second poll must not rename the button. Only a press shows
  // "Refreshing…"; otherwise the label flashes off and on forever.
  var _trainingRunStatusRefreshShowsBusy = false;
  var _trainingRunStatusUserRefreshPending = false;
  DateTime? _trainingRunStatusCheckedAt;
  var _trainingRunStatusCheckError = '';
  EngelTrainingProcessHandle? _trainingProcess;
  Timer? _trainingRunStatusTimer;
  // Run-identity and liveness guards. The status poll must never attribute a
  // previous run's receipts or log events to the run on screen, and must not
  // believe a RUNNING sentinel whose launcher process is gone.
  DateTime? _trainingProcessStartedAt;
  var _trainingCountsRunKey = '';
  DateTime? _trainingLauncherPidCheckedAt;
  int? _trainingLauncherPidChecked;
  var _trainingLauncherPidAlive = true;
  var _trainingLogSilentPolls = 0;
  // Model Training panel. Prompt training only PRACTISED until the real
  // training cycle existed, so this panel reports receipts rather than live
  // state: a missing receipt means that step never ran, and is shown as such
  // instead of as a confident zero.
  Map<String, dynamic>? _modelTrainingCycle;
  Map<String, dynamic>? _modelTrainingPack;
  Map<String, dynamic>? _modelTrainingSlmMirror;
  var _modelTrainingAllPackFiles = 0;
  var _modelTrainingAllPackRows = 0;
  var _modelTrainingAllPackAdmitted = 0;
  var _modelTrainingAllPackRejected = 0;
  var _modelTrainingAdmissionMinimum = 40;
  var _modelTrainingReceiptsRefreshing = false;
  DateTime? _modelTrainingReceiptsCheckedAt;
  var _modelTrainingCycleResult = '';
  var _modelTrainingCycleResultIsError = false;
  EngelTrainingProcessHandle? _modelTrainingCycleProcess;
  Timer? _modelTrainingCycleDeadline;
  Future<bool>? _modelTrainingCycleStopFuture;

  Future<bool> _stopModelTrainingCycleTreeOnce(
    EngelTrainingProcessHandle process,
  ) {
    final existing = _modelTrainingCycleStopFuture;
    if (existing != null) return existing;
    final stopFuture = process.stopTree();
    _modelTrainingCycleStopFuture = stopFuture;
    return stopFuture;
  }

  Future<bool> _enforceModelTrainingDeadline(
    EngelTrainingProcessHandle process,
    EngelTrainingCycleRuntimeBudget budget,
  ) async {
    if (!mounted || !identical(_modelTrainingCycleProcess, process)) {
      return false;
    }
    final deadlineLabel = _formatTrainingTime(
      budget.wholeCycleDeadline.inSeconds,
    );
    setState(() {
      _status = 'model training deadline reached; stopping';
      _modelTrainingCycleResult =
          'The reviewed $deadlineLabel cycle deadline plus termination grace '
          'was exhausted. Stopping owned process tree PID ${process.pid}...';
      _modelTrainingCycleResultIsError = true;
    });

    var stopRequested = false;
    Object? stopError;
    try {
      stopRequested = await _stopModelTrainingCycleTreeOnce(process);
    } catch (error) {
      stopError = error;
    }
    if (!stopRequested) {
      if (mounted && identical(_modelTrainingCycleProcess, process)) {
        setState(() {
          _status = 'CRITICAL: model training termination unconfirmed';
          _modelTrainingCycleResult =
              'Windows did not confirm a stop request for model-training PID '
              '${process.pid}. It may still be running. Do not start another '
              'cycle; review Task Manager and the run log.'
              '${stopError == null ? '' : ' Stop error: $stopError'}';
          _modelTrainingCycleResultIsError = true;
        });
      }
      return false;
    }

    try {
      await process.exitCode.timeout(budget.terminationGrace);
    } on TimeoutException {
      if (mounted && identical(_modelTrainingCycleProcess, process)) {
        setState(() {
          _status = 'CRITICAL: model training termination unconfirmed';
          _modelTrainingCycleResult =
              'A stop was requested for model-training PID ${process.pid}, but '
              'it did not exit within the reviewed termination grace. It may '
              'still be running. Do not start another cycle.';
          _modelTrainingCycleResultIsError = true;
        });
      }
      return false;
    } catch (error) {
      if (mounted && identical(_modelTrainingCycleProcess, process)) {
        setState(() {
          _status = 'CRITICAL: model training termination unconfirmed';
          _modelTrainingCycleResult =
              'Model-training PID ${process.pid} returned an unreadable exit '
              'result after its stop request: $error. Treat it as running.';
          _modelTrainingCycleResultIsError = true;
        });
      }
      return false;
    }

    if (mounted && identical(_modelTrainingCycleProcess, process)) {
      setState(() {
        _status = 'model training stopped at runtime limit';
        _modelTrainingCycleResult =
            'The cycle exceeded its reviewed runtime and owned process PID '
            '${process.pid} exited after the process-tree stop. Its log and '
            'any partial receipt are on disk.';
        _modelTrainingCycleResultIsError = true;
      });
    }
    return true;
  }

  void _disposeModelTrainingCycleGuard() {
    _modelTrainingCycleDeadline?.cancel();
    _modelTrainingCycleDeadline = null;
    final process = _modelTrainingCycleProcess;
    _modelTrainingCycleProcess = null;
    if (process == null) {
      _modelTrainingCycleStopFuture = null;
      return;
    }
    final stopFuture = _modelTrainingCycleStopFuture ?? process.stopTree();
    _modelTrainingCycleStopFuture = stopFuture;

    Future<void> reportStopFailure() async {
      try {
        if (!await stopFuture) {
          debugPrint(
            'Engel could not confirm model-training process-tree stop during '
            'application disposal (PID ${process.pid}).',
          );
        }
      } catch (error) {
        debugPrint(
          'Engel model-training process-tree stop threw during application '
          'disposal (PID ${process.pid}): $error',
        );
      }
    }

    unawaited(reportStopFailure());
  }

  // --- Training derived values and helpers ---
  EngelTrainingProcessStarter get _trainingProcessStarter =>
      widget.trainingProcessStarter ?? defaultTrainingProcessStarter;

  String get _resolvedTrainingAssetsManifestPath =>
      widget.trainingAssetsManifestPathOverride ?? trainingAssetsManifestPath;

  String get _resolvedTrainingCurriculaIndexPath =>
      widget.trainingCurriculaIndexPathOverride ?? trainingCurriculaIndexPath;

  // Test and recovery fixtures intentionally provide a small curriculum index
  // without the production manifest's five binding receipts. The shipped app
  // always uses both canonical files, so only that path takes the strict
  // binding gate below; fixture-driven UI tests keep their existing contract.
  bool get _trainingUsesCanonicalCatalog =>
      widget.trainingAssetsManifestPathOverride == null &&
      widget.trainingCurriculaIndexPathOverride == null;

  String get _resolvedTrainingActiveSentinelPath =>
      widget.trainingActiveSentinelPathOverride ?? trainingActiveSentinelPath;

  String get _resolvedTrainingSessionReceiptPath =>
      widget.trainingSessionReceiptPathOverride ?? trainingSessionReceiptPath;

  String get _resolvedTrainingPromptReservationsPath =>
      widget.trainingPromptReservationsPathOverride ??
      trainingPromptReservationsPath;

  String get _resolvedModelTrainingRuntimeContractPath {
    final script = File(widget.realTrainingCycleScriptPath);
    return '${script.parent.path}${Platform.pathSeparator}'
        'engel_training_cycle_runtime_contract.contract';
  }

  Future<EngelTrainingCycleRuntimeBudget> _readModelTrainingRuntimeBudget(
    String trainingTargets,
  ) async {
    final contract = File(_resolvedModelTrainingRuntimeContractPath);
    if (!await contract.exists()) {
      throw StateError(
        'Model-training runtime contract is missing: ${contract.path}',
      );
    }
    return parseEngelTrainingCycleRuntimeBudget(
      await contract.readAsString(),
      trainingTargets,
    );
  }

  Future<({Set<int> positions, List<String> problems})>
  _readPromptUseReservationsForRun(String runId) async {
    final positions = <int>{};
    final problems = <String>[];
    final directory = Directory(_resolvedTrainingPromptReservationsPath);
    if (!await directory.exists()) {
      return (positions: positions, problems: problems);
    }
    try {
      final directoryType = await FileSystemEntity.type(
        directory.path,
        followLinks: false,
      );
      if (directoryType != FileSystemEntityType.directory) {
        return (
          positions: positions,
          problems: ['prompt-use reservation path is not a real directory'],
        );
      }
      final entries = await directory
          .list(followLinks: false)
          .where(
            (entry) =>
                entry.path.toLowerCase().endsWith('.json') &&
                entry.uri.pathSegments.last.startsWith(
                  'ENGEL_PROMPT_USE_RESERVATION_',
                ),
          )
          .toList();
      entries.sort((left, right) => left.path.compareTo(right.path));
      for (final entry in entries) {
        if (await FileSystemEntity.type(entry.path, followLinks: false) !=
            FileSystemEntityType.file) {
          problems.add('reservation is not a regular file: ${entry.path}');
          continue;
        }
        try {
          final decoded = jsonDecode(await File(entry.path).readAsString());
          if (decoded is! Map) {
            problems.add('reservation is not a JSON object: ${entry.path}');
            continue;
          }
          final reservation = Map<String, dynamic>.from(decoded);
          final reservationRunId = '${reservation['run_id'] ?? ''}'.trim();
          final position = int.tryParse(
            '${reservation['prompt_position'] ?? ''}',
          );
          final basePromptHash = '${reservation['base_prompt_sha256'] ?? ''}'
              .trim();
          final reservationId = '${reservation['reservation_id'] ?? ''}'.trim();
          final fileName = entry.uri.pathSegments.last;
          final claim = reservation['prompt_run_claim'];
          final claimMap = claim is Map
              ? Map<String, dynamic>.from(claim)
              : const <String, dynamic>{};
          final claimOwnerPid = int.tryParse('${claimMap['owner_pid'] ?? ''}');
          final hashBindings = <String>[
            'history_snapshot_sha256',
            'history_pack_snapshot_sha256',
            'history_reservation_snapshot_sha256',
            'planned_prompt_set_sha256',
          ];
          final valid =
              reservation['schema'] == 'engel_prompt_use_reservation_v1' &&
              RegExp(r'^[0-9a-f]{64}$').hasMatch(reservationId) &&
              fileName == 'ENGEL_PROMPT_USE_RESERVATION_$reservationId.json' &&
              reservationRunId.isNotEmpty &&
              position != null &&
              position >= 1 &&
              '${reservation['base_prompt'] ?? ''}'.trim().isNotEmpty &&
              RegExp(r'^[0-9a-fA-F]{64}$').hasMatch(basePromptHash) &&
              reservation['base_prompt_hash_canonicalization'] ==
                  'unicode_nfkc_casefold_collapsed_whitespace_v1' &&
              '${reservation['created_at_utc'] ?? ''}'.trim().isNotEmpty &&
              claimMap['run_id'] == reservationRunId &&
              claimOwnerPid != null &&
              claimOwnerPid > 0 &&
              '${claimMap['claim_path'] ?? ''}'.trim().isNotEmpty &&
              hashBindings.every(
                (key) => RegExp(
                  r'^[0-9a-fA-F]{64}$',
                ).hasMatch('${reservation[key] ?? ''}'),
              );
          if (!valid) {
            problems.add('invalid prompt-use reservation: ${entry.path}');
            continue;
          }
          if (reservationRunId == runId && !positions.add(position)) {
            problems.add(
              'prompt $position has duplicate reservations for run $runId',
            );
          }
        } catch (_) {
          problems.add('unreadable prompt-use reservation: ${entry.path}');
        }
      }
    } catch (_) {
      problems.add('prompt-use reservation history could not be read');
    }
    return (positions: positions, problems: problems);
  }

  String get _trainingLevelLabel =>
      _trainingLevelLabels[math.min(
        _trainingLevelLabels.length - 1,
        math.max(0, _trainingLevelIndex),
      )];

  String get _trainingLevelSlug => _trainingLevelLabel.toLowerCase();

  String get _trainingTargetsSlug =>
      [if (_trainSlmTarget) 'slm', if (_trainLlmTarget) 'llm'].join(',');

  String get _trainingTargetsLabel {
    if (_trainSlmTarget && _trainLlmTarget) {
      return 'SLM roster + local LLM adapter';
    }
    if (_trainSlmTarget) {
      return 'SLM roster';
    }
    if (_trainLlmTarget) {
      return 'Local LLM adapter';
    }
    return 'No model selected';
  }

  bool get _trainingControlsLocked =>
      _trainingConfirming ||
      _trainingStarting ||
      _trainingStopping ||
      _trainingProcess != null ||
      _trainingRunActive;

  String _trainingHourLabel([int? hours]) {
    final value = hours ?? _trainingHours;
    return value == 1 ? '1 hour' : '$value hours';
  }

  String _trainingLevelDescriptionForIndex(int index) => switch (index) {
    0 => 'Deep synthesis, tradeoffs, and adversarial verification',
    1 => 'Cross-system design: second-order effects, blast radius, rollback',
    2 => 'Adversarial self-refutation: strongest counter-case, falsification',
    _ => 'First-principles derivation that leaves a reusable invariant',
  };

  String get _trainingLevelDescription =>
      _trainingLevelDescriptionForIndex(_trainingLevelIndex);

  String get _trainingsPerHourLabel => '$_trainingsPerHour per hour';

  String _trainingsPerHourSemanticLabel([int? trainingsPerHour]) {
    final value = trainingsPerHour ?? _trainingsPerHour;
    return value == 1 ? '1 training per hour' : '$value trainings per hour';
  }

  String get _trainingCadenceSummary {
    final cadenceMinutes = 60 / _trainingsPerHour;
    final cadenceLabel = cadenceMinutes == cadenceMinutes.roundToDouble()
        ? '${cadenceMinutes.round()}'
        : cadenceMinutes.toStringAsFixed(1);
    return _trainingsPerHour == 1
        ? 'about one each hour'
        : 'about one every $cadenceLabel minutes';
  }

  String get _trainingPlanSummary {
    final total = _trainingHours * _trainingsPerHour;
    final trainingLabel = total == 1 ? 'training' : 'trainings';
    return '$total $trainingLabel over ${_trainingHourLabel()} · '
        '$_trainingLevelLabel depth · $_trainingCadenceSummary';
  }

  Map<String, dynamic> get _selectedTrainingCurriculum =>
      _trainingCurricula.firstWhere(
        (curriculum) => '${curriculum['id']}' == _selectedCurriculumId,
        orElse: () => <String, dynamic>{},
      );

  int _curriculumMaximumHours(Map<String, dynamic> curriculum) {
    if (curriculum.isEmpty) return 8;
    final explicit = int.tryParse('${curriculum['maximum_hours'] ?? ''}');
    final novel = int.tryParse('${curriculum['novel_hours_available'] ?? ''}');
    final topics = int.tryParse('${curriculum['topic_count'] ?? ''}');
    final materialHours = explicit ?? topics ?? 8;
    final available = novel == null
        ? materialHours
        : math.min(materialHours, novel);
    // Exhausted curricula are disabled separately. Keep Slider's numeric
    // contract valid while the chip explains why it cannot start.
    return available.clamp(1, 8).toInt();
  }

  /// Titles of curricula whose material is fully used, for the honest one-liner
  /// under the picker; they are no longer offered as choices.
  List<String> get _spentCurriculumNames => _trainingCurricula
      .where((curriculum) => !_curriculumNoveltyReady(curriculum))
      .map((curriculum) => '${curriculum['title'] ?? curriculum['id']}'.trim())
      .where((title) => title.isNotEmpty)
      .toList(growable: false);

  bool _curriculumNoveltyReady(Map<String, dynamic> curriculum) =>
      curriculum['novelty_ready'] != false;

  bool _selectedCurriculumHasManifestProblem(Map<String, dynamic> curriculum) {
    if (curriculum.isEmpty || _trainingManifestProblems.isEmpty) return false;
    final identifiers = <String>{
      '${curriculum['id'] ?? ''}'.trim().toLowerCase(),
      '${curriculum['title'] ?? ''}'.trim().toLowerCase(),
      '${curriculum['discipline'] ?? ''}'.trim().toLowerCase(),
      '${curriculum['generated_source_id'] ?? ''}'.trim().toLowerCase(),
      '${curriculum['generated_adoption_receipt'] ?? ''}'.trim().toLowerCase(),
    }..removeWhere((value) => value.isEmpty);
    for (final rawProblem in _trainingManifestProblems) {
      final problem = rawProblem.trim().toLowerCase();
      if (problem.isEmpty) continue;
      if (identifiers.any(problem.contains)) return true;
    }
    return false;
  }

  String _normalizeTrainingPath(String value) {
    var normalized = value.trim().replaceAll('\\', '/');
    while (normalized.length > 1 && normalized.endsWith('/')) {
      normalized = normalized.substring(0, normalized.length - 1);
    }
    return normalized.toLowerCase();
  }

  int? _trainingManifestInt(Object? value) =>
      int.tryParse('${value ?? ''}'.trim());

  /// Mirrors the runner's selected-template binding checks before the user
  /// sees a confirmation dialog. This is deliberately a UI preflight only;
  /// the Python runner repeats the authoritative hash/content checks at launch.
  bool _selectedCurriculumHasBindingProblem(Map<String, dynamic> curriculum) {
    if (curriculum.isEmpty || !_trainingUsesCanonicalCatalog) return false;
    if (!_trainingManifestSchemaOk) return true;
    final id = '${curriculum['id'] ?? ''}'.trim();
    if (id.isEmpty) return true;
    final matches = _trainingManifestBindings
        .where((binding) => '${binding['id'] ?? ''}'.trim() == id)
        .toList(growable: false);
    if (matches.length != 1) return true;
    final binding = matches.single;
    final title = '${curriculum['title'] ?? ''}'.trim();
    final discipline = '${curriculum['discipline'] ?? ''}'.trim();
    final bindingTitle = '${binding['title'] ?? ''}'.trim();
    final bindingDiscipline = '${binding['discipline'] ?? ''}'.trim();
    if (title.isEmpty ||
        discipline.isEmpty ||
        bindingTitle.isEmpty ||
        bindingDiscipline.isEmpty ||
        title != bindingTitle ||
        discipline != bindingDiscipline) {
      return true;
    }
    final curriculumPath = _normalizeTrainingPath(
      '${curriculum['template_path'] ?? ''}',
    );
    final bindingPath = _normalizeTrainingPath(
      '${binding['template_path'] ?? ''}',
    );
    if (curriculumPath.isEmpty ||
        bindingPath.isEmpty ||
        curriculumPath != bindingPath) {
      return true;
    }
    final templateSha = '${binding['template_sha256'] ?? ''}'.trim();
    if (!RegExp(r'^[0-9a-fA-F]{64}$').hasMatch(templateSha)) return true;
    if (_trainingManifestInt(binding['prompt_count']) != 80 ||
        _trainingManifestInt(binding['maximum_hours']) != 8 ||
        _trainingManifestInt(curriculum['prompt_count']) != 80 ||
        _trainingManifestInt(curriculum['maximum_hours']) != 8 ||
        _trainingManifestInt(curriculum['prompt_count']) !=
            _trainingManifestInt(binding['prompt_count']) ||
        _trainingManifestInt(curriculum['maximum_hours']) !=
            _trainingManifestInt(binding['maximum_hours'])) {
      return true;
    }
    final curriculumVersion = '${curriculum['version'] ?? ''}'.trim();
    final bindingVersion = '${binding['version'] ?? ''}'.trim();
    if (curriculumVersion.isEmpty ||
        bindingVersion.isEmpty ||
        curriculumVersion != bindingVersion) {
      return true;
    }
    return false;
  }

  bool get _trainingFilesPresent {
    return _trainingMaximumPromptCount > 0 &&
        _trainingHourlyCycleCount > 0 &&
        _trainingMissingCount == 0 &&
        _trainingManifestSchemaOk &&
        _trainingAssetStatus != 'not synced' &&
        !_trainingAssetStatus.startsWith('manifest unreadable');
  }

  int get _selectedTrainingMaximumHours =>
      _curriculumMaximumHours(_selectedTrainingCurriculum);

  List<String> get _selectedTrainingTopics {
    final topics = _selectedTrainingCurriculum['topics'];
    if (topics is! List) return const <String>[];
    return topics
        .map((topic) => '$topic'.trim())
        .where((topic) => topic.isNotEmpty)
        .toList(growable: false);
  }

  /// The exact first template cycle represented by the curriculum index.
  ///
  /// A fully fresh curriculum can safely fall back to cycle 1 when an older
  /// index omitted this field. A partial curriculum cannot: guessing would
  /// make the confirmation name one topic while the runner trains another.
  int? _curriculumNovelStartCycle(Map<String, dynamic> curriculum) {
    final topics = curriculum['topics'];
    final topicCount = topics is List
        ? topics.where((topic) => '$topic'.trim().isNotEmpty).length
        : 0;
    if (topicCount < 1) return null;
    final explicit = int.tryParse(
      '${curriculum['novel_hours_start_cycle'] ?? ''}',
    );
    if (explicit != null && explicit >= 1 && explicit <= topicCount) {
      return explicit;
    }
    final available = int.tryParse(
      '${curriculum['novel_hours_available'] ?? ''}',
    );
    final complete = int.tryParse(
      '${curriculum['novel_complete_cycle_count'] ?? ''}',
    );
    final fullyReady =
        curriculum['novelty_fully_ready'] == true ||
        (available == topicCount && complete == topicCount);
    return fullyReady ? 1 : null;
  }

  List<String> _curriculumTopicPlan(
    Map<String, dynamic> curriculum,
    int hours,
    int templateCycle,
  ) {
    final rawTopics = curriculum['topics'];
    if (rawTopics is! List || hours < 1) return const <String>[];
    final topics = rawTopics
        .map((topic) => '$topic'.trim())
        .where((topic) => topic.isNotEmpty)
        .toList(growable: false);
    if (topics.isEmpty || templateCycle < 1 || templateCycle > topics.length) {
      return const <String>[];
    }
    return List<String>.generate(
      hours,
      (offset) => topics[(templateCycle - 1 + offset) % topics.length],
      growable: false,
    );
  }

  String get _modelTrainingAdmissionGapSummary {
    final admitGap = math.max(
      0,
      _modelTrainingAdmissionMinimum - _modelTrainingAllPackAdmitted,
    );
    final rejectGap = math.max(
      0,
      _modelTrainingAdmissionMinimum - _modelTrainingAllPackRejected,
    );
    if (_modelTrainingAllPackFiles == 0) {
      return 'No cumulative prompt-pack evidence has been read yet.';
    }
    if (admitGap == 0 && rejectGap == 0) {
      return 'Training Admission has at least $_modelTrainingAdmissionMinimum examples in each class.';
    }
    return 'Training Admission still needs $admitGap admitted and $rejectGap rejected examples. The run can add evidence, but its class balance is not guaranteed.';
  }

  String _friendlyTrainingBlocker(String rawBlocker) {
    final blocker = rawBlocker.trim();
    final normalized = blocker.toLowerCase();
    if (normalized.contains(
      'strict local-only run contains a turn not verified as local llm only',
    )) {
      return 'One completed prompt did not include the required proof that it '
          'used only Engel\'s local model. Engel stopped instead of accepting '
          'an unverified result.';
    }
    if (normalized.contains(
      'ct246 did not stamp every turn as local-only training',
    )) {
      return 'One completed prompt was missing its local-only training stamp. '
          'Engel stopped so an unverified result would not be accepted.';
    }
    if (normalized.contains('stopped after') &&
        normalized.contains('consecutive delivery failures')) {
      return 'Two consecutive prompts did not return a usable chat reply. '
          'Engel stopped safely and kept the completed replies and training pack. '
          'Recovery checks the write-ahead ledger before offering an unused resume point.';
    }
    if (normalized.contains(
      'no local turns produced a domain-eligible training sample',
    )) {
      return 'Replies came back, but none kept the training form '
          '(Confirmed/Proof, Result/Check, or Sourced facts), so nothing '
          'could be captured. Spoken-chat rewrite is now skipped for those '
          'turns. Use Test 3 Prompts, then Review and try again.';
    }
    final meetingRoomMatch = RegExp(
      r'^prompt\s+(\d+)\s+did not complete through Flutter wrapper and Meeting Room$',
      caseSensitive: false,
    ).firstMatch(blocker);
    if (meetingRoomMatch != null) {
      return 'Prompt ${meetingRoomMatch.group(1)} did not finish. '
          'The Flutter chat and Meeting Room handoff did not return the '
          'required completion proof.';
    }
    return blocker.isEmpty
        ? 'The previous run ended with an error. Open its log for details.'
        : 'The previous run reported: $blocker';
  }

  // --- Prompt-training and model-training logic ---
  Future<void> _scanTrainingManifest() async {
    final file = File(_resolvedTrainingAssetsManifestPath);
    if (!file.existsSync()) {
      if (!mounted) return;
      setState(() {
        _trainingAssetStatus = 'not synced';
        _trainingManifestProblems = <String>[];
        _trainingManifestSchemaOk = false;
        _trainingManifestBindings = <Map<String, dynamic>>[];
        _trainingPromptTemplateCount = 0;
        _trainingHourlyCycleCount = 0;
        _trainingMaximumPromptCount = 0;
        _trainingMissingCount = 0;
        _trainingMissingAssets = <String>[];
      });
      return;
    }
    try {
      // Sync read on purpose: this small local file is read during initState
      // and the page's first frame (and the tests' first pump) must already
      // see the manifest counts.
      final parsed = _decodeTrainingJson(file.readAsStringSync());
      if (parsed == null) {
        throw const FormatException('manifest is not a JSON object');
      }
      if (!mounted) return;
      setState(() {
        _trainingAssetStatus = parsed['ok'] == true ? 'synced' : 'needs review';
        final rawBindings = parsed['curriculum_bindings'];
        final bindings = <Map<String, dynamic>>[];
        if (rawBindings is List) {
          for (final entry in rawBindings) {
            if (entry is Map) {
              bindings.add(Map<String, dynamic>.from(entry));
            }
          }
        }
        _trainingManifestSchemaOk =
            parsed['schema'] == 'engel_main_training_assets_manifest_v1' &&
            rawBindings is List &&
            bindings.length == 5 &&
            parsed['missing'] is List &&
            (int.tryParse('${parsed['template_prompt_count'] ?? ''}') ?? 0) >
                0 &&
            (int.tryParse('${parsed['template_hourly_cycle_count'] ?? ''}') ??
                    0) >
                0 &&
            (int.tryParse('${parsed['template_maximum_prompt_count'] ?? ''}') ??
                    0) >
                0;
        _trainingManifestBindings = bindings;
        final rawProblems = parsed['curriculum_problems'];
        _trainingManifestProblems = rawProblems is List
            ? rawProblems
                  .map((entry) => '$entry'.trim())
                  .where((entry) => entry.isNotEmpty)
                  .toList(growable: false)
            : <String>[];
        _trainingPromptTemplateCount =
            int.tryParse('${parsed['template_prompt_count']}') ?? 0;
        _trainingHourlyCycleCount =
            int.tryParse('${parsed['template_hourly_cycle_count']}') ?? 0;
        _trainingMaximumPromptCount =
            int.tryParse('${parsed['template_maximum_prompt_count']}') ?? 0;
        final missing = parsed['missing'];
        _trainingMissingAssets = missing is List
            ? missing
                  .map((entry) => '$entry'.trim())
                  .where((entry) => entry.isNotEmpty)
                  .toList(growable: false)
            : <String>[];
        _trainingMissingCount = _trainingMissingAssets.length;
      });
    } catch (error) {
      // An unreadable manifest is reported as exactly that. It is never
      // converted into a fabricated missing-file count: the count and the
      // name list must stay consistent for the missing-assets notice.
      if (!mounted) return;
      setState(() {
        _trainingManifestProblems = <String>[];
        _trainingManifestSchemaOk = false;
        _trainingManifestBindings = <Map<String, dynamic>>[];
        _trainingAssetStatus = 'manifest unreadable — run Prepare Files';
        _trainingPromptTemplateCount = 0;
        _trainingHourlyCycleCount = 0;
        _trainingMaximumPromptCount = 0;
        _trainingMissingCount = 0;
        _trainingMissingAssets = <String>[];
      });
    }
    await _scanTrainingCurricula();
  }

  Future<void> _scanTrainingCurricula() async {
    final file = File(_resolvedTrainingCurriculaIndexPath);
    if (!file.existsSync()) {
      if (!mounted) return;
      setState(() {
        _trainingCurricula = <Map<String, dynamic>>[];
        _selectedCurriculumId = '';
        _selectedCurriculumTemplatePath = trainingMixedTemplatePath;
      });
      return;
    }
    try {
      // Sync read on purpose — same first-frame contract as the manifest.
      final parsed = _decodeTrainingJson(file.readAsStringSync());
      if (parsed == null) {
        throw const FormatException('curricula index is not a JSON object');
      }
      final raw = parsed['curricula'];
      final list = <Map<String, dynamic>>[];
      if (raw is List) {
        for (final entry in raw) {
          if (entry is Map) list.add(Map<String, dynamic>.from(entry));
        }
      }
      final activeId = '${parsed['active_id'] ?? ''}'.trim();
      var selectedId = _preferredCurriculumId.isNotEmpty
          ? _preferredCurriculumId
          : _selectedCurriculumId;
      final hasSelected = list.any(
        (c) => '${c['id']}' == selectedId && _curriculumNoveltyReady(c),
      );
      if (!hasSelected) {
        selectedId =
            list.any(
              (c) => '${c['id']}' == activeId && _curriculumNoveltyReady(c),
            )
            ? activeId
            : (list.any(_curriculumNoveltyReady)
                  ? '${list.firstWhere(_curriculumNoveltyReady)['id']}'
                  : (list.isNotEmpty ? '${list.first['id']}' : ''));
      }
      if (!mounted) return;
      setState(() {
        _trainingCurricula = list;
        _selectedCurriculumId = selectedId;
        _applySelectedCurriculumCounts();
      });
    } catch (_) {
      // A transient partial write must not wipe the picker and silently move
      // the launch template back to the mixed default: keep the previously
      // loaded curricula (and the user's selection) until a good read lands.
      if (_trainingCurricula.isNotEmpty) return;
      if (!mounted) return;
      setState(() {
        _trainingCurricula = <Map<String, dynamic>>[];
        _selectedCurriculumId = '';
        _selectedCurriculumTemplatePath = trainingMixedTemplatePath;
      });
    }
  }

  // Drives the displayed counts + launch template from the selected curriculum.
  // Call inside setState.
  void _applySelectedCurriculumCounts() {
    final selected = _trainingCurricula.firstWhere(
      (c) => '${c['id']}' == _selectedCurriculumId,
      orElse: () => <String, dynamic>{},
    );
    if (selected.isEmpty) {
      _selectedCurriculumTemplatePath = trainingMixedTemplatePath;
      return;
    }
    final topicCount = int.tryParse('${selected['topic_count']}') ?? 0;
    final promptCount = int.tryParse('${selected['prompt_count']}') ?? 0;
    final path = '${selected['template_path'] ?? ''}'.trim();
    _selectedCurriculumTemplatePath = path.isEmpty
        ? trainingMixedTemplatePath
        : path;
    _trainingHourlyCycleCount = topicCount;
    _trainingPromptTemplateCount = topicCount > 0
        ? (promptCount ~/ topicCount)
        : 0;
    _trainingMaximumPromptCount = promptCount;
    _trainingHours = _trainingHours
        .clamp(1, _curriculumMaximumHours(selected))
        .toInt();
  }

  void _selectCurriculum(String id) {
    if (id == _selectedCurriculumId) return;
    final selected = _trainingCurricula.firstWhere(
      (curriculum) => '${curriculum['id']}' == id,
      orElse: () => <String, dynamic>{},
    );
    if (selected.isEmpty || !_curriculumNoveltyReady(selected)) return;
    if (!mounted) return;
    setState(() {
      _selectedCurriculumId = id;
      _preferredCurriculumId = id;
      _applySelectedCurriculumCounts();
    });
    unawaited(_saveUiPreferences());
  }

  Widget _trainingCurriculumPicker() {
    if (_trainingCurricula.isEmpty) {
      return Container(
        key: const Key('training-curriculum-picker-empty'),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(
          color: const Color(0xff151b27),
          borderRadius: BorderRadius.circular(7),
          border: Border.all(color: const Color(0xff334157)),
        ),
        child: const Text(
          'No curricula found. Run Sync Training Assets to build the '
          'training library.',
          style: TextStyle(color: Color(0xff8ea3bf), fontSize: 12),
        ),
      );
    }
    final selected = _trainingCurricula.firstWhere(
      (c) => '${c['id']}' == _selectedCurriculumId,
      orElse: () => <String, dynamic>{},
    );
    final selectedDetail = '${selected['detail'] ?? ''}'.trim();
    final readyCount = _trainingCurricula.where(_curriculumNoveltyReady).length;
    return Container(
      key: const Key('training-curriculum-picker'),
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xff11161f),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xff334157)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(
                Icons.menu_book_outlined,
                color: Color(0xff00e5ff),
                size: 15,
              ),
              const SizedBox(width: 7),
              Text(
                'Curriculum · $readyCount of ${_trainingCurricula.length} ready',
                style: const TextStyle(
                  color: Color(0xffd8e5f4),
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 7),
          // (2026-08-11) Only curricula that can actually start are offered. A spent
          // one is not a choice -- it was a dead chip that pushed Start below the fold
          // -- so it is named in one honest line underneath instead of taking a slot.
          // Bounded on purpose: the picker grows as material is generated, and an
          // unbounded Wrap pushed Start and Train Selected Models below the fold
          // every time a curriculum was added. Two rows show; the rest scrolls.
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 66),
            child: SingleChildScrollView(
              child: Wrap(
                spacing: 6,
                runSpacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  ..._trainingCurricula
                      .where(_curriculumNoveltyReady)
                      .map(_trainingCurriculumChip),
                  // Flows WITH the chips rather than claiming its own row: a dedicated
                  // line cost more vertical space than the dead chips it replaced and
                  // pushed Start back below the fold.
                  if (_spentCurriculumNames.isNotEmpty)
                    Text(
                      '${_spentCurriculumNames.join(', ')} out of material · '
                      'Prepare Files',
                      key: const Key('training-curricula-out-of-material'),
                      style: const TextStyle(
                        color: Color(0xffffc857),
                        fontSize: 10.5,
                      ),
                    ),
                ],
              ),
            ),
          ),
          if (selectedDetail.isNotEmpty) ...[
            const SizedBox(height: 7),
            Text(
              selectedDetail,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Color(0xff8ea3bf),
                fontSize: 11,
                height: 1.3,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _trainingCurriculumChip(Map<String, dynamic> curriculum) {
    final id = '${curriculum['id'] ?? ''}';
    final title = '${curriculum['title'] ?? id}';
    final prompts = int.tryParse('${curriculum['prompt_count']}') ?? 0;
    final isActive = curriculum['active'] == true;
    final selected = id == _selectedCurriculumId;
    final noveltyReady = _curriculumNoveltyReady(curriculum);
    final noveltyStatus = '${curriculum['novelty_status'] ?? ''}'
        .trim()
        .toUpperCase();
    final partial = noveltyReady && noveltyStatus == 'PARTIAL';
    final freshHours = _curriculumMaximumHours(curriculum);
    final materialHours =
        int.tryParse('${curriculum['maximum_hours'] ?? ''}') ?? 8;
    final promptsPerHour = materialHours > 0
        ? (prompts / materialHours).round()
        : 10;
    final selectablePrompts = partial ? freshHours * promptsPerHour : prompts;
    final noveltyTooltip = !noveltyReady
        ? (noveltyStatus == 'BLOCKED_HISTORY'
              ? '$title: prompt history could not be read, so novelty cannot be '
                    'proven. Review history before training on this material.'
              : '$title: every hour of this material has been used. Choose '
                    'Prepare Files to load reviewed new material.')
        : partial
        ? '$title: $freshHours of $materialHours hours are still novel '
              '($selectablePrompts unused prompts). Engel starts the plan at the '
              'first unused hour.'
        : '$title: all $materialHours hours are novel ($prompts prompts).';
    // Same lock predicate as every other training control: the curriculum
    // must not be switchable behind an open confirm dialog or a busy Engel —
    // the launch reads _selectedCurriculumTemplatePath at start time.
    final disabled = _running || _trainingControlsLocked || !noveltyReady;
    return Tooltip(
      message: noveltyTooltip,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          key: Key('training-curriculum-tile-$id'),
          borderRadius: BorderRadius.circular(20),
          onTap: disabled ? null : () => _selectCurriculum(id),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
            decoration: BoxDecoration(
              color: selected
                  ? const Color(0xff123043)
                  : const Color(0xff151b27),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: selected
                    ? const Color(0xff00e5ff)
                    : const Color(0xff2a3a4f),
                width: selected ? 1.4 : 1.0,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  selected ? Icons.check_circle : Icons.radio_button_unchecked,
                  color: selected
                      ? const Color(0xff00e5ff)
                      : const Color(0xff5c7089),
                  size: 15,
                ),
                const SizedBox(width: 7),
                // The title must be able to shrink: at 200 percent text the
                // longest curriculum name overflowed this chip's Row by 114 px.
                Flexible(
                  child: Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: selected
                          ? const Color(0xffeaf4ff)
                          : const Color(0xffd8e5f4),
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                // Partly-spent material is still runnable, so the count shows the
                // prompts that are actually LEFT rather than calling the whole
                // curriculum used. Keeping it to one number also keeps the picker
                // at two rows, which is what holds Start above the fold.
                Text(
                  noveltyReady ? '$selectablePrompts' : 'USED',
                  style: TextStyle(
                    color: noveltyReady
                        ? (partial
                              ? const Color(0xff5fd0a8)
                              : const Color(0xff7fb7cc))
                        : const Color(0xffffc857),
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (!noveltyReady && noveltyStatus.isNotEmpty) ...[
                  const SizedBox(width: 5),
                  Text(
                    noveltyStatus == 'BLOCKED_HISTORY'
                        ? 'REVIEW HISTORY'
                        : 'PREPARE NEW',
                    style: const TextStyle(
                      color: Color(0xffffc857),
                      fontSize: 8.5,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
                if (isActive) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 5,
                      vertical: 1,
                    ),
                    decoration: BoxDecoration(
                      color: const Color(0xff0f3a2a),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(color: const Color(0xff1f7a55)),
                    ),
                    child: const Text(
                      'DEFAULT',
                      style: TextStyle(
                        color: Color(0xff5fe0a5),
                        fontSize: 8.5,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _setTrainingModelTarget({required bool slm, required bool selected}) {
    final nextSlm = slm ? selected : _trainSlmTarget;
    final nextLlm = slm ? _trainLlmTarget : selected;
    if (!nextSlm && !nextLlm) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Keep at least one trainable model selected.'),
        ),
      );
      return;
    }
    setState(() {
      _trainSlmTarget = nextSlm;
      _trainLlmTarget = nextLlm;
    });
    unawaited(_saveUiPreferences());
  }

  Widget _trainingModelTargetsSelector() {
    final locked = _running || _trainingControlsLocked;
    Widget targetTile({
      required Key key,
      required bool slm,
      required bool value,
      required String title,
      required String detail,
      required IconData icon,
    }) {
      return CheckboxListTile(
        key: key,
        dense: true,
        contentPadding: EdgeInsets.zero,
        controlAffinity: ListTileControlAffinity.leading,
        secondary: Icon(icon, size: 18, color: const Color(0xff7fb7cc)),
        value: value,
        onChanged: locked
            ? null
            : (selected) => _setTrainingModelTarget(
                slm: slm,
                selected: selected ?? value,
              ),
        title: Text(
          title,
          style: const TextStyle(
            color: Color(0xffd8e5f4),
            fontSize: 12.5,
            fontWeight: FontWeight.w800,
          ),
        ),
        subtitle: Text(
          detail,
          style: const TextStyle(
            color: Color(0xff8ea3bf),
            fontSize: 11,
            height: 1.3,
          ),
        ),
      );
    }

    return Container(
      key: const Key('training-model-targets'),
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xff11161f),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xff334157)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(
                Icons.model_training,
                color: Color(0xff00e5ff),
                size: 17,
              ),
              const SizedBox(width: 7),
              const Expanded(
                child: Text(
                  'Models to train',
                  style: TextStyle(
                    color: Color(0xffd8e5f4),
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              // (2026-08-10) The value must be able to shrink: at 200 percent
              // text its intrinsic width overflowed this Row by 114 px.
              Flexible(
                child: Text(
                  _trainingTargetsLabel,
                  key: const Key('training-model-targets-value'),
                  textAlign: TextAlign.right,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xff00e5ff),
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          targetTile(
            key: const Key('training-target-slm'),
            slm: true,
            value: _trainSlmTarget,
            title: 'SLM roster',
            detail:
                'Retrains the active intent, style, reply, and admission heads. Route Governor and Failure Triage stay visible while collecting enough real data.',
            icon: Icons.hub_outlined,
          ),
          targetTile(
            key: const Key('training-target-llm'),
            slm: false,
            value: _trainLlmTarget,
            title: 'Local LLM adapter',
            detail:
                'Trains and evaluates a Qwen2.5 1.5B LoRA adapter on CT246. Exact approval is required; it is never auto-deployed.',
            icon: Icons.psychology_outlined,
          ),
          const Text(
            'Workflow: run Prompt Training to capture reviewed answers, then use Train Selected Models below to update the checked model artifacts.',
            key: Key('training-model-targets-workflow'),
            style: TextStyle(
              color: Color(0xffaeb8cb),
              fontSize: 11,
              height: 1.3,
            ),
          ),
        ],
      ),
    );
  }

  Map<String, dynamic>? _decodeTrainingJson(String text) {
    try {
      final parsed = jsonDecode(text.replaceFirst('\ufeff', ''));
      return parsed is Map ? Map<String, dynamic>.from(parsed) : null;
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>?> _latestTrainingLogEvent(String logPath) async {
    if (logPath.trim().isEmpty) return null;
    final file = File(logPath);
    if (!await file.exists()) return null;
    try {
      final handle = await file.open();
      late final String tail;
      try {
        final length = await handle.length();
        await handle.setPosition(0);
        final prefix = await handle.read(math.min(2, length));
        final utf16Le =
            prefix.length >= 2 && prefix[0] == 0xff && prefix[1] == 0xfe;
        final utf16Be =
            prefix.length >= 2 && prefix[0] == 0xfe && prefix[1] == 0xff;
        var start = math.max(0, length - 1024 * 1024);
        if ((utf16Le || utf16Be) && start.isOdd) start -= 1;
        await handle.setPosition(start);
        final bytes = await handle.read(length - start);
        if (utf16Le || utf16Be) {
          final offset = start == 0 && bytes.length >= 2 ? 2 : 0;
          final codeUnits = <int>[];
          for (var index = offset; index + 1 < bytes.length; index += 2) {
            codeUnits.add(
              utf16Le
                  ? bytes[index] | (bytes[index + 1] << 8)
                  : (bytes[index] << 8) | bytes[index + 1],
            );
          }
          tail = String.fromCharCodes(codeUnits);
        } else {
          tail = utf8.decode(bytes, allowMalformed: true);
        }
      } finally {
        await handle.close();
      }
      final lines = const LineSplitter().convert(tail);
      for (final raw in lines.reversed) {
        final line = raw.trim();
        if (!line.startsWith('{') || !line.endsWith('}')) continue;
        final parsed = _decodeTrainingJson(line);
        if (parsed?['event']?.toString().startsWith('flutter_') == true) {
          return parsed;
        }
      }
    } catch (_) {
      // A growing log may be momentarily locked. The next poll will retry.
    }
    return null;
  }

  Future<void> _refreshTrainingRunStatus({bool userInitiated = false}) async {
    if (_trainingRunStatusRefreshing) {
      // A caller with fresh cause (manual click, process exit) must not be
      // silently dropped because the 3-second poll is mid-flight: queue one
      // trailing refresh instead.
      _trainingRunStatusRefreshQueued = true;
      if (userInitiated) {
        _trainingRunStatusUserRefreshPending = true;
        if (mounted) {
          setState(() => _trainingRunStatusRefreshShowsBusy = true);
        }
      }
      return;
    }
    _trainingRunStatusRefreshing = true;
    _trainingRunStatusCheckError = '';
    final showBusy = userInitiated || _trainingRunStatusUserRefreshPending;
    _trainingRunStatusUserRefreshPending = false;
    if (showBusy && mounted) {
      setState(() => _trainingRunStatusRefreshShowsBusy = true);
    }
    try {
      Map<String, dynamic>? sentinel;
      final sentinelFile = File(_resolvedTrainingActiveSentinelPath);
      if (await sentinelFile.exists()) {
        sentinel = _decodeTrainingJson(await sentinelFile.readAsString());
      }

      final ownsRun = _trainingProcess != null || _trainingStarting;
      final ownedSince = _trainingProcessStartedAt;
      var sentinelStarted = DateTime.tryParse(
        '${sentinel?['started_at_utc'] ?? ''}',
      );
      // A just-started owned run: the artifacts on disk still belong to the
      // previous run until the wrapper rewrites the sentinel. Drop them so the
      // old run's final log event and receipt cannot be misread as this
      // run's status ("Training complete" seconds after pressing start).
      if (ownsRun &&
          ownedSince != null &&
          (sentinelStarted == null || sentinelStarted.isBefore(ownedSince))) {
        sentinel = null;
        sentinelStarted = null;
      }

      var sentinelStatus = (sentinel?['status'] ?? '').toString().toUpperCase();
      final rawExpiry = sentinel?['expires_at_epoch'];
      final expiry = rawExpiry is num
          ? rawExpiry.toDouble()
          : double.tryParse('$rawExpiry') ?? 0;
      var active =
          sentinelStatus == 'RUNNING' &&
          expiry > DateTime.now().millisecondsSinceEpoch / 1000;
      // A RUNNING sentinel from a launcher this app instance does not own is
      // only believed while that launcher process is actually alive. A hard
      // kill cannot update the sentinel, which would otherwise claim an
      // active run until its expiry hours later.
      if (active && !ownsRun) {
        final launcherPid = int.tryParse('${sentinel?['launcher_pid'] ?? ''}');
        if (launcherPid != null &&
            !await _isTrainingLauncherAlive(launcherPid)) {
          _markOrphanedTrainingRunFailed(launcherPid);
          sentinelStatus = 'FAILED';
          active = false;
        }
      }
      if (ownsRun) active = true;

      final logPath = (sentinel?['log'] ?? _trainingLastLog).toString().trim();
      final event = await _latestTrainingLogEvent(logPath);

      Map<String, dynamic>? session;
      final sessionFile = File(_resolvedTrainingSessionReceiptPath);
      if (await sessionFile.exists()) {
        session = _decodeTrainingJson(await sessionFile.readAsString());
      }
      // The wrapper lifecycle deliberately has its own run id. Correlate the
      // Python session only with a Python progress event from the same log.
      final expectedRunId = '${event?['run_id'] ?? ''}'.trim();
      final sessionRunId = '${session?['run_id'] ?? ''}'.trim();
      final staleSession =
          expectedRunId.isNotEmpty &&
          sessionRunId.isNotEmpty &&
          expectedRunId != sessionRunId;
      // While a run is active a session receipt written for an EARLIER run
      // must not feed its progress into the live banner. Without a log event
      // the run ids cannot be compared, so the start timestamps correlate:
      // a session that started before the active run is the previous run's.
      final runStartedAt = ownsRun && ownedSince != null
          ? ownedSince
          : sentinelStarted;
      final sessionStarted = DateTime.tryParse(
        '${session?['started_at_utc'] ?? ''}',
      );
      final sessionPredatesRun =
          active &&
          runStartedAt != null &&
          sessionStarted != null &&
          sessionStarted.isBefore(runStartedAt);
      if (staleSession || sessionPredatesRun) session = null;
      final summary = session?['summary'] is Map
          ? Map<String, dynamic>.from(session!['summary'] as Map)
          : const <String, dynamic>{};
      final blockers = session?['blockers'] is List
          ? List<Object?>.from(session!['blockers'] as List)
          : const <Object?>[];

      // The in-memory counts are only a valid fallback while they describe
      // THIS run. A run key (the run's start time) makes that explicit; when
      // the key changes the stale counts are dropped instead of displayed.
      final runKey = runStartedAt?.toIso8601String() ?? '';
      final priorCountsBelongToRun =
          runKey.isNotEmpty && _trainingCountsRunKey == runKey;
      var completed =
          int.tryParse('${summary['prompts_completed'] ?? ''}') ??
          int.tryParse('${sentinel?['prompts_completed'] ?? ''}') ??
          (active && !priorCountsBelongToRun ? 0 : _trainingCompletedPrompts);
      var requested =
          int.tryParse('${summary['prompts_requested'] ?? ''}') ??
          int.tryParse('${sentinel?['requested_prompts'] ?? ''}') ??
          int.tryParse('${sentinel?['prompts_requested'] ?? ''}') ??
          (active && !priorCountsBelongToRun ? 0 : _trainingRequestedPrompts);
      var packRows =
          int.tryParse('${summary['training_pack_rows'] ?? ''}') ?? 0;
      var packAdmitted =
          int.tryParse('${summary['training_pack_admitted'] ?? ''}') ?? 0;
      var packRejected = math.max(0, packRows - packAdmitted);
      final packError = '${summary['training_pack_error'] ?? ''}'.trim();
      int? secondsToNext;
      int? secondsRemaining;
      var status = _trainingRunStatus;
      var detail = _trainingRunDetail;
      var previousRun = _trainingRunIsPrevious;
      var needsRecovery = _trainingRunNeedsRecovery;
      var resumeStartIndex = 0;
      var resumeRemainingPrompts = 0;
      var resumeHours = 0;
      var resumeLevel = '';
      var resumeTargets = '';
      var resumePerHour = 0;
      var resumeTemplatePath = '';
      var resumeTemplateCycle = 0;
      var resumeRequiresNewMaterial = false;
      if (active) {
        previousRun = false;
        needsRecovery = false;
      }
      if (event != null || !active) _trainingLogSilentPolls = 0;

      if (event != null) {
        requested =
            int.tryParse('${event['requested'] ?? ''}') ??
            int.tryParse('${event['prompts_requested'] ?? ''}') ??
            requested;
        final eventHours =
            int.tryParse('${event['scheduled_hours'] ?? ''}') ?? _trainingHours;
        final eventLevel = (event['training_level'] ?? _trainingLevelSlug)
            .toString();
        final eventLevelLabel = eventLevel.isEmpty
            ? _trainingLevelLabel
            : '${eventLevel[0].toUpperCase()}${eventLevel.substring(1)}';
        final eventTrainingsPerHour =
            int.tryParse('${event['trainings_per_hour'] ?? ''}') ??
            _trainingsPerHour;
        secondsToNext = int.tryParse(
          '${event['seconds_to_next_prompt'] ?? ''}',
        );
        secondsRemaining = int.tryParse(
          '${event['seconds_to_deadline'] ?? ''}',
        );
        switch (event['event']?.toString()) {
          case 'flutter_training_started':
            status = 'Training started';
            detail =
                '$requested prompts scheduled for ${_trainingHourLabel(eventHours)} '
                'at $eventLevelLabel level, $eventTrainingsPerHour per hour.';
          case 'flutter_prompt_started':
            final index = int.tryParse('${event['index'] ?? ''}') ?? 1;
            final position =
                int.tryParse('${event['position'] ?? ''}') ?? index;
            final startIndex =
                int.tryParse('${event['start_index'] ?? ''}') ?? 1;
            completed = math.max(0, position - 1);
            status = startIndex > 1
                ? 'Running plan prompt $index '
                      '${requested > 0 ? '(remaining $position of $requested)' : ''}'
                : 'Running prompt $position'
                      '${requested > 0 ? ' of $requested' : ''}';
            detail = 'Engel is waiting for the visible Chat reply and receipt.';
          case 'flutter_prompt_complete':
            final index = int.tryParse('${event['index'] ?? ''}') ?? 0;
            final position =
                int.tryParse('${event['position'] ?? ''}') ?? index;
            final startIndex =
                int.tryParse('${event['start_index'] ?? ''}') ?? 1;
            final promptStatus = (event['status'] ?? '').toString();
            if (promptStatus == 'DONE') {
              completed = math.max(completed, position);
              status = startIndex > 1
                  ? 'Completed plan prompt $index '
                        '${requested > 0 ? '(remaining $position of $requested)' : ''}'
                  : 'Completed prompt $position'
                        '${requested > 0 ? ' of $requested' : ''}';
              detail = 'The prompt and its proof receipt both completed.';
            } else if (active) {
              // A single failed prompt does NOT end the run: the runner stops only
              // after repeated failures. Reporting one as 'Training failed' made a
              // healthy run read as dead (2026-08-03: a 49/50 run looked stopped
              // at the one prompt that failed).
              status = 'Prompt $index did not pass — training continues';
              detail =
                  'The reply or required proof did not complete for this prompt. '
                  'The run keeps going and stops only after repeated failures. '
                  'Open the log for details.';
            } else {
              status = 'Training failed at prompt $index';
              detail =
                  'The reply or required proof did not complete. Open the log for details.';
            }
          case 'flutter_paced_wait':
            completed =
                int.tryParse('${event['completed_prompts'] ?? ''}') ??
                completed;
            status = 'Training is pacing the next prompt';
            detail = secondsToNext == null
                ? 'The next scheduled prompt is pending.'
                : 'Next prompt in ${_formatTrainingTime(secondsToNext)}.';
          case 'flutter_final_wait':
            completed =
                int.tryParse('${event['completed_prompts'] ?? ''}') ??
                completed;
            status = 'All prompts sent';
            detail = 'Finishing the requested training duration.';
          case 'flutter_training_complete':
            final runStatus = (event['status'] ?? '').toString();
            status = runStatus == 'PASS'
                ? 'Training complete'
                : 'Training failed';
        }
      }

      // Progress events describe the live delivery loop. Once the run is no
      // longer active, the finished session is authoritative: a paced-wait
      // event can legitimately say 30 prompts were sent while only 28 replies
      // passed the DONE/completion gate.
      if (!active && !staleSession && summary.isNotEmpty) {
        completed =
            int.tryParse('${summary['prompts_completed'] ?? ''}') ?? completed;
        requested =
            int.tryParse('${summary['prompts_requested'] ?? ''}') ?? requested;
      }

      if (!active &&
          const {'COMPLETE', 'COMPLETED', 'PASS'}.contains(sentinelStatus)) {
        final missed = requested > 0 ? math.max(0, requested - completed) : 0;
        if (staleSession) {
          status = 'Previous training receipt needs review';
          detail =
              'The latest progress log and session receipt belong to different runs. '
              'Refresh again or open the run log before starting another training.';
          needsRecovery = true;
        } else if (packError.isNotEmpty) {
          status = 'Last training needs review';
          detail =
              'The prompts finished, but Engel could not create the model-training pack. '
              'Open the run log before training models.';
          needsRecovery = true;
        } else if (missed > 0 || packRejected > 0) {
          status = 'Last training completed with exclusions';
          detail = <String>[
            if (requested > 0) '$completed of $requested replies completed',
            if (packRows > 0)
              '$packAdmitted admitted and $packRejected excluded',
            'Review the receipt before training models.',
          ].join(' · ');
          needsRecovery = false;
        } else {
          status = 'Last training completed';
          detail = packRows > 0
              ? 'All $completed replies completed and all $packAdmitted captured samples were admitted.'
              : 'The previous run completed. Its receipts are available.';
          needsRecovery = false;
        }
        previousRun = true;
      } else if (!active && sentinelStatus == 'FAILED') {
        status = 'Last training failed';
        detail = blockers.isNotEmpty
            ? _friendlyTrainingBlocker(blockers.first.toString())
            : 'The previous run ended with an error. Open its log for details.';
        previousRun = true;
        needsRecovery = true;
      } else if (!active && sentinelStatus == 'STOPPED') {
        status = 'Last training stopped';
        detail = 'The previous run was stopped from Engel Main.';
        previousRun = true;
        needsRecovery = false;
      } else if (!active &&
          sentinelStatus == 'RUNNING' &&
          expiry > 0 &&
          expiry <= DateTime.now().millisecondsSinceEpoch / 1000) {
        status = 'Previous training status is stale';
        detail =
            'Engel cannot confirm how the previous run ended because its status '
            'marker expired. Open its log before trying again.';
        previousRun = true;
        needsRecovery = true;
      } else if (active && event == null) {
        _trainingLogSilentPolls += 1;
        status = _trainingStarting
            ? 'Starting training'
            : 'Training is running';
        if (_trainingStarting) {
          detail = 'Waiting for the launcher to write its first receipt.';
        } else if (completed > 0) {
          // Progress has been reported for THIS run before; the log is just
          // quiet or momentarily unreadable. Never claim to be waiting for
          // the first event while showing non-zero progress.
          detail =
              'No new progress event has been read yet; the last reported '
              'progress is shown.';
        } else if (_trainingLogSilentPolls >= 5 && logPath.isNotEmpty) {
          detail =
              'The run is active but no progress event has appeared in its '
              'log yet: $logPath';
        } else {
          detail = 'Waiting for the first progress event.';
        }
      }
      if (!active && status.startsWith('Training failed')) {
        status = 'Last ${status[0].toLowerCase()}${status.substring(1)}';
        previousRun = true;
        needsRecovery = true;
      } else if (!active && status == 'Training complete') {
        status = 'Last training completed';
        previousRun = true;
        needsRecovery = false;
      }
      // A paced run stops after a final streak of transport/delivery failures.
      // Keep the completed pack and continue only after every prompt consumed by
      // the immutable write-ahead ledger. A transport failure does not make a
      // reserved prompt novel again. Legacy receipts without reservation evidence
      // retain their original first-failed-prompt recovery behavior.
      if (!active && sentinelStatus == 'FAILED' && session != null) {
        final stoppedForDelivery = blockers.any((entry) {
          final value = '$entry'.toLowerCase();
          return value.contains('stopped after') &&
              value.contains('consecutive delivery failures');
        });
        final rawResults = session['prompt_results'];
        if (stoppedForDelivery && rawResults is List && rawResults.isNotEmpty) {
          var trailingStart = rawResults.length;
          while (trailingStart > 0) {
            final raw = rawResults[trailingStart - 1];
            final item = raw is Map
                ? Map<String, dynamic>.from(raw)
                : const <String, dynamic>{};
            if ('${item['status'] ?? ''}'.toUpperCase() == 'DONE') break;
            trailingStart--;
          }
          final runStart = int.tryParse('${session['start_index'] ?? ''}') ?? 1;
          final legacyCandidateStart = runStart + trailingStart;
          var candidateStart = legacyCandidateStart;
          final sessionRunId = '${session['run_id'] ?? ''}'.trim();
          final reservationLedger = await _readPromptUseReservationsForRun(
            sessionRunId,
          );
          var malformedReservationEvidence =
              reservationLedger.problems.isNotEmpty;
          final reservedPositions = <int>{...reservationLedger.positions};
          for (final raw in rawResults) {
            final item = raw is Map
                ? Map<String, dynamic>.from(raw)
                : const <String, dynamic>{};
            if (!item.containsKey('prompt_use_reservation')) continue;
            final rawReservation = item['prompt_use_reservation'];
            if (rawReservation is! Map) {
              malformedReservationEvidence = true;
              break;
            }
            final reservation = Map<String, dynamic>.from(rawReservation);
            final position = int.tryParse(
              '${reservation['prompt_position'] ?? ''}',
            );
            final resultPosition = int.tryParse(
              '${item['prompt_index'] ?? item['index'] ?? ''}',
            );
            final reservationHash = '${reservation['base_prompt_sha256'] ?? ''}'
                .trim();
            final validReservation =
                reservation['schema'] == 'engel_prompt_use_reservation_v1' &&
                reservation['immutable'] == true &&
                '${reservation['reservation_id'] ?? ''}'.trim().isNotEmpty &&
                '${reservation['path'] ?? ''}'.trim().isNotEmpty &&
                RegExp(r'^[0-9a-fA-F]{64}$').hasMatch(reservationHash) &&
                '${reservation['run_id'] ?? ''}'.trim() == sessionRunId &&
                position != null &&
                resultPosition != null &&
                position == resultPosition;
            if (!validReservation) {
              malformedReservationEvidence = true;
              break;
            }
            if (!reservedPositions.contains(position)) {
              // The session says this prompt was reserved, but the immutable
              // ledger cannot prove it. Recovery must fail closed.
              malformedReservationEvidence = true;
              break;
            }
          }
          for (final position in reservedPositions) {
            if (position >= legacyCandidateStart) {
              // A resumed plan contains every prompt from StartIndex onward. Move
              // beyond the highest ledger position, including a reservation
              // published just before a crash that never reached prompt_results.
              candidateStart = math.max(candidateStart, position + 1);
            }
          }
          final candidateHours =
              int.tryParse('${session['scheduled_hours'] ?? ''}') ?? 0;
          final candidatePerHour =
              int.tryParse('${session['trainings_per_hour'] ?? ''}') ?? 0;
          final planPrompts = candidateHours * candidatePerHour;
          final candidateLevel = '${session['training_level'] ?? ''}'
              .trim()
              .toLowerCase();
          final candidateTargets = '${session['training_targets'] ?? ''}'
              .trim()
              .toLowerCase();
          final candidateTemplate = '${session['template_path'] ?? ''}'.trim();
          final rawSessionPreflight = session['session_preflight'];
          final sessionPreflight = rawSessionPreflight is Map
              ? Map<String, dynamic>.from(rawSessionPreflight)
              : const <String, dynamic>{};
          final candidateTemplateCycle =
              int.tryParse(
                '${sessionPreflight['template_cycle_effective'] ?? ''}',
              ) ??
              int.tryParse('${session['template_cycle'] ?? ''}') ??
              0;
          if (malformedReservationEvidence) {
            resumeRequiresNewMaterial = true;
            detail =
                'The failed run has incomplete prompt-reservation evidence. '
                'Engel will not risk replaying consumed prompts. Prepare new material.';
          } else if (candidateStart > planPrompts &&
              candidateStart > legacyCandidateStart) {
            resumeRequiresNewMaterial = true;
            detail =
                'The write-ahead ledger already consumed every remaining prompt '
                'in this plan. Prepare new material before training again.';
          } else if (candidateTemplateCycle < 1 || candidateTemplateCycle > 8) {
            resumeRequiresNewMaterial = true;
            detail =
                'The failed run does not prove which template cycle it used. '
                'Engel will not show or launch a guessed topic plan. Prepare new material.';
          } else if (candidateStart >= 1 &&
              candidateStart <= planPrompts &&
              candidateHours >= 1 &&
              candidateHours <= 8 &&
              candidatePerHour >= 1 &&
              candidatePerHour <= 10 &&
              _trainingLevelLabels
                  .map((label) => label.toLowerCase())
                  .contains(candidateLevel) &&
              const {'slm', 'llm', 'slm,llm'}.contains(candidateTargets) &&
              candidateTemplate.isNotEmpty) {
            resumeStartIndex = candidateStart;
            resumeRemainingPrompts = planPrompts - candidateStart + 1;
            resumeHours = candidateHours;
            resumeLevel = candidateLevel;
            resumeTargets = candidateTargets;
            resumePerHour = candidatePerHour;
            resumeTemplatePath = candidateTemplate;
            resumeTemplateCycle = candidateTemplateCycle;
            if (candidateStart > legacyCandidateStart) {
              final skipped = candidateStart - legacyCandidateStart;
              detail =
                  'The write-ahead ledger preserved $skipped attempted '
                  '${skipped == 1 ? 'prompt' : 'prompts'}. Resume starts at '
                  'prompt $candidateStart, the first unused prompt.';
            }
          }
        }
      }
      if (!active) {
        secondsToNext = null;
        secondsRemaining = null;
      }

      if (!mounted) return;
      setState(() {
        _trainingRunStatusCheckedAt = DateTime.now().toUtc();
        _trainingRunStatusCheckError = '';
        _trainingRunActive = active;
        _trainingRunIsPrevious = previousRun;
        _trainingRunNeedsRecovery = needsRecovery;
        _trainingRunStatus = status;
        _trainingRunDetail = detail;
        _trainingCountsRunKey = active ? runKey : '';
        _trainingCompletedPrompts = completed;
        _trainingRequestedPrompts = requested;
        _trainingPackRows = packRows;
        _trainingPackAdmitted = packAdmitted;
        _trainingPackRejected = packRejected;
        _trainingResumeStartIndex = resumeStartIndex;
        _trainingResumeRemainingPrompts = resumeRemainingPrompts;
        _trainingResumeHours = resumeHours;
        _trainingResumeLevel = resumeLevel;
        _trainingResumeTargets = resumeTargets;
        _trainingResumePerHour = resumePerHour;
        _trainingResumeTemplatePath = resumeTemplatePath;
        _trainingResumeTemplateCycle = resumeTemplateCycle;
        _trainingResumeRequiresNewMaterial = resumeRequiresNewMaterial;
        _trainingSecondsToNextPrompt = secondsToNext;
        _trainingSecondsRemaining = secondsRemaining;
        if (logPath.isNotEmpty) _trainingLastLog = logPath;
        if (active && _trainingProcess == null) {
          final restoredHours = int.tryParse(
            '${sentinel?['scheduled_hours'] ?? sentinel?['hours'] ?? ''}',
          );
          final restoredLevel = (sentinel?['training_level'] ?? '')
              .toString()
              .toLowerCase();
          final restoredTrainingsPerHour = int.tryParse(
            '${sentinel?['trainings_per_hour'] ?? ''}',
          );
          if (restoredHours != null &&
              restoredHours >= 1 &&
              restoredHours <= 8) {
            _trainingHours = restoredHours;
          }
          final restoredIndex = _trainingLevelLabels
              .map((label) => label.toLowerCase())
              .toList()
              .indexOf(restoredLevel);
          if (restoredIndex >= 0) _trainingLevelIndex = restoredIndex;
          if (restoredTrainingsPerHour != null &&
              restoredTrainingsPerHour >= 1 &&
              restoredTrainingsPerHour <= 10) {
            _trainingsPerHour = restoredTrainingsPerHour;
          }
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _trainingRunStatusCheckError =
            'Status refresh failed. The last known Training status is still shown; try Refresh Status again.';
      });
    } finally {
      _trainingRunStatusRefreshing = false;
      final runQueued = _trainingRunStatusRefreshQueued;
      final queuedByUser = _trainingRunStatusUserRefreshPending;
      _trainingRunStatusRefreshQueued = false;
      if (!runQueued || !queuedByUser) {
        if (mounted && _trainingRunStatusRefreshShowsBusy) {
          setState(() => _trainingRunStatusRefreshShowsBusy = false);
        } else {
          _trainingRunStatusRefreshShowsBusy = false;
        }
      }
      if (runQueued && mounted) {
        unawaited(_refreshTrainingRunStatus(userInitiated: queuedByUser));
      }
    }
  }

  String _formatTrainingTime(int seconds) {
    final safe = math.max(0, seconds);
    final hours = safe ~/ 3600;
    final minutes = (safe % 3600) ~/ 60;
    if (hours > 0) return '${hours}h ${minutes}m';
    if (minutes > 0) return '${minutes}m';
    return '${safe}s';
  }

  String get _trainingStatusFreshnessLabel {
    final checkedAt = _trainingRunStatusCheckedAt;
    if (checkedAt == null) return 'Run status has not been refreshed yet';
    final age = DateTime.now().toUtc().difference(checkedAt);
    if (age.isNegative || age.inMinutes < 1) {
      return 'Run status checked just now';
    }
    if (age.inHours < 1) {
      return 'Run status checked ${age.inMinutes} '
          '${age.inMinutes == 1 ? 'minute' : 'minutes'} ago';
    }
    return 'Run status checked ${age.inHours} '
        '${age.inHours == 1 ? 'hour' : 'hours'} ago';
  }

  Map<String, String> get _trainingProcessEnvironment => {
    'ENGEL_APP_ROOT': appRoot,
    'TEMP': engelTempRoot,
    'TMP': engelTempRoot,
    'TMPDIR': engelTempRoot,
    'CARGO_HOME': engelCargoHome,
  };

  Future<void> _syncTrainingAssets() async {
    if (_running) return;
    final python = await _findStandaloneChatPython();
    final script = File(trainingAssetSyncScriptPath);
    if (python == null || !await script.exists()) {
      if (!mounted) return;
      setState(() {
        _status = 'training sync unavailable';
        _trainingRunStatus = 'Training files are unavailable';
        _trainingRunDetail =
            'Required local Training files are missing. Review the technical details below.';
        _output = [
          if (python == null)
            'Python missing. Expected $runtimePythonExe or python.exe.',
          if (!script.existsSync())
            'Training sync script missing: $trainingAssetSyncScriptPath',
        ].join('\n');
      });
      return;
    }
    final args = [trainingAssetSyncScriptPath, '--summary'];
    setState(() {
      _running = true;
      _status = 'syncing training assets';
      _trainingRunStatus = 'Preparing Training files';
      _trainingRunDetail =
          'Engel is checking and preparing the local prompt library.';
      _lastCommand = '${python.path} ${args.join(' ')}';
      _output = [
        'Running real command:',
        _lastCommand,
        '',
        'Canonical folder: $trainingCanonicalRoot',
      ].join('\n');
    });
    try {
      final sw = Stopwatch()..start();
      final result = await _processRunner(
        python.path,
        args,
        workingDirectory: appRoot,
        environment: _trainingProcessEnvironment,
      ).timeout(const Duration(seconds: 90));
      sw.stop();
      await _scanTrainingManifest();
      if (!mounted) return;
      final stdoutText = _pretty(result.stdout.toString());
      final stderrText = result.stderr.toString().trim();
      setState(() {
        _output = [
          'Command: $_lastCommand',
          'Exit: ${result.exitCode}',
          'Elapsed: ${sw.elapsedMilliseconds} ms',
          'Canonical folder: $trainingCanonicalRoot',
          'Manifest: $_resolvedTrainingAssetsManifestPath',
          if (stdoutText.isNotEmpty) 'summary json:\n$stdoutText',
          if (stderrText.isNotEmpty) 'stderr:\n$stderrText',
        ].join('\n\n');
        _status = result.exitCode == 0
            ? 'training assets synced'
            : 'training sync exit ${result.exitCode}';
        _trainingRunStatus = result.exitCode == 0
            ? 'Training files are ready'
            : 'Training files need attention';
        _trainingRunDetail = result.exitCode == 0
            ? 'The local prompt library and manifest were prepared successfully.'
            : 'Preparing the Training files exited with code ${result.exitCode}. Review the technical details below.';
      });
    } on TimeoutException {
      if (!mounted) return;
      setState(() {
        _output = 'TIMEOUT after 90s\nCommand: $_lastCommand';
        _status = 'training sync timeout';
        _trainingRunStatus = 'Preparing Training files timed out';
        _trainingRunDetail =
            'The file preparation did not finish within 90 seconds. Try again.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _output = 'ERROR: $error\nCommand: $_lastCommand';
        _status = 'training sync error';
        _trainingRunStatus = 'Could not prepare Training files';
        _trainingRunDetail =
            'Engel could not finish preparing the prompt library. Review the technical details below.';
      });
    } finally {
      if (mounted) {
        setState(() => _running = false);
      }
    }
  }

  Future<void> _runTrainingSmoke() async {
    if (_running) return;
    final python = await _findStandaloneChatPython();
    final runner = File(trainingFlutterPromptRunnerPath);
    final template = File(_selectedCurriculumTemplatePath);
    if (python == null || !await runner.exists() || !await template.exists()) {
      if (!mounted) return;
      setState(() {
        _status = 'training smoke unavailable';
        _trainingRunStatus = 'Three-prompt test is unavailable';
        _trainingRunDetail =
            'Required local Training files are missing. Choose Prepare Files, then try again.';
        _output = [
          if (python == null)
            'Python missing. Expected $runtimePythonExe or python.exe.',
          if (!runner.existsSync())
            'Runner missing: $trainingFlutterPromptRunnerPath',
          if (!template.existsSync())
            'Template missing. Choose Prepare Files first: ${template.path}',
        ].join('\n');
      });
      return;
    }
    final args = [
      trainingFlutterPromptRunnerPath,
      '--mode',
      'smoke',
      // The runner treats --minutes as the wall deadline for the whole smoke.
      // 3 prompts at the 240s per-prompt budget need up to 12 minutes; a
      // 3-minute wall fit only one expert-depth prompt and failed the rest
      // unsent. The outer process timeout below stays at 15 minutes.
      '--minutes',
      '12',
      '--per-prompt-timeout',
      '240',
      '--template',
      _selectedCurriculumTemplatePath,
      '--training-targets',
      _trainingTargetsSlug,
      '--training-level',
      _trainingLevelSlug,
      '--trainings-per-hour',
      '$_trainingsPerHour',
      '--local-only',
      '--fresh-chat',
    ];
    setState(() {
      _running = true;
      _status = 'running training smoke';
      _trainingRunStatus = 'Testing 3 local prompts';
      _trainingRunDetail =
          'Engel is testing three $_trainingLevelLabel prompts from the selected curriculum through the same local-only route.';
      _lastCommand = '${python.path} ${args.join(' ')}';
      _output = 'Running real command:\n$_lastCommand';
    });
    try {
      final sw = Stopwatch()..start();
      final result = await _processRunner(
        python.path,
        args,
        workingDirectory: appRoot,
        environment: _trainingProcessEnvironment,
      ).timeout(const Duration(minutes: 15));
      sw.stop();
      final stdoutText = _pretty(result.stdout.toString());
      final stderrText = result.stderr.toString().trim();
      if (!mounted) return;
      setState(() {
        _output = [
          'Command: $_lastCommand',
          'Exit: ${result.exitCode}',
          'Elapsed: ${sw.elapsedMilliseconds} ms',
          if (stdoutText.isNotEmpty) 'stdout:\n$stdoutText',
          if (stderrText.isNotEmpty) 'stderr:\n$stderrText',
        ].join('\n\n');
        _status = result.exitCode == 0
            ? 'training smoke passed'
            : 'training smoke exit ${result.exitCode}';
        _trainingRunStatus = result.exitCode == 0
            ? 'Three-prompt test passed'
            : 'Three-prompt test failed';
        _trainingRunDetail = result.exitCode == 0
            ? 'All smoke-test prompts returned a successful local-only result.'
            : 'The smoke test exited with code ${result.exitCode}. Review the technical details below.';
      });
    } on TimeoutException {
      if (!mounted) return;
      setState(() {
        _output = 'TIMEOUT after 15m\nCommand: $_lastCommand';
        _status = 'training smoke timeout';
        _trainingRunStatus = 'Three-prompt test timed out';
        _trainingRunDetail =
            'The prompt did not finish within 15 minutes. Try again or review the technical details below.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _output = 'ERROR: $error\nCommand: $_lastCommand';
        _status = 'training smoke error';
        _trainingRunStatus = 'Three-prompt test failed';
        _trainingRunDetail =
            'Engel could not complete the prompt. Review the technical details below.';
      });
    } finally {
      if (mounted) {
        setState(() => _running = false);
      }
    }
  }

  Future<void> _resumeFailedTraining() async {
    if (_trainingResumeStartIndex < 1 ||
        _trainingResumeRemainingPrompts < 1 ||
        _trainingControlsLocked) {
      return;
    }
    final resumeTemplate = _trainingResumeTemplatePath
        .replaceAll('/', '\\')
        .toLowerCase();
    final curriculum = _trainingCurricula.firstWhere(
      (entry) =>
          '${entry['template_path'] ?? ''}'
              .replaceAll('/', '\\')
              .toLowerCase() ==
          resumeTemplate,
      orElse: () => <String, dynamic>{},
    );
    if (curriculum.isEmpty) {
      setState(() {
        _trainingRunStatus = 'Resume files need attention';
        _trainingRunDetail =
            'The original curriculum is not available. Choose Prepare Files, then Refresh Status.';
      });
      return;
    }
    final resumeMaximumHours = _curriculumMaximumHours(curriculum);
    if (_trainingResumeHours > resumeMaximumHours) {
      setState(() {
        _trainingRunStatus = 'Resume plan no longer fits this curriculum';
        _trainingRunDetail =
            'The saved plan requests $_trainingResumeHours hours, but this curriculum has '
            '$resumeMaximumHours distinct ${resumeMaximumHours == 1 ? 'hour' : 'hours'}. '
            'Start a new plan within the available material instead of replaying a cycle.';
      });
      return;
    }
    // Legacy resume receipts may carry low/medium/high; indexOf returns -1 for those
    // and a negative Slider value asserts. Clamp to Expert -- the new floor.
    final levelIndex = _trainingLevelLabels
        .map((label) => label.toLowerCase())
        .toList()
        .indexOf(_trainingResumeLevel);
    final startIndex = _trainingResumeStartIndex;
    setState(() {
      _trainingHours = _trainingResumeHours;
      _trainingLevelIndex = levelIndex < 0 ? 0 : levelIndex;
      _trainingsPerHour = _trainingResumePerHour;
      _trainSlmTarget = _trainingResumeTargets.split(',').contains('slm');
      _trainLlmTarget = _trainingResumeTargets.split(',').contains('llm');
      _selectedCurriculumId = '${curriculum['id']}';
      _applySelectedCurriculumCounts();
    });
    await _confirmHourPromptTraining(startIndex: startIndex);
  }

  Future<void> _confirmHourPromptTraining({int startIndex = 1}) async {
    if (_running || _trainingControlsLocked) return;
    await _scanTrainingManifest();
    await _scanTrainingCurricula();
    if (!mounted) return;
    final hours = _trainingHours;
    final level = _trainingLevelLabel;
    final levelSlug = _trainingLevelSlug;
    final trainingsPerHour = _trainingsPerHour;
    final promptCount = trainingsPerHour * hours;
    final remainingPromptCount = promptCount - startIndex + 1;
    final resume = startIndex > 1;
    final remainingMinutes = math.max(
      1,
      (remainingPromptCount * 60 / trainingsPerHour).ceil(),
    );
    final trainingTargets = _trainingTargetsSlug;
    final trainingTargetsLabel = _trainingTargetsLabel;
    final curriculumLabel = _selectedTrainingCurriculum['title']?.toString();
    final templateCycle = resume
        ? (_trainingResumeTemplateCycle >= 1 &&
                  _trainingResumeTemplateCycle <= _selectedTrainingTopics.length
              ? _trainingResumeTemplateCycle
              : null)
        : _curriculumNovelStartCycle(_selectedTrainingCurriculum);
    final selectedTopics = templateCycle == null
        ? const <String>[]
        : _curriculumTopicPlan(
            _selectedTrainingCurriculum,
            hours,
            templateCycle,
          );
    final maximumHours = _selectedTrainingMaximumHours;
    final launcher = File(
      '$trainingCanonicalRoot\\run_hour_prompt_training.ps1',
    );
    final preflightProblems = <String>[
      // `training_assets_manifest.json` covers all five curriculum slots. A
      // stale generated binding in an unrelated slot must not strand a fresh,
      // independently bound selection; the runner still performs its own
      // canonical binding and novelty checks immediately before delivery.
      if (!_trainingFilesPresent)
        'Training files are not ready (${_trainingAssetStatus.trim()}).',
      if (_trainingMissingCount > 0)
        '$_trainingMissingCount required Training files are missing.',
      if (_trainingCurricula.isEmpty || _selectedCurriculumId.isEmpty)
        'No curriculum is selected.',
      if (!_curriculumNoveltyReady(_selectedTrainingCurriculum))
        'This curriculum has no unused hours left. Choose Prepare Files to load reviewed new material.',
      if (_selectedCurriculumHasManifestProblem(_selectedTrainingCurriculum))
        'The selected curriculum has a provenance issue in the asset manifest. Choose Prepare Files and review the generated binding before training.',
      if (_selectedCurriculumHasBindingProblem(_selectedTrainingCurriculum))
        'The selected curriculum binding is missing or does not match the reviewed manifest. Choose Prepare Files and refresh the Training library before starting.',
      if (templateCycle == null)
        'The curriculum does not provide a valid fresh-material start cycle. Refusing to guess which topics will run.',
      if (!File(_selectedCurriculumTemplatePath).existsSync())
        'The selected curriculum template is missing.',
      // Fresh material is counted in whole hours: a plan longer than what is
      // left would replay consumed prompts and the runner would refuse it.
      if (_curriculumNoveltyReady(_selectedTrainingCurriculum) &&
          hours > maximumHours)
        'This curriculum has $maximumHours fresh '
            '${maximumHours == 1 ? 'hour' : 'hours'} left; choose a shorter '
            'duration or Prepare Files for new material.',
      if (selectedTopics.length < hours)
        'The selected curriculum supports up to $maximumHours '
            '${maximumHours == 1 ? 'hour' : 'hours'}; choose a shorter duration.',
      if (startIndex < 1 || startIndex > promptCount)
        'The resume point is outside the selected training plan.',
      if (!launcher.existsSync()) 'The Training launcher is missing.',
    ];
    if (preflightProblems.isNotEmpty) {
      setState(() {
        _trainingRunIsPrevious = false;
        _trainingRunNeedsRecovery = true;
        _trainingRunStatus = 'Training preflight needs attention';
        _trainingRunDetail =
            '${preflightProblems.first} Choose Prepare Files, then Refresh Status.';
      });
      return;
    }
    final firstResumeHour = (startIndex - 1) ~/ trainingsPerHour;
    final topicPlan = selectedTopics
        .skip(firstResumeHour)
        .toList()
        .asMap()
        .entries
        .map((entry) => '${entry.key + firstResumeHour + 1}. ${entry.value}')
        .join('\n');
    final previousEvidence = _trainingRequestedPrompts > 0
        ? 'Previous run: $_trainingCompletedPrompts/$_trainingRequestedPrompts replies completed'
              '${_trainingPackRows > 0 ? ', $_trainingPackAdmitted admitted, and $_trainingPackRejected excluded.' : '.'}'
        : 'Previous run: no completed prompt-training receipt is loaded.';
    setState(() => _trainingConfirming = true);
    bool? confirmed;
    try {
      confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(
            resume
                ? 'Resume $hours-hour training?'
                : hours == 1
                ? 'Start one-hour training?'
                : 'Start $hours-hour training?',
          ),
          content: SingleChildScrollView(
            child: Text(
              '${resume ? 'This resumes the local-only plan at prompt $startIndex. The prior receipts and pack stay preserved; this continuation writes a new receipt and pack.' : 'This starts a real local-only training run.'}\n\n'
              'Keep Engel Main open and keep this PC awake and unlocked for up to '
              '${resume ? '$remainingMinutes minutes' : '${_trainingHourLabel(hours)} (${hours * 60} minutes)'}.\n\n'
              'Training level: $level\n'
              'Curriculum: ${curriculumLabel ?? 'Selected prompt library'}\n'
              'Trainings per hour: $trainingsPerHour\n'
              'Full plan: $promptCount prompts\n'
              '${resume ? 'Resume point: prompt $startIndex\nPrompts remaining: $remainingPromptCount\n' : ''}'
              'Models collecting evidence: $trainingTargetsLabel\n\n'
              'Step 1 only captures and grades reviewed local answers. It does not update or deploy model weights. After reviewing the receipts, use Train Selected Models as a separate approval-gated step.\n\n'
              'Local-only safety: provider fallback is disabled and each served reply must carry local-model proof.\n\n'
              '$previousEvidence\n'
              'Cumulative packs: $_modelTrainingAllPackAdmitted admitted / $_modelTrainingAllPackRejected rejected.\n'
              '$_modelTrainingAdmissionGapSummary\n\n'
              'Hourly topic plan:\n$topicPlan\n\n'
              'Pacing: The first prompt starts after setup. Later prompts run $_trainingCadenceSummary.\n\n'
              'Receipts and logs:\n$trainingCanonicalRoot\\runs\\ui_prompt',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              key: const Key('confirm-hour-training'),
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: Text(resume ? 'Resume training' : 'Start training'),
            ),
          ],
        ),
      );
    } finally {
      if (mounted) setState(() => _trainingConfirming = false);
    }
    if (confirmed == true && mounted) {
      await _startHourPromptTrainingFromUi(
        hours: hours,
        trainingLevel: levelSlug,
        trainingsPerHour: trainingsPerHour,
        trainingTargets: trainingTargets,
        startIndex: startIndex,
        templateCycle: templateCycle!,
      );
    }
  }

  Future<void> _startHourPromptTrainingFromUi({
    required int hours,
    required String trainingLevel,
    required int trainingsPerHour,
    required String trainingTargets,
    required int templateCycle,
    int startIndex = 1,
  }) async {
    if (_running ||
        _trainingStarting ||
        _trainingProcess != null ||
        _trainingRunActive) {
      return;
    }
    final maximumHours = _selectedTrainingMaximumHours;
    if (hours < 1 ||
        hours > 8 ||
        hours > maximumHours ||
        !_curriculumNoveltyReady(_selectedTrainingCurriculum) ||
        trainingsPerHour < 1 ||
        trainingsPerHour > 10 ||
        templateCycle < 1 ||
        templateCycle > _selectedTrainingTopics.length ||
        startIndex < 1 ||
        startIndex > hours * trainingsPerHour ||
        !_trainingLevelLabels
            .map((label) => label.toLowerCase())
            .contains(trainingLevel) ||
        !const {'slm', 'llm', 'slm,llm'}.contains(trainingTargets)) {
      setState(() {
        _trainingRunIsPrevious = false;
        _trainingRunNeedsRecovery = false;
        _trainingRunStatus = 'Training settings are invalid';
        _trainingRunDetail =
            'Choose 1–$maximumHours ${maximumHours == 1 ? 'hour' : 'hours'} for '
            'this curriculum, Expert through Fellow, and 1–10 trainings per hour.';
      });
      return;
    }
    setState(() {
      _trainingStarting = true;
      // The launch timestamp is the run key: status polling ignores on-disk
      // artifacts older than this so the previous run's sentinel, log, and
      // receipt cannot masquerade as the run being started.
      _trainingProcessStartedAt = DateTime.now().toUtc();
      _trainingCountsRunKey = '';
      _trainingLogSilentPolls = 0;
      _trainingRunIsPrevious = false;
      _trainingRunNeedsRecovery = false;
      _trainingRunStatus = 'Starting training';
      _trainingRunDetail = 'Checking the launcher and active-run guard.';
    });

    final launcher = File(
      '$trainingCanonicalRoot\\run_hour_prompt_training.ps1',
    );
    try {
      final sentinelFile = File(_resolvedTrainingActiveSentinelPath);
      if (sentinelFile.existsSync()) {
        final sentinel = _decodeTrainingJson(sentinelFile.readAsStringSync());
        final status = (sentinel?['status'] ?? '').toString().toUpperCase();
        final rawExpiry = sentinel?['expires_at_epoch'];
        final expiry = rawExpiry is num
            ? rawExpiry.toDouble()
            : double.tryParse('$rawExpiry') ?? 0;
        if (status == 'RUNNING' &&
            expiry > DateTime.now().millisecondsSinceEpoch / 1000) {
          if (!mounted) return;
          setState(() {
            _trainingRunActive = true;
            _trainingRunIsPrevious = false;
            _trainingRunNeedsRecovery = false;
            _trainingRunStatus = 'Training is already running';
            _trainingRunDetail =
                'The active run must finish or stop before another can start.';
          });
          return;
        }
      }
      if (!launcher.existsSync()) {
        if (!mounted) return;
        setState(() {
          _status = 'training launcher missing';
          _trainingRunIsPrevious = false;
          _trainingRunNeedsRecovery = false;
          _trainingRunStatus = 'Training launcher is missing';
          _trainingRunDetail =
              'Run Sync Training Assets, then try the training run again.';
          _output =
              'Training launcher missing. Run Sync Training Assets first:\n${launcher.path}';
        });
        return;
      }

      final args = [
        '-NoProfile',
        '-WindowStyle',
        'Hidden',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        launcher.path,
        '-Hours',
        '$hours',
        '-TrainingLevel',
        trainingLevel,
        '-TrainingTargets',
        trainingTargets,
        '-TrainingsPerHour',
        '$trainingsPerHour',
        '-TemplateCycle',
        '$templateCycle',
        '-StartIndex',
        '$startIndex',
        '-PerPromptTimeout',
        '760',
        '-Template',
        _selectedCurriculumTemplatePath,
      ];
      final levelLabel = _trainingLevelLabels.firstWhere(
        (label) => label.toLowerCase() == trainingLevel,
      );
      final trainingTargetsLabel = trainingTargets == 'slm,llm'
          ? 'SLM roster + local LLM adapter'
          : trainingTargets == 'slm'
          ? 'SLM roster'
          : 'Local LLM adapter';
      final curriculumLabel = _trainingCurricula
          .firstWhere(
            (c) => '${c['id']}' == _selectedCurriculumId,
            orElse: () => <String, dynamic>{},
          )['title']
          ?.toString();
      final promptCount = trainingsPerHour * hours;
      final remainingPromptCount = promptCount - startIndex + 1;
      final remainingSeconds = (remainingPromptCount * 3600 / trainingsPerHour)
          .ceil();
      if (!mounted) return;
      setState(() {
        _status = 'starting ${_trainingHourLabel(hours)} training';
        _lastCommand = 'powershell.exe ${args.join(' ')}';
        _trainingLastLog = '$trainingCanonicalRoot\\runs\\ui_prompt';
        _trainingCompletedPrompts = 0;
        _trainingRequestedPrompts = remainingPromptCount;
        _trainingSecondsRemaining = remainingSeconds;
        _trainingSecondsToNextPrompt = null;
        _trainingRunIsPrevious = false;
        _trainingRunNeedsRecovery = false;
        _trainingResumeStartIndex = 0;
        _trainingResumeRemainingPrompts = 0;
        _trainingResumeTemplateCycle = 0;
        _trainingRunStatus = 'Starting training';
        _trainingRunDetail =
            '${curriculumLabel == null ? '' : '$curriculumLabel · '}'
            '${_trainingHourLabel(hours)} · $levelLabel · '
            '$trainingsPerHour per hour · '
            '${startIndex > 1 ? '$remainingPromptCount remaining from prompt $startIndex' : '$promptCount total'} · '
            '$trainingTargetsLabel';
        _output = [
          'Starting real local-only prompt training in the background:',
          _lastCommand,
          '',
          if (curriculumLabel != null) 'Curriculum: $curriculumLabel',
          'Duration: ${_trainingHourLabel(hours)} plan'
              '${startIndex > 1 ? ' (resuming at prompt $startIndex)' : ''}',
          'Training level: $levelLabel',
          'Models selected: $trainingTargetsLabel',
          'Trainings per hour: $trainingsPerHour',
          'Trainings in this run: $remainingPromptCount',
          '',
          'Logs and launch receipts will be written under:',
          _trainingLastLog,
        ].join('\n');
      });

      final trainingProcess = await _trainingProcessStarter(
        'powershell.exe',
        args,
        workingDirectory: appRoot,
      );
      if (!mounted) {
        // The shell is gone, so this run is being killed before its wrapper
        // can write a completion update. Stamp the sentinel STOPPED, or it
        // stays RUNNING and the next app launch reports a phantom active run
        // until the sentinel expires.
        final stopped = await trainingProcess.stopTree();
        if (stopped) _markOwnedTrainingRunStopped(trainingProcess.pid);
        return;
      }
      setState(() {
        _trainingProcess = trainingProcess;
        _trainingStarting = false;
        _trainingRunActive = true;
        _trainingRunIsPrevious = false;
        _trainingRunNeedsRecovery = false;
        _trainingRunStatus = 'Training is running';
        _trainingRunDetail =
            '${_trainingHourLabel(hours)} · $levelLabel · '
            '$trainingsPerHour per hour · $trainingTargetsLabel · '
            'PID ${trainingProcess.pid}';
        _status =
            '${_trainingHourLabel(hours)} training running (PID ${trainingProcess.pid})';
      });
      unawaited(
        trainingProcess.exitCode.then((exitCode) {
          if (!mounted || !identical(_trainingProcess, trainingProcess)) {
            return;
          }
          setState(() {
            _trainingProcess = null;
            _trainingStopping = false;
            _trainingRunActive = false;
            _trainingRunIsPrevious = true;
            _trainingRunNeedsRecovery = exitCode != 0;
            _status = exitCode == 0
                ? 'training complete'
                : 'training failed (exit $exitCode)';
            _trainingRunStatus = exitCode == 0
                ? 'Last training completed'
                : 'Last training failed';
            _trainingRunDetail = exitCode == 0
                ? 'The previous run finished. Its final receipts are available.'
                : 'The previous run ended unexpectedly with exit code '
                      '$exitCode. Open its log for details.';
          });
          unawaited(_refreshTrainingRunStatus());
        }),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _status = 'training start error';
        _trainingRunIsPrevious = false;
        _trainingRunNeedsRecovery = false;
        _trainingRunStatus = 'Training could not start';
        _trainingRunDetail = '$error';
        _output = 'ERROR starting prompt training:\n$error';
      });
    } finally {
      if (mounted && _trainingProcess == null) {
        setState(() => _trainingStarting = false);
      }
    }
  }

  Future<void> _stopHourPromptTraining() async {
    final process = _trainingProcess;
    if (process == null || _trainingStopping) return;
    setState(() {
      _trainingStopping = true;
      _status = 'stopping training';
      _trainingRunStatus = 'Stopping training';
      _trainingRunDetail = 'Stopping the complete owned training process tree.';
    });
    final stopped = await process.stopTree();
    if (stopped) _markOwnedTrainingRunStopped(process.pid);
    if (!mounted) return;
    if (_trainingProcess != null && !identical(_trainingProcess, process)) {
      return;
    }
    setState(() {
      _trainingStopping = false;
      if (!stopped) {
        _trainingRunStatus = 'Training stop needs attention';
        _trainingRunDetail =
            'Windows did not confirm the process-tree stop. Review the run log.';
      }
    });
    if (stopped) unawaited(_refreshTrainingRunStatus());
  }

  void _markOwnedTrainingRunStopped(int launcherPid) {
    try {
      final sentinelFile = File(_resolvedTrainingActiveSentinelPath);
      if (!sentinelFile.existsSync()) return;
      final sentinel = _decodeTrainingJson(sentinelFile.readAsStringSync());
      if (sentinel == null ||
          (sentinel['status'] ?? '').toString().toUpperCase() != 'RUNNING' ||
          int.tryParse('${sentinel['launcher_pid'] ?? ''}') != launcherPid) {
        return;
      }
      final finishedAt = DateTime.now().toUtc().toIso8601String();
      sentinel['status'] = 'STOPPED';
      sentinel['finished_at_utc'] = finishedAt;
      sentinel['expires_at_epoch'] = 0;
      sentinel['stopped_by_ui'] = true;
      sentinelFile.writeAsStringSync(
        const JsonEncoder.withIndent('  ').convert(sentinel),
      );

      final lifecyclePath = (sentinel['lifecycle_receipt'] ?? '')
          .toString()
          .trim();
      if (lifecyclePath.isEmpty) return;
      final lifecycleFile = File(lifecyclePath);
      if (!lifecycleFile.existsSync()) return;
      final lifecycle = _decodeTrainingJson(lifecycleFile.readAsStringSync());
      if (lifecycle == null ||
          (lifecycle['status'] ?? '').toString().toUpperCase() != 'RUNNING') {
        return;
      }
      lifecycle['status'] = 'STOPPED';
      lifecycle['finished_at_utc'] = finishedAt;
      final events = lifecycle['events'] is List
          ? List<Object?>.from(lifecycle['events'] as List)
          : <Object?>[];
      events.add({
        'event': 'ui_stop_confirmed',
        'time_utc': finishedAt,
        'status': 'STOPPED',
        'launcher_pid': launcherPid,
      });
      lifecycle['events'] = events;
      lifecycleFile.writeAsStringSync(
        const JsonEncoder.withIndent('  ').convert(lifecycle),
      );
    } catch (_) {
      // The owned process is already stopped. Status polling will surface any
      // receipt-write problem without risking an unrelated process or file.
    }
  }

  /// Whether the wrapper process behind the on-disk RUNNING sentinel is still
  /// alive. Only consulted for runs this app instance did not start, and
  /// throttled so the 3-second status poll does not spawn a tasklist per tick.
  Future<bool> _isTrainingLauncherAlive(int pid) async {
    final now = DateTime.now().toUtc();
    final checkedAt = _trainingLauncherPidCheckedAt;
    if (_trainingLauncherPidChecked == pid &&
        checkedAt != null &&
        now.difference(checkedAt) < const Duration(seconds: 15)) {
      return _trainingLauncherPidAlive;
    }
    var alive = true;
    try {
      final result = await Process.run('tasklist.exe', [
        '/FI',
        'PID eq $pid',
        '/FO',
        'CSV',
        '/NH',
      ]).timeout(const Duration(seconds: 10));
      final text = result.stdout.toString().toLowerCase();
      // Requiring a known launcher image alongside the PID keeps a recycled
      // PID from impersonating the dead launcher. Scheduled runs are launched
      // by powershell.exe (the wrapper), but a smoke run's sentinel is written
      // by the python runner itself, so python.exe/pythonw.exe is equally a
      // live launcher — treating it as dead killed the smoke lane's
      // local-only guard mid-run.
      alive =
          text.contains('"$pid"') &&
          (text.contains('powershell') || text.contains('python'));
    } catch (_) {
      // Liveness could not be proven either way; keep believing the sentinel
      // so a slow system never fails the status of a real run.
      alive = true;
    }
    _trainingLauncherPidCheckedAt = now;
    _trainingLauncherPidChecked = pid;
    _trainingLauncherPidAlive = alive;
    return alive;
  }

  /// Stamps a RUNNING sentinel whose launcher died without writing its
  /// completion update (hard kill, crash at launch). Mirrors
  /// _markOwnedTrainingRunStopped, but records FAILED so the page offers
  /// recovery instead of claiming an active run until the sentinel expires.
  void _markOrphanedTrainingRunFailed(int launcherPid) {
    try {
      final sentinelFile = File(_resolvedTrainingActiveSentinelPath);
      if (!sentinelFile.existsSync()) return;
      final sentinel = _decodeTrainingJson(sentinelFile.readAsStringSync());
      if (sentinel == null ||
          (sentinel['status'] ?? '').toString().toUpperCase() != 'RUNNING' ||
          int.tryParse('${sentinel['launcher_pid'] ?? ''}') != launcherPid) {
        return;
      }
      final finishedAt = DateTime.now().toUtc().toIso8601String();
      sentinel['status'] = 'FAILED';
      sentinel['finished_at_utc'] = finishedAt;
      sentinel['expires_at_epoch'] = 0;
      sentinel['failure_note'] =
          'Launcher process $launcherPid was no longer running; '
          'marked FAILED by Engel Main.';
      sentinelFile.writeAsStringSync(
        const JsonEncoder.withIndent('  ').convert(sentinel),
      );

      final lifecyclePath = (sentinel['lifecycle_receipt'] ?? '')
          .toString()
          .trim();
      if (lifecyclePath.isEmpty) return;
      final lifecycleFile = File(lifecyclePath);
      if (!lifecycleFile.existsSync()) return;
      final lifecycle = _decodeTrainingJson(lifecycleFile.readAsStringSync());
      if (lifecycle == null ||
          (lifecycle['status'] ?? '').toString().toUpperCase() != 'RUNNING') {
        return;
      }
      lifecycle['status'] = 'FAILED';
      lifecycle['finished_at_utc'] = finishedAt;
      final events = lifecycle['events'] is List
          ? List<Object?>.from(lifecycle['events'] as List)
          : <Object?>[];
      events.add({
        'event': 'orphan_detected_marked_failed',
        'time_utc': finishedAt,
        'status': 'FAILED',
        'launcher_pid': launcherPid,
      });
      lifecycle['events'] = events;
      lifecycleFile.writeAsStringSync(
        const JsonEncoder.withIndent('  ').convert(lifecycle),
      );
    } catch (_) {
      // Best effort: the UI already treats the run as failed for this pass,
      // and the next poll retries the receipt write if the file was locked.
    }
  }

  /// Stops a run detected from the sentinel: the run was started before this
  /// app instance, so there is no in-memory process handle to stop. Kills the
  /// launcher's process tree by the sentinel's launcher_pid and stamps the
  /// receipts, exactly like stopping an owned run.
  Future<void> _stopExternalTrainingRun() async {
    if (_trainingStopping) return;
    int? launcherPid;
    try {
      final sentinelFile = File(_resolvedTrainingActiveSentinelPath);
      if (await sentinelFile.exists()) {
        final sentinel = _decodeTrainingJson(await sentinelFile.readAsString());
        if ((sentinel?['status'] ?? '').toString().toUpperCase() == 'RUNNING') {
          launcherPid = int.tryParse('${sentinel?['launcher_pid'] ?? ''}');
        }
      }
    } catch (_) {
      launcherPid = null;
    }
    if (launcherPid == null) {
      // No stoppable run on disk after all; re-read so the buttons catch up.
      unawaited(_refreshTrainingRunStatus());
      return;
    }
    if (!mounted) return;
    setState(() {
      _trainingStopping = true;
      _status = 'stopping training';
      _trainingRunStatus = 'Stopping training';
      _trainingRunDetail =
          'Stopping the detected training run (launcher PID $launcherPid).';
    });
    var stopped = false;
    try {
      final result = await Process.run('taskkill.exe', [
        '/PID',
        '$launcherPid',
        '/T',
        '/F',
      ]).timeout(const Duration(seconds: 10));
      stopped = result.exitCode == 0;
    } catch (_) {
      stopped = false;
    }
    if (stopped) _markOwnedTrainingRunStopped(launcherPid);
    if (!mounted) return;
    setState(() {
      _trainingStopping = false;
      if (!stopped) {
        _trainingRunStatus = 'Training stop needs attention';
        _trainingRunDetail =
            'Windows did not confirm stopping launcher PID $launcherPid. '
            'Review the run log.';
      }
    });
    if (stopped) unawaited(_refreshTrainingRunStatus());
  }

  /// Reads the model-training receipts the Training window reports on.
  ///
  /// Fail-open: this is instrumentation, so an absent or unreadable receipt
  /// clears only that one source and leaves the rest of the page usable. It is
  /// never treated as "zero rows" — the panel says the step has not run.
  Future<void> _refreshModelTrainingReceipts() async {
    if (_modelTrainingReceiptsRefreshing) return;
    if (mounted) {
      setState(() => _modelTrainingReceiptsRefreshing = true);
    } else {
      _modelTrainingReceiptsRefreshing = true;
    }
    try {
      final cycle = await _readModelTrainingReceipt(
        widget.realTrainingCycleReceiptPath,
      );
      final pack = await _readModelTrainingReceipt(
        widget.promptTrainingPackReceiptPath,
      );
      final mirror = await _readModelTrainingReceipt(
        widget.slmRosterMirrorPath,
      );
      final allPacks = await _readAllModelTrainingPacks(
        widget.promptTrainingPackReceiptPath,
      );
      final admissionMinimum = _modelTrainingAdmissionMinimumFromReceipts(
        cycle,
        mirror,
      );
      if (!mounted) return;
      setState(() {
        _modelTrainingCycle = cycle;
        _modelTrainingPack = pack;
        _modelTrainingSlmMirror = mirror;
        _modelTrainingAllPackFiles = allPacks.files;
        _modelTrainingAllPackRows = allPacks.rows;
        _modelTrainingAllPackAdmitted = allPacks.admitted;
        _modelTrainingAllPackRejected = allPacks.rejected;
        _modelTrainingAdmissionMinimum = admissionMinimum;
        _modelTrainingReceiptsCheckedAt = DateTime.now().toUtc();
      });
    } catch (_) {
      // Instrumentation never takes the Training page down with it: an
      // unreadable receipt leaves the previously read values on screen and the
      // next refresh tries again.
    } finally {
      if (mounted) {
        setState(() => _modelTrainingReceiptsRefreshing = false);
      } else {
        _modelTrainingReceiptsRefreshing = false;
      }
    }
  }

  Future<Map<String, dynamic>?> _readModelTrainingReceipt(String path) async {
    final trimmed = path.trim();
    if (trimmed.isEmpty) return null;
    try {
      final file = File(trimmed);
      if (!await file.exists()) return null;
      return _decodeTrainingJson(await file.readAsString());
    } catch (_) {
      // A receipt being rewritten right now reads as absent rather than as a
      // half-parsed result; the next refresh picks up the finished file.
      return null;
    }
  }

  Future<({int files, int rows, int admitted, int rejected})>
  _readAllModelTrainingPacks(String latestReceiptPath) async {
    final trimmed = latestReceiptPath.trim();
    if (trimmed.isEmpty) return (files: 0, rows: 0, admitted: 0, rejected: 0);
    try {
      final directory = File(trimmed).parent;
      if (!await directory.exists()) {
        return (files: 0, rows: 0, admitted: 0, rejected: 0);
      }
      var files = 0;
      var rows = 0;
      var admitted = 0;
      var rejected = 0;
      await for (final entity in directory.list(followLinks: false)) {
        if (entity is! File ||
            !RegExp(
              r'^ENGEL_PROMPT_TRAINING_PACK_.+\.jsonl$',
              caseSensitive: false,
            ).hasMatch(entity.uri.pathSegments.last)) {
          continue;
        }
        files += 1;
        for (final raw in await entity.readAsLines()) {
          final row = _decodeTrainingJson(raw.trim());
          if (row == null || '${row['status'] ?? ''}'.toUpperCase() != 'DONE') {
            continue;
          }
          rows += 1;
          if (row['admit'] == true) {
            admitted += 1;
          } else {
            rejected += 1;
          }
        }
      }
      return (files: files, rows: rows, admitted: admitted, rejected: rejected);
    } catch (_) {
      return (files: 0, rows: 0, admitted: 0, rejected: 0);
    }
  }

  int _modelTrainingAdmissionMinimumFromReceipts(
    Map<String, dynamic>? cycle,
    Map<String, dynamic>? mirror,
  ) {
    final slm = cycle?['slm'];
    final tasks = slm is Map ? slm['tasks'] : null;
    final trainAdmit = tasks is Map ? tasks['train_admit'] : null;
    final cycleMinimum = trainAdmit is Map
        ? _modelTrainingNumber(trainAdmit['min_per_class'])?.round()
        : null;
    if (cycleMinimum != null && cycleMinimum > 0) return cycleMinimum;
    final results = mirror?['results'];
    if (results is List) {
      for (final raw in results) {
        if (raw is! Map || '${raw['task'] ?? ''}' != 'train_admit') continue;
        final minimum = _modelTrainingNumber(raw['min_per_class'])?.round();
        if (minimum != null && minimum > 0) return minimum;
      }
    }
    return 40;
  }

  /// Parses a receipt number without inventing one.
  ///
  /// Returns null for missing, non-numeric, and non-finite values so a panel
  /// line can say the number was not recorded instead of showing a confident 0
  /// that nothing on disk actually claims.
  double? _modelTrainingNumber(Object? raw) {
    if (raw is bool) return null;
    if (raw is num) return raw.isFinite ? raw.toDouble() : null;
    final parsed = double.tryParse('$raw'.trim());
    return parsed != null && parsed.isFinite ? parsed : null;
  }

  Map<String, int> _modelTrainingClassCounts(Object? raw) {
    if (raw is! Map) return const <String, int>{};
    final counts = <String, int>{};
    raw.forEach((key, value) {
      final label = '$key'.trim();
      final count = _modelTrainingNumber(value)?.round();
      if (label.isNotEmpty && count != null && count >= 0) {
        counts[label] = count;
      }
    });
    return counts;
  }

  String _modelTrainingAgeLabel(Object? rawIsoUtc) {
    final text = '${rawIsoUtc ?? ''}'.trim();
    if (text.isEmpty) return 'time not recorded';
    final parsed = DateTime.tryParse(text);
    if (parsed == null) return text;
    final age = DateTime.now().toUtc().difference(parsed.toUtc());
    if (age.isNegative || age.inMinutes < 1) return 'just now';
    if (age.inHours < 1) {
      return '${age.inMinutes} '
          '${age.inMinutes == 1 ? 'minute' : 'minutes'} ago';
    }
    if (age.inDays < 1) {
      return '${age.inHours} ${age.inHours == 1 ? 'hour' : 'hours'} ago';
    }
    return '${age.inDays} ${age.inDays == 1 ? 'day' : 'days'} ago';
  }

  String get _modelTrainingReceiptsFreshnessLabel {
    final checkedAt = _modelTrainingReceiptsCheckedAt;
    if (checkedAt == null) return 'Receipts have not been read yet';
    final age = DateTime.now().toUtc().difference(checkedAt);
    if (age.isNegative || age.inMinutes < 1) return 'Receipts read just now';
    if (age.inHours < 1) {
      return 'Receipts read ${age.inMinutes} '
          '${age.inMinutes == 1 ? 'minute' : 'minutes'} ago';
    }
    return 'Receipts read ${age.inHours} '
        '${age.inHours == 1 ? 'hour' : 'hours'} ago';
  }

  Map<String, Map<String, dynamic>> get _modelTrainingMirrorEntries {
    final entries = <String, Map<String, dynamic>>{};
    final results = _modelTrainingSlmMirror?['results'];
    if (results is! List) return entries;
    for (final raw in results) {
      if (raw is! Map) continue;
      final entry = Map<String, dynamic>.from(raw);
      final task = '${entry['task'] ?? ''}'.trim();
      if (task.isEmpty) continue;
      final metrics = entry['metrics'] is Map
          ? Map<String, dynamic>.from(entry['metrics'] as Map)
          : const <String, dynamic>{};
      entries[task] = {
        ...entry,
        'macro_f1': metrics['macro_f1'],
        'baseline': metrics['majority_baseline_accuracy'],
        'lift': metrics['lift_over_baseline'],
        'rows': entry['train_rows'],
      };
    }
    return entries;
  }

  bool get _modelTrainingMirrorMatchesCycle {
    final cycleFinished = DateTime.tryParse(
      '${_modelTrainingCycle?['finished_at_utc'] ?? ''}',
    );
    final mirrorGenerated = DateTime.tryParse(
      '${_modelTrainingSlmMirror?['generated_at_utc'] ?? ''}',
    );
    if (cycleFinished == null || mirrorGenerated == null) return false;
    return cycleFinished.toUtc().difference(mirrorGenerated.toUtc()).abs() <=
        const Duration(minutes: 10);
  }

  /// The roster models' last training result, plus where that result came from.
  ///
  /// The cycle receipt wins when it exists because it describes THIS cycle. The
  /// ROG mirror is only a fallback for machines where no cycle has run yet, and
  /// the source string is rendered so an old mirror is never mistaken for the
  /// result of today's run.
  ({String source, List<EngelSlmRosterLine> lines})
  get _modelTrainingSlmRoster {
    final slm = _modelTrainingCycle?['slm'];
    final tasks = slm is Map ? slm['tasks'] : null;
    final entries = <String, Map<String, dynamic>>{};
    final mirrorEntries = _modelTrainingMirrorEntries;
    if (tasks is Map && tasks.isNotEmpty) {
      tasks.forEach((key, value) {
        final task = '$key'.trim();
        if (task.isEmpty) return;
        final cycleEntry = value is Map
            ? Map<String, dynamic>.from(value)
            : const <String, dynamic>{};
        final supplement = _modelTrainingMirrorMatchesCycle
            ? mirrorEntries[task]
            : null;
        entries[task] = {if (supplement != null) ...supplement, ...cycleEntry};
      });
      return (
        source: 'latest cycle',
        lines: _modelTrainingRosterLines(entries),
      );
    }
    entries.addAll(mirrorEntries);
    return (
      source: entries.isEmpty ? 'no training result yet' : 'last local receipt',
      lines: _modelTrainingRosterLines(entries),
    );
  }

  List<EngelSlmRosterLine> _modelTrainingRosterLines(
    Map<String, Map<String, dynamic>> entries,
  ) {
    return _engelSlmRosterCatalog
        .map((spec) {
          final task = spec['task']!;
          final entry = entries[task];
          return EngelSlmRosterLine(
            task: task,
            displayName: spec['name']!,
            purpose: spec['purpose']!,
            stage: spec['stage']!,
            recorded: entry != null,
            ok: entry?['ok'] == true,
            status: entry == null
                ? 'Not selected in the latest training run.'
                : '${entry['status'] ?? ''}'.trim(),
            macroF1: _modelTrainingNumber(entry?['macro_f1']),
            baseline: _modelTrainingNumber(entry?['baseline']),
            lift: _modelTrainingNumber(entry?['lift']),
            rows: _modelTrainingNumber(entry?['rows'])?.round(),
            classCounts: _modelTrainingClassCounts(entry?['class_counts']),
            minPerClass: _modelTrainingNumber(entry?['min_per_class'])?.round(),
          );
        })
        .toList(growable: false);
  }

  /// The one-line verdict for a roster model.
  ///
  /// The gate verdict is stated in the line itself rather than left implicit in
  /// the receipt's status prose, because "trained" and "trained well enough to
  /// ship" are the distinction this panel exists to make. The raw status text
  /// stays available as the row tooltip.
  String _modelTrainingRosterDetail(EngelSlmRosterLine line) {
    if (!line.recorded) {
      return switch (line.stage) {
        'collecting_data' => 'collecting real data · not trained in this run',
        'shadow_candidate' => 'shadow candidate · not trained in this run',
        _ => 'not trained in this run',
      };
    }
    if (!line.ok && line.macroF1 == null) {
      final status = line.status.toLowerCase();
      if (status.contains('not enough') || status.contains('insufficient')) {
        if (line.classCounts.isNotEmpty && line.minPerClass != null) {
          final counts = line.classCounts.entries
              .map((entry) => '${entry.value} ${entry.key}')
              .join(' / ');
          return '$counts · needs ${line.minPerClass} of each · no score yet';
        }
        return 'needs more examples · no score yet';
      }
      return 'did not meet the gate · no score recorded';
    }
    // The baseline is a majority-class ACCURACY and the gate measures lift against it, so
    // this shows the lift rather than parking that baseline next to macro-F1: a head can
    // sit below its baseline on F1 while beating it soundly on the measure the gate uses
    // (intent_router, 20260801: F1 0.908, baseline 0.917, lift +0.066). Printing the two
    // side by side made a passing model read as worse than guessing.
    return <String>[
      line.ok ? 'met the gate' : 'below the gate',
      if (line.macroF1 != null)
        'macro-F1 ${line.macroF1!.toStringAsFixed(3)}'
      else
        'macro-F1 not recorded',
      if (line.lift != null)
        '${line.lift! >= 0 ? '+' : ''}${line.lift!.toStringAsFixed(3)} over baseline'
      else if (line.baseline != null)
        'baseline ${line.baseline!.toStringAsFixed(3)}',
      if (line.rows != null) '${line.rows} rows',
    ].join(' · ');
  }

  String _modelTrainingRosterSummary(List<EngelSlmRosterLine> lines) {
    final ready = lines.where((line) => line.recorded && line.ok).length;
    final needsData = lines.where((line) => line.recorded && !line.ok).length;
    final collecting = lines
        .where((line) => !line.recorded && line.stage == 'collecting_data')
        .length;
    final notTrained = lines.length - ready - needsData - collecting;
    return <String>[
      if (ready > 0) '$ready ready',
      if (needsData > 0) '$needsData ${needsData == 1 ? 'needs' : 'need'} data',
      if (collecting > 0) '$collecting collecting',
      if (notTrained > 0) '$notTrained not trained',
    ].join(' · ');
  }

  String _modelTrainingRosterSupportingText(EngelSlmRosterLine line) {
    if (line.task == 'train_admit' &&
        line.recorded &&
        !line.ok &&
        line.minPerClass != null) {
      final target = line.minPerClass!;
      final admitGap = math.max(0, target - (line.classCounts['admit'] ?? 0));
      final rejectGap = math.max(0, target - (line.classCounts['reject'] ?? 0));
      final totalGap = admitGap + rejectGap;
      if (totalGap > 0) {
        return 'Next: review at least $totalGap more answers — '
            '$admitGap admitted and $rejectGap rejected.';
      }
    }
    return line.purpose;
  }

  Color _realTrainingCycleColor(String status) {
    if (status == 'PASS') return const Color(0xff5fd0a8);
    if (status == 'PARTIAL') return const Color(0xffe5c07b);
    if (status == 'FAIL') return const Color(0xffe06c75);
    return const Color(0xff6f8497);
  }

  Future<void> _confirmRealTrainingCycleFromUi() async {
    if (_modelTrainingCycleProcess != null ||
        _running ||
        _trainingControlsLocked) {
      return;
    }
    final targets = _trainingTargetsSlug;
    final targetLabel = _trainingTargetsLabel;
    final needsLlmApproval = targets.split(',').contains('llm');
    var approvalText = '';
    String? approval;
    approval = await showDialog<String>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('Train selected models?'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Targets: $targetLabel\n\n'
                  'Engel will validate and push admitted prompt packs, rebuild the training dataset, and run each selected trainer.',
                ),
                if (needsLlmApproval) ...[
                  const SizedBox(height: 14),
                  const Text(
                    'The local LLM run creates and evaluates new adapter weights on CT246. It does not deploy or promote them. Type the exact approval phrase to continue:',
                    style: TextStyle(height: 1.35),
                  ),
                  const SizedBox(height: 8),
                  const SelectableText(
                    engelLocalLlmTrainingApprovalPhrase,
                    key: Key('model-training-approval-phrase'),
                    style: TextStyle(
                      color: Color(0xffffc857),
                      fontFamily: 'Consolas',
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    key: const Key('model-training-approval-input'),
                    autofocus: true,
                    autocorrect: false,
                    enableSuggestions: false,
                    decoration: const InputDecoration(
                      labelText: 'Exact approval phrase',
                    ),
                    onChanged: (value) =>
                        setDialogState(() => approvalText = value),
                  ),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              key: const Key('confirm-model-training'),
              onPressed:
                  needsLlmApproval &&
                      approvalText != engelLocalLlmTrainingApprovalPhrase
                  ? null
                  : () => Navigator.of(
                      dialogContext,
                    ).pop(needsLlmApproval ? approvalText : ''),
              child: const Text('Train models'),
            ),
          ],
        ),
      ),
    );
    if (approval == null || !mounted) return;
    await _runRealTrainingCycleFromUi(
      trainingTargets: targets,
      llmApproval: approval,
    );
  }

  /// Runs the real training cycle for the explicitly selected model families.
  ///
  /// It rides the same injectable process starter as the prompt-training
  /// launcher so the run is owned (stoppable, and killed with the app) instead
  /// of being a fire-and-forget child, and so widget tests can intercept it.
  Future<void> _runRealTrainingCycleFromUi({
    required String trainingTargets,
    String llmApproval = '',
  }) async {
    if (_modelTrainingCycleProcess != null ||
        _running ||
        _trainingControlsLocked) {
      return;
    }
    final python = await _findStandaloneChatPython();
    final script = File(widget.realTrainingCycleScriptPath);
    if (python == null || !await script.exists()) {
      if (!mounted) return;
      setState(() {
        _modelTrainingCycleResult = [
          if (python == null)
            'Python is missing. Expected $runtimePythonExe or python.exe.',
          if (python != null)
            'The training cycle orchestrator is missing: '
                '${widget.realTrainingCycleScriptPath}',
        ].join(' ');
        _modelTrainingCycleResultIsError = true;
      });
      return;
    }

    late final String canonicalTrainingTargets;
    late final EngelTrainingCycleRuntimeBudget runtimeBudget;
    try {
      canonicalTrainingTargets = normalizeEngelModelTrainingTargets(
        trainingTargets,
      );
      runtimeBudget = await _readModelTrainingRuntimeBudget(
        canonicalTrainingTargets,
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _modelTrainingCycleResult =
            'Model training was refused before launch because its runtime '
            'safety contract is missing or invalid: $error';
        _modelTrainingCycleResultIsError = true;
        _status = 'model training runtime contract invalid';
      });
      return;
    }
    final wholeCycleDeadlineLabel = _formatTrainingTime(
      runtimeBudget.wholeCycleDeadline.inSeconds,
    );
    final clientDeadlineLabel = _formatTrainingTime(
      runtimeBudget.clientDeadline.inSeconds,
    );

    final args = [
      widget.realTrainingCycleScriptPath,
      '--all',
      '--targets',
      canonicalTrainingTargets,
      if (canonicalTrainingTargets.split(',').contains('llm')) ...[
        '--llm-approval',
        llmApproval,
      ],
      '--summary',
    ];
    final displayArgs = args
        .asMap()
        .entries
        .map(
          (entry) => entry.key > 0 && args[entry.key - 1] == '--llm-approval'
              ? '<APPROVAL_REDACTED>'
              : entry.value,
        )
        .toList(growable: false);
    if (!mounted) return;
    setState(() {
      _modelTrainingCycleResult =
          'Starting the training cycle. Nothing is reported until it writes '
          'its receipt.';
      _modelTrainingCycleResultIsError = false;
      _lastCommand = '${python.path} ${displayArgs.join(' ')}';
      _status = 'running the real training cycle';
      _output = [
        'Running the real training cycle in the background:',
        _lastCommand,
        '',
        'Cycle receipt: ${widget.realTrainingCycleReceiptPath}',
      ].join('\n');
    });

    Future<bool>? deadlineEnforcement;
    try {
      final process = await _trainingProcessStarter(
        python.path,
        args,
        workingDirectory: appRoot,
      );
      if (!mounted) {
        try {
          if (!await process.stopTree()) {
            debugPrint(
              'Engel could not confirm model-training process-tree stop after '
              'the UI was disposed during launch (PID ${process.pid}).',
            );
          }
        } catch (error) {
          debugPrint(
            'Engel model-training stop threw after disposal during launch '
            '(PID ${process.pid}): $error',
          );
        }
        return;
      }
      _modelTrainingCycleStopFuture = null;
      setState(() {
        _modelTrainingCycleProcess = process;
        _modelTrainingCycleResult =
            'Training cycle running (PID ${process.pid}). The dataset build '
            'and selected model trainers can take a while; this panel updates from the '
            'receipt when the cycle finishes. Orchestrator limit: '
            '$wholeCycleDeadlineLabel; UI safety limit with termination grace: '
            '$clientDeadlineLabel.';
        _modelTrainingCycleResultIsError = false;
      });
      // A wedged cycle must not hold the button hostage forever, and a
      // half-finished run is a blocker to report, not a silent hang. The local
      // LLM proof has a bounded train plus evaluation budget that can exceed the
      // SLM-only window.
      _modelTrainingCycleDeadline?.cancel();
      _modelTrainingCycleDeadline = Timer(runtimeBudget.clientDeadline, () {
        if (!identical(_modelTrainingCycleProcess, process)) return;
        deadlineEnforcement = _enforceModelTrainingDeadline(
          process,
          runtimeBudget,
        );
      });
      unawaited(
        process.exitCode.then((exitCode) async {
          _modelTrainingCycleDeadline?.cancel();
          _modelTrainingCycleDeadline = null;
          final enforcement = deadlineEnforcement;
          final terminationConfirmed = enforcement == null
              ? false
              : await enforcement;
          if (!mounted || !identical(_modelTrainingCycleProcess, process)) {
            return;
          }
          setState(() {
            _modelTrainingCycleProcess = null;
            _modelTrainingCycleStopFuture = null;
            _status = exitCode == 0
                ? 'real training cycle complete'
                : 'real training cycle exit $exitCode';
          });
          await _refreshModelTrainingReceipts();
          if (!mounted || terminationConfirmed) return;
          final cycle = _modelTrainingCycle;
          final cycleStatus = '${cycle?['status'] ?? ''}'.trim();
          final steps = cycle?['steps'];
          final stepList = steps is List ? steps : const <Object?>[];
          final okSteps = stepList
              .where((step) => step is Map && step['ok'] == true)
              .length;
          setState(() {
            _modelTrainingCycleResult = cycle == null
                ? 'The training cycle exited with code $exitCode and wrote no '
                      'cycle receipt, so nothing about it can be reported.'
                : 'Training cycle $cycleStatus · exit code $exitCode · '
                      '$okSteps of ${stepList.length} steps ok';
            _modelTrainingCycleResultIsError =
                cycle == null || exitCode != 0 || cycleStatus == 'FAIL';
          });
        }),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _modelTrainingCycleProcess = null;
        _modelTrainingCycleStopFuture = null;
        _status = 'real training cycle error';
        _modelTrainingCycleResult =
            'The training cycle could not start: $error';
        _modelTrainingCycleResultIsError = true;
        _output = 'ERROR starting the real training cycle:\n$error';
      });
    }
  }

  // --- Training UI ---
  Widget _trainingActions() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        FilledButton.icon(
          key: const Key('hour-training-control'),
          // Three states: stop an owned run, stop a run detected from the
          // sentinel (started before this app instance — previously this was
          // a dead 'Training already running' button with no way to stop the
          // wrapper for hours), or review + start a new run.
          onPressed: _trainingProcess != null
              ? _trainingStopping
                    ? null
                    : () => unawaited(_stopHourPromptTraining())
              : _trainingRunActive
              ? _trainingStopping
                    ? null
                    : () => unawaited(_stopExternalTrainingRun())
              : _running || _trainingControlsLocked
              ? null
              : () => unawaited(_confirmHourPromptTraining()),
          icon: Icon(
            _trainingProcess != null || _trainingRunActive
                ? Icons.stop_circle_outlined
                : Icons.hourglass_top,
            size: 17,
          ),
          label: Text(
            _trainingStopping
                ? 'Stopping…'
                : _trainingProcess != null
                ? 'Stop training'
                : _trainingStarting
                ? 'Starting…'
                : _trainingRunActive
                ? 'Stop detected training'
                : 'Review $_trainingHours-hour Prompt Training',
          ),
          style: _trainingProcess != null || _trainingRunActive
              ? FilledButton.styleFrom(
                  backgroundColor: const Color(0xffb23246),
                  foregroundColor: Colors.white,
                )
              : null,
        ),
        OutlinedButton.icon(
          key: const Key('training-apply-models'),
          onPressed:
              _modelTrainingCycleProcess != null ||
                  _running ||
                  _trainingControlsLocked
              ? null
              : () => unawaited(_confirmRealTrainingCycleFromUi()),
          icon: const Icon(Icons.model_training, size: 17),
          label: Text(
            _modelTrainingCycleProcess != null
                ? 'Training models…'
                : 'Review Model Training',
          ),
        ),
        OutlinedButton.icon(
          key: const Key('training-test-one'),
          onPressed: _running || _trainingControlsLocked
              ? null
              : () => unawaited(_runTrainingSmoke()),
          icon: const Icon(Icons.play_circle, size: 17),
          label: const Text('Test 3 Prompts'),
        ),
        OutlinedButton.icon(
          key: const Key('training-prepare-files'),
          onPressed: _running || _trainingControlsLocked
              ? null
              : () => unawaited(_syncTrainingAssets()),
          icon: const Icon(Icons.sync, size: 17),
          label: const Text('Prepare Files'),
        ),
        OutlinedButton.icon(
          key: const Key('training-refresh-status'),
          onPressed: _trainingRunStatusRefreshShowsBusy
              ? null
              : () {
                  unawaited(_scanTrainingManifest());
                  unawaited(
                    _refreshTrainingRunStatus(userInitiated: true),
                  );
                },
          icon: Icon(
            _trainingRunStatusRefreshShowsBusy ? Icons.sync : Icons.refresh,
            size: 17,
          ),
          label: Text(
            _trainingRunStatusRefreshShowsBusy
                ? 'Refreshing…'
                : 'Refresh Status',
          ),
        ),
      ],
    );
  }

  String _trainingAssetDisplayName(String assetPath) {
    final parts = assetPath.trim().split(RegExp(r'[\\/]'));
    return parts.isEmpty || parts.last.isEmpty ? assetPath : parts.last;
  }

  Widget _trainingMissingAssetsNotice() {
    // Dedup on the full path (distinct files can share a basename); the
    // '...and N more' remainder is computed from what is actually listed so
    // the header count and the rows can never disagree.
    final paths = _trainingMissingAssets.toSet().toList(growable: false);
    final shown = paths.take(6).toList(growable: false);
    final names = <String>[];
    for (final path in shown) {
      final base = _trainingAssetDisplayName(path);
      final collides =
          shown.where((p) => _trainingAssetDisplayName(p) == base).length > 1;
      names.add(collides ? path : base);
    }
    final hiddenCount = paths.length - shown.length;
    return Container(
      key: const Key('training-missing-assets'),
      margin: const EdgeInsets.only(top: 4, bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xffffc857).withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(7),
        border: Border.all(
          color: const Color(0xffffc857).withValues(alpha: 0.45),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '$_trainingMissingCount required Training '
            '${_trainingMissingCount == 1 ? 'file is' : 'files are'} missing',
            style: const TextStyle(
              color: Color(0xffffd978),
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 5),
          for (final name in names)
            Text(
              '- $name',
              key: Key('training-missing-asset-$name'),
              style: const TextStyle(
                color: Color(0xffd8e5f4),
                fontFamily: 'Consolas',
                fontSize: 11.5,
                height: 1.4,
              ),
            ),
          if (hiddenCount > 0)
            Text(
              '...and $hiddenCount more',
              style: const TextStyle(color: Color(0xffaeb8cb), fontSize: 11.5),
            ),
          const SizedBox(height: 5),
          const Text(
            'Choose Prepare Files below. Engel will show the result '
            'here before any training can start.',
            style: TextStyle(
              color: Color(0xffaeb8cb),
              fontSize: 11.5,
              height: 1.35,
            ),
          ),
        ],
      ),
    );
  }

  /// Reveals the run log without the shared-output ceremony of
  /// _revealFileInExplorer: recovery must stay reachable while Engel is busy
  /// (_running), and peeking at a log must not overwrite the busy task's
  /// status panel.
  Future<void> _openTrainingRunLog() async {
    final path = _trainingLastLog.trim();
    if (path.isEmpty) return;
    try {
      if (await Directory(path).exists()) {
        await _processRunner('explorer.exe', [path]);
      } else if (await File(path).exists()) {
        await _processRunner('explorer.exe', ['/select,', path]);
      }
    } catch (_) {
      // Best-effort reveal; the path itself is visible in the run detail.
    }
  }

  Widget _trainingRecoveryActions() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        if (_trainingLastLog.isNotEmpty)
          OutlinedButton.icon(
            key: const Key('training-recovery-open-log'),
            // Revealing a log in Explorer conflicts with nothing; recovery
            // must stay reachable even while Engel is busy elsewhere.
            onPressed: () => unawaited(_openTrainingRunLog()),
            icon: const Icon(Icons.article_outlined, size: 17),
            label: const Text('Open run log'),
          ),
        if (_trainingResumeRequiresNewMaterial)
          FilledButton.icon(
            key: const Key('training-recovery-prepare-new'),
            onPressed: _running || _trainingControlsLocked
                ? null
                : () => unawaited(_syncTrainingAssets()),
            icon: const Icon(Icons.sync, size: 17),
            label: const Text('Prepare new material'),
          ),
      ],
    );
  }

  Widget _trainingCompactStatus() {
    final refreshError = _trainingRunStatusCheckError.trim();
    final showDetail =
        _trainingRunNeedsRecovery ||
        refreshError.isNotEmpty ||
        _trainingPackRejected > 0 ||
        (_trainingRequestedPrompts > 0 &&
            _trainingCompletedPrompts < _trainingRequestedPrompts);
    final attention = _trainingRunNeedsRecovery || refreshError.isNotEmpty;
    final accent = _trainingRunActive
        ? const Color(0xff00e87a)
        : attention
        ? const Color(0xffffc857)
        : const Color(0xff334157);
    final leadingIcon = _trainingRunActive
        ? Icons.play_circle_outline
        : attention
        ? Icons.error_outline
        : Icons.info_outline;
    final leadingColor = _trainingRunActive
        ? const Color(0xff00e87a)
        : attention
        ? const Color(0xffffc857)
        : const Color(0xff9fb0c8);
    // Statuses produced from prompt events already carry their own counts
    // ('Running prompt 29 of 50'); appending the summary suffix to those
    // would read 'Running prompt 29 of 50 — 28 of 50 complete'.
    final statusCarriesCounts = _trainingRunStatus.contains(' of ');
    final visibleStatus = refreshError.isNotEmpty
        ? refreshError
        : _trainingRequestedPrompts > 0 && !statusCarriesCounts
        ? '$_trainingRunStatus — $_trainingCompletedPrompts of '
              '$_trainingRequestedPrompts complete'
        : _trainingRunStatus;
    return Container(
      key: const Key('training-compact-status'),
      margin: const EdgeInsets.only(top: 4, bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
      decoration: BoxDecoration(
        color: const Color(0xff111827),
        borderRadius: BorderRadius.circular(7),
        border: Border.all(color: accent),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(leadingIcon, size: 18, color: leadingColor),
              const SizedBox(width: 9),
              Expanded(
                child: Text(
                  visibleStatus,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Color(0xffd8e5f4),
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Tooltip(
                message: refreshError.isNotEmpty
                    ? refreshError
                    : _trainingStatusFreshnessLabel,
                child: Icon(
                  refreshError.isNotEmpty
                      ? Icons.error_outline
                      : Icons.schedule_outlined,
                  size: 17,
                  color: refreshError.isNotEmpty
                      ? const Color(0xffffc857)
                      : const Color(0xff9fb0c8),
                ),
              ),
            ],
          ),
          if (showDetail) ...[
            const SizedBox(height: 8),
            const Divider(height: 1, color: Color(0xff334157)),
            const SizedBox(height: 8),
            Semantics(
              liveRegion: true,
              child: Text(
                refreshError.isNotEmpty ? refreshError : _trainingRunDetail,
                key: const Key('training-compact-status-detail'),
                style: const TextStyle(
                  color: Color(0xffd8e5f4),
                  fontSize: 12,
                  height: 1.35,
                ),
              ),
            ),
            if (_trainingRunNeedsRecovery) ...[
              const SizedBox(height: 9),
              Container(
                key: const Key('training-recovery-state'),
                alignment: Alignment.centerLeft,
                child: _trainingRecoveryActions(),
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _modelTrainingRosterRow(EngelSlmRosterLine line) {
    final color = !line.recorded
        ? const Color(0xff6f8497)
        : line.ok
        ? const Color(0xff5fd0a8)
        : const Color(0xffe5c07b);
    return Tooltip(
      message:
          '${line.purpose}\n\nTechnical id: ${line.task}\n'
          '${line.status.isEmpty ? 'The receipt recorded no status text.' : line.status}',
      child: Padding(
        key: Key('model-training-slm-${line.task}'),
        padding: const EdgeInsets.only(left: 28, bottom: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              !line.recorded
                  ? Icons.schedule_outlined
                  : line.ok
                  ? Icons.check_circle_outline
                  : Icons.error_outline,
              color: color,
              size: 15,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${line.displayName} · ${_modelTrainingRosterDetail(line)}',
                    style: const TextStyle(
                      color: Color(0xffd7e4ef),
                      fontSize: 11.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _modelTrainingRosterSupportingText(line),
                    style: const TextStyle(
                      color: Color(0xff8ea3bf),
                      fontSize: 10.5,
                      height: 1.25,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// What the machine actually did with the answers prompt training captured.
  ///
  /// Everything here is read from receipts on disk. When a receipt is absent
  /// the panel says the step has not run rather than rendering a zero, because
  /// a confident 0 rows is indistinguishable from a cycle that never happened.
  Widget _modelTrainingPanel() {
    final cycle = _modelTrainingCycle;
    final pack = _modelTrainingPack;
    final roster = _modelTrainingSlmRoster;
    final recordedHeadsNeedingEvidence = roster.lines
        .where((line) => line.recorded && !line.ok)
        .toList(growable: false);
    final receiptCycleStatus = '${cycle?['status'] ?? ''}'.trim();
    final cycleStatus =
        receiptCycleStatus == 'PASS' && recordedHeadsNeedingEvidence.isNotEmpty
        ? 'PARTIAL'
        : receiptCycleStatus;
    final receiptStatusContradictsEvidence =
        receiptCycleStatus == 'PASS' && cycleStatus == 'PARTIAL';
    final dataset = cycle?['dataset'] is Map
        ? Map<String, dynamic>.from(cycle!['dataset'] as Map)
        : const <String, dynamic>{};
    final cycleTargets = cycle?['targets'] is List
        ? List<Object?>.from(cycle!['targets'] as List)
              .map((target) => '$target'.trim())
              .where((target) => target.isNotEmpty)
              .toList(growable: false)
        : const <String>[];
    final llm = cycle?['llm'] is Map
        ? Map<String, dynamic>.from(cycle!['llm'] as Map)
        : const <String, dynamic>{};
    final blockers = cycle?['blockers'] is List
        ? List<Object?>.from(cycle!['blockers'] as List)
              .map((blocker) => '$blocker'.trim())
              .where((blocker) => blocker.isNotEmpty)
              .toList(growable: false)
        : const <String>[];
    final loraSteps = cycle?['lora_next_steps'] is List
        ? List<Object?>.from(cycle!['lora_next_steps'] as List)
              .map((step) => '$step'.trim())
              .where((step) => step.isNotEmpty)
              .toList(growable: false)
        : const <String>[];
    final packRows = _modelTrainingNumber(pack?['rows'])?.round();
    final packAdmitted = _modelTrainingNumber(pack?['admitted'])?.round();
    final trainRows = _modelTrainingNumber(dataset['train'])?.round();
    final valRows = _modelTrainingNumber(dataset['val'])?.round();
    final promptTrainingRows = _modelTrainingNumber(
      dataset['prompt_training_rows'],
    )?.round();
    final cycleRunning = _modelTrainingCycleProcess != null;

    final packValue = pack == null
        ? 'No pack receipt yet'
        : packRows == null
        ? 'A pack receipt exists but recorded no row count'
        : 'Last session: $packRows answers captured, '
              '${packAdmitted == null ? 'admitted count not recorded' : '$packAdmitted admitted for training'}';
    final datasetValue = cycle == null
        ? 'No cycle receipt yet'
        : trainRows == null && valRows == null
        ? 'The cycle recorded no dataset counts'
        : '${trainRows == null ? 'train not recorded' : '$trainRows train'} · '
              '${valRows == null ? 'validation not recorded' : '$valRows validation'}'
              '${promptTrainingRows == null ? '' : ' · $promptTrainingRows prompt-training'}'
              ' · ${_modelTrainingAgeLabel(dataset['built_at_utc'])}';

    return _macToolPanel(
      key: const Key('model-training-panel'),
      title: 'Model Training',
      icon: Icons.psychology_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (cycle == null)
            Container(
              key: const Key('model-training-empty'),
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xff151b27),
                borderRadius: BorderRadius.circular(7),
                border: Border.all(color: const Color(0xff334157)),
              ),
              child: const Text(
                'No training cycle has run yet — prompt training practices, '
                'this is what turns it into model training. Run the cycle to '
                'push captured answers into the SFT dataset and train the '
                'selected SLM roster and/or local LLM adapter.',
                style: TextStyle(
                  color: Color(0xff8ea3bf),
                  fontSize: 12,
                  height: 1.35,
                ),
              ),
            )
          else ...[
            Padding(
              key: const Key('model-training-cycle-status'),
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Icon(
                    Icons.fact_check_outlined,
                    color: _realTrainingCycleColor(cycleStatus),
                    size: 18,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Latest model results: '
                      '${cycleStatus.isEmpty ? 'status not recorded' : cycleStatus}'
                      ' · cycle finished '
                      '${_modelTrainingAgeLabel(cycle['finished_at_utc'])}',
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: _realTrainingCycleColor(cycleStatus),
                        fontSize: 12.5,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            if (receiptStatusContradictsEvidence)
              Padding(
                key: const Key('model-training-cycle-roster-warning'),
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  'The older receipt says PASS, but '
                  '${recordedHeadsNeedingEvidence.map((line) => line.displayName).join(', ')} '
                  '${recordedHeadsNeedingEvidence.length == 1 ? 'needs' : 'need'} more evidence.',
                  style: const TextStyle(
                    color: Color(0xffe5c07b),
                    fontSize: 11.5,
                    height: 1.35,
                  ),
                ),
              ),
            if (blockers.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  'First blocker: ${blockers.first}',
                  key: const Key('model-training-cycle-blocker'),
                  style: const TextStyle(
                    color: Color(0xffe5c07b),
                    fontSize: 11.5,
                    height: 1.35,
                  ),
                ),
              ),
          ],
          KeyedSubtree(
            key: const Key('model-training-pack-summary'),
            child: _macSettingLine(
              label: 'Latest training pack',
              value: packValue,
              icon: Icons.inventory_2_outlined,
            ),
          ),
          if (_modelTrainingAllPackFiles > 0)
            KeyedSubtree(
              key: const Key('model-training-all-packs-summary'),
              child: _macSettingLine(
                label: 'All captured packs',
                value:
                    '$_modelTrainingAllPackRows completed answers · '
                    '$_modelTrainingAllPackAdmitted admitted / '
                    '$_modelTrainingAllPackRejected rejected · '
                    '$_modelTrainingAllPackFiles pack files',
                icon: Icons.inventory_outlined,
              ),
            ),
          if (_modelTrainingAllPackFiles > 0)
            Padding(
              key: const Key('model-training-admission-gap'),
              padding: const EdgeInsets.only(left: 28, bottom: 7),
              child: Text(
                _modelTrainingAdmissionGapSummary,
                style: const TextStyle(
                  color: Color(0xffaeb8cb),
                  fontSize: 11.5,
                  height: 1.35,
                ),
              ),
            ),
          KeyedSubtree(
            key: const Key('model-training-dataset-summary'),
            child: _macSettingLine(
              label: 'SFT dataset',
              value: datasetValue,
              icon: Icons.dataset_outlined,
            ),
          ),
          KeyedSubtree(
            key: const Key('model-training-target-summary'),
            child: _macSettingLine(
              label: 'Current model plan',
              value: _trainingTargetsLabel,
              icon: Icons.model_training,
            ),
          ),
          KeyedSubtree(
            key: const Key('model-training-previous-target-summary'),
            child: _macSettingLine(
              label: 'Previous model cycle',
              value: cycle == null
                  ? 'No previous cycle receipt'
                  : cycleTargets.isEmpty
                  ? 'SLM roster · older receipt format'
                  : cycleTargets
                        .map(
                          (target) => target == 'slm'
                              ? 'SLM roster'
                              : target == 'llm'
                              ? 'Local LLM adapter'
                              : target,
                        )
                        .join(' + '),
              icon: Icons.model_training,
            ),
          ),
          KeyedSubtree(
            key: const Key('model-training-slm-source'),
            child: _macSettingLine(
              label: 'SLM roster · ${roster.source}',
              value: _modelTrainingRosterSummary(roster.lines),
              icon: Icons.hub_outlined,
            ),
          ),
          for (final line in roster.lines) _modelTrainingRosterRow(line),
          KeyedSubtree(
            key: const Key('model-training-llm-summary'),
            child: _macSettingLine(
              label: 'Local LLM adapter',
              value: cycle == null
                  ? '${_trainLlmTarget ? 'Selected now' : 'Not selected now'} · no previous result'
                  : !cycleTargets.contains('llm')
                  ? '${_trainLlmTarget ? 'Selected now' : 'Not selected now'} · not trained in the previous cycle'
                  : llm['new_adapter_trained'] == true && llm['ok'] == true
                  ? '${_trainLlmTarget ? 'Selected now · ' : ''}trained and evaluated · not deployed'
                  : llm['preflight'] is Map &&
                        (llm['preflight'] as Map)['ok'] == true
                  ? 'Preflight passed; training did not pass'
                  : 'Training did not pass — review the blocker',
              icon: Icons.psychology_outlined,
            ),
          ),
          if ('${llm['new_adapter_path'] ?? ''}'.trim().isNotEmpty)
            Padding(
              key: const Key('model-training-llm-adapter-path'),
              padding: const EdgeInsets.only(left: 28, bottom: 6),
              child: Text(
                'Adapter: ${llm['new_adapter_path']}'
                '${llm['validation_loss_delta'] == null ? '' : ' · validation loss Δ ${llm['validation_loss_delta']}'}',
                style: const TextStyle(
                  color: Color(0xffb8b8c4),
                  fontSize: 11.5,
                ),
              ),
            ),
          const SizedBox(height: 4),
          Container(
            key: const Key('model-training-lora-next-steps'),
            decoration: BoxDecoration(
              color: const Color(0xffffc857).withValues(alpha: 0.07),
              borderRadius: BorderRadius.circular(7),
              border: Border.all(
                color: const Color(0xffffc857).withValues(alpha: 0.38),
              ),
            ),
            child: ExpansionTile(
              key: const Key('model-training-advanced-commands'),
              initiallyExpanded: false,
              tilePadding: const EdgeInsets.symmetric(horizontal: 10),
              childrenPadding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
              iconColor: const Color(0xffffc857),
              collapsedIconColor: const Color(0xffffc857),
              title: const Text(
                'Local LLM approval and advanced commands',
                style: TextStyle(
                  color: Color(0xffffc857),
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                ),
              ),
              subtitle: const Text(
                'Exact approval is required. New weights are evaluated but never auto-deployed.',
                style: TextStyle(
                  color: Color(0xffc4cede),
                  fontSize: 11,
                  height: 1.35,
                ),
              ),
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: SelectableText(
                    loraSteps.isEmpty
                        ? 'No manual fallback or canary commands recorded yet.'
                        : loraSteps.map((step) => '- $step').join('\n'),
                    key: const Key('model-training-advanced-command-text'),
                    style: const TextStyle(
                      color: Color(0xffd7e4ef),
                      fontFamily: 'Consolas',
                      fontSize: 11.5,
                      height: 1.35,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              Tooltip(
                message:
                    'Pushes captured packs, rebuilds the dataset, and trains '
                    'the selected SLM and/or local LLM targets. LLM training '
                    'requires exact approval and never auto-deploys.',
                child: FilledButton.icon(
                  key: const Key('model-training-run-cycle'),
                  onPressed: cycleRunning || _running || _trainingControlsLocked
                      ? null
                      : () => unawaited(_confirmRealTrainingCycleFromUi()),
                  icon: Icon(
                    cycleRunning ? Icons.hourglass_top : Icons.play_arrow,
                    size: 17,
                  ),
                  label: Text(
                    cycleRunning
                        ? 'Training cycle running…'
                        : 'Train Selected Models',
                  ),
                ),
              ),
              Tooltip(
                message:
                    'Re-reads the cycle, pack, and roster receipts from disk. '
                    'Nothing is started.',
                child: OutlinedButton.icon(
                  key: const Key('model-training-refresh'),
                  onPressed: _modelTrainingReceiptsRefreshing
                      ? null
                      : () => unawaited(_refreshModelTrainingReceipts()),
                  icon: Icon(
                    _modelTrainingReceiptsRefreshing
                        ? Icons.sync
                        : Icons.refresh,
                    size: 17,
                  ),
                  label: Text(
                    _modelTrainingReceiptsRefreshing
                        ? 'Reading…'
                        : 'Refresh Receipts',
                  ),
                ),
              ),
            ],
          ),
          if (_modelTrainingCycleResult.isNotEmpty) ...[
            const SizedBox(height: 8),
            Semantics(
              container: true,
              liveRegion: true,
              label: 'Model training: $_modelTrainingCycleResult',
              excludeSemantics: true,
              child: Text(
                _modelTrainingCycleResult,
                key: const Key('model-training-cycle-result'),
                style: TextStyle(
                  color: _modelTrainingCycleResultIsError
                      ? const Color(0xffe06c75)
                      : const Color(0xff5fd0a8),
                  fontSize: 11.5,
                  height: 1.35,
                ),
              ),
            ),
          ],
          const SizedBox(height: 6),
          Text(
            _modelTrainingReceiptsFreshnessLabel,
            key: const Key('model-training-receipts-freshness'),
            style: const TextStyle(color: Color(0xff8793aa), fontSize: 11),
          ),
        ],
      ),
    );
  }

  /// One labelled slider block of the Training page. Duration, level, and
  /// frequency all share this structure, and the shared lock guard
  /// (_running || _trainingControlsLocked) lives here so a future slider
  /// cannot forget it.
  Widget _trainingSliderSection({
    required String title,
    required String valueLabel,
    required Key valueKey,
    required Widget caption,
    required Key semanticsKey,
    required String semanticsLabel,
    required String semanticsValue,
    required Key sliderKey,
    required double value,
    required double min,
    required double max,
    required int? divisions,
    required String Function(double value) semanticFormatter,
    required ValueChanged<double> onChanged,
    required List<String> endpointLabels,
  }) {
    final locked = _running || _trainingControlsLocked;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                title,
                style: const TextStyle(
                  color: Color(0xfff0f4ff),
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            Text(
              valueLabel,
              key: valueKey,
              style: const TextStyle(
                color: Color(0xff00e5ff),
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
        const SizedBox(height: 2),
        caption,
        MergeSemantics(
          key: semanticsKey,
          child: Semantics(
            label: semanticsLabel,
            value: semanticsValue,
            child: Slider(
              key: sliderKey,
              value: value.clamp(min, max).toDouble(),
              min: min,
              max: max,
              divisions: divisions,
              semanticFormatterCallback: semanticFormatter,
              onChanged: locked
                  ? null
                  : (newValue) => setState(() => onChanged(newValue)),
              onChangeEnd: locked
                  ? null
                  : (_) => unawaited(_saveUiPreferences()),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              for (final label in endpointLabels)
                Text(
                  label,
                  style: const TextStyle(
                    color: Color(0xff8793aa),
                    fontSize: 11,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _trainingPage() {
    return _PageFrame(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 920),
          child: SingleChildScrollView(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'Training',
                    style: TextStyle(
                      color: Color(0xfff7f7fb),
                      fontSize: 34,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0,
                    ),
                  ),
                  const SizedBox(height: 6),
                  if (_running) ...[
                    _busyNotice(
                      'training-work-notice',
                      _chatRunning
                          ? 'Engel is answering a chat. Your Training choices are saved. Stop the chat or wait for it to finish before starting Training.'
                          : 'Engel is finishing another task. Your Training choices are saved, and the controls will be available when it finishes.',
                    ),
                    const SizedBox(height: 10),
                  ],
                  _macToolPanel(
                    title: 'Prompt Training',
                    icon: Icons.school,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _macSettingLine(
                          label: 'Prompt library',
                          value: _trainingMaximumPromptCount > 0
                              ? '$_trainingMaximumPromptCount scheduled prompts across $_trainingHourlyCycleCount hourly topics'
                              : 'Not scanned yet — choose Prepare Files below',
                          icon: Icons.library_books_outlined,
                        ),
                        _trainingCurriculumPicker(),
                        _trainingModelTargetsSelector(),
                        Tooltip(
                          message:
                              'The prepared library has up to '
                              '$_trainingPromptTemplateCount prompts for each hourly topic.',
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 8,
                            ),
                            margin: const EdgeInsets.only(bottom: 8),
                            decoration: BoxDecoration(
                              color: const Color(0xff151b27),
                              borderRadius: BorderRadius.circular(7),
                              border: Border.all(
                                color: const Color(0xff334157),
                              ),
                            ),
                            child: Row(
                              children: [
                                const Icon(
                                  Icons.schedule_outlined,
                                  color: Color(0xff00e5ff),
                                  size: 18,
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          _trainingPlanSummary,
                                          key: const Key(
                                            'training-plan-summary',
                                          ),
                                          style: const TextStyle(
                                            color: Color(0xffd8e5f4),
                                            fontSize: 12,
                                            fontWeight: FontWeight.w700,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Tooltip(
                                        message:
                                            'Training choices save automatically.',
                                        child: Semantics(
                                          key: const Key(
                                            'training-preferences-save-note',
                                          ),
                                          label:
                                              'Training choices save automatically.',
                                          child: const Icon(
                                            Icons.cloud_done_outlined,
                                            size: 17,
                                            color: Color(0xff79f0ad),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        Tooltip(
                          message: _trainingManifestProblems.isEmpty
                              ? 'All required files are present.'
                              : _selectedCurriculumHasManifestProblem(
                                  _selectedTrainingCurriculum,
                                )
                              ? 'The selected curriculum has a provenance issue. Prepare Files and review its binding before starting.'
                              : 'Some other curriculum provenance needs review. The selected plan is checked independently.',
                          child: _macSettingLine(
                            label: 'Readiness',
                            value: !_trainingFilesPresent
                                ? _trainingAssetStatus
                                : _selectedCurriculumHasManifestProblem(
                                    _selectedTrainingCurriculum,
                                  )
                                ? 'Selected curriculum binding needs review'
                                : _trainingMissingCount == 0
                                ? 'Files ready — all required assets present'
                                : '$_trainingMissingCount assets missing',
                            icon: Icons.monitor_heart,
                          ),
                        ),
                        if (_trainingMissingCount > 0)
                          _trainingMissingAssetsNotice(),
                        _trainingCompactStatus(),
                        _trainingActions(),
                        const SizedBox(height: 10),
                        _trainingSliderSection(
                          title: 'Training duration',
                          valueLabel: _trainingHourLabel(),
                          valueKey: const Key('training-hours-value'),
                          caption: Text(
                            'Choose how long Engel should keep practicing. '
                            'This curriculum has $_selectedTrainingMaximumHours distinct '
                            '${_selectedTrainingMaximumHours == 1 ? 'hour' : 'hours'} available.',
                            style: const TextStyle(
                              color: Color(0xffaeb8cb),
                              fontSize: 12,
                            ),
                          ),
                          semanticsKey: const Key('training-hours-semantics'),
                          semanticsLabel: 'Training duration',
                          semanticsValue: _trainingHourLabel(),
                          sliderKey: const Key('training-hours-slider'),
                          value: _trainingHours.toDouble(),
                          min: 1,
                          max: _selectedTrainingMaximumHours.toDouble(),
                          divisions: _selectedTrainingMaximumHours > 1
                              ? _selectedTrainingMaximumHours - 1
                              : null,
                          semanticFormatter: (value) =>
                              _trainingHourLabel(value.round()),
                          onChanged: (value) => _trainingHours = value
                              .round()
                              .clamp(1, _selectedTrainingMaximumHours),
                          endpointLabels: [
                            '1 hour',
                            _trainingHourLabel(_selectedTrainingMaximumHours),
                          ],
                        ),
                        const SizedBox(height: 8),
                        _trainingSliderSection(
                          title: 'Training level',
                          valueLabel: _trainingLevelLabel,
                          valueKey: const Key('training-level-value'),
                          caption: Text(
                            _trainingLevelDescription,
                            key: const Key('training-level-description'),
                            style: const TextStyle(
                              color: Color(0xffaeb8cb),
                              fontSize: 12,
                            ),
                          ),
                          semanticsKey: const Key('training-level-semantics'),
                          semanticsLabel: 'Training level',
                          semanticsValue:
                              '$_trainingLevelLabel. $_trainingLevelDescription',
                          sliderKey: const Key('training-level-slider'),
                          value: _trainingLevelIndex.toDouble(),
                          min: 0,
                          max: 3,
                          divisions: 3,
                          semanticFormatter: (value) {
                            final index = math.min(
                              _trainingLevelLabels.length - 1,
                              math.max(0, value.round()),
                            );
                            return '${_trainingLevelLabels[index]}. '
                                '${_trainingLevelDescriptionForIndex(index)}';
                          },
                          onChanged: (value) =>
                              _trainingLevelIndex = value.round(),
                          endpointLabels: const [
                            'Expert',
                            'Principal',
                            'Distinguished',
                            'Fellow',
                          ],
                        ),
                        const SizedBox(height: 8),
                        _trainingSliderSection(
                          title: 'Trainings per hour',
                          valueLabel: _trainingsPerHourLabel,
                          valueKey: const Key('training-frequency-value'),
                          caption: const Text(
                            'Choose how many training prompts Engel runs each hour.',
                            style: TextStyle(
                              color: Color(0xffaeb8cb),
                              fontSize: 12,
                            ),
                          ),
                          semanticsKey: const Key(
                            'training-frequency-semantics',
                          ),
                          semanticsLabel: 'Trainings per hour',
                          semanticsValue: _trainingsPerHourSemanticLabel(),
                          sliderKey: const Key('training-frequency-slider'),
                          value: _trainingsPerHour.toDouble(),
                          min: 1,
                          max: 10,
                          divisions: 9,
                          semanticFormatter: (value) =>
                              _trainingsPerHourSemanticLabel(value.round()),
                          onChanged: (value) =>
                              _trainingsPerHour = value.round(),
                          endpointLabels: const ['1 per hour', '10 per hour'],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  KeyedSubtree(
                    key: const Key('training-run-panel'),
                    child: _macToolPanel(
                      title: 'Training Status',
                      icon: _trainingRunActive
                          ? Icons.model_training
                          : Icons.monitor_heart_outlined,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Semantics(
                            key: const Key('training-status-announcement'),
                            container: true,
                            liveRegion: true,
                            label:
                                'Training status: $_trainingRunStatus. '
                                '$_trainingRunDetail',
                            excludeSemantics: true,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                _macSettingLine(
                                  label: 'Run status',
                                  value: _trainingRunStatus,
                                  icon: _trainingRunActive
                                      ? Icons.play_circle_outline
                                      : Icons.info_outline,
                                ),
                                Text(
                                  _trainingRunDetail,
                                  key: const Key('training-run-detail'),
                                  style: const TextStyle(
                                    color: Color(0xffc4cede),
                                    height: 1.35,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 10),
                          _macSettingLine(
                            label: _trainingRunActive
                                ? 'Current run progress'
                                : _trainingRunIsPrevious
                                ? 'Previous run progress'
                                : 'Progress',
                            value: _trainingRequestedPrompts > 0
                                ? '$_trainingCompletedPrompts / $_trainingRequestedPrompts prompts'
                                : 'No prompts scheduled',
                            icon: Icons.checklist,
                          ),
                          if (_trainingSecondsToNextPrompt != null)
                            _macSettingLine(
                              label: 'Next prompt',
                              value: _formatTrainingTime(
                                _trainingSecondsToNextPrompt!,
                              ),
                              icon: Icons.schedule,
                            ),
                          if (_trainingSecondsRemaining != null)
                            _macSettingLine(
                              label: 'Time remaining',
                              value: _formatTrainingTime(
                                _trainingSecondsRemaining!,
                              ),
                              icon: Icons.timelapse,
                            ),
                          if (_trainingLastLog.isNotEmpty)
                            _macSettingLine(
                              label: 'Log',
                              value: _trainingLastLog,
                              icon: Icons.article_outlined,
                            ),
                          const SizedBox(height: 10),
                          LinearProgressIndicator(
                            key: const Key('training-run-progress'),
                            value: _trainingRequestedPrompts > 0
                                ? (_trainingCompletedPrompts /
                                          _trainingRequestedPrompts)
                                      .clamp(0.0, 1.0)
                                : _trainingRunActive
                                ? null
                                : 0,
                            minHeight: 7,
                            borderRadius: BorderRadius.circular(99),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  _modelTrainingPanel(),
                  const SizedBox(height: 12),
                  ExpansionTile(
                    key: const Key('training-files-tools'),
                    title: const Text(
                      'Training files',
                      style: TextStyle(fontWeight: FontWeight.w800),
                    ),
                    subtitle: const Text(
                      'Prompt templates, manifests, and previous run logs.',
                    ),
                    childrenPadding: const EdgeInsets.only(top: 6),
                    children: [
                      _macToolPanel(
                        title: 'Training file locations',
                        icon: Icons.folder_copy,
                        child: Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            OutlinedButton.icon(
                              onPressed: () => unawaited(
                                _revealFileInExplorer(trainingCanonicalRoot),
                              ),
                              icon: const Icon(Icons.folder_open, size: 17),
                              label: const Text('Open prompt folder'),
                            ),
                            OutlinedButton.icon(
                              onPressed: () => unawaited(
                                _revealFileInExplorer(
                                  trainingMixedTemplatePath,
                                ),
                              ),
                              icon: const Icon(Icons.list_alt, size: 17),
                              label: const Text('Open prompt template'),
                            ),
                            OutlinedButton.icon(
                              onPressed: () => unawaited(
                                _revealFileInExplorer(
                                  _resolvedTrainingAssetsManifestPath,
                                ),
                              ),
                              icon: const Icon(Icons.receipt_long, size: 17),
                              label: const Text('Open asset list'),
                            ),
                            OutlinedButton.icon(
                              onPressed: () => unawaited(
                                _revealFileInExplorer(
                                  '$trainingCanonicalRoot\\runs\\ui_prompt',
                                ),
                              ),
                              icon: const Icon(Icons.article, size: 17),
                              label: const Text('Open previous runs'),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  SizedBox(height: 260, child: _outputPanel()),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
