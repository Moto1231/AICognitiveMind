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
        private string _status = "Starting Axiom Body...";
        private string _message = string.Empty;
        private string _reply = string.Empty;
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
        private BodyModelPolicy _bodyModelPolicy =
            BodyModelPolicy.CognitiveOnly;
        private DesktopView _view = DesktopView.Body;
        private Vector2 _avatarScroll = Vector2.zero;
        private Vector2 _memoryScroll = Vector2.zero;
        private Vector2 _journalScroll = Vector2.zero;
        private string _avatarEditorStatus = "Appearance changes preview immediately.";
        private string _skinColorText = "#b88566";
        private string _hairColorText = "#090a0d";
        private string _shirtColorText = "#2e4257";
        private string _pantsColorText = "#1a1f29";
        private string _eyeColorText = "#090a0d";
        private string _shoeColorText = "#090a0d";

        private enum DesktopView
        {
            Body,
            Bodies,
            Avatar,
            Memory,
            Journal,
            Admin
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

            EnsureCamera();
            EnsureLight();

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
            _view = DesktopView.Body;
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
                _status = "Connected.";
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
            _view = DesktopView.Body;
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
                MindInteractionResponse response = await _client.InteractAsync(outgoing);
                _reply = response.response_text;
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
                return;
            }

            if (_view == DesktopView.Memory)
            {
                DrawMemoryView();
                return;
            }

            if (_view == DesktopView.Journal)
            {
                DrawJournalView();
                return;
            }

            if (_view == DesktopView.Admin)
            {
                if (_adminRuntime != null)
                {
                    _adminRuntime.DrawGUI(
                        () => _view = DesktopView.Body
                    );
                }
                else
                {
                    _view = DesktopView.Body;
                }
                return;
            }

            DrawControlStrip();
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
            const float top = 8f;
            const float height = 38f;
            float x = 8f;

            Color previousBackground = GUI.backgroundColor;
            GUIStyle powerStyle = new GUIStyle(GUI.skin.button)
            {
                fontSize = 17,
                fontStyle = FontStyle.Bold
            };

            GUI.backgroundColor = _connected
                ? new Color(0.20f, 0.78f, 0.30f)
                : new Color(0.86f, 0.22f, 0.22f);
            if (
                GUI.Button(
                    new Rect(x, top, 58f, height),
                    "POWER",
                    powerStyle
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
            GUI.backgroundColor = previousBackground;
            x += 64f;

            string modeLabel =
                _bodyModelPolicy == BodyModelPolicy.FullBodyModel
                    ? "Mode: Full Body ▼"
                    : "Mode: Cognitive ▼";
            if (GUI.Button(new Rect(x, top, 150f, height), modeLabel))
            {
                _modeDropdownOpen = !_modeDropdownOpen;
                _bodyDropdownOpen = false;
            }
            float modeX = x;
            x += 156f;

            string bodyName =
                _avatarLoader != null && _avatarLoader.Root != null
                    ? _avatarLoader.CurrentBodyName
                    : "Body";
            GUI.enabled = _connected && _avatarLoader != null;
            if (
                GUI.Button(
                    new Rect(x, top, 150f, height),
                    bodyName + " ▼"
                )
            )
            {
                _bodyDropdownOpen = !_bodyDropdownOpen;
                _modeDropdownOpen = false;
            }
            float bodyX = x;
            GUI.enabled = true;
            x += 156f;

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
                    new Rect(x, top, 92f, height),
                    sensesOn ? "SENSES ON" : "SENSES OFF"
                )
            )
            {
                _ = ToggleSensesAsync();
            }
            GUI.enabled = true;
            GUI.backgroundColor = previousBackground;
            x += 98f;

            GUI.enabled = _connected && _mindData != null;
            if (GUI.Button(new Rect(x, top, 76f, height), "Memory"))
            {
                _memoryScroll = Vector2.zero;
                _view = DesktopView.Memory;
                _ = _mindData.LoadMemoryAsync(0);
            }
            x += 82f;

            if (GUI.Button(new Rect(x, top, 76f, height), "Journal"))
            {
                _journalScroll = Vector2.zero;
                _view = DesktopView.Journal;
                _ = _mindData.LoadJournalAsync(0);
            }
            x += 82f;

            GUI.enabled = _connected && _adminRuntime != null;
            if (GUI.Button(new Rect(x, top, 68f, height), "Admin"))
            {
                _view = DesktopView.Admin;
            }
            GUI.enabled = true;
            x += 74f;

            if (Screen.width > x + 100f)
            {
                GUI.Label(
                    new Rect(x + 4f, top + 8f, Screen.width - x - 16f, 24f),
                    CompactText(_status, 120)
                );
            }

            if (_modeDropdownOpen)
            {
                DrawModeDropdown(modeX, top + height + 4f);
            }

            if (_bodyDropdownOpen)
            {
                DrawBodyDropdown(bodyX, top + height + 4f);
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

        private void DrawMemoryView()
        {
            const float width = 640f;
            float height = Mathf.Min(720f, Mathf.Max(460f, Screen.height - 36f));

            GUI.Box(new Rect(18f, 18f, width, height), "Memory");

            if (GUI.Button(new Rect(34f, 48f, 112f, 30f), "Back to Body"))
            {
                _view = DesktopView.Body;
                return;
            }

            if (_mindData == null)
            {
                GUI.Label(
                    new Rect(34f, 96f, width - 68f, 40f),
                    "Connect to the Mind before viewing memory."
                );
                return;
            }

            GUI.enabled = !_mindData.LoadingMemory;
            if (GUI.Button(new Rect(158f, 48f, 82f, 30f), "Refresh"))
            {
                _ = _mindData.LoadMemoryAsync(_mindData.MemoryPage.offset);
            }
            GUI.enabled = true;

            GUI.Label(new Rect(34f, 94f, 58f, 24f), "Search");
            _mindData.MemorySearch = GUI.TextField(
                new Rect(92f, 90f, width - 226f, 28f),
                _mindData.MemorySearch ?? string.Empty,
                200
            );

            GUI.enabled = !_mindData.LoadingMemory;
            if (GUI.Button(new Rect(width - 120f, 90f, 86f, 28f), "Search"))
            {
                _memoryScroll = Vector2.zero;
                _ = _mindData.LoadMemoryAsync(0);
            }
            GUI.enabled = true;

            DesktopMemoryPage page = _mindData.MemoryPage ?? new DesktopMemoryPage();
            DesktopMemoryItem[] items = page.items ?? Array.Empty<DesktopMemoryItem>();

            Rect viewport = new Rect(34f, 132f, width - 50f, height - 222f);
            float contentHeight = Mathf.Max(
                viewport.height - 4f,
                items.Length * 126f
            );
            _memoryScroll = GUI.BeginScrollView(
                viewport,
                _memoryScroll,
                new Rect(0f, 0f, width - 86f, contentHeight)
            );

            for (int index = 0; index < items.Length; index++)
            {
                DesktopMemoryItem item = items[index];
                float y = index * 126f;
                GUI.Box(new Rect(0f, y, width - 102f, 116f), string.Empty);

                GUI.Label(
                    new Rect(10f, y + 7f, 180f, 22f),
                    (item.memory_class ?? "memory").ToUpperInvariant()
                );
                GUI.Label(
                    new Rect(194f, y + 7f, width - 316f, 22f),
                    CompactTimestamp(item.formed_at)
                );

                GUI.Label(
                    new Rect(10f, y + 31f, width - 126f, 46f),
                    CompactText(item.content, 220)
                );

                string associations = JoinCompact(item.associations, 90);
                string grounding = JoinCompact(item.grounding, 90);
                GUI.Label(
                    new Rect(10f, y + 80f, width - 126f, 18f),
                    string.IsNullOrEmpty(associations)
                        ? "Associations: —"
                        : "Associations: " + associations
                );
                GUI.Label(
                    new Rect(10f, y + 98f, width - 126f, 18f),
                    string.IsNullOrEmpty(grounding)
                        ? "Grounding: —"
                        : "Grounding: " + grounding
                );
            }

            GUI.EndScrollView();

            float footerY = height - 76f;
            GUI.Label(
                new Rect(34f, footerY, width - 250f, 24f),
                _mindData.MemoryStatus
            );

            GUI.enabled = !_mindData.LoadingMemory && page.offset > 0;
            if (GUI.Button(new Rect(width - 202f, footerY - 2f, 78f, 28f), "Previous"))
            {
                _memoryScroll = Vector2.zero;
                _ = _mindData.PreviousMemoryAsync();
            }

            GUI.enabled = !_mindData.LoadingMemory && page.has_more;
            if (GUI.Button(new Rect(width - 114f, footerY - 2f, 78f, 28f), "Next"))
            {
                _memoryScroll = Vector2.zero;
                _ = _mindData.NextMemoryAsync();
            }
            GUI.enabled = true;
        }

        private void DrawJournalView()
        {
            const float width = 640f;
            float height = Mathf.Min(720f, Mathf.Max(460f, Screen.height - 36f));

            GUI.Box(new Rect(18f, 18f, width, height), "Journal");

            if (GUI.Button(new Rect(34f, 48f, 112f, 30f), "Back to Body"))
            {
                _view = DesktopView.Body;
                return;
            }

            if (_mindData == null)
            {
                GUI.Label(
                    new Rect(34f, 96f, width - 68f, 40f),
                    "Connect to the Mind before viewing the journal."
                );
                return;
            }

            GUI.enabled = !_mindData.LoadingJournal;
            if (GUI.Button(new Rect(158f, 48f, 82f, 30f), "Refresh"))
            {
                _ = _mindData.LoadJournalAsync(_mindData.JournalPage.offset);
            }
            GUI.enabled = true;

            GUI.Label(new Rect(34f, 94f, 58f, 24f), "Search");
            _mindData.JournalSearch = GUI.TextField(
                new Rect(92f, 90f, width - 226f, 28f),
                _mindData.JournalSearch ?? string.Empty,
                200
            );

            GUI.enabled = !_mindData.LoadingJournal;
            if (GUI.Button(new Rect(width - 120f, 90f, 86f, 28f), "Search"))
            {
                _journalScroll = Vector2.zero;
                _ = _mindData.LoadJournalAsync(0);
            }
            GUI.enabled = true;

            DesktopJournalPage page = _mindData.JournalPage ?? new DesktopJournalPage();
            DesktopJournalItem[] items = page.items ?? Array.Empty<DesktopJournalItem>();

            Rect viewport = new Rect(34f, 132f, width - 50f, height - 222f);
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
                GUI.Box(new Rect(0f, y, width - 102f, 86f), string.Empty);

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

            float footerY = height - 76f;
            GUI.Label(
                new Rect(34f, footerY, width - 250f, 24f),
                _mindData.JournalStatus
            );

            GUI.enabled = !_mindData.LoadingJournal && page.offset > 0;
            if (GUI.Button(new Rect(width - 202f, footerY - 2f, 78f, 28f), "Previous"))
            {
                _journalScroll = Vector2.zero;
                _ = _mindData.PreviousJournalAsync();
            }

            GUI.enabled = !_mindData.LoadingJournal && page.has_more;
            if (GUI.Button(new Rect(width - 114f, footerY - 2f, 78f, 28f), "Next"))
            {
                _journalScroll = Vector2.zero;
                _ = _mindData.NextJournalAsync();
            }
            GUI.enabled = true;
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
