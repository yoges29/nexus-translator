"use client";

import { ActionButton } from "@/components/ActionButton";
import { LanguageSelect } from "@/components/LanguageSelect";
import { getSourceLanguages, getTranslatableLanguages } from "@/lib/languages";
import { getVoiceWebSocketUrl, synthesizeSpeech } from "@/services/api";
import type { TranslationStyle } from "@/types/language";
import { useCallback, useEffect, useRef, useState } from "react";

interface SpeechRecognitionResultItem {
  transcript: string;
}

interface SpeechRecognitionResultObj {
  isFinal: boolean;
  [index: number]: SpeechRecognitionResultItem;
}

interface SpeechRecognitionResultListObj {
  length: number;
  [index: number]: SpeechRecognitionResultObj;
}

interface SpeechRecognitionEventObj {
  resultIndex: number;
  results: SpeechRecognitionResultListObj;
}

interface SpeechRecognitionErrorEventObj {
  error: string;
  message?: string;
}

interface ISpeechRecognitionInstance {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventObj) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventObj) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionConstructor = new () => ISpeechRecognitionInstance;

interface TranscriptItem {
  id: string;
  original: string;
  translated: string;
  sourceLang: string;
  targetLang: string;
  timestamp: Date;
  detectedLang?: string | null;
}

interface RealTimeVoiceTranslatorProps {
  onHistoryRefresh?: () => void;
}

export function RealTimeVoiceTranslator({ onHistoryRefresh }: RealTimeVoiceTranslatorProps) {
  const sourceLanguages = getSourceLanguages();
  const targetLanguages = getTranslatableLanguages();

  const [sourceLanguage, setSourceLanguage] = useState("en");
  const [targetLanguage, setTargetLanguage] = useState("ta");
  const [translationStyle, setTranslationStyle] = useState<TranslationStyle>("general");

  const [isListening, setIsListening] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"idle" | "connecting" | "connected" | "error">("idle");
  const [permissionError, setPermissionError] = useState<string | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [autoSpeak, setAutoSpeak] = useState(false);

  // Live streaming text
  const [interimOriginal, setInterimOriginal] = useState("");
  const [interimTranslated, setInterimTranslated] = useState("");
  const [finalTranscripts, setFinalTranscripts] = useState<TranscriptItem[]>([]);
  const [activeTtsId, setActiveTtsId] = useState<string | null>(null);

  // Audio visualization
  const [audioLevel, setAudioLevel] = useState(0);

  // References for cleanup
  const socketRef = useRef<WebSocket | null>(null);
  const recognitionRef = useRef<ISpeechRecognitionInstance | null>(null);

  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isStoppingRef = useRef(false);

  // Play audio readout
  const playSpeech = useCallback(async (text: string, lang: string, id: string) => {
    if (!text.trim()) return;
    try {
      setActiveTtsId(id);
      const audioBlob = await synthesizeSpeech({
        text,
        language: lang,
        speed: 1.0,
      });
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audio.onended = () => {
        setActiveTtsId(null);
        URL.revokeObjectURL(audioUrl);
      };
      audio.onerror = () => {
        setActiveTtsId(null);
        URL.revokeObjectURL(audioUrl);
      };
      await audio.play();
    } catch {
      setActiveTtsId(null);
      // Fallback to browser SpeechSynthesis
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = lang;
        utterance.onend = () => setActiveTtsId(null);
        utterance.onerror = () => setActiveTtsId(null);
        window.speechSynthesis.speak(utterance);
      }
    }
  }, []);

  // Stop all active tracks and audio context
  const cleanupMedia = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
      recognitionRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  // Stop listening cleanly
  const stopListening = useCallback(() => {
    isStoppingRef.current = true;
    setIsListening(false);
    setConnectionStatus("idle");
    setInterimOriginal("");
    setInterimTranslated("");

    cleanupMedia();

    if (socketRef.current) {
      if (socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.close(1000, "User stopped listening");
      }
      socketRef.current = null;
    }
  }, [cleanupMedia]);

  // Start real-time voice translation
  const startListening = async () => {
    setPermissionError(null);
    setNetworkError(null);
    setInterimOriginal("");
    setInterimTranslated("");
    isStoppingRef.current = false;

    // Check browser compatibility
    if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setPermissionError("Audio recording is not supported in this browser. Please use Chrome, Edge, or Safari.");
      return;
    }

    // 1. Request microphone permission
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;
    } catch (err: unknown) {
      const error = err as { name?: string; message?: string };
      if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
        setPermissionError("Microphone permission was denied. Please allow microphone access in your browser to use real-time voice translation.");
      } else if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
        setPermissionError("No microphone found. Please connect an audio input device.");
      } else {
        setPermissionError(`Could not access microphone: ${error.message || "Unknown error"}`);
      }
      return;
    }

    // 2. Set up audio level visualizer
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        const audioCtx = new AudioCtx();
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64;
        const source = audioCtx.createMediaStreamSource(stream);
        source.connect(analyser);

        audioContextRef.current = audioCtx;
        analyserRef.current = analyser;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const updateLevel = () => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const avg = sum / dataArray.length;
          setAudioLevel(Math.min(100, Math.round((avg / 128) * 100)));
          animFrameRef.current = requestAnimationFrame(updateLevel);
        };
        updateLevel();
      }
    } catch {
      // AudioContext visualization is non-critical
    }

    // 3. Connect WebSocket streaming channel
    setConnectionStatus("connecting");
    const wsUrl = getVoiceWebSocketUrl({
      sourceLanguage,
      targetLanguage,
      translationStyle,
    });

    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl);
      socketRef.current = ws;
    } catch {
      setNetworkError("Failed to initiate WebSocket connection.");
      cleanupMedia();
      return;
    }

    ws.onopen = () => {
      setConnectionStatus("connected");
      // Setup periodic ping
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, 15000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "interim") {
          setInterimOriginal(data.original_text || "");
          setInterimTranslated(data.translated_text || "");
        } else if (data.type === "final") {
          const newItem: TranscriptItem = {
            id: `voice-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
            original: data.original_text,
            translated: data.translated_text,
            sourceLang: data.source_language || sourceLanguage,
            targetLang: data.target_language || targetLanguage,
            timestamp: new Date(),
            detectedLang: data.detected_language,
          };
          setFinalTranscripts((prev) => [newItem, ...prev]);
          setInterimOriginal("");
          setInterimTranslated("");
          onHistoryRefresh?.();

          if (autoSpeak && data.translated_text) {
            playSpeech(data.translated_text, data.target_language || targetLanguage, newItem.id);
          }
        } else if (data.type === "error") {
          setNetworkError(data.message || "Voice translation stream encountered an error.");
        }
      } catch {}
    };

    ws.onerror = () => {
      if (!isStoppingRef.current) {
        setNetworkError("WebSocket connection encountered a network error. Check backend connectivity.");
        setConnectionStatus("error");
      }
    };

    ws.onclose = () => {
      if (!isStoppingRef.current) {
        setConnectionStatus("idle");
      }
    };

    // 4. Initialize Speech Recognition
    const SpeechRecognition =
      (window as unknown as { SpeechRecognition?: SpeechRecognitionConstructor }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: SpeechRecognitionConstructor }).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = sourceLanguage === "auto" ? "en-US" : sourceLanguage;
      recognitionRef.current = recognition;

      recognition.onresult = (event: SpeechRecognitionEventObj) => {
        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            if (ws.readyState === WebSocket.OPEN && transcript.trim()) {
              ws.send(
                JSON.stringify({
                  type: "transcript",
                  text: transcript.trim(),
                  is_final: true,
                })
              );
            }
          } else {
            interimText += transcript;
          }
        }
        if (interimText.trim() && ws.readyState === WebSocket.OPEN) {
          ws.send(
            JSON.stringify({
              type: "transcript",
              text: interimText.trim(),
              is_final: false,
            })
          );
        }
      };

      recognition.onerror = (event: SpeechRecognitionErrorEventObj) => {
        if (event.error === "not-allowed") {
          setPermissionError("Speech recognition access denied.");
          stopListening();
        }
      };

      recognition.onend = () => {
        // Restart speech recognition automatically if still listening
        if (!isStoppingRef.current && socketRef.current?.readyState === WebSocket.OPEN) {
          try {
            recognition.start();
          } catch {}
        }
      };

      try {
        recognition.start();
      } catch (err: unknown) {
        const error = err as Error;
        setNetworkError(`Could not start speech recognition: ${error.message || "Error"}`);
      }
    } else {
      // Fallback for browsers without Web Speech API: Send audio chunks via MediaRecorder
      try {
        const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
        mediaRecorder.ondataavailable = async (e) => {
          if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            const buffer = await e.data.arrayBuffer();
            ws.send(buffer);
          }
        };
        mediaRecorder.start(2500); // 2.5s slice
      } catch {
        setPermissionError("Live speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.");
      }
    }

    setIsListening(true);
  };

  // Swap languages
  const swapLanguages = () => {
    if (sourceLanguage === "auto") return;
    const temp = sourceLanguage;
    setSourceLanguage(targetLanguage);
    setTargetLanguage(temp);

    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(
        JSON.stringify({
          type: "config",
          source_language: targetLanguage,
          target_language: temp,
          translation_style: translationStyle,
        })
      );
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isStoppingRef.current = true;
      cleanupMedia();
      if (socketRef.current) {
        try {
          socketRef.current.close(1000, "Component unmounted");
        } catch {}
      }
    };
  }, [cleanupMedia]);

  return (
    <div className="space-y-6">
      {/* Header card */}
      <section className="rounded-2xl border border-nexus-border bg-nexus-surface p-6 shadow-nexus">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-nexus-border pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2.5 w-2.5 rounded-full bg-nexus-accent animate-pulse" />
              <h2 className="text-lg font-semibold tracking-tight text-nexus-foreground">
                Real-Time Voice Translation
              </h2>
            </div>
            <p className="mt-1 text-xs text-nexus-muted">
              Live microphone capture with continuous speech recognition and ultra-low latency streaming translation.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs font-medium text-nexus-muted cursor-pointer select-none">
              <input
                type="checkbox"
                checked={autoSpeak}
                onChange={(e) => setAutoSpeak(e.target.checked)}
                className="h-4 w-4 rounded border-nexus-border text-nexus-accent focus:ring-nexus-accent"
              />
              Auto-Speak Translation
            </label>
            <div
              className={`rounded-full px-3 py-1 text-xs font-medium border ${
                connectionStatus === "connected"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : connectionStatus === "connecting"
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
                  : connectionStatus === "error"
                  ? "border-rose-500/30 bg-rose-500/10 text-rose-400"
                  : "border-nexus-border bg-nexus-surface-2 text-nexus-muted"
              }`}
            >
              {connectionStatus === "connected" && "WebSocket Connected"}
              {connectionStatus === "connecting" && "Connecting Channel..."}
              {connectionStatus === "error" && "Channel Error"}
              {connectionStatus === "idle" && "Channel Ready"}
            </div>
          </div>
        </div>

        {/* Permission / Network alerts */}
        {permissionError && (
          <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300">
            <strong className="font-semibold block mb-1">Microphone Access Error:</strong>
            {permissionError}
          </div>
        )}

        {networkError && (
          <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-300 flex items-center justify-between">
            <div>
              <strong className="font-semibold block mb-0.5">Streaming Channel Warning:</strong>
              {networkError}
            </div>
            <button
              onClick={() => setNetworkError(null)}
              className="ml-3 rounded-lg border border-amber-500/30 px-2 py-1 text-[11px] hover:bg-amber-500/20"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Language & Style Configuration */}
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-12 items-end">
          <div className="sm:col-span-5">
            <LanguageSelect
              id="voice-source"
              label="Spoken Language"
              value={sourceLanguage}
              languages={sourceLanguages}
              onChange={(code) => {
                setSourceLanguage(code);
                if (socketRef.current?.readyState === WebSocket.OPEN) {
                  socketRef.current.send(
                    JSON.stringify({
                      type: "config",
                      source_language: code,
                      target_language: targetLanguage,
                      translation_style: translationStyle,
                    })
                  );
                }
              }}
            />
          </div>

          <div className="sm:col-span-2 flex justify-center pb-1">
            <button
              type="button"
              onClick={swapLanguages}
              disabled={sourceLanguage === "auto"}
              title="Swap languages"
              className="rounded-xl border border-nexus-border bg-nexus-surface-2 p-2.5 text-nexus-muted hover:border-nexus-accent hover:text-nexus-accent transition disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ⇄
            </button>
          </div>

          <div className="sm:col-span-5">
            <LanguageSelect
              id="voice-target"
              label="Translated Language"
              value={targetLanguage}
              languages={targetLanguages}
              onChange={(code) => {
                setTargetLanguage(code);
                if (socketRef.current?.readyState === WebSocket.OPEN) {
                  socketRef.current.send(
                    JSON.stringify({
                      type: "config",
                      source_language: sourceLanguage,
                      target_language: code,
                      translation_style: translationStyle,
                    })
                  );
                }
              }}
            />
          </div>
        </div>

        {/* Translation Style Selector */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wider text-nexus-muted mr-1">Style:</span>
          {(["general", "formal", "casual"] as const).map((style) => (
            <button
              key={style}
              type="button"
              onClick={() => {
                setTranslationStyle(style);
                if (socketRef.current?.readyState === WebSocket.OPEN) {
                  socketRef.current.send(
                    JSON.stringify({
                      type: "config",
                      source_language: sourceLanguage,
                      target_language: targetLanguage,
                      translation_style: style,
                    })
                  );
                }
              }}
              className={`rounded-lg px-3 py-1 text-xs font-medium capitalize transition ${
                translationStyle === style
                  ? "bg-nexus-accent text-white"
                  : "border border-nexus-border bg-nexus-surface-2 text-nexus-muted hover:text-nexus-foreground"
              }`}
            >
              {style}
            </button>
          ))}
        </div>

        {/* Tactical Recording Action Bar */}
        <div className="mt-8 flex flex-col items-center justify-center rounded-2xl border border-nexus-border bg-nexus-surface-2 p-6 text-center">
          {/* Audio waveform / volume meter */}
          <div className="mb-4 flex items-center justify-center gap-1.5 h-12 w-full max-w-xs">
            {[...Array(16)].map((_, i) => {
              const active = isListening && audioLevel > i * 4;
              const height = isListening
                ? Math.max(6, Math.min(48, Math.sin((i / 16) * Math.PI) * (audioLevel * 0.6) + 6))
                : 6;
              return (
                <div
                  key={i}
                  style={{ height: `${height}px` }}
                  className={`w-1.5 rounded-full transition-all duration-75 ${
                    active
                      ? "bg-gradient-to-t from-nexus-accent to-emerald-400 shadow-sm"
                      : "bg-nexus-border/60"
                  }`}
                />
              );
            })}
          </div>

          {/* Central microphone toggle button */}
          <button
            type="button"
            onClick={isListening ? stopListening : startListening}
            className={`group relative flex items-center gap-3 rounded-2xl px-8 py-4 font-semibold text-white shadow-lg transition-all transform active:scale-95 ${
              isListening
                ? "bg-rose-600 hover:bg-rose-500 shadow-rose-600/30"
                : "bg-nexus-accent hover:opacity-90 shadow-nexus-accent/30"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 rounded-full ${
                isListening ? "bg-white animate-ping" : "bg-white/80"
              }`}
            />
            <span className="text-base tracking-wide">
              {isListening ? "Stop Voice Stream" : "Start Real-Time Voice"}
            </span>
          </button>

          <p className="mt-3 text-xs text-nexus-muted">
            {isListening
              ? "Microphone is live. Speak clearly into your mic to translate in real time."
              : "Click above to request microphone access and begin live two-way voice streaming."}
          </p>
        </div>
      </section>

      {/* Live Stream Viewport */}
      {(isListening || interimOriginal || interimTranslated) && (
        <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Spoken interim card */}
          <div className="rounded-2xl border border-nexus-accent/40 bg-nexus-surface p-5 shadow-nexus relative overflow-hidden">
            <div className="flex items-center justify-between border-b border-nexus-border pb-2 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-nexus-accent flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-nexus-accent animate-pulse" />
                Live Input ({sourceLanguage.toUpperCase()})
              </span>
              <span className="text-[10px] text-nexus-muted">Interim STT</span>
            </div>
            <p className="text-base text-nexus-foreground min-h-[48px] leading-relaxed">
              {interimOriginal ? (
                <span className="italic text-nexus-foreground/90">{interimOriginal}</span>
              ) : (
                <span className="text-nexus-muted/50 italic">Listening for speech...</span>
              )}
            </p>
          </div>

          {/* Translated interim card */}
          <div className="rounded-2xl border border-emerald-500/40 bg-nexus-surface p-5 shadow-nexus relative overflow-hidden">
            <div className="flex items-center justify-between border-b border-nexus-border pb-2 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                Live Translation ({targetLanguage.toUpperCase()})
              </span>
              <span className="text-[10px] text-nexus-muted">Streaming</span>
            </div>
            <p className="text-base text-emerald-300 min-h-[48px] leading-relaxed font-medium">
              {interimTranslated ? (
                <span className="animate-fade-in">{interimTranslated}</span>
              ) : (
                <span className="text-nexus-muted/50 italic">Translation will appear instantly...</span>
              )}
            </p>
          </div>
        </section>
      )}

      {/* Session Utterance History */}
      <section className="rounded-2xl border border-nexus-border bg-nexus-surface p-6 shadow-nexus">
        <div className="flex items-center justify-between border-b border-nexus-border pb-4 mb-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-nexus-foreground">
            Session Utterances ({finalTranscripts.length})
          </h3>
          {finalTranscripts.length > 0 && (
            <button
              type="button"
              onClick={() => setFinalTranscripts([])}
              className="text-xs text-nexus-muted hover:text-rose-400 transition"
            >
              Clear Session
            </button>
          )}
        </div>

        {finalTranscripts.length === 0 ? (
          <div className="py-8 text-center text-xs text-nexus-muted">
            No voice utterances recorded in this session yet. Start speaking above!
          </div>
        ) : (
          <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
            {finalTranscripts.map((item) => (
              <div
                key={item.id}
                className="rounded-xl border border-nexus-border bg-nexus-surface-2 p-4 transition hover:border-nexus-accent/40"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-nexus-muted mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-nexus-accent uppercase">
                      {item.sourceLang} ➔ {item.targetLang}
                    </span>
                    {item.detectedLang && (
                      <span className="rounded bg-nexus-surface px-1.5 py-0.5 text-[10px] text-nexus-muted border border-nexus-border">
                        detected: {item.detectedLang}
                      </span>
                    )}
                  </div>
                  <span>{item.timestamp.toLocaleTimeString()}</span>
                </div>

                <div className="space-y-1.5">
                  <div className="text-xs text-nexus-muted flex items-start gap-2">
                    <span className="select-none text-[10px] uppercase font-bold text-nexus-muted/60 mt-0.5">
                      IN:
                    </span>
                    <span className="text-nexus-foreground/90">{item.original}</span>
                  </div>
                  <div className="text-sm text-emerald-400 font-medium flex items-start gap-2">
                    <span className="select-none text-[10px] uppercase font-bold text-emerald-500/60 mt-0.5">
                      OUT:
                    </span>
                    <span>{item.translated}</span>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-end gap-2 border-t border-nexus-border/60 pt-2">
                  <ActionButton
                    label="📋 Copy"
                    onClick={() => {
                      navigator.clipboard.writeText(item.translated);
                    }}
                  />
                  <ActionButton
                    label={activeTtsId === item.id ? "Playing..." : "🔊 Listen"}
                    disabled={activeTtsId === item.id}
                    onClick={() => playSpeech(item.translated, item.targetLang, item.id)}
                  />
                </div>

              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
