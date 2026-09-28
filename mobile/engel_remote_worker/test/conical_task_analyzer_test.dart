import 'dart:convert';

import 'package:engel_remote_worker/conical_task_analyzer.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const assignment = '''
Engel conical job: job-1
Assigned role: requirements analyst
Bounded task: analyze the requested build.

User request:
Build a local Python web app. Let me choose a directory of JSON receipts. Show worker returns, model route, package path, rollback proof, and final status.
''';

  test(
    'requirements analysis is task-specific and excludes capability dumps',
    () {
      final parsed =
          jsonDecode(
                ConicalTaskAnalyzer.analyze(
                  taskType: 'conical_requirements_analysis',
                  title: 'requirements',
                  assignmentText: assignment,
                ),
              )
              as Map<String, dynamic>;
      expect(parsed['schema'], 'engel_android_conical_requirements_v1');
      expect(parsed['analysis_engine'], 'on_device_deterministic_conical_v1');
      expect(parsed['inputs'], contains('JSON receipt files'));
      expect(parsed['outputs'], contains('per-worker result view'));
      expect(jsonEncode(parsed), isNot(contains('device_capabilities')));
    },
  );

  test('verification plan includes input and preview failure states', () {
    final parsed =
        jsonDecode(
              ConicalTaskAnalyzer.analyze(
                taskType: 'conical_verification_plan',
                title: 'verification',
                assignmentText: assignment,
              ),
            )
            as Map<String, dynamic>;
    final checks = (parsed['test_matrix'] as List<dynamic>)
        .map((item) => (item as Map<String, dynamic>)['check'])
        .toList();
    expect(checks, contains('directory states'));
    expect(checks, contains('JSON states'));
    expect(checks, contains('web preview'));
  });

  test('underspecified elder app expands into real requirements', () {
    const elderAssignment = '''
Engel conical job: job-elder
Assigned role: requirements analyst
Bounded task: analyze the requested build.

User request:
Create me a App for Elders
''';
    final parsed =
        jsonDecode(
              ConicalTaskAnalyzer.analyze(
                taskType: 'conical_requirements_analysis',
                title: 'requirements',
                assignmentText: elderAssignment,
              ),
            )
            as Map<String, dynamic>;
    final requirements = (parsed['functional_requirements'] as List<dynamic>)
        .map((item) => item.toString())
        .toList();
    expect(requirements.length, greaterThan(1));
    expect(
      requirements.join(' ').toLowerCase(),
      contains('emergency'),
    );
    expect(
      requirements.join(' ').toLowerCase(),
      contains('reminders'),
    );
  });

  test('risk analysis remains offline and CT246-centered', () {
    final parsed =
        jsonDecode(
              ConicalTaskAnalyzer.analyze(
                taskType: 'conical_dependency_risk_check',
                title: 'risk',
                assignmentText: assignment,
              ),
            )
            as Map<String, dynamic>;
    expect(
      parsed['dependencies'],
      contains('Strict JSON parsing with per-file error isolation'),
    );
    expect(
      parsed['offline_constraints'],
      contains('All active artifacts and receipts remain on CT246 SSD paths.'),
    );
  });
}
