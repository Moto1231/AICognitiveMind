using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Axiom.Body
{
    /// <summary>
    /// Reference Unity transport for the Axiom Body protocol.
    /// Connects outward to the Mind's /body/ws endpoint and executes semantic
    /// commands on Unity's main thread.
    /// </summary>
    public class AxiomBodyWebSocketClient : MonoBehaviour
    {
        [Header("Mind connection")]
        [SerializeField] private string serverUrl = "ws://127.0.0.1:8000/body/ws";
        [SerializeField] private string bodyId = "axiom.reference.unity";
        [SerializeField] private bool connectOnStart = true;
        [SerializeField] private float reconnectDelaySeconds = 3f;

        [Header("Body")]
        [SerializeField] private AxiomBodyCommandRouter router;

        private readonly ConcurrentQueue<Func<Task>> mainThreadQueue = new();
        private ClientWebSocket socket;
        private CancellationTokenSource lifetimeCts;
        private Task connectionLoop;

        public bool IsConnected => socket != null && socket.State == WebSocketState.Open;
        public string ServerUrl => serverUrl;

        public void Configure(string configuredServerUrl, string configuredBodyId, AxiomBodyCommandRouter configuredRouter, bool configuredConnectOnStart = true)
        {
            if (!string.IsNullOrWhiteSpace(configuredServerUrl)) serverUrl = configuredServerUrl;
            if (!string.IsNullOrWhiteSpace(configuredBodyId)) bodyId = configuredBodyId;
            if (configuredRouter != null) router = configuredRouter;
            connectOnStart = configuredConnectOnStart;
        }

        private void Start()
        {
            if (connectOnStart)
                Connect();
        }

        private void Update()
        {
            while (mainThreadQueue.TryDequeue(out var work))
                _ = RunQueuedWorkAsync(work);
        }

        private async Task RunQueuedWorkAsync(Func<Task> work)
        {
            try { await work(); }
            catch (Exception ex) { Debug.LogException(ex); }
        }

        private void OnDestroy()
        {
            // OnDestroy already executes on Unity's main thread; do not enqueue work
            // that would require another Update tick after this component is gone.
            if (lifetimeCts != null)
                lifetimeCts.Cancel();

            if (socket != null)
            {
                try { socket.Abort(); } catch { }
                socket.Dispose();
                socket = null;
            }

            if (router != null)
                _ = router.NotifyTransportDisconnectedAsync();
        }

        public void Connect()
        {
            if (connectionLoop != null && !connectionLoop.IsCompleted)
                return;

            lifetimeCts = new CancellationTokenSource();
            connectionLoop = ConnectionLoopAsync(lifetimeCts.Token);
        }

        public async Task DisconnectAsync()
        {
            if (lifetimeCts == null)
                return;

            lifetimeCts.Cancel();

            if (socket != null)
            {
                try
                {
                    if (socket.State == WebSocketState.Open)
                        await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Unity body shutting down", CancellationToken.None);
                }
                catch { }
                socket.Dispose();
                socket = null;
            }

            if (router != null)
                await RunOnMainThreadAsync(() => router.NotifyTransportDisconnectedAsync());

            lifetimeCts.Dispose();
            lifetimeCts = null;
        }

        public async Task EmitEventAsync(string eventName, object payload = null)
        {
            if (!IsConnected)
                return;

            var envelope = new BodyEventEnvelope
            {
                eventId = $"evt_{Guid.NewGuid():N}",
                bodyId = bodyId,
                eventName = eventName,
                occurredAt = DateTimeOffset.UtcNow.ToString("O"),
                payload = payload == null ? new JObject() : JObject.FromObject(payload)
            };

            await SendJsonAsync(envelope, lifetimeCts?.Token ?? CancellationToken.None);
        }

        private async Task ConnectionLoopAsync(CancellationToken cancellationToken)
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                try
                {
                    socket = new ClientWebSocket();
                    await socket.ConnectAsync(BuildUri(), cancellationToken);

                    if (router != null)
                        await RunOnMainThreadAsync(() => router.NotifyTransportConnectedAsync());

                    await EmitEventAsync("body.ready", new { ready = true });
                    await ReceiveLoopAsync(cancellationToken);
                }
                catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"Axiom Body connection error: {ex.Message}");
                }
                finally
                {
                    if (socket != null)
                    {
                        socket.Dispose();
                        socket = null;
                    }

                    if (router != null && !cancellationToken.IsCancellationRequested)
                        await RunOnMainThreadAsync(() => router.NotifyTransportDisconnectedAsync());
                }

                if (!cancellationToken.IsCancellationRequested)
                {
                    int delay = Mathf.Max(250, Mathf.RoundToInt(reconnectDelaySeconds * 1000f));
                    await Task.Delay(delay, cancellationToken);
                }
            }
        }

        private async Task ReceiveLoopAsync(CancellationToken cancellationToken)
        {
            var buffer = new byte[16 * 1024];

            while (socket != null && socket.State == WebSocketState.Open && !cancellationToken.IsCancellationRequested)
            {
                using var stream = new MemoryStream();
                WebSocketReceiveResult result;

                do
                {
                    result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), cancellationToken);
                    if (result.MessageType == WebSocketMessageType.Close)
                        return;
                    stream.Write(buffer, 0, result.Count);
                }
                while (!result.EndOfMessage);

                string json = Encoding.UTF8.GetString(stream.ToArray());
                var command = JsonConvert.DeserializeObject<BodyCommandEnvelope>(json);
                if (command == null || command.messageType != "command")
                    continue;

                BodyResultEnvelope response;
                if (router == null)
                {
                    response = new BodyResultEnvelope
                    {
                        commandId = command.commandId,
                        bodyId = bodyId,
                        success = false,
                        code = "BODY_NOT_READY",
                        message = "No AxiomBodyCommandRouter is assigned."
                    };
                }
                else
                {
                    response = await RunOnMainThreadAsync(() => router.RouteAsync(command));
                }

                await SendJsonAsync(response, cancellationToken);
            }
        }

        private Uri BuildUri()
        {
            string separator = serverUrl.Contains("?") ? "&" : "?";
            return new Uri($"{serverUrl}{separator}body_id={Uri.EscapeDataString(bodyId)}");
        }

        private async Task SendJsonAsync(object value, CancellationToken cancellationToken)
        {
            if (!IsConnected)
                return;

            string json = JsonConvert.SerializeObject(value);
            byte[] bytes = Encoding.UTF8.GetBytes(json);
            await socket.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cancellationToken);
        }

        private Task RunOnMainThreadAsync(Func<Task> work)
        {
            var tcs = new TaskCompletionSource<bool>();
            mainThreadQueue.Enqueue(async () =>
            {
                try
                {
                    await work();
                    tcs.TrySetResult(true);
                }
                catch (Exception ex)
                {
                    tcs.TrySetException(ex);
                }
            });
            return tcs.Task;
        }

        private Task<T> RunOnMainThreadAsync<T>(Func<Task<T>> work)
        {
            var tcs = new TaskCompletionSource<T>();
            mainThreadQueue.Enqueue(async () =>
            {
                try
                {
                    T result = await work();
                    tcs.TrySetResult(result);
                }
                catch (Exception ex)
                {
                    tcs.TrySetException(ex);
                }
            });
            return tcs.Task;
        }
    }
}
