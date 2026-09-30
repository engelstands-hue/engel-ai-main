import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:engel_flutter_main/discord_desk_chat_page.dart';

void main() {
  test('template discord lines stay out of the room', () {
    expect(
      discordChatLineIsTemplate(
        'Engel Memory. No receipt file is there. collab if this helps the house.',
      ),
      isTrue,
    );
    expect(
      discordChatLineIsTemplate(
        'Engel Research posted today\'s public competition board. 6 titles are in the research forum.',
      ),
      isFalse,
    );
    expect(
      discordMouthPresence('Memory', const [
        EngelRoomLine(author: 'Engel Memory', text: 'Receipt saved.'),
      ]),
      'Online',
    );
    expect(
      discordMouthPresence('Ops', const [
        EngelRoomLine(author: 'Engel Memory', text: 'Receipt saved.'),
      ]),
      'Quiet',
    );
  });

  testWidgets('quiet room stays quiet and the desk manager still tunes a bot', (
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
    expect(find.text('Online'), findsNothing);
    expect(find.text('Quiet'), findsWidgets);

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
