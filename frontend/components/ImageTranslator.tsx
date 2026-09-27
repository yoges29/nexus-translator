"use client";

import { useEffect, useRef, useState } from "react";
import {
  getLanguageLabel,
  getSourceLanguages,
  getTranslatableLanguages,
} from "@/lib/languages";
import { synthesizeSpeech, translateImage } from "@/services/api";
import type { ImageTranslateResponse, OCRRegion } from "@/types/language";
import { LanguageSelect } from "./LanguageSelect";

interface ImageTranslatorProps {
  onHistoryRefresh?: () => void;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
const ALLOWED_EXTENSIONS = ["png", "jpg", "jpeg", "webp"];

export function ImageTranslator({ onHistoryRefresh }: ImageTranslatorProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [sourceLanguage, setSourceLanguage] = useState<string>("auto");
  const [targetLanguage, setTargetLanguage] = useState<string>("en");
  const [translationStyle, setTranslationStyle] = useState<"general" | "formal" | "casual">("general");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImageTranslateResponse | null>(null);

  const [isCopiedOriginal, setIsCopiedOriginal] = useState<boolean>(false);
  const [isCopiedTranslation, setIsCopiedTranslation] = useState<boolean>(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [showRegions, setShowRegions] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  const sourceLanguages = getSourceLanguages();
  const translatableLanguages = getTranslatableLanguages();

  // Cleanup object URLs on unmount or file change
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      }
    };
  }, [previewUrl]);

  const validateAndSetFile = (file: File) => {
    setError(null);
    setResult(null);

    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported image format ".${ext}". Please upload a PNG, JPG, JPEG, or WEBP file.`);
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError("Image size exceeds the 10MB maximum limit. Please choose a smaller image.");
      return;
    }

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    const url = URL.createObjectURL(file);
    setSelectedFile(file);
    setPreviewUrl(url);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      validateAndSetFile(file);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      validateAndSetFile(file);
    }
  };

  const handleRemoveImage = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setSelectedFile(null);
    setPreviewUrl(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleExtractAndTranslate = async () => {
    if (!selectedFile) {
      setError("Please select or drop an image first.");
      return;
    }

    setIsLoading(true);
    setError(null);
    setAudioError(null);

    try {
      const response = await translateImage({
        imageFile: selectedFile,
        targetLanguage,
        sourceLanguage,
        translationStyle,
        filename: selectedFile.name,
      });
      setResult(response);
      if (onHistoryRefresh) {
        onHistoryRefresh();
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Image translation failed. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyOriginal = async () => {
    if (!result?.extracted_text) return;
    try {
      await navigator.clipboard.writeText(result.extracted_text);
      setIsCopiedOriginal(true);
      setTimeout(() => setIsCopiedOriginal(false), 2000);
    } catch {
      setError("Failed to copy original text to clipboard.");
    }
  };

  const handleCopyTranslation = async () => {
    if (!result?.translated_text) return;
    try {
      await navigator.clipboard.writeText(result.translated_text);
      setIsCopiedTranslation(true);
      setTimeout(() => setIsCopiedTranslation(false), 2000);
    } catch {
      setError("Failed to copy translated text to clipboard.");
    }
  };

  const handlePlayTTS = async () => {
    if (!result?.translated_text) return;

    if (isPlayingAudio && currentAudioRef.current) {
      currentAudioRef.current.pause();
      setIsPlayingAudio(false);
      return;
    }

    setIsPlayingAudio(true);
    setAudioError(null);

    try {
      const blob = await synthesizeSpeech({
        text: result.translated_text,
        language: result.target_language,
        speed: 1.0,
      });

      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;

      audio.onended = () => {
        setIsPlayingAudio(false);
        URL.revokeObjectURL(audioUrl);
        currentAudioRef.current = null;
      };

      audio.onerror = () => {
        setIsPlayingAudio(false);
        setAudioError("Audio playback error.");
        URL.revokeObjectURL(audioUrl);
        currentAudioRef.current = null;
      };

      await audio.play();
    } catch (err: unknown) {
      setIsPlayingAudio(false);
      const msg = err instanceof Error ? err.message : "Failed to synthesize speech.";
      setAudioError(msg);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and description */}
      <div className="rounded-2xl border border-nexus-border bg-nexus-surface/60 p-5 shadow-nexus backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-nexus-foreground sm:text-xl">
              Image Translator & OCR
            </h2>
            <p className="mt-1 text-xs text-nexus-muted sm:text-sm">
              Extract text from images using optical character recognition and translate instantly into your target language.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-nexus-muted">
            <span className="inline-flex items-center rounded-full border border-nexus-border bg-nexus-surface px-2.5 py-1 font-mono text-[11px]">
              PNG · JPG · WEBP · Max 10MB
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: Upload & Controls */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Column: Image Upload & Preview */}
        <div className="flex flex-col gap-4">
          <input
            ref={fileInputRef}
            type="file"
            accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
            className="hidden"
            onChange={handleFileChange}
            id="image-file-input"
          />

          {!previewUrl ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`group flex min-h-[280px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-all ${
                isDragOver
                  ? "border-nexus-accent bg-nexus-accent/10"
                  : "border-nexus-border bg-nexus-surface/40 hover:border-nexus-accent/60 hover:bg-nexus-surface/80"
              }`}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  fileInputRef.current?.click();
                }
              }}
              aria-label="Upload Image Area"
            >
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-nexus-accent/10 text-nexus-accent transition group-hover:scale-110">
                <svg
                  className="h-7 w-7"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium text-nexus-foreground">
                <span className="text-nexus-accent underline">Click to upload</span> or drag and drop
              </p>
              <p className="mt-1 text-xs text-nexus-muted">
                PNG, JPG, JPEG, or WEBP up to 10MB
              </p>
            </div>
          ) : (
            <div className="relative flex min-h-[280px] flex-col items-center justify-center overflow-hidden rounded-2xl border border-nexus-border bg-nexus-surface/60 p-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="Upload preview"
                className="max-h-[340px] w-auto max-w-full rounded-lg object-contain shadow-sm"
              />
              <div className="mt-4 flex w-full items-center justify-between border-t border-nexus-border/60 pt-3">
                <div className="truncate text-xs text-nexus-muted">
                  <span className="font-medium text-nexus-foreground">{selectedFile?.name}</span> (
                  {((selectedFile?.size ?? 0) / 1024).toFixed(1)} KB)
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="rounded-lg border border-nexus-border bg-nexus-surface px-3 py-1.5 text-xs font-medium text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                  >
                    Change Image
                  </button>
                  <button
                    type="button"
                    onClick={handleRemoveImage}
                    className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 transition hover:bg-red-500/20"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Language Controls & Execution */}
        <div className="flex flex-col justify-between gap-6 rounded-2xl border border-nexus-border bg-nexus-surface/60 p-5 backdrop-blur">
          <div className="space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-nexus-accent">
              Translation Settings
            </h3>

            <div className="grid gap-4 sm:grid-cols-2">
              <LanguageSelect
                id="source-language-select"
                label="Source Language"
                value={sourceLanguage}
                languages={sourceLanguages}
                onChange={setSourceLanguage}
              />

              <LanguageSelect
                id="target-language-select"
                label="Target Language"
                value={targetLanguage}
                languages={translatableLanguages}
                onChange={setTargetLanguage}
              />
            </div>

            <div>
              <label
                htmlFor="translation-style-select"
                className="text-xs font-medium uppercase tracking-[0.18em] text-nexus-muted"
              >
                Style Mode
              </label>
              <div className="mt-1.5 grid grid-cols-3 gap-2">
                {(["general", "formal", "casual"] as const).map((style) => (
                  <button
                    key={style}
                    type="button"
                    onClick={() => setTranslationStyle(style)}
                    className={`rounded-xl border py-2 text-xs font-medium capitalize transition ${
                      translationStyle === style
                        ? "border-nexus-accent bg-nexus-accent/20 text-nexus-accent font-semibold"
                        : "border-nexus-border bg-nexus-surface text-nexus-muted hover:border-nexus-accent hover:text-nexus-foreground"
                    }`}
                  >
                    {style}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
                <span className="font-semibold">Error:</span> {error}
              </div>
            )}

            {audioError && (
              <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-3 text-xs text-yellow-400">
                <span className="font-semibold">Audio Notice:</span> {audioError}
              </div>
            )}
          </div>

          <div className="pt-2">
            <button
              type="button"
              onClick={handleExtractAndTranslate}
              disabled={!selectedFile || isLoading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-nexus-accent py-3 text-sm font-semibold text-white shadow-nexus transition hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-nexus-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isLoading ? (
                <>
                  <svg
                    className="h-4 w-4 animate-spin text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v8H4z"
                    />
                  </svg>
                  <span>Processing OCR & Translating...</span>
                </>
              ) : (
                <>
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                  <span>Extract & Translate</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Results Display */}
      {result && (
        <div className="space-y-4 rounded-2xl border border-nexus-border bg-nexus-surface/80 p-6 shadow-nexus backdrop-blur">
          {/* Detected Language Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-nexus-border pb-4">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider text-nexus-muted">
                Detected Language:
              </span>
              <span className="rounded-full bg-nexus-accent/20 px-3 py-0.5 text-xs font-semibold text-nexus-accent">
                {result.detected_language
                  ? getLanguageLabel(result.detected_language)
                  : getLanguageLabel(result.source_language)}
              </span>
            </div>
            <div className="text-xs text-nexus-muted">
              Style: <span className="font-semibold text-nexus-foreground capitalize">{result.translation_style}</span>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {/* Original Text Block */}
            <div className="flex flex-col justify-between rounded-xl border border-nexus-border bg-nexus-surface/50 p-4">
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-nexus-muted">
                    Original Text (Extracted)
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyOriginal}
                    className="inline-flex items-center gap-1 rounded-md border border-nexus-border bg-nexus-surface px-2.5 py-1 text-xs text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                    title="Copy extracted text"
                  >
                    {isCopiedOriginal ? "Copied!" : "Copy"}
                  </button>
                </div>
                <div className="max-h-60 overflow-y-auto whitespace-pre-wrap font-sans text-sm leading-relaxed text-nexus-foreground">
                  {result.extracted_text}
                </div>
              </div>
            </div>

            {/* Translated Text Block */}
            <div className="flex flex-col justify-between rounded-xl border border-nexus-border bg-nexus-surface/50 p-4">
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-nexus-accent">
                    Translation ({getLanguageLabel(result.target_language)})
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handlePlayTTS}
                      className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs transition ${
                        isPlayingAudio
                          ? "border-nexus-accent bg-nexus-accent text-white"
                          : "border-nexus-border bg-nexus-surface text-nexus-muted hover:border-nexus-accent hover:text-nexus-accent"
                      }`}
                      title="Play speech for translated text"
                      aria-label="Listen to translation"
                    >
                      {isPlayingAudio ? (
                        <>
                          <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                          <span>Stop</span>
                        </>
                      ) : (
                        <>
                          <svg
                            className="h-3.5 w-3.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
                            />
                          </svg>
                          <span>Play (TTS)</span>
                        </>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={handleCopyTranslation}
                      className="inline-flex items-center gap-1 rounded-md border border-nexus-border bg-nexus-surface px-2.5 py-1 text-xs text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                      title="Copy translated text"
                    >
                      {isCopiedTranslation ? "Copied!" : "Copy"}
                    </button>
                  </div>
                </div>
                <div className="max-h-60 overflow-y-auto whitespace-pre-wrap font-sans text-sm leading-relaxed text-nexus-foreground font-medium">
                  {result.translated_text}
                </div>
              </div>
            </div>
          </div>

          {/* OCR Regions / Bounding Boxes inspector (Expandable) */}
          {result.regions && result.regions.length > 0 && (
            <div className="border-t border-nexus-border pt-4">
              <button
                type="button"
                onClick={() => setShowRegions(!showRegions)}
                className="flex items-center gap-2 text-xs font-medium text-nexus-muted hover:text-nexus-accent"
              >
                <span>{showRegions ? "▼ Hide" : "▶ Show"} OCR Detected Regions ({result.regions.length})</span>
              </button>

              {showRegions && (
                <div className="mt-3 max-h-48 overflow-y-auto rounded-lg border border-nexus-border bg-nexus-bg p-3 font-mono text-xs">
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
                    {result.regions.map((region: OCRRegion, idx: number) => (
                      <div
                        key={idx}
                        className="rounded border border-nexus-border/60 bg-nexus-surface/50 p-2"
                      >
                        <div className="truncate font-semibold text-nexus-foreground">
                          &ldquo;{region.text}&rdquo;
                        </div>
                        <div className="mt-1 text-[11px] text-nexus-muted">
                          x:{region.bounding_box.x} y:{region.bounding_box.y} w:{region.bounding_box.width} h:{region.bounding_box.height}
                          {region.confidence != null && (
                            <span className="ml-1 text-emerald-400">
                              ({(region.confidence * 100).toFixed(0)}%)
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
