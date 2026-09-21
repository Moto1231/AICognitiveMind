// Copyright (c) 2026 William Enright. All rights reserved.
// Use, reproduction, modification, distribution, or commercial exploitation
// of this file is prohibited without prior written permission from the
// copyright holder.

using System;
using UnityEngine;

namespace Axiom.Body
{
    public enum BodyModelPolicy
    {
        CognitiveOnly,
        FullBodyModel
    }

    public static class AxiomRuntimeConfig
    {
        private const string MindUrlKey = "axiom.mind.url";
        private const string MindUsernameKey = "axiom.mind.username";
        private const string BodyModelPolicyKey = "axiom.body.model-policy";

        public static string MindBaseUrl
        {
            get
            {
                string environment = Environment.GetEnvironmentVariable("AXIOM_MIND_URL");
                if (!string.IsNullOrWhiteSpace(environment))
                {
                    return NormalizeBaseUrl(environment);
                }

                string saved = PlayerPrefs.GetString(MindUrlKey, string.Empty);
                return NormalizeBaseUrl(
                    string.IsNullOrWhiteSpace(saved)
                        ? "http://127.0.0.1:8000"
                        : saved
                );
            }
        }

        public static string MindUsername
        {
            get
            {
                string environment = Environment.GetEnvironmentVariable(
                    "AXIOM_MIND_USERNAME"
                );
                if (!string.IsNullOrWhiteSpace(environment))
                {
                    return environment.Trim();
                }

                string saved = PlayerPrefs.GetString(MindUsernameKey, string.Empty);
                return string.IsNullOrWhiteSpace(saved) ? "mind" : saved.Trim();
            }
        }

        public static string MindPassword =>
            Environment.GetEnvironmentVariable("AXIOM_MIND_PASSWORD") ?? string.Empty;

        public static BodyModelPolicy ModelPolicy
        {
            get
            {
                string environment = Environment.GetEnvironmentVariable(
                    "AXIOM_BODY_MODEL_POLICY"
                );
                if (TryParseBodyModelPolicy(environment, out BodyModelPolicy policy))
                {
                    return policy;
                }

                string saved = PlayerPrefs.GetString(
                    BodyModelPolicyKey,
                    string.Empty
                );
                return TryParseBodyModelPolicy(saved, out policy)
                    ? policy
                    : BodyModelPolicy.CognitiveOnly;
            }
        }

        public static void SaveConnection(string baseUrl, string username)
        {
            PlayerPrefs.SetString(MindUrlKey, NormalizeBaseUrl(baseUrl));
            PlayerPrefs.SetString(
                MindUsernameKey,
                string.IsNullOrWhiteSpace(username) ? "mind" : username.Trim()
            );
            PlayerPrefs.Save();
        }

        public static void SaveBodyModelPolicy(BodyModelPolicy policy)
        {
            PlayerPrefs.SetString(
                BodyModelPolicyKey,
                policy == BodyModelPolicy.FullBodyModel
                    ? "full-body"
                    : "cognitive-only"
            );
            PlayerPrefs.Save();
        }

        public static string NormalizeBaseUrl(string value)
        {
            return (value ?? string.Empty).Trim().TrimEnd('/');
        }

        private static bool TryParseBodyModelPolicy(
            string value,
            out BodyModelPolicy policy
        )
        {
            string normalized = (value ?? string.Empty)
                .Trim()
                .ToLowerInvariant()
                .Replace("_", "-");

            if (
                normalized == "full-body" ||
                normalized == "full" ||
                normalized == "model-all"
            )
            {
                policy = BodyModelPolicy.FullBodyModel;
                return true;
            }

            if (
                normalized == "cognitive-only" ||
                normalized == "cognitive" ||
                normalized == "budgeted"
            )
            {
                policy = BodyModelPolicy.CognitiveOnly;
                return true;
            }

            policy = BodyModelPolicy.CognitiveOnly;
            return false;
        }
    }
}
