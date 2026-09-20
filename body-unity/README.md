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
10. samples the actual audio amplitude and drives the VRM mouth expression in sync.

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

- native continuous webcam perception
- native continuous microphone perception
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

`AxiomLipSync` samples the active Unity `AudioSource` with
`GetOutputData`, calculates RMS amplitude, smooths attack/release, and maps
the result to the standard VRM 1.0 `aa` expression through
`Runtime.Expression.SetWeight`.

This is real audio-reactive synchronization, but it is not yet
phoneme-specific viseme recognition. The later refinement can distribute
speech across `aa`, `ih`, `ou`, `ee`, and `oh` while retaining the
same Mouth/audio pipeline.
