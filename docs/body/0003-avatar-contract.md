# Body — Avatar Contract

**Status:** Locked architectural decision.

## Decision

The Body's avatar format is **VRM 1.0**.

The browser rendering/control stack is:

- **Three.js**
- **@pixiv/three-vrm**

The primary authoring and deep-customization tool is:

- **Blender**

## Architectural boundary

The avatar is part of the **Body**, not the Mind's identity.

Changing the avatar's:

- face;
- body;
- hair;
- skin;
- clothing;
- textures;
- accessories;
- expressions;
- animations;

does not change who the Mind is.

Identity, memory, beliefs, values, governance, and continuity remain owned by the Mind.

## Why VRM

VRM is the Body's portable avatar contract rather than a vendor-specific avatar platform.

The goal is full ownership and replaceability of the visual body:

```text
Mind
  ↓
ExpressionIntent
  ↓
Body / Face
  ↓
Avatar Runtime
Three.js + @pixiv/three-vrm
  ↓
*.vrm avatar asset
  ↓
Browser
```

## Required capabilities

The avatar architecture must support, without changing the Mind contract:

- fully replaceable appearance;
- facial expressions;
- eye gaze;
- lip synchronization;
- head and body motion;
- gestures and animation;
- clothing and accessory changes;
- custom materials and textures;
- secondary motion such as hair and clothing physics;
- future visual evolution of the Body.

## Ownership rule

No hosted avatar service is the canonical owner of the Body's appearance.

External tools may be used to create, edit, convert, or enhance avatar assets, but the canonical avatar must remain an owned VRM asset that can be rendered by the Body without depending on a proprietary avatar platform.

## V0 direction

The first avatar slice should remain narrow:

1. load one VRM avatar in the browser;
2. render it through Three.js;
3. drive one neutral expression and one explicit expression through the existing `ExpressionIntent` boundary.

Lip sync, speech coupling, gestures, animation libraries, and customization UI come after that first vertical slice is proven.


## Implemented slice

[0004 — Face V0.1](0004-face-v0.1.md) implements the first executable browser VRM renderer and
routes neutral/happy expression commands through the Body's `ExpressionIntent` boundary.
