from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIVE_BODY = ROOT / "src" / "aicognitive_mind" / "static" / "live_body.html"
DEPLOYMENT = ROOT / "src" / "aicognitive_mind" / "deployment.py"


def test_live_body_supports_bounded_voice_requested_camera_observation():
    source = LIVE_BODY.read_text(encoding="utf-8")
    assert "DEFAULT_LOOK_SECONDS = 5" in source
    assert "MAX_LOOK_SECONDS = 30" in source
    assert "conversation.item.input_audio_transcription.completed" in source
    assert "performBoundedLook(seconds, transcript)" in source
    assert 'source: "browser-camera-bounded"' in source
    assert 'stream?.getTracks().forEach((track) => track.stop())' in source
    assert "Hands-free voice remains active." in source


def test_realtime_session_enables_input_transcription():
    source = DEPLOYMENT.read_text(encoding="utf-8")
    assert '"transcription": {"model": "gpt-4o-mini-transcribe"}' in source
    assert '"create_response": False' in source
    assert '"interrupt_response": False' in source


def test_live_body_polls_for_host_camera_requests_without_overlapping_or_spamming():
    source = LIVE_BODY.read_text(encoding="utf-8")
    assert '"/v1/body/camera/request"' in source
    assert '"/v1/body/camera/complete"' in source
    assert "checkForHostCameraRequest" in source
    assert 'source: "browser-camera-mcp"' in source
    function_start = source.index("async function checkForHostCameraRequest()")
    request_start = source.index('bodyFetch("/v1/body/camera/request"', function_start)
    busy_lock = source.index("hostCameraRequestBusy = true;", function_start)
    assert busy_lock < request_start
    assert "response.status === 429" in source[function_start:source.index("function setSenseStatus", function_start)]
    assert 'response.headers.get("Retry-After")' in source[function_start:source.index("function setSenseStatus", function_start)]
    assert "hostCameraPollDelayMs * 2" in source[function_start:source.index("function setSenseStatus", function_start)]

def test_live_body_host_status_poll_does_not_overlap_and_backs_off():
    source = LIVE_BODY.read_text(encoding="utf-8")
    function_start = source.index("async function refreshConnectedHostStatus()")
    function_end = source.index("function setSenseStatus", function_start)
    function_source = source[function_start:function_end]
    assert "refreshConnectedHostStatus.inFlight" in function_source
    assert "refreshConnectedHostStatus.inFlight = true;" in function_source
    assert "finally" in function_source
    assert "refreshConnectedHostStatus.inFlight = false;" in function_source
    assert 'response.status === 429' in function_source
    assert 'response.headers.get("Retry-After")' in function_source
    assert "Math.max(5_000, (refreshConnectedHostStatus.pollDelayMs || 5_000) * 2)" in function_source
    assert "30_000" in function_source
    assert "retryAfterSeconds * 1_000" in function_source
    assert "refreshConnectedHostStatus.nextPollAt = Date.now() + refreshConnectedHostStatus.pollDelayMs" in function_source


def test_live_body_shows_independent_vision_and_audio_statuses():
    source = LIVE_BODY.read_text(encoding="utf-8")
    assert 'id="visionSenseStatus"' in source
    assert 'id="audioSenseStatus"' in source
    assert 'setSenseStatus("vision"' in source
    assert 'setSenseStatus("audio"' in source
    assert 'reportSenseFailure("vision", error)' in source
    assert 'reportSenseFailure("audio", error)' in source
    assert 'Evidence saved; interpretation failed:' in source
    assert 'placeholder="Message"' in source
    assert 'placeholder="Message the Mind..."' not in source


def test_live_body_has_independent_vision_hearing_and_voice_controls():
    source = LIVE_BODY.read_text(encoding="utf-8")
    assert 'id="visionToggle"' in source
    assert 'id="hearingToggle"' in source
    assert 'id="voiceToggle"' in source
    assert 'function toggleVision()' in source
    assert 'function toggleHearing()' in source
    assert 'function toggleVoice()' in source
    assert 'localStorage.setItem("aicognitive_mind.vision"' in source
    assert 'localStorage.setItem("aicognitive_mind.hearing"' in source
    assert 'localStorage.setItem("aicognitive_mind.voice"' in source
    assert "sensesEnabled" not in source


def test_live_body_does_not_poll_or_capture_camera_when_vision_is_off():
    source = LIVE_BODY.read_text(encoding="utf-8")
    function_start = source.index("async function checkForHostCameraRequest()")
    function_end = source.index("let pageSourceSnapshot", function_start)
    camera_function = source[function_start:function_end]
    assert "if (!visionEnabled || hostCameraRequestBusy" in camera_function
    assert camera_function.index("if (!visionEnabled || hostCameraRequestBusy") < camera_function.index('bodyFetch("/v1/body/camera/request"')
    assert "if (!visionEnabled) return;" in camera_function
    assert 'setSenseStatus("vision", "Vision is off. No camera polling or capture will run."' in source


def test_live_body_voice_off_blocks_spoken_output_and_mouth_event_delivery():
    source = LIVE_BODY.read_text(encoding="utf-8")
    assert 'if (!voiceEnabled || !intent?.text) return;' in source
    drain_start = source.index("async function consumeExpressionOutputs()")
    events_start = source.index("function connectMouthEvents()", drain_start)
    events_end = source.index("async function registerActiveBodySession()", events_start)
    drain_source = source[drain_start:events_start]
    events_source = source[events_start:events_end]
    assert 'if (!voiceEnabled || mouthPollBusy) return false;' in drain_source
    assert 'while (voiceEnabled)' in drain_source
    assert events_source.index('if (!voiceEnabled) {') < events_source.index('new EventSource(')
    assert 'mouthEvents?.close();' in events_source
    assert 'mouthEvents = null;' in events_source
    listener_source = events_source[events_source.index('addEventListener("voice-ready"'):]
    assert listener_source.index('if (!voiceEnabled) return;') < listener_source.index('consumeExpressionOutputs()')
    assert 'setInterval(consumeExpressionOutputs' not in source


def test_live_body_voice_off_stops_current_audio_playback():
    source = LIVE_BODY.read_text(encoding="utf-8")
    voice_toggle_start = source.index("function toggleVoice()")
    voice_toggle_end = source.index("interactionForm.addEventListener", voice_toggle_start)
    voice_toggle = source[voice_toggle_start:voice_toggle_end]
    assert "stopTalking();" in voice_toggle
    assert "cancelBodySpeech();" in voice_toggle
    stop_start = source.index("function stopTalking(")
    stop_end = source.index("async function startTalking(", stop_start)
    assert 'cancelBodySpeech("realtime");' in source[stop_start:stop_end]
    cancel_start = source.index("function cancelBodySpeech(")
    cancel_end = source.index("async function speakIntent", cancel_start)
    cancel = source[cancel_start:cancel_end]
    assert "activeSpeechAudio.pause()" in cancel
    assert "activeSpeechAudio.currentTime = 0" in cancel
    assert "window.speechSynthesis?.cancel()" in cancel
    assert "voiceEnabled && generation === speechGeneration && isCurrent()" in source[source.index("async function speakIntent"):source.index("function resumeTalking")]



def test_live_body_triggers_camera_uploads_only_for_meaningful_motion_with_cooldown():
    source = LIVE_BODY.read_text(encoding="utf-8")
    assert "const VISION_INTERVAL_MS = 250;" in source
    assert "const MOTION_PIXEL_DELTA = 22;" in source
    assert "const MOTION_PIXEL_RATIO = 0.07;" in source
    assert "const MOTION_CAPTURE_COOLDOWN_MS = 2_500;" in source
    assert "Motion detection active; waiting for movement." in source
    assert "if (changedPixels / signature.length < MOTION_PIXEL_RATIO) return;" in source
    assert "if (performance.now() - lastMotionCaptureAt < MOTION_CAPTURE_COOLDOWN_MS) return;" in source
    assert "lastFrameSignature = signature;" in source
    assert "lastSuccessfulFrame" not in source
    assert "luminance[pixel] = Math.round(" in source

def test_live_body_hearing_loop_is_independent_of_vision():
    source = LIVE_BODY.read_text(encoding="utf-8")
    function_start = source.index("async function runHearingLoop(generation)")
    function_end = source.index("function startSensoryLoop()", function_start)
    hearing_loop = source[function_start:function_end]
    assert "while (hearingEnabled && generation === sensoryLoopGeneration)" in hearing_loop
    assert 'if (hearingEnabled && generation === sensoryLoopGeneration)' in hearing_loop
    assert "while (visionEnabled" not in hearing_loop
    assert 'reportSenseFailure("audio", error)' in hearing_loop
