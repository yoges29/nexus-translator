"use client";

import { ActionButton } from "@/components/ActionButton";
import { LanguageSelect } from "@/components/LanguageSelect";
import { VoiceSettingsModal } from "@/components/VoiceSettingsModal";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import { useCopyFeedback } from "@/hooks/useCopyFeedback";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { useVoiceSettings } from "@/hooks/useVoiceSettings";
import { getLanguageByCode, getSourceLanguages, getTranslatableLanguages } from "@/lib/languages";
import { detectLanguage, fetchAlternatives, fetchOfflineStatus, translateText } from "@/services/api";
import type { InputMethod, OfflineStatusResponse, TranslateResponse, TranslationMode, TranslationStyle } from "@/types/language";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const MAX_CHAR_COUNT = 20000;

interface TranslatorWorkspaceProps {
  onHistoryRefresh?: () => void;
  externalReuse?: {
    source: string;
    target: string;
    sourceText: string;
    translatedText: string;
  } | null;
  onReuseApplied?: () => void;
}

export function TranslatorWorkspace({
  onHistoryRefresh,
  externalReuse,
  onReuseApplied,
}: TranslatorWorkspaceProps) {
  const sourceLanguages = useMemo(() => getSourceLanguages(), []);
  const targetLanguages = useMemo(() => getTranslatableLanguages(), []);

  const [sourceLanguage, setSourceLanguage] = useState("auto");
  const [targetLanguage, setTargetLanguage] = useState("ta");
  const [sourceText, setSourceText] = useState("");
  const [translatedText, setTranslatedText] = useState("");
  const [detectedLanguage, setDetectedLanguage] = useState<string | null>(null);
  const [detectedLanguageName, setDetectedLanguageName] = useState<string | null>(null);
  const [translationStyle, setTranslationStyle] = useState<TranslationStyle>("general");
  const [translationMode, setTranslationMode] = useState<TranslationMode>("auto");
  const [isOfflineResult, setIsOfflineResult] = useState<boolean | null>(null);
  const [providerUsed, setProviderUsed] = useState<string | null>(null);
  const [offlineStatus, setOfflineStatus] = useState<OfflineStatusResponse | null>(null);
  const [alternatives, setAlternatives] = useState<string[]>([]);
  const [isLoadingAlternatives, setIsLoadingAlternatives] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);


  const { copiedField, copy } = useCopyFeedback();
  const { settings, updateSettings } = useVoiceSettings();

  const audioPlayer = useAudioPlayer({
    onError: (msg) => setError(msg),
  });

  const handleTranscriptionComplete = useCallback(
    async (transcribedText: string, detectedLang?: string | null) => {
      setSourceText(transcribedText);
      if (detectedLang) {
        setDetectedLanguage(detectedLang);
        const meta = getLanguageByCode(detectedLang);
        if (meta) setDetectedLanguageName(meta.name);
      }
      setError(null);

      // Auto-translate workflow if setting is enabled
      if (settings.autoTranslateAfterSpeaking && transcribedText.trim()) {
        void executeTranslation(transcribedText, "voice");
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [settings.autoTranslateAfterSpeaking, sourceLanguage, targetLanguage, translationStyle],
  );

  const voiceRecorder = useVoiceRecorder({
    language: sourceLanguage === "auto" ? undefined : sourceLanguage,
    onTranscriptionComplete: handleTranscriptionComplete,
    onError: (msg) => setError(msg),
  });

  // Debounced auto-detection when user is typing in "auto" mode
  const detectTimerRef = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => {
    if (sourceLanguage !== "auto" || !sourceText.trim() || sourceText.length < 3) {
      if (sourceLanguage !== "auto") {
        setDetectedLanguage(null);
        setDetectedLanguageName(null);
      }
      return;
    }

    if (detectTimerRef.current) clearTimeout(detectTimerRef.current);

    detectTimerRef.current = setTimeout(async () => {
      try {
        const result = await detectLanguage(sourceText.slice(0, 300));
        if (result.language && result.language !== "auto") {
          setDetectedLanguage(result.language);
          const meta = getLanguageByCode(result.language);
          setDetectedLanguageName(meta ? meta.name : result.language_name ?? result.language.toUpperCase());
        }
      } catch {
        // quiet ignore for auto-detect debounced preview
      }
    }, 600);

    return () => {
      if (detectTimerRef.current) clearTimeout(detectTimerRef.current);
    };
  }, [sourceText, sourceLanguage]);

  useEffect(() => {
    fetchOfflineStatus()
      .then(setOfflineStatus)
      .catch(() => {});
  }, []);

  const isOfflinePairSupported = useMemo(() => {
    const src = sourceLanguage === "auto" ? detectedLanguage ?? "en" : sourceLanguage;
    const tgt = targetLanguage;
    if (offlineStatus?.supported_pairs && offlineStatus.supported_pairs.length > 0) {
      return offlineStatus.supported_pairs.some(
        (p) => p.source === src && p.target === tgt,
      );
    }
    const defaultPairs = [
      "en-ta", "ta-en",
      "en-es", "es-en",
      "en-fr", "fr-en",
      "en-de", "de-en",
      "en-hi", "hi-en",
    ];
    return defaultPairs.includes(`${src}-${tgt}`);
  }, [sourceLanguage, targetLanguage, detectedLanguage, offlineStatus]);

  const applyReuse = useCallback(
    (payload: { source: string; target: string; sourceText: string; translatedText: string }) => {
      setSourceLanguage(payload.source);
      setTargetLanguage(payload.target);
      setSourceText(payload.sourceText);
      setTranslatedText(payload.translatedText);
      setDetectedLanguage(payload.source === "auto" ? null : payload.source);
      setAlternatives([]);
      setError(null);
    },
    [],
  );

  useEffect(() => {
    if (!externalReuse) return;
    applyReuse(externalReuse);
    onReuseApplied?.();
  }, [externalReuse, applyReuse, onReuseApplied]);

  const sourceDirection = getLanguageByCode(
    sourceLanguage === "auto" ? detectedLanguage ?? "en" : sourceLanguage,
  )?.direction;
  const targetDirection = getLanguageByCode(targetLanguage)?.direction;

  const translationCacheRef = useRef<Map<string, TranslateResponse>>(new Map());

  const executeTranslation = async (textToTranslate: string, inputMethod: InputMethod = "text") => {
    const text = textToTranslate.trim();
    if (!text || isTranslating) return;

    if (text.length > MAX_CHAR_COUNT) {
      setError(`Text exceeds maximum length of ${MAX_CHAR_COUNT.toLocaleString()} characters.`);
      return;
    }

    // Cancel any pending debounced auto-detection to avoid wasted network calls
    if (detectTimerRef.current) {
      clearTimeout(detectTimerRef.current);
      detectTimerRef.current = null;
    }

    // Check client-side translation cache
    const cacheKey = `${sourceLanguage}:${targetLanguage}:${translationStyle}:${translationMode}:${text}`;
    const cached = translationCacheRef.current.get(cacheKey);
    if (cached) {
      setTranslatedText(cached.translated_text);
      setIsOfflineResult(cached.is_offline ?? false);
      setProviderUsed(cached.provider_used ?? (cached.is_offline ? "offline_local" : "online"));
      if (cached.detected_language) {
        setDetectedLanguage(cached.detected_language);
        const meta = getLanguageByCode(cached.detected_language);
        if (meta) setDetectedLanguageName(meta.name);
      }
      setError(null);
      return;
    }

    setIsTranslating(true);
    setError(null);
    setAlternatives([]);

    try {
      const result = await translateText({
        source_language: sourceLanguage,
        target_language: targetLanguage,
        text,
        translation_style: translationStyle,
        input_method: inputMethod,
        mode: translationMode,
      });

      // Display main translation immediately
      setTranslatedText(result.translated_text);
      setIsOfflineResult(result.is_offline ?? false);
      setProviderUsed(result.provider_used ?? (result.is_offline ? "offline_local" : "online"));
      if (result.detected_language) {
        setDetectedLanguage(result.detected_language);
        const meta = getLanguageByCode(result.detected_language);
        if (meta) setDetectedLanguageName(meta.name);
      }

      // Store in client-side cache (bounded to 100 items)
      if (translationCacheRef.current.size >= 100) {
        const firstKey = translationCacheRef.current.keys().next().value;
        if (firstKey) translationCacheRef.current.delete(firstKey);
      }
      translationCacheRef.current.set(cacheKey, result);

      onHistoryRefresh?.();

      // Auto-read aloud if enabled
      if (settings.autoPlayTranslation && result.translated_text) {
        void audioPlayer.play(
          result.translated_text,
          result.target_language,
          settings.speechSpeed,
        );
      }

      // Fetch alternatives asynchronously in background (only for short/medium phrases)
      if (text.length <= 1000) {
        void loadAlternatives(text, result.source_language, result.target_language, translationStyle);
      }
    } catch (err) {
      setTranslatedText("");
      setError(err instanceof Error ? err.message : "Translation failed. Please try again.");
    } finally {
      setIsTranslating(false);
    }
  };


  const loadAlternatives = async (
    text: string,
    source: string,
    target: string,
    style: TranslationStyle,
  ) => {
    setIsLoadingAlternatives(true);
    try {
      const altResult = await fetchAlternatives({
        source_language: source,
        target_language: target,
        text,
        translation_style: style,
      });
      setAlternatives(altResult.alternatives || []);
    } catch {
      // Alternatives are supplementary; do not overwrite translation error
    } finally {
      setIsLoadingAlternatives(false);
    }
  };

  const handleTranslate = () => {
    void executeTranslation(sourceText, "text");
  };

  const handleSwap = () => {
    const nextSource = targetLanguage;
    let nextTarget = sourceLanguage;
    if (sourceLanguage === "auto") {
      nextTarget = detectedLanguage ?? "en";
    }
    if (nextSource === nextTarget) return;

    setSourceLanguage(nextSource);
    setTargetLanguage(nextTarget);
    setSourceText(translatedText || sourceText);
    setTranslatedText(sourceText);
    setAlternatives([]);
    if (nextSource !== "auto") {
      setDetectedLanguage(nextSource);
      const meta = getLanguageByCode(nextSource);
      setDetectedLanguageName(meta ? meta.name : nextSource.toUpperCase());
    } else {
      setDetectedLanguage(null);
      setDetectedLanguageName(null);
    }
    setError(null);
  };

  const handleClear = () => {
    setSourceText("");
    setTranslatedText("");
    setAlternatives([]);
    setDetectedLanguage(null);
    setDetectedLanguageName(null);
    setError(null);
    audioPlayer.stop();
  };

  const handleApplyAlternative = (altText: string) => {
    setTranslatedText(altText);
  };

  const charCount = sourceText.length;
  const isOverLimit = charCount > MAX_CHAR_COUNT;

  return (
    <section aria-label="Translator workspace" className="space-y-6">
      {/* Top Bar: Language Selectors, Swap, Translation Style, Settings */}
      <div className="flex flex-col items-stretch gap-4 lg:flex-row lg:items-end">
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <label htmlFor="source-language" className="block text-xs font-semibold uppercase tracking-wider text-nexus-muted">
              Source Language
            </label>
            {sourceLanguage === "auto" && detectedLanguageName ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-nexus-accent/15 px-2.5 py-0.5 text-[11px] font-medium text-nexus-accent animate-fade-in">
                <span className="h-1.5 w-1.5 rounded-full bg-nexus-accent animate-pulse" />
                Detected: {detectedLanguageName}
              </span>
            ) : null}
          </div>
          <div className="mt-1.5">
            <LanguageSelect
              id="source-language"
              label="Source language"
              value={sourceLanguage}
              languages={sourceLanguages}
              onChange={(val) => {
                setSourceLanguage(val);
                if (val !== "auto") {
                  setDetectedLanguage(val);
                  const meta = getLanguageByCode(val);
                  setDetectedLanguageName(meta ? meta.name : val.toUpperCase());
                } else {
                  setDetectedLanguage(null);
                  setDetectedLanguageName(null);
                }
              }}
            />
          </div>
        </div>

        <div className="flex justify-center lg:pb-1">
          <button
            type="button"
            onClick={handleSwap}
            className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-nexus-border bg-nexus-surface text-lg text-nexus-accent shadow-nexus transition hover:scale-105 hover:border-nexus-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-nexus-accent"
            aria-label="Swap source and target languages"
            title="Swap languages"
          >
            ⇄
          </button>
        </div>

        <div className="flex-1">
          <label htmlFor="target-language" className="block text-xs font-semibold uppercase tracking-wider text-nexus-muted">
            Target Language
          </label>
          <div className="mt-1.5">
            <LanguageSelect
              id="target-language"
              label="Target language"
              value={targetLanguage}
              languages={targetLanguages}
              onChange={setTargetLanguage}
            />
          </div>
        </div>
      </div>

      {/* Toolbar: Translation Style Selector, Offline Engine Selector & Voice Settings Button */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-nexus-border/70 bg-nexus-panel/60 px-4 py-2.5 shadow-sm">
        <div className="flex flex-wrap items-center gap-4">
          {/* Style */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-nexus-muted">
              Style:
            </span>
            {(
              [
                ["general", "General"],
                ["formal", "Formal"],
                ["casual", "Casual"],
              ] as const
            ).map(([styleKey, styleLabel]) => (
              <button
                key={styleKey}
                type="button"
                onClick={() => {
                  setTranslationStyle(styleKey);
                  if (translatedText && sourceText.trim()) {
                    void executeTranslation(sourceText, "text");
                  }
                }}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  translationStyle === styleKey
                    ? "bg-nexus-accent text-white shadow-nexus"
                    : "border border-nexus-border/60 bg-nexus-surface text-nexus-muted hover:border-nexus-accent hover:text-nexus-foreground"
                }`}
              >
                {styleLabel}
              </button>
            ))}
          </div>

          <div className="hidden h-4 w-px bg-nexus-border sm:block" />

          {/* Engine Mode (Stage 4.2 Offline Architecture) */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-nexus-muted">
              Engine:
            </span>
            {(
              [
                ["auto", "Auto (Fallback)"],
                ["online", "Online"],
                ["offline", "Offline"],
              ] as const
            ).map(([mKey, mLabel]) => (
              <button
                key={mKey}
                type="button"
                onClick={() => setTranslationMode(mKey as TranslationMode)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  translationMode === mKey
                    ? mKey === "offline"
                      ? "bg-amber-600 text-white shadow-sm"
                      : "bg-nexus-accent text-white shadow-nexus"
                    : "border border-nexus-border/60 bg-nexus-surface text-nexus-muted hover:border-nexus-accent hover:text-nexus-foreground"
                }`}
              >
                {mKey === "offline" ? "⚡ " : mKey === "online" ? "☁ " : "🔄 "}
                {mLabel}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsSettingsOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-full border border-nexus-border bg-nexus-surface px-3 py-1 text-xs font-medium text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
            aria-label="Voice and audio settings"
          >
            <span>🎙️</span>
            <span>Audio Settings ({settings.speechSpeed}x)</span>
          </button>
        </div>
      </div>

      {/* Offline Status & Pair Notice Banner */}
      {translationMode === "offline" && (
        <div
          className={`rounded-xl border p-3 text-xs flex items-center justify-between ${
            isOfflinePairSupported
              ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
              : "border-rose-500/30 bg-rose-500/10 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-2">
            <span>{isOfflinePairSupported ? "⚡" : "⚠️"}</span>
            <span>
              {isOfflinePairSupported
                ? "Offline Mode Active: Translating locally using offline lexical model. No internet connection required."
                : "Unsupported Offline Pair: Offline translation is available for EN ↔ TA, EN ↔ ES, EN ↔ FR, EN ↔ DE, EN ↔ HI. Please switch to Online mode or pick a supported pair."}
            </span>
          </div>
          <span className="text-[11px] font-semibold uppercase tracking-wider opacity-85">
            {isOfflinePairSupported ? "Offline Ready" : "Requires Online"}
          </span>
        </div>
      )}


      {/* Translation Workspace Grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Source Box */}
        <div className="flex flex-col gap-3">
          <div className="relative overflow-hidden rounded-2xl border border-nexus-border bg-nexus-panel shadow-nexus transition focus-within:border-nexus-accent/60">
            <textarea
              value={sourceText}
              onChange={(event) => setSourceText(event.target.value)}
              onKeyDown={(event) => {
                if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                  event.preventDefault();
                  handleTranslate();
                }
              }}
              placeholder="Enter text or click the microphone to speak..."
              dir={sourceDirection ?? "ltr"}
              maxLength={MAX_CHAR_COUNT}
              className="min-h-[220px] w-full resize-y bg-transparent px-4 py-4 text-base leading-relaxed text-nexus-foreground placeholder:text-nexus-muted/70 focus-visible:outline-none"
              aria-label="Source text"
            />
            {/* Character counter */}
            <div className="absolute bottom-3 right-4 select-none text-[11px] font-mono text-nexus-muted">
              <span className={isOverLimit ? "font-bold text-red-500" : ""}>{charCount}</span> / {MAX_CHAR_COUNT}
            </div>
          </div>

          {/* Source Action Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              {/* Microphone Button with Dynamic States */}
              {voiceRecorder.state === "listening" ? (
                <button
                  type="button"
                  onClick={voiceRecorder.stopRecording}
                  className="inline-flex items-center gap-2 rounded-full border border-red-500/40 bg-red-500/10 px-3.5 py-1.5 text-xs font-medium text-red-500 animate-pulse transition hover:bg-red-500/20"
                  aria-label="Stop recording"
                  title="Click to stop recording"
                >
                  <span className="h-2 w-2 rounded-full bg-red-500 animate-ping" />
                  <span>Recording... ({voiceRecorder.recordingDuration}s)</span>
                  <span className="font-bold">⏹</span>
                </button>
              ) : voiceRecorder.state === "processing" ? (
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center gap-1.5 rounded-full border border-nexus-accent/40 bg-nexus-accent/10 px-3.5 py-1.5 text-xs font-medium text-nexus-accent"
                  aria-label="Processing speech..."
                >
                  <span className="inline-block animate-spin">⏳</span>
                  <span>Transcribing...</span>
                </button>
              ) : voiceRecorder.state === "complete" ? (
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3.5 py-1.5 text-xs font-medium text-emerald-500"
                  aria-label="Speech transcribed successfully"
                >
                  <span>✓</span>
                  <span>Text added</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={voiceRecorder.startRecording}
                  className="inline-flex items-center gap-1.5 rounded-full border border-nexus-border bg-nexus-surface px-3.5 py-1.5 text-xs font-medium text-nexus-foreground transition hover:border-nexus-accent hover:text-nexus-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-nexus-accent"
                  aria-label="Start voice input"
                  title="Speak into microphone"
                >
                  <span>🎤</span>
                  <span>Speak</span>
                </button>
              )}

              <ActionButton
                label="Copy"
                confirmLabel="Copied ✓"
                showConfirm={copiedField === "source"}
                onClick={() => copy(sourceText, "source")}
                disabled={!sourceText.trim()}
              />
              <ActionButton label="Clear" onClick={handleClear} disabled={!sourceText && !translatedText} />
            </div>

            <span className="text-[10px] uppercase tracking-wider text-nexus-muted">
              Input
            </span>
          </div>

          <p className="text-[11px] text-nexus-muted/80">
            🔒 Audio is processed securely and never stored on disk.
          </p>
        </div>

        {/* Target Translation Box */}
        <div className="flex flex-col gap-3">
          <div className="relative overflow-hidden rounded-2xl border border-nexus-border bg-nexus-panel shadow-nexus">
            <textarea
              value={isTranslating ? "Translating..." : translatedText}
              readOnly
              placeholder="Translation will appear here..."
              dir={targetDirection ?? "ltr"}
              className="min-h-[220px] w-full resize-y bg-transparent px-4 py-4 text-base leading-relaxed text-nexus-foreground placeholder:text-nexus-muted/70 focus-visible:outline-none"
              aria-label="Translated text"
              aria-busy={isTranslating}
            />
            {isTranslating ? (
              <div className="pointer-events-none absolute inset-0 animate-pulse bg-nexus-accent/5" aria-hidden />
            ) : null}
          </div>

          {/* Target Action Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <ActionButton
                label="Copy"
                confirmLabel="Copied ✓"
                showConfirm={copiedField === "target"}
                onClick={() => copy(translatedText, "target")}
                disabled={!translatedText.trim()}
              />

              {/* Text-to-Speech Button with Play/Pause/Loading states */}
              {audioPlayer.isLoading ? (
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center gap-1.5 rounded-full border border-nexus-accent/40 bg-nexus-accent/10 px-3.5 py-1.5 text-xs font-medium text-nexus-accent"
                  aria-label="Synthesizing speech..."
                >
                  <span className="inline-block animate-spin">⏳</span>
                  <span>Synthesizing...</span>
                </button>
              ) : audioPlayer.isPlaying ? (
                <div className="inline-flex items-center gap-1.5 rounded-full border border-nexus-accent bg-nexus-accent/10 px-3 py-1 text-xs font-medium text-nexus-accent animate-pulse">
                  <button
                    type="button"
                    onClick={audioPlayer.pause}
                    aria-label="Pause speech"
                    className="hover:opacity-80"
                    title="Pause audio"
                  >
                    ⏸ Pause
                  </button>
                  <button
                    type="button"
                    onClick={audioPlayer.stop}
                    aria-label="Stop speech"
                    className="hover:opacity-80 font-bold"
                    title="Stop audio"
                  >
                    ⏹
                  </button>
                </div>
              ) : audioPlayer.isPaused ? (
                <div className="inline-flex items-center gap-1.5 rounded-full border border-nexus-accent/50 bg-nexus-surface px-3 py-1 text-xs font-medium text-nexus-accent">
                  <button
                    type="button"
                    onClick={audioPlayer.resume}
                    aria-label="Resume speech"
                    className="hover:opacity-80"
                    title="Resume audio"
                  >
                    ▶ Resume
                  </button>
                  <button
                    type="button"
                    onClick={audioPlayer.stop}
                    aria-label="Stop speech"
                    className="hover:opacity-80 font-bold"
                    title="Stop audio"
                  >
                    ⏹
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  disabled={!translatedText.trim()}
                  onClick={() =>
                    audioPlayer.play(translatedText, targetLanguage, settings.speechSpeed)
                  }
                  className="inline-flex items-center gap-1.5 rounded-full border border-nexus-border bg-nexus-surface px-3.5 py-1.5 text-xs font-medium text-nexus-foreground transition hover:border-nexus-accent hover:text-nexus-accent disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label="Listen to translation"
                  title="Read aloud"
                >
                  <span>🔊</span>
                  <span>Listen</span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              {providerUsed && (
                <span
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                    isOfflineResult
                      ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                      : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  }`}
                >
                  {isOfflineResult ? "⚡ Offline Engine" : "☁ Online Cloud"}
                </span>
              )}
              <span className="text-[10px] uppercase tracking-wider text-nexus-muted">
                Output
              </span>
            </div>

          </div>

          {/* Translation Alternatives Section */}
          {alternatives.length > 0 ? (
            <div className="rounded-2xl border border-nexus-border/80 bg-nexus-surface/50 p-4 animate-fade-in">
              <p className="text-xs font-semibold uppercase tracking-wider text-nexus-muted">
                Alternative Translations:
              </p>
              <ul className="mt-2 space-y-2">
                {alternatives.map((alt, idx) => (
                  <li
                    key={idx}
                    className="group flex items-center justify-between gap-3 rounded-xl border border-nexus-border/50 bg-nexus-panel p-2.5 transition hover:border-nexus-accent/40"
                  >
                    <p className="text-sm text-nexus-foreground">{alt}</p>
                    <button
                      type="button"
                      onClick={() => handleApplyAlternative(alt)}
                      className="shrink-0 rounded-lg border border-nexus-border px-2.5 py-1 text-[11px] font-medium text-nexus-muted opacity-80 transition hover:border-nexus-accent hover:text-nexus-accent group-hover:opacity-100"
                      title="Use this alternative"
                    >
                      Use this
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : isLoadingAlternatives ? (
            <p className="text-xs text-nexus-muted animate-pulse">Loading alternative translations...</p>
          ) : null}
        </div>
      </div>

      {/* Error Alert */}
      {error ? (
        <div
          role="alert"
          className="flex items-center justify-between rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-300"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-xs font-semibold uppercase tracking-wider hover:underline"
          >
            Dismiss
          </button>
        </div>
      ) : null}

      {/* Main Translate Button */}
      <div className="flex justify-center pt-2">
        <button
          type="button"
          onClick={handleTranslate}
          disabled={isTranslating || !sourceText.trim() || isOverLimit}
          className="inline-flex min-w-[220px] items-center justify-center rounded-full bg-nexus-accent px-8 py-3.5 text-sm font-semibold uppercase tracking-[0.2em] text-white shadow-nexus transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-nexus-accent disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Translate text"
        >
          {isTranslating ? "Translating..." : "Translate"}
        </button>
      </div>

      {/* Voice Settings Modal */}
      <VoiceSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onUpdateSettings={updateSettings}
      />
    </section>
  );
}
