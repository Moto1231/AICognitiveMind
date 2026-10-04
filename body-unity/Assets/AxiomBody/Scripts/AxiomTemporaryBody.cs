using UnityEngine;

namespace Axiom.Body
{
    /// <summary>
    /// Development-only stand-in for the final approved Axiom model.
    /// Add this component to an empty GameObject named "Axiom".
    /// It creates a simple visible humanoid/fox-like body from Unity primitives
    /// and ensures the existing Axiom Body runtime bootstrap is present.
    ///
    /// Delete this component and its generated TemporaryVisual child when the
    /// production model/prefab is ready; the Body API/runtime can remain unchanged.
    /// </summary>
    [ExecuteAlways]
    [DisallowMultipleComponent]
    public sealed class AxiomTemporaryBody : MonoBehaviour
    {
        private const string VisualRootName = "TemporaryVisual";

        [SerializeField] private bool buildAutomatically = true;
        [SerializeField] private bool frameMainCamera = true;
        [SerializeField] private bool ensureSceneLight = true;

        private void OnEnable()
        {
            if (buildAutomatically)
                Build();
        }

        [ContextMenu("Build Temporary Axiom Body")]
        public void Build()
        {
            Transform existing = transform.Find(VisualRootName);
            if (existing == null)
            {
                var visualRoot = new GameObject(VisualRootName);
                visualRoot.transform.SetParent(transform, false);
                BuildVisual(visualRoot.transform);
            }

            if (GetComponent<AudioSource>() == null)
                gameObject.AddComponent<AudioSource>();

            if (GetComponent<AxiomBodyBootstrap>() == null)
                gameObject.AddComponent<AxiomBodyBootstrap>();

            if (GetComponent<AxiomBodyConnectionDebug>() == null)
                gameObject.AddComponent<AxiomBodyConnectionDebug>();

            if (ensureSceneLight)
                EnsureLight();

            if (frameMainCamera)
                FrameCamera();
        }

        [ContextMenu("Remove Temporary Visual")]
        public void RemoveTemporaryVisual()
        {
            Transform existing = transform.Find(VisualRootName);
            if (existing == null)
                return;

            if (Application.isPlaying)
                Destroy(existing.gameObject);
            else
                DestroyImmediate(existing.gameObject);
        }

        private static void BuildVisual(Transform parent)
        {
            CreatePrimitive(PrimitiveType.Capsule, "Torso", parent,
                new Vector3(0f, 1.25f, 0f),
                new Vector3(0.95f, 1.15f, 0.65f));

            CreatePrimitive(PrimitiveType.Sphere, "Head", parent,
                new Vector3(0f, 2.35f, 0f),
                new Vector3(1.05f, 0.92f, 0.92f));

            CreatePrimitive(PrimitiveType.Cube, "EarLeft", parent,
                new Vector3(-0.38f, 3.03f, 0f),
                new Vector3(0.28f, 0.65f, 0.24f),
                new Vector3(0f, 0f, 18f));

            CreatePrimitive(PrimitiveType.Cube, "EarRight", parent,
                new Vector3(0.38f, 3.03f, 0f),
                new Vector3(0.28f, 0.65f, 0.24f),
                new Vector3(0f, 0f, -18f));

            CreatePrimitive(PrimitiveType.Sphere, "EyeLeft", parent,
                new Vector3(-0.24f, 2.45f, -0.43f),
                new Vector3(0.13f, 0.13f, 0.09f));

            CreatePrimitive(PrimitiveType.Sphere, "EyeRight", parent,
                new Vector3(0.24f, 2.45f, -0.43f),
                new Vector3(0.13f, 0.13f, 0.09f));

            CreatePrimitive(PrimitiveType.Capsule, "ArmLeft", parent,
                new Vector3(-0.72f, 1.35f, 0f),
                new Vector3(0.28f, 0.72f, 0.28f),
                new Vector3(0f, 0f, -12f));

            CreatePrimitive(PrimitiveType.Capsule, "ArmRight", parent,
                new Vector3(0.72f, 1.35f, 0f),
                new Vector3(0.28f, 0.72f, 0.28f),
                new Vector3(0f, 0f, 12f));

            CreatePrimitive(PrimitiveType.Capsule, "LegLeft", parent,
                new Vector3(-0.28f, 0.25f, 0f),
                new Vector3(0.34f, 0.78f, 0.34f));

            CreatePrimitive(PrimitiveType.Capsule, "LegRight", parent,
                new Vector3(0.28f, 0.25f, 0f),
                new Vector3(0.34f, 0.78f, 0.34f));

            CreatePrimitive(PrimitiveType.Capsule, "Tail", parent,
                new Vector3(0f, 1.10f, 0.48f),
                new Vector3(0.30f, 0.75f, 0.30f),
                new Vector3(55f, 0f, 0f));

            var lookTarget = new GameObject("LookTarget");
            lookTarget.transform.SetParent(parent, false);
            lookTarget.transform.localPosition = new Vector3(0f, 2.35f, -3f);
        }

        private static GameObject CreatePrimitive(
            PrimitiveType type,
            string name,
            Transform parent,
            Vector3 localPosition,
            Vector3 localScale,
            Vector3? localEulerAngles = null)
        {
            GameObject go = GameObject.CreatePrimitive(type);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPosition;
            go.transform.localScale = localScale;
            go.transform.localEulerAngles = localEulerAngles ?? Vector3.zero;

            Collider collider = go.GetComponent<Collider>();
            if (collider != null)
            {
                if (Application.isPlaying)
                    Destroy(collider);
                else
                    DestroyImmediate(collider);
            }

            return go;
        }

        private static void EnsureLight()
        {
            if (Object.FindFirstObjectByType<Light>() != null)
                return;

            var lightGo = new GameObject("Axiom Development Light");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.2f;
            lightGo.transform.rotation = Quaternion.Euler(45f, -30f, 0f);
        }

        private void FrameCamera()
        {
            Camera camera = Camera.main;
            if (camera == null)
                camera = Object.FindFirstObjectByType<Camera>();

            if (camera == null)
            {
                var cameraGo = new GameObject("Main Camera");
                camera = cameraGo.AddComponent<Camera>();
                cameraGo.tag = "MainCamera";
            }

            Vector3 target = transform.position + new Vector3(0f, 1.55f, 0f);
            camera.transform.position = transform.position + new Vector3(0f, 1.55f, -6.5f);
            camera.transform.LookAt(target);
        }
    }
}
