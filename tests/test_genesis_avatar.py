import json
import struct
import unittest

from aicognitive_mind.api import app
from aicognitive_mind.body.genesis_avatar import build_genesis_vrm


REQUIRED_BONES = {
    "hips",
    "spine",
    "head",
    "leftUpperArm",
    "leftLowerArm",
    "leftHand",
    "rightUpperArm",
    "rightLowerArm",
    "rightHand",
    "leftUpperLeg",
    "leftLowerLeg",
    "leftFoot",
    "rightUpperLeg",
    "rightLowerLeg",
    "rightFoot",
}


def parse_glb_json(payload: bytes) -> dict:
    magic, version, total_length = struct.unpack("<4sII", payload[:12])
    if magic != b"glTF":
        raise AssertionError("Genesis is not a GLB/VRM payload")
    if version != 2:
        raise AssertionError("Genesis does not use glTF 2.0")
    if total_length != len(payload):
        raise AssertionError("Genesis GLB length header is incorrect")

    json_length, chunk_type = struct.unpack("<I4s", payload[12:20])
    if chunk_type != b"JSON":
        raise AssertionError("Genesis first GLB chunk is not JSON")
    return json.loads(payload[20 : 20 + json_length].decode("utf-8").rstrip())


class GenesisAvatarV01Tests(unittest.TestCase):
    def test_genesis_is_owned_vrm_1_0_with_required_humanoid_bones(self) -> None:
        payload = build_genesis_vrm()
        model = parse_glb_json(payload)

        self.assertEqual(model["asset"]["version"], "2.0")
        self.assertIn("VRMC_vrm", model["extensionsUsed"])

        vrm = model["extensions"]["VRMC_vrm"]
        self.assertEqual(vrm["specVersion"], "1.0")
        self.assertEqual(vrm["meta"]["name"], "Genesis")
        self.assertEqual(vrm["meta"]["authors"], ["AICognitiveMind"])
        self.assertEqual(vrm["meta"]["modification"], "allowModificationRedistribution")
        self.assertTrue(vrm["meta"]["allowRedistribution"])

        bones = set(vrm["humanoid"]["humanBones"])
        self.assertTrue(REQUIRED_BONES.issubset(bones))

    def test_genesis_has_a_happy_expression_morph_target(self) -> None:
        model = parse_glb_json(build_genesis_vrm())
        happy = model["extensions"]["VRMC_vrm"]["expressions"]["preset"]["happy"]

        self.assertEqual(len(happy["morphTargetBinds"]), 1)
        bind = happy["morphTargetBinds"][0]
        self.assertEqual(bind["index"], 0)
        self.assertEqual(bind["weight"], 1.0)

        node = model["nodes"][bind["node"]]
        mesh = model["meshes"][node["mesh"]]
        self.assertEqual(mesh["extras"]["targetNames"], ["happySmile", "aaOpen"])
        self.assertEqual(len(mesh["primitives"][0]["targets"]), 2)

        aa = model["extensions"]["VRMC_vrm"]["expressions"]["preset"]["aa"]
        self.assertEqual(len(aa["morphTargetBinds"]), 1)
        aa_bind = aa["morphTargetBinds"][0]
        self.assertEqual(aa_bind["node"], bind["node"])
        self.assertEqual(aa_bind["index"], 1)
        self.assertEqual(aa_bind["weight"], 1.0)

    def test_body_exposes_default_genesis_avatar_route(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/v1/body/face/avatar", paths)


if __name__ == "__main__":
    unittest.main()
