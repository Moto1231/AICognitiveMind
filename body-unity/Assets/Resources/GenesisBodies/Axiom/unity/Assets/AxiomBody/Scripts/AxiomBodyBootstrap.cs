using UnityEngine;

namespace Axiom.Body
{
    /// <summary>
    /// Makes the reference body close to drop-in: add this to the Axiom root,
    /// then use Configure Now from the component context menu (or let Awake wire it).
    /// It only adds/wires protocol components; it does not alter the visual model.
    /// </summary>
    [DisallowMultipleComponent]
    public class AxiomBodyBootstrap : MonoBehaviour
    {
        [Header("Mind connection")]
        [SerializeField] private string serverUrl = "ws://127.0.0.1:8000/body/ws";
        [SerializeField] private string bodyId = "axiom.reference.unity";
        [SerializeField] private bool connectOnStart = true;

        [Header("Optional model references")]
        [SerializeField] private Animator animator;
        [SerializeField] private Transform lookTarget;
        [SerializeField] private AudioSource voiceSource;

        [SerializeField, HideInInspector] private AxiomBodyController controller;
        [SerializeField, HideInInspector] private AxiomBodyCommandRouter router;
        [SerializeField, HideInInspector] private AxiomBodyWebSocketClient transport;
        [SerializeField, HideInInspector] private AxiomBodyEventEmitter eventEmitter;

        public AxiomBodyController Controller => controller;
        public AxiomBodyWebSocketClient Transport => transport;

        private void Awake()
        {
            Configure();
        }

        [ContextMenu("Configure Axiom Body")]
        public void Configure()
        {
            controller = GetOrAdd<AxiomBodyController>();
            router = GetOrAdd<AxiomBodyCommandRouter>();
            transport = GetOrAdd<AxiomBodyWebSocketClient>();
            eventEmitter = GetOrAdd<AxiomBodyEventEmitter>();

            if (animator == null)
                animator = GetComponentInChildren<Animator>(true);

            if (voiceSource == null)
                voiceSource = GetComponentInChildren<AudioSource>(true);

            if (lookTarget == null)
            {
                var existing = transform.Find("Targets/LookTarget");
                if (existing != null)
                {
                    lookTarget = existing;
                }
                else
                {
                    var targets = transform.Find("Targets");
                    if (targets == null)
                    {
                        var targetsGo = new GameObject("Targets");
                        targetsGo.transform.SetParent(transform, false);
                        targets = targetsGo.transform;
                    }

                    var lookTargetGo = new GameObject("LookTarget");
                    lookTargetGo.transform.SetParent(targets, false);
                    lookTarget = lookTargetGo.transform;
                }
            }

            controller.Configure(animator, lookTarget, voiceSource);
            router.Configure(controller);
            transport.Configure(serverUrl, bodyId, router, connectOnStart);
            eventEmitter.Configure(transport);
        }

        private T GetOrAdd<T>() where T : Component
        {
            var component = GetComponent<T>();
            return component != null ? component : gameObject.AddComponent<T>();
        }
    }
}
