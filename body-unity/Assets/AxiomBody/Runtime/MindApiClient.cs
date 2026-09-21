// Copyright (c) 2026 William Enright. All rights reserved.
// Use, reproduction, modification, distribution, or commercial exploitation
// of this file is prohibited without prior written permission from the
// copyright holder.

using System;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;

namespace Axiom.Body
{
    [Serializable]
    public sealed class MindApiErrorResponse
    {
        public string detail = string.Empty;
    }

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
    public sealed class DesktopMemoryItem
    {
        public string memory_class = string.Empty;
        public string formed_at = string.Empty;
        public string content = string.Empty;
        public string[] associations = Array.Empty<string>();
        public string[] grounding = Array.Empty<string>();
    }

    [Serializable]
    public sealed class DesktopMemoryPage
    {
        public DesktopMemoryItem[] items = Array.Empty<DesktopMemoryItem>();
        public int total;
        public int offset;
        public int limit;
        public bool has_more;
        public int next_offset;
    }

    [Serializable]
    public sealed class DesktopJournalItem
    {
        public string kind = string.Empty;
        public string occurred_at = string.Empty;
        public string title = string.Empty;
        public string preview = string.Empty;
        public string search_text = string.Empty;
    }

    [Serializable]
    public sealed class DesktopJournalPage
    {
        public DesktopJournalItem[] items = Array.Empty<DesktopJournalItem>();
        public int total;
        public int offset;
        public int limit;
        public bool has_more;
        public int next_offset;
    }

    [Serializable]
    public sealed class DesktopMindIdentity
    {
        public string self_name = string.Empty;
        public string pronouns = string.Empty;
        public string[] foundational_values = Array.Empty<string>();
        public string[] commitments = Array.Empty<string>();
    }

    [Serializable]
    public sealed class DesktopMindSummary
    {
        public DesktopMindIdentity identity = new DesktopMindIdentity();
        public string developmental_state = string.Empty;
        public string created_at = string.Empty;
    }

    [Serializable]
    public sealed class DesktopIntegrationStatus
    {
        public string protocol = string.Empty;
        public string reasoning_owner = string.Empty;
        public string identity_owner = string.Empty;
        public string memory_owner = string.Empty;
    }

    [Serializable]
    public sealed class DesktopReasoningStatus
    {
        public string primary_mode = string.Empty;
        public string external_host_protocol = string.Empty;
        public string external_host_reasoning_owner = string.Empty;
        public string standalone_fallback_provider = string.Empty;
        public string standalone_fallback_model = string.Empty;
        public string standalone_fallback_requested_model = string.Empty;

        // Backwards-compatible fields for older Mind servers.
        public string backend = string.Empty;
        public string model = string.Empty;
        public string requested_model = string.Empty;
    }

    [Serializable]
    public sealed class DesktopAdministrationStatus
    {
        public bool pin_required;
        public bool memory_editing;
    }

    [Serializable]
    public sealed class DesktopPortalStatus
    {
        public DesktopMindSummary mind = new DesktopMindSummary();
        public int durable_memory_count;
        public int journal_experience_count;
        public DesktopIntegrationStatus integration =
            new DesktopIntegrationStatus();
        public DesktopReasoningStatus reasoning =
            new DesktopReasoningStatus();
        public DesktopAdministrationStatus administration =
            new DesktopAdministrationStatus();
    }

    [Serializable]
    public sealed class AdminStatusResponse
    {
        public bool authorized;
        public bool memory_editing;
    }

    [Serializable]
    public sealed class DesktopAdminMemoryRevisionRequest
    {
        public string original_memory_class = string.Empty;
        public string original_formed_at = string.Empty;
        public string original_content = string.Empty;
        public string[] original_associations = Array.Empty<string>();
        public string[] original_grounding = Array.Empty<string>();
        public string replacement_memory_class = string.Empty;
        public string replacement_content = string.Empty;
        public string[] replacement_associations = Array.Empty<string>();
        public string[] replacement_grounding = Array.Empty<string>();
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

        public async Task AuthenticateAsync()
        {
            using UnityWebRequest request =
                UnityWebRequest.Get(Url("/v1/mind"));
            await SendAsync(request);
        }

        public async Task<DesktopPortalStatus> PortalStatusAsync()
        {
            using UnityWebRequest request =
                UnityWebRequest.Get(Url("/v1/portal/status"));
            await SendAsync(request);

            DesktopPortalStatus response =
                JsonUtility.FromJson<DesktopPortalStatus>(
                    request.downloadHandler.text
                );
            if (response == null)
            {
                throw new InvalidOperationException(
                    "Mind returned an unreadable summary status."
                );
            }

            response.mind ??= new DesktopMindSummary();
            response.mind.identity ??= new DesktopMindIdentity();
            response.mind.identity.foundational_values ??=
                Array.Empty<string>();
            response.mind.identity.commitments ??=
                Array.Empty<string>();
            response.integration ??= new DesktopIntegrationStatus();
            response.reasoning ??= new DesktopReasoningStatus();
            response.administration ??=
                new DesktopAdministrationStatus();
            return response;
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

        public async Task<DesktopMemoryPage> MemoryPageAsync(
            string search,
            string memoryClass,
            string association,
            string grounding,
            string fromDate,
            string toDate,
            int offset,
            int limit = 12
        )
        {
            string path =
                "/v1/portal/memory?order=newest&limit=" +
                Math.Max(1, limit) +
                "&offset=" +
                Math.Max(0, offset);

            path = AppendQuery(path, "search", search);
            path = AppendQuery(path, "memory_class", memoryClass);
            path = AppendQuery(path, "association", association);
            path = AppendQuery(path, "grounding", grounding);
            path = AppendQuery(path, "from", fromDate);
            path = AppendQuery(path, "to", toDate);

            using UnityWebRequest request = UnityWebRequest.Get(Url(path));
            await SendAsync(request);

            DesktopMemoryPage page =
                JsonUtility.FromJson<DesktopMemoryPage>(
                    request.downloadHandler.text
                );
            if (page == null)
            {
                throw new InvalidOperationException(
                    "Mind returned an unreadable memory page."
                );
            }

            page.items ??= Array.Empty<DesktopMemoryItem>();
            return page;
        }

        public async Task<DesktopJournalPage> JournalPageAsync(
            string search,
            string kind,
            string fromDate,
            string toDate,
            int offset,
            int limit = 12
        )
        {
            string path =
                "/v1/portal/journal?order=newest&limit=" +
                Math.Max(1, limit) +
                "&offset=" +
                Math.Max(0, offset);

            path = AppendQuery(path, "search", search);
            path = AppendQuery(path, "kind", kind);
            path = AppendQuery(path, "from", fromDate);
            path = AppendQuery(path, "to", toDate);

            using UnityWebRequest request = UnityWebRequest.Get(Url(path));
            await SendAsync(request);

            DesktopJournalPage page =
                JsonUtility.FromJson<DesktopJournalPage>(
                    request.downloadHandler.text
                );
            if (page == null)
            {
                throw new InvalidOperationException(
                    "Mind returned an unreadable journal page."
                );
            }

            page.items ??= Array.Empty<DesktopJournalItem>();
            return page;
        }

        public async Task<AdminStatusResponse> AdminStatusAsync(string pin)
        {
            using UnityWebRequest request =
                UnityWebRequest.Get(Url("/v1/admin/status"));
            ApplyAdminPin(request, pin);
            await SendAsync(request);

            AdminStatusResponse response =
                JsonUtility.FromJson<AdminStatusResponse>(
                    request.downloadHandler.text
                );
            if (response == null)
            {
                throw new InvalidOperationException(
                    "Mind returned an unreadable admin status."
                );
            }

            return response;
        }

        public async Task<DesktopMemoryItem> ReviseMemoryAsync(
            string pin,
            DesktopMemoryItem original,
            string replacementMemoryClass,
            string replacementContent,
            string[] replacementAssociations,
            string[] replacementGrounding
        )
        {
            if (original == null)
            {
                throw new ArgumentNullException(nameof(original));
            }

            DesktopAdminMemoryRevisionRequest payload =
                new DesktopAdminMemoryRevisionRequest
                {
                    original_memory_class = original.memory_class,
                    original_formed_at = original.formed_at,
                    original_content = original.content,
                    original_associations =
                        original.associations ?? Array.Empty<string>(),
                    original_grounding =
                        original.grounding ?? Array.Empty<string>(),
                    replacement_memory_class =
                        replacementMemoryClass ?? string.Empty,
                    replacement_content =
                        replacementContent ?? string.Empty,
                    replacement_associations =
                        replacementAssociations ?? Array.Empty<string>(),
                    replacement_grounding =
                        replacementGrounding ?? Array.Empty<string>()
                };

            using UnityWebRequest request = new UnityWebRequest(
                Url("/v1/admin/desktop/memory"),
                UnityWebRequest.kHttpVerbPUT
            );
            request.uploadHandler = new UploadHandlerRaw(
                Encoding.UTF8.GetBytes(JsonUtility.ToJson(payload))
            );
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            ApplyAdminPin(request, pin);

            await SendAsync(request);

            DesktopMemoryItem revised =
                JsonUtility.FromJson<DesktopMemoryItem>(
                    request.downloadHandler.text
                );
            if (revised == null)
            {
                throw new InvalidOperationException(
                    "Mind returned an unreadable revised memory."
                );
            }

            revised.associations ??= Array.Empty<string>();
            revised.grounding ??= Array.Empty<string>();
            return revised;
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

        private static string AppendQuery(
            string path,
            string name,
            string value
        )
        {
            string normalized = (value ?? string.Empty).Trim();
            if (string.IsNullOrEmpty(normalized))
            {
                return path;
            }

            return path +
                "&" +
                name +
                "=" +
                UnityWebRequest.EscapeURL(normalized);
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
                string detail = ApiErrorDetail(request);
                throw new InvalidOperationException(
                    $"Mind API request failed ({request.responseCode}): {detail}"
                );
            }
        }

        private static string ApiErrorDetail(UnityWebRequest request)
        {
            string body = request.downloadHandler?.text?.Trim() ?? string.Empty;
            if (!string.IsNullOrEmpty(body))
            {
                try
                {
                    MindApiErrorResponse response =
                        JsonUtility.FromJson<MindApiErrorResponse>(body);
                    if (
                        response != null &&
                        !string.IsNullOrWhiteSpace(response.detail)
                    )
                    {
                        return response.detail.Trim();
                    }
                }
                catch (ArgumentException)
                {
                    // Fall through to a compact raw body if the server did
                    // not return FastAPI's normal {"detail": "..."} shape.
                }

                const int maxLength = 300;
                return body.Length <= maxLength
                    ? body
                    : body.Substring(0, maxLength - 1) + "…";
            }

            return string.IsNullOrWhiteSpace(request.error)
                ? "Unknown HTTP error"
                : request.error;
        }

        private static void ApplyAdminPin(
            UnityWebRequest request,
            string pin
        )
        {
            if (!string.IsNullOrEmpty(pin))
            {
                request.SetRequestHeader("X-Admin-Pin", pin);
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
