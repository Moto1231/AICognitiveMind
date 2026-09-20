using System;
using System.Collections.Generic;
using UniVRM10;
using UnityEngine;

namespace Axiom.Body
{
    [Serializable]
    public sealed class AxiomAvatarAppearance
    {
        public string skinColor = "#b88566";
        public string hairColor = "#090a0d";
        public string shirtColor = "#2e4257";
        public string pantsColor = "#1a1f29";
        public string eyeColor = "#090a0d";
        public string shoeColor = "#090a0d";

        public float headSize = 1f;
        public float hairVolume = 1f;
        public float eyeSize = 1f;
        public float eyeSpacing = 1f;
        public float mouthWidth = 1f;
        public float torsoWidth = 1f;
        public float shoulderWidth = 1f;
        public float armThickness = 1f;
        public float legThickness = 1f;

        public AxiomAvatarAppearance Clone()
        {
            return JsonUtility.FromJson<AxiomAvatarAppearance>(
                JsonUtility.ToJson(this)
            );
        }

        public void Normalize()
        {
            skinColor = NormalizeHex(skinColor, "#b88566");
            hairColor = NormalizeHex(hairColor, "#090a0d");
            shirtColor = NormalizeHex(shirtColor, "#2e4257");
            pantsColor = NormalizeHex(pantsColor, "#1a1f29");
            eyeColor = NormalizeHex(eyeColor, "#090a0d");
            shoeColor = NormalizeHex(shoeColor, "#090a0d");

            headSize = Mathf.Clamp(headSize, 0.75f, 1.35f);
            hairVolume = Mathf.Clamp(hairVolume, 0.60f, 1.60f);
            eyeSize = Mathf.Clamp(eyeSize, 0.60f, 1.60f);
            eyeSpacing = Mathf.Clamp(eyeSpacing, 0.65f, 1.45f);
            mouthWidth = Mathf.Clamp(mouthWidth, 0.60f, 1.50f);
            torsoWidth = Mathf.Clamp(torsoWidth, 0.70f, 1.40f);
            shoulderWidth = Mathf.Clamp(shoulderWidth, 0.75f, 1.40f);
            armThickness = Mathf.Clamp(armThickness, 0.65f, 1.50f);
            legThickness = Mathf.Clamp(legThickness, 0.65f, 1.50f);
        }

        public static AxiomAvatarAppearance Defaults()
        {
            return new AxiomAvatarAppearance();
        }

        private static string NormalizeHex(string candidate, string fallback)
        {
            string value = (candidate ?? string.Empty).Trim();
            if (
                value.Length == 7 &&
                value[0] == '#' &&
                ColorUtility.TryParseHtmlString(value, out _)
            )
            {
                return value.ToLowerInvariant();
            }

            return fallback;
        }
    }

    public sealed class AxiomAvatarEditorRuntime : MonoBehaviour
    {
        private const string AppearanceKey = "axiom.avatar.appearance.v0.1";

        private readonly Dictionary<string, NodeBaseline> _baseline =
            new Dictionary<string, NodeBaseline>(StringComparer.Ordinal);
        private readonly Dictionary<string, List<Material>> _materials =
            new Dictionary<string, List<Material>>(StringComparer.OrdinalIgnoreCase);

        private Vrm10Instance _avatar;
        private AxiomAvatarAppearance _appearance =
            AxiomAvatarAppearance.Defaults();

        public AxiomAvatarAppearance Appearance => _appearance;

        public void Attach(Vrm10Instance avatar)
        {
            if (avatar == null)
            {
                throw new ArgumentNullException(nameof(avatar));
            }

            if (!ReferenceEquals(_avatar, avatar))
            {
                _avatar = avatar;
                CaptureBaseline();
                CaptureMaterials();
            }

            _appearance = LoadSaved();
            ApplyPreview();
        }

        public void ApplyPreview()
        {
            if (_avatar == null)
            {
                return;
            }

            _appearance.Normalize();

            SetMaterialColor("Skin", _appearance.skinColor);
            SetMaterialColor("Hair", _appearance.hairColor);
            SetMaterialColor("Shirt", _appearance.shirtColor);
            SetMaterialColor("Pants", _appearance.pantsColor);
            SetMaterialColor("Eyes", _appearance.eyeColor);
            SetMaterialColor("Shoes", _appearance.shoeColor);

            SetNodeScale(
                "HeadVisual",
                _appearance.headSize,
                _appearance.headSize,
                _appearance.headSize
            );
            SetNodeScale(
                "HairVisual",
                _appearance.hairVolume,
                _appearance.hairVolume,
                _appearance.hairVolume
            );

            SetNodeScale(
                "LeftEyeVisual",
                _appearance.eyeSize,
                _appearance.eyeSize,
                _appearance.eyeSize
            );
            SetNodeScale(
                "RightEyeVisual",
                _appearance.eyeSize,
                _appearance.eyeSize,
                _appearance.eyeSize
            );
            SetNodePositionX("LeftEyeVisual", _appearance.eyeSpacing);
            SetNodePositionX("RightEyeVisual", _appearance.eyeSpacing);

            SetNodeScale("MouthVisual", _appearance.mouthWidth, 1f, 1f);

            SetNodeScale("PelvisVisual", _appearance.torsoWidth, 1f, 1f);
            SetNodeScale("TorsoLowerVisual", _appearance.torsoWidth, 1f, 1f);
            SetNodeScale("TorsoUpperVisual", _appearance.torsoWidth, 1f, 1f);

            SetNodePositionX("LeftUpperArm", _appearance.shoulderWidth);
            SetNodePositionX("RightUpperArm", _appearance.shoulderWidth);

            foreach (string name in new[]
            {
                "LeftUpperArmVisual",
                "LeftLowerArmVisual",
                "RightUpperArmVisual",
                "RightLowerArmVisual"
            })
            {
                SetNodeScale(
                    name,
                    1f,
                    _appearance.armThickness,
                    _appearance.armThickness
                );
            }

            foreach (string name in new[]
            {
                "LeftUpperLegVisual",
                "LeftLowerLegVisual",
                "RightUpperLegVisual",
                "RightLowerLegVisual"
            })
            {
                SetNodeScale(
                    name,
                    _appearance.legThickness,
                    1f,
                    _appearance.legThickness
                );
            }
        }

        public void Save()
        {
            _appearance.Normalize();
            PlayerPrefs.SetString(AppearanceKey, JsonUtility.ToJson(_appearance));
            PlayerPrefs.Save();
        }

        public void Reset()
        {
            PlayerPrefs.DeleteKey(AppearanceKey);
            PlayerPrefs.Save();
            _appearance = AxiomAvatarAppearance.Defaults();
            ApplyPreview();
        }

        private AxiomAvatarAppearance LoadSaved()
        {
            if (!PlayerPrefs.HasKey(AppearanceKey))
            {
                return AxiomAvatarAppearance.Defaults();
            }

            try
            {
                AxiomAvatarAppearance loaded =
                    JsonUtility.FromJson<AxiomAvatarAppearance>(
                        PlayerPrefs.GetString(AppearanceKey)
                    );
                if (loaded == null)
                {
                    return AxiomAvatarAppearance.Defaults();
                }

                loaded.Normalize();
                return loaded;
            }
            catch
            {
                return AxiomAvatarAppearance.Defaults();
            }
        }

        private void CaptureBaseline()
        {
            _baseline.Clear();
            foreach (Transform node in _avatar.GetComponentsInChildren<Transform>(true))
            {
                if (!_baseline.ContainsKey(node.name))
                {
                    _baseline[node.name] = new NodeBaseline
                    {
                        Position = node.localPosition,
                        Scale = node.localScale
                    };
                }
            }
        }

        private void CaptureMaterials()
        {
            _materials.Clear();
            foreach (
                Renderer renderer in
                _avatar.GetComponentsInChildren<Renderer>(true)
            )
            {
                foreach (Material material in renderer.materials)
                {
                    AddMaterial("Skin", material);
                    AddMaterial("Hair", material);
                    AddMaterial("Shirt", material);
                    AddMaterial("Pants", material);
                    AddMaterial("Eyes", material);
                    AddMaterial("Shoes", material);
                }
            }
        }

        private void AddMaterial(string canonicalName, Material material)
        {
            if (
                material == null ||
                !material.name.StartsWith(
                    canonicalName,
                    StringComparison.OrdinalIgnoreCase
                )
            )
            {
                return;
            }

            if (!_materials.TryGetValue(canonicalName, out List<Material> list))
            {
                list = new List<Material>();
                _materials[canonicalName] = list;
            }

            if (!list.Contains(material))
            {
                list.Add(material);
            }
        }

        private void SetMaterialColor(string materialName, string hex)
        {
            if (
                !_materials.TryGetValue(materialName, out List<Material> materials) ||
                !ColorUtility.TryParseHtmlString(hex, out Color color)
            )
            {
                return;
            }

            foreach (Material material in materials)
            {
                if (material.HasProperty("_BaseColor"))
                {
                    material.SetColor("_BaseColor", color);
                }

                if (material.HasProperty("_Color"))
                {
                    material.SetColor("_Color", color);
                }

                if (
                    !material.HasProperty("_BaseColor") &&
                    !material.HasProperty("_Color")
                )
                {
                    continue;
                }
            }
        }

        private void SetNodeScale(
            string name,
            float xMultiplier,
            float yMultiplier,
            float zMultiplier
        )
        {
            Transform node = FindNode(name);
            if (node == null || !_baseline.TryGetValue(name, out NodeBaseline baseline))
            {
                return;
            }

            node.localScale = new Vector3(
                baseline.Scale.x * xMultiplier,
                baseline.Scale.y * yMultiplier,
                baseline.Scale.z * zMultiplier
            );
        }

        private void SetNodePositionX(string name, float multiplier)
        {
            Transform node = FindNode(name);
            if (node == null || !_baseline.TryGetValue(name, out NodeBaseline baseline))
            {
                return;
            }

            Vector3 position = node.localPosition;
            position.x = baseline.Position.x * multiplier;
            node.localPosition = position;
        }

        private Transform FindNode(string name)
        {
            if (_avatar == null)
            {
                return null;
            }

            foreach (
                Transform node in
                _avatar.GetComponentsInChildren<Transform>(true)
            )
            {
                if (string.Equals(node.name, name, StringComparison.Ordinal))
                {
                    return node;
                }
            }

            return null;
        }

        private struct NodeBaseline
        {
            public Vector3 Position;
            public Vector3 Scale;
        }
    }
}
