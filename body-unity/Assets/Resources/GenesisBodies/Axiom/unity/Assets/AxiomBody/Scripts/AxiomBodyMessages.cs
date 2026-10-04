using System;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Axiom.Body
{
    /// <summary>
    /// Wire DTOs for axiom.body/0.1. Payloads are JSON objects on the wire.
    /// Newtonsoft JSON is used intentionally because Unity JsonUtility cannot
    /// represent arbitrary object payloads.
    /// </summary>
    public class BodyCommandEnvelope
    {
        public string protocol = "axiom.body/0.1";

        [JsonProperty("message_type")]
        public string messageType = "command";

        [JsonProperty("command_id")]
        public string commandId;

        [JsonProperty("body_id")]
        public string bodyId;

        public string action;
        public JObject payload = new JObject();
    }

    public class BodyResultEnvelope
    {
        public string protocol = "axiom.body/0.1";

        [JsonProperty("message_type")]
        public string messageType = "result";

        [JsonProperty("command_id")]
        public string commandId;

        [JsonProperty("body_id")]
        public string bodyId;

        public bool success;
        public string code = "OK";
        public string message;
        public JObject payload = new JObject();
    }

    public class BodyEventEnvelope
    {
        public string protocol = "axiom.body/0.1";

        [JsonProperty("message_type")]
        public string messageType = "event";

        [JsonProperty("event_id")]
        public string eventId;

        [JsonProperty("body_id")]
        public string bodyId;

        [JsonProperty("event")]
        public string eventName;

        [JsonProperty("occurred_at")]
        public string occurredAt;

        public JObject payload = new JObject();
    }

    public class PresencePayload
    {
        public string presence;
        public float intensity = 1f;
    }

    public class LookAtPayload
    {
        public BodyTarget target = new BodyTarget();
        public float intensity = 1f;
    }

    public class ExpressionPayload
    {
        public string expression;
        public float intensity = 1f;

        [JsonProperty("duration_ms")]
        public int durationMs;
    }

    public class GesturePayload
    {
        public string gesture;
        public float intensity = 1f;
        public BodyTarget target;
    }

    public class SpeakPayload
    {
        public string text;
        public string emotion = "neutral";

        [JsonProperty("attention_target")]
        public BodyTarget attentionTarget;
    }

    public class ListenPayload
    {
        public string mode = "conversation";
    }

    public class ObservePayload
    {
        public string mode = "current_view";
        public BodyTarget target;
    }

    public class PosturePayload
    {
        public string posture = "stand";
    }
}
