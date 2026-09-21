// Copyright (c) 2026 William Enright. All rights reserved.
// Use, reproduction, modification, distribution, or commercial exploitation
// of this file is prohibited without prior written permission from the
// copyright holder.

using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class AxiomSensesRuntime : MonoBehaviour
    {
        private const float VisionIntervalSeconds = 15f;
        private const float AudioIntervalSeconds = 15f;
        private const int AudioWindowSeconds = 4;
        private const int AudioSampleRate = 16000;
        private const int VisionSignatureColumns = 12;
        private const int VisionSignatureRows = 8;
        private const float VisionChangeThreshold = 0.045f;
        private const float AudioRmsThreshold = 0.008f;
        private const float AudioPeakThreshold = 0.06f;

        private readonly SemaphoreSlim _cognitionGate =
            new SemaphoreSlim(1, 1);

        private MindApiClient _client;
        private WebCamTexture _camera;
        private bool _enabled;
        private bool _visionBusy;
        private bool _audioBusy;
        private int _generation;
        private string _visionStatus = "Eyes idle";
        private string _audioStatus = "Ears idle";
        private BodyModelPolicy _modelPolicy = BodyModelPolicy.CognitiveOnly;
        private float[] _visionBaseline;

        public event Action<string> StatusChanged;

        public bool IsEnabled => _enabled;
        public bool VisionBusy => _visionBusy;
        public bool AudioBusy => _audioBusy;
        public BodyModelPolicy ModelPolicy => _modelPolicy;

        public void SetModelPolicy(BodyModelPolicy policy)
        {
            if (_modelPolicy == policy)
            {
                return;
            }

            _modelPolicy = policy;
            _visionBaseline = null;
            if (_enabled)
            {
                StatusChanged?.Invoke(
                    policy == BodyModelPolicy.FullBodyModel
                        ? "Body model policy: Full Body Model."
                        : "Body model policy: Cognitive Only."
                );
            }
        }

        public void Attach(MindApiClient client)
        {
            _client = client;
        }

        public async Task SetEnabledAsync(bool enabled)
        {
            if (enabled == _enabled)
            {
                return;
            }

            if (!enabled)
            {
                Disable();
                StatusChanged?.Invoke(
                    "Senses off. Camera and microphone released."
                );
                return;
            }

            if (_client == null)
            {
                throw new InvalidOperationException(
                    "Mind connection is not available."
                );
            }

            _generation += 1;
            int generation = _generation;

            await StartCameraAsync(generation);
            if (generation != _generation)
            {
                return;
            }

            _enabled = true;
            _visionStatus = "Eyes active";
            _audioStatus = "Ears active";
            EmitStatus();

            // Eyes and Ears capture independently. Remote interpretation
            // and Cognitive Core work are serialized by _cognitionGate so
            // concurrent hardware sensing does not create reasoning bursts.
            _ = RunVisionLoopAsync(generation);
            _ = RunAudioLoopAsync(generation);
        }

        public void Detach()
        {
            _client = null;
            Disable();
        }

        private async Task StartCameraAsync(int generation)
        {
            if (WebCamTexture.devices.Length == 0)
            {
                throw new InvalidOperationException(
                    "No camera is available."
                );
            }

            string deviceName = WebCamTexture.devices[0].name;
            _camera = new WebCamTexture(
                deviceName,
                960,
                540,
                15
            );
            _camera.Play();

            float timeoutAt = Time.realtimeSinceStartup + 5f;
            while (
                generation == _generation &&
                _camera != null &&
                _camera.isPlaying &&
                (_camera.width <= 16 || _camera.height <= 16) &&
                Time.realtimeSinceStartup < timeoutAt
            )
            {
                await Task.Yield();
            }

            if (
                generation != _generation ||
                _camera == null ||
                !_camera.isPlaying
            )
            {
                throw new InvalidOperationException(
                    "Camera startup was interrupted."
                );
            }

            if (_camera.width <= 16 || _camera.height <= 16)
            {
                throw new InvalidOperationException(
                    "Camera did not provide usable video frames."
                );
            }
        }

        private async Task RunVisionLoopAsync(int generation)
        {
            while (_enabled && generation == _generation)
            {
                if (!_visionBusy)
                {
                    try
                    {
                        _visionBusy = true;
                        await PerceiveVisionAsync(generation);
                    }
                    catch (Exception exception)
                    {
                        if (_enabled && generation == _generation)
                        {
                            SetVisionStatus(
                                "Eyes failed: " + exception.Message
                            );
                            Debug.LogException(exception);
                        }
                    }
                    finally
                    {
                        _visionBusy = false;
                    }
                }

                if (
                    !await WaitAsync(
                        VisionIntervalSeconds,
                        generation
                    )
                )
                {
                    return;
                }
            }
        }

        private async Task RunAudioLoopAsync(int generation)
        {
            while (_enabled && generation == _generation)
            {
                if (!_audioBusy)
                {
                    try
                    {
                        _audioBusy = true;
                        await PerceiveAudioAsync(generation);
                    }
                    catch (Exception exception)
                    {
                        if (_enabled && generation == _generation)
                        {
                            SetAudioStatus(
                                "Ears failed: " + exception.Message
                            );
                            Debug.LogException(exception);
                        }
                    }
                    finally
                    {
                        _audioBusy = false;
                    }
                }

                if (
                    !await WaitAsync(
                        AudioIntervalSeconds,
                        generation
                    )
                )
                {
                    return;
                }
            }
        }

        private async Task PerceiveVisionAsync(int generation)
        {
            if (
                _client == null ||
                _camera == null ||
                !_camera.isPlaying ||
                generation != _generation
            )
            {
                return;
            }

            int width = _camera.width;
            int height = _camera.height;
            Texture2D frame = new Texture2D(
                width,
                height,
                TextureFormat.RGB24,
                false
            );

            try
            {
                Color32[] pixels = _camera.GetPixels32();
                if (
                    _modelPolicy == BodyModelPolicy.CognitiveOnly &&
                    !VisionRequiresModel(pixels, width, height)
                )
                {
                    SetVisionStatus(
                        "Eyes: scene unchanged; model skipped."
                    );
                    return;
                }

                frame.SetPixels32(pixels);
                frame.Apply(false, false);
                byte[] jpeg =
                    ImageConversion.EncodeToJPG(frame, 72);
                string dataUrl =
                    "data:image/jpeg;base64," +
                    Convert.ToBase64String(jpeg);

                SetVisionStatus("Eyes waiting for cognition...");
                await _cognitionGate.WaitAsync();
                try
                {
                    if (
                        !_enabled ||
                        generation != _generation ||
                        _client == null
                    )
                    {
                        return;
                    }

                    SetVisionStatus("Eyes interpreting...");
                    await _client.ObserveVisionAsync(
                        dataUrl,
                        width,
                        height
                    );
                    EmbodiedPerceptionResponse result =
                        await _client.SeeAsync();

                    if (_enabled && generation == _generation)
                    {
                        SetVisionStatus(
                            "Eyes: " + Compact(result.interpretation)
                        );
                    }
                }
                finally
                {
                    _cognitionGate.Release();
                }
            }
            finally
            {
                Destroy(frame);
            }
        }

        private async Task PerceiveAudioAsync(int generation)
        {
            if (_client == null || generation != _generation)
            {
                return;
            }

            if (Microphone.devices.Length == 0)
            {
                throw new InvalidOperationException(
                    "No microphone is available."
                );
            }

            string device = Microphone.devices[0];
            AudioClip clip = null;

            try
            {
                SetAudioStatus("Ears listening...");
                clip = Microphone.Start(
                    device,
                    false,
                    AudioWindowSeconds,
                    AudioSampleRate
                );

                if (clip == null)
                {
                    throw new InvalidOperationException(
                        "Microphone recording could not start."
                    );
                }

                float startupTimeout =
                    Time.realtimeSinceStartup + 2f;
                while (
                    _enabled &&
                    generation == _generation &&
                    Microphone.GetPosition(device) <= 0 &&
                    Time.realtimeSinceStartup < startupTimeout
                )
                {
                    await Task.Yield();
                }

                if (!_enabled || generation != _generation)
                {
                    return;
                }

                if (Microphone.GetPosition(device) <= 0)
                {
                    throw new InvalidOperationException(
                        "Microphone did not provide audio samples."
                    );
                }

                if (
                    !await WaitAsync(
                        AudioWindowSeconds,
                        generation
                    )
                )
                {
                    return;
                }

                Microphone.End(device);

                if (
                    _modelPolicy == BodyModelPolicy.CognitiveOnly &&
                    !AudioRequiresModel(clip)
                )
                {
                    SetAudioStatus(
                        "Ears: quiet/background audio; model skipped."
                    );
                    return;
                }

                byte[] wav = EncodePcm16Wav(clip);
                int durationMs = Mathf.RoundToInt(
                    (clip.samples / (float)clip.frequency) * 1000f
                );
                string dataUrl =
                    "data:audio/wav;base64," +
                    Convert.ToBase64String(wav);

                SetAudioStatus("Ears waiting for cognition...");
                await _cognitionGate.WaitAsync();
                try
                {
                    if (
                        !_enabled ||
                        generation != _generation ||
                        _client == null
                    )
                    {
                        return;
                    }

                    SetAudioStatus("Ears interpreting...");
                    await _client.ObserveAudioAsync(
                        dataUrl,
                        durationMs
                    );
                    EmbodiedPerceptionResponse result =
                        await _client.HearAsync();

                    if (_enabled && generation == _generation)
                    {
                        SetAudioStatus(
                            "Ears: " + Compact(result.interpretation)
                        );
                    }
                }
                finally
                {
                    _cognitionGate.Release();
                }
            }
            finally
            {
                if (Microphone.IsRecording(device))
                {
                    Microphone.End(device);
                }

                if (clip != null)
                {
                    Destroy(clip);
                }
            }
        }

        private async Task<bool> WaitAsync(
            float seconds,
            int generation
        )
        {
            float until = Time.realtimeSinceStartup + seconds;
            while (
                _enabled &&
                generation == _generation &&
                Time.realtimeSinceStartup < until
            )
            {
                await Task.Yield();
            }

            return _enabled && generation == _generation;
        }

        private void SetVisionStatus(string status)
        {
            _visionStatus = status;
            EmitStatus();
        }

        private void SetAudioStatus(string status)
        {
            _audioStatus = status;
            EmitStatus();
        }

        private void EmitStatus()
        {
            if (!_enabled)
            {
                return;
            }

            StatusChanged?.Invoke(
                _visionStatus + " | " + _audioStatus
            );
        }

        private void Disable()
        {
            _enabled = false;
            _visionBusy = false;
            _audioBusy = false;
            _generation += 1;
            _visionStatus = "Eyes idle";
            _audioStatus = "Ears idle";
            _visionBaseline = null;

            if (_camera != null)
            {
                if (_camera.isPlaying)
                {
                    _camera.Stop();
                }

                Destroy(_camera);
                _camera = null;
            }

            foreach (string device in Microphone.devices)
            {
                if (Microphone.IsRecording(device))
                {
                    Microphone.End(device);
                }
            }
        }

        private bool VisionRequiresModel(
            Color32[] pixels,
            int width,
            int height
        )
        {
            float[] signature = BuildVisionSignature(
                pixels,
                width,
                height
            );

            if (_visionBaseline == null)
            {
                _visionBaseline = signature;
                return true;
            }

            float difference = 0f;
            for (int index = 0; index < signature.Length; index++)
            {
                difference += Mathf.Abs(
                    signature[index] - _visionBaseline[index]
                );
            }

            difference /= signature.Length;
            if (difference < VisionChangeThreshold)
            {
                return false;
            }

            _visionBaseline = signature;
            return true;
        }

        private static float[] BuildVisionSignature(
            Color32[] pixels,
            int width,
            int height
        )
        {
            float[] signature = new float[
                VisionSignatureColumns * VisionSignatureRows
            ];

            int signatureIndex = 0;
            for (int row = 0; row < VisionSignatureRows; row++)
            {
                int y = Mathf.Clamp(
                    Mathf.RoundToInt(
                        ((row + 0.5f) / VisionSignatureRows) *
                        (height - 1)
                    ),
                    0,
                    height - 1
                );

                for (
                    int column = 0;
                    column < VisionSignatureColumns;
                    column++
                )
                {
                    int x = Mathf.Clamp(
                        Mathf.RoundToInt(
                            ((column + 0.5f) / VisionSignatureColumns) *
                            (width - 1)
                        ),
                        0,
                        width - 1
                    );
                    Color32 pixel = pixels[(y * width) + x];
                    signature[signatureIndex++] =
                        (
                            (0.2126f * pixel.r) +
                            (0.7152f * pixel.g) +
                            (0.0722f * pixel.b)
                        ) / 255f;
                }
            }

            return signature;
        }

        private static bool AudioRequiresModel(AudioClip clip)
        {
            int channels = Mathf.Max(1, clip.channels);
            int sampleCount = clip.samples * channels;
            float[] samples = new float[sampleCount];
            clip.GetData(samples, 0);

            double sumSquares = 0d;
            float peak = 0f;
            for (int index = 0; index < samples.Length; index++)
            {
                float value = Mathf.Abs(samples[index]);
                peak = Mathf.Max(peak, value);
                sumSquares += value * value;
            }

            float rms = samples.Length == 0
                ? 0f
                : Mathf.Sqrt(
                    (float)(sumSquares / samples.Length)
                );

            return rms >= AudioRmsThreshold ||
                peak >= AudioPeakThreshold;
        }

        private static byte[] EncodePcm16Wav(AudioClip clip)
        {
            int channels = Mathf.Max(1, clip.channels);
            int sampleCount = clip.samples * channels;
            float[] samples = new float[sampleCount];
            clip.GetData(samples, 0);

            using MemoryStream stream = new MemoryStream();
            using BinaryWriter writer = new BinaryWriter(
                stream,
                Encoding.ASCII,
                true
            );

            int dataLength = sampleCount * 2;
            int byteRate = clip.frequency * channels * 2;

            writer.Write(Encoding.ASCII.GetBytes("RIFF"));
            writer.Write(36 + dataLength);
            writer.Write(Encoding.ASCII.GetBytes("WAVE"));
            writer.Write(Encoding.ASCII.GetBytes("fmt "));
            writer.Write(16);
            writer.Write((short)1);
            writer.Write((short)channels);
            writer.Write(clip.frequency);
            writer.Write(byteRate);
            writer.Write((short)(channels * 2));
            writer.Write((short)16);
            writer.Write(Encoding.ASCII.GetBytes("data"));
            writer.Write(dataLength);

            for (
                int index = 0;
                index < samples.Length;
                index++
            )
            {
                float clamped = Mathf.Clamp(
                    samples[index],
                    -1f,
                    1f
                );
                writer.Write(
                    (short)Mathf.RoundToInt(
                        clamped * short.MaxValue
                    )
                );
            }

            writer.Flush();
            return stream.ToArray();
        }

        private static string Compact(string text)
        {
            string value = (text ?? string.Empty).Trim();
            const int maxLength = 180;
            if (value.Length <= maxLength)
            {
                return value;
            }

            return value.Substring(
                0,
                maxLength - 1
            ) + "…";
        }

        private void OnDisable()
        {
            Disable();
        }

        private void OnDestroy()
        {
            Disable();
        }
    }
}
