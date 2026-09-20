using UniVRM10;
using UnityEngine;

namespace Axiom.Body
{
    public sealed class AxiomLipSync : MonoBehaviour
    {
        private const int SampleCount = 256;
        private static readonly ExpressionKey MouthKey =
            ExpressionKey.CreateFromPreset(ExpressionPreset.aa);

        private readonly float[] _samples = new float[SampleCount];
        private Vrm10Instance _avatar;
        private AudioSource _audioSource;
        private float _weight;

        public void Attach(Vrm10Instance avatar, AudioSource audioSource)
        {
            _avatar = avatar;
            _audioSource = audioSource;
            _weight = 0f;
            ApplyWeight(0f);
        }

        public void Detach()
        {
            ApplyWeight(0f);
            _avatar = null;
            _audioSource = null;
            _weight = 0f;
        }

        private void Update()
        {
            float target = 0f;

            if (
                _avatar != null &&
                _avatar.Runtime != null &&
                _audioSource != null &&
                _audioSource.isPlaying
            )
            {
                _audioSource.GetOutputData(_samples, 0);

                float energy = 0f;
                for (int index = 0; index < _samples.Length; index++)
                {
                    float sample = _samples[index];
                    energy += sample * sample;
                }

                float rms = Mathf.Sqrt(energy / _samples.Length);
                target = Mathf.Clamp01((rms - 0.004f) * 24f);
                target = Mathf.Pow(target, 0.7f);
            }

            float attack = target > _weight ? 22f : 13f;
            float blend = 1f - Mathf.Exp(-attack * Time.unscaledDeltaTime);
            _weight = Mathf.Lerp(_weight, target, blend);

            ApplyWeight(_weight);
        }

        private void ApplyWeight(float value)
        {
            if (_avatar?.Runtime?.Expression == null)
            {
                return;
            }

            _avatar.Runtime.Expression.SetWeight(
                MouthKey,
                Mathf.Clamp01(value)
            );
        }

        private void OnDisable()
        {
            ApplyWeight(0f);
        }

        private void OnDestroy()
        {
            ApplyWeight(0f);
        }
    }
}
