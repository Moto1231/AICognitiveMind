using System;
using UnityEngine;

namespace Axiom.Body
{
    public static class AxiomRuntimeConfig
    {
        private const string MindUrlKey = "axiom.mind.url";
        private const string MindUsernameKey = "axiom.mind.username";

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

        public static void SaveConnection(string baseUrl, string username)
        {
            PlayerPrefs.SetString(MindUrlKey, NormalizeBaseUrl(baseUrl));
            PlayerPrefs.SetString(
                MindUsernameKey,
                string.IsNullOrWhiteSpace(username) ? "mind" : username.Trim()
            );
            PlayerPrefs.Save();
        }

        public static string NormalizeBaseUrl(string value)
        {
            return (value ?? string.Empty).Trim().TrimEnd('/');
        }
    }
}
