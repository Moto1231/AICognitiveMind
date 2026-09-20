from __future__ import annotations

import json
import math
import struct


def build_genesis_vrm() -> bytes:
    """Build the owned Genesis V0.3 smooth humanoid VRM as a GLB."""

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

    def make_uv_sphere(
        *,
        longitudes: int = 24,
        latitudes: int = 16,
        phi_max: float = math.pi,
    ) -> tuple[list[float], list[float], list[int]]:
        positions: list[float] = []
        normals: list[float] = []
        indices: list[int] = []

        for latitude in range(latitudes + 1):
            phi = phi_max * latitude / latitudes
            y = math.cos(phi)
            ring = math.sin(phi)
            for longitude in range(longitudes + 1):
                theta = math.tau * longitude / longitudes
                x = ring * math.cos(theta)
                z = ring * math.sin(theta)
                positions.extend([x, y, z])
                length = math.sqrt(x * x + y * y + z * z) or 1.0
                normals.extend([x / length, y / length, z / length])

        row = longitudes + 1
        for latitude in range(latitudes):
            for longitude in range(longitudes):
                a = latitude * row + longitude
                b = (latitude + 1) * row + longitude
                c = b + 1
                d = a + 1
                indices.extend([a, b, c, a, c, d])

        return positions, normals, indices

    def geometry_accessors(
        positions: list[float],
        normals: list[float],
        indices: list[int],
    ) -> tuple[int, int, int]:
        xs = positions[0::3]
        ys = positions[1::3]
        zs = positions[2::3]
        position_accessor = add_accessor(
            positions,
            5126,
            "VEC3",
            len(positions) // 3,
            34962,
            [min(xs), min(ys), min(zs)],
            [max(xs), max(ys), max(zs)],
        )
        normal_accessor = add_accessor(
            normals,
            5126,
            "VEC3",
            len(normals) // 3,
            34962,
        )
        index_component = 5123 if max(indices, default=0) <= 65535 else 5125
        index_accessor = add_accessor(
            indices,
            index_component,
            "SCALAR",
            len(indices),
            34963,
            [min(indices, default=0)],
            [max(indices, default=0)],
        )
        return position_accessor, normal_accessor, index_accessor

    sphere_accessors = geometry_accessors(*make_uv_sphere())
    hair_cap_accessors = geometry_accessors(
        *make_uv_sphere(longitudes=24, latitudes=10, phi_max=math.pi * 0.58)
    )

    mouth_xs = [-0.14, -0.07, 0.0, 0.07, 0.14]
    mouth_positions: list[float] = []
    mouth_normals: list[float] = []
    for y_offset in (0.008, -0.008):
        for x in mouth_xs:
            mouth_positions.extend([x, y_offset, 0.0])
            mouth_normals.extend([0.0, 0.0, 1.0])

    mouth_indices: list[int] = []
    for index in range(4):
        a, b, c, d = index, index + 1, 5 + index + 1, 5 + index
        mouth_indices.extend([a, d, c, a, c, b])

    mouth_smile_delta: list[float] = []
    smile = [0.04, 0.018, -0.006, 0.018, 0.04]
    for _ in range(2):
        for delta_y in smile:
            mouth_smile_delta.extend([0.0, delta_y, 0.0])

    mouth_open_delta: list[float] = []
    for delta_y in (0.016, 0.018, 0.020, 0.018, 0.016):
        mouth_open_delta.extend([0.0, delta_y, 0.0])
    for delta_y in (-0.026, -0.030, -0.034, -0.030, -0.026):
        mouth_open_delta.extend([0.0, delta_y, 0.0])

    mouth_position_accessor = add_accessor(
        mouth_positions,
        5126,
        "VEC3",
        10,
        34962,
        [-0.14, -0.008, 0.0],
        [0.14, 0.008, 0.0],
    )
    mouth_normal_accessor = add_accessor(mouth_normals, 5126, "VEC3", 10, 34962)
    mouth_index_accessor = add_accessor(
        mouth_indices,
        5123,
        "SCALAR",
        24,
        34963,
        [0],
        [9],
    )
    mouth_smile_target_accessor = add_accessor(
        mouth_smile_delta,
        5126,
        "VEC3",
        10,
        34962,
        [0.0, -0.006, 0.0],
        [0.0, 0.04, 0.0],
    )
    mouth_open_target_accessor = add_accessor(
        mouth_open_delta,
        5126,
        "VEC3",
        10,
        34962,
        [0.0, -0.034, 0.0],
        [0.0, 0.020, 0.0],
    )

    def material(
        name: str,
        color: list[float],
        roughness: float,
    ) -> dict:
        return {
            "name": name,
            "doubleSided": True,
            "pbrMetallicRoughness": {
                "baseColorFactor": color,
                "metallicFactor": 0,
                "roughnessFactor": roughness,
            },
        }

    materials = [
        material("Skin", [0.72, 0.52, 0.40, 1], 0.82),
        material("Shirt", [0.18, 0.26, 0.34, 1], 0.88),
        material("Pants", [0.10, 0.12, 0.16, 1], 0.92),
        material("Hair", [0.035, 0.04, 0.05, 1], 0.68),
        material("Eyes", [0.12, 0.18, 0.20, 1], 0.55),
        material("Shoes", [0.035, 0.04, 0.05, 1], 0.78),
        material("Mouth", [0.36, 0.06, 0.07, 1], 0.72),
        material("EyeWhite", [0.92, 0.93, 0.90, 1], 0.45),
    ]

    meshes: list[dict] = []

    def add_mesh(
        name: str,
        material_index: int,
        accessor_set: tuple[int, int, int] = sphere_accessors,
    ) -> int:
        position_accessor, normal_accessor, index_accessor = accessor_set
        meshes.append(
            {
                "name": name,
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": position_accessor,
                            "NORMAL": normal_accessor,
                        },
                        "indices": index_accessor,
                        "material": material_index,
                    }
                ],
            }
        )
        return len(meshes) - 1

    skin_mesh = add_mesh("SkinSmooth", 0)
    shirt_mesh = add_mesh("ShirtSmooth", 1)
    pants_mesh = add_mesh("PantsSmooth", 2)
    hair_mesh = add_mesh("HairCap", 3, hair_cap_accessors)
    eye_mesh = add_mesh("EyeIris", 4)
    shoe_mesh = add_mesh("ShoeSmooth", 5)
    eye_white_mesh = add_mesh("EyeWhite", 7)

    mouth_mesh = len(meshes)
    meshes.append(
        {
            "name": "Mouth",
            "weights": [0.0, 0.0],
            "extras": {"targetNames": ["happySmile", "aaOpen"]},
            "primitives": [
                {
                    "attributes": {
                        "POSITION": mouth_position_accessor,
                        "NORMAL": mouth_normal_accessor,
                    },
                    "indices": mouth_index_accessor,
                    "material": 6,
                    "targets": [
                        {"POSITION": mouth_smile_target_accessor},
                        {"POSITION": mouth_open_target_accessor},
                    ],
                }
            ],
        }
    )

    nodes: list[dict] = []

    def node(
        name: str,
        translation: list[float],
        mesh: int | None = None,
        scale: list[float] | None = None,
    ) -> int:
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
        (root, hips),
        (hips, spine),
        (hips, left_upper_leg),
        (hips, right_upper_leg),
        (spine, chest),
        (chest, neck),
        (chest, left_upper_arm),
        (chest, right_upper_arm),
        (neck, head),
        (left_upper_arm, left_lower_arm),
        (left_lower_arm, left_hand),
        (right_upper_arm, right_lower_arm),
        (right_lower_arm, right_hand),
        (left_upper_leg, left_lower_leg),
        (left_lower_leg, left_foot),
        (right_upper_leg, right_lower_leg),
        (right_lower_leg, right_foot),
    ):
        attach(parent, child)

    def visual(
        parent: int,
        name: str,
        mesh: int,
        translation: list[float],
        scale: list[float],
    ) -> int:
        index = node(name, translation, mesh, scale)
        attach(parent, index)
        return index

    # Rounded torso volumes.
    visual(hips, "PelvisVisual", pants_mesh, [0, 0.015, 0], [0.25, 0.13, 0.17])
    visual(spine, "TorsoLowerVisual", shirt_mesh, [0, 0.105, 0], [0.27, 0.20, 0.16])
    visual(chest, "TorsoUpperVisual", shirt_mesh, [0, 0.11, 0], [0.33, 0.21, 0.18])
    visual(neck, "NeckVisual", skin_mesh, [0, 0.055, 0], [0.075, 0.10, 0.075])

    # Face.
    visual(head, "HeadVisual", skin_mesh, [0, 0.115, 0], [0.235, 0.285, 0.225])
    visual(head, "HairVisual", hair_mesh, [0, 0.145, -0.005], [0.247, 0.305, 0.237])
    visual(head, "LeftEarVisual", skin_mesh, [-0.238, 0.115, 0], [0.032, 0.070, 0.035])
    visual(head, "RightEarVisual", skin_mesh, [0.238, 0.115, 0], [0.032, 0.070, 0.035])
    visual(head, "NoseVisual", skin_mesh, [0, 0.085, 0.220], [0.042, 0.060, 0.055])

    left_eye = node("LeftEyeVisual", [-0.077, 0.145, 0.214])
    right_eye = node("RightEyeVisual", [0.077, 0.145, 0.214])
    attach(head, left_eye)
    attach(head, right_eye)

    visual(left_eye, "LeftEyeWhite", eye_white_mesh, [0, 0, 0], [0.064, 0.042, 0.026])
    visual(right_eye, "RightEyeWhite", eye_white_mesh, [0, 0, 0], [0.064, 0.042, 0.026])
    visual(left_eye, "LeftIrisVisual", eye_mesh, [0, 0, 0.024], [0.028, 0.028, 0.013])
    visual(right_eye, "RightIrisVisual", eye_mesh, [0, 0, 0.024], [0.028, 0.028, 0.013])

    visual(head, "LeftBrowVisual", hair_mesh, [-0.077, 0.205, 0.211], [0.080, 0.018, 0.020])
    visual(head, "RightBrowVisual", hair_mesh, [0.077, 0.205, 0.211], [0.080, 0.018, 0.020])

    mouth_node = visual(
        head,
        "MouthVisual",
        mouth_mesh,
        [0, 0.010, 0.228],
        [0.72, 0.72, 0.72],
    )

    # Rounded limbs. Elongated spheres create capsule-like forms without hard cube edges.
    visual(
        left_upper_arm,
        "LeftUpperArmVisual",
        skin_mesh,
        [-0.17, 0, 0],
        [0.18, 0.073, 0.073],
    )
    visual(
        left_lower_arm,
        "LeftLowerArmVisual",
        skin_mesh,
        [-0.17, 0, 0],
        [0.18, 0.062, 0.062],
    )
    visual(
        left_hand,
        "LeftHandVisual",
        skin_mesh,
        [-0.080, 0, 0],
        [0.090, 0.070, 0.045],
    )

    visual(
        right_upper_arm,
        "RightUpperArmVisual",
        skin_mesh,
        [0.17, 0, 0],
        [0.18, 0.073, 0.073],
    )
    visual(
        right_lower_arm,
        "RightLowerArmVisual",
        skin_mesh,
        [0.17, 0, 0],
        [0.18, 0.062, 0.062],
    )
    visual(
        right_hand,
        "RightHandVisual",
        skin_mesh,
        [0.080, 0, 0],
        [0.090, 0.070, 0.045],
    )

    visual(
        left_upper_leg,
        "LeftUpperLegVisual",
        pants_mesh,
        [0, -0.20, 0],
        [0.105, 0.22, 0.115],
    )
    visual(
        left_lower_leg,
        "LeftLowerLegVisual",
        pants_mesh,
        [0, -0.19, 0],
        [0.090, 0.20, 0.095],
    )
    visual(
        left_foot,
        "LeftFootVisual",
        shoe_mesh,
        [0, -0.035, 0.080],
        [0.105, 0.070, 0.165],
    )

    visual(
        right_upper_leg,
        "RightUpperLegVisual",
        pants_mesh,
        [0, -0.20, 0],
        [0.105, 0.22, 0.115],
    )
    visual(
        right_lower_leg,
        "RightLowerLegVisual",
        pants_mesh,
        [0, -0.19, 0],
        [0.090, 0.20, 0.095],
    )
    visual(
        right_foot,
        "RightFootVisual",
        shoe_mesh,
        [0, -0.035, 0.080],
        [0.105, 0.070, 0.165],
    )

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
        "asset": {
            "version": "2.0",
            "generator": "AICognitiveMind Genesis Avatar Builder V0.3",
        },
        "extensionsUsed": ["VRMC_vrm"],
        "extensions": {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {
                    "name": "Genesis",
                    "version": "0.3",
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
                            "morphTargetBinds": [
                                {"node": mouth_node, "index": 0, "weight": 1.0}
                            ],
                            "overrideBlink": "none",
                            "overrideLookAt": "none",
                            "overrideMouth": "none",
                        },
                        "aa": {
                            "isBinary": False,
                            "morphTargetBinds": [
                                {"node": mouth_node, "index": 1, "weight": 1.0}
                            ],
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
