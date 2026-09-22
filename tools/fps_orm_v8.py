        rgb = tuple(linear_to_srgb_byte(source[offset + channel]) for channel in range(3))
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
    if counts["glove_palm"] + counts["glove_mid"] + counts["glove_top"] < 200_000:
        raise RuntimeError("ORM classification found too little glove material")

    write_png_rgb(OUT_ORM, packed, width, height)
