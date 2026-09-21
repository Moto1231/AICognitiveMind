// Copyright (c) 2026 William Enright. All rights reserved.
// Use, reproduction, modification, distribution, or commercial exploitation
// of this file is prohibited without prior written permission from the
// copyright holder.

using UnityEngine;

namespace Axiom.Body
{
    [DefaultExecutionOrder(12500)]
    public sealed class AxiomBodyMotionRuntime : MonoBehaviour
    {
        private GameObject _avatarRoot;
        private AxiomMouthRuntime _mouth;
        private Transform _head;
        private Vector3 _basePosition;
        private Quaternion _baseRotation;
        private Quaternion _baseHeadRotation;
        private float _phaseOffset;

        public void Attach(
            GameObject avatarRoot,
            AxiomMouthRuntime mouth
        )
        {
            RestoreBasePose();

            _avatarRoot = avatarRoot;
            _mouth = mouth;
            _head = FindHead(avatarRoot);

            if (_avatarRoot == null)
            {
                return;
            }

            _basePosition = _avatarRoot.transform.localPosition;
            _baseRotation = _avatarRoot.transform.localRotation;
            _baseHeadRotation = _head != null
                ? _head.localRotation
                : Quaternion.identity;

            // Different bodies should not all move on exactly the same phase.
            _phaseOffset = Mathf.Abs(
                (_avatarRoot.name ?? string.Empty).GetHashCode() % 997
            ) / 97f;
        }

        public void Detach()
        {
            RestoreBasePose();
            _avatarRoot = null;
            _mouth = null;
            _head = null;
        }

        private void LateUpdate()
        {
            if (_avatarRoot == null)
            {
                return;
            }

            float t = Time.unscaledTime + _phaseOffset;
            bool speaking = _mouth != null && _mouth.IsSpeaking;

            float breath = Mathf.Sin(t * 1.65f);
            float sway = Mathf.Sin(t * 0.58f);
            float counterSway = Mathf.Sin((t * 0.83f) + 1.2f);

            float vertical = breath * (speaking ? 0.007f : 0.004f);
            float lateral = sway * (speaking ? 0.006f : 0.003f);
            float yaw = sway * (speaking ? 1.8f : 0.8f);
            float roll = counterSway * (speaking ? 0.8f : 0.35f);

            _avatarRoot.transform.localPosition =
                _basePosition + new Vector3(lateral, vertical, 0f);
            _avatarRoot.transform.localRotation =
                _baseRotation *
                Quaternion.Euler(0f, yaw, roll);

            if (_head != null)
            {
                float headPitch =
                    Mathf.Sin((t * 0.71f) + 0.4f) *
                    (speaking ? 2.0f : 0.8f);
                float headYaw =
                    Mathf.Sin((t * 0.47f) + 2.0f) *
                    (speaking ? 2.8f : 1.2f);

                _head.localRotation =
                    _baseHeadRotation *
                    Quaternion.Euler(
                        headPitch,
                        headYaw,
                        0f
                    );
            }
        }

        private void RestoreBasePose()
        {
            if (_avatarRoot != null)
            {
                _avatarRoot.transform.localPosition = _basePosition;
                _avatarRoot.transform.localRotation = _baseRotation;
            }

            if (_head != null)
            {
                _head.localRotation = _baseHeadRotation;
            }
        }

        private static Transform FindHead(GameObject avatarRoot)
        {
            if (avatarRoot == null)
            {
                return null;
            }

            Animator animator =
                avatarRoot.GetComponentInChildren<Animator>(true);
            if (animator != null && animator.isHuman)
            {
                Transform humanoidHead =
                    animator.GetBoneTransform(HumanBodyBones.Head);
                if (humanoidHead != null)
                {
                    return humanoidHead;
                }
            }

            Transform[] transforms =
                avatarRoot.GetComponentsInChildren<Transform>(true);
            foreach (Transform candidate in transforms)
            {
                if (
                    candidate != null &&
                    string.Equals(
                        candidate.name,
                        "Head",
                        System.StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    return candidate;
                }
            }

            return null;
        }

        private void OnDisable()
        {
            RestoreBasePose();
        }

        private void OnDestroy()
        {
            RestoreBasePose();
        }
    }
}
