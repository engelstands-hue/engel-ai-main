import 'package:engel_flutter_main/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Future<void> tapSideSection(WidgetTester tester, String sectionId) async {
  await tester.enterText(find.byKey(const Key('section-search')), sectionId);
  await tester.pump();
  final finder = find.byKey(Key('section-$sectionId'));
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

void main() {
  testWidgets(
    'live chat UI creates a Mission Control artifact through CT246',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1800, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
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

      final createdReply = find.textContaining('Mission Control created');
      final receiptPath = find.textContaining('final_receipt.md');
      for (
        var i = 0;
        i < 360 &&
            (createdReply.evaluate().isEmpty || receiptPath.evaluate().isEmpty);
        i++
      ) {
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(seconds: 1)),
        );
        await tester.pump();
      }

      expect(createdReply, findsWidgets);
      expect(receiptPath, findsWidgets);
      expect(find.textContaining('ui_mission_control_demo'), findsWidgets);
      expect(find.textContaining('Engel Error'), findsNothing);
      expect(find.textContaining('timed out'), findsNothing);
    },
    timeout: const Timeout(Duration(minutes: 7)),
  );
}
