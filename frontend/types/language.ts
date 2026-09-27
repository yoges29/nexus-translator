export type TextDirection = "ltr" | "rtl";
export type TranslationStyle = "general" | "formal" | "casual";
export type InputMethod = "text" | "voice";

export interface Language {
  code: string;
  name: string;
  nativeName: string;
  direction: TextDirection;
  translationSupported: boolean;
  detectOnly?: boolean;
}

export type TranslationMode = "auto" | "online" | "offline";

export interface TranslateResponse {
  source_language: string;
  target_language: string;
  original_text: string;
  translated_text: string;
  translation_style?: TranslationStyle;
  input_method?: InputMethod;
  detected_language?: string | null;
  history_id?: number | null;
  is_offline?: boolean;
  provider_used?: string;
}


export interface AlternativesResponse {
  primary: string;
  alternatives: string[];
}

export interface DetectLanguageResponse {
  language: string;
  language_name?: string | null;
  confidence?: number | null;
}

export interface TranscribeResponse {
  text: string;
  language?: string | null;
  confidence?: number | null;
}

export interface HistoryItem {
  id: number;
  user_id: number | null;
  source_language: string;
  target_language: string;
  original_text: string;
  translated_text: string;
  detected_language?: string | null;
  translation_style?: TranslationStyle;
  input_method?: InputMethod;
  created_at: string;
}

export interface HistoryListResponse {
  items: HistoryItem[];
  total: number;
}

export interface VoiceSettings {
  preferredVoice: string;
  speechSpeed: number; // 0.75, 1.0, 1.25, 1.5
  autoTranslateAfterSpeaking: boolean;
  autoPlayTranslation: boolean;
}

export interface ApiError {
  detail: string;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface OCRRegion {
  text: string;
  bounding_box: BoundingBox;
  confidence?: number | null;
  translated_text?: string | null;
}

export interface OfflinePairItem {
  source: string;
  target: string;
}

export interface OfflineStatusResponse {
  online_available: boolean;
  current_mode: string;
  supported_pairs: OfflinePairItem[];
}


export interface OCRExtractResponse {
  text: string;
  language?: string | null;
  regions: OCRRegion[];
}

export interface ImageTranslateResponse {
  source_language: string;
  target_language: string;
  extracted_text: string;
  translated_text: string;
  detected_language?: string | null;
  translation_style: string;
  regions: OCRRegion[];
  history_id?: number | null;
}

export interface DocumentItem {
  id: number;
  user_id: number | null;
  filename: string;
  document_type: string; // 'pdf' | 'txt'
  file_size: number;
  source_language: string;
  target_language: string;
  page_count: number;
  original_text_sample: string;
  translated_text_sample: string;
  status: string;
  download_filename: string;
  download_url?: string | null;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
}

export interface ConversationMessageItem {
  id: number;
  session_id: number;
  speaker: "speaker_a" | "speaker_b";
  source_language: string;
  target_language: string;
  original_text: string;
  translated_text: string;
  created_at: string;
}

export interface ConversationSessionItem {
  id: number;
  user_id: number | null;
  title: string;
  language_a: string;
  language_b: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: ConversationMessageItem[];
}

export interface ConversationSessionListResponse {
  items: ConversationSessionItem[];
  total: number;
}


