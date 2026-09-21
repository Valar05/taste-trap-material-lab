# Taste Trap Material Lab

Phone-first Three.js inspection surface for the existing `FPSPlayer` arms.

Current scope is deliberately small:

- the original skinned mesh and skeleton;
- the existing donor PBR texture set;
- first-person view from the rig's `Camera` bone;
- third-person orbit, zoom, reset, and turntable;
- a small selector for existing ready poses.

No mesh surgery, reweighting, procedural material generation, Painter round-trip, or tessellation is implemented yet. Those are later layers, after the base model view is accepted.

## Run locally

Serve the repository root over HTTP and open `index.html`. ES modules and the GLB loader will not work reliably from a `file://` URL.

For example:

```sh
python -m http.server 4173
```

Then open `http://localhost:4173/`.

## Lineage

The viewport behavior is extracted from the useful viewing parts of Pose Lab: capped pixel density, touch-friendly damped orbit, model-aware framing, donor PBR-map transfer, and first-person camera attachment. Animation authoring and pose-editing systems are intentionally excluded.

