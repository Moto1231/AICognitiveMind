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

        private readonly float[] _samples = new float[SampleCount];
        private Vrm10Instance _avatar;
        private AudioSource _audioSource;
        private SkinnedMeshRenderer _mouthRenderer;
        private int _mouthBlendShapeIndex = -1;
        private bool _hasVrmMouthExpression;
        private float _weight;

        public bool HasMouthTarget =>
            _hasVrmMouthExpression || _mouthBlendShapeIndex >= 0;

        public string TargetDescription
        {
            get
            {
                if (_hasVrmMouthExpression && _mouthBlendShapeIndex >= 0)
                {
                    return "VRM aa + aaOpen blendshape";
                }

                if (_hasVrmMouthExpression)
                {
                    return "VRM aa expression";
                }

                if (_mouthBlendShapeIndex >= 0)
                {
                    return "aaOpen blendshape";
                }

                return "no mouth animation target";
            }
        }

        public void Attach(Vrm10Instance avatar, AudioSource audioSource)
        {
            _avatar = avatar;
            _audioSource = audioSource;
            _weight = 0f;

            ResolveMouthTargets();
            SetVrmWeight(0f);
            SetDirectBlendShapeWeight(0f);
        }

        public void Detach()
        {
            SetVrmWeight(0f);
            SetDirectBlendShapeWeight(0f);

            _avatar = null;
            _audioSource = null;
            _mouthRenderer = null;
            _mouthBlendShapeIndex = -1;
            _hasVrmMouthExpression = false;
            _weight = 0f;
        }

        private void ResolveMouthTargets()
        {
            _mouthRenderer = null;
            _mouthBlendShapeIndex = -1;
            _hasVrmMouthExpression = false;

            if (_avatar == null)
            {
                return;
            }

            if (_avatar.Runtime?.Expression != null)
            {
                _hasVrmMouthExpression =
                    _avatar.Runtime.Expression.GetWeights().ContainsKey(MouthKey);
            }

            foreach (
                SkinnedMeshRenderer renderer in
                _avatar.GetComponentsInChildren<SkinnedMeshRenderer>(true)
            )
            {
                Mesh mesh = renderer.sharedMesh;
                if (mesh == null)
                {
                    continue;
                }

                for (int index = 0; index < mesh.blendShapeCount; index++)
                {
                    string name = mesh.GetBlendShapeName(index);
                    if (
                        string.Equals(
                            name,
                            "aaOpen",
                            StringComparison.OrdinalIgnoreCase
                        ) ||
                        name.EndsWith(
                            ".aaOpen",
                            StringComparison.OrdinalIgnoreCase
                        )
                    )
                    {
                        _mouthRenderer = renderer;
                        _mouthBlendShapeIndex = index;
                        return;
                    }
                }
            }
        }

        private void Update()
        {
            float target = MeasureCurrentSpeechAmplitude();

            float attack = target > _weight ? 24f : 14f;
            float blend = 1f - Mathf.Exp(-attack * Time.unscaledDeltaTime);
            _weight = Mathf.Lerp(_weight, target, blend);

            // Feed UniVRM before its LateUpdate applies expression weights.
            SetVrmWeight(_weight);
        }

        private void LateUpdate()
        {
            // UniVRM processes at execution order 11000. This component runs at
            // 12000, so the raw blendshape fallback is applied afterward and
            // cannot be overwritten during the same frame.
            SetDirectBlendShapeWeight(_weight);
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
            int framesInWindow = Mathf.Max(1, SampleCount / channels);
            int latestStart = Mathf.Max(0, clip.samples - framesInWindow);
            int offset = Mathf.Clamp(_audioSource.timeSamples, 0, latestStart);

            Array.Clear(_samples, 0, _samples.Length);
            if (!clip.GetData(_samples, offset))
            {
                return 0f;
            }

            float energy = 0f;
            for (int index = 0; index < _samples.Length; index++)
            {
                float sample = _samples[index];
                energy += sample * sample;
            }

            float rms = Mathf.Sqrt(energy / _samples.Length);

            // Windows SAPI speech WAVs generally have conservative levels.
            // Lift normal spoken RMS into a clear but still graded mouth range.
            float normalized = Mathf.Clamp01((rms - 0.0015f) * 38f);
            return Mathf.Pow(normalized, 0.65f);
        }

        private void SetVrmWeight(float value)
        {
            if (!_hasVrmMouthExpression || _avatar?.Runtime?.Expression == null)
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
            if (_mouthRenderer == null || _mouthBlendShapeIndex < 0)
            {
                return;
            }

            _mouthRenderer.SetBlendShapeWeight(
                _mouthBlendShapeIndex,
                Mathf.Clamp01(value) * 100f
            );
        }

        private void OnDisable()
        {
            SetVrmWeight(0f);
            SetDirectBlendShapeWeight(0f);
        }

        private void OnDestroy()
        {
            SetVrmWeight(0f);
            SetDirectBlendShapeWeight(0f);
        }
    }
}
