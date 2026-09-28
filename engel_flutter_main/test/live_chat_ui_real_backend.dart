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
    'live chat composer returns Engel AI Main natural reply through real backend',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1800, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(const EngelMainApp(enableStartupTasks: false));
      await tester.pump();

      await tapSideSection(tester, 'chat_runtime');

      const prompt =
          'Joshua says the chat feels robotic. Reply as Engel AI Main in a natural, direct way, one short paragraph, like a real person not a bot.';
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

      final naturalReply = find.textContaining(
        'You are right, Joshua. I am Engel AI Main',
      );
      for (var i = 0; i < 240 && naturalReply.evaluate().isEmpty; i++) {
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(seconds: 1)),
        );
        await tester.pump();
      }

      expect(naturalReply, findsWidgets);
      expect(find.textContaining('not like a help desk'), findsWidgets);
      expect(find.textContaining('Engel Error'), findsNothing);
      expect(find.textContaining('no readable assistant answer'), findsNothing);
    },
    timeout: const Timeout(Duration(minutes: 5)),
  );
}
