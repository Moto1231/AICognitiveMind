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

    def test_live_body_exposes_avatar_editor_controls(self) -> None:
        markup = Path("src/aicognitive_mind/static/live_body.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('id="avatarEditorTitle"', markup)
        self.assertIn('data-avatar-key="skinColor"', markup)
        self.assertIn('data-avatar-key="hairColor"', markup)
        self.assertIn('data-avatar-key="headSize"', markup)
        self.assertIn('data-avatar-key="eyeSpacing"', markup)
        self.assertIn('data-avatar-key="torsoWidth"', markup)
        self.assertIn('data-avatar-key="shoulderWidth"', markup)
        self.assertIn('data-avatar-key="armThickness"', markup)
        self.assertIn('data-avatar-key="legThickness"', markup)
        self.assertIn('id="saveAvatarAppearance"', markup)
        self.assertIn('id="resetAvatarAppearance"', markup)
        self.assertIn('from "/static/avatar_customizer.js"', markup)


if __name__ == "__main__":
    unittest.main()
