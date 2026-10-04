using System.Threading.Tasks;
using UnityEngine;

namespace Axiom.Body
{
    /// <summary>
    /// Small reference event facade. Sensor/audio components can depend on this
    /// instead of knowing anything about WebSockets or the Mind host.
    /// </summary>
    public class AxiomBodyEventEmitter : MonoBehaviour
    {
        [SerializeField] private AxiomBodyWebSocketClient transport;

        public void Configure(AxiomBodyWebSocketClient configuredTransport)
        {
            if (configuredTransport != null) transport = configuredTransport;
        }

        public Task SawAsync(string artifactId, string artifactType, string summary, float confidence) =>
            EmitAsync("body.saw", new
            {
                artifact_id = artifactId,
                artifact_type = artifactType,
                summary,
                confidence
            });

        public Task HeardAsync(string artifactId, string transcript, float confidence, string speakerId = null) =>
            EmitAsync("body.heard", new
            {
                artifact_id = artifactId,
                artifact_type = "audio",
                transcript,
                confidence,
                speaker = speakerId == null ? null : new { id = speakerId }
            });

        public Task SpeechStartedAsync(string utteranceId) =>
            EmitAsync("body.speech_started", new { utterance_id = utteranceId });

        public Task SpeechFinishedAsync(string utteranceId) =>
            EmitAsync("body.speech_finished", new { utterance_id = utteranceId });

        private Task EmitAsync(string eventName, object payload)
        {
            return transport == null ? Task.CompletedTask : transport.EmitEventAsync(eventName, payload);
        }
    }
}
