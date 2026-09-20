import json
import unittest
from pathlib import Path


class UnityBodyScaffoldTests(unittest.TestCase):
    def test_unity_body_packages_include_vrm_1_runtime(self) -> None:
        manifest = json.loads(
            Path("body-unity/Packages/manifest.json").read_text(encoding="utf-8")
        )
        dependencies = manifest["dependencies"]

        self.assertIn("com.vrmc.gltf", dependencies)
        self.assertIn("com.vrmc.vrm", dependencies)
        self.assertIn("UniVRM.git", dependencies["com.vrmc.vrm"])
        self.assertIn("path=/Packages/VRM10", dependencies["com.vrmc.vrm"])

    def test_unity_body_talks_to_mind_not_storage(self) -> None:
        client = Path(
            "body-unity/Assets/AxiomBody/Runtime/MindApiClient.cs"
        ).read_text(encoding="utf-8")
        config = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomRuntimeConfig.cs"
        ).read_text(encoding="utf-8")
        combined = client + config

        self.assertIn("/health", client)
        self.assertIn("/v1/body/face/avatar", client)
        self.assertIn("/v1/mind/body/interact", client)
        self.assertIn("AXIOM_MIND_URL", config)
        self.assertNotIn("SURREALDB_", combined)
        self.assertNotIn("MONGODB_", combined)

    def test_unity_body_runtime_references_required_univrm_assemblies(self) -> None:
        asmdef = json.loads(
            Path(
                "body-unity/Assets/AxiomBody/Runtime/Axiom.Body.Runtime.asmdef"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(asmdef["name"], "Axiom.Body.Runtime")
        self.assertIn("VRM10", asmdef["references"])
        self.assertIn("UniGLTF", asmdef["references"])
        self.assertIn("UniGLTF.Utils", asmdef["references"])

    def test_unity_body_runtime_loads_vrm_and_persists_across_scenes(self) -> None:
        loader = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomAvatarLoader.cs"
        ).read_text(encoding="utf-8")
        bootstrap = Path(
            "body-unity/Assets/AxiomBody/Runtime/AxiomBodyBootstrap.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("Vrm10.LoadBytesAsync", loader)
        self.assertIn("DontDestroyOnLoad", bootstrap)
        self.assertIn("RuntimeInitializeOnLoadMethod", bootstrap)
        self.assertIn("FindAnyObjectByType", bootstrap)
        self.assertNotIn("FindFirstObjectByType", bootstrap)


if __name__ == "__main__":
    unittest.main()
