// Copyright (c) 2026 William Enright. All rights reserved.
// Use, reproduction, modification, distribution, or commercial exploitation
// of this file is prohibited without prior written permission from the
// copyright holder.

using System;
using System.Threading.Tasks;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class AxiomBodyBootstrap : MonoBehaviour
    {
        private MindApiClient _client;
        private AxiomAvatarLoader _avatarLoader;
        private AxiomMouthRuntime _mouthRuntime;
        private AxiomSensesRuntime _sensesRuntime;
        private AxiomBodyMotionRuntime _bodyMotionRuntime;
        private AxiomAvatarEditorRuntime _avatarEditor;
        private AxiomMindDataRuntime _mindData;
        private AxiomAdminRuntime _adminRuntime;
        private WindowsDesktopTransparency _desktopTransparency;
        private string _status = "Starting Axiom Body...";
        private string _message = string.Empty;
        private string _reply = string.Empty;
        private string _chatTranscript = string.Empty;
        private string _mindUrl = string.Empty;
        private string _mindUsername = string.Empty;
        private string _mindPassword = string.Empty;
        private bool _sending;
        private bool _connecting;
        private bool _connected;
        private bool _sensesChanging;
        private bool _bodySwitching;
        private bool _connectionDialogOpen = true;
        private bool _modeDropdownOpen;
        private bool _bodyDropdownOpen;
        private bool _adminPromptOpen;
        private string _adminPinInput = string.Empty;
        private BodyModelPolicy _bodyModelPolicy =
            BodyModelPolicy.CognitiveOnly;
        private DesktopView _view = DesktopView.Summary;
        private Vector2 _avatarScroll = Vector2.zero;
        private Vector2 _memoryScroll = Vector2.zero;
        private Vector2 _journalScroll = Vector2.zero;
        private Vector2 _chatScroll = Vector2.zero;
        private string _avatarEditorStatus = "Appearance changes preview immediately.";
        private string _skinColorText = "#b88566";
        private string _hairColorText = "#090a0d";
        private string _shirtColorText = "#2e4257";
        private string _pantsColorText = "#1a1f29";
        private string _eyeColorText = "#090a0d";
        private string _shoeColorText = "#090a0d";

        private static readonly string[] MemoryFilterClasses =
        {
            "",
            "working",
            "episodic",
            "semantic",
            "procedural",
            "identity",
            "reflective"
        };

        private static readonly string[] JournalFilterKinds =
        {
            "",
            "initialization",
            "interaction",
            "reflection",
            "tension",
            "checkpoint",
            "memory_revision",
            "belief_transition",
            "belief_reframe",
            "sensory_evidence",
            "evidence_review",
            "identity_revision"
        };

        private enum DesktopView
        {
            Body,
            Summary,
            Bodies,
            Avatar,
            Memory,
            Journal
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void CreateRuntime()
        {
            if (FindAnyObjectByType<AxiomBodyBootstrap>() != null)
            {
                return;
            }

            GameObject runtime = new GameObject("Axiom Body Runtime");
            DontDestroyOnLoad(runtime);
            runtime.AddComponent<AxiomBodyBootstrap>();
        }

        private void Start()
        {
            _mindUrl = AxiomRuntimeConfig.MindBaseUrl;
            _mindUsername = AxiomRuntimeConfig.MindUsername;
            _mindPassword = AxiomRuntimeConfig.MindPassword;
            _bodyModelPolicy = AxiomRuntimeConfig.ModelPolicy;

            Camera camera = EnsureCamera();
            EnsureLight();

            _desktopTransparency =
                gameObject.AddComponent<WindowsDesktopTransparency>();
            _desktopTransparency.Apply(camera);
            Application.runInBackground = true;

            _status = "Not connected.";
            _connectionDialogOpen = true;
        }

        private async Task ConnectAsync()
        {
            if (_connecting)
            {
                return;
            }

            string normalizedUrl = AxiomRuntimeConfig.NormalizeBaseUrl(_mindUrl);
            if (string.IsNullOrWhiteSpace(normalizedUrl))
            {
                _status = "Enter the Mind URL.";
                return;
            }

            _connecting = true;
            _connected = false;
            _view = DesktopView.Summary;
            _modeDropdownOpen = false;
            _bodyDropdownOpen = false;
            _mouthRuntime?.Detach();
            _sensesRuntime?.Detach();
            _bodyMotionRuntime?.Detach();
            _status = "Connecting to Mind...";

            try
            {
                _client = new MindApiClient(
                    normalizedUrl,
                    string.IsNullOrWhiteSpace(_mindUsername) ? "mind" : _mindUsername.Trim(),
                    _mindPassword
                );

                await _client.HealthAsync();
                await _client.AuthenticateAsync();

                Camera camera = EnsureCamera();
                _status = "Loading Axiom...";

                if (_avatarLoader == null)
                {
                    _avatarLoader = gameObject.AddComponent<AxiomAvatarLoader>();
                }

                if (_avatarLoader.Root == null)
                {
                    await _avatarLoader.LoadSelectedAsync(
                        _client,
                        camera
                    );
                }

                _mindUrl = normalizedUrl;
                _mindUsername = string.IsNullOrWhiteSpace(_mindUsername)
                    ? "mind"
                    : _mindUsername.Trim();

                AxiomRuntimeConfig.SaveConnection(_mindUrl, _mindUsername);

                if (_avatarEditor == null)
                {
                    _avatarEditor =
                        gameObject.AddComponent<AxiomAvatarEditorRuntime>();
                }
                if (
                    _avatarLoader.IsGenesis &&
                    _avatarLoader.Instance != null
                )
                {
                    _avatarEditor.Attach(
                        _avatarLoader.Instance
                    );
                    LoadAvatarEditorFields();
                }

                if (_mindData == null)
                {
                    _mindData = gameObject.AddComponent<AxiomMindDataRuntime>();
                }
                _mindData.Attach(_client);

                if (_adminRuntime == null)
                {
                    _adminRuntime = gameObject.AddComponent<AxiomAdminRuntime>();
                }
                _adminRuntime.Attach(_client, _mindData);

                if (_mouthRuntime == null)
                {
                    _mouthRuntime = gameObject.AddComponent<AxiomMouthRuntime>();
                    _mouthRuntime.StatusChanged += HandleBodyStatus;
                }
                _mouthRuntime.Attach(
                    _client,
                    _avatarLoader.Root,
                    _avatarLoader.Instance
                );

                if (_sensesRuntime == null)
                {
                    _sensesRuntime = gameObject.AddComponent<AxiomSensesRuntime>();
                    _sensesRuntime.StatusChanged += HandleBodyStatus;
                }
                _sensesRuntime.Attach(_client);
                _sensesRuntime.SetModelPolicy(_bodyModelPolicy);

                if (_bodyMotionRuntime == null)
                {
                    _bodyMotionRuntime =
                        gameObject.AddComponent<AxiomBodyMotionRuntime>();
                }
                _bodyMotionRuntime.Attach(
                    _avatarLoader.Root,
                    _mouthRuntime
                );

                _connected = true;
                _connectionDialogOpen = false;
                _view = DesktopView.Summary;
                _status = "Connected.";
                await _mindData.LoadSummaryAsync();
            }
            catch (Exception exception)
            {
                _connected = false;
                _avatarLoader?.Unload();
                _mouthRuntime?.Detach();
                _sensesRuntime?.Detach();
                _bodyMotionRuntime?.Detach();
                _connectionDialogOpen = true;
                _status = "Connection failed: " + exception.Message;
                Debug.LogException(exception);
            }
            finally
            {
                _connecting = false;
            }
        }

        private void HandleBodyStatus(string status)
        {
            _status = status;
        }

        private void Disconnect(bool showConnectionDialog)
        {
            _sensesRuntime?.Detach();
            _mouthRuntime?.Detach();
            _bodyMotionRuntime?.Detach();
            _avatarLoader?.Unload();

            _client = null;
            _connected = false;
            _connecting = false;
            _sending = false;
            _sensesChanging = false;
            _bodySwitching = false;
            _modeDropdownOpen = false;
            _bodyDropdownOpen = false;
            _view = DesktopView.Summary;
            _adminPromptOpen = false;
            _adminPinInput = string.Empty;
            _adminRuntime?.Deauthorize();
            _status = "Not connected.";
            _connectionDialogOpen = showConnectionDialog;
        }

        private void SetBodyModelPolicy(BodyModelPolicy policy)
        {
            _bodyModelPolicy = policy;
            AxiomRuntimeConfig.SaveBodyModelPolicy(_bodyModelPolicy);
            _sensesRuntime?.SetModelPolicy(_bodyModelPolicy);
            _modeDropdownOpen = false;

            _status =
                _bodyModelPolicy == BodyModelPolicy.FullBodyModel
                    ? "Mode: Full Body Model."
                    : "Mode: Cognitive Only.";
        }

        private void ToggleBodyModelPolicy()
        {
            SetBodyModelPolicy(
                _bodyModelPolicy == BodyModelPolicy.CognitiveOnly
                    ? BodyModelPolicy.FullBodyModel
                    : BodyModelPolicy.CognitiveOnly
            );
        }

        private async Task ToggleSensesAsync()
        {
            if (
                !_connected ||
                _client == null ||
                _sensesChanging ||
                _sensesRuntime == null
            )
            {
                return;
            }

            _sensesChanging = true;
            bool enable = !_sensesRuntime.IsEnabled;
            _status = enable ? "Turning senses on..." : "Turning senses off...";

            try
            {
                await _sensesRuntime.SetEnabledAsync(enable);
            }
            catch (Exception exception)
            {
                _status = "Senses failed: " + exception.Message;
                Debug.LogException(exception);
            }
            finally
            {
                _sensesChanging = false;
            }
        }

        private Camera EnsureCamera()
        {
            Camera camera = Camera.main;
            if (camera != null)
            {
                return camera;
            }

            GameObject cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.055f, 0.06f, 0.075f);
            camera.fieldOfView = 30f;
            return camera;
        }

        private void EnsureLight()
        {
            if (FindAnyObjectByType<Light>() != null)
            {
                return;
            }

            GameObject lightObject = new GameObject("Axiom Key Light");
            Light light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.35f;
            light.transform.rotation = Quaternion.Euler(38f, -28f, 0f);
        }

        private async Task SendInteractionAsync()
        {
            string outgoing = _message.Trim();
            if (
                _sending ||
                !_connected ||
                string.IsNullOrEmpty(outgoing) ||
                _client == null
            )
            {
                return;
            }

            _sending = true;
            _status = "Thinking...";

            try
            {
                AppendChat("You", outgoing);
                MindInteractionResponse response =
                    await _client.InteractAsync(outgoing);
                _reply = response.response_text;
                AppendChat("Axiom", response.response_text);
                _message = string.Empty;

                if (_mouthRuntime != null)
                {
                    await _mouthRuntime.SpeakTextAsync(response.response_text);
                }
                else
                {
                    _status = "Mind responded.";
                }
            }
            catch (Exception exception)
            {
                _status = "Interaction failed: " + exception.Message;
                Debug.LogException(exception);
            }
            finally
            {
                _sending = false;
            }
        }

        private void OnGUI()
        {
            if (_connectionDialogOpen)
            {
                DrawConnectionDialog();
                return;
            }

            if (_view == DesktopView.Avatar)
            {
                DrawAvatarEditor();
            }
            else if (_view == DesktopView.Memory)
            {
                DrawMemoryView();
            }
            else if (_view == DesktopView.Journal)
            {
                DrawJournalView();
            }

            DrawSummaryView();
            DrawControlStrip();

            if (_adminPromptOpen)
            {
                DrawAdminAuthorization();
            }
        }

        private void DrawConnectionDialog()
        {
            const float width = 500f;
            const float height = 246f;
            float left = Mathf.Max(18f, (Screen.width - width) * 0.5f);
            float top = Mathf.Max(18f, (Screen.height - height) * 0.5f);

            GUI.Box(
                new Rect(left, top, width, height),
                "Connect Axiom"
            );

            GUI.Label(
                new Rect(left + 24f, top + 42f, 90f, 24f),
                "Mind URL"
            );
            _mindUrl = GUI.TextField(
                new Rect(left + 116f, top + 38f, width - 140f, 30f),
                _mindUrl,
                500
            );

            GUI.Label(
                new Rect(left + 24f, top + 82f, 90f, 24f),
                "Username"
            );
            _mindUsername = GUI.TextField(
                new Rect(left + 116f, top + 78f, width - 140f, 30f),
                _mindUsername,
                120
            );

            GUI.Label(
                new Rect(left + 24f, top + 122f, 90f, 24f),
                "Password"
            );
            _mindPassword = GUI.PasswordField(
                new Rect(left + 116f, top + 118f, width - 140f, 30f),
                _mindPassword,
                '*',
                240
            );

            GUI.enabled = !_connecting;
            if (
                GUI.Button(
                    new Rect(left + 116f, top + 166f, 108f, 32f),
                    _connecting ? "Connecting..." : "Connect"
                )
            )
            {
                _ = ConnectAsync();
            }

            if (
                GUI.Button(
                    new Rect(left + 236f, top + 166f, 108f, 32f),
                    "Cancel"
                )
            )
            {
                _connectionDialogOpen = false;
                _status = "Not connected.";
            }
            GUI.enabled = true;

            if (!string.IsNullOrWhiteSpace(_status))
            {
                GUI.Label(
                    new Rect(left + 24f, top + 208f, width - 48f, 28f),
                    _status
                );
            }
        }

        private void DrawControlStrip()
        {
            float railWidth = Mathf.Clamp(
                Screen.width * 0.34f,
                360f,
                500f
            );
            float left = Screen.width - railWidth - 10f;
            const float top = 8f;
            const float buttonHeight = 28f;
            const float gap = 5f;
            float innerLeft = left + 10f;
            float innerWidth = railWidth - 20f;

            Color priorBackground = GUI.backgroundColor;
            GUIStyle smallButton = new GUIStyle(GUI.skin.button)
            {
                fontSize = 11
            };

            float row1Y = top + 8f;
            float x = innerLeft;

            GUI.backgroundColor = _connected
                ? new Color(0.20f, 0.78f, 0.30f)
                : new Color(0.86f, 0.22f, 0.22f);
            if (
                GUI.Button(
                    new Rect(x, row1Y, 48f, buttonHeight),
                    _connected ? "ON" : "OFF",
                    smallButton
                )
            )
            {
                if (_connected)
                {
                    Disconnect(showConnectionDialog: true);
                }
                else
                {
                    _connectionDialogOpen = true;
                }
            }
            GUI.backgroundColor = priorBackground;
            x += 48f + gap;

            string modeLabel =
                _bodyModelPolicy == BodyModelPolicy.FullBodyModel
                    ? "Full ▼"
                    : "Cognitive ▼";
            float modeWidth = 86f;
            if (
                GUI.Button(
                    new Rect(x, row1Y, modeWidth, buttonHeight),
                    modeLabel,
                    smallButton
                )
            )
            {
                _modeDropdownOpen = !_modeDropdownOpen;
                _bodyDropdownOpen = false;
            }
            float modeX = x;
            x += modeWidth + gap;

            string bodyName =
                _avatarLoader != null && _avatarLoader.Root != null
                    ? _avatarLoader.CurrentBodyName
                    : "Body";
            float bodyWidth = Mathf.Max(
                92f,
                innerWidth - (48f + modeWidth + 72f + (gap * 3f))
            );
            GUI.enabled = _connected && _avatarLoader != null;
            if (
                GUI.Button(
                    new Rect(x, row1Y, bodyWidth, buttonHeight),
                    CompactText(bodyName, 16) + " ▼",
                    smallButton
                )
            )
            {
                _bodyDropdownOpen = !_bodyDropdownOpen;
                _modeDropdownOpen = false;
            }
            float bodyX = x;
            GUI.enabled = true;
            x += bodyWidth + gap;

            bool sensesOn =
                _connected &&
                _sensesRuntime != null &&
                _sensesRuntime.IsEnabled;
            GUI.backgroundColor = sensesOn
                ? new Color(0.20f, 0.78f, 0.30f)
                : new Color(0.86f, 0.22f, 0.22f);
            GUI.enabled =
                _connected &&
                !_sensesChanging &&
                _sensesRuntime != null;
            if (
                GUI.Button(
                    new Rect(x, row1Y, 72f, buttonHeight),
                    "Senses",
                    smallButton
                )
            )
            {
                _ = ToggleSensesAsync();
            }
            GUI.enabled = true;
            GUI.backgroundColor = priorBackground;

            float row2Y = row1Y + buttonHeight + gap;
            float row2Width = (innerWidth - (gap * 3f)) / 4f;
            x = innerLeft;

            GUI.enabled = _connected && _mindData != null;
            if (
                GUI.Button(
                    new Rect(x, row2Y, row2Width, buttonHeight),
                    "Home",
                    smallButton
                )
            )
            {
                _view = DesktopView.Summary;
                _ = _mindData.LoadSummaryAsync();
            }
            x += row2Width + gap;

            if (
                GUI.Button(
                    new Rect(x, row2Y, row2Width, buttonHeight),
                    "Memory",
                    smallButton
                )
            )
            {
                _memoryScroll = Vector2.zero;
                _view = DesktopView.Memory;
                _ = _mindData.LoadMemoryAsync(0);
            }
            x += row2Width + gap;

            if (
                GUI.Button(
                    new Rect(x, row2Y, row2Width, buttonHeight),
                    "Journal",
                    smallButton
                )
            )
            {
                _journalScroll = Vector2.zero;
                _view = DesktopView.Journal;
                _ = _mindData.LoadJournalAsync(0);
            }
            x += row2Width + gap;

            GUI.enabled = _connected && _adminRuntime != null;
            bool adminOn =
                _adminRuntime != null &&
                _adminRuntime.Authorized;
            GUI.backgroundColor = adminOn
                ? new Color(0.20f, 0.78f, 0.30f)
                : priorBackground;
            if (
                GUI.Button(
                    new Rect(x, row2Y, row2Width, buttonHeight),
                    adminOn ? "Admin ✓" : "Admin",
                    smallButton
                )
            )
            {
                if (adminOn)
                {
                    _adminRuntime.Deauthorize();
                    _adminPromptOpen = false;
                    _adminPinInput = string.Empty;
                    _status = "Administrator mode off.";
                }
                else
                {
                    _adminPromptOpen = true;
                    _adminPinInput = string.Empty;
                }
            }
            GUI.backgroundColor = priorBackground;
            GUI.enabled = true;

            if (_modeDropdownOpen)
            {
                DrawModeDropdown(
                    modeX,
                    row1Y + buttonHeight + 2f
                );
            }

            if (_bodyDropdownOpen)
            {
                DrawBodyDropdown(
                    bodyX,
                    row1Y + buttonHeight + 2f
                );
            }
        }

        private void DrawAdminAuthorization()
        {
            const float width = 390f;
            const float height = 146f;
            float left = Mathf.Max(18f, (Screen.width - width) * 0.5f);
            float top = 62f;

            GUI.Box(
                new Rect(left, top, width, height),
                "Administrator Authorization"
            );
            GUI.Label(
                new Rect(left + 20f, top + 38f, 86f, 24f),
                "Admin PIN"
            );
            _adminPinInput = GUI.PasswordField(
                new Rect(left + 106f, top + 34f, width - 126f, 30f),
                _adminPinInput,
                '*',
                120
            );

            GUI.enabled =
                _adminRuntime != null &&
                !_adminRuntime.Busy;
            if (
                GUI.Button(
                    new Rect(left + 106f, top + 82f, 100f, 30f),
                    "Authorize"
                )
            )
            {
                _ = AuthorizeAdminAsync();
            }
            if (
                GUI.Button(
                    new Rect(left + 216f, top + 82f, 90f, 30f),
                    "Cancel"
                )
            )
            {
                _adminPromptOpen = false;
                _adminPinInput = string.Empty;
            }
            GUI.enabled = true;

            if (_adminRuntime != null)
            {
                GUI.Label(
                    new Rect(left + 20f, top + 116f, width - 40f, 24f),
                    CompactText(_adminRuntime.Status, 90)
                );
            }
        }

        private async Task AuthorizeAdminAsync()
        {
            if (_adminRuntime == null)
            {
                return;
            }

            await _adminRuntime.AuthorizeAsync(_adminPinInput);
            if (_adminRuntime.Authorized)
            {
                _adminPromptOpen = false;
                _adminPinInput = string.Empty;
                _status = "Administrator mode on.";
            }
            else
            {
                _status = _adminRuntime.Status;
            }
        }

        private void DrawModeDropdown(float left, float top)
        {
            const float width = 150f;
            const float rowHeight = 30f;
            GUI.Box(
                new Rect(left, top, width, (rowHeight * 2f) + 8f),
                string.Empty
            );

            if (
                GUI.Button(
                    new Rect(left + 4f, top + 4f, width - 8f, rowHeight),
                    "Cognitive Only"
                )
            )
            {
                SetBodyModelPolicy(BodyModelPolicy.CognitiveOnly);
            }

            if (
                GUI.Button(
                    new Rect(
                        left + 4f,
                        top + 4f + rowHeight,
                        width - 8f,
                        rowHeight
                    ),
                    "Full Body Model"
                )
            )
            {
                SetBodyModelPolicy(BodyModelPolicy.FullBodyModel);
            }
        }

        private void DrawBodyDropdown(float left, float top)
        {
            if (_avatarLoader == null)
            {
                _bodyDropdownOpen = false;
                return;
            }

            string[] bodies = _avatarLoader.AvailableBodies;
            const float width = 150f;
            const float rowHeight = 30f;
            float boxHeight =
                Mathf.Max(rowHeight + 8f, (bodies.Length * rowHeight) + 8f);

            GUI.Box(
                new Rect(left, top, width, boxHeight),
                string.Empty
            );

            GUI.enabled = !_bodySwitching;
            for (int index = 0; index < bodies.Length; index++)
            {
                string bodyName = bodies[index];
                if (
                    GUI.Button(
                        new Rect(
                            left + 4f,
                            top + 4f + (index * rowHeight),
                            width - 8f,
                            rowHeight
                        ),
                        bodyName
                    )
                )
                {
                    _bodyDropdownOpen = false;
                    if (
                        !string.Equals(
                            bodyName,
                            _avatarLoader.CurrentBodyName,
                            StringComparison.OrdinalIgnoreCase
                        )
                    )
                    {
                        _ = SwitchBodyAsync(bodyName);
                    }
                }
            }
            GUI.enabled = true;
        }

        private void DrawSummaryView()
        {
            if (_mindData == null)
            {
                return;
            }

            float width = Mathf.Clamp(
                Screen.width * 0.34f,
                360f,
                500f
            );
            float left = Screen.width - width - 10f;
            const float top = 76f;
            float height = Mathf.Max(
                360f,
                Screen.height - top - 18f
            );

            Color priorColor = GUI.color;
            GUI.color = new Color(1f, 1f, 1f, 0.36f);
            GUI.Box(
                new Rect(
                    left,
                    8f,
                    width,
                    Screen.height - 18f
                ),
                string.Empty
            );
            GUI.color = priorColor;

            DesktopPortalStatus summary =
                _mindData.Summary ?? new DesktopPortalStatus();
            DesktopMindSummary mind =
                summary.mind ?? new DesktopMindSummary();
            DesktopMindIdentity identity =
                mind.identity ?? new DesktopMindIdentity();

            float innerLeft = left + 14f;
            float innerWidth = width - 28f;
            float y = top + 4f;

            GUIStyle heading = new GUIStyle(GUI.skin.label)
            {
                fontSize = 14,
                fontStyle = FontStyle.Bold
            };

            GUI.Label(
                new Rect(innerLeft, y, innerWidth - 66f, 22f),
                "Summary",
                heading
            );

            GUI.enabled = !_mindData.LoadingSummary;
            if (
                GUI.Button(
                    new Rect(
                        left + width - 66f,
                        y - 2f,
                        54f,
                        22f
                    ),
                    "↻"
                )
            )
            {
                _ = _mindData.LoadSummaryAsync();
            }
            GUI.enabled = true;
            y += 25f;

            GUI.Label(
                new Rect(innerLeft, y, innerWidth, 20f),
                (
                    string.IsNullOrWhiteSpace(identity.self_name)
                        ? "Axiom"
                        : identity.self_name
                ) +
                (
                    string.IsNullOrWhiteSpace(identity.pronouns)
                        ? string.Empty
                        : " · " + identity.pronouns
                ) +
                " · " +
                (
                    string.IsNullOrWhiteSpace(mind.developmental_state)
                        ? "—"
                        : mind.developmental_state
                )
            );
            y += 21f;

            string fallbackReasoning =
                summary.reasoning != null
                    ? (
                        (summary.reasoning.backend ?? string.Empty) +
                        " · " +
                        (summary.reasoning.model ?? string.Empty)
                    ).Trim(' ', '·')
                    : string.Empty;
            string hostProtocol =
                summary.reasoning != null &&
                !string.IsNullOrWhiteSpace(
                    summary.reasoning.external_host_protocol
                )
                    ? summary.reasoning.external_host_protocol
                    : "MCP";

            GUI.Label(
                new Rect(innerLeft, y, innerWidth, 20f),
                "Memory " +
                summary.durable_memory_count +
                " · Journal " +
                summary.journal_experience_count
            );
            y += 21f;

            GUI.Label(
                new Rect(innerLeft, y, innerWidth, 20f),
                "Primary: External Host · " + hostProtocol
            );
            y += 21f;

            GUI.Label(
                new Rect(innerLeft, y, innerWidth, 20f),
                "Fallback: " +
                (
                    string.IsNullOrWhiteSpace(fallbackReasoning)
                        ? "Not configured"
                        : fallbackReasoning
                )
            );
            y += 21f;

            GUI.Label(
                new Rect(innerLeft, y, innerWidth, 20f),
                (
                    _avatarLoader == null
                        ? "Body —"
                        : _avatarLoader.CurrentBodyName
                ) +
                " · " +
                (
                    _bodyModelPolicy ==
                    BodyModelPolicy.FullBodyModel
                        ? "Full"
                        : "Cognitive"
                ) +
                " · Senses " +
                (
                    _sensesRuntime != null &&
                    _sensesRuntime.IsEnabled
                        ? "On"
                        : "Off"
                )
            );
            y += 25f;

            GUI.Box(
                new Rect(innerLeft, y, innerWidth, 1f),
                string.Empty
            );
            y += 9f;

            GUI.Label(
                new Rect(innerLeft, y, innerWidth, 22f),
                "Chat",
                heading
            );
            y += 24f;

            const float inputHeight = 62f;
            const float sendHeight = 26f;
            float transcriptHeight = Mathf.Max(
                100f,
                top + height -
                y -
                inputHeight -
                sendHeight -
                18f
            );

            GUIStyle transcriptStyle =
                new GUIStyle(GUI.skin.label)
                {
                    wordWrap = true,
                    alignment = TextAnchor.UpperLeft,
                    padding = new RectOffset(6, 6, 6, 6)
                };

            string transcript =
                string.IsNullOrWhiteSpace(_chatTranscript)
                    ? "Chat with Axiom."
                    : _chatTranscript;

            float transcriptContentHeight = Mathf.Max(
                transcriptHeight - 4f,
                transcriptStyle.CalcHeight(
                    new GUIContent(transcript),
                    innerWidth - 24f
                ) + 12f
            );

            _chatScroll = GUI.BeginScrollView(
                new Rect(
                    innerLeft,
                    y,
                    innerWidth,
                    transcriptHeight
                ),
                _chatScroll,
                new Rect(
                    0f,
                    0f,
                    innerWidth - 16f,
                    transcriptContentHeight
                )
            );
            GUI.Label(
                new Rect(
                    0f,
                    0f,
                    innerWidth - 20f,
                    transcriptContentHeight
                ),
                transcript,
                transcriptStyle
            );
            GUI.EndScrollView();

            y += transcriptHeight + 5f;

            _message = GUI.TextArea(
                new Rect(
                    innerLeft,
                    y,
                    innerWidth,
                    inputHeight
                ),
                _message ?? string.Empty,
                4000
            );
            y += inputHeight + 4f;

            GUI.enabled =
                _connected &&
                !_sending &&
                !string.IsNullOrWhiteSpace(_message);
            if (
                GUI.Button(
                    new Rect(
                        left + width - 76f,
                        y,
                        64f,
                        sendHeight
                    ),
                    _sending ? "..." : "Send"
                )
            )
            {
                _ = SendInteractionAsync();
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(
                    innerLeft,
                    y + 3f,
                    innerWidth - 72f,
                    22f
                ),
                CompactText(_status, 72)
            );
        }

        private void AppendChat(string speaker, string text)
        {
            string content = (text ?? string.Empty).Trim();
            if (string.IsNullOrWhiteSpace(content))
            {
                return;
            }

            if (!string.IsNullOrWhiteSpace(_chatTranscript))
            {
                _chatTranscript += "\n\n";
            }

            _chatTranscript += speaker + ": " + content;
            _chatScroll.y = float.MaxValue;
        }

        private void DrawMemoryView()
        {
            const float width = 760f;
            const float top = 58f;
            float height = Mathf.Min(
                720f,
                Mathf.Max(500f, Screen.height - 76f)
            );

            GUI.Box(new Rect(18f, top, width, height), "Memory");

            if (_mindData == null)
            {
                GUI.Label(
                    new Rect(34f, top + 42f, width - 68f, 40f),
                    "Memory data is unavailable."
                );
                return;
            }

            if (
                _adminRuntime != null &&
                _adminRuntime.EditingMemory
            )
            {
                _adminRuntime.DrawMemoryEditor(width, height);
                return;
            }

            GUI.Label(
                new Rect(34f, top + 34f, 90f, 24f),
                "Filters"
            );

            GUI.Label(
                new Rect(34f, top + 64f, 52f, 24f),
                "Search"
            );
            _mindData.MemorySearch = GUI.TextField(
                new Rect(88f, top + 60f, 318f, 28f),
                _mindData.MemorySearch ?? string.Empty,
                200
            );

            string classLabel =
                string.IsNullOrWhiteSpace(_mindData.MemoryClass)
                    ? "Class: All"
                    : "Class: " + _mindData.MemoryClass;
            if (
                GUI.Button(
                    new Rect(416f, top + 60f, 150f, 28f),
                    classLabel
                )
            )
            {
                _mindData.MemoryClass = NextFilter(
                    _mindData.MemoryClass,
                    MemoryFilterClasses
                );
            }

            GUI.enabled = !_mindData.LoadingMemory;
            if (
                GUI.Button(
                    new Rect(576f, top + 60f, 76f, 28f),
                    "Apply"
                )
            )
            {
                _memoryScroll = Vector2.zero;
                _ = _mindData.LoadMemoryAsync(0);
            }
            if (
                GUI.Button(
                    new Rect(662f, top + 60f, 76f, 28f),
                    "Clear"
                )
            )
            {
                ClearMemoryFilters();
                _memoryScroll = Vector2.zero;
                _ = _mindData.LoadMemoryAsync(0);
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(34f, top + 100f, 78f, 24f),
                "Association"
            );
            _mindData.MemoryAssociation = GUI.TextField(
                new Rect(112f, top + 96f, 220f, 28f),
                _mindData.MemoryAssociation ?? string.Empty,
                200
            );

            GUI.Label(
                new Rect(344f, top + 100f, 76f, 24f),
                "Grounding"
            );
            _mindData.MemoryGrounding = GUI.TextField(
                new Rect(420f, top + 96f, 318f, 28f),
                _mindData.MemoryGrounding ?? string.Empty,
                200
            );

            GUI.Label(
                new Rect(34f, top + 136f, 42f, 24f),
                "From"
            );
            _mindData.MemoryFrom = GUI.TextField(
                new Rect(76f, top + 132f, 128f, 28f),
                _mindData.MemoryFrom ?? string.Empty,
                10
            );
            GUI.Label(
                new Rect(214f, top + 136f, 24f, 24f),
                "To"
            );
            _mindData.MemoryTo = GUI.TextField(
                new Rect(240f, top + 132f, 128f, 28f),
                _mindData.MemoryTo ?? string.Empty,
                10
            );
            GUI.Label(
                new Rect(378f, top + 136f, 168f, 24f),
                "Dates: YYYY-MM-DD"
            );

            GUI.enabled = !_mindData.LoadingMemory;
            if (
                GUI.Button(
                    new Rect(662f, top + 132f, 76f, 28f),
                    "Refresh"
                )
            )
            {
                _ = _mindData.LoadMemoryAsync(
                    _mindData.MemoryPage.offset
                );
            }
            GUI.enabled = true;

            DesktopMemoryPage page =
                _mindData.MemoryPage ?? new DesktopMemoryPage();
            DesktopMemoryItem[] items =
                page.items ?? Array.Empty<DesktopMemoryItem>();

            Rect viewport = new Rect(
                34f,
                top + 174f,
                width - 50f,
                height - 246f
            );
            float contentHeight = Mathf.Max(
                viewport.height - 4f,
                items.Length * 126f
            );
            _memoryScroll = GUI.BeginScrollView(
                viewport,
                _memoryScroll,
                new Rect(0f, 0f, width - 86f, contentHeight)
            );

            bool canEdit =
                _adminRuntime != null &&
                _adminRuntime.Authorized;

            for (int index = 0; index < items.Length; index++)
            {
                DesktopMemoryItem item = items[index];
                float y = index * 126f;
                GUI.Box(
                    new Rect(0f, y, width - 102f, 116f),
                    string.Empty
                );

                GUI.Label(
                    new Rect(10f, y + 7f, 180f, 22f),
                    (item.memory_class ?? "memory").ToUpperInvariant()
                );
                GUI.Label(
                    new Rect(194f, y + 7f, 190f, 22f),
                    CompactTimestamp(item.formed_at)
                );

                float contentWidth =
                    canEdit ? width - 220f : width - 126f;
                GUI.Label(
                    new Rect(10f, y + 31f, contentWidth, 46f),
                    CompactText(item.content, 220)
                );

                string associations =
                    JoinCompact(item.associations, 90);
                string grounding =
                    JoinCompact(item.grounding, 90);
                GUI.Label(
                    new Rect(10f, y + 80f, contentWidth, 18f),
                    string.IsNullOrEmpty(associations)
                        ? "Associations: —"
                        : "Associations: " + associations
                );
                GUI.Label(
                    new Rect(10f, y + 98f, contentWidth, 18f),
                    string.IsNullOrEmpty(grounding)
                        ? "Grounding: —"
                        : "Grounding: " + grounding
                );

                if (
                    canEdit &&
                    GUI.Button(
                        new Rect(
                            width - 190f,
                            y + 38f,
                            72f,
                            30f
                        ),
                        "Edit"
                    )
                )
                {
                    _adminRuntime.BeginEdit(item);
                }
            }

            GUI.EndScrollView();

            float footerY = top + height - 44f;
            GUI.Label(
                new Rect(34f, footerY, width - 280f, 24f),
                _mindData.MemoryStatus +
                (
                    canEdit
                        ? " · Admin editing enabled"
                        : string.Empty
                )
            );

            GUI.enabled =
                !_mindData.LoadingMemory &&
                page.offset > 0;
            if (
                GUI.Button(
                    new Rect(width - 202f, footerY - 2f, 78f, 28f),
                    "Previous"
                )
            )
            {
                _memoryScroll = Vector2.zero;
                _ = _mindData.PreviousMemoryAsync();
            }

            GUI.enabled =
                !_mindData.LoadingMemory &&
                page.has_more;
            if (
                GUI.Button(
                    new Rect(width - 114f, footerY - 2f, 78f, 28f),
                    "Next"
                )
            )
            {
                _memoryScroll = Vector2.zero;
                _ = _mindData.NextMemoryAsync();
            }
            GUI.enabled = true;
        }

        private void DrawJournalView()
        {
            const float width = 760f;
            const float top = 58f;
            float height = Mathf.Min(
                720f,
                Mathf.Max(500f, Screen.height - 76f)
            );

            GUI.Box(new Rect(18f, top, width, height), "Journal");

            if (_mindData == null)
            {
                GUI.Label(
                    new Rect(34f, top + 42f, width - 68f, 40f),
                    "Journal data is unavailable."
                );
                return;
            }

            GUI.Label(
                new Rect(34f, top + 34f, 90f, 24f),
                "Filters"
            );

            GUI.Label(
                new Rect(34f, top + 64f, 52f, 24f),
                "Search"
            );
            _mindData.JournalSearch = GUI.TextField(
                new Rect(88f, top + 60f, 318f, 28f),
                _mindData.JournalSearch ?? string.Empty,
                200
            );

            string kindLabel =
                string.IsNullOrWhiteSpace(_mindData.JournalKind)
                    ? "Kind: All"
                    : "Kind: " + _mindData.JournalKind;
            if (
                GUI.Button(
                    new Rect(416f, top + 60f, 150f, 28f),
                    kindLabel
                )
            )
            {
                _mindData.JournalKind = NextFilter(
                    _mindData.JournalKind,
                    JournalFilterKinds
                );
            }

            GUI.enabled = !_mindData.LoadingJournal;
            if (
                GUI.Button(
                    new Rect(576f, top + 60f, 76f, 28f),
                    "Apply"
                )
            )
            {
                _journalScroll = Vector2.zero;
                _ = _mindData.LoadJournalAsync(0);
            }
            if (
                GUI.Button(
                    new Rect(662f, top + 60f, 76f, 28f),
                    "Clear"
                )
            )
            {
                ClearJournalFilters();
                _journalScroll = Vector2.zero;
                _ = _mindData.LoadJournalAsync(0);
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(34f, top + 102f, 42f, 24f),
                "From"
            );
            _mindData.JournalFrom = GUI.TextField(
                new Rect(76f, top + 98f, 128f, 28f),
                _mindData.JournalFrom ?? string.Empty,
                10
            );
            GUI.Label(
                new Rect(214f, top + 102f, 24f, 24f),
                "To"
            );
            _mindData.JournalTo = GUI.TextField(
                new Rect(240f, top + 98f, 128f, 28f),
                _mindData.JournalTo ?? string.Empty,
                10
            );
            GUI.Label(
                new Rect(378f, top + 102f, 168f, 24f),
                "Dates: YYYY-MM-DD"
            );

            GUI.enabled = !_mindData.LoadingJournal;
            if (
                GUI.Button(
                    new Rect(662f, top + 98f, 76f, 28f),
                    "Refresh"
                )
            )
            {
                _ = _mindData.LoadJournalAsync(
                    _mindData.JournalPage.offset
                );
            }
            GUI.enabled = true;

            DesktopJournalPage page =
                _mindData.JournalPage ?? new DesktopJournalPage();
            DesktopJournalItem[] items =
                page.items ?? Array.Empty<DesktopJournalItem>();

            Rect viewport = new Rect(
                34f,
                top + 140f,
                width - 50f,
                height - 212f
            );
            float contentHeight = Mathf.Max(
                viewport.height - 4f,
                items.Length * 96f
            );
            _journalScroll = GUI.BeginScrollView(
                viewport,
                _journalScroll,
                new Rect(0f, 0f, width - 86f, contentHeight)
            );

            for (int index = 0; index < items.Length; index++)
            {
                DesktopJournalItem item = items[index];
                float y = index * 96f;
                GUI.Box(
                    new Rect(0f, y, width - 102f, 86f),
                    string.Empty
                );

                GUI.Label(
                    new Rect(10f, y + 7f, 220f, 22f),
                    string.IsNullOrWhiteSpace(item.title)
                        ? (item.kind ?? "Journal")
                        : item.title
                );
                GUI.Label(
                    new Rect(234f, y + 7f, width - 356f, 22f),
                    CompactTimestamp(item.occurred_at)
                );
                GUI.Label(
                    new Rect(10f, y + 32f, width - 126f, 44f),
                    CompactText(item.preview, 250)
                );
            }

            GUI.EndScrollView();

            float footerY = top + height - 44f;
            GUI.Label(
                new Rect(34f, footerY, width - 280f, 24f),
                _mindData.JournalStatus
            );

            GUI.enabled =
                !_mindData.LoadingJournal &&
                page.offset > 0;
            if (
                GUI.Button(
                    new Rect(width - 202f, footerY - 2f, 78f, 28f),
                    "Previous"
                )
            )
            {
                _journalScroll = Vector2.zero;
                _ = _mindData.PreviousJournalAsync();
            }

            GUI.enabled =
                !_mindData.LoadingJournal &&
                page.has_more;
            if (
                GUI.Button(
                    new Rect(width - 114f, footerY - 2f, 78f, 28f),
                    "Next"
                )
            )
            {
                _journalScroll = Vector2.zero;
                _ = _mindData.NextJournalAsync();
            }
            GUI.enabled = true;
        }

        private void ClearMemoryFilters()
        {
            if (_mindData == null)
            {
                return;
            }

            _mindData.MemorySearch = string.Empty;
            _mindData.MemoryClass = string.Empty;
            _mindData.MemoryAssociation = string.Empty;
            _mindData.MemoryGrounding = string.Empty;
            _mindData.MemoryFrom = string.Empty;
            _mindData.MemoryTo = string.Empty;
        }

        private void ClearJournalFilters()
        {
            if (_mindData == null)
            {
                return;
            }

            _mindData.JournalSearch = string.Empty;
            _mindData.JournalKind = string.Empty;
            _mindData.JournalFrom = string.Empty;
            _mindData.JournalTo = string.Empty;
        }

        private static string NextFilter(
            string current,
            string[] values
        )
        {
            if (values == null || values.Length == 0)
            {
                return string.Empty;
            }

            int index = Array.IndexOf(
                values,
                current ?? string.Empty
            );
            int next =
                index < 0
                    ? 0
                    : (index + 1) % values.Length;
            return values[next];
        }

        private static string CompactTimestamp(string timestamp)
        {
            if (string.IsNullOrWhiteSpace(timestamp))
            {
                return string.Empty;
            }

            if (DateTimeOffset.TryParse(timestamp, out DateTimeOffset parsed))
            {
                return parsed.ToLocalTime().ToString("yyyy-MM-dd HH:mm");
            }

            return CompactText(timestamp, 22);
        }

        private static string JoinCompact(string[] values, int maxLength)
        {
            if (values == null || values.Length == 0)
            {
                return string.Empty;
            }

            return CompactText(string.Join(", ", values), maxLength);
        }

        private static string CompactText(string value, int maxLength)
        {
            string text = (value ?? string.Empty)
                .Replace("\r", " ")
                .Replace("\n", " ")
                .Trim();

            if (text.Length <= maxLength)
            {
                return text;
            }

            return text.Substring(0, Mathf.Max(0, maxLength - 1)) + "…";
        }

        private async Task SwitchBodyAsync(string bodyName)
        {
            if (
                _bodySwitching ||
                !_connected ||
                _client == null ||
                _avatarLoader == null
            )
            {
                return;
            }

            _bodySwitching = true;
            _status = "Switching body to " + bodyName + "...";

            try
            {
                await _avatarLoader.SelectBodyAsync(
                    bodyName,
                    _client,
                    EnsureCamera()
                );

                if (
                    _avatarLoader.IsGenesis &&
                    _avatarLoader.Instance != null &&
                    _avatarEditor != null
                )
                {
                    _avatarEditor.Attach(
                        _avatarLoader.Instance
                    );
                    LoadAvatarEditorFields();
                }

                _mouthRuntime?.RefreshAvatar(
                    _avatarLoader.Root,
                    _avatarLoader.Instance
                );
                _bodyMotionRuntime?.Attach(
                    _avatarLoader.Root,
                    _mouthRuntime
                );

                _status =
                    "Body selected: " +
                    _avatarLoader.CurrentBodyName +
                    ".";
            }
            catch (Exception exception)
            {
                _status =
                    "Body switch failed: " +
                    exception.Message;
                Debug.LogException(exception);
            }
            finally
            {
                _bodySwitching = false;
            }
        }

        private void DrawBodiesView()
        {
            const float width = 560f;
            float height = Mathf.Min(
                620f,
                Mathf.Max(420f, Screen.height - 36f)
            );

            GUI.Box(
                new Rect(18f, 18f, width, height),
                "Genesis Bodies"
            );

            if (
                GUI.Button(
                    new Rect(34f, 48f, 112f, 30f),
                    "Back to Body"
                )
            )
            {
                _view = DesktopView.Body;
                return;
            }

            if (_avatarLoader == null)
            {
                GUI.Label(
                    new Rect(34f, 96f, width - 68f, 40f),
                    "Connect to the Mind before selecting a body."
                );
                return;
            }

            string[] bodies = _avatarLoader.AvailableBodies;
            int currentIndex = Array.FindIndex(
                bodies,
                value => string.Equals(
                    value,
                    _avatarLoader.CurrentBodyName,
                    StringComparison.OrdinalIgnoreCase
                )
            );
            if (currentIndex < 0)
            {
                currentIndex = 0;
            }

            GUI.Label(
                new Rect(34f, 96f, width - 68f, 24f),
                "Select Axiom's body"
            );

            int columns = Mathf.Min(
                3,
                Mathf.Max(1, bodies.Length)
            );
            int rows = Mathf.CeilToInt(
                bodies.Length / (float)columns
            );
            float gridHeight = Mathf.Max(34f, rows * 34f);

            GUI.enabled = !_bodySwitching;
            int selectedIndex = GUI.SelectionGrid(
                new Rect(
                    34f,
                    126f,
                    width - 68f,
                    gridHeight
                ),
                currentIndex,
                bodies,
                columns
            );
            GUI.enabled = true;

            if (
                selectedIndex != currentIndex &&
                selectedIndex >= 0 &&
                selectedIndex < bodies.Length &&
                !_bodySwitching
            )
            {
                _ = SwitchBodyAsync(
                    bodies[selectedIndex]
                );
            }

            float y = 142f + gridHeight;
            GUI.Label(
                new Rect(34f, y, width - 68f, 28f),
                "Current: " +
                _avatarLoader.CurrentBodyName
            );
            y += 34f;

            if (_avatarLoader.IsGenesis)
            {
                GUI.Label(
                    new Rect(34f, y, width - 68f, 44f),
                    "Genesis is Axiom's editable body. " +
                    "Its saved appearance remains independent " +
                    "of predefined bodies."
                );
                y += 52f;

                GUI.enabled =
                    !_bodySwitching &&
                    _avatarLoader.Instance != null &&
                    _avatarEditor != null;
                if (
                    GUI.Button(
                        new Rect(34f, y, 140f, 30f),
                        "Edit Genesis"
                    )
                )
                {
                    LoadAvatarEditorFields();
                    _view = DesktopView.Avatar;
                }
                GUI.enabled = true;
            }
            else
            {
                GUI.Label(
                    new Rect(34f, y, width - 68f, 52f),
                    "This is a predefined Genesis body. Axiom keeps the " +
                    "same Mind, voice, senses, memory, and identity; " +
                    "only the rendered Body changes."
                );
                y += 62f;

                GUI.Label(
                    new Rect(34f, y, width - 68f, 52f),
                    "Lip sync will use a VRM mouth expression, " +
                    "a common mouth blendshape, or a Mouth transform " +
                    "when the asset exposes one."
                );
            }

            GUI.Label(
                new Rect(
                    34f,
                    height - 72f,
                    width - 68f,
                    46f
                ),
                "Genesis Bodies assets are auto-discovered from " +
                "Assets/Resources/GenesisBodies/."
            );
        }

        private void DrawAvatarEditor()
        {
            const float width = 520f;
            float height = Mathf.Min(650f, Mathf.Max(420f, Screen.height - 36f));

            GUI.Box(new Rect(18f, 18f, width, height), "Genesis Editor");

            if (GUI.Button(new Rect(34f, 48f, 112f, 30f), "Back to Body"))
            {
                _view = DesktopView.Body;
                return;
            }

            if (
                _avatarLoader == null ||
                !_avatarLoader.IsGenesis ||
                _avatarLoader.Instance == null
            )
            {
                GUI.Label(
                    new Rect(34f, 100f, width - 68f, 42f),
                    "Select Genesis before editing its appearance."
                );
                return;
            }

            GUI.enabled = _avatarEditor != null;
            if (GUI.Button(new Rect(158f, 48f, 82f, 30f), "Save"))
            {
                CommitAvatarColors();
                _avatarEditor.ApplyPreview();
                _avatarEditor.Save();
                _mouthRuntime?.RefreshAvatar(_avatarLoader?.Instance);
                _avatarEditorStatus = "Appearance saved on this desktop.";
            }

            if (GUI.Button(new Rect(250f, 48f, 82f, 30f), "Reset"))
            {
                _avatarEditor.Reset();
                LoadAvatarEditorFields();
                _mouthRuntime?.RefreshAvatar(_avatarLoader?.Instance);
                _avatarEditorStatus = "Genesis appearance reset.";
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(344f, 50f, width - 364f, 42f),
                _avatarEditorStatus
            );

            if (_avatarEditor == null)
            {
                GUI.Label(
                    new Rect(34f, 100f, width - 68f, 40f),
                    "Connect to the Mind before editing the avatar."
                );
                return;
            }

            AxiomAvatarAppearance appearance = _avatarEditor.Appearance;
            Rect viewport = new Rect(34f, 96f, width - 50f, height - 116f);
            Rect content = new Rect(0f, 0f, width - 86f, 690f);
            _avatarScroll = GUI.BeginScrollView(
                viewport,
                _avatarScroll,
                content
            );

            bool previewChanged = false;
            float y = 4f;

            GUI.Label(new Rect(0f, y, 180f, 24f), "Colors (hex)");
            y += 30f;

            previewChanged |= DrawColorField(
                ref _skinColorText,
                "Skin",
                ref appearance.skinColor,
                y
            );
            y += 32f;
            previewChanged |= DrawColorField(
                ref _hairColorText,
                "Hair",
                ref appearance.hairColor,
                y
            );
            y += 32f;
            previewChanged |= DrawColorField(
                ref _shirtColorText,
                "Shirt",
                ref appearance.shirtColor,
                y
            );
            y += 32f;
            previewChanged |= DrawColorField(
                ref _pantsColorText,
                "Pants",
                ref appearance.pantsColor,
                y
            );
            y += 32f;
            previewChanged |= DrawColorField(
                ref _eyeColorText,
                "Eyes",
                ref appearance.eyeColor,
                y
            );
            y += 32f;
            previewChanged |= DrawColorField(
                ref _shoeColorText,
                "Shoes",
                ref appearance.shoeColor,
                y
            );
            y += 42f;

            GUI.Label(new Rect(0f, y, 180f, 24f), "Proportions");
            y += 30f;

            previewChanged |= DrawAvatarSlider(
                ref appearance.headSize,
                "Head size",
                0.75f,
                1.35f,
                y
            );
            y += 38f;
            previewChanged |= DrawAvatarSlider(
                ref appearance.hairVolume,
                "Hair volume",
                0.60f,
                1.60f,
                y
            );
            y += 38f;
            previewChanged |= DrawAvatarSlider(
                ref appearance.eyeSize,
                "Eye size",
                0.60f,
                1.60f,
                y
            );
            y += 38f;
            previewChanged |= DrawAvatarSlider(
                ref appearance.eyeSpacing,
                "Eye spacing",
                0.65f,
                1.45f,
                y
            );
            y += 38f;
            previewChanged |= DrawAvatarSlider(
                ref appearance.mouthWidth,
                "Mouth width",
                0.60f,
                1.50f,
                y
            );
            y += 38f;
            previewChanged |= DrawAvatarSlider(
                ref appearance.torsoWidth,
                "Torso width",
                0.70f,
                1.40f,
                y
            );
            y += 38f;
            previewChanged |= DrawAvatarSlider(
                ref appearance.shoulderWidth,
                "Shoulder width",
                0.75f,
                1.40f,
                y
            );
            y += 38f;
            previewChanged |= DrawAvatarSlider(
                ref appearance.armThickness,
                "Arm thickness",
                0.65f,
                1.50f,
                y
            );
            y += 38f;
            previewChanged |= DrawAvatarSlider(
                ref appearance.legThickness,
                "Leg thickness",
                0.65f,
                1.50f,
                y
            );

            GUI.EndScrollView();

            if (previewChanged)
            {
                _avatarEditor.ApplyPreview();
                _mouthRuntime?.RefreshAvatar(_avatarLoader?.Instance);
                _avatarEditorStatus = "Previewing unsaved appearance.";
            }
        }

        private bool DrawColorField(
            ref string editorValue,
            string label,
            ref string appearanceValue,
            float y
        )
        {
            GUI.Label(new Rect(0f, y + 2f, 120f, 24f), label);
            string next = GUI.TextField(
                new Rect(126f, y, 112f, 26f),
                editorValue,
                7
            );

            if (string.Equals(next, editorValue, StringComparison.Ordinal))
            {
                return false;
            }

            editorValue = next;
            if (
                next.Length == 7 &&
                next[0] == '#' &&
                ColorUtility.TryParseHtmlString(next, out _)
            )
            {
                appearanceValue = next;
                return true;
            }

            _avatarEditorStatus = "Colors use #RRGGBB.";
            return false;
        }

        private static bool DrawAvatarSlider(
            ref float value,
            string label,
            float minimum,
            float maximum,
            float y
        )
        {
            GUI.Label(new Rect(0f, y, 122f, 24f), label);
            float next = GUI.HorizontalSlider(
                new Rect(126f, y + 6f, 220f, 20f),
                value,
                minimum,
                maximum
            );
            GUI.Label(
                new Rect(356f, y, 58f, 24f),
                next.ToString("0.00")
            );

            if (Mathf.Approximately(next, value))
            {
                return false;
            }

            value = next;
            return true;
        }

        private void LoadAvatarEditorFields()
        {
            if (_avatarEditor == null)
            {
                return;
            }

            AxiomAvatarAppearance appearance = _avatarEditor.Appearance;
            _skinColorText = appearance.skinColor;
            _hairColorText = appearance.hairColor;
            _shirtColorText = appearance.shirtColor;
            _pantsColorText = appearance.pantsColor;
            _eyeColorText = appearance.eyeColor;
            _shoeColorText = appearance.shoeColor;
        }

        private void CommitAvatarColors()
        {
            if (_avatarEditor == null)
            {
                return;
            }

            AxiomAvatarAppearance appearance = _avatarEditor.Appearance;
            ApplyValidColor(_skinColorText, ref appearance.skinColor);
            ApplyValidColor(_hairColorText, ref appearance.hairColor);
            ApplyValidColor(_shirtColorText, ref appearance.shirtColor);
            ApplyValidColor(_pantsColorText, ref appearance.pantsColor);
            ApplyValidColor(_eyeColorText, ref appearance.eyeColor);
            ApplyValidColor(_shoeColorText, ref appearance.shoeColor);
        }

        private static void ApplyValidColor(string candidate, ref string target)
        {
            if (
                !string.IsNullOrWhiteSpace(candidate) &&
                candidate.Length == 7 &&
                candidate[0] == '#' &&
                ColorUtility.TryParseHtmlString(candidate, out _)
            )
            {
                target = candidate;
            }
        }
    }
}
