# Body — Avatar Customization V0.1

**Status:** First live appearance editor.

## Purpose

Avatar Customization V0.1 turns Genesis from a fixed starter body into a runtime-editable Body.

The editor lives inside:

```text
/body/live
```

Changes affect only the avatar appearance. They do not modify Mind identity, memory, beliefs, or
cognitive history.

## Reusable customization layer

The browser customization functions live in:

```text
src/aicognitive_mind/static/avatar_customizer.js
```

`AvatarCustomizer` exposes reusable operations including:

- `setMaterialColor()`;
- `setNodeScale()`;
- `setNodePositionX()`;
- `apply()`;
- `reset()`.

The module also owns normalization and browser-local preset functions.

## V0.1 controls

Genesis can now be changed live through:

### Color

- skin;
- hair;
- shirt;
- pants;
- eyes;
- shoes.

### Proportion

- head size;
- hair volume;
- eye size;
- eye spacing;
- mouth width;
- torso width;
- shoulder width;
- arm thickness;
- leg thickness.

## Genesis material correction

The original Genesis starter avatar reused one `Dark` material for hair, eyes, and shoes.

That prevented independent editing.

Avatar Customization V0.1 replaces that shared material with independently addressable:

- `Hair`;
- `Eyes`;
- `Shoes`.

The default visual appearance remains effectively unchanged, but future edits no longer cause
unrelated body parts to change together.

## Persistence boundary

The first editor stores its preset in browser `localStorage`.

This is deliberate for the first slice:

- it allows immediate experimentation;
- it does not add appearance data to Mind memory;
- it avoids defining a permanent Body-persistence schema before the useful control set is known.

Browser-local persistence is not the canonical long-term Body store.

Once the customization vocabulary stabilizes, a later slice can persist the Body appearance
configuration independently of the Mind so it follows the Body across browsers and devices.

## V0.1 success criterion

The slice is proven when the deployed `/body/live` page can:

1. change Genesis materials independently;
2. change the listed proportions live;
3. save the appearance in the current browser;
4. reload and restore that browser preset;
5. reset Genesis to its default appearance;
6. continue using Eyes, Ears, Face, and Mouth after customization.

## Deliberately not included yet

- canonical cross-device Body appearance persistence;
- hair-style selection;
- clothing mesh replacement;
- accessories;
- texture uploads;
- facial-shape morph targets;
- body-height / limb-length rig editing;
- Blender-authored high-detail replacement assets;
- automatic appearance decisions by the Mind.
