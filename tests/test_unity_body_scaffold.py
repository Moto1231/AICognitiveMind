import json
import unittest
from pathlib import Path


class UnityBodyScaffoldTests(unittest.TestCase):
    def test_unity_body_packages_include_vrm_1_runtime(self) -> None:
        manifest = json.loads(
            Path("body-unity/Packages/manifest.json").read_text(encoding="utf-8")
        )
        dependencies = manifest["dependencies"]

        self.assertIn("com.vrmc.gltf", dependencies)
        self.assertIn("com.vrmc.vrm", dependencies)
        self.assertIn("UniVRM.git", dependencies["com.vrmc.vrm"])
        self.assertIn("path=/Packages/VRM10", dependencies["com.vrmc.vrm"])
        self.assertIn("com.unity.modules.audio", dependencies)
        self.assertIn("com.unity.modules.imageconversion", dependencies)
        self.assertIn("com.unity.modules.unitywebrequest", dependencies)
        self.assertIn("com.unity.modules.unitywebrequestaudio", dependencies)

    def test_unity_body_talks_to_mind_not_storage(self) -> None:
        client = Path(
            "body-unity/Assets/AxiomBody/Runtime/MindApiClient.cs"
        ).read_text(encoding="utf-8")
        config = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomRuntimeConfig.cs"
        ).read_text(encoding="utf-8")
        combined = client + config

        self.assertIn("/health", client)
        self.assertIn("/v1/body/face/avatar", client)
        self.assertIn("/v1/mind/body/interact?express=false", client)
        self.assertIn("/v1/body/mouth/next", client)
        self.assertIn("AXIOM_MIND_URL", config)
        self.assertNotIn("SURREALDB_", combined)
        self.assertNotIn("MONGODB_", combined)

    def test_unity_body_runtime_references_required_univrm_assemblies(self) -> None:
        asmdef = json.loads(
            Path(
                "body-unity/Assets/AxiomBody/Runtime/Axiom.Body.Runtime.asmdef"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(asmdef["name"], "Axiom.Body.Runtime")
        self.assertIn("VRM10", asmdef["references"])
        self.assertIn("UniGLTF", asmdef["references"])
        self.assertIn("UniGLTF.Utils", asmdef["references"])

    def test_unity_body_surfaces_api_error_detail(self) -> None:
        client = Path(
            "body-unity/Assets/AxiomBody/Runtime/MindApiClient.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("MindApiErrorResponse", client)
        self.assertIn("ApiErrorDetail", client)
        self.assertIn("response.detail", client)
        self.assertIn("Mind API request failed", client)

    def test_unity_body_exposes_local_connection_settings(self) -> None:
        config = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomRuntimeConfig.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("PlayerPrefs.SetString", config)
        self.assertIn("SaveConnection", config)
        self.assertIn("GUI.PasswordField", bootstrap)
        self.assertIn("ConnectAsync", bootstrap)
        self.assertIn("DrawConnectionDialog", bootstrap)
        self.assertIn('"Connect"', bootstrap)
        self.assertIn('"Cancel"', bootstrap)
        self.assertIn("Connection failed:", bootstrap)

    def test_unity_body_has_switchable_model_policy_and_local_motion(self) -> None:
        config = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomRuntimeConfig.cs"
        ).read_text(encoding="utf-8")
        senses = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomSensesRuntime.cs"
        ).read_text(encoding="utf-8")
        motion = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyMotionRuntime.cs"
        ).read_text(encoding="utf-8")
        mouth = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomMouthRuntime.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")
        client = Path(
            "body-unity/Assets/AxiomBody/Runtime/MindApiClient.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("BodyModelPolicy.CognitiveOnly", config)
        self.assertIn("BodyModelPolicy.FullBodyModel", config)
        self.assertIn("AXIOM_BODY_MODEL_POLICY", config)
        self.assertIn("SaveBodyModelPolicy", config)
        self.assertIn("VisionRequiresModel", senses)
        self.assertIn("AudioRequiresModel", senses)
        self.assertIn("model skipped", senses)
        self.assertIn("SetModelPolicy", senses)
        self.assertIn("Mode: Cognitive", bootstrap)
        self.assertIn("Mode: Full Body", bootstrap)
        self.assertIn("ToggleBodyModelPolicy", bootstrap)

        self.assertIn("AxiomBodyMotionRuntime", bootstrap)
        self.assertIn("DefaultExecutionOrder(12500)", motion)
        self.assertIn("breath", motion)
        self.assertIn("sway", motion)
        self.assertIn("HumanBodyBones.Head", motion)
        self.assertIn("IsSpeaking", mouth)
        self.assertIn("_bodyMotionRuntime?.Attach", bootstrap)

        self.assertIn("AuthenticateAsync", client)
        self.assertIn('Url("/v1/mind")', client)
        self.assertIn("await _client.AuthenticateAsync()", bootstrap)

    def test_unity_body_uses_connection_dialog_and_slim_control_strip(self) -> None:
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")
        loader = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomAvatarLoader.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("_connectionDialogOpen = true", bootstrap)
        self.assertIn("DrawConnectionDialog", bootstrap)
        self.assertIn("DrawControlStrip", bootstrap)
        self.assertIn('"ON" : "OFF"', bootstrap)
        self.assertIn("0.20f, 0.78f, 0.30f", bootstrap)
        self.assertIn("0.86f, 0.22f, 0.22f", bootstrap)
        self.assertIn("DrawModeDropdown", bootstrap)
        self.assertIn("DrawBodyDropdown", bootstrap)
        self.assertIn('"Senses"', bootstrap)
        self.assertIn('"Memory"', bootstrap)
        self.assertIn('"Journal"', bootstrap)
        self.assertIn('"Summary"', bootstrap)
        self.assertIn('"Admin"', bootstrap)
        self.assertIn("Disconnect(showConnectionDialog: true)", bootstrap)
        self.assertIn("_avatarLoader?.Unload()", bootstrap)
        self.assertIn("public void Unload()", loader)

        start = bootstrap[
            bootstrap.index("private void Start()"):
            bootstrap.index("private async Task ConnectAsync()")
        ]
        self.assertNotIn("ConnectAsync()", start)

    def test_unity_body_keeps_controls_and_chat_on_right_rail(self) -> None:
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("Screen.width - railWidth - 10f", bootstrap)
        self.assertIn("Screen.height - 18f", bootstrap)
        self.assertIn('"ON" : "OFF"', bootstrap)
        self.assertIn('"Cognitive ▼"', bootstrap)
        self.assertIn('"Full ▼"', bootstrap)
        self.assertIn('"Senses"', bootstrap)
        self.assertIn('"Home"', bootstrap)
        self.assertIn('"Memory"', bootstrap)
        self.assertIn('"Journal"', bootstrap)
        self.assertIn('"Admin ✓" : "Admin"', bootstrap)
        self.assertIn("DrawControlStrip();", bootstrap)
        self.assertIn("DrawSummaryView();", bootstrap)
        self.assertIn('"Chat"', bootstrap)
        self.assertIn("SendInteractionAsync", bootstrap)
        self.assertIn("new Color(1f, 1f, 1f, 0.36f)", bootstrap)

    def test_unity_body_consumes_mouth_intents_through_windows_speech(self) -> None:
        client = Path(
            "body-unity/Assets/AxiomBody/Runtime/MindApiClient.cs"
        ).read_text(encoding="utf-8")
        mouth = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomMouthRuntime.cs"
        ).read_text(encoding="utf-8")
        speech = Path(
            "body-unity/Assets/AxiomBody/Runtime/WindowsSpeechOutput.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("NextMouthIntentAsync", client)
        self.assertIn("/v1/body/mouth/next", client)
        self.assertIn("VoiceExpressionIntent", client)
        self.assertIn("PollAsync", mouth)
        self.assertIn("SpeakTextAsync", mouth)
        self.assertIn("WindowsSpeechOutput", mouth)
        self.assertIn("powershell.exe", speech)
        self.assertIn("System.Speech", speech)
        self.assertIn("SelectVoice", speech)
        self.assertIn("SpeakSsml", speech)
        self.assertIn("SetOutputToWaveFile", speech)
        self.assertIn("_avatarLoader.Root", bootstrap)
        self.assertIn("_avatarLoader.Instance", bootstrap)
        self.assertIn("await _mouthRuntime.SpeakTextAsync(response.response_text)", bootstrap)

    def test_unity_body_drives_vrm_mouth_from_actual_audio(self) -> None:
        mouth = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomMouthRuntime.cs"
        ).read_text(encoding="utf-8")
        lip_sync = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomLipSync.cs"
        ).read_text(encoding="utf-8")
        speech = Path(
            "body-unity/Assets/AxiomBody/Runtime/WindowsSpeechOutput.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("SynthesizeWavAsync", speech)
        self.assertIn("SetOutputToWaveFile", speech)
        self.assertIn("UnityWebRequestMultimedia.GetAudioClip", mouth)
        self.assertIn("AudioSource", mouth)
        self.assertIn("clip.GetData", lip_sync)
        self.assertNotIn("GetOutputData", lip_sync)
        self.assertIn("ExpressionPreset.aa", lip_sync)
        self.assertIn("Runtime.Expression.SetWeight", lip_sync)
        self.assertIn("aaOpen", lip_sync)
        self.assertIn("SetBlendShapeWeight", lip_sync)
        self.assertIn("MouthVisual", lip_sync)
        self.assertIn("SetMouthTransformWeight", lip_sync)
        self.assertIn("localScale", lip_sync)
        self.assertIn("DefaultExecutionOrder(12000)", lip_sync)
        self.assertIn("CurrentWeight", lip_sync)
        self.assertIn("Lip target:", mouth)

    def test_unity_body_has_desktop_eyes_and_ears(self) -> None:
        client = Path(
            "body-unity/Assets/AxiomBody/Runtime/MindApiClient.cs"
        ).read_text(encoding="utf-8")
        senses = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomSensesRuntime.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("/v1/body/eyes/observe", client)
        self.assertIn("/v1/mind/body/see?express=false", client)
        self.assertIn("/v1/body/ears/observe", client)
        self.assertIn("/v1/mind/body/hear?express=false", client)
        self.assertIn("WebCamTexture", senses)
        self.assertIn("ImageConversion.EncodeToJPG", senses)
        self.assertIn("Microphone.Start", senses)
        self.assertIn("data:audio/wav;base64,", senses)
        self.assertIn("EncodePcm16Wav", senses)
        self.assertIn("VisionIntervalSeconds = 15f", senses)
        self.assertIn("AudioIntervalSeconds = 15f", senses)
        self.assertIn("AudioWindowSeconds = 4", senses)
        self.assertIn("RunVisionLoopAsync", senses)
        self.assertIn("RunAudioLoopAsync", senses)
        self.assertIn("_visionBusy", senses)
        self.assertIn("_audioBusy", senses)
        self.assertNotIn("RunSensoryLoopAsync", senses)
        self.assertNotIn("private bool _busy", senses)
        self.assertIn('"Senses"', bootstrap)
        self.assertIn("ToggleSensesAsync", bootstrap)
        self.assertIn("_sensesRuntime.Attach(_client)", bootstrap)

    def test_unity_eyes_and_ears_run_as_independent_workers(self) -> None:
        senses = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomSensesRuntime.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("_ = RunVisionLoopAsync(generation);", senses)
        self.assertIn("_ = RunAudioLoopAsync(generation);", senses)
        self.assertIn("VisionBusy => _visionBusy", senses)
        self.assertIn("AudioBusy => _audioBusy", senses)
        self.assertIn("SetVisionStatus", senses)
        self.assertIn("SetAudioStatus", senses)
        self.assertIn("_visionStatus + \" | \" + _audioStatus", senses)
        self.assertIn("SemaphoreSlim", senses)
        self.assertIn("_cognitionGate.WaitAsync()", senses)
        self.assertIn("_cognitionGate.Release()", senses)
        self.assertIn("Eyes waiting for cognition...", senses)
        self.assertIn("Ears waiting for cognition...", senses)

    def test_unity_body_supports_genesis_bodies_library(self) -> None:
        loader = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomAvatarLoader.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")
        mouth = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomMouthRuntime.cs"
        ).read_text(encoding="utf-8")
        lip_sync = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomLipSync.cs"
        ).read_text(encoding="utf-8")

        self.assertIn('PresetResourcePath = "GenesisBodies"', loader)
        self.assertNotIn('"AxiomBodies"', loader + bootstrap)
        self.assertIn("AvailableBodies", loader)
        self.assertIn("RefreshBodyCatalog", loader)
        self.assertIn("EnsureBodyCatalog", loader)
        self.assertIn("_presetAssets", loader)
        self.assertIn("Resources.LoadAll<GameObject>", loader)
        self.assertIn("SelectBodyAsync", loader)
        self.assertIn("LoadSelectedAsync", loader)
        self.assertIn("axiom.body.selected.v0.1", loader)
        self.assertIn("DrawBodyDropdown", bootstrap)
        self.assertIn("AvailableBodies", bootstrap)
        self.assertIn("SwitchBodyAsync", bootstrap)
        self.assertIn("Assets/Resources/GenesisBodies/", bootstrap)
        self.assertIn("GameObject avatarRoot", mouth)
        self.assertIn("GameObject avatarRoot", lip_sync)
        self.assertIn("MouthOpen", lip_sync)
        self.assertIn("JawOpen", lip_sync)

    def test_unity_body_has_separate_avatar_editor_view(self) -> None:
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")
        editor = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomAvatarEditorRuntime.cs"
        ).read_text(encoding="utf-8")
        mouth = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomMouthRuntime.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("DesktopView.Avatar", bootstrap)
        self.assertIn("DrawAvatarEditor", bootstrap)
        self.assertIn('"Genesis Editor"', bootstrap)
        self.assertIn('"Back to Body"', bootstrap)
        self.assertIn("AxiomAvatarEditorRuntime", bootstrap)
        self.assertIn("PlayerPrefs.SetString", editor)
        self.assertIn("axiom.avatar.appearance.v0.1", editor)
        self.assertIn("skinColor", editor)
        self.assertIn("hairColor", editor)
        self.assertIn("shirtColor", editor)
        self.assertIn("pantsColor", editor)
        self.assertIn("eyeColor", editor)
        self.assertIn("shoeColor", editor)
        self.assertIn("headSize", editor)
        self.assertIn("hairVolume", editor)
        self.assertIn("eyeSize", editor)
        self.assertIn("eyeSpacing", editor)
        self.assertIn("mouthWidth", editor)
        self.assertIn("torsoWidth", editor)
        self.assertIn("shoulderWidth", editor)
        self.assertIn("armThickness", editor)
        self.assertIn("legThickness", editor)
        self.assertIn("RefreshAvatar(Vrm10Instance avatar)", mouth)
        self.assertIn("_mouthRuntime?.RefreshAvatar", bootstrap)

    def test_unity_body_supports_transparent_desktop_summary_chat_rail(self) -> None:
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")
        transparency = Path(
            "body-unity/Assets/AxiomBody/Runtime/WindowsDesktopTransparency.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("WindowsDesktopTransparency", bootstrap)
        self.assertIn("_desktopTransparency.Apply(camera)", bootstrap)
        self.assertIn("Application.runInBackground = true", bootstrap)
        self.assertIn("Screen.width * 0.34f", bootstrap)
        self.assertIn('"Chat"', bootstrap)
        self.assertIn("GUI.TextArea", bootstrap)
        self.assertIn("SendInteractionAsync", bootstrap)
        self.assertIn("AppendChat", bootstrap)
        self.assertIn("_chatTranscript", bootstrap)
        self.assertIn("0.36f", bootstrap)

        self.assertIn("DwmExtendFrameIntoClientArea", transparency)
        self.assertIn("GetActiveWindow", transparency)
        self.assertIn("new Color(0f, 0f, 0f, 0f)", transparency)
        self.assertIn("UNITY_STANDALONE_WIN", transparency)
        self.assertIn("!UNITY_EDITOR", transparency)

    def test_unity_body_restores_summary_view(self) -> None:
        client = Path(
            "body-unity/Assets/AxiomBody/Runtime/MindApiClient.cs"
        ).read_text(encoding="utf-8")
        data_runtime = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomMindDataRuntime.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("/v1/portal/status", client)
        self.assertIn("DesktopPortalStatus", client)
        self.assertIn("PortalStatusAsync", client)
        self.assertIn("LoadSummaryAsync", data_runtime)
        self.assertIn("DesktopView.Summary", bootstrap)
        self.assertIn("DrawSummaryView", bootstrap)
        self.assertIn('"Summary"', bootstrap)
        self.assertIn("durable_memory_count", bootstrap)
        self.assertIn("journal_experience_count", bootstrap)
        self.assertIn("await _mindData.LoadSummaryAsync()", bootstrap)
        self.assertIn('"Primary: External Host · "', bootstrap)
        self.assertIn('"Fallback: "', bootstrap)
        self.assertIn("external_host_protocol", client)

    def test_unity_body_has_memory_and_journal_views(self) -> None:
        client = Path(
            "body-unity/Assets/AxiomBody/Runtime/MindApiClient.cs"
        ).read_text(encoding="utf-8")
        data_runtime = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomMindDataRuntime.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("/v1/portal/memory?order=newest", client)
        self.assertIn("/v1/portal/journal?order=newest", client)
        self.assertIn("UnityWebRequest.EscapeURL", client)
        self.assertIn("DesktopMemoryPage", client)
        self.assertIn("DesktopJournalPage", client)
        self.assertIn("PageSize = 12", data_runtime)
        self.assertIn("LoadMemoryAsync", data_runtime)
        self.assertIn("LoadJournalAsync", data_runtime)
        self.assertIn("NextMemoryAsync", data_runtime)
        self.assertIn("PreviousMemoryAsync", data_runtime)
        self.assertIn("NextJournalAsync", data_runtime)
        self.assertIn("PreviousJournalAsync", data_runtime)
        self.assertIn("DesktopView.Memory", bootstrap)
        self.assertIn("DesktopView.Journal", bootstrap)
        self.assertIn("DrawMemoryView", bootstrap)
        self.assertIn("DrawJournalView", bootstrap)
        self.assertIn('"Memory"', bootstrap)
        self.assertIn('"Journal"', bootstrap)
        self.assertIn("_mindData.MemorySearch", bootstrap)
        self.assertIn("_mindData.MemoryClass", bootstrap)
        self.assertIn("_mindData.MemoryAssociation", bootstrap)
        self.assertIn("_mindData.MemoryGrounding", bootstrap)
        self.assertIn("_mindData.MemoryFrom", bootstrap)
        self.assertIn("_mindData.MemoryTo", bootstrap)
        self.assertIn("_mindData.JournalSearch", bootstrap)
        self.assertIn("_mindData.JournalKind", bootstrap)
        self.assertIn("_mindData.JournalFrom", bootstrap)
        self.assertIn("_mindData.JournalTo", bootstrap)
        self.assertIn('AppendQuery(path, "memory_class"', client)
        self.assertIn('AppendQuery(path, "association"', client)
        self.assertIn('AppendQuery(path, "grounding"', client)
        self.assertIn('AppendQuery(path, "kind"', client)

    def test_unity_body_has_session_only_admin_memory_editing(self) -> None:
        client = Path(
            "body-unity/Assets/AxiomBody/Runtime/MindApiClient.cs"
        ).read_text(encoding="utf-8")
        admin = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomAdminRuntime.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")
        api = Path(
            "src/aicognitive_mind/api.py"
        ).read_text(encoding="utf-8")

        self.assertIn("/v1/admin/status", client)
        self.assertIn("/v1/admin/desktop/memory", client)
        self.assertIn("X-Admin-Pin", client)
        self.assertIn("AdminStatusAsync", client)
        self.assertIn("ReviseMemoryAsync", client)
        self.assertIn("AxiomAdminRuntime", bootstrap)
        self.assertNotIn("DesktopView.Admin", bootstrap)
        self.assertIn('"Admin"', bootstrap)
        self.assertIn("DrawAdminAuthorization", bootstrap)
        self.assertIn("AuthorizeAdminAsync", bootstrap)
        self.assertIn("_adminRuntime.Authorized", bootstrap)
        self.assertIn("_adminRuntime.BeginEdit(item)", bootstrap)
        self.assertIn("DrawMemoryEditor(width, height)", bootstrap)
        self.assertIn("public async Task AuthorizeAsync(string pin)", admin)
        self.assertIn("public void Deauthorize()", admin)
        self.assertIn("public void BeginEdit", admin)
        self.assertIn("GUI.PasswordField", admin)
        self.assertIn("Save Revision", admin)
        self.assertIn("memory_revision", api.lower())
        self.assertIn('channel="desktop"', api)
        self.assertIn("artifacts=original.artifacts", api)
        self.assertNotIn("PlayerPrefs", admin)

    def test_genesis_avatar_exposes_vrm_aa_mouth_expression(self) -> None:
        genesis = Path(
            "src/aicognitive_mind/body/genesis_avatar.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"aaOpen"', genesis)
        self.assertIn('"aa": {', genesis)
        self.assertIn('"index": 1', genesis)
        self.assertIn("mouth_open_delta", genesis)

    def test_unity_body_runtime_loads_vrm_and_persists_across_scenes(self) -> None:
        loader = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomAvatarLoader.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("Vrm10.LoadBytesAsync", loader)
        self.assertIn("DontDestroyOnLoad", bootstrap)
        self.assertIn("RuntimeInitializeOnLoadMethod", bootstrap)
        self.assertIn("FindAnyObjectByType", bootstrap)
        self.assertNotIn("FindFirstObjectByType", bootstrap)


if __name__ == "__main__":
    unittest.main()
