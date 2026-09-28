import 'package:engel_remote_worker/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Future<void> pumpApp(WidgetTester tester) async {
    tester.view.physicalSize = const Size(1200, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(const EngelRemoteWorkerApp());
    for (var index = 0; index < 8; index += 1) {
      await tester.pump(const Duration(milliseconds: 250));
    }
  }

  testWidgets(
    'New-tech operator page shows agent ready, brain, and pair controls.',
    (tester) async {
      await pumpApp(tester);

      expect(find.textContaining('Engel Remote Worker'), findsWidgets);
      expect(find.textContaining('android_worker_'), findsWidgets);
      expect(find.text('AGENT READY'), findsOneWidget);
      expect(find.textContaining('Brain ·'), findsOneWidget);
      expect(find.textContaining('Dedicated phone'), findsOneWidget);
      expect(find.widgetWithText(TextField, 'PC host'), findsOneWidget);
      expect(find.widgetWithText(TextField, 'pair code'), findsOneWidget);
      expect(find.text('Test Pairing'), findsOneWidget);
      expect(find.text('Check'), findsOneWidget);
      expect(find.text('Auto'), findsOneWidget);
      await tester.tap(find.text('Auto'));
      await tester.pump(const Duration(milliseconds: 250));
      expect(find.text('Pause'), findsOneWidget);
    },
  );

  testWidgets('unsafe command labels are absent', (tester) async {
    await pumpApp(tester);

    for (final label in <String>[
      'Apply Fix',
      'Execute',
      'Run Route',
      'Write Memory',
      'Promote',
      'Trust',
      'Control Engel',
      'Upload Result',
      'Download Packet',
    ]) {
      expect(find.text(label), findsNothing);
    }
  });
}
