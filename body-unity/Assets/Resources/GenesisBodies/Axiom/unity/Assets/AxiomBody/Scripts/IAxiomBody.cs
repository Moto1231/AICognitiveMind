using System.Threading.Tasks;

namespace Axiom.Body
{
    public interface IAxiomBody
    {
        BodyIdentity GetIdentity();
        BodyCapabilities GetCapabilities();
        BodyState GetState();

        Task<BodyResult> ConnectAsync();
        Task<BodyResult> DisconnectAsync();
        Task<BodyResult> SetPresenceAsync(string presence, float intensity = 1f);
        Task<BodyResult> LookAtAsync(BodyTarget target, float intensity = 1f);
        Task<BodyResult> SetExpressionAsync(string expression, float intensity = 1f, int durationMs = 0);
        Task<BodyResult> GestureAsync(string gesture, float intensity = 1f, BodyTarget target = null);
        Task<BodyResult> SpeakAsync(string text, string emotion = "neutral", BodyTarget attentionTarget = null);
        Task<BodyResult> ListenAsync(string mode = "conversation");
        Task<BodyResult> ObserveAsync(string mode = "current_view", BodyTarget target = null);
        Task<BodyResult> SetPostureAsync(string posture);
        Task<BodyResult> StopAsync();
    }
}
