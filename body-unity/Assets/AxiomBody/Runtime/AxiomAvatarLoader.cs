using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using UniVRM10;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class AxiomAvatarLoader : MonoBehaviour
    {
        public const string GenesisBodyName = "Genesis";

        private const string SelectedBodyKey = "axiom.body.selected.v0.1";
        private const string PresetResourcePath = "GenesisBodies";

        private readonly Dictionary<string, GameObject> _presetAssets =
            new Dictionary<string, GameObject>(
                StringComparer.OrdinalIgnoreCase
            );

        private Vrm10Instance _instance;
        private GameObject _root;
        private string _currentBodyName = GenesisBodyName;
        private string[] _availableBodies;

        public Vrm10Instance Instance => _instance;
        public GameObject Root => _root;
        public string CurrentBodyName => _currentBodyName;
        public bool IsGenesis =>
            string.Equals(
                _currentBodyName,
                GenesisBodyName,
                StringComparison.Ordinal
            );

        public string[] AvailableBodies
        {
            get
            {
                EnsureBodyCatalog();
                return (string[])_availableBodies.Clone();
            }
        }

        public void RefreshBodyCatalog()
        {
            _availableBodies = null;
            _presetAssets.Clear();
            EnsureBodyCatalog();
        }

        private void EnsureBodyCatalog()
        {
            if (_availableBodies != null)
            {
                return;
            }

            _presetAssets.Clear();

            foreach (
                GameObject asset in
                Resources.LoadAll<GameObject>(PresetResourcePath)
            )
            {
                if (
                    asset == null ||
                    string.IsNullOrWhiteSpace(asset.name) ||
                    string.Equals(
                        asset.name,
                        GenesisBodyName,
                        StringComparison.OrdinalIgnoreCase
                    ) ||
                    _presetAssets.ContainsKey(asset.name)
                )
                {
                    continue;
                }

                _presetAssets[asset.name] = asset;
            }

            List<string> names = new List<string>
            {
                GenesisBodyName
            };
            names.AddRange(
                _presetAssets.Keys.OrderBy(
                    value => value,
                    StringComparer.OrdinalIgnoreCase
                )
            );
            _availableBodies = names.ToArray();
        }

        public async Task<Vrm10Instance> LoadAsync(
            MindApiClient client,
            Camera targetCamera
        )
        {
            await SelectBodyAsync(
                GenesisBodyName,
                client,
                targetCamera,
                persist: false
            );
            return _instance;
        }

        public async Task LoadSelectedAsync(
            MindApiClient client,
            Camera targetCamera
        )
        {
            string selected = PlayerPrefs.GetString(
                SelectedBodyKey,
                GenesisBodyName
            );

            try
            {
                await SelectBodyAsync(
                    selected,
                    client,
                    targetCamera,
                    persist: false
                );
            }
            catch (InvalidOperationException)
            {
                await SelectBodyAsync(
                    GenesisBodyName,
                    client,
                    targetCamera,
                    persist: true
                );
            }
        }

        public async Task SelectBodyAsync(
            string bodyName,
            MindApiClient client,
            Camera targetCamera,
            bool persist = true
        )
        {
            string requested = string.IsNullOrWhiteSpace(bodyName)
                ? GenesisBodyName
                : bodyName.Trim();

            if (
                string.Equals(
                    requested,
                    GenesisBodyName,
                    StringComparison.OrdinalIgnoreCase
                )
            )
            {
                await LoadGenesisAsync(client, targetCamera);
                _currentBodyName = GenesisBodyName;
            }
            else
            {
                LoadPreset(requested, targetCamera);
                _currentBodyName = requested;
            }

            if (persist)
            {
                PlayerPrefs.SetString(
                    SelectedBodyKey,
                    _currentBodyName
                );
                PlayerPrefs.Save();
            }
        }

        private async Task LoadGenesisAsync(
            MindApiClient client,
            Camera targetCamera
        )
        {
            if (client == null)
            {
                throw new ArgumentNullException(nameof(client));
            }

            byte[] bytes = await client.DownloadAvatarAsync();
            if (bytes == null || bytes.Length == 0)
            {
                throw new InvalidOperationException(
                    "Mind returned an empty avatar."
                );
            }

            Vrm10Instance next = await Vrm10.LoadBytesAsync(bytes);
            if (next == null)
            {
                throw new InvalidOperationException(
                    "UniVRM could not load the Mind's VRM body."
                );
            }

            DestroyCurrent();

            _instance = next;
            _root = next.gameObject;
            _root.name = "Axiom - Genesis";
            _root.transform.SetParent(transform, false);
            FrameAvatar(targetCamera, _root);
        }

        private void LoadPreset(
            string bodyName,
            Camera targetCamera
        )
        {
            EnsureBodyCatalog();
            _presetAssets.TryGetValue(
                bodyName,
                out GameObject asset
            );

            if (asset == null)
            {
                throw new InvalidOperationException(
                    "Preset body '" +
                    bodyName +
                    "' was not found under Resources/" +
                    PresetResourcePath +
                    "."
                );
            }

            GameObject next = Instantiate(asset);
            next.name = "Axiom - " + asset.name;
            next.transform.SetParent(transform, false);
            next.SetActive(true);

            DestroyCurrent();

            _instance = next.GetComponentInChildren<Vrm10Instance>(true);
            _root = next;
            FrameAvatar(targetCamera, _root);
        }

        public void Unload()
        {
            DestroyCurrent();
            _currentBodyName = GenesisBodyName;
        }

        private void DestroyCurrent()
        {
            if (_root != null)
            {
                Destroy(_root);
            }

            _instance = null;
            _root = null;
        }

        public static void FrameAvatar(
            Camera camera,
            GameObject avatar
        )
        {
            if (camera == null || avatar == null)
            {
                return;
            }

            Renderer[] renderers =
                avatar.GetComponentsInChildren<Renderer>(true);
            if (renderers.Length == 0)
            {
                camera.transform.position =
                    new Vector3(0f, 1.2f, 3f);
                camera.transform.LookAt(
                    new Vector3(0f, 1.2f, 0f)
                );
                return;
            }

            Bounds bounds = renderers[0].bounds;
            for (
                int index = 1;
                index < renderers.Length;
                index++
            )
            {
                bounds.Encapsulate(renderers[index].bounds);
            }

            Vector3 center = bounds.center;
            float verticalFov =
                camera.fieldOfView * Mathf.Deg2Rad;
            float horizontalFov =
                2f *
                Mathf.Atan(
                    Mathf.Tan(verticalFov / 2f) *
                    camera.aspect
                );
            float distanceForHeight =
                bounds.size.y *
                1.18f /
                (2f * Mathf.Tan(verticalFov / 2f));
            float distanceForWidth =
                bounds.size.x *
                1.18f /
                (2f * Mathf.Tan(horizontalFov / 2f));
            float distance = Mathf.Max(
                distanceForHeight,
                distanceForWidth,
                1.5f
            );

            camera.transform.position =
                center + Vector3.forward * distance;
            camera.transform.LookAt(center);
            camera.nearClipPlane = Mathf.Max(
                0.01f,
                distance / 100f
            );
            camera.farClipPlane = Mathf.Max(
                50f,
                distance * 20f
            );
        }
    }
}
