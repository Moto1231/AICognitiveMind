# Body — Genesis V0.2: Smooth Humanoid

**Status:** Smooth owned starter avatar.

## Purpose

Genesis V0.2 replaces the deliberately blocky V0.1 proof model with a visibly more human
source-generated body while preserving the same VRM 1.0 Body contract.

The surrounding Mind/Body architecture does not change.

## What changed

V0.1 reused one cube primitive for almost every body part.

V0.2 replaces that cube with smooth-shaded rounded geometry generated directly by:

```text
src/aicognitive_mind/body/genesis_avatar.py
```

The avatar now uses:

- rounded head;
- rounded torso and pelvis;
- capsule-like arms and legs;
- rounded hands and feet;
- separate eyeballs and irises;
- nose;
- ears;
- brows;
- a curved hair cap;
- the existing mouth morph target for the `happy` expression.

## Compatibility

The editor-facing node names remain stable, including:

- `HeadVisual`;
- `HairVisual`;
- `LeftEyeVisual` / `RightEyeVisual`;
- `MouthVisual`;
- `PelvisVisual`;
- `TorsoLowerVisual`;
- `TorsoUpperVisual`;
- limb visual nodes.

Therefore the existing Avatar Customization V0.1 controls continue to operate without a new
Mind/Body interface.

Eye color now applies to the iris material while the sclera remains independently white.

## Ownership

Genesis remains fully owned and source-generated.

No third-party avatar, proprietary avatar platform, or opaque binary asset becomes canonical.

The runtime endpoint remains:

```text
GET /v1/body/face/avatar
```

and emits the current Genesis VRM directly from source.

## Geometry

The old cube primitive contained 24 vertices.

The V0.2 rounded primitive contains hundreds of vertices with per-vertex surface normals, giving
Three.js enough geometry to render a smooth silhouette and smooth lighting.

The model remains intentionally lightweight enough for the browser-hosted Body runtime.

## What V0.2 is not

V0.2 is a meaningful visual upgrade, but it is not a photorealistic character.

It deliberately does not yet include:

- sculpted human facial topology;
- skin textures;
- normal maps;
- realistic hair strands/cards;
- fitted clothing meshes;
- fingers/toes;
- facial blendshape library;
- lip sync;
- physically based skin shading.

Those can be layered onto the same VRM contract after the owned smooth base is proven.

## Success criterion

Genesis V0.2 is successful when the deployed `/body/live` page:

1. loads a visibly rounded humanoid rather than block primitives;
2. preserves the existing avatar editor controls;
3. preserves Face expressions;
4. preserves Eyes/Ears/Mouth integration;
5. remains replaceable by another VRM without changing Mind identity.
