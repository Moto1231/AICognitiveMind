using System;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Axiom.Body
{
    /// <summary>
    /// Converts stable semantic Axiom Body commands into IAxiomBody calls.
    /// Transport remains outside this class.
    /// </summary>
    public class AxiomBodyCommandRouter : MonoBehaviour
    {
        [SerializeField] private AxiomBodyController body;

        public string BodyId => body != null ? body.GetIdentity().bodyId : "axiom.reference.unity";

        public void Configure(AxiomBodyController configuredBody)
        {
            if (configuredBody != null) body = configuredBody;
        }

        public async Task NotifyTransportConnectedAsync()
        {
            if (body != null)
                await body.ConnectAsync();
        }

        public async Task NotifyTransportDisconnectedAsync()
        {
            if (body != null)
                await body.DisconnectAsync();
        }

        public async Task<BodyResultEnvelope> RouteAsync(BodyCommandEnvelope command)
        {
            if (command == null)
                return Failure(null, "INVALID_INTENT", "Command is null.");

            if (body == null)
                return Failure(command, "BODY_NOT_READY", "No body controller is assigned.");

            BodyResult result;

            try
            {
                switch ((command.action ?? string.Empty).Trim().ToLowerInvariant())
                {
                    case "connect":
                        result = await body.ConnectAsync();
                        break;

                    case "disconnect":
                        result = await body.DisconnectAsync();
                        break;

                    case "presence":
                    {
                        var p = Parse<PresencePayload>(command.payload);
                        result = await body.SetPresenceAsync(p.presence, p.intensity);
                        break;
                    }

                    case "look_at":
                    {
                        var p = Parse<LookAtPayload>(command.payload);
                        result = await body.LookAtAsync(p.target, p.intensity);
                        break;
                    }

                    case "expression":
                    {
                        var p = Parse<ExpressionPayload>(command.payload);
                        result = await body.SetExpressionAsync(p.expression, p.intensity, p.durationMs);
                        break;
                    }

                    case "gesture":
                    {
                        var p = Parse<GesturePayload>(command.payload);
                        result = await body.GestureAsync(p.gesture, p.intensity, p.target);
                        break;
                    }

                    case "speak":
                    {
                        var p = Parse<SpeakPayload>(command.payload);
                        result = await body.SpeakAsync(p.text, p.emotion, p.attentionTarget);
                        break;
                    }

                    case "listen":
                    {
                        var p = Parse<ListenPayload>(command.payload);
                        result = await body.ListenAsync(p.mode);
                        break;
                    }

                    case "observe":
                    {
                        var p = Parse<ObservePayload>(command.payload);
                        result = await body.ObserveAsync(p.mode, p.target);
                        break;
                    }

                    case "posture":
                    {
                        var p = Parse<PosturePayload>(command.payload);
                        result = await body.SetPostureAsync(p.posture);
                        break;
                    }

                    case "stop":
                        result = await body.StopAsync();
                        break;

                    case "status":
                        return Success(command, JObject.FromObject(body.GetState()));

                    case "capabilities":
                        return Success(command, JObject.FromObject(body.GetCapabilities()));

                    default:
                        return Failure(command, "INVALID_INTENT", $"Unknown body action '{command.action}'.");
                }
            }
            catch (Exception ex)
            {
                return Failure(command, "INTERNAL_BODY_ERROR", ex.Message);
            }

            return new BodyResultEnvelope
            {
                commandId = command.commandId,
                bodyId = body.GetIdentity().bodyId,
                success = result.success,
                code = result.code,
                message = result.message,
                payload = new JObject()
            };
        }

        private static T Parse<T>(JObject payload) where T : new()
        {
            if (payload == null) return new T();
            try
            {
                return payload.ToObject<T>() ?? new T();
            }
            catch
            {
                return new T();
            }
        }

        private BodyResultEnvelope Success(BodyCommandEnvelope command, JObject payload) =>
            new BodyResultEnvelope
            {
                commandId = command.commandId,
                bodyId = body.GetIdentity().bodyId,
                success = true,
                code = "OK",
                payload = payload ?? new JObject()
            };

        private BodyResultEnvelope Failure(BodyCommandEnvelope command, string code, string message) =>
            new BodyResultEnvelope
            {
                commandId = command?.commandId,
                bodyId = body != null ? body.GetIdentity().bodyId : null,
                success = false,
                code = code,
                message = message,
                payload = new JObject()
            };
    }
}
