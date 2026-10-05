import json
import struct
import unittest
from pathlib import Path

from aicognitive_mind.body.genesis_avatar import build_genesis_vrm


def parse_glb_json(payload: bytes) -> dict:
    magic, version, total_length = struct.unpack("<4sII", payload[:12])
    if magic != b"glTF" or version != 2 or total_length != len(payload):
        raise AssertionError("Genesis is not a valid glTF 2.0 binary")
    json_length, chunk_type = struct.unpack("<I4s", payload[12:20])
    if chunk_type != b"JSON":
        raise AssertionError("Genesis first GLB chunk is not JSON")
    return json.loads(payload[20 : 20 + json_length].decode("utf-8").rstrip())


class AvatarCustomizationV01Tests(unittest.TestCase):
    def test_genesis_exposes_independent_customizable_materials(self) -> None:
        model = parse_glb_json(build_genesis_vrm())
        material_names = {material["name"] for material in model["materials"]}

        self.assertTrue(
            {
                "Skin",
                "Hair",
                "Shirt",
                "Pants",
                "Eyes",
                "Shoes",
                "Mouth",
            }.issubset(material_names)
        )
        self.assertNotIn("Dark", material_names)

    def test_genesis_v03_is_smooth_and_preserves_editor_contract(self) -> None:
        model = parse_glb_json(build_genesis_vrm())

        vrm_meta = model["extensions"]["VRMC_vrm"]["meta"]
        self.assertEqual(vrm_meta["version"], "0.3")
        self.assertIn("V0.3", model["asset"]["generator"])

        mesh_names = {mesh["name"] for mesh in model["meshes"]}
        self.assertNotIn("SkinCube", mesh_names)
        self.assertNotIn("ShirtCube", mesh_names)
        self.assertNotIn("PantsCube", mesh_names)
        self.assertTrue(
            {
                "SkinSmooth",
                "ShirtSmooth",
                "PantsSmooth",
                "HairCap",
                "EyeIris",
                "ShoeSmooth",
            }.issubset(mesh_names)
        )

        # The old cube primitive had only 24 vertices. V0.3's rounded surface
        # uses hundreds of smoothly normaled vertices.
        vec3_counts = [
            accessor["count"]
            for accessor in model["accessors"]
            if accessor["type"] == "VEC3"
        ]
        self.assertGreaterEqual(max(vec3_counts), 400)

        node_names = {node["name"] for node in model["nodes"]}
        self.assertTrue(
            {
                "HeadVisual",
                "HairVisual",
                "LeftEyeVisual",
                "RightEyeVisual",
                "MouthVisual",
                "PelvisVisual",
                "TorsoLowerVisual",
                "TorsoUpperVisual",
                "LeftUpperArmVisual",
                "RightUpperArmVisual",
                "LeftUpperLegVisual",
                "RightUpperLegVisual",
            }.issubset(node_names)
        )
        self.assertTrue(
            {
                "NoseVisual",
                "LeftEarVisual",
                "RightEarVisual",
                "LeftBrowVisual",
                "RightBrowVisual",
                "LeftEyeWhite",
                "RightEyeWhite",
                "LeftIrisVisual",
                "RightIrisVisual",
            }.issubset(node_names)
        )

    def test_avatar_customizer_exports_runtime_editing_functions(self) -> None:
        source = Path("src/aicognitive_mind/static/avatar_customizer.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("export class AvatarCustomizer", source)
        self.assertIn("setMaterialColor(", source)
        self.assertIn("setNodeScale(", source)
        self.assertIn("setNodePositionX(", source)
        self.assertIn("loadSavedAvatarAppearance", source)
        self.assertIn("saveAvatarAppearance", source)
        self.assertIn("clearSavedAvatarAppearance", source)
        self.assertIn("DEFAULT_AVATAR_APPEARANCE", source)

    def test_avatar_editor_surface_is_removed(self) -> None:
        live_markup = Path("src/aicognitive_mind/static/live_body.html").read_text(
            encoding="utf-8"
        )
        portal_markup = Path("src/aicognitive_mind/static/index.html").read_text(
            encoding="utf-8"
        )
        api_source = Path("src/aicognitive_mind/api.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn('href="/body/avatar"', live_markup)
        self.assertNotIn("Avatar Editor", live_markup)
        self.assertNotIn('href="/body/avatar"', portal_markup)
        self.assertNotIn("Avatar Editor", portal_markup)
        self.assertNotIn('"/body/avatar"', api_source)
        self.assertFalse(Path("src/aicognitive_mind/static/avatar_editor.html").exists())

    def test_live_body_has_no_avatar_renderer(self) -> None:
        markup = Path("src/aicognitive_mind/static/live_body.html").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("loadSavedAvatarAppearance", markup)
        self.assertNotIn("AvatarCustomizer", markup)
        self.assertNotIn("@pixiv/three-vrm", markup)
        self.assertNotIn("avatarCustomizer", markup)


if __name__ == "__main__":
    unittest.main()
