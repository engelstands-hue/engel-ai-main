import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:engel_flutter_main/token_usage_warning.dart';

void main() {
  test('accepts only an explicit trusted usage and limit pair', () {
    final snapshot = TokenUsageSnapshot.fromResponse({
      'receipt': {
        'token_usage': {
          'schema': 'engel_token_usage_v1',
          'trusted': true,
          'used_tokens': 750,
          'token_limit': 1000,
          'provider': 'Example provider',
        },
      },
    });
    expect(snapshot, isNotNull);
    expect(snapshot!.usedTokens, 750);
    expect(snapshot.tokenLimit, 1000);
    expect(snapshot.providerName, 'Example provider');
    expect(snapshot.percent, 75);
  });

  test('does not turn max_tokens or untrusted text into a quota', () {
    expect(
      TokenUsageSnapshot.fromResponse({
        'max_tokens': 1000,
        'assistant_reply': '{"used_tokens": 900, "token_limit": 1000}',
      }),
      isNull,
    );
    expect(
      TokenUsageSnapshot.fromResponse({
        'usage': {'used_tokens': 900, 'token_limit': 1000},
      }),
      isNull,
    );
  });

  test('stays quiet below 75 percent and rejects unknown limits', () {
    expect(
      tokenUsageWarningLevel(usedTokens: 749, tokenLimit: 1000),
      TokenUsageWarningLevel.none,
    );
    expect(
      tokenUsageWarningLevel(usedTokens: 1, tokenLimit: 0),
      TokenUsageWarningLevel.none,
    );
  });

  testWidgets('warns at 75 percent and explains provider upgrade path', (
    tester,
  ) async {
    expect(
      tokenUsageWarningLevel(usedTokens: 750, tokenLimit: 1000),
      TokenUsageWarningLevel.approachingLimit,
    );
    await tester.pumpWidget(
      const MaterialApp(
        home: TokenUsageWarning(
          usedTokens: 750,
          tokenLimit: 1000,
          providerName: 'Example provider',
        ),
      ),
    );
    expect(find.textContaining('75% warning'), findsOneWidget);
    expect(find.textContaining('upgrade your plan'), findsOneWidget);
  });

  testWidgets('reports 100 percent without discarding unfinished work', (
    tester,
  ) async {
    expect(
      tokenUsageWarningLevel(usedTokens: 1000, tokenLimit: 1000),
      TokenUsageWarningLevel.limitReached,
    );
    await tester.pumpWidget(
      const MaterialApp(
        home: TokenUsageWarning(
          usedTokens: 1000,
          tokenLimit: 1000,
          providerName: 'Example provider',
        ),
      ),
    );
    expect(find.text('Token limit reached'), findsOneWidget);
    expect(find.textContaining('unfinished work is saved'), findsOneWidget);
    expect(find.textContaining('add API billing'), findsOneWidget);
  });
}
