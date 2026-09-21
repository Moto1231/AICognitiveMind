// Copyright (c) 2026 William Enright. All rights reserved.
// Use, reproduction, modification, distribution, or commercial exploitation
// of this file is prohibited without prior written permission from the
// copyright holder.

using System;
using System.Threading.Tasks;
using UniVRM10;
using UnityEngine;
using UnityEngine.Networking;

namespace Axiom.Body
{
    public sealed class AxiomMouthRuntime : MonoBehaviour
    {
        private const float PollIntervalSeconds = 0.35f;

        private readonly WindowsSpeechOutput _speech = new WindowsSpeechOutput();
        private MindApiClient _client;
        private AudioSource _audioSource;
        private AxiomLipSync _lipSync;
        private string _currentAudioPath = string.Empty;
        private bool _polling;
        private float _nextPollAt;

        public event Action<string> StatusChanged;

        public bool IsSpeaking =>
            _audioSource != null && _audioSource.isPlaying;

        public void Attach(MindApiClient client, Vrm10Instance avatar)
        {
            Attach(
                client,
                avatar != null ? avatar.gameObject : null,
                avatar
            );
        }

        public void Attach(
            MindApiClient client,
            GameObject avatarRoot,
            Vrm10Instance vrmAvatar
        )
        {
            _client = client;
            _nextPollAt = 0f;

            if (_audioSource == null)
            {
                _audioSource = gameObject.GetComponent<AudioSource>();
                if (_audioSource == null)
                {
                    _audioSource = gameObject.AddComponent<AudioSource>();
                }
                _audioSource.playOnAwake = false;
                _audioSource.loop = false;
                _audioSource.spatialBlend = 0f;
            }

            if (_lipSync == null)
            {
                _lipSync = gameObject.GetComponent<AxiomLipSync>();
                if (_lipSync == null)
                {
                    _lipSync = gameObject.AddComponent<AxiomLipSync>();
                }
            }

            _lipSync.Attach(
                avatarRoot,
                vrmAvatar,
                _audioSource
            );
            StatusChanged?.Invoke(
                "Axiom Body connected. Lip target: " + _lipSync.TargetDescription
            );
        }

        public void RefreshAvatar(Vrm10Instance avatar)
        {
            RefreshAvatar(
                avatar != null ? avatar.gameObject : null,
                avatar
            );
        }

        public void RefreshAvatar(
            GameObject avatarRoot,
            Vrm10Instance vrmAvatar
        )
        {
            if (
                _audioSource == null ||
                _lipSync == null ||
                avatarRoot == null
            )
            {
                return;
            }

            _lipSync.Attach(
                avatarRoot,
                vrmAvatar,
                _audioSource
            );
        }

        public void Detach()
        {
            _client = null;
            StopPlayback();
            _lipSync?.Detach();
        }

        public async Task SpeakTextAsync(string text)
        {
            string spokenText = (text ?? string.Empty).Trim();
            if (string.IsNullOrEmpty(spokenText))
            {
                return;
            }

            while (_polling)
            {
                await Task.Yield();
            }

            _polling = true;
            try
            {
                VoiceExpressionIntent intent = new VoiceExpressionIntent
                {
                    modality = "voice",
                    text = spokenText,
                    metadata = new VoiceIntentMetadata()
                };
                await SpeakIntentAsync(intent);
            }
            finally
            {
                _polling = false;
            }
        }

        private void Update()
        {
            if (
                _client == null ||
                _polling ||
                Time.unscaledTime < _nextPollAt
            )
            {
                return;
            }

            _nextPollAt = Time.unscaledTime + PollIntervalSeconds;
            _ = PollAsync();
        }

        private async Task PollAsync()
        {
            if (_client == null || _polling)
            {
                return;
            }

            _polling = true;
            try
            {
                VoiceExpressionIntent intent = await _client.NextMouthIntentAsync();
                if (
                    intent == null ||
                    !string.Equals(
                        intent.modality,
                        "voice",
                        StringComparison.OrdinalIgnoreCase
                    ) ||
                    string.IsNullOrWhiteSpace(intent.text)
                )
                {
                    return;
                }

                await SpeakIntentAsync(intent);
            }
            finally
            {
                _polling = false;
            }
        }

        private async Task SpeakIntentAsync(VoiceExpressionIntent intent)
        {
            string wavPath = string.Empty;
            try
            {
                StatusChanged?.Invoke("Preparing speech...");
                wavPath = await _speech.SynthesizeWavAsync(intent);
                _currentAudioPath = wavPath;

                StatusChanged?.Invoke(
                    "Speaking... Lip target: " + _lipSync.TargetDescription
                );
                await PlayWavAsync(wavPath);

                StatusChanged?.Invoke(
                    "Axiom Body connected. Lip target: " + _lipSync.TargetDescription
                );
            }
            catch (Exception exception)
            {
                StatusChanged?.Invoke("Voice failed: " + exception.Message);
                Debug.LogException(exception);
                throw;
            }
            finally
            {
                if (string.Equals(_currentAudioPath, wavPath, StringComparison.Ordinal))
                {
                    _currentAudioPath = string.Empty;
                }

                WindowsSpeechOutput.TryDelete(wavPath);
            }
        }

        private async Task PlayWavAsync(string path)
        {
            if (_audioSource == null)
            {
                throw new InvalidOperationException("Unity audio output is unavailable.");
            }

            string uri = new Uri(path).AbsoluteUri;
            using UnityWebRequest request =
                UnityWebRequestMultimedia.GetAudioClip(uri, AudioType.WAV);

            UnityWebRequestAsyncOperation operation = request.SendWebRequest();
            while (!operation.isDone)
            {
                await Task.Yield();
            }

            if (request.result != UnityWebRequest.Result.Success)
            {
                throw new InvalidOperationException(
                    "Unity could not load synthesized speech: " + request.error
                );
            }

            AudioClip clip = DownloadHandlerAudioClip.GetContent(request);
            if (clip == null)
            {
                throw new InvalidOperationException(
                    "Unity returned an empty speech audio clip."
                );
            }

            try
            {
                _audioSource.clip = clip;
                _audioSource.Play();

                float nextLipStatusAt = 0f;
                while (_audioSource.isPlaying)
                {
                    if (
                        _lipSync != null &&
                        Time.unscaledTime >= nextLipStatusAt
                    )
                    {
                        nextLipStatusAt = Time.unscaledTime + 0.25f;
                        StatusChanged?.Invoke(
                            "Speaking... lip=" +
                            _lipSync.CurrentWeight.ToString("0.00") +
                            " via " +
                            _lipSync.TargetDescription
                        );
                    }

                    await Task.Yield();
                }
            }
            finally
            {
                _audioSource.Stop();
                _audioSource.clip = null;
                Destroy(clip);
            }
        }

        private void StopPlayback()
        {
            _speech.Stop();

            if (_audioSource != null)
            {
                _audioSource.Stop();
                _audioSource.clip = null;
            }

            if (!string.IsNullOrWhiteSpace(_currentAudioPath))
            {
                WindowsSpeechOutput.TryDelete(_currentAudioPath);
                _currentAudioPath = string.Empty;
            }
        }

        private void OnDisable()
        {
            StopPlayback();
        }

        private void OnDestroy()
        {
            StopPlayback();
        }
    }
}
