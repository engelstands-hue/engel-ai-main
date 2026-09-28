import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:engel_flutter_main/discord_desk_chat_page.dart';

void main() {
  testWidgets('quiet room stays online and the desk manager still tunes a bot', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: EngelDiscordChatPage(live: false)),
      ),
    );

    expect(find.text('The room is quiet. No desk is speaking.'), findsOneWidget);
    expect(find.text('Speaking'), findsNothing);
    expect(find.text('Thinking'), findsNothing);
    expect(find.text('Online'), findsWidgets);

    await tester.pumpWidget(const EngelDeskManagerApp());
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('discord-desk-manager-popout')), findsOneWidget);
    expect(find.text('67.0'), findsOneWidget);

    await tester.tap(find.byKey(const Key('desk-select-support')));
    await tester.pumpAndSettle();
    expect(find.text('70.4'), findsOneWidget);

    await tester.drag(find.byType(Slider).first, const Offset(-120, 0));
    await tester.pumpAndSettle();
    expect(find.text('61%'), findsNothing);
  });
}
