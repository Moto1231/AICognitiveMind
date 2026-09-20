# Axiom Unity Body

This directory is the desktop Body for the existing AI Cognitive Mind.

## Architectural boundary

Unity owns the **Body** only:

- VRM rendering and animation
- camera and microphone hardware
- audio playback / voice
- face, mouth, movement, and desktop lifecycle

The Python application remains the **Mind**:

- Cognitive Core
- Memory Steward and Governance
- reasoning
- sensory interpretation
- evidence preservation
- **SurrealDB persistence**

The Unity client must not receive SurrealDB credentials and must never read or write SurrealDB directly.

## Current bootstrap

The first slice:

1. starts a persistent Unity Body runtime;
2. checks the existing Python runtime at `/health`;
3. downloads the canonical VRM from `/v1/body/face/avatar`;
4. loads the VRM at runtime through UniVRM;
5. frames the avatar automatically;
6. provides a temporary developer interaction box that posts to `/v1/mind/body/interact`;
7. polls `/v1/body/mouth/next` for the Mind's existing VOICE expression intents;
8. synthesizes those intents to temporary WAV audio through the local Windows System.Speech engine;
9. plays the WAV through a Unity `AudioSource`;
10. samples the actual audio amplitude and drives the avatar mouth in sync;
11. exposes a desktop Senses toggle that activates camera and microphone perception;
12. preserves Unity camera frames and microphone recordings through the Mind's existing evidence pipeline.

UniVRM is pinned through Unity Package Manager to the VRM 1.0 package.

## Runtime configuration

Set these environment variables before launching the Unity editor or built application:

- `AXIOM_MIND_URL` — Python Mind base URL. Defaults to `http://127.0.0.1:8000`.
- `AXIOM_MIND_USERNAME` — HTTP Basic username. Defaults to `mind`.
- `AXIOM_MIND_PASSWORD` — HTTP Basic password. Leave empty only when the Mind runtime has no access password configured.

No database credentials belong in this project.

## Opening

Open the `body-unity` directory as a Unity project. The baseline project version is Unity 6.0. Unity may offer to upgrade it when opened in a newer Unity 6 editor.

The runtime bootstrap is created automatically after a scene loads, so an empty scene is sufficient for the first connection test. Press Play and the Body should connect and load Axiom from the Mind.

## Next body increments

After the bootstrap is proven on Windows:

- diagnostics inside the desktop application
- voice-pack controls inside the desktop application
- phoneme/viseme refinement beyond amplitude-driven mouth opening
- broader expression mapping
- animation/state machine
- replace the temporary IMGUI developer overlay with the actual Body UI

## Desktop Mouth V0.2

The Windows Mouth uses the local Windows speech engine through
`powershell.exe` + `System.Speech`. Speech is synthesized to a temporary
WAV file and then played by Unity so the Body owns the actual audio signal.

It supports:

- installed Windows voice selection when `voice_name` is supplied by the Mind;
- rate;
- pitch through SSML prosody;
- volume;
- serialized speech so Mouth intents do not overlap;
- Unity-owned WAV playback;
- amplitude-driven VRM mouth movement synchronized to the actual speech audio.

Speech remains a Body concern. The Mind still emits only transient VOICE
`ExpressionIntent` objects.

This is intentionally a zero-cost local adapter. A future neural TTS provider
can replace it behind the same Mouth boundary without changing the Cognitive
Core or SurrealDB architecture.

### Lip sync

`AxiomLipSync` samples the active speech `AudioClip` at the current
playback position, calculates RMS amplitude, and smooths attack/release. It
uses the standard VRM 1.0 `aa` expression when available and directly
animates the generated Genesis `MouthVisual` transform as the deterministic
fallback for the current unskinned Genesis mouth mesh.

This is real audio-reactive synchronization, but it is not yet
phoneme-specific viseme recognition. The later refinement can distribute
speech across `aa`, `ih`, `ou`, `ee`, and `oh` while retaining the
same Mouth/audio pipeline.

## Desktop Senses V0.1

`AxiomSensesRuntime` moves the existing Eyes and Ears loop into Unity.

When Senses are enabled:

- Unity captures JPEG frames from the first available `WebCamTexture`;
- visual evidence is admitted through `/v1/body/eyes/observe` and interpreted through `/v1/mind/body/see?express=false`;
- Unity records four-second microphone windows and encodes them as PCM16 WAV;
- audio evidence is admitted through `/v1/body/ears/observe` and interpreted through `/v1/mind/body/hear?express=false`;
- vision and hearing alternate with the same 15-second pause used by the browser prototype;
- passive perception does not automatically speak every Mind response.

Turning Senses off releases both camera and microphone hardware.

## Desktop Avatar Editor V0.1

The Unity Body now owns avatar appearance editing instead of requiring the
browser editor.

The live Body view exposes an **Avatar** selection that opens a separate
desktop editing view. It carries forward the existing Genesis appearance
contract:

- skin, hair, shirt, pants, eye, and shoe colors;
- head size and hair volume;
- eye size and eye spacing;
- mouth width;
- torso and shoulder width;
- arm and leg thickness.

Changes preview immediately on the loaded VRM. **Save** persists the normalized
appearance in Unity `PlayerPrefs`; **Reset** returns Genesis to the canonical
defaults.

Saved appearance is applied before the Unity Mouth attaches so lip-sync uses
the customized mouth width as its neutral baseline. Live editor changes refresh
that lip-sync baseline without changing the Mind or SurrealDB.

## Desktop Memory + Journal V0.1

The Unity desktop application now exposes separate **Memory** and **Journal**
views from the main Body screen.

Both views use the existing protected Mind portal APIs; Unity never reads
SurrealDB directly.

Memory provides:

- newest-first paging in 12-item pages;
- full-text search through the existing memory query contract;
- memory class and formation timestamp;
- memory content;
- associations and grounding summaries;
- previous / next page navigation.

Journal provides:

- newest-first paging in 12-item pages;
- full-text search through the existing journal query contract;
- journal kind/title and occurrence timestamp;
- the existing server-generated journal preview;
- previous / next page navigation.

This slice is intentionally read-only. Privileged memory revision remains an
Admin-mode function and is the next desktop consolidation boundary.

## Desktop Admin V0.1

The Unity desktop application now exposes a separate **Admin** view.

Admin authorization uses the server's existing `X-Admin-Pin` contract. The
PIN is held only in the running Unity session; it is never written to
`PlayerPrefs`.

Once authorized, the desktop Admin view provides governed durable-memory
revision:

- search and page through the same canonical memory data shown in the normal
  Memory view;
- select a durable memory and edit its memory class, content, associations,
  and grounding;
- save through the protected admin API;
- preserve the original `formed_at` value and all Steward artifacts on the
  server;
- reject ambiguous/stale revisions instead of guessing which memory to change;
- append the same `memory_revision` journal experience used by the browser
  portal, with the channel recorded as `desktop`;
- refresh Memory and Journal after a successful revision.

Unity still has no direct SurrealDB credentials or storage access.
