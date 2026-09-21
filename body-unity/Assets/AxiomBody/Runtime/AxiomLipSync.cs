using System;
using UniVRM10;
using UnityEngine;

namespace Axiom.Body
{
    [DefaultExecutionOrder(12000)]
    public sealed class AxiomLipSync : MonoBehaviour
    {
        private const int SampleCount = 256;
        private static readonly ExpressionKey MouthKey =
            ExpressionKey.CreateFromPreset(ExpressionPreset.aa);

        private static readonly string[] MouthBlendShapeNames =
        {
            "aaOpen",
            "MouthOpen",
            "JawOpen",
            "vrc.v_aa",
            "AA",
            "A"
        };

        private static readonly string[] MouthTransformNames =
        {
            "MouthVisual",
            "Mouth",
            "mouth"
        };

        private readonly float[] _samples = new float[SampleCount];
        private GameObject _avatarRoot;
        private Vrm10Instance _avatar;
        private AudioSource _audioSource;
        private SkinnedMeshRenderer _mouthRenderer;
        private Transform _mouthTransform;
        private Vector3 _mouthRestScale = Vector3.one;
        private Vector3 _mouthRestPosition = Vector3.zero;
        private int _mouthBlendShapeIndex = -1;
        private bool _hasVrmMouthExpression;
        private bool _genesisMouthTransform;
        private float _weight;

        public bool HasMouthTarget =>
            _hasVrmMouthExpression ||
            _mouthBlendShapeIndex >= 0 ||
            _mouthTransform != null;

        public float CurrentWeight => _weight;

        public string TargetDescription
        {
            get
            {
                if (_mouthTransform != null)
                {
                    return _genesisMouthTransform
                        ? "Genesis MouthVisual transform"
                        : _mouthTransform.name + " transform";
                }

                if (
                    _hasVrmMouthExpression &&
                    _mouthBlendShapeIndex >= 0
                )
                {
                    return "VRM aa + " +
                        _mouthRenderer.sharedMesh.GetBlendShapeName(
                            _mouthBlendShapeIndex
                        ) +
                        " blendshape";
                }

                if (_hasVrmMouthExpression)
                {
                    return "VRM aa expression";
                }

                if (_mouthBlendShapeIndex >= 0)
                {
                    return _mouthRenderer.sharedMesh.GetBlendShapeName(
                        _mouthBlendShapeIndex
                    ) + " blendshape";
                }

                return "no mouth animation target";
            }
        }

        public void Attach(
            Vrm10Instance avatar,
            AudioSource audioSource
        )
        {
            Attach(
                avatar != null ? avatar.gameObject : null,
                avatar,
                audioSource
            );
        }

        public void Attach(
            GameObject avatarRoot,
            Vrm10Instance vrmAvatar,
            AudioSource audioSource
        )
        {
            _avatarRoot = avatarRoot;
            _avatar = vrmAvatar;
            _audioSource = audioSource;
            _weight = 0f;

            ResolveMouthTargets();
            SetVrmWeight(0f);
            SetDirectBlendShapeWeight(0f);
            SetMouthTransformWeight(0f);
        }

        public void Detach()
        {
            SetVrmWeight(0f);
            SetDirectBlendShapeWeight(0f);
            SetMouthTransformWeight(0f);

            _avatarRoot = null;
            _avatar = null;
            _audioSource = null;
            _mouthRenderer = null;
            _mouthTransform = null;
            _mouthBlendShapeIndex = -1;
            _hasVrmMouthExpression = false;
            _genesisMouthTransform = false;
            _weight = 0f;
        }

        private void ResolveMouthTargets()
        {
            _mouthRenderer = null;
            _mouthTransform = null;
            _mouthBlendShapeIndex = -1;
            _hasVrmMouthExpression = false;
            _genesisMouthTransform = false;

            if (_avatarRoot == null)
            {
                return;
            }

            if (_avatar?.Runtime?.Expression != null)
            {
                _hasVrmMouthExpression =
                    _avatar.Runtime.Expression
                        .GetWeights()
                        .ContainsKey(MouthKey);
            }

            foreach (
                Transform candidate in
                _avatarRoot.GetComponentsInChildren<Transform>(true)
            )
            {
                for (
                    int index = 0;
                    index < MouthTransformNames.Length;
                    index++
                )
                {
                    if (
                        string.Equals(
                            candidate.name,
                            MouthTransformNames[index],
                            StringComparison.Ordinal
                        )
                    )
                    {
                        _mouthTransform = candidate;
                        _mouthRestScale = candidate.localScale;
                        _mouthRestPosition = candidate.localPosition;
                        _genesisMouthTransform =
                            string.Equals(
                                candidate.name,
                                "MouthVisual",
                                StringComparison.Ordinal
                            );
                        break;
                    }
                }

                if (_mouthTransform != null)
                {
                    break;
                }
            }

            foreach (
                SkinnedMeshRenderer renderer in
                _avatarRoot.GetComponentsInChildren<SkinnedMeshRenderer>(true)
            )
            {
                Mesh mesh = renderer.sharedMesh;
                if (mesh == null)
                {
                    continue;
                }

                for (
                    int index = 0;
                    index < mesh.blendShapeCount;
                    index++
                )
                {
                    string name = mesh.GetBlendShapeName(index);
                    if (IsMouthBlendShape(name))
                    {
                        _mouthRenderer = renderer;
                        _mouthBlendShapeIndex = index;
                        return;
                    }
                }
            }
        }

        private static bool IsMouthBlendShape(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
            {
                return false;
            }

            for (
                int index = 0;
                index < MouthBlendShapeNames.Length;
                index++
            )
            {
                string candidate = MouthBlendShapeNames[index];
                if (
                    string.Equals(
                        name,
                        candidate,
                        StringComparison.OrdinalIgnoreCase
                    ) ||
                    name.EndsWith(
                        "." + candidate,
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    return true;
                }
            }

            return false;
        }

        private void Update()
        {
            float target = MeasureCurrentSpeechAmplitude();

            float attack = target > _weight ? 24f : 14f;
            float blend =
                1f -
                Mathf.Exp(
                    -attack * Time.unscaledDeltaTime
                );
            _weight = Mathf.Lerp(_weight, target, blend);

            SetVrmWeight(_weight);
        }

        private void LateUpdate()
        {
            SetDirectBlendShapeWeight(_weight);
            SetMouthTransformWeight(_weight);
        }

        private float MeasureCurrentSpeechAmplitude()
        {
            if (
                _audioSource == null ||
                !_audioSource.isPlaying ||
                _audioSource.clip == null
            )
            {
                return 0f;
            }

            AudioClip clip = _audioSource.clip;
            int channels = Mathf.Max(1, clip.channels);
            int framesInWindow =
                Mathf.Max(1, SampleCount / channels);
            int latestStart =
                Mathf.Max(0, clip.samples - framesInWindow);
            int offset = Mathf.Clamp(
                _audioSource.timeSamples,
                0,
                latestStart
            );

            Array.Clear(
                _samples,
                0,
                _samples.Length
            );
            if (!clip.GetData(_samples, offset))
            {
                return 0f;
            }

            float energy = 0f;
            for (
                int index = 0;
                index < _samples.Length;
                index++
            )
            {
                float sample = _samples[index];
                energy += sample * sample;
            }

            float rms = Mathf.Sqrt(
                energy / _samples.Length
            );
            float normalized = Mathf.Clamp01(
                (rms - 0.0015f) * 38f
            );
            return Mathf.Pow(normalized, 0.65f);
        }

        private void SetVrmWeight(float value)
        {
            if (
                !_hasVrmMouthExpression ||
                _avatar?.Runtime?.Expression == null
            )
            {
                return;
            }

            _avatar.Runtime.Expression.SetWeight(
                MouthKey,
                Mathf.Clamp01(value)
            );
        }

        private void SetDirectBlendShapeWeight(float value)
        {
            if (
                _mouthRenderer == null ||
                _mouthBlendShapeIndex < 0
            )
            {
                return;
            }

            _mouthRenderer.SetBlendShapeWeight(
                _mouthBlendShapeIndex,
                Mathf.Clamp01(value) * 100f
            );
        }

        private void SetMouthTransformWeight(float value)
        {
            if (_mouthTransform == null)
            {
                return;
            }

            float weight = Mathf.Clamp01(value);

            if (_genesisMouthTransform)
            {
                _mouthTransform.localScale = new Vector3(
                    _mouthRestScale.x *
                        (1f - 0.12f * weight),
                    _mouthRestScale.y *
                        (1f + 5.5f * weight),
                    _mouthRestScale.z
                );
                _mouthTransform.localPosition =
                    _mouthRestPosition +
                    new Vector3(
                        0f,
                        -0.006f * weight,
                        0f
                    );
                return;
            }

            _mouthTransform.localScale = new Vector3(
                _mouthRestScale.x *
                    (1f - 0.06f * weight),
                _mouthRestScale.y *
                    (1f + 0.45f * weight),
                _mouthRestScale.z
            );
        }

        private void OnDisable()
        {
            SetVrmWeight(0f);
            SetDirectBlendShapeWeight(0f);
            SetMouthTransformWeight(0f);
        }

        private void OnDestroy()
        {
            SetVrmWeight(0f);
            SetDirectBlendShapeWeight(0f);
            SetMouthTransformWeight(0f);
        }
    }
}
