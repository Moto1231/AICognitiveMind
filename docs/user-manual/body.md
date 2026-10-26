# Body, devices, voice and sensory evidence

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. Sections inherit this revision unless an explicit section review below overrides it. This is source review, not authenticated browser or physical-device certification.

## Check access before hardware

> This section was reviewed against `275e9202313b2ba41fe092e2be0da16186cb5ce2` on 2026-10-25. Other sections retain their stated review revisions. This is source review, not authenticated-browser or physical-device certification.

The browser Body uses local camera, microphone and playback devices with the remote application runtime. The browser owns device permission. A connected chat cannot remotely grant microphone permission.

**Live** at `/body/live` now opens for a valid account-scoped session. Its text interactions, sensory evidence, camera requests, host requests, queues, voice preferences and presence scope bind to the verified account's Mind. Output delivery also separates Minds even when their browser sessions use the same session name. Opening the page is not proof that a model, host or hardware operation has succeeded.

Account cognition uses its own saved task endpoints or a connected host attached to the same Mind. It does not inherit the deployment's OpenAI, Gemini or Fish Audio credentials as an unconfigured fallback. Configure the task endpoints needed by the operation, including Memory Recall/Steward requirements where applicable; an unrelated Mind's connected host does not satisfy this account's connection requirement.

**Realtime voice remains unavailable for account-scoped sessions.** Realtime startup checks the account capability before requesting microphone access or creating a session. The reported reason is **Realtime voice is not configured for this account.** Ordinary text, camera/hearing interpretation and non-Realtime speech use their separate paths. The deployment Body fallback switch, backup and custom GitHub skill drafts retain their own access restrictions.

No authenticated browser or physical-device test was performed for this manual. This source review does not certify camera/microphone permission, live provider quotas, host handoff or actual speech output.

Section sources: [account runtime and credential boundary](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L455-L514), [scope guard](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L793-L832), [queue/output scope](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/body_sessions.py#L14-L48), [Realtime capability](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L1427-L1451), [preflight before microphone](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/static/live_body.html#L653-L679), [Realtime session restriction](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/deployment.py#L302-L320).

## Select devices

> This section was reviewed against `80a3a4105379bb6c95afb6c71483c8d556a0ccc3` on 2026-10-25. Other sections retain their stated review revisions. This is source review, not authenticated-browser or physical-device certification.

1. On the browser/device you will use for Live, open **Administration → Devices**.
2. Read the camera and microphone permission statuses.
3. In **Body camera**, **Body microphone**, or **Body speaker / audio output**, use the **Use for Body operation** selector to choose a specific exposed device or **Browser default**.
4. Review the unsaved-change status, then choose **Save** to apply changed, valid choices. **Cancel** reloads the saved choices instead.
5. Open Live on that same browser after saving.

Selecting a device changes a form draft; it does not save immediately. The **Saved for this browser** summary continues to describe persisted preferences until Save succeeds. The clean form adds no device-choice helper sentence. A valid changed draft shows **Unsaved changes.**; meaningful errors remain visible. Save is enabled only when the draft differs from the saved choices and its selections are valid. Leaving Devices for another Administration section or returning to Main discards the unsaved device draft.

Preferences remain in this browser's local storage using the existing Body device keys. They do not select a camera on another phone, synchronize device IDs across browsers or grant hardware permission. Clearing a selection to **Browser default** takes effect when saved.

The inventory refreshes on supported device-change events. Refresh preserves unsaved choices; an older discovery response cannot replace a newer result. A previously saved device that is currently unavailable remains an explicit option rather than silently becoming Browser default. If a newly selected device disappears before Save, choose an available device or Cancel before saving.

If saved preferences changed elsewhere while this form was being edited, Save reports the conflict; Cancel reloads those saved values. A storage failure keeps the draft and attempts to restore the previous choices. Read the status: if restoration also fails, some preferences may have changed, and Cancel reloads the values actually saved.

Labels may be hidden until the browser grants permission. Missing labels do not prove a microphone is a speaker; use the device type and test deliberately. A browser without `setSinkId` cannot route media-element playback to the selected speaker and uses its default output.

These browser preferences do not grant provider access, attach a host or enable account Realtime voice. No new browser or physical-device exercise is established by this source review.

Section sources: [Devices controls](https://github.com/Moto1231/AICognitiveMind/blob/80a3a4105379bb6c95afb6c71483c8d556a0ccc3/src/aicognitive_mind/static/index.html#L552-L566), [device draft, Save/Cancel and inventory refresh](https://github.com/Moto1231/AICognitiveMind/blob/80a3a4105379bb6c95afb6c71483c8d556a0ccc3/src/aicognitive_mind/static/portal.js#L3111-L3352), [Main navigation rollback](https://github.com/Moto1231/AICognitiveMind/blob/80a3a4105379bb6c95afb6c71483c8d556a0ccc3/src/aicognitive_mind/static/portal.js#L336-L346), [Administration navigation rollback](https://github.com/Moto1231/AICognitiveMind/blob/80a3a4105379bb6c95afb6c71483c8d556a0ccc3/src/aicognitive_mind/static/portal.js#L3002-L3021).

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

> This section was reviewed against `275e9202313b2ba41fe092e2be0da16186cb5ce2` on 2026-10-25. Other sections retain their stated review revisions. This is source review, not authenticated-browser or physical-device certification.

1. Open **Administration → Speech Settings** in the intended account.
2. Wait for its authorized settings read to succeed, then adjust the controls below.
3. Choose **Save**.
4. Test a short spoken result on the intended browser.

| Setting | UI range | Scope/limit |
| --- | --- | --- |
| Speech rate | 0.5–1.75 | Saved speech preference for the authorized Mind; verify the actual output path |
| Pitch (browser voices) | 0.5–1.5 | Browser speech, not a promise of provider pitch control |
| Volume | 0–1 | Output preference; device/system volume still matters |
| Browser voice name | Text; blank uses default | Must exist on the playback device to select it |

Account-scoped sessions read and save their own voice preferences. They do not read the deployment's Fish Audio key, model or reference fallback. The non-admin Body settings response omits the saved secret. Administrator credential-bearing responses remain sensitive.

For provider speech, configure an endpoint and the **Audio/Voice** task. The task exposes a **Fish Audio reference / voice ID** field. The speech route can also use a Fish Audio key explicitly saved in that account's authorized voice configuration; an account with neither task configuration nor its own key receives an explicit configuration error. The ordinary Speech Settings sliders do not themselves supply provider credentials. Audio input/transcription belongs to **Audio/Transcription**, separately from output.

The Live playback implementation first calls the server speech route and visibly falls back to browser speech when that route fails and browser speech is available. Read whether status says **Fish Audio** or **browser speech**; hearing speech does not prove the provider succeeded. The exact provider/adapter must support the requested operation.

Voice Save remains disabled after a failed settings read. An unavailable or unknown capability clears old displayed values, and an earlier voice response cannot restore them. Read the form status before retrying. Administration Refresh loads the account-owned voice settings and skips the separate root-only deployment fallback setting.

The Realtime/WebRTC path remains unavailable to account-scoped sessions, with the preflight described [above](#check-access-before-hardware). Its presence in source does not certify a hands-free host handoff or a separate visible Talk control.

Section sources: [voice form](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/static/index.html#L527-L551), [account voice read/save and secret handling](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L874-L927), [speech task/own-key routing](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L1296-L1351), [load and Save gating](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/static/portal.js#L1426-L1524), [separate fallback capability](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L1529-L1535).

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

- **403 on Realtime or deployment administration:** read the precise capability/access message; enabling camera or microphone permission does not grant those capabilities.
- **Body opens, but reasoning/interpretation fails:** check this account's task endpoints and whether its own host is attached; opening Live does not supply deployment credentials.
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
