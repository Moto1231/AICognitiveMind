using System;
using System.Threading.Tasks;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class AxiomBodyBootstrap : MonoBehaviour
    {
        private MindApiClient _client;
        private string _status = "Starting Axiom Body...";
        private string _message = string.Empty;
        private string _reply = string.Empty;
        private bool _sending;

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
            _client = new MindApiClient(
                AxiomRuntimeConfig.MindBaseUrl,
                AxiomRuntimeConfig.MindUsername,
                AxiomRuntimeConfig.MindPassword
            );

            Camera camera = EnsureCamera();
            EnsureLight();

            try
            {
                _status = "Connecting to Mind...";
                await _client.HealthAsync();

                _status = "Loading Axiom...";
                AxiomAvatarLoader avatarLoader =
                    gameObject.AddComponent<AxiomAvatarLoader>();
                await avatarLoader.LoadAsync(_client, camera);

                _status = "Axiom Body connected.";
            }
            catch (Exception exception)
            {
                _status = "Body startup failed: " + exception.Message;
                Debug.LogException(exception);
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
            if (_sending || string.IsNullOrEmpty(outgoing) || _client == null)
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
            const float width = 460f;
            Rect panel = new Rect(18f, 18f, width, 176f);
            GUI.Box(panel, "Axiom Body — Unity Bootstrap");

            GUI.Label(new Rect(34f, 48f, width - 32f, 24f), _status);

            _message = GUI.TextField(
                new Rect(34f, 78f, width - 132f, 30f),
                _message,
                2000
            );

            GUI.enabled = !_sending && !string.IsNullOrWhiteSpace(_message);
            if (GUI.Button(new Rect(width - 82f, 78f, 76f, 30f), "Send"))
            {
                _ = SendInteractionAsync();
            }
            GUI.enabled = true;

            GUI.Label(
                new Rect(34f, 116f, width - 32f, 48f),
                string.IsNullOrEmpty(_reply) ? "Mind response will appear here." : _reply
            );
        }
    }
}
