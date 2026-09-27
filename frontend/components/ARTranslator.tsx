"use client";

import { LanguageSelect } from "@/components/LanguageSelect";
import { getSourceLanguages, getTranslatableLanguages } from "@/lib/languages";
import { synthesizeSpeech, translateImage } from "@/services/api";
import type { ImageTranslateResponse, OCRRegion } from "@/types/language";
import { useCallback, useEffect, useRef, useState } from "react";

type OverlayMode = "translation" | "original" | "both";

interface ARTranslatorProps {
  onHistoryRefresh?: () => void;
  onExit?: () => void;
}

export function ARTranslator({ onHistoryRefresh, onExit }: ARTranslatorProps) {
  const [isCameraActive, setIsCameraActive] = useState<boolean>(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [processingStatus, setProcessingStatus] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  const [sourceLanguage, setSourceLanguage] = useState<string>("auto");
  const [targetLanguage, setTargetLanguage] = useState<string>("ta");
  const [translationStyle, setTranslationStyle] = useState<"general" | "formal" | "casual">("general");

  const [overlayMode, setOverlayMode] = useState<OverlayMode>("translation");
  const [activeRegionIndex, setActiveRegionIndex] = useState<number | null>(null);
  const [result, setResult] = useState<ImageTranslateResponse | null>(null);
  const [frameDimensions, setFrameDimensions] = useState<{ width: number; height: number }>({
    width: 640,
    height: 480,
  });

  const [frozenFrame, setFrozenFrame] = useState<string | null>(null);
  const [activeTtsText, setActiveTtsText] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const sourceLanguages = getSourceLanguages();
  const targetLanguages = getTranslatableLanguages();

  // Stop camera tracks cleanly
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch {}
      });
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraActive(false);
  }, []);

  // Start camera preview
  const startCamera = useCallback(async () => {
    setCameraError(null);
    setProcessingStatus(null);

    if (typeof window === "undefined" || !navigator?.mediaDevices?.getUserMedia) {
      setCameraError(
        "Camera access is not supported by your browser. Please use Chrome, Edge, Safari, or Firefox over HTTPS."
      );
      return;
    }

    stopCamera();

    try {
      let stream: MediaStream;
      try {
        // Try environment camera for real-world document/sign overlay
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        });
      } catch {
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
      setFrozenFrame(null);
    } catch (err: unknown) {
      setIsCameraActive(false);
      const error = err as { name?: string; message?: string };
      if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
        setCameraError("Camera permission was denied. Please allow camera permissions in your browser to use AR Overlay.");
      } else if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
        setCameraError("No camera found on this device.");
      } else {
        setCameraError(`Camera error: ${error.message || "Could not start camera."}`);
      }
    }
  }, [stopCamera]);

  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, [startCamera, stopCamera]);

  // Capture current frame and run OCR + translation
  const scanAndOverlay = async () => {
    if (!videoRef.current || isProcessing) return;
    const video = videoRef.current;

    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    setFrameDimensions({ width, height });

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      setProcessingStatus("Failed to capture frame canvas.");
      return;
    }

    ctx.drawImage(video, 0, 0, width, height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
    setFrozenFrame(dataUrl);

    setIsProcessing(true);
    setProcessingStatus("Capturing frame and analyzing text bounding boxes remotely...");

    canvas.toBlob(
      async (blob) => {
        if (!blob) {
          setIsProcessing(false);
          setProcessingStatus("Failed to encode frame.");
          return;
        }

        try {
          const res = await translateImage({
            imageFile: blob,
            targetLanguage,
            sourceLanguage,
            translationStyle,
            filename: "ar_frame.jpg",
          });

          setResult(res);
          setProcessingStatus(
            res.regions && res.regions.length > 0
              ? `Detected and translated ${res.regions.length} text region(s).`
              : "No distinct text regions detected in this view."
          );
          onHistoryRefresh?.();
        } catch (err: unknown) {
          const error = err as Error;
          setProcessingStatus(error.message || "Failed to analyze and translate frame.");
        } finally {
          setIsProcessing(false);
        }
      },
      "image/jpeg",
      0.9
    );
  };

  // Clear current overlay and resume live preview
  const resumeLiveCamera = () => {
    setFrozenFrame(null);
    setResult(null);
    setProcessingStatus(null);
    setActiveRegionIndex(null);
    startCamera();
  };

  // Text-to-speech for selected region
  const playSpeech = async (text: string) => {
    if (!text.trim()) return;
    try {
      setActiveTtsText(text);
      const blob = await synthesizeSpeech({
        text,
        language: targetLanguage,
        speed: 1.0,
      });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => setActiveTtsText(null);
      audio.onerror = () => setActiveTtsText(null);
      await audio.play();
    } catch {
      setActiveTtsText(null);
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = targetLanguage;
        u.onend = () => setActiveTtsText(null);
        window.speechSynthesis.speak(u);
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <section className="rounded-2xl border border-nexus-border bg-nexus-surface p-6 shadow-nexus">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-nexus-border pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2.5 w-2.5 rounded-full bg-cyan-400 animate-pulse" />
              <h2 className="text-lg font-semibold tracking-tight text-nexus-foreground">
                AR-Style Translation Overlay
              </h2>
            </div>
            <p className="mt-1 text-xs text-nexus-muted">
              Spatial visual translation overlay positioned directly over detected text bounding boxes in camera view.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {onExit && (
              <button
                type="button"
                onClick={() => {
                  stopCamera();
                  onExit();
                }}
                className="rounded-full border border-nexus-border bg-nexus-surface-2 px-3.5 py-1.5 text-xs font-medium text-nexus-muted hover:border-rose-500 hover:text-rose-400 transition"
              >
                ✕ Exit AR Mode
              </button>
            )}
          </div>
        </div>

        {/* Camera Permission Error */}
        {cameraError && (
          <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300">
            <strong className="font-semibold block mb-1">Camera Permission Error:</strong>
            {cameraError}
          </div>
        )}

        {/* Language Selection */}
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <LanguageSelect
            id="ar-source"
            label="Source Language"
            value={sourceLanguage}
            languages={sourceLanguages}
            onChange={setSourceLanguage}
          />
          <LanguageSelect
            id="ar-target"
            label="Translate Into"
            value={targetLanguage}
            languages={targetLanguages}
            onChange={setTargetLanguage}
          />
        </div>

        {/* Translation Style Selector */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wider text-nexus-muted mr-1">Style:</span>
          {(["general", "formal", "casual"] as const).map((style) => (
            <button
              key={style}
              type="button"
              onClick={() => setTranslationStyle(style)}
              className={`rounded-lg px-3 py-1 text-xs font-medium capitalize transition ${
                translationStyle === style
                  ? "bg-cyan-500 text-black font-semibold shadow-sm"
                  : "border border-nexus-border bg-nexus-surface-2 text-nexus-muted hover:text-nexus-foreground"
              }`}
            >
              {style}
            </button>
          ))}
        </div>

        {/* View Mode Toggle: Show Translation / Show Original / Both */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-nexus-border pt-4">
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase tracking-wider text-nexus-muted mr-1">Overlay View:</span>
            {(
              [
                ["translation", "Show Translation"],
                ["original", "Show Original"],
                ["both", "Both (Side-by-Side)"],
              ] as const
            ).map(([mode, label]) => (
              <button
                key={mode}
                type="button"
                onClick={() => setOverlayMode(mode)}
                className={`rounded-lg px-3 py-1 text-xs font-medium transition ${
                  overlayMode === mode
                    ? "bg-cyan-500 text-black font-semibold shadow-sm"
                    : "border border-nexus-border bg-nexus-surface-2 text-nexus-muted hover:text-nexus-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>


          <div className="flex items-center gap-2">
            {frozenFrame ? (
              <button
                type="button"
                onClick={resumeLiveCamera}
                className="rounded-xl border border-nexus-border bg-nexus-surface-2 px-4 py-2 text-xs font-semibold text-nexus-foreground hover:border-nexus-accent transition"
              >
                🔄 Resume Live Camera
              </button>
            ) : null}

            <button
              type="button"
              onClick={scanAndOverlay}
              disabled={!isCameraActive || isProcessing}
              className="flex items-center gap-2 rounded-xl bg-cyan-500 px-5 py-2 text-xs font-bold text-black shadow-lg shadow-cyan-500/20 hover:bg-cyan-400 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isProcessing ? (
                <>
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-black border-t-transparent" />
                  <span>Scanning Frame...</span>
                </>
              ) : (
                <>
                  <span>⚡ Scan & Translate View</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Processing Notification */}
        {processingStatus && (
          <div className="mt-3 text-xs text-nexus-muted flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-cyan-400" />
            <span>{processingStatus}</span>
          </div>
        )}
      </section>

      {/* AR Viewport */}
      <section className="relative overflow-hidden rounded-2xl border border-nexus-border bg-black shadow-nexus">
        <div
          ref={containerRef}
          className="relative flex items-center justify-center overflow-hidden min-h-[420px] max-h-[640px] w-full"
        >
          {/* Live Video Feed */}
          <video
            ref={videoRef}
            playsInline
            muted
            className={`w-full h-auto max-h-[640px] object-contain transition-opacity duration-300 ${
              frozenFrame ? "opacity-0 absolute pointer-events-none" : "opacity-100"
            }`}
          />

          {/* Frozen captured frame when analyzing/overlaying */}
          {frozenFrame && (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={frozenFrame}
              alt="AR Freeze Frame"
              className="w-full h-auto max-h-[640px] object-contain select-none pointer-events-none"
            />
          )}


          {/* AR HUD Scanning Guide overlay */}
          {!frozenFrame && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="relative h-64 w-80 max-w-[85%] border-2 border-cyan-400/40 rounded-xl">
                {/* Corner markers */}
                <div className="absolute -top-1 -left-1 h-5 w-5 border-t-2 border-l-2 border-cyan-400" />
                <div className="absolute -top-1 -right-1 h-5 w-5 border-t-2 border-r-2 border-cyan-400" />
                <div className="absolute -bottom-1 -left-1 h-5 w-5 border-b-2 border-l-2 border-cyan-400" />
                <div className="absolute -bottom-1 -right-1 h-5 w-5 border-b-2 border-r-2 border-cyan-400" />

                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="rounded bg-black/60 px-3 py-1 text-[11px] font-medium tracking-wide text-cyan-300 backdrop-blur-sm">
                    Center text here & Click Scan
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Spatial AR Text Bounding Box Overlays */}
          {result?.regions && result.regions.length > 0 && (
            <div className="absolute inset-0 pointer-events-auto">
              {result.regions.map((region: OCRRegion, idx: number) => {
                const { x, y, width, height } = region.bounding_box;
                const leftPercent = (x / frameDimensions.width) * 100;
                const topPercent = (y / frameDimensions.height) * 100;
                const widthPercent = (width / frameDimensions.width) * 100;
                const heightPercent = (height / frameDimensions.height) * 100;

                const textToDisplay =
                  overlayMode === "translation"
                    ? region.translated_text || result.translated_text
                    : overlayMode === "original"
                    ? region.text
                    : `${region.text} ➔ ${region.translated_text || result.translated_text}`;

                const isSelected = activeRegionIndex === idx;

                return (
                  <div
                    key={`ar-box-${idx}`}
                    style={{
                      left: `${leftPercent}%`,
                      top: `${topPercent}%`,
                      minWidth: `${Math.max(widthPercent, 12)}%`,
                    }}
                    onClick={() => setActiveRegionIndex(isSelected ? null : idx)}
                    className={`absolute z-10 cursor-pointer transform -translate-y-1 transition-all group ${
                      isSelected ? "scale-105 z-30" : "hover:scale-102"
                    }`}
                  >
                    {/* Bounding box outline */}
                    <div
                      style={{
                        width: `${Math.max(widthPercent, 4)}%`,
                        height: `${Math.max(heightPercent, 3)}%`,
                      }}
                      className="absolute inset-0 border border-cyan-400/60 rounded pointer-events-none"
                    />

                    {/* Augmented Reality Translated Pill */}
                    <div className="inline-flex flex-col rounded-lg border border-cyan-400/80 bg-neutral-950/90 px-2.5 py-1 text-xs text-cyan-100 shadow-xl backdrop-blur-md max-w-xs sm:max-w-sm">
                      {overlayMode === "both" ? (
                        <>
                          <span className="text-[10px] text-nexus-muted line-through opacity-70">
                            {region.text}
                          </span>
                          <span className="font-semibold text-cyan-300">
                            {region.translated_text || result.translated_text}
                          </span>
                        </>
                      ) : (
                        <span className="font-semibold tracking-wide text-cyan-200">
                          {textToDisplay}
                        </span>
                      )}

                      {/* Region Action toolbar when clicked */}
                      {isSelected && (
                        <div className="mt-1 flex items-center gap-2 border-t border-nexus-border/60 pt-1 text-[10px]">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigator.clipboard.writeText(
                                region.translated_text || result.translated_text
                              );
                            }}
                            className="text-cyan-300 hover:text-white"
                          >
                            📋 Copy
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              playSpeech(region.translated_text || result.translated_text);
                            }}
                            className="text-cyan-300 hover:text-white"
                          >
                            🔊 {activeTtsText ? "Playing..." : "Speak"}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* Region Summaries Grid */}
      {result && (
        <section className="rounded-2xl border border-nexus-border bg-nexus-surface p-6 shadow-nexus">
          <div className="flex items-center justify-between border-b border-nexus-border pb-3 mb-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-nexus-foreground">
              Detected Regions ({result.regions?.length || 0})
            </h3>
            <span className="text-xs text-nexus-muted">
              {result.source_language.toUpperCase()} ➔ {result.target_language.toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-72 overflow-y-auto pr-1">
            {result.regions?.map((reg, i) => (
              <div
                key={i}
                onClick={() => setActiveRegionIndex(i)}
                className={`rounded-xl border p-3 cursor-pointer transition ${
                  activeRegionIndex === i
                    ? "border-cyan-400 bg-cyan-500/10"
                    : "border-nexus-border bg-nexus-surface-2 hover:border-cyan-400/40"
                }`}
              >
                <div className="flex items-center justify-between text-[11px] text-nexus-muted mb-1">
                  <span className="font-semibold text-cyan-400">Region #{i + 1}</span>
                  {reg.confidence && (
                    <span>conf: {Math.round(reg.confidence * 100)}%</span>
                  )}
                </div>
                <p className="text-xs text-nexus-muted">
                  <strong className="text-nexus-foreground font-medium">Original:</strong> {reg.text}
                </p>
                <p className="text-xs text-cyan-300 mt-1 font-medium">
                  <strong>Translated:</strong> {reg.translated_text || result.translated_text}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
