export const AVATAR_APPEARANCE_STORAGE_KEY =
  "aicognitive_mind.avatar.appearance.v0.1";

export const DEFAULT_AVATAR_APPEARANCE = Object.freeze({
  skinColor: "#b88566",
  hairColor: "#090a0d",
  shirtColor: "#2e4257",
  pantsColor: "#1a1f29",
  eyeColor: "#090a0d",
  shoeColor: "#090a0d",
  headSize: 1.0,
  hairVolume: 1.0,
  eyeSize: 1.0,
  eyeSpacing: 1.0,
  mouthWidth: 1.0,
  torsoWidth: 1.0,
  shoulderWidth: 1.0,
  armThickness: 1.0,
  legThickness: 1.0
});

const NUMBER_LIMITS = Object.freeze({
  headSize: [0.75, 1.35],
  hairVolume: [0.60, 1.60],
  eyeSize: [0.60, 1.60],
  eyeSpacing: [0.65, 1.45],
  mouthWidth: [0.60, 1.50],
  torsoWidth: [0.70, 1.40],
  shoulderWidth: [0.75, 1.40],
  armThickness: [0.65, 1.50],
  legThickness: [0.65, 1.50]
});

const NODE_NAMES = [
  "HeadVisual",
  "HairVisual",
  "LeftEyeVisual",
  "RightEyeVisual",
  "MouthVisual",
  "PelvisVisual",
  "TorsoLowerVisual",
  "TorsoUpperVisual",
  "LeftUpperArm",
  "RightUpperArm",
  "LeftUpperArmVisual",
  "LeftLowerArmVisual",
  "RightUpperArmVisual",
  "RightLowerArmVisual",
  "LeftUpperLegVisual",
  "LeftLowerLegVisual",
  "RightUpperLegVisual",
  "RightLowerLegVisual"
];

function cloneTransform(node) {
  return {
    position: node.position.clone(),
    scale: node.scale.clone()
  };
}

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function normalizeHex(value, fallback) {
  const candidate = String(value || "").trim();
  return /^#[0-9a-fA-F]{6}$/.test(candidate) ? candidate.toLowerCase() : fallback;
}

export function normalizeAvatarAppearance(candidate = {}) {
  const normalized = { ...DEFAULT_AVATAR_APPEARANCE };

  for (const key of [
    "skinColor",
    "hairColor",
    "shirtColor",
    "pantsColor",
    "eyeColor",
    "shoeColor"
  ]) {
    normalized[key] = normalizeHex(candidate[key], DEFAULT_AVATAR_APPEARANCE[key]);
  }

  for (const [key, [minimum, maximum]] of Object.entries(NUMBER_LIMITS)) {
    const parsed = Number(candidate[key]);
    normalized[key] = Number.isFinite(parsed)
      ? clamp(parsed, minimum, maximum)
      : DEFAULT_AVATAR_APPEARANCE[key];
  }

  return normalized;
}

export function loadSavedAvatarAppearance(storage = window.localStorage) {
  try {
    const raw = storage.getItem(AVATAR_APPEARANCE_STORAGE_KEY);
    return raw
      ? normalizeAvatarAppearance(JSON.parse(raw))
      : { ...DEFAULT_AVATAR_APPEARANCE };
  } catch {
    return { ...DEFAULT_AVATAR_APPEARANCE };
  }
}

export function saveAvatarAppearance(config, storage = window.localStorage) {
  const normalized = normalizeAvatarAppearance(config);
  storage.setItem(AVATAR_APPEARANCE_STORAGE_KEY, JSON.stringify(normalized));
  return normalized;
}

export function clearSavedAvatarAppearance(storage = window.localStorage) {
  storage.removeItem(AVATAR_APPEARANCE_STORAGE_KEY);
}

export class AvatarCustomizer {
  constructor(vrm) {
    if (!vrm?.scene) {
      throw new Error("AvatarCustomizer requires a loaded VRM");
    }

    this.vrm = vrm;
    this.scene = vrm.scene;
    this._baseline = new Map();

    for (const name of NODE_NAMES) {
      const node = this.scene.getObjectByName(name);
      if (node) this._baseline.set(name, cloneTransform(node));
    }
  }

  apply(candidate) {
    const config = normalizeAvatarAppearance(candidate);

    this.setMaterialColor("Skin", config.skinColor);
    this.setMaterialColor("Hair", config.hairColor);
    this.setMaterialColor("Shirt", config.shirtColor);
    this.setMaterialColor("Pants", config.pantsColor);
    this.setMaterialColor("Eyes", config.eyeColor);
    this.setMaterialColor("Shoes", config.shoeColor);

    this.setNodeScale("HeadVisual", config.headSize, config.headSize, config.headSize);
    this.setNodeScale(
      "HairVisual",
      config.hairVolume,
      config.hairVolume,
      config.hairVolume
    );
    this.setNodeScale("LeftEyeVisual", config.eyeSize, config.eyeSize, config.eyeSize);
    this.setNodeScale("RightEyeVisual", config.eyeSize, config.eyeSize, config.eyeSize);
    this.setNodePositionX("LeftEyeVisual", config.eyeSpacing);
    this.setNodePositionX("RightEyeVisual", config.eyeSpacing);
    this.setNodeScale("MouthVisual", config.mouthWidth, 1, 1);

    this.setNodeScale("PelvisVisual", config.torsoWidth, 1, 1);
    this.setNodeScale("TorsoLowerVisual", config.torsoWidth, 1, 1);
    this.setNodeScale("TorsoUpperVisual", config.torsoWidth, 1, 1);

    this.setNodePositionX("LeftUpperArm", config.shoulderWidth);
    this.setNodePositionX("RightUpperArm", config.shoulderWidth);

    for (const name of [
      "LeftUpperArmVisual",
      "LeftLowerArmVisual",
      "RightUpperArmVisual",
      "RightLowerArmVisual"
    ]) {
      this.setNodeScale(name, 1, config.armThickness, config.armThickness);
    }

    for (const name of [
      "LeftUpperLegVisual",
      "LeftLowerLegVisual",
      "RightUpperLegVisual",
      "RightLowerLegVisual"
    ]) {
      this.setNodeScale(name, config.legThickness, 1, config.legThickness);
    }

    return config;
  }

  reset() {
    return this.apply(DEFAULT_AVATAR_APPEARANCE);
  }

  setMaterialColor(materialName, hexColor) {
    const normalized = normalizeHex(hexColor, "#ffffff");
    let changed = false;

    this.scene.traverse((object) => {
      if (!object?.isMesh || !object.material) return;
      const materials = Array.isArray(object.material)
        ? object.material
        : [object.material];

      for (const material of materials) {
        if (material.name !== materialName || !material.color) continue;
        material.color.set(normalized);
        material.needsUpdate = true;
        changed = true;
      }
    });

    return changed;
  }

  setNodeScale(name, xMultiplier = 1, yMultiplier = 1, zMultiplier = 1) {
    const node = this.scene.getObjectByName(name);
    const baseline = this._baseline.get(name);
    if (!node || !baseline) return false;

    node.scale.set(
      baseline.scale.x * xMultiplier,
      baseline.scale.y * yMultiplier,
      baseline.scale.z * zMultiplier
    );
    return true;
  }

  setNodePositionX(name, multiplier = 1) {
    const node = this.scene.getObjectByName(name);
    const baseline = this._baseline.get(name);
    if (!node || !baseline) return false;

    node.position.x = baseline.position.x * multiplier;
    return true;
  }
}
