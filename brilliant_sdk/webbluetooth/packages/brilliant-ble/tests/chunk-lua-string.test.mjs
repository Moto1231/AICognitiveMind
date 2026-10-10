// Unit tests for chunkLuaString. No device or test framework required:
// run with `npm test` (node --test) after `npm run build`.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { chunkLuaString } from '../dist/brilliant-ble.es.js';

// Applies the same escaping that uploadFileFromString performs before chunking
function escapeLua(content) {
    return content.replace(/\r/g, "")
                  .replace(/\\/g, "\\\\")
                  .replace(/\n/g, "\\n")
                  .replace(/\t/g, "\\t")
                  .replace(/'/g, "\\'")
                  .replace(/"/g, '\\"');
}

function assertValidChunks(escaped, maxChunkBytes) {
    const chunks = chunkLuaString(new TextEncoder().encode(escaped), maxChunkBytes);

    // Reassembles to the original
    assert.equal(chunks.join(""), escaped);

    for (const chunk of chunks) {
        // Every chunk fits the byte budget
        assert.ok(new TextEncoder().encode(chunk).byteLength <= maxChunkBytes);

        // No chunk ends mid-escape: an odd run of trailing backslashes
        // would leave the closing quote of f:write("...") escaped
        let trailing = 0;
        while (trailing < chunk.length && chunk[chunk.length - 1 - trailing] === "\\") {
            trailing++;
        }
        assert.equal(trailing % 2, 0, `chunk ends mid-escape: ...${chunk.slice(-trailing)}`);
    }
}

test('multi-byte characters never split or exceed the byte budget', () => {
    // 45° repeated: each ° is 2 bytes in UTF-8, so character-based
    // chunking would overshoot the budget (the original bug)
    const script = Array(50).fill('print("45°")').join('\n');
    assertValidChunks(escapeLua(script), 20);
});

test('4-byte characters (emoji) survive chunking at awkward budgets', () => {
    const script = '\u{1F600}'.repeat(30);
    for (let budget = 4; budget <= 9; budget++) {
        assertValidChunks(script, budget);
    }
});

test('escape sequences are not split across chunks', () => {
    const script = escapeLua("a'b\"c\\d\ne".repeat(20));
    for (let budget = 3; budget <= 12; budget++) {
        assertValidChunks(script, budget);
    }
});

test('runs of escaped backslashes split only between pairs', () => {
    const script = escapeLua('\\'.repeat(10));
    for (let budget = 2; budget <= 7; budget++) {
        assertValidChunks(script, budget);
    }
});

test('plain ASCII chunks at exactly the budget', () => {
    assert.deepEqual(chunkLuaString(new TextEncoder().encode('a'.repeat(10)), 4),
        ['aaaa', 'aaaa', 'aa']);
});

test('empty payload yields no chunks', () => {
    assert.deepEqual(chunkLuaString(new Uint8Array(0), 10), []);
});

test('budget too small for the next character throws', () => {
    assert.throws(() => chunkLuaString(new TextEncoder().encode('°°'), 1));
    assert.throws(() => chunkLuaString(new TextEncoder().encode('ab'), 0));
});
