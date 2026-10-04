using UnityEngine;

namespace Axiom.Body
{
    /// <summary>
    /// Minimal no-UI diagnostic for the first live Unity connection.
    /// Logs connection transitions without adding a dependency on TMP/UI packages.
    /// </summary>
    [DisallowMultipleComponent]
    public class AxiomBodyConnectionDebug : MonoBehaviour
    {
        [SerializeField] private AxiomBodyWebSocketClient transport;
        [SerializeField] private float pollSeconds = 0.5f;

        private bool lastConnected;
        private float nextPoll;

        private void Awake()
        {
            if (transport == null)
                transport = GetComponent<AxiomBodyWebSocketClient>();
        }

        private void Update()
        {
            if (transport == null || Time.unscaledTime < nextPoll)
                return;

            nextPoll = Time.unscaledTime + Mathf.Max(0.1f, pollSeconds);
            bool connected = transport.IsConnected;
            if (connected == lastConnected)
                return;

            lastConnected = connected;
            Debug.Log(connected
                ? $"[Axiom Body] CONNECTED to {transport.ServerUrl}"
                : "[Axiom Body] DISCONNECTED");
        }
    }
}
