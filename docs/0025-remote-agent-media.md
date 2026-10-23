# Remote agent audio and vision without Body

Axiom has two device interfaces. Self-hosted mode uses Body for full embodied
functionality. A remote reasoning host can instead use its own device adapter for
camera capture, microphone capture, and audio playback. Both interfaces use the
same existing `vision`, `audio` (Audio / Transcription), and `audio_voice`
(Audio / Voice) task assignments. No Body browser, session, check-in, Mouth queue,
or Body speech API is needed by the remote adapter.

## Existing task contract

Authenticated MCP `execute_task` supports:

| Task | Operation | Input | Output |
| --- | --- | --- | --- |
| `audio` | `transcribe` | Base64 audio, filename, MIME type | Transcription |
| `audio_voice` | `synthesize_voice` | `text` | Base64 MP3 and `audio/mpeg` |
| `vision` | `chat` | Messages with text and image content | Vision response |

Endpoint, model, provider fallback chain, behavior, voice reference, and saved
speaking rate/volume are resolved by Axiom. The remote host does not concatenate
provider URL suffixes, choose a replacement provider, or copy provider API keys.

Only an explicit `status: not_configured` from the voice task selects the local
Windows voice. Authentication failures, quota errors, and provider failures stay
failures. Unconfigured speech synthesis is never handed to a text reasoning host
as though it could manufacture audio bytes.

## Windows/Codex reference adapter

Install the optional local device dependencies on the user's computer:

```powershell
pip install -e '.[remote-media]'
```

The reference client uses the installed Codex app-server's authenticated MCP
connection, including its existing OAuth refresh storage. It opens an ephemeral
MCP transport context and makes direct tool calls. It never starts a reasoning
turn, resumes the user's chat, reads chat transcripts, or changes the selected
conversation model. No extra OpenAI API key is required for these tool calls.

```powershell
cognitive-mind-media camera .\camera.jpg
cognitive-mind-media record .\microphone.wav --seconds 5
cognitive-mind-media transcribe .\microphone.wav
cognitive-mind-media speak 'Hello from Axiom.' .\reply.mp3
cognitive-mind-media describe .\camera.jpg
```

`--codex` selects an explicit Codex executable and `--server` selects an existing
MCP server name (default `axiom`). These options go before the subcommand. The
client uses that configured connection; it has no hardcoded Render speech URL.
`speak --no-play` saves audio for a host's own player. Explicit Windows fallback
saves a WAV with a `.wav` suffix instead of labelling it as MP3. Camera and
microphone commands open local device APIs directly, release devices afterward,
and do not upload data unless a processing command is explicitly requested.

Camera defaults to device `0`; microphone defaults to the Windows input device.
Both support `--device`. `devices` lists the audio devices. Microphone capture is
bounded to 30 seconds. Camera currently captures one frame per command. Device
permission, busy-device errors, and provider errors are reported rather than
changing privacy settings or using Body as a hidden fallback.

## Completed-reply speech

A project-local Codex `Stop` hook can call:

```text
cognitive-mind-media hook --session-id CHAT_ID --state-dir LOCAL_RUNTIME_FOLDER
```

Use an asynchronous command hook. This mode consumes the native Stop input,
accepts only the specified chat, deduplicates completed turn IDs, and speaks
`last_assistant_message` through the saved Audio / Voice assignment. It returns
`{}` and never asks the reasoning agent to continue. Code blocks and memory
citation metadata are omitted from speech while the written answer is untouched.
Runtime status and generated audio remain in the selected local runtime folder;
failed turns are not automatically retried. Codex's normal exact-hook trust
review still applies; installing the package does not approve a hook.

This adapter supplies bounded media operations and completed-reply output. It
does not install an always-on listener, send dictated text into a conversation,
or claim support for arbitrary chat hosts and mobile browsers. Those clients
must supply their own permission-aware capture/playback and normal text-input
integration while continuing to call these same Axiom task contracts.
