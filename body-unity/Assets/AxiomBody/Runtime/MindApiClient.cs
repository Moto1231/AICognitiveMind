using System;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;

namespace Axiom.Body
{
    [Serializable]
    public sealed class MindInteractionRequest
    {
        public string message = string.Empty;
    }

    [Serializable]
    public sealed class MindInteractionResponse
    {
        public string response_text = string.Empty;
    }

    [Serializable]
    public sealed class VisionObservationRequest
    {
        public string image_data_url = string.Empty;
        public int width;
        public int height;
        public string source = "unity-camera";
    }

    [Serializable]
    public sealed class AudioObservationRequest
    {
        public string audio_data_url = string.Empty;
        public int duration_ms;
        public string source = "unity-microphone";
    }

    [Serializable]
    public sealed class EmbodiedPerceptionResponse
    {
        public string interpretation = string.Empty;
        public string response_text = string.Empty;
    }

    [Serializable]
    public sealed class VoiceIntentMetadata
    {
        public float rate = 1f;
        public float pitch = 1f;
        public float volume = 1f;
        public string voice_name = string.Empty;
        public bool transient;
        public string transport = string.Empty;
    }

    [Serializable]
    public sealed class VoiceExpressionIntent
    {
        public string modality = string.Empty;
        public string text = string.Empty;
        public VoiceIntentMetadata metadata = new VoiceIntentMetadata();
    }

    public sealed class MindApiClient
    {
        private readonly string _baseUrl;
        private readonly string _username;
        private readonly string _password;

        public MindApiClient(string baseUrl, string username, string password)
        {
            _baseUrl = baseUrl.TrimEnd('/');
            _username = username ?? string.Empty;
            _password = password ?? string.Empty;
        }

        public async Task<string> HealthAsync()
        {
            using UnityWebRequest request = UnityWebRequest.Get(Url("/health"));
            await SendAsync(request);
            return request.downloadHandler.text;
        }

        public async Task<byte[]> DownloadAvatarAsync()
        {
            using UnityWebRequest request = UnityWebRequest.Get(Url("/v1/body/face/avatar"));
            await SendAsync(request);
            return request.downloadHandler.data;
        }

        public async Task ObserveVisionAsync(
            string imageDataUrl,
            int width,
            int height
        )
        {
            VisionObservationRequest payload = new VisionObservationRequest
            {
                image_data_url = imageDataUrl,
                width = width,
                height = height,
                source = "unity-camera"
            };
            await PostJsonAsync("/v1/body/eyes/observe", JsonUtility.ToJson(payload));
        }

        public async Task<EmbodiedPerceptionResponse> SeeAsync()
        {
            using UnityWebRequest request = new UnityWebRequest(
                Url("/v1/mind/body/see?express=false"),
                UnityWebRequest.kHttpVerbPOST
            );
            request.downloadHandler = new DownloadHandlerBuffer();
            await SendAsync(request);
            return ParsePerception(request.downloadHandler.text, "vision");
        }

        public async Task ObserveAudioAsync(
            string audioDataUrl,
            int durationMs
        )
        {
            AudioObservationRequest payload = new AudioObservationRequest
            {
                audio_data_url = audioDataUrl,
                duration_ms = durationMs,
                source = "unity-microphone"
            };
            await PostJsonAsync("/v1/body/ears/observe", JsonUtility.ToJson(payload));
        }

        public async Task<EmbodiedPerceptionResponse> HearAsync()
        {
            using UnityWebRequest request = new UnityWebRequest(
                Url("/v1/mind/body/hear?express=false"),
                UnityWebRequest.kHttpVerbPOST
            );
            request.downloadHandler = new DownloadHandlerBuffer();
            await SendAsync(request);
            return ParsePerception(request.downloadHandler.text, "audio");
        }

        public async Task<VoiceExpressionIntent> NextMouthIntentAsync()
        {
            using UnityWebRequest request =
                UnityWebRequest.Get(Url("/v1/body/mouth/next"));
            await SendAsync(request);

            string json = request.downloadHandler.text?.Trim() ?? string.Empty;
            if (string.IsNullOrEmpty(json) || json == "null")
            {
                return null;
            }

            VoiceExpressionIntent intent =
                JsonUtility.FromJson<VoiceExpressionIntent>(json);
            if (intent == null)
            {
                throw new InvalidOperationException(
                    "Mind returned an unreadable Mouth intent."
                );
            }

            intent.metadata ??= new VoiceIntentMetadata();
            return intent;
        }

        public async Task<MindInteractionResponse> InteractAsync(string message)
        {
            MindInteractionRequest payload = new MindInteractionRequest
            {
                message = message
            };

            string json = JsonUtility.ToJson(payload);
            using UnityWebRequest request = new UnityWebRequest(
                Url("/v1/mind/body/interact?express=false"),
                UnityWebRequest.kHttpVerbPOST
            );
            request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            await SendAsync(request);

            MindInteractionResponse response =
                JsonUtility.FromJson<MindInteractionResponse>(request.downloadHandler.text);
            if (response == null)
            {
                throw new InvalidOperationException("Mind returned an unreadable interaction response.");
            }

            return response;
        }

        private async Task PostJsonAsync(string path, string json)
        {
            using UnityWebRequest request = new UnityWebRequest(
                Url(path),
                UnityWebRequest.kHttpVerbPOST
            );
            request.uploadHandler =
                new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            await SendAsync(request);
        }

        private static EmbodiedPerceptionResponse ParsePerception(
            string json,
            string modality
        )
        {
            EmbodiedPerceptionResponse response =
                JsonUtility.FromJson<EmbodiedPerceptionResponse>(json);
            if (response == null)
            {
                throw new InvalidOperationException(
                    "Mind returned an unreadable " + modality + " perception response."
                );
            }

            return response;
        }

        private async Task SendAsync(UnityWebRequest request)
        {
            ApplyAuthorization(request);

            UnityWebRequestAsyncOperation operation = request.SendWebRequest();
            while (!operation.isDone)
            {
                await Task.Yield();
            }

            if (request.result != UnityWebRequest.Result.Success)
            {
                throw new InvalidOperationException(
                    $"Mind API request failed ({request.responseCode}): {request.error}"
                );
            }
        }

        private void ApplyAuthorization(UnityWebRequest request)
        {
            if (string.IsNullOrEmpty(_password))
            {
                return;
            }

            string raw = $"{_username}:{_password}";
            string token = Convert.ToBase64String(Encoding.UTF8.GetBytes(raw));
            request.SetRequestHeader("Authorization", $"Basic {token}");
        }

        private string Url(string path)
        {
            return _baseUrl + path;
        }
    }
}
