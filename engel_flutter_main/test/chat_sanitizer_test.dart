import 'dart:convert';

import 'package:engel_flutter_main/main.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final replacement = String.fromCharCode(0xFFFD); // U+FFFD
  final emoji = String.fromCharCodes(const [0xD83D, 0xDE00]); // 😀 valid pair
  final loneHigh = String.fromCharCode(0xD83D);
  final loneLow = String.fromCharCode(0xDE00);
  final nul = String.fromCharCode(0);
  final tab = String.fromCharCode(9);
  final lf = String.fromCharCode(10);
  final cr = String.fromCharCode(13);

  group('sanitizeEngelChatTextForWorker', () {
    test('preserves a valid astral pair (emoji) unchanged', () {
      expect(sanitizeEngelChatTextForWorker('hi $emoji there'), 'hi $emoji there');
      expect(sanitizeEngelChatTextForWorker(emoji), emoji);
    });

    test('replaces a LONE HIGH surrogate (the worker-crash case) with U+FFFD', () {
      expect(sanitizeEngelChatTextForWorker(loneHigh), replacement);
      expect(sanitizeEngelChatTextForWorker('hi$loneHigh'), 'hi$replacement');
      expect(sanitizeEngelChatTextForWorker('${loneHigh}A'), '${replacement}A');
    });

    test('replaces a LONE LOW surrogate with U+FFFD', () {
      expect(sanitizeEngelChatTextForWorker(loneLow), replacement);
      expect(sanitizeEngelChatTextForWorker('a${loneLow}b'), 'a${replacement}b');
    });

    test('a sanitized string encodes to UTF-8 without throwing', () {
      final broken = 'paste ${String.fromCharCode(0xD800)} boom';
      final cleaned = sanitizeEngelChatTextForWorker(broken);
      expect(() => utf8.encode(cleaned), returnsNormally);
      expect(cleaned.codeUnits.any((u) => u >= 0xD800 && u <= 0xDFFF), isFalse);
    });

    test('strips disallowed control chars but keeps tab/newline/carriage', () {
      expect(sanitizeEngelChatTextForWorker('a${nul}bc'), 'abc');
      final kept = 'a${tab}b${lf}c${cr}d';
      expect(sanitizeEngelChatTextForWorker(kept), kept);
    });

    test('empty and plain strings pass through', () {
      expect(sanitizeEngelChatTextForWorker(''), '');
      expect(sanitizeEngelChatTextForWorker('normal text 123'), 'normal text 123');
    });
  });
}
