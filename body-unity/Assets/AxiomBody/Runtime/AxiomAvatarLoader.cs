using System;
using System.Threading.Tasks;
using UniVRM10;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class AxiomAvatarLoader : MonoBehaviour
    {
        private Vrm10Instance _instance;

        public Vrm10Instance Instance => _instance;

        public async Task<Vrm10Instance> LoadAsync(
            MindApiClient client,
            Camera targetCamera
        )
        {
            byte[] bytes = await client.DownloadAvatarAsync();
            if (bytes == null || bytes.Length == 0)
            {
                throw new InvalidOperationException("Mind returned an empty avatar.");
            }

            _instance = await Vrm10.LoadBytesAsync(bytes);
            if (_instance == null)
            {
                throw new InvalidOperationException("UniVRM could not load the Mind's VRM body.");
            }

            _instance.name = "Axiom";
            _instance.transform.SetParent(transform, false);
            FrameAvatar(targetCamera, _instance.gameObject);
            return _instance;
        }

        private static void FrameAvatar(Camera camera, GameObject avatar)
        {
            Renderer[] renderers = avatar.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0)
            {
                camera.transform.position = new Vector3(0f, 1.2f, 3f);
                camera.transform.LookAt(new Vector3(0f, 1.2f, 0f));
                return;
            }

            Bounds bounds = renderers[0].bounds;
            for (int index = 1; index < renderers.Length; index++)
            {
                bounds.Encapsulate(renderers[index].bounds);
            }

            Vector3 center = bounds.center;
            float verticalFov = camera.fieldOfView * Mathf.Deg2Rad;
            float horizontalFov =
                2f * Mathf.Atan(Mathf.Tan(verticalFov / 2f) * camera.aspect);
            float distanceForHeight =
                bounds.size.y * 1.18f / (2f * Mathf.Tan(verticalFov / 2f));
            float distanceForWidth =
                bounds.size.x * 1.18f / (2f * Mathf.Tan(horizontalFov / 2f));
            float distance = Mathf.Max(distanceForHeight, distanceForWidth, 1.5f);

            camera.transform.position = center + Vector3.forward * distance;
            camera.transform.LookAt(center);
            camera.nearClipPlane = Mathf.Max(0.01f, distance / 100f);
            camera.farClipPlane = Mathf.Max(50f, distance * 20f);
        }
    }
}
