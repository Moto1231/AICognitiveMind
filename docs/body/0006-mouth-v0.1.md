# Body — Mouth V0.1

**Status:** First executable voice-output slice.

## Purpose

Mouth V0.1 proves the Body can express text as audible speech without installing a local
application runtime on the user's machine.

The application remains remote. The browser is the hardware bridge to the local speakers:

```text
VOICE ExpressionIntent
      ↓
BodyRuntime.speak_intent()
      ↓
BrowserVoiceOutput
      ↓
transient pending intent
      ↓ HTTPS
browser SpeechSynthesis
      ↓
local speakers
```

## Runtime boundary

The Codespace owns:

- the Body runtime;
- validation of voice intents;
- the transient voice-output queue;
- the API contract.

The browser owns only:

- enumerating browser/OS speech voices;
- constructing `SpeechSynthesisUtterance`;
- sending sound to the local speakers.

No local Python process is required.

## Voice ExpressionIntent

Mouth V0.1 supports:

```json
{
  "modality": "voice",
  "text": "Hello. The Body now has a voice.",
  "metadata": {
    "rate": 1.0,
    "pitch": 1.0,
    "volume": 1.0,
    "voice_name": null
  }
}
```

Validated ranges:

- rate: 0.1–10.0;
- pitch: 0.0–2.0;
- volume: 0.0–1.0.

A named voice is optional because the available voice catalog belongs to the browser/OS
environment.

## Memory boundary

Voice output is transient Body expression.

`BrowserVoiceOutput` keeps only the latest unconsumed voice intent. Once the browser consumes
it, that pending intent is cleared.

Mouth V0.1:

- creates no durable memory;
- writes no audio file;
- changes no identity or belief state;
- does not make a browser/OS voice part of identity.

## Browser proof

When the Codespace-hosted application is available, open:

```text
/body/mouth
```

The page lets the human:

1. choose an available browser/OS voice or use the browser default;
2. set rate, pitch, and volume;
3. enter text;
4. press **Speak through Body**.

The button first submits the command to the Body API. The page then consumes the returned
pending VOICE `ExpressionIntent` and hands it to browser speech synthesis.

## V0.1 success criterion

Mouth V0.1 is proven when pressing **Speak through Body** causes audible speech and the page
reports:

```text
MOUTH RECEIVED VOICE INTENT
```

The important proof is that speech travels through the Body expression boundary before the
browser drives the speakers.

## Deliberately not included yet

- canonical voice identity;
- cloud neural text-to-speech;
- generated audio files;
- lip synchronization;
- speech/emotion coupling;
- automatic speaking from Mind responses;
- interruption policy;
- continuous autonomous output.

Those belong after the basic voice-output path is proven.
