/**
 * Audio Recording Helper Utilities
 * Handles browser-supported MIME type detection and file naming.
 */

export const PREFERRED_AUDIO_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/wav",
] as const;

/**
 * Detect a browser-supported MIME type safely in preferred order:
 * 1. audio/webm;codecs=opus
 * 2. audio/webm
 * 3. audio/mp4
 * 4. audio/wav
 */
export function getSupportedAudioMimeType(): string {
  if (typeof window === "undefined" || typeof MediaRecorder === "undefined") {
    return "audio/webm";
  }

  for (const candidate of PREFERRED_AUDIO_MIME_TYPES) {
    try {
      if (
        typeof MediaRecorder.isTypeSupported === "function" &&
        MediaRecorder.isTypeSupported(candidate)
      ) {
        return candidate;
      }
    } catch {
      // Ignore and proceed to next candidate
    }
  }

  // Fallback if none explicitly reported true
  return "";
}

/**
 * Returns matching file extension (.webm, .mp4, .wav, .ogg) for given MIME type.
 */
export function getAudioExtensionFromMime(mimeType: string): string {
  const normalized = (mimeType || "").toLowerCase();
  if (normalized.includes("wav") || normalized.includes("wave")) {
    return "wav";
  }
  if (
    normalized.includes("mp4") ||
    normalized.includes("m4a") ||
    normalized.includes("aac")
  ) {
    return "mp4";
  }
  if (normalized.includes("ogg") || normalized.includes("opus")) {
    return "ogg";
  }
  return "webm";
}

/**
 * Generates an appropriate filename with extension matching the Blob MIME type.
 */
export function getAudioFilename(blob: Blob, baseName: string = "recording"): string {
  const ext = getAudioExtensionFromMime(blob.type);
  return `${baseName}.${ext}`;
}

/**
 * Ensures a Blob has a concrete audio MIME type instead of empty or generic application/octet-stream.
 */
export function ensureValidAudioBlob(blob: Blob, fallbackMime: string = "audio/webm"): Blob {
  if (!blob.type || blob.type === "application/octet-stream") {
    return new Blob([blob], { type: fallbackMime });
  }
  return blob;
}

