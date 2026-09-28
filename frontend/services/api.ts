import type {
  AlternativesResponse,
  ConversationMessageItem,
  ConversationSessionItem,
  ConversationSessionListResponse,
  DetectLanguageResponse,
  DocumentItem,
  DocumentListResponse,
  HistoryListResponse,
  ImageTranslateResponse,
  InputMethod,
  OCRExtractResponse,
  OfflineStatusResponse,
  TranscribeResponse,
  TranslateResponse,
  TranslationMode,
  TranslationStyle,
} from "@/types/language";
import { getAudioFilename, ensureValidAudioBlob } from "@/lib/audioRecorder";


const rawApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
const API_URL = (rawApiUrl || "http://localhost:8000").replace(/\/+$/, "");

async function parseError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string | { msg?: string }[] };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    // ignore parse errors
  }
  if (response.status === 413) {
    return "Audio file is too large. Please record a shorter message.";
  }
  if (response.status === 503) {
    return "Translation or speech service is temporarily unavailable. Please try again.";
  }
  if (response.status >= 500) {
    return "Something went wrong on our side. Please try again.";
  }
  return "Unable to complete the request. Please check your input and try again.";
}

export async function translateText(payload: {
  source_language: string;
  target_language: string;
  text: string;
  translation_style?: TranslationStyle;
  input_method?: InputMethod;
  mode?: TranslationMode;
}): Promise<TranslateResponse> {
  const response = await fetch(`${API_URL}/api/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_language: payload.source_language,
      target_language: payload.target_language,
      text: payload.text,
      translation_style: payload.translation_style ?? "general",
      input_method: payload.input_method ?? "text",
      mode: payload.mode ?? "auto",
    }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function fetchOfflineStatus(): Promise<OfflineStatusResponse> {
  const response = await fetch(`${API_URL}/api/offline/status`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}


export async function detectLanguage(text: string): Promise<DetectLanguageResponse> {
  const response = await fetch(`${API_URL}/api/detect-language`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function fetchAlternatives(payload: {
  source_language: string;
  target_language: string;
  text: string;
  translation_style?: TranslationStyle;
}): Promise<AlternativesResponse> {
  const response = await fetch(`${API_URL}/api/translate/alternatives`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_language: payload.source_language,
      target_language: payload.target_language,
      text: payload.text,
      translation_style: payload.translation_style ?? "general",
    }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function transcribeAudio(audioBlob: Blob, language?: string): Promise<TranscribeResponse> {
  const validBlob = ensureValidAudioBlob(audioBlob);
  const filename = getAudioFilename(validBlob, "recording");
  const formData = new FormData();
  formData.append("file", validBlob, filename);
  if (language && language !== "auto") {
    formData.append("language", language);
  }

  const response = await fetch(`${API_URL}/api/speech/transcribe`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function synthesizeSpeech(payload: {
  text: string;
  language: string;
  speed?: number;
  voice?: string;
}): Promise<Blob> {
  const response = await fetch(`${API_URL}/api/speech/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: payload.text,
      language: payload.language,
      speed: payload.speed ?? 1.0,
      voice: payload.voice ?? null,
    }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.blob();
}

export async function fetchHistory(): Promise<HistoryListResponse> {
  const response = await fetch(`${API_URL}/api/history`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function deleteHistoryItem(id: number): Promise<void> {
  const response = await fetch(`${API_URL}/api/history/${id}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
}

export async function extractOCR(imageFile: File | Blob, filename?: string): Promise<OCRExtractResponse> {
  const formData = new FormData();
  formData.append("image", imageFile, filename || (imageFile instanceof File ? imageFile.name : "image.png"));

  const response = await fetch(`${API_URL}/api/ocr/extract`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function translateImage(payload: {
  imageFile: File | Blob;
  targetLanguage: string;
  sourceLanguage?: string;
  translationStyle?: TranslationStyle;
  filename?: string;
}): Promise<ImageTranslateResponse> {
  const formData = new FormData();
  formData.append(
    "image",
    payload.imageFile,
    payload.filename || (payload.imageFile instanceof File ? payload.imageFile.name : "image.png")
  );
  formData.append("target_language", payload.targetLanguage);
  formData.append("source_language", payload.sourceLanguage ?? "auto");
  formData.append("translation_style", payload.translationStyle ?? "general");

  const response = await fetch(`${API_URL}/api/image/translate`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function translateDocument(payload: {
  file: File | Blob;
  targetLanguage: string;
  sourceLanguage?: string;
  translationStyle?: TranslationStyle;
  filename?: string;
}): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append(
    "file",
    payload.file,
    payload.filename || (payload.file instanceof File ? payload.file.name : "document.txt")
  );
  formData.append("target_language", payload.targetLanguage);
  formData.append("source_language", payload.sourceLanguage ?? "auto");
  formData.append("translation_style", payload.translationStyle ?? "general");

  const response = await fetch(`${API_URL}/api/documents/translate`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function translateDocxDocument(payload: {
  file: File | Blob;
  targetLanguage: string;
  sourceLanguage?: string;
  translationStyle?: TranslationStyle;
  filename?: string;
}): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append(
    "file",
    payload.file,
    payload.filename || (payload.file instanceof File ? payload.file.name : "document.docx")
  );
  formData.append("target_language", payload.targetLanguage);
  formData.append("source_language", payload.sourceLanguage ?? "auto");
  formData.append("translation_style", payload.translationStyle ?? "general");

  const response = await fetch(`${API_URL}/api/documents/docx/translate`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function listDocuments(): Promise<DocumentListResponse> {
  const response = await fetch(`${API_URL}/api/documents`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function deleteDocument(docId: number): Promise<void> {
  const response = await fetch(`${API_URL}/api/documents/${docId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
}

export function getDocumentDownloadUrl(docId: number): string {
  return `${API_URL}/api/documents/${docId}/download`;
}

// ============================================================================
// Stage 3 Part 5: Conversation Mode API
// ============================================================================

export async function createConversationSession(payload: {
  language_a: string;
  language_b: string;
  title?: string;
}): Promise<ConversationSessionItem> {
  const response = await fetch(`${API_URL}/api/conversations/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function listConversationSessions(params?: {
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<ConversationSessionListResponse> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));

  const qs = query.toString() ? `?${query.toString()}` : "";
  const response = await fetch(`${API_URL}/api/conversations/sessions${qs}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function getConversationSession(
  sessionId: number
): Promise<ConversationSessionItem> {
  const response = await fetch(`${API_URL}/api/conversations/sessions/${sessionId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function deleteConversationSession(sessionId: number): Promise<void> {
  const response = await fetch(`${API_URL}/api/conversations/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
}

export async function swapConversationSession(
  sessionId: number
): Promise<ConversationSessionItem> {
  const response = await fetch(
    `${API_URL}/api/conversations/sessions/${sessionId}/swap`,
    {
      method: "POST",
    }
  );
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function updateConversationSession(
  sessionId: number,
  payload: { language_a?: string; language_b?: string; title?: string }
): Promise<ConversationSessionItem> {
  const response = await fetch(`${API_URL}/api/conversations/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function sendConversationMessage(
  sessionId: number,
  payload: {
    speaker: "speaker_a" | "speaker_b";
    text: string;
  }
): Promise<ConversationMessageItem> {
  const response = await fetch(
    `${API_URL}/api/conversations/sessions/${sessionId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export async function sendConversationAudioMessage(
  sessionId: number,
  payload: {
    speaker: "speaker_a" | "speaker_b";
    audioBlob: Blob;
    contentType?: string;
  }
): Promise<ConversationMessageItem> {
  const fallbackMime = payload.contentType || "audio/webm";
  const validBlob = ensureValidAudioBlob(payload.audioBlob, fallbackMime);
  const filename = getAudioFilename(validBlob, `speech_${payload.speaker}`);
  const formData = new FormData();
  formData.append("speaker", payload.speaker);
  formData.append("file", validBlob, filename);

  const response = await fetch(
    `${API_URL}/api/conversations/sessions/${sessionId}/messages/audio`,
    {
      method: "POST",
      body: formData,
    }
  );
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

// ============================================================================
// Stage 4: Real-Time Voice Translation API
// ============================================================================

export function getVoiceWebSocketUrl(params?: {
  sourceLanguage?: string;
  targetLanguage?: string;
  translationStyle?: string;
}): string {
  const wsBase = (process.env.NEXT_PUBLIC_WS_URL?.trim() || API_URL)
    .replace(/^http:\/\//i, "ws://")
    .replace(/^https:\/\//i, "wss://")
    .replace(/\/+$/, "");
  const query = new URLSearchParams();
  if (params?.sourceLanguage) query.set("source_language", params.sourceLanguage);
  if (params?.targetLanguage) query.set("target_language", params.targetLanguage);
  if (params?.translationStyle) query.set("translation_style", params.translationStyle);
  const qs = query.toString() ? `?${query.toString()}` : "";
  return `${wsBase}/api/voice/stream${qs}`;
}

export async function translateVoiceSpeech(payload: {
  audioBlob: Blob;
  targetLanguage: string;
  sourceLanguage?: string;
  translationStyle?: TranslationStyle;
}): Promise<TranslateResponse> {
  const validBlob = ensureValidAudioBlob(payload.audioBlob);
  const filename = getAudioFilename(validBlob, "recording");
  const formData = new FormData();
  formData.append("file", validBlob, filename);
  formData.append("target_language", payload.targetLanguage);
  formData.append("source_language", payload.sourceLanguage ?? "auto");
  formData.append("translation_style", payload.translationStyle ?? "general");

  const response = await fetch(`${API_URL}/api/voice/translate-speech`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}




