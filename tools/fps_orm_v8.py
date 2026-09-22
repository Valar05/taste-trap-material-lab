#!/usr/bin/env python3
"""Author and bind the ARIES v8 occlusion/roughness/metallic texture.

Run inside Blender 4.3+ with the accepted v7.2 master open. The script preserves
geometry, rig, actions, base color, and normals. It also injects the exact packed
ORM PNG into the accepted runtime GLB without invoking the memory-heavy exporter.
"""

import binascii
import hashlib
import json
import os
import struct
import zlib
from array import array

import bpy


DOWNLOAD = "/storage/emulated/0/Download"
SOURCE_BLEND = os.path.join(DOWNLOAD, "FPSPlayer_ARIES_Plates_v7_2.blend")
SOURCE_GLB = os.path.join(DOWNLOAD, "FPSPlayer_ARIES_Plates_v7_2_runtime.glb")
OUT_BLEND = os.path.join(DOWNLOAD, "FPSPlayer_ARIES_ORM_v8.blend")
OUT_ORM = os.path.join(DOWNLOAD, "FPSPlayer_ARIES_ORM_v8.png")
OUT_GLB = os.path.join(DOWNLOAD, "FPSPlayer_ARIES_ORM_v8_runtime.glb")

EXPECTED_BLEND_SHA256 = "960354b6fc471e7f3fa9401a95f90f1deb0af0bc3f76d504ba6e0f8524230d8d"
EXPECTED_GLB_SHA256 = "cb81cfa5cbdb0d05ea58c775564c64f69e1d8393663430eeeb23bcfccd17b414"

PALETTE = {
    "glove_palm": (47, 43, 36),
    "glove_mid": (70, 63, 52),
    "glove_top": (94, 82, 65),
    "knuckle": (143, 119, 82),
    "cuff": (174, 111, 29),
    "cuff_shadow": (126, 79, 27),
    "armor": (163, 153, 133),
    "armor_top": (188, 178, 154),
    "armor_shadow": (132, 124, 108),
    "undersuit": (56, 52, 46),
    "trim": (73, 65, 55),
    "utility": (157, 101, 30),
    "warning_red": (135, 47, 35),
    "leg": (166, 155, 134),
    "boot": (51, 47, 41),
}

# R=ambient occlusion, G=roughness, B=metallic. These are manufactured
# material identities, not luminance remapping or procedural wear.
ORM = {
    "glove_palm": (0.96, 0.90, 0.00),
    "glove_mid": (0.98, 0.84, 0.00),
    "glove_top": (1.00, 0.78, 0.00),
    "knuckle": (0.96, 0.58, 0.38),
    "cuff": (1.00, 0.42, 0.82),
    "cuff_shadow": (0.78, 0.48, 0.76),
    "armor": (1.00, 0.58, 0.03),
    "armor_top": (1.00, 0.52, 0.03),
    "armor_shadow": (0.86, 0.64, 0.03),
    "undersuit": (0.74, 0.90, 0.00),
    "trim": (0.58, 0.72, 0.18),
    "utility": (0.98, 0.45, 0.78),
    "warning_red": (1.00, 0.62, 0.00),
    "leg": (1.00, 0.60, 0.03),
    "boot": (0.92, 0.88, 0.00),
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_source_identity():
    if sha256(SOURCE_BLEND) != EXPECTED_BLEND_SHA256:
        raise RuntimeError("accepted v7.2 Blender master hash mismatch")
    if sha256(SOURCE_GLB) != EXPECTED_GLB_SHA256:
        raise RuntimeError("accepted v7.2 runtime GLB hash mismatch")
    current = os.path.realpath(bpy.data.filepath)
    if current != os.path.realpath(SOURCE_BLEND):
        raise RuntimeError(f"wrong Blender master open: {current}")


def png_chunk(kind, payload):
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def write_png_rgb(path, pixels, width, height):
    stride = width * 3
    raw = b"".join(
        b"\x00" + bytes(pixels[y * stride : (y + 1) * stride])
        for y in range(height - 1, -1, -1)
    )
    data = bytearray(b"\x89PNG\r\n\x1a\n")
    data.extend(png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    data.extend(png_chunk(b"IDAT", zlib.compress(raw, 9)))
    data.extend(png_chunk(b"IEND", b""))
    with open(path, "wb") as handle:
        handle.write(data)


def nearest_material(rgb):
    if max(rgb) < 8:
        return "unused"
    return min(
        PALETTE,
        key=lambda name: sum((rgb[i] - PALETTE[name][i]) ** 2 for i in range(3)),
    )


def build_orm_from_accepted_albedo():
    albedo = next(
        (image for image in bpy.data.images if "FPSPlayer_ARIES_Albedo_v5_1" in image.name),
        None,
    )
    if albedo is None:
        external = os.path.join(DOWNLOAD, "FPSPlayer_ARIES_Albedo_v5_1.png")
        albedo = bpy.data.images.load(external, check_existing=True)
    width, height = tuple(albedo.size)
    if (width, height) != (1024, 1024):
        raise RuntimeError(f"accepted albedo must remain 1024x1024, got {width}x{height}")

    source = array("f", [0.0]) * (width * height * 4)
    albedo.pixels.foreach_get(source)
    packed = bytearray(width * height * 3)
    cache = {}
    counts = {name: 0 for name in (*PALETTE.keys(), "unused")}
    for pixel in range(width * height):
        offset = pixel * 4
        # The accepted generated albedo is stored in authored byte space.
        rgb = tuple(max(0, min(255, round(source[offset + channel] * 255))) for channel in range(3))
        material = cache.get(rgb)
        if material is None:
            material = nearest_material(rgb)
            cache[rgb] = material
        counts[material] += 1
        ao, roughness, metallic = ORM.get(material, (1.0, 1.0, 0.0))
        target = pixel * 3
        packed[target : target + 3] = bytes(
            (round(ao * 255), round(roughness * 255), round(metallic * 255))
        )

    print("semantic_counts_preflight", json.dumps(counts, sort_keys=True))
    if counts["cuff"] + counts["utility"] + counts["cuff_shadow"] < 8_000:
        raise RuntimeError("ORM classification found too little metallic gold hardware")
    if counts["armor"] + counts["armor_top"] + counts["armor_shadow"] < 150_000:
        raise RuntimeError("ORM classification found too little painted armor")
    if counts["glove_palm"] + counts["glove_mid"] + counts["glove_top"] < 150_000:
        raise RuntimeError("ORM classification found too little glove material")

    write_png_rgb(OUT_ORM, packed, width, height)
    return counts


def ensure_gltf_occlusion_group():
    group = bpy.data.node_groups.get("glTF Material Output")
    if group is None:
        group = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    sockets = [item for item in group.interface.items_tree if getattr(item, "item_type", "") == "SOCKET"]
    if not any(socket.name == "Occlusion" and socket.in_out == "INPUT" for socket in sockets):
        group.interface.new_socket(name="Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return group


def bind_orm_to_master():
    orm_image = bpy.data.images.load(OUT_ORM, check_existing=False)
    orm_image.name = "FPSPlayer_ARIES_ORM_v8"
    orm_image.colorspace_settings.name = "Non-Color"
    orm_image.pack()
    occlusion_group = ensure_gltf_occlusion_group()
    bound = 0

    for material in bpy.data.materials:
        if not material.use_nodes or not material.node_tree:
            continue
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        bsdf = next((node for node in nodes if node.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        for node in list(nodes):
            if node.get("aries_orm_v8"):
                nodes.remove(node)

        texture = nodes.new("ShaderNodeTexImage")
        texture.name = "ARIES ORM v8"
        texture.label = "ARIES ORM v8 (R=AO G=Roughness B=Metallic)"
        texture.image = orm_image
        texture.interpolation = "Linear"
        texture.extension = "EXTEND"
        texture["aries_orm_v8"] = True

        separate = nodes.new("ShaderNodeSeparateColor")
        separate.name = "ARIES ORM v8 Channels"
        separate.mode = "RGB"
        separate["aries_orm_v8"] = True
        links.new(texture.outputs["Color"], separate.inputs["Color"])
        links.new(separate.outputs["Green"], bsdf.inputs["Roughness"])
        links.new(separate.outputs["Blue"], bsdf.inputs["Metallic"])
        bsdf.inputs["Roughness"].default_value = 1.0
        bsdf.inputs["Metallic"].default_value = 1.0

        gltf_output = nodes.new("ShaderNodeGroup")
        gltf_output.name = "glTF Material Output"
        gltf_output.node_tree = occlusion_group
        gltf_output["aries_orm_v8"] = True
        links.new(separate.outputs["Red"], gltf_output.inputs["Occlusion"])
        bound += 1

    if bound < 2:
        raise RuntimeError(f"expected both ARIES materials to receive ORM, bound {bound}")
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    return bound


def parse_glb(path):
    blob = open(path, "rb").read()
    if blob[:4] != b"glTF" or struct.unpack_from("<I", blob, 4)[0] != 2:
        raise RuntimeError("source runtime is not glTF 2.0 GLB")
    json_length, json_type = struct.unpack_from("<II", blob, 12)
    if json_type != 0x4E4F534A:
        raise RuntimeError("GLB JSON chunk is missing")
    json_start = 20
    document = json.loads(blob[json_start : json_start + json_length].decode("utf-8"))
    bin_header = json_start + json_length
    bin_length, bin_type = struct.unpack_from("<II", blob, bin_header)
    if bin_type != 0x004E4942:
        raise RuntimeError("GLB BIN chunk is missing")
    binary = blob[bin_header + 8 : bin_header + 8 + bin_length]
    return document, binary


def write_glb(path, document, binary):
    encoded = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    encoded += b" " * ((4 - len(encoded) % 4) % 4)
    binary += b"\x00" * ((4 - len(binary) % 4) % 4)
    total = 12 + 8 + len(encoded) + 8 + len(binary)
    with open(path, "wb") as handle:
        handle.write(struct.pack("<4sII", b"glTF", 2, total))
        handle.write(struct.pack("<II", len(encoded), 0x4E4F534A))
        handle.write(encoded)
        handle.write(struct.pack("<II", len(binary), 0x004E4942))
        handle.write(binary)


def inject_orm_into_runtime():
    document, old_binary = parse_glb(SOURCE_GLB)
    immutable = {
        key: json.dumps(document.get(key), sort_keys=True)
        for key in ("nodes", "meshes", "skins", "animations", "accessors")
    }
    png = open(OUT_ORM, "rb").read()
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("generated ORM is not a PNG")
    offset = (len(old_binary) + 3) & ~3
    binary = old_binary + b"\x00" * (offset - len(old_binary)) + png
    document.setdefault("bufferViews", []).append(
        {"buffer": 0, "byteOffset": offset, "byteLength": len(png)}
    )
    view_index = len(document["bufferViews"]) - 1
    document.setdefault("images", []).append(
        {"bufferView": view_index, "mimeType": "image/png", "name": "FPSPlayer_ARIES_ORM_v8"}
    )
    image_index = len(document["images"]) - 1
    document.setdefault("textures", []).append({"sampler": 1, "source": image_index})
    texture_index = len(document["textures"]) - 1
    for material in document.get("materials", []):
        pbr = material.setdefault("pbrMetallicRoughness", {})
        pbr["metallicFactor"] = 1.0
        pbr["roughnessFactor"] = 1.0
        pbr["metallicRoughnessTexture"] = {"index": texture_index, "texCoord": 1}
        material["occlusionTexture"] = {"index": texture_index, "texCoord": 1, "strength": 1.0}
    document["buffers"][0]["byteLength"] = len(binary)
    write_glb(OUT_GLB, document, binary)

    rebuilt, _rebuilt_binary = parse_glb(OUT_GLB)
    for key, before in immutable.items():
        if json.dumps(rebuilt.get(key), sort_keys=True) != before:
            raise RuntimeError(f"ORM injection unexpectedly changed {key}")
    if len(rebuilt.get("animations", [])) != 57 or len(rebuilt.get("meshes", [])) != 16:
        raise RuntimeError("runtime animation or mesh inventory changed")
    if len(rebuilt.get("skins", [])) != 1:
        raise RuntimeError("runtime skin inventory changed")
    for material in rebuilt.get("materials", []):
        pbr = material.get("pbrMetallicRoughness", {})
        if pbr.get("metallicRoughnessTexture", {}).get("index") != texture_index:
            raise RuntimeError("runtime material is missing packed metallic/roughness")
        if material.get("occlusionTexture", {}).get("index") != texture_index:
            raise RuntimeError("runtime material is missing packed occlusion")


def main():
    require_source_identity()
    if len([obj for obj in bpy.data.objects if obj.type == "MESH" and obj.name.startswith("ARIES_Plate_")]) != 15:
        raise RuntimeError("accepted 15-piece plate inventory changed")
    if len(bpy.data.actions) != 57:
        raise RuntimeError("accepted 57-animation inventory changed")
    counts = build_orm_from_accepted_albedo()
    bound = bind_orm_to_master()
    inject_orm_into_runtime()
    print("FPS_ARIES_ORM_V8_OK")
    print("materials_bound", bound)
    print("semantic_counts", json.dumps(counts, sort_keys=True))
    print("orm", OUT_ORM, os.path.getsize(OUT_ORM), sha256(OUT_ORM))
    print("blend", OUT_BLEND, os.path.getsize(OUT_BLEND), sha256(OUT_BLEND))
    print("glb", OUT_GLB, os.path.getsize(OUT_GLB), sha256(OUT_GLB))


main()
