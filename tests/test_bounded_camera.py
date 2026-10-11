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


def test_live_body_polls_for_host_camera_requests():
    source = LIVE_BODY.read_text(encoding="utf-8")
    assert '"/v1/body/camera/request"' in source
    assert '"/v1/body/camera/complete"' in source
    assert "checkForHostCameraRequest" in source
    assert 'source: "browser-camera-mcp"' in source

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


def test_senses_activation_starts_hands_free_voice():
    source = LIVE_BODY.read_text(encoding="utf-8")
    assert "await startTalking();" in source
    assert "realtimeMicrophone = microphoneStream || await navigator.mediaDevices.getUserMedia({ audio: true });" in source
