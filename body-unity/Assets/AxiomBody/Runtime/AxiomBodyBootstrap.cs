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
        private string _status = "Starting Axiom Body...";
        private string _message = string.Empty;
        private string _reply = string.Empty;
        private string _mindUrl = string.Empty;
        private string _mindUsername = string.Empty;
        private string _mindPassword = string.Empty;
        private bool _sending;
        private bool _connecting;
        private bool _connected;

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

                if (_mouthRuntime == null)
                {
                    _mouthRuntime = gameObject.AddComponent<AxiomMouthRuntime>();
                    _mouthRuntime.StatusChanged += HandleBodyStatus;
                }
                _mouthRuntime.Attach(_client, _avatarLoader.Instance);

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
                _status = "Mind responded.";
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
            const float width = 520f;
            const float panelHeight = 310f;

            Rect panel = new Rect(18f, 18f, width, panelHeight);
            GUI.Box(panel, "Axiom Body — Unity Bootstrap");

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
            if (GUI.Button(new Rect(34f, 116f, 112f, 30f), _connected ? "Reconnect" : "Connect"))
            {
                _ = ConnectAsync();
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(160f, 119f, width - 178f, 48f),
                _status
            );

            GUI.Box(new Rect(34f, 166f, width - 68f, 1f), string.Empty);

            _message = GUI.TextField(
                new Rect(34f, 184f, width - 132f, 30f),
                _message,
                2000
            );

            GUI.enabled =
                _connected &&
                !_sending &&
                !string.IsNullOrWhiteSpace(_message);

            if (GUI.Button(new Rect(width - 82f, 184f, 76f, 30f), "Send"))
            {
                _ = SendInteractionAsync();
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(34f, 224f, width - 68f, 62f),
                string.IsNullOrEmpty(_reply)
                    ? "Mind response will appear here."
                    : _reply
            );
        }
    }
}
