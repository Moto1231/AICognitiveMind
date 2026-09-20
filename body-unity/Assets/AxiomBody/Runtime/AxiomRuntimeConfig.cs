using System;

namespace Axiom.Body
{
    public static class AxiomRuntimeConfig
    {
        public static string MindBaseUrl =>
            NormalizeBaseUrl(Environment.GetEnvironmentVariable("AXIOM_MIND_URL")
                ?? "http://127.0.0.1:8000");

        public static string MindUsername =>
            Environment.GetEnvironmentVariable("AXIOM_MIND_USERNAME") ?? "mind";

        public static string MindPassword =>
            Environment.GetEnvironmentVariable("AXIOM_MIND_PASSWORD") ?? string.Empty;

        private static string NormalizeBaseUrl(string value)
        {
            return value.Trim().TrimEnd('/');
        }
    }
}
