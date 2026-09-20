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
        private AxiomAvatarEditorRuntime _avatarEditor;
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
        private DesktopView _view = DesktopView.Body;
        private Vector2 _avatarScroll = Vector2.zero;
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
            Avatar
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

        private async void Start()
        {
            _mindUrl = AxiomRuntimeConfig.MindBaseUrl;
            _mindUsername = AxiomRuntimeConfig.MindUsername;
            _mindPassword = AxiomRuntimeConfig.MindPassword;

            EnsureCamera();
            EnsureLight();

            await ConnectAsync();
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
            _mouthRuntime?.Detach();
            _sensesRuntime?.Detach();
            _status = "Connecting to Mind...";

            try
            {
                _client = new MindApiClient(
                    normalizedUrl,
                    string.IsNullOrWhiteSpace(_mindUsername) ? "mind" : _mindUsername.Trim(),
                    _mindPassword
                );

                await _client.HealthAsync();

                Camera camera = EnsureCamera();
                _status = "Loading Axiom...";

                if (_avatarLoader == null)
                {
                    _avatarLoader = gameObject.AddComponent<AxiomAvatarLoader>();
                }

                if (_avatarLoader.Instance == null)
                {
                    await _avatarLoader.LoadAsync(_client, camera);
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
                _avatarEditor.Attach(_avatarLoader.Instance);
                LoadAvatarEditorFields();

                if (_mouthRuntime == null)
                {
                    _mouthRuntime = gameObject.AddComponent<AxiomMouthRuntime>();
                    _mouthRuntime.StatusChanged += HandleBodyStatus;
                }
                _mouthRuntime.Attach(_client, _avatarLoader.Instance);

                if (_sensesRuntime == null)
                {
                    _sensesRuntime = gameObject.AddComponent<AxiomSensesRuntime>();
                    _sensesRuntime.StatusChanged += HandleBodyStatus;
                }
                _sensesRuntime.Attach(_client);

                _connected = true;
                _status = "Axiom Body connected. Voice + lip sync ready.";
            }
            catch (Exception exception)
            {
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
            if (_view == DesktopView.Avatar)
            {
                DrawAvatarEditor();
                return;
            }

            DrawBodyView();
        }

        private void DrawBodyView()
        {
            const float width = 520f;
            const float panelHeight = 396f;

            Rect panel = new Rect(18f, 18f, width, panelHeight);
            GUI.Box(panel, "Axiom Body");

            GUI.Label(new Rect(34f, 48f, 90f, 24f), "Mind URL");
            _mindUrl = GUI.TextField(
                new Rect(124f, 46f, width - 142f, 28f),
                _mindUrl,
                500
            );

            GUI.Label(new Rect(34f, 82f, 90f, 24f), "Username");
            _mindUsername = GUI.TextField(
                new Rect(124f, 80f, 180f, 28f),
                _mindUsername,
                120
            );

            GUI.Label(new Rect(314f, 82f, 80f, 24f), "Password");
            _mindPassword = GUI.PasswordField(
                new Rect(390f, 80f, width - 408f, 28f),
                _mindPassword,
                '*',
                240
            );

            GUI.enabled = !_connecting;
            if (
                GUI.Button(
                    new Rect(34f, 116f, 112f, 30f),
                    _connected ? "Reconnect" : "Connect"
                )
            )
            {
                _ = ConnectAsync();
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(160f, 119f, width - 178f, 48f),
                _status
            );

            GUI.enabled =
                _connected &&
                !_connecting &&
                !_sensesChanging &&
                _sensesRuntime != null;
            string sensesLabel =
                _sensesRuntime != null && _sensesRuntime.IsEnabled
                    ? "Senses Off"
                    : "Senses On";
            if (GUI.Button(new Rect(34f, 156f, 112f, 30f), sensesLabel))
            {
                _ = ToggleSensesAsync();
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(160f, 159f, width - 178f, 28f),
                _sensesRuntime != null && _sensesRuntime.IsEnabled
                    ? "Eyes + Ears active"
                    : "Eyes + Ears inactive"
            );

            GUI.Box(new Rect(34f, 198f, width - 68f, 1f), string.Empty);

            _message = GUI.TextField(
                new Rect(34f, 216f, width - 132f, 30f),
                _message,
                2000
            );

            GUI.enabled =
                _connected &&
                !_sending &&
                !string.IsNullOrWhiteSpace(_message);

            if (GUI.Button(new Rect(width - 82f, 216f, 76f, 30f), "Send"))
            {
                _ = SendInteractionAsync();
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(34f, 256f, width - 68f, 62f),
                string.IsNullOrEmpty(_reply)
                    ? "Mind response will appear here."
                    : _reply
            );

            GUI.enabled = _connected && _avatarEditor != null;
            if (GUI.Button(new Rect(34f, 342f, 112f, 30f), "Avatar"))
            {
                LoadAvatarEditorFields();
                _view = DesktopView.Avatar;
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(160f, 347f, width - 178f, 24f),
                "Appearance editor"
            );
        }

        private void DrawAvatarEditor()
        {
            const float width = 520f;
            float height = Mathf.Min(650f, Mathf.Max(420f, Screen.height - 36f));

            GUI.Box(new Rect(18f, 18f, width, height), "Avatar");

            if (GUI.Button(new Rect(34f, 48f, 112f, 30f), "Back to Body"))
            {
                _view = DesktopView.Body;
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
