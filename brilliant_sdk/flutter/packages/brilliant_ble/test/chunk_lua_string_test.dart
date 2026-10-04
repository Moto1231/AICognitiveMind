import 'dart:convert';

import 'package:brilliant_ble/brilliant_device.dart';
import 'package:flutter_test/flutter_test.dart';

/// Applies the same escaping that uploadScript performs before chunking.
String escapeLua(String fileContents) {
  return fileContents
      .replaceAll('\\', '\\\\')
      .replaceAll("\r\n", "\\n")
      .replaceAll("\n", "\\n")
      .replaceAll("'", "\\'")
      .replaceAll('"', '\\"');
}

void main() {
  group('chunkLuaString', () {
    void expectValidChunks(String escaped, int maxChunkBytes) {
      final chunks = chunkLuaString(utf8.encode(escaped), maxChunkBytes);

      // Reassembles to the original
      expect(chunks.join(), escaped);

      for (final chunk in chunks) {
        // Every chunk fits the byte budget
        expect(utf8.encode(chunk).length, lessThanOrEqualTo(maxChunkBytes));

        // No chunk ends mid-escape: an odd run of trailing backslashes
        // would leave the closing quote of f:write('...') escaped
        var trailing = 0;
        while (trailing < chunk.length &&
            chunk[chunk.length - 1 - trailing] == '\\') {
          trailing++;
        }
        expect(trailing.isEven, isTrue,
            reason: 'chunk ends mid-escape: ...${chunk.substring(chunk.length - trailing)}');
      }
    }

    test('multi-byte characters never split or exceed the byte budget', () {
      // 45° repeated: each ° is 2 bytes in UTF-8, so character-based
      // chunking would overshoot the budget (the original bug)
      final script = List.filled(50, 'print("45°")').join('\n');
      expectValidChunks(escapeLua(script), 20);
    });

    test('4-byte characters (emoji) survive chunking at awkward budgets', () {
      final script = '\u{1F600}' * 30;
      for (var budget = 4; budget <= 9; budget++) {
        expectValidChunks(script, budget);
      }
    });

    test('escape sequences are not split across chunks', () {
      final script = escapeLua("a'b\"c\\d\ne" * 20);
      for (var budget = 3; budget <= 12; budget++) {
        expectValidChunks(script, budget);
      }
    });

    test('runs of escaped backslashes split only between pairs', () {
      final script = escapeLua('\\' * 10);
      for (var budget = 2; budget <= 7; budget++) {
        expectValidChunks(script, budget);
      }
    });

    test('plain ASCII chunks at exactly the budget', () {
      final chunks = chunkLuaString(utf8.encode('a' * 10), 4);
      expect(chunks, ['aaaa', 'aaaa', 'aa']);
    });

    test('empty payload yields no chunks', () {
      expect(chunkLuaString(utf8.encode(''), 10), isEmpty);
    });

    test('budget too small for the next character throws', () {
      expect(() => chunkLuaString(utf8.encode('°°'), 1),
          throwsArgumentError);
      expect(() => chunkLuaString(utf8.encode('ab'), 0), throwsArgumentError);
    });
  });
}
