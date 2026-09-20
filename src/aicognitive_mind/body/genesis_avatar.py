from __future__ import annotations

import json
import struct
def build_genesis_vrm() -> bytes:
    buffer = bytearray()
    buffer_views: list[dict] = []
    accessors: list[dict] = []

    def align4() -> None:
        while len(buffer) % 4:
            buffer.append(0)

    def add_data(raw: bytes, target: int | None = None) -> int:
        align4()
        offset = len(buffer)
        buffer.extend(raw)
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(raw)}
        if target is not None:
            view["target"] = target
        buffer_views.append(view)
        return len(buffer_views) - 1

    def add_accessor(
        values: list[float] | list[int],
        component_type: int,
        value_type: str,
        count: int,
        target: int | None = None,
        minimum: list[float] | list[int] | None = None,
        maximum: list[float] | list[int] | None = None,
    ) -> int:
        fmt = {5126: "f", 5123: "H", 5125: "I"}[component_type]
        raw = struct.pack("<" + fmt * len(values), *values)
        accessor = {
            "bufferView": add_data(raw, target),
            "componentType": component_type,
            "count": count,
            "type": value_type,
        }
        if minimum is not None:
            accessor["min"] = minimum
        if maximum is not None:
            accessor["max"] = maximum
        accessors.append(accessor)
        return len(accessors) - 1

    faces = [
        ((0, 0, 1), [(-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]),
        ((0, 0, -1), [(0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5)]),
        ((1, 0, 0), [(0.5, -0.5, 0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5)]),
        ((-1, 0, 0), [(-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5)]),
        ((0, 1, 0), [(-0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5)]),
        ((0, -1, 0), [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5)]),
    ]
    positions: list[float] = []
    normals: list[float] = []
    indices: list[int] = []
    for normal, corners in faces:
        base = len(positions) // 3
        for point in corners:
            positions.extend(point)
            normals.extend(normal)
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    position_accessor = add_accessor(
        positions, 5126, "VEC3", 24, 34962, [-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]
    )
    normal_accessor = add_accessor(normals, 5126, "VEC3", 24, 34962)
    index_accessor = add_accessor(indices, 5123, "SCALAR", 36, 34963, [0], [23])

    xs = [-0.14, -0.07, 0.0, 0.07, 0.14]
    mouth_positions: list[float] = []
    mouth_normals: list[float] = []
    for y_offset in (0.008, -0.008):
        for x in xs:
            mouth_positions.extend([x, y_offset, 0.0])
            mouth_normals.extend([0.0, 0.0, 1.0])

    mouth_indices: list[int] = []
    for index in range(4):
        a, b, c, d = index, index + 1, 5 + index + 1, 5 + index
        mouth_indices.extend([a, d, c, a, c, b])

    mouth_delta: list[float] = []
    smile = [0.04, 0.018, -0.006, 0.018, 0.04]
    for _ in range(2):
        for delta_y in smile:
            mouth_delta.extend([0.0, delta_y, 0.0])

    mouth_position_accessor = add_accessor(
        mouth_positions, 5126, "VEC3", 10, 34962, [-0.14, -0.008, 0.0], [0.14, 0.008, 0.0]
    )
    mouth_normal_accessor = add_accessor(mouth_normals, 5126, "VEC3", 10, 34962)
    mouth_index_accessor = add_accessor(mouth_indices, 5123, "SCALAR", 24, 34963, [0], [9])
    mouth_target_accessor = add_accessor(
        mouth_delta, 5126, "VEC3", 10, 34962, [0.0, -0.006, 0.0], [0.0, 0.04, 0.0]
    )

    materials = [
        {"name": "Skin", "pbrMetallicRoughness": {"baseColorFactor": [0.72, 0.52, 0.40, 1], "metallicFactor": 0, "roughnessFactor": 0.85}},
        {"name": "Shirt", "pbrMetallicRoughness": {"baseColorFactor": [0.18, 0.26, 0.34, 1], "metallicFactor": 0, "roughnessFactor": 0.90}},
        {"name": "Pants", "pbrMetallicRoughness": {"baseColorFactor": [0.10, 0.12, 0.16, 1], "metallicFactor": 0, "roughnessFactor": 0.95}},
        {"name": "Hair", "pbrMetallicRoughness": {"baseColorFactor": [0.035, 0.04, 0.05, 1], "metallicFactor": 0, "roughnessFactor": 0.70}},
        {"name": "Eyes", "pbrMetallicRoughness": {"baseColorFactor": [0.035, 0.04, 0.05, 1], "metallicFactor": 0, "roughnessFactor": 0.70}},
        {"name": "Shoes", "pbrMetallicRoughness": {"baseColorFactor": [0.035, 0.04, 0.05, 1], "metallicFactor": 0, "roughnessFactor": 0.80}},
        {"name": "Mouth", "pbrMetallicRoughness": {"baseColorFactor": [0.36, 0.06, 0.07, 1], "metallicFactor": 0, "roughnessFactor": 0.80}},
    ]

    meshes = []
    for name, material in (
        ("SkinCube", 0),
        ("ShirtCube", 1),
        ("PantsCube", 2),
        ("HairCube", 3),
        ("EyeCube", 4),
        ("ShoeCube", 5),
    ):
        meshes.append(
            {
                "name": name,
                "primitives": [
                    {
                        "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor},
                        "indices": index_accessor,
                        "material": material,
                    }
                ],
            }
        )

    mouth_mesh = len(meshes)
    meshes.append(
        {
            "name": "Mouth",
            "weights": [0.0],
            "extras": {"targetNames": ["happySmile"]},
            "primitives": [
                {
                    "attributes": {"POSITION": mouth_position_accessor, "NORMAL": mouth_normal_accessor},
                    "indices": mouth_index_accessor,
                    "material": 6,
                    "targets": [{"POSITION": mouth_target_accessor}],
                }
            ],
        }
    )

    nodes: list[dict] = []

    def node(name: str, translation: list[float], mesh: int | None = None, scale: list[float] | None = None) -> int:
        value: dict = {"name": name, "translation": translation}
        if mesh is not None:
            value["mesh"] = mesh
        if scale is not None:
            value["scale"] = scale
        nodes.append(value)
        return len(nodes) - 1

    def attach(parent: int, child: int) -> None:
        nodes[parent].setdefault("children", []).append(child)

    root = node("Root", [0, 0, 0])
    hips = node("Hips", [0, 1.0, 0])
    spine = node("Spine", [0, 0.23, 0])
    chest = node("Chest", [0, 0.23, 0])
    neck = node("Neck", [0, 0.28, 0])
    head = node("Head", [0, 0.16, 0])
    left_upper_arm = node("LeftUpperArm", [-0.28, 0.18, 0])
    left_lower_arm = node("LeftLowerArm", [-0.34, 0, 0])
    left_hand = node("LeftHand", [-0.30, 0, 0])
    right_upper_arm = node("RightUpperArm", [0.28, 0.18, 0])
    right_lower_arm = node("RightLowerArm", [0.34, 0, 0])
    right_hand = node("RightHand", [0.30, 0, 0])
    left_upper_leg = node("LeftUpperLeg", [-0.14, -0.12, 0])
    left_lower_leg = node("LeftLowerLeg", [0, -0.42, 0])
    left_foot = node("LeftFoot", [0, -0.40, 0.07])
    right_upper_leg = node("RightUpperLeg", [0.14, -0.12, 0])
    right_lower_leg = node("RightLowerLeg", [0, -0.42, 0])
    right_foot = node("RightFoot", [0, -0.40, 0.07])

    for parent, child in (
        (root, hips), (hips, spine), (hips, left_upper_leg), (hips, right_upper_leg),
        (spine, chest), (chest, neck), (chest, left_upper_arm), (chest, right_upper_arm),
        (neck, head), (left_upper_arm, left_lower_arm), (left_lower_arm, left_hand),
        (right_upper_arm, right_lower_arm), (right_lower_arm, right_hand),
        (left_upper_leg, left_lower_leg), (left_lower_leg, left_foot),
        (right_upper_leg, right_lower_leg), (right_lower_leg, right_foot),
    ):
        attach(parent, child)

    def visual(parent: int, name: str, mesh: int, translation: list[float], scale: list[float]) -> int:
        index = node(name, translation, mesh, scale)
        attach(parent, index)
        return index

    visual(hips, "PelvisVisual", 2, [0, 0.02, 0], [0.42, 0.18, 0.23])
    visual(spine, "TorsoLowerVisual", 1, [0, 0.11, 0], [0.50, 0.34, 0.25])
    visual(chest, "TorsoUpperVisual", 1, [0, 0.12, 0], [0.58, 0.34, 0.27])
    visual(neck, "NeckVisual", 0, [0, 0.05, 0], [0.12, 0.14, 0.12])
    visual(head, "HeadVisual", 0, [0, 0.12, 0], [0.34, 0.38, 0.30])
    visual(head, "HairVisual", 3, [0, 0.28, -0.005], [0.36, 0.12, 0.31])
    visual(head, "LeftEyeVisual", 4, [-0.075, 0.17, 0.158], [0.045, 0.035, 0.018])
    visual(head, "RightEyeVisual", 4, [0.075, 0.17, 0.158], [0.045, 0.035, 0.018])
    mouth_node = visual(head, "MouthVisual", mouth_mesh, [0, 0.06, 0.162], [1, 1, 1])

    visual(left_upper_arm, "LeftUpperArmVisual", 0, [-0.17, 0, 0], [0.34, 0.11, 0.11])
    visual(left_lower_arm, "LeftLowerArmVisual", 0, [-0.17, 0, 0], [0.34, 0.095, 0.095])
    visual(left_hand, "LeftHandVisual", 0, [-0.08, 0, 0], [0.16, 0.12, 0.07])
    visual(right_upper_arm, "RightUpperArmVisual", 0, [0.17, 0, 0], [0.34, 0.11, 0.11])
    visual(right_lower_arm, "RightLowerArmVisual", 0, [0.17, 0, 0], [0.34, 0.095, 0.095])
    visual(right_hand, "RightHandVisual", 0, [0.08, 0, 0], [0.16, 0.12, 0.07])
    visual(left_upper_leg, "LeftUpperLegVisual", 2, [0, -0.20, 0], [0.18, 0.40, 0.19])
    visual(left_lower_leg, "LeftLowerLegVisual", 2, [0, -0.19, 0], [0.16, 0.38, 0.17])
    visual(left_foot, "LeftFootVisual", 5, [0, -0.04, 0.08], [0.18, 0.12, 0.31])
    visual(right_upper_leg, "RightUpperLegVisual", 2, [0, -0.20, 0], [0.18, 0.40, 0.19])
    visual(right_lower_leg, "RightLowerLegVisual", 2, [0, -0.19, 0], [0.16, 0.38, 0.17])
    visual(right_foot, "RightFootVisual", 5, [0, -0.04, 0.08], [0.18, 0.12, 0.31])

    human_bones = {
        "hips": {"node": hips},
        "spine": {"node": spine},
        "chest": {"node": chest},
        "neck": {"node": neck},
        "head": {"node": head},
        "leftUpperArm": {"node": left_upper_arm},
        "leftLowerArm": {"node": left_lower_arm},
        "leftHand": {"node": left_hand},
        "rightUpperArm": {"node": right_upper_arm},
        "rightLowerArm": {"node": right_lower_arm},
        "rightHand": {"node": right_hand},
        "leftUpperLeg": {"node": left_upper_leg},
        "leftLowerLeg": {"node": left_lower_leg},
        "leftFoot": {"node": left_foot},
        "rightUpperLeg": {"node": right_upper_leg},
        "rightLowerLeg": {"node": right_lower_leg},
        "rightFoot": {"node": right_foot},
    }

    gltf = {
        "asset": {"version": "2.0", "generator": "AICognitiveMind Genesis Avatar Builder"},
        "extensionsUsed": ["VRMC_vrm"],
        "extensions": {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {
                    "name": "Genesis",
                    "version": "0.1",
                    "authors": ["AICognitiveMind"],
                    "licenseUrl": "https://vrm.dev/licenses/1.0/",
                    "avatarPermission": "everyone",
                    "commercialUsage": "corporation",
                    "creditNotation": "unnecessary",
                    "allowRedistribution": True,
                    "modification": "allowModificationRedistribution",
                },
                "humanoid": {"humanBones": human_bones},
                "expressions": {
                    "preset": {
                        "happy": {
                            "isBinary": False,
                            "morphTargetBinds": [{"node": mouth_node, "index": 0, "weight": 1.0}],
                            "overrideBlink": "none",
                            "overrideLookAt": "none",
                            "overrideMouth": "none",
                        }
                    }
                },
            }
        },
        "scene": 0,
        "scenes": [{"name": "GenesisScene", "nodes": [root]}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(buffer)}],
    }

    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    binary_chunk = bytes(buffer)
    while len(binary_chunk) % 4:
        binary_chunk += b"\x00"

    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)
    return (
        struct.pack("<4sII", b"glTF", 2, total_length)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(binary_chunk), b"BIN\x00")
        + binary_chunk
    )

