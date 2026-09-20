using System;
using System.Threading.Tasks;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class AxiomMouthRuntime : MonoBehaviour
    {
        private const float PollIntervalSeconds = 0.35f;

        private readonly WindowsSpeechOutput _speech = new WindowsSpeechOutput();
        private MindApiClient _client;
        private bool _polling;
        private float _nextPollAt;

        public event Action<string> StatusChanged;

        public void Attach(MindApiClient client)
        {
            _client = client;
            _nextPollAt = 0f;
            StatusChanged?.Invoke("Axiom Body connected. Voice ready.");
        }

        public void Detach()
        {
            _client = null;
            _speech.Stop();
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

                StatusChanged?.Invoke("Speaking...");
                await _speech.SpeakAsync(intent);
                StatusChanged?.Invoke("Axiom Body connected. Voice ready.");
            }
            catch (Exception exception)
            {
                StatusChanged?.Invoke("Voice failed: " + exception.Message);
                Debug.LogException(exception);
            }
            finally
            {
                _polling = false;
            }
        }

        private void OnDisable()
        {
            _speech.Stop();
        }

        private void OnDestroy()
        {
            _speech.Stop();
        }
    }
}
