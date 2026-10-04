using Newtonsoft.Json;
using UnityEngine;

namespace Axiom.Body
{
    public class BodyIdentity
    {
        [JsonProperty("body_id")]
        public string bodyId = "axiom.reference.unity";

        [JsonProperty("name")]
        public string displayName = "Axiom Reference Body";

        [JsonProperty("body_type")]
        public string bodyType = "virtual_avatar";

        public string provider = "Axiom";
        public string version = "0.1.0";
    }

    public class BodyCapabilities
    {
        public bool speech = true;
        public bool hearing = true;
        public bool vision = true;
        public bool gaze = true;

        [JsonProperty("facial_expression")]
        public bool facialExpression = true;

        public bool gesture = true;
        public bool locomotion = false;

        [JsonProperty("tail_expression")]
        public bool tailExpression = true;

        [JsonProperty("ear_expression")]
        public bool earExpression = true;

        public bool touch = false;
    }

    public class BodyTarget
    {
        public string type = "none";
        public string id;

        [JsonProperty("world_position")]
        public Vector3 worldPosition;
    }

    public class BodyState
    {
        public bool ready;
        public bool connected;
        public string presence = "neutral";
        public string expression = "neutral";
        public string posture = "standing";
        public bool speaking;
        public bool listening;
        public bool moving;
        public BodyTarget attention = new BodyTarget();
    }

    public class BodyResult
    {
        public bool success;
        public string code;
        public string message;

        public static BodyResult Ok(string message = null) => new BodyResult
        {
            success = true,
            code = "OK",
            message = message
        };

        public static BodyResult Fail(string code, string message) => new BodyResult
        {
            success = false,
            code = code,
            message = message
        };
    }
}
