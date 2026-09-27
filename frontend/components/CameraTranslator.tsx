"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getLanguageLabel,
  getSourceLanguages,
  getTranslatableLanguages,
} from "@/lib/languages";
import { synthesizeSpeech, translateImage } from "@/services/api";
import type { ImageTranslateResponse } from "@/types/language";
import { LanguageSelect } from "./LanguageSelect";

interface CameraTranslatorProps {
  onHistoryRefresh?: () => void;
}

export function CameraTranslator({ onHistoryRefresh }: CameraTranslatorProps) {
  const [isCameraActive, setIsCameraActive] = useState<boolean>(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);

  const [targetLanguage, setTargetLanguage] = useState<string>("en");
  const [sourceLanguage, setSourceLanguage] = useState<string>("auto");
  const [translationStyle, setTranslationStyle] = useState<"general" | "formal" | "casual">("general");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [result, setResult] = useState<ImageTranslateResponse | null>(null);

  const [isCopiedOriginal, setIsCopiedOriginal] = useState<boolean>(false);
  const [isCopiedTranslation, setIsCopiedTranslation] = useState<boolean>(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState<boolean>(false);
  const [audioError, setAudioError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  const sourceLanguages = getSourceLanguages();
  const translatableLanguages = getTranslatableLanguages();

  // Safely stop all media tracks
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch {
          // ignore error on stop
        }
      });
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraActive(false);
  }, []);

  // Safe camera startup with browser checks and permission error handling
  const startCamera = useCallback(async () => {
    setCameraError(null);
    setProcessingError(null);

    if (typeof window === "undefined" || !navigator?.mediaDevices?.getUserMedia) {
      setCameraError(
        "Camera access is not supported by your browser or environment. Please use a modern browser (Chrome, Edge, Safari, Firefox) over HTTPS or localhost."
      );
      return;
    }

    // Stop existing stream if any
    stopCamera();

    try {
      let stream: MediaStream;
      try {
        // Try environment/back camera first (best for mobile document/sign scanning)
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
      } catch {
        // Fallback to standard camera request
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
      }

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(() => {});
      }
      setIsCameraActive(true);
    } catch (err: unknown) {
      setIsCameraActive(false);
      if (err instanceof DOMException) {
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          setCameraError(
            "Camera permission was denied. Please allow camera access in your browser site permissions to use live translation."
          );
          return;
        }
        if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
          setCameraError("No camera device was detected on your system.");
          return;
        }
        if (err.name === "NotReadableError" || err.name === "TrackStartError") {
          setCameraError(
            "Camera is currently in use by another application or tab. Please close other camera apps and try again."
          );
          return;
        }
      }
      setCameraError("Unable to access camera. Please check camera connections and permissions.");
    }
  }, [stopCamera]);

  // Start camera on mount, stop when unmounted or leaving tab
  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      }
    };
  }, [startCamera, stopCamera]);

  const handleCapture = async () => {
    if (!videoRef.current) return;
    const video = videoRef.current;

    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;

    let canvas = canvasRef.current;
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvasRef.current = canvas;
    }
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      setProcessingError("Failed to initialize canvas context for frame capture.");
      return;
    }

    ctx.drawImage(video, 0, 0, width, height);

    // Get snapshot data URL for immediate visual confirmation
    const snapshotUrl = canvas.toDataURL("image/jpeg", 0.9);
    setCapturedImage(snapshotUrl);

    // Stop live camera to conserve battery & privacy while reviewing
    stopCamera();

    // Convert to Blob for upload
    canvas.toBlob(
      async (blob) => {
        if (!blob) {
          setProcessingError("Failed to encode captured frame.");
          return;
        }

        setIsLoading(true);
        setProcessingError(null);
        setAudioError(null);

        try {
          const response = await translateImage({
            imageFile: blob,
            targetLanguage,
            sourceLanguage,
            translationStyle,
            filename: "camera_capture.jpg",
          });

          setResult(response);
          if (onHistoryRefresh) {
            onHistoryRefresh();
          }
        } catch (err: unknown) {
          const message =
            err instanceof Error ? err.message : "Failed to extract and translate text from captured frame.";
          setProcessingError(message);
        } finally {
          setIsLoading(false);
        }
      },
      "image/jpeg",
      0.92
    );
  };

  const handleRetake = () => {
    setCapturedImage(null);
    setResult(null);
    setProcessingError(null);
    setAudioError(null);
    startCamera();
  };

  const handleCopyOriginal = async () => {
    if (!result?.extracted_text) return;
    try {
      await navigator.clipboard.writeText(result.extracted_text);
      setIsCopiedOriginal(true);
      setTimeout(() => setIsCopiedOriginal(false), 2000);
    } catch {
      setProcessingError("Failed to copy original text to clipboard.");
    }
  };

  const handleCopyTranslation = async () => {
    if (!result?.translated_text) return;
    try {
      await navigator.clipboard.writeText(result.translated_text);
      setIsCopiedTranslation(true);
      setTimeout(() => setIsCopiedTranslation(false), 2000);
    } catch {
      setProcessingError("Failed to copy translated text to clipboard.");
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
      {/* Header and status banner */}
      <div className="rounded-2xl border border-nexus-border bg-nexus-surface/60 p-5 shadow-nexus backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-nexus-foreground sm:text-xl">
              Camera Translator
            </h2>
            <p className="mt-1 text-xs text-nexus-muted sm:text-sm">
              Point your camera at signs, labels, or documents to capture and translate text instantly.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isCameraActive ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
                <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
                Live Camera
              </span>
            ) : capturedImage ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-400">
                Frame Captured
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-nexus-border bg-nexus-surface px-3 py-1 text-xs font-medium text-nexus-muted">
                Camera Idle
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Main Viewport Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Viewport / Captured Image */}
        <div className="relative flex min-h-[380px] flex-col items-center justify-center overflow-hidden rounded-2xl border border-nexus-border bg-black/90 shadow-nexus">
          {capturedImage ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={capturedImage}
              alt="Captured frame"
              className="max-h-[460px] w-auto max-w-full rounded-xl object-contain"
            />
          ) : (
            <>
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={`max-h-[460px] w-full object-cover transition-opacity ${
                  isCameraActive ? "opacity-100" : "opacity-0"
                }`}
              />
              {/* Scan viewport guide overlay */}
              {isCameraActive && (
                <div className="pointer-events-none absolute inset-8 flex items-center justify-center rounded-xl border-2 border-dashed border-nexus-accent/60">
                  <span className="rounded bg-black/60 px-2 py-1 font-mono text-[10px] text-nexus-accent">
                    ALIGN TEXT INSIDE FRAME
                  </span>
                </div>
              )}
            </>
          )}

          {/* Hidden canvas used for capture */}
          <canvas ref={canvasRef} className="hidden" />

          {/* Camera Permission / Device Error Banner */}
          {cameraError && !capturedImage && (
            <div className="absolute inset-4 flex flex-col items-center justify-center rounded-xl bg-nexus-surface/95 p-6 text-center text-nexus-foreground backdrop-blur">
              <svg
                className="mb-3 h-10 w-10 text-red-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              <p className="max-w-md text-sm text-red-400">{cameraError}</p>
              <button
                type="button"
                onClick={startCamera}
                className="mt-4 rounded-xl bg-nexus-accent px-4 py-2 text-xs font-semibold text-white shadow-nexus transition hover:opacity-90"
              >
                Request Access / Try Again
              </button>
            </div>
          )}

          {/* Bottom Bar inside Viewport */}
          <div className="absolute bottom-4 flex items-center gap-3">
            {isCameraActive && (
              <>
                <button
                  type="button"
                  onClick={handleCapture}
                  className="flex items-center gap-2 rounded-full bg-nexus-accent px-6 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:scale-105 active:scale-95"
                >
                  <span className="h-3 w-3 rounded-full bg-white animate-ping" />
                  Capture Photo
                </button>
                <button
                  type="button"
                  onClick={stopCamera}
                  className="rounded-full bg-black/60 px-4 py-2 text-xs font-medium text-white/80 backdrop-blur transition hover:bg-black/80"
                >
                  Stop Camera
                </button>
              </>
            )}

            {!isCameraActive && !capturedImage && !cameraError && (
              <button
                type="button"
                onClick={startCamera}
                className="rounded-full bg-nexus-accent px-6 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:opacity-95"
              >
                Open Camera
              </button>
            )}

            {capturedImage && (
              <button
                type="button"
                onClick={handleRetake}
                className="flex items-center gap-2 rounded-full bg-nexus-surface/90 px-5 py-2 text-xs font-semibold text-nexus-foreground shadow backdrop-blur transition hover:bg-nexus-surface hover:text-nexus-accent"
              >
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
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                Retake Photo
              </button>
            )}
          </div>
        </div>

        {/* Right: Settings & Status */}
        <div className="flex flex-col justify-between gap-6 rounded-2xl border border-nexus-border bg-nexus-surface/60 p-5 backdrop-blur">
          <div className="space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-nexus-accent">
              Translation Language & Style
            </h3>

            <div className="grid gap-4 sm:grid-cols-2">
              <LanguageSelect
                id="camera-source-language-select"
                label="Source Language"
                value={sourceLanguage}
                languages={sourceLanguages}
                onChange={setSourceLanguage}
              />

              <LanguageSelect
                id="camera-target-language-select"
                label="Target Language"
                value={targetLanguage}
                languages={translatableLanguages}
                onChange={setTargetLanguage}
              />
            </div>

            <div>
              <label
                htmlFor="camera-translation-style"
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

            {/* Error Banners */}
            {processingError && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
                <span className="font-semibold">Notice:</span> {processingError}
              </div>
            )}

            {audioError && (
              <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-3 text-xs text-yellow-400">
                <span className="font-semibold">Audio Notice:</span> {audioError}
              </div>
            )}

            {isLoading && (
              <div className="flex items-center gap-3 rounded-xl border border-nexus-accent/30 bg-nexus-accent/10 p-4 text-xs text-nexus-accent">
                <svg
                  className="h-5 w-5 animate-spin"
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
                <span>Extracting text from camera frame and translating...</span>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-nexus-border/60 bg-nexus-surface/40 p-4 text-xs text-nexus-muted">
            <p className="font-medium text-nexus-foreground">Camera Scanning Tips:</p>
            <ul className="mt-1.5 list-disc space-y-1 pl-4 text-[11px]">
              <li>Hold device steady to avoid camera blur.</li>
              <li>Ensure good lighting over text or signs.</li>
              <li>Align lines of text horizontally inside the viewport guide.</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Captured Results Card */}
      {result && (
        <div className="space-y-4 rounded-2xl border border-nexus-border bg-nexus-surface/80 p-6 shadow-nexus backdrop-blur">
          {/* Header */}
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
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleRetake}
                className="inline-flex items-center gap-1 rounded-md border border-nexus-border bg-nexus-surface px-2.5 py-1 text-xs text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
              >
                Retake
              </button>
            </div>
          </div>

          {/* Content Columns */}
          <div className="grid gap-6 md:grid-cols-2">
            {/* Extracted Text */}
            <div className="flex flex-col justify-between rounded-xl border border-nexus-border bg-nexus-surface/50 p-4">
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-nexus-muted">
                    Extracted Text
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyOriginal}
                    className="inline-flex items-center gap-1 rounded-md border border-nexus-border bg-nexus-surface px-2.5 py-1 text-xs text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                  >
                    {isCopiedOriginal ? "Copied!" : "Copy"}
                  </button>
                </div>
                <div className="max-h-60 overflow-y-auto whitespace-pre-wrap font-sans text-sm leading-relaxed text-nexus-foreground">
                  {result.extracted_text}
                </div>
              </div>
            </div>

            {/* Translated Text */}
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
                    >
                      {isCopiedTranslation ? "Copied!" : "Copy"}
                    </button>
                  </div>
                </div>
                <div className="max-h-60 overflow-y-auto whitespace-pre-wrap font-sans text-sm font-medium leading-relaxed text-nexus-foreground">
                  {result.translated_text}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
