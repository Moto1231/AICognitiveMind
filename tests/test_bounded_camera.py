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
    assert '"input": {"transcription": {"model": "gpt-4o-mini-transcribe"}}' in source


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
    assert "refreshConnectedHostStatus.pollDelayMs * 2" in function_source
    assert "refreshConnectedHostStatus.nextPollAt" in function_source


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
