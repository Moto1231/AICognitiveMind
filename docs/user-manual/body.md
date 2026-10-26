# Body, devices, voice and sensory evidence

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. Sections inherit this revision unless an explicit section review below overrides it. This is source review, not authenticated browser or physical-device certification.

## Check access before hardware

The browser Body uses local camera, microphone and playback devices with the remote application runtime. The browser owns device permission. A connected chat cannot remotely grant microphone permission.

At this revision, the authentication middleware explicitly rejects Body routes and Body administration routes for account-scoped sessions with **This endpoint is not available for account-scoped sessions.** The dedicated Realtime session route also rejects those sessions. The following workflows apply where the deployment's authorized access supports them. They are not a workaround for a 403.

No authenticated browser or physical-device test was performed for this manual. Hardware/browser support, account scope and provider configuration must be verified separately.

## Select devices

> This section was reviewed against `29e11c94af84e07b278c4aae6fd650cd92e6a428` on 2026-10-25. Other sections retain the opening review baseline.

1. On the browser/device you will use for Live, open **Administration → Devices**.
2. Read the camera and microphone permission statuses.
3. In **Body camera**, **Body microphone**, or **Body speaker / audio output**, use the **Use for Body operation** selector to choose a specific exposed device or **Browser default**.
4. Review the unsaved-change status, then choose **Save** to apply changed, valid choices. **Cancel** reloads the saved choices instead.
5. Open Live on that same browser after saving.

Selecting a device changes a form draft; it does not save immediately. The **Saved for this browser** summary continues to describe persisted preferences until Save succeeds. Save is enabled only when the draft differs from the saved choices and its selections are valid. Leaving Devices for another Administration section or returning to Main discards the unsaved device draft.

Preferences remain in this browser's local storage using the existing Body device keys. They do not select a camera on another phone, synchronize device IDs across browsers or grant hardware permission. Clearing a selection to **Browser default** takes effect when saved.

The inventory refreshes on supported device-change events. Refresh preserves unsaved choices; an older discovery response cannot replace a newer result. A previously saved device that is currently unavailable remains an explicit option rather than silently becoming Browser default. If a newly selected device disappears before Save, choose an available device or Cancel before saving.

If saved preferences changed elsewhere while this form was being edited, Save reports the conflict; Cancel reloads those saved values. A storage failure keeps the draft and attempts to restore the previous choices. Read the status: if restoration also fails, some preferences may have changed, and Cancel reloads the values actually saved.

Labels may be hidden until the browser grants permission. Missing labels do not prove a microphone is a speaker; use the device type and test deliberately. A browser without `setSinkId` cannot route media-element playback to the selected speaker and uses its default output.

These controls do not change the account-scope restrictions described above. No new browser or physical-device exercise is established by this source review.

Section sources: [Devices controls](https://github.com/Moto1231/AICognitiveMind/blob/29e11c94af84e07b278c4aae6fd650cd92e6a428/src/aicognitive_mind/static/index.html#L552-L571), [device draft, Save/Cancel and inventory refresh](https://github.com/Moto1231/AICognitiveMind/blob/29e11c94af84e07b278c4aae6fd650cd92e6a428/src/aicognitive_mind/static/portal.js#L3044-L3289), [Main navigation rollback](https://github.com/Moto1231/AICognitiveMind/blob/29e11c94af84e07b278c4aae6fd650cd92e6a428/src/aicognitive_mind/static/portal.js#L339-L349), [Administration navigation rollback](https://github.com/Moto1231/AICognitiveMind/blob/29e11c94af84e07b278c4aae6fd650cd92e6a428/src/aicognitive_mind/static/portal.js#L2941-L2960).

## Send a text message in Live

1. Choose **Live** from the portal.
2. Type a short message in the conversation composer.
3. Choose **Send**.
4. Wait for the response or explicit error.
5. Read status messages before assuming the reasoning host or speech output worked.

Text interaction does not require enabling camera or hearing. A **Thinking...** placeholder is not a completed response. **Clear conversation** clears the displayed conversation; it is not a deletion command for durable memory or history.

Live's **Return** points to the signed-in portal interface.

## Turn camera, hearing and voice on separately

| Control | Meaning |
| --- | --- |
| Vision Off / Vision On | Toggle camera capture |
| Hearing Off / Hearing On | Toggle microphone capture and hearing processing |
| Voice Off / Voice On | Toggle spoken output |
| Hearing level meter | Local microphone signal level, not transcription success |
| Camera preview | Local stream visibility, not proof that an image was interpreted |
| Host/status display | Connection diagnostics, not proof every queued request completed |

1. Enable **Vision** only when camera use is intended; grant the browser permission.
2. Confirm the preview and vision status.
3. Enable **Hearing** separately and grant microphone permission.
4. Speak briefly and check both the meter and processing/result status.
5. Enable **Voice** when spoken output is desired.
6. Turn off the relevant input when finished.

Turning Vision off leaves Hearing and Voice unchanged; turning Hearing off leaves Vision and Voice unchanged. Capture loops are separate, but processing can be gated by busy/in-flight state. Do not describe this as guaranteed simultaneous unlimited inference.

The browser remembers toggle preferences. Returning to Live can attempt to resume previously enabled inputs, subject to browser permission and policy.

## Camera and audio limits

The camera loop uses motion detection to decide when to admit frames, with a 2.5-second motion-capture cooldown in this revision. A still room can legitimately remain at **waiting for movement**. Preview continuity does not mean every video frame is uploaded or interpreted.

Audio recording follows an utterance, ending after detected silence and bounded by a maximum of 30 seconds. Quiet windows stop after four seconds; an idle-window message does not mean every spoken clip is fixed at four seconds. Hearing pauses processing while speech is being played to reduce self-listening.

The browser's speech-energy heuristic is not a guarantee of perfect voice activity detection. Noise, quiet speech, unsupported recording formats or permission failures can produce missing/failed interpretations.

## Configure Speech Settings

1. Open **Administration → Speech Settings**.
2. Adjust the controls below.
3. Choose **Save**.
4. Test a short spoken result on the intended browser.

| Setting | UI range | Scope/limit |
| --- | --- | --- |
| Speech rate | 0.5–1.75 | Saved speech preference; verify the actual output path |
| Pitch (browser voices) | 0.5–1.5 | Browser speech, not a promise of provider pitch control |
| Volume | 0–1 | Output preference; device/system volume still matters |
| Browser voice name | Text; blank uses default | Must exist on the playback device to select it |

For provider speech, configure an endpoint and the **Audio/Voice** task. The task exposes a **Fish Audio reference / voice ID** field. Audio input/transcription belongs to **Audio/Transcription**, separately from output.

The Live playback implementation first calls the server speech route and visibly falls back to browser speech when that route fails and browser speech is available. Read whether status says **Fish Audio** or **browser speech**; hearing speech does not prove the provider succeeded. The exact provider/adapter must support the requested operation.

There is Realtime/WebRTC code in the page, but the ordinary visible controls are the Vision/Hearing/Voice toggles. This manual does not invent a separate Talk button or certify a hands-free host handoff from the presence of that code.

## Understand sensory evidence

A continuous stream, an admitted observation, an interpretation and a curated memory are distinct.

A deliberate See/Hear observation can preserve the exact submitted image/audio artifact before interpretation. Its reference includes capture time, media type, byte length and SHA-256. Interpretation can fail even though evidence admission succeeded.

To review evidence:

1. Open **Administration → Journals**.
2. Find the relevant experience by time and context.
3. Open its detail.
4. Inspect the referenced **Sensory Evidence** if available and authorized.
5. Keep the original capture time and the later interpretation/review distinct.

The evidence-review capability can revisit an exact preserved artifact; it does not rewrite the original observation or make it live. Erasing stored media leaves an audit record. An unavailable artifact is a limitation to report, not a reason to invent what it showed.

## Troubleshooting sequence

- **403 scope restriction:** stop hardware troubleshooting and check supported account scope.
- **Permission denied/no stream:** inspect browser camera/microphone permissions and secure HTTPS context.
- **Preview/meter works, interpretation does not:** inspect provider/task configuration and request status.
- **Waiting for movement:** move deliberately within the permitted scene; do not infer a frozen camera solely from that message.
- **Speech silent:** check Voice toggle, volume, output device, browser playback restrictions and provider status.
- **Browser speech instead of expected voice:** check the displayed fallback error and Audio/Voice configuration.
- **Host attached but no response:** attachment is not completion; record the specific request error and inspect the configured fallback.

Do not place raw private camera/audio evidence into GitHub to demonstrate a problem.

## Source references

- [src/aicognitive_mind/static/live_body.html](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/live_body.html)
- [src/aicognitive_mind/static/portal.js](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/portal.js)
- [src/aicognitive_mind/api.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/api.py)
- [src/aicognitive_mind/deployment.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/deployment.py)
- [src/aicognitive_mind/body_sessions.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/body_sessions.py)
- [src/aicognitive_mind/voice_settings.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/voice_settings.py)
- [docs/body/0010-sensory-evidence-v0.1.md](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/docs/body/0010-sensory-evidence-v0.1.md)
- [docs/body/0011-sensory-evidence-review-v0.1.md](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/docs/body/0011-sensory-evidence-review-v0.1.md)
