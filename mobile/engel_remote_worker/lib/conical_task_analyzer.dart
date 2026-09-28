import 'dart:convert';

class ConicalTaskAnalyzer {
  static const Set<String> supportedTaskTypes = <String>{
    'conical_requirements_analysis',
    'conical_verification_plan',
    'conical_dependency_risk_check',
  };

  static bool supports(String taskType) =>
      supportedTaskTypes.contains(taskType);

  static String analyze({
    required String taskType,
    required String title,
    required String assignmentText,
  }) {
    final request = _operatorRequest(assignmentText);
    final requirements = _requirements(request);
    final payload = switch (taskType) {
      'conical_requirements_analysis' => _requirementsPayload(
        title,
        request,
        requirements,
      ),
      'conical_verification_plan' => _verificationPayload(
        title,
        request,
        requirements,
      ),
      'conical_dependency_risk_check' => _riskPayload(
        title,
        request,
        requirements,
      ),
      _ => <String, Object?>{
        'schema': 'engel_android_conical_analysis_v1',
        'title': title,
        'status': 'unsupported_task_type',
      },
    };
    return const JsonEncoder.withIndent('  ').convert(payload);
  }

  static Map<String, Object?> _requirementsPayload(
    String title,
    String request,
    List<String> requirements,
  ) {
    return <String, Object?>{
      'schema': 'engel_android_conical_requirements_v1',
      'title': title,
      'role': 'requirements_analyst',
      'request_summary': _bounded(request, 700),
      'functional_requirements': requirements,
      'inputs': _inputs(request),
      'outputs': _outputs(request),
      'acceptance_criteria': requirements
          .map((item) => 'Visible proof confirms: $item')
          .toList(growable: false),
      'analysis_engine': 'on_device_deterministic_conical_v1',
      'status': 'candidate_only',
      'human_review_required': true,
    };
  }

  static Map<String, Object?> _verificationPayload(
    String title,
    String request,
    List<String> requirements,
  ) {
    final low = request.toLowerCase();
    final tests = <Map<String, String>>[
      <String, String>{
        'check': 'startup',
        'proof':
            'Entry point starts successfully and returns a readable UI or result.',
      },
      <String, String>{
        'check': 'requirements',
        'proof':
            'Each of the ${requirements.length} extracted requirements has one visible assertion.',
      },
      if (low.contains('directory') || low.contains('folder'))
        <String, String>{
          'check': 'directory states',
          'proof':
              'Valid, empty, missing, and unreadable directories are handled without a crash.',
        },
      if (low.contains('json'))
        <String, String>{
          'check': 'JSON states',
          'proof':
              'Valid, malformed, partial, and empty JSON files produce deterministic results.',
        },
      if (low.contains('web') ||
          low.contains('http') ||
          low.contains('app') ||
          low.contains('application'))
        <String, String>{
          'check': 'web preview',
          'proof':
              'Local preview returns HTTP 200 and renders the requested fields.',
        },
      if (low.contains('package') || low.contains('zip'))
        <String, String>{
          'check': 'package',
          'proof': 'Package exists, opens, and has a recorded SHA-256 digest.',
        },
      if (low.contains('rollback'))
        <String, String>{
          'check': 'rollback',
          'proof':
              'Rollback location exists and is displayed from receipt data.',
        },
    ];
    return <String, Object?>{
      'schema': 'engel_android_conical_verification_v1',
      'title': title,
      'role': 'verification_planner',
      'request_summary': _bounded(request, 700),
      'test_matrix': tests,
      'terminal_success_rule':
          'Do not claim completion unless every required worker return and build verification pass.',
      'analysis_engine': 'on_device_deterministic_conical_v1',
      'status': 'candidate_only',
      'human_review_required': true,
    };
  }

  static Map<String, Object?> _riskPayload(
    String title,
    String request,
    List<String> requirements,
  ) {
    final low = request.toLowerCase();
    final dependencies = <String>[
      if (low.contains('python'))
        'Python runtime and standard-library compatibility',
      if (low.contains('web') ||
          low.contains('app') ||
          low.contains('application'))
        'Local HTTP server and browser rendering',
      if (low.contains('json'))
        'Strict JSON parsing with per-file error isolation',
      if (low.contains('directory') || low.contains('folder'))
        'Bounded filesystem access to the operator-selected directory',
      if (low.contains('package') || low.contains('zip'))
        'Repeatable local archive creation and hashing',
      if (low.contains('receipt')) 'Stable Engel receipt schema handling',
    ];
    if (dependencies.isEmpty) {
      dependencies.add(
        'Requested runtime and deterministic local file handling',
      );
    }
    final risks = <String>[
      'Malformed or mixed-schema input could hide a job unless errors remain visible.',
      'Missing worker fields must be shown as unknown, not silently treated as success.',
      if (low.contains('directory') || low.contains('folder'))
        'Large directory scans need bounded file size and count limits.',
      if (low.contains('web'))
        'Preview assets must remain local so offline operation does not regress.',
      if (low.contains('rollback'))
        'Rollback proof must come from a receipt, not inferred static text.',
    ];
    return <String, Object?>{
      'schema': 'engel_android_conical_dependency_risk_v1',
      'title': title,
      'role': 'dependency_and_risk_checker',
      'request_summary': _bounded(request, 700),
      'dependencies': dependencies,
      'risks': risks,
      'offline_constraints': <String>[
        'No CDN, remote font, or provider call is required at runtime.',
        'All active artifacts and receipts remain on CT246 SSD paths.',
      ],
      'deterministic_checks': <String>[
        'Run the build twice against the same fixture and compare normalized output.',
        'Reject path traversal and continue after one malformed input file.',
        'Verify all ${requirements.length} extracted requirement records are represented.',
      ],
      'analysis_engine': 'on_device_deterministic_conical_v1',
      'status': 'candidate_only',
      'human_review_required': true,
    };
  }

  static String _operatorRequest(String text) {
    const marker = 'User request:';
    final index = text.lastIndexOf(marker);
    final selected = index >= 0 ? text.substring(index + marker.length) : text;
    return selected.replaceAll(RegExp(r'\s+'), ' ').trim();
  }

  static List<String> _requirements(String request) {
    final normalized = request.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (normalized.isEmpty) {
      return <String>['Return a readable result for the supplied request.'];
    }
    final clauses = normalized
        .split(RegExp(r'(?<=[.!?;])\s+'))
        .map((item) => item.replaceFirst(RegExp(r'^[-: ]+'), '').trim())
        .where((item) => item.length >= 8)
        .map((item) => _bounded(item, 260))
        .toList(growable: true);
    for (final item in _impliedAudienceAppRequirements(normalized)) {
      if (!clauses.contains(item)) {
        clauses.add(item);
      }
    }
    final selected = clauses.take(10).toList(growable: false);
    return selected.isEmpty ? <String>[_bounded(normalized, 260)] : selected;
  }

  static List<String> _impliedAudienceAppRequirements(String request) {
    final low = request.toLowerCase();
    final isApp = RegExp(
      r'\b(app|application|website|web app|webpage)\b',
    ).hasMatch(low);
    if (!isApp) {
      return const <String>[];
    }
    if (RegExp(r'\b(elder|elderly|senior|older adult)').hasMatch(low)) {
      return const <String>[
        'Extra-large high-contrast text and extra-large tappable buttons.',
        'Home screen with emergency help, today reminders, contacts, and notes.',
        'Reminders can be added and completed for medication, appointments, and meals.',
        'Contacts store a name and phone number and show them in large type.',
      ];
    }
    return const <String>[];
  }

  static List<String> _inputs(String request) {
    final low = request.toLowerCase();
    final values = <String>[
      if (low.contains('directory') || low.contains('folder'))
        'operator-selected directory',
      if (low.contains('json')) 'JSON receipt files',
      if (low.contains('worker')) 'worker return records',
      if (low.contains('model')) 'model route metadata',
      if (low.contains('rollback')) 'rollback receipt metadata',
    ];
    return values.isEmpty ? <String>['operator request'] : values;
  }

  static List<String> _outputs(String request) {
    final low = request.toLowerCase();
    final values = <String>[
      if (low.contains('web')) 'local web interface',
      if (low.contains('status')) 'visible terminal status',
      if (low.contains('package')) 'verified package path and digest',
      if (low.contains('proof')) 'durable proof view',
      if (low.contains('worker')) 'per-worker result view',
    ];
    return values.isEmpty ? <String>['reviewable candidate result'] : values;
  }

  static String _bounded(String text, int limit) {
    if (text.length <= limit) return text;
    return '${text.substring(0, limit)}...';
  }
}
