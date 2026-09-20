const STORAGE_KEY = "aicognitive_mind.voice_pack.v1";

export const DEFAULT_VOICE_PACK = Object.freeze({
  voiceName: "",
  voiceURI: "",
  lang: "",
  rate: 1.0,
  pitch: 1.0,
  volume: 1.0
});

function clamp(value, minimum, maximum, fallback) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.max(minimum, Math.min(maximum, number));
}

export function normalizeVoicePack(value = {}) {
  return {
    voiceName: String(value.voiceName || "").trim(),
    voiceURI: String(value.voiceURI || "").trim(),
    lang: String(value.lang || "").trim(),
    rate: clamp(value.rate, 0.5, 1.75, DEFAULT_VOICE_PACK.rate),
    pitch: clamp(value.pitch, 0.5, 1.5, DEFAULT_VOICE_PACK.pitch),
    volume: clamp(value.volume, 0.0, 1.0, DEFAULT_VOICE_PACK.volume)
  };
}

export function loadSavedVoicePack() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_VOICE_PACK };
    return normalizeVoicePack(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_VOICE_PACK };
  }
}

export function saveVoicePack(value) {
  const pack = normalizeVoicePack(value);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(pack));
  return pack;
}

export function clearSavedVoicePack() {
  localStorage.removeItem(STORAGE_KEY);
}

export function resolveVoice(pack, voices) {
  const normalized = normalizeVoicePack(pack);
  if (!Array.isArray(voices) || voices.length === 0) return null;

  if (normalized.voiceURI) {
    const byUri = voices.find((voice) => voice.voiceURI === normalized.voiceURI);
    if (byUri) return byUri;
  }

  if (normalized.voiceName) {
    const byNameAndLang = voices.find(
      (voice) =>
        voice.name === normalized.voiceName &&
        (!normalized.lang || voice.lang === normalized.lang)
    );
    if (byNameAndLang) return byNameAndLang;

    const byName = voices.find((voice) => voice.name === normalized.voiceName);
    if (byName) return byName;
  }

  return null;
}

export function applyVoicePack(utterance, pack, voices = []) {
  const normalized = normalizeVoicePack(pack);
  utterance.rate = normalized.rate;
  utterance.pitch = normalized.pitch;
  utterance.volume = normalized.volume;

  const voice = resolveVoice(normalized, voices);
  if (voice) utterance.voice = voice;

  return normalized;
}
