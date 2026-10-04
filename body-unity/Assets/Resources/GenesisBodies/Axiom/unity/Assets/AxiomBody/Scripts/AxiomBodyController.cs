using System.Threading.Tasks;
using UnityEngine;

namespace Axiom.Body
{
    public class AxiomBodyController : MonoBehaviour, IAxiomBody
    {
        [Header("Identity")]
        [SerializeField] private BodyIdentity identity = new BodyIdentity();
        [SerializeField] private BodyCapabilities capabilities = new BodyCapabilities();

        [Header("Unity Components")]
        [SerializeField] private Animator animator;
        [SerializeField] private Transform lookTarget;
        [SerializeField] private AudioSource voiceSource;

        private readonly BodyState state = new BodyState();

        private void Awake()
        {
            state.ready = true;
            state.connected = false;
        }

        public void Configure(Animator configuredAnimator, Transform configuredLookTarget, AudioSource configuredVoiceSource)
        {
            if (configuredAnimator != null) animator = configuredAnimator;
            if (configuredLookTarget != null) lookTarget = configuredLookTarget;
            if (configuredVoiceSource != null) voiceSource = configuredVoiceSource;
        }

        public BodyIdentity GetIdentity() => identity;
        public BodyCapabilities GetCapabilities() => capabilities;
        public BodyState GetState() => state;

        public Task<BodyResult> ConnectAsync()
        {
            state.connected = true;
            return Task.FromResult(BodyResult.Ok("Body connected."));
        }

        public Task<BodyResult> DisconnectAsync()
        {
            state.connected = false;
            state.listening = false;
            state.speaking = false;
            return Task.FromResult(BodyResult.Ok("Body disconnected."));
        }

        public Task<BodyResult> SetPresenceAsync(string presence, float intensity = 1f)
        {
            if (!state.ready) return Task.FromResult(NotReady());

            state.presence = string.IsNullOrWhiteSpace(presence) ? "neutral" : presence;
            // Future: map semantic presence to animator/ears/tail/gaze.
            return Task.FromResult(BodyResult.Ok());
        }

        public Task<BodyResult> LookAtAsync(BodyTarget target, float intensity = 1f)
        {
            if (!capabilities.gaze) return Task.FromResult(CapabilityUnavailable("gaze"));
            if (!state.ready) return Task.FromResult(NotReady());

            state.attention = target ?? new BodyTarget();

            if (lookTarget != null && target != null && target.type == "world_position")
                lookTarget.position = target.worldPosition;

            return Task.FromResult(BodyResult.Ok());
        }

        public Task<BodyResult> SetExpressionAsync(string expression, float intensity = 1f, int durationMs = 0)
        {
            if (!capabilities.facialExpression) return Task.FromResult(CapabilityUnavailable("facial_expression"));
            if (!state.ready) return Task.FromResult(NotReady());

            state.expression = string.IsNullOrWhiteSpace(expression) ? "neutral" : expression;
            // Future: map expression + intensity to blendshapes and ear/tail support motion.
            return Task.FromResult(BodyResult.Ok());
        }

        public Task<BodyResult> GestureAsync(string gesture, float intensity = 1f, BodyTarget target = null)
        {
            if (!capabilities.gesture) return Task.FromResult(CapabilityUnavailable("gesture"));
            if (!state.ready) return Task.FromResult(NotReady());

            if (animator != null && !string.IsNullOrWhiteSpace(gesture))
            {
                string trigger = gesture.Trim().ToLowerInvariant() switch
                {
                    "wave" => "Wave",
                    "acknowledge" => "Acknowledge",
                    "point" => "Point",
                    _ => null
                };

                if (trigger != null)
                    animator.SetTrigger(trigger);
            }

            return Task.FromResult(BodyResult.Ok());
        }

        public Task<BodyResult> SpeakAsync(string text, string emotion = "neutral", BodyTarget attentionTarget = null)
        {
            if (!capabilities.speech) return Task.FromResult(CapabilityUnavailable("speech"));
            if (!state.ready) return Task.FromResult(NotReady());
            if (string.IsNullOrWhiteSpace(text))
                return Task.FromResult(BodyResult.Fail("INVALID_INTENT", "Speech text is empty."));

            state.speaking = true;
            state.expression = string.IsNullOrWhiteSpace(emotion) ? "neutral" : emotion;
            if (attentionTarget != null) state.attention = attentionTarget;

            if (animator != null)
                animator.SetBool("IsSpeaking", true);

            // v0.1 intentionally does not choose a TTS provider.
            // The speech adapter will supply audio and lip-sync later.
            return Task.FromResult(BodyResult.Ok("Speech accepted."));
        }

        public Task<BodyResult> ListenAsync(string mode = "conversation")
        {
            if (!capabilities.hearing) return Task.FromResult(CapabilityUnavailable("hearing"));
            if (!state.ready) return Task.FromResult(NotReady());

            state.listening = mode != "off";
            if (animator != null)
                animator.SetBool("IsListening", state.listening);

            return Task.FromResult(BodyResult.Ok());
        }

        public Task<BodyResult> ObserveAsync(string mode = "current_view", BodyTarget target = null)
        {
            if (!capabilities.vision) return Task.FromResult(CapabilityUnavailable("vision"));
            if (!state.ready) return Task.FromResult(NotReady());

            // Future: AxiomBodySensors creates a durable evidence artifact.
            return Task.FromResult(BodyResult.Ok("Observation requested."));
        }

        public Task<BodyResult> SetPostureAsync(string posture)
        {
            if (!state.ready) return Task.FromResult(NotReady());

            state.posture = string.IsNullOrWhiteSpace(posture) ? "standing" : posture;
            if (animator != null)
                animator.SetBool("IsSitting", state.posture == "sit" || state.posture == "sitting");

            return Task.FromResult(BodyResult.Ok());
        }

        public Task<BodyResult> StopAsync()
        {
            state.moving = false;
            state.speaking = false;

            if (animator != null)
            {
                animator.SetBool("IsSpeaking", false);
                animator.SetFloat("Speed", 0f);
            }

            if (voiceSource != null && voiceSource.isPlaying)
                voiceSource.Stop();

            return Task.FromResult(BodyResult.Ok("Voluntary body actions stopped."));
        }

        public void NotifySpeechFinished()
        {
            state.speaking = false;
            if (animator != null)
                animator.SetBool("IsSpeaking", false);
        }

        private static BodyResult NotReady() =>
            BodyResult.Fail("BODY_NOT_READY", "Body is not ready.");

        private static BodyResult CapabilityUnavailable(string capability) =>
            BodyResult.Fail("CAPABILITY_UNAVAILABLE", $"This body does not support {capability}.");
    }
}
