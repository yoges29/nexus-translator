"use client";

import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import { getLanguageByCode, getTranslatableLanguages } from "@/lib/languages";
import {
  createConversationSession,
  deleteConversationSession,
  getConversationSession,
  listConversationSessions,
  sendConversationAudioMessage,
  sendConversationMessage,
  swapConversationSession,
} from "@/services/api";
import type { ConversationMessageItem, ConversationSessionItem } from "@/types/language";
import { useCallback, useEffect, useRef, useState } from "react";
import { LanguageSelect } from "./LanguageSelect";

interface ConversationTranslatorProps {
  onHistoryRefresh?: () => void;
}

type SpeakerRole = "speaker_a" | "speaker_b";
type VoiceState = "idle" | "listening" | "processing" | "complete" | "error";

export function ConversationTranslator({ onHistoryRefresh }: ConversationTranslatorProps) {
  const translatableLanguages = getTranslatableLanguages();

  // Active Session & Languages
  const [session, setSession] = useState<ConversationSessionItem | null>(null);
  const [langA, setLangA] = useState<string>("ta"); // Tamil default for Person A
  const [langB, setLangB] = useState<string>("en"); // English default for Person B
  const [messages, setMessages] = useState<ConversationMessageItem[]>([]);

  // Controls & Settings
  const [autoSpeak, setAutoSpeak] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isCopiedId, setIsCopiedId] = useState<number | string | null>(null);

  // Speaker Active Recording States
  const [speakerAState, setSpeakerAState] = useState<VoiceState>("idle");
  const [speakerBState, setSpeakerBState] = useState<VoiceState>("idle");
  const [activeRecordingSpeaker, setActiveRecordingSpeaker] = useState<SpeakerRole | null>(null);
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);

  // Text Fallback Inputs
  const [showTextA, setShowTextA] = useState<boolean>(false);
  const [showTextB, setShowTextB] = useState<boolean>(false);
  const [textInputA, setTextInputA] = useState<string>("");
  const [textInputB, setTextInputB] = useState<string>("");
  const [isSendingText, setIsSendingText] = useState<boolean>(false);

  // Previous Conversations Drawer
  const [showHistoryDrawer, setShowHistoryDrawer] = useState<boolean>(false);
  const [pastSessions, setPastSessions] = useState<ConversationSessionItem[]>([]);
  const [historySearch, setHistorySearch] = useState<string>("");
  const [isLoadingPastSessions, setIsLoadingPastSessions] = useState<boolean>(false);

  // Audio Playback
  const audioPlayer = useAudioPlayer({
    onError: (err) => setErrorMessage(err),
  });
  const [playingMessageId, setPlayingMessageId] = useState<number | null>(null);

  // References for MediaRecorder & Timer
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);

  // --------------------------------------------------------------------------
  // Initialize / Load Session
  // --------------------------------------------------------------------------
  const initSession = useCallback(
    async (targetLangA: string, targetLangB: string) => {
      try {
        setErrorMessage(null);
        const newSession = await createConversationSession({
          language_a: targetLangA,
          language_b: targetLangB,
        });
        setSession(newSession);
        setMessages([]);
        setLangA(newSession.language_a);
        setLangB(newSession.language_b);
        if (onHistoryRefresh) onHistoryRefresh();
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to initialize conversation session.";
        setErrorMessage(msg);
      }
    },
    [onHistoryRefresh]
  );

  useEffect(() => {
    void initSession("ta", "en");
    return () => {
      stopRecordingCleanup();
      audioPlayer.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto scroll chat to bottom when messages update
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // --------------------------------------------------------------------------
  // MediaRecorder Cleanup & Stopping
  // --------------------------------------------------------------------------
  const stopRecordingCleanup = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    mediaRecorderRef.current = null;
    audioChunksRef.current = [];
    setActiveRecordingSpeaker(null);
    setRecordingSeconds(0);
  }, []);

  // --------------------------------------------------------------------------
  // Auto Speak Handler
  // --------------------------------------------------------------------------
  const triggerAutoSpeak = useCallback(
    async (text: string, lang: string, msgId: number) => {
      if (!autoSpeak || !text.trim()) return;
      try {
        setPlayingMessageId(msgId);
        await audioPlayer.play(text, lang, 1.0);
      } catch {
        // Fallback silently if auto speak fails
      }
    },
    [autoSpeak, audioPlayer]
  );

  // --------------------------------------------------------------------------
  // Voice Recording for a Speaker
  // --------------------------------------------------------------------------
  const startRecording = async (speaker: SpeakerRole) => {
    setErrorMessage(null);

    // If currently recording this speaker, stop recording
    if (activeRecordingSpeaker === speaker) {
      stopRecording();
      return;
    }

    // Stop any active audio playback
    audioPlayer.stop();
    setPlayingMessageId(null);

    // Stop previous recording if another speaker was active
    stopRecordingCleanup();

    if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      const msg = "Your browser does not support microphone voice input.";
      setErrorMessage(msg);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      let mimeType = "audio/webm";
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        mimeType = "audio/webm;codecs=opus";
      } else if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
        mimeType = "audio/ogg;codecs=opus";
      } else if (MediaRecorder.isTypeSupported("audio/wav")) {
        mimeType = "audio/wav";
      }

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        if (speaker === "speaker_a") setSpeakerAState("processing");
        else setSpeakerBState("processing");

        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        stopRecordingCleanup();

        if (audioBlob.size < 100) {
          const msg = "No speech detected. Please speak closer to your microphone.";
          setErrorMessage(msg);
          if (speaker === "speaker_a") setSpeakerAState("idle");
          else setSpeakerBState("idle");
          return;
        }

        if (!session) {
          setErrorMessage("No active conversation session.");
          if (speaker === "speaker_a") setSpeakerAState("idle");
          else setSpeakerBState("idle");
          return;
        }

        try {
          const newMsg = await sendConversationAudioMessage(session.id, {
            speaker,
            audioBlob,
            contentType: mimeType,
          });

          setMessages((prev) => [...prev, newMsg]);
          if (speaker === "speaker_a") setSpeakerAState("complete");
          else setSpeakerBState("complete");

          setTimeout(() => {
            if (speaker === "speaker_a") setSpeakerAState("idle");
            else setSpeakerBState("idle");
          }, 2000);

          if (onHistoryRefresh) onHistoryRefresh();

          // Auto speak translation
          void triggerAutoSpeak(newMsg.translated_text, newMsg.target_language, newMsg.id);
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Voice translation failed. Please try again.";
          setErrorMessage(msg);
          if (speaker === "speaker_a") setSpeakerAState("error");
          else setSpeakerBState("error");
          setTimeout(() => {
            if (speaker === "speaker_a") setSpeakerAState("idle");
            else setSpeakerBState("idle");
          }, 3000);
        }
      };

      recorder.start(250);
      setActiveRecordingSpeaker(speaker);
      if (speaker === "speaker_a") setSpeakerAState("listening");
      else setSpeakerBState("listening");

      setRecordingSeconds(0);
      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => {
          if (prev >= 60) {
            stopRecording();
            return 60;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (err: unknown) {
      stopRecordingCleanup();
      let friendly = "Failed to access microphone. Please check permissions.";
      if (err instanceof DOMException) {
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          friendly = "Microphone permission was denied. Please allow microphone access in your browser settings.";
        } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
          friendly = "No microphone was found on this device.";
        } else if (err.name === "NotReadableError") {
          friendly = "Microphone is in use by another application.";
        }
      }
      setErrorMessage(friendly);
      if (speaker === "speaker_a") setSpeakerAState("error");
      else setSpeakerBState("error");
      setTimeout(() => {
        if (speaker === "speaker_a") setSpeakerAState("idle");
        else setSpeakerBState("idle");
      }, 3000);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        stopRecordingCleanup();
      }
    } else {
      stopRecordingCleanup();
    }
  };

  // --------------------------------------------------------------------------
  // Send Typed Text Message
  // --------------------------------------------------------------------------
  const handleSendText = async (speaker: SpeakerRole) => {
    const text = speaker === "speaker_a" ? textInputA.trim() : textInputB.trim();
    if (!text || !session || isSendingText) return;

    setIsSendingText(true);
    setErrorMessage(null);

    try {
      const newMsg = await sendConversationMessage(session.id, {
        speaker,
        text,
      });

      setMessages((prev) => [...prev, newMsg]);
      if (speaker === "speaker_a") setTextInputA("");
      else setTextInputB("");

      if (onHistoryRefresh) onHistoryRefresh();
      void triggerAutoSpeak(newMsg.translated_text, newMsg.target_language, newMsg.id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to send message.";
      setErrorMessage(msg);
    } finally {
      setIsSendingText(false);
    }
  };

  // --------------------------------------------------------------------------
  // Controls: Swap Languages
  // --------------------------------------------------------------------------
  const handleSwapLanguages = async () => {
    if (!session) return;
    try {
      audioPlayer.stop();
      stopRecordingCleanup();
      setErrorMessage(null);

      const updated = await swapConversationSession(session.id);
      setSession(updated);
      setLangA(updated.language_a);
      setLangB(updated.language_b);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to swap languages.";
      setErrorMessage(msg);
    }
  };

  // --------------------------------------------------------------------------
  // Controls: Change Speaker Language
  // --------------------------------------------------------------------------
  const handleChangeLanguage = async (speaker: SpeakerRole, newLang: string) => {
    if (!session) return;
    const nextA = speaker === "speaker_a" ? newLang : langA;
    const nextB = speaker === "speaker_b" ? newLang : langB;

    if (nextA === nextB) {
      setErrorMessage("Person A and Person B must speak different languages.");
      return;
    }

    try {
      audioPlayer.stop();
      setErrorMessage(null);
      // Create a fresh session with updated languages
      await initSession(nextA, nextB);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update language.";
      setErrorMessage(msg);
    }
  };

  // --------------------------------------------------------------------------
  // Controls: Clear Conversation
  // --------------------------------------------------------------------------
  const handleClearConversation = () => {
    if (messages.length > 0) {
      const confirmed = window.confirm(
        "Are you sure you want to clear current visible messages and start a fresh session? Previous history will remain preserved."
      );
      if (!confirmed) return;
    }
    audioPlayer.stop();
    stopRecordingCleanup();
    void initSession(langA, langB);
  };

  // --------------------------------------------------------------------------
  // Controls: End Conversation
  // --------------------------------------------------------------------------
  const handleEndConversation = () => {
    audioPlayer.stop();
    stopRecordingCleanup();
    setSession(null);
    setMessages([]);
    setErrorMessage("Conversation ended. Messages are securely saved in history.");
  };

  // --------------------------------------------------------------------------
  // Copy to Clipboard
  // --------------------------------------------------------------------------
  const handleCopy = async (text: string, id: number | string) => {
    try {
      await navigator.clipboard.writeText(text);
      setIsCopiedId(id);
      setTimeout(() => setIsCopiedId(null), 2000);
    } catch {
      setErrorMessage("Failed to copy text to clipboard.");
    }
  };

  // --------------------------------------------------------------------------
  // Speech Playback (Play / Pause / Resume / Stop)
  // --------------------------------------------------------------------------
  const handleToggleAudio = async (msg: ConversationMessageItem) => {
    if (playingMessageId === msg.id && audioPlayer.isPlaying) {
      audioPlayer.pause();
      return;
    }
    if (playingMessageId === msg.id && audioPlayer.isPaused) {
      audioPlayer.resume();
      return;
    }

    setPlayingMessageId(msg.id);
    try {
      await audioPlayer.play(msg.translated_text, msg.target_language, 1.0);
    } catch {
      setErrorMessage("Failed to play speech audio.");
    }
  };

  // --------------------------------------------------------------------------
  // History Drawer Functions
  // --------------------------------------------------------------------------
  const loadPastSessions = async () => {
    setIsLoadingPastSessions(true);
    try {
      const res = await listConversationSessions({
        search: historySearch || undefined,
        limit: 20,
      });
      setPastSessions(res.items);
    } catch {
      // Quiet ignore
    } finally {
      setIsLoadingPastSessions(false);
    }
  };

  const handleOpenDrawer = () => {
    setShowHistoryDrawer(true);
    void loadPastSessions();
  };

  const handleReopenSession = async (pastSessionId: number) => {
    try {
      audioPlayer.stop();
      stopRecordingCleanup();
      const past = await getConversationSession(pastSessionId);
      setSession(past);
      setLangA(past.language_a);
      setLangB(past.language_b);
      setMessages(past.messages || []);
      setShowHistoryDrawer(false);
      setErrorMessage(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to reopen conversation session.";
      setErrorMessage(msg);
    }
  };

  const handleDeleteSession = async (pastSessionId: number) => {
    const confirmed = window.confirm("Are you sure you want to permanently delete this conversation session?");
    if (!confirmed) return;

    try {
      await deleteConversationSession(pastSessionId);
      setPastSessions((prev) => prev.filter((s) => s.id !== pastSessionId));
      if (session?.id === pastSessionId) {
        void initSession(langA, langB);
      }
      if (onHistoryRefresh) onHistoryRefresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to delete conversation.";
      setErrorMessage(msg);
    }
  };

  // Find latest message per speaker for the card view
  const lastMsgA = [...messages].reverse().find((m) => m.speaker === "speaker_a");
  const lastMsgB = [...messages].reverse().find((m) => m.speaker === "speaker_b");

  return (
    <div className="space-y-6">
      {/* Header & Controls Bar */}
      <div className="rounded-2xl border border-nexus-border bg-nexus-surface/60 p-5 shadow-nexus backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold tracking-tight text-nexus-foreground sm:text-xl">
                Conversation Mode
              </h2>
              {session && (
                <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 font-mono text-[11px] font-semibold text-emerald-400">
                  Live Session #{session.id}
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-nexus-muted sm:text-sm">
              Two-party bidirectional voice & text translator with instant speech output.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Auto Speak Toggle */}
            <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-nexus-border bg-nexus-surface px-3 py-1.5 text-xs text-nexus-muted transition hover:border-nexus-accent">
              <input
                type="checkbox"
                checked={autoSpeak}
                onChange={(e) => setAutoSpeak(e.target.checked)}
                className="h-3.5 w-3.5 accent-nexus-accent"
              />
              <span className={autoSpeak ? "font-semibold text-nexus-accent" : ""}>Auto Speak</span>
            </label>

            {/* Swap Languages */}
            <button
              type="button"
              onClick={handleSwapLanguages}
              disabled={!session}
              title="Swap Speaker Languages"
              className="inline-flex items-center gap-1.5 rounded-xl border border-nexus-border bg-nexus-surface px-3 py-1.5 text-xs font-medium text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent disabled:opacity-40"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
              <span>Swap</span>
            </button>

            {/* Clear Conversation */}
            <button
              type="button"
              onClick={handleClearConversation}
              className="rounded-xl border border-nexus-border bg-nexus-surface px-3 py-1.5 text-xs font-medium text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-foreground"
            >
              Clear
            </button>

            {/* End Conversation */}
            <button
              type="button"
              onClick={handleEndConversation}
              className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 transition hover:bg-red-500/20"
            >
              End Session
            </button>

            {/* Previous Conversations */}
            <button
              type="button"
              onClick={handleOpenDrawer}
              className="rounded-xl bg-nexus-accent px-3 py-1.5 text-xs font-semibold text-white shadow transition hover:opacity-90"
            >
              Previous Sessions
            </button>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="flex items-center justify-between rounded-xl border border-red-500/30 bg-red-500/10 p-3.5 text-xs text-red-400">
          <div className="flex items-center gap-2">
            <svg className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="text-red-400 hover:text-red-300"
          >
            ✕
          </button>
        </div>
      )}

      {/* Two-Party Interactive Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Person A Card */}
        <div
          className={`flex flex-col justify-between rounded-2xl border p-5 shadow-nexus backdrop-blur transition-all ${
            activeRecordingSpeaker === "speaker_a"
              ? "border-emerald-500 bg-emerald-500/5 ring-2 ring-emerald-500/20"
              : "border-nexus-border bg-nexus-surface/60"
          }`}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-nexus-border/60 pb-3">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/10 font-bold text-emerald-400 text-xs">
                  A
                </span>
                <span className="font-semibold text-sm text-nexus-foreground">Person A</span>
              </div>
              <span className="text-xs text-nexus-muted">
                Speaks: <strong className="text-nexus-foreground">{getLanguageByCode(langA)?.name || langA}</strong>
              </span>
            </div>

            <LanguageSelect
              id="person-a-language-select"
              label="Person A Language"
              value={langA}
              languages={translatableLanguages}
              onChange={(code) => handleChangeLanguage("speaker_a", code)}
            />

            {/* Microphone Speak Zone */}
            <div className="flex flex-col items-center justify-center py-6 text-center">
              <button
                type="button"
                onClick={() => startRecording("speaker_a")}
                disabled={activeRecordingSpeaker === "speaker_b" || speakerAState === "processing"}
                className={`group relative flex h-24 w-24 items-center justify-center rounded-full transition-all focus-visible:outline-none focus-visible:ring-4 ${
                  speakerAState === "listening"
                    ? "bg-red-500 text-white shadow-lg shadow-red-500/30 ring-4 ring-red-500/30 animate-pulse"
                    : speakerAState === "processing"
                    ? "bg-nexus-accent/20 text-nexus-accent"
                    : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500 hover:text-white hover:scale-105"
                } disabled:cursor-not-allowed disabled:opacity-40`}
                aria-label="Tap to speak for Person A"
              >
                {speakerAState === "listening" ? (
                  <div className="flex flex-col items-center">
                    <span className="h-4 w-4 rounded-sm bg-white" />
                  </div>
                ) : speakerAState === "processing" ? (
                  <svg className="h-8 w-8 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                ) : (
                  <svg className="h-9 w-9" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3z" />
                  </svg>
                )}
              </button>

              <div className="mt-3">
                {speakerAState === "listening" ? (
                  <p className="font-semibold text-xs text-red-400 animate-pulse">
                    🔴 Listening... ({recordingSeconds}s) · Tap to finish
                  </p>
                ) : speakerAState === "processing" ? (
                  <p className="font-semibold text-xs text-nexus-accent">⏳ Translating speech...</p>
                ) : speakerAState === "complete" ? (
                  <p className="font-semibold text-xs text-emerald-400">✓ Translation complete</p>
                ) : (
                  <p className="text-xs text-nexus-muted">Tap microphone to speak</p>
                )}
              </div>
            </div>

            {/* Latest Translation Display */}
            {lastMsgA && (
              <div className="space-y-2 rounded-xl border border-nexus-border/60 bg-nexus-surface/40 p-3.5">
                <div className="flex items-center justify-between text-[11px] text-nexus-muted">
                  <span>Latest from Person A</span>
                  <span>{new Date(lastMsgA.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                </div>
                <p className="font-sans text-xs italic text-nexus-muted">&ldquo;{lastMsgA.original_text}&rdquo;</p>
                <div className="border-t border-nexus-border/40 pt-2">
                  <p className="font-sans text-xs font-semibold text-nexus-foreground">
                    → {lastMsgA.translated_text}
                  </p>
                </div>
                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => handleToggleAudio(lastMsgA)}
                    className="flex items-center gap-1 rounded-lg border border-nexus-border bg-nexus-surface px-2.5 py-1 text-[11px] text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                  >
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                    </svg>
                    <span>{playingMessageId === lastMsgA.id && audioPlayer.isPlaying ? "Pause" : "Speak"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCopy(lastMsgA.translated_text, `a-${lastMsgA.id}`)}
                    className="flex items-center gap-1 rounded-lg border border-nexus-border bg-nexus-surface px-2.5 py-1 text-[11px] text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                  >
                    <span>{isCopiedId === `a-${lastMsgA.id}` ? "Copied" : "Copy"}</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Text Input Fallback */}
          <div className="mt-4 border-t border-nexus-border/60 pt-3">
            <button
              type="button"
              onClick={() => setShowTextA(!showTextA)}
              className="text-[11px] text-nexus-muted hover:text-nexus-accent underline"
            >
              {showTextA ? "Hide text input" : "Or type a message instead"}
            </button>
            {showTextA && (
              <div className="mt-2 flex gap-2">
                <input
                  type="text"
                  value={textInputA}
                  onChange={(e) => setTextInputA(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handleSendText("speaker_a");
                  }}
                  placeholder={`Type in ${getLanguageByCode(langA)?.name || langA}...`}
                  className="flex-1 rounded-xl border border-nexus-border bg-nexus-surface px-3 py-1.5 text-xs text-nexus-foreground focus-visible:outline-none focus-visible:border-nexus-accent"
                />
                <button
                  type="button"
                  onClick={() => handleSendText("speaker_a")}
                  disabled={!textInputA.trim() || isSendingText}
                  className="rounded-xl bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
                >
                  Send
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Person B Card */}
        <div
          className={`flex flex-col justify-between rounded-2xl border p-5 shadow-nexus backdrop-blur transition-all ${
            activeRecordingSpeaker === "speaker_b"
              ? "border-nexus-accent bg-nexus-accent/5 ring-2 ring-nexus-accent/20"
              : "border-nexus-border bg-nexus-surface/60"
          }`}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-nexus-border/60 pb-3">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-nexus-accent/10 font-bold text-nexus-accent text-xs">
                  B
                </span>
                <span className="font-semibold text-sm text-nexus-foreground">Person B</span>
              </div>
              <span className="text-xs text-nexus-muted">
                Speaks: <strong className="text-nexus-foreground">{getLanguageByCode(langB)?.name || langB}</strong>
              </span>
            </div>

            <LanguageSelect
              id="person-b-language-select"
              label="Person B Language"
              value={langB}
              languages={translatableLanguages}
              onChange={(code) => handleChangeLanguage("speaker_b", code)}
            />

            {/* Microphone Speak Zone */}
            <div className="flex flex-col items-center justify-center py-6 text-center">
              <button
                type="button"
                onClick={() => startRecording("speaker_b")}
                disabled={activeRecordingSpeaker === "speaker_a" || speakerBState === "processing"}
                className={`group relative flex h-24 w-24 items-center justify-center rounded-full transition-all focus-visible:outline-none focus-visible:ring-4 ${
                  speakerBState === "listening"
                    ? "bg-red-500 text-white shadow-lg shadow-red-500/30 ring-4 ring-red-500/30 animate-pulse"
                    : speakerBState === "processing"
                    ? "bg-nexus-accent/20 text-nexus-accent"
                    : "bg-nexus-accent/10 text-nexus-accent hover:bg-nexus-accent hover:text-white hover:scale-105"
                } disabled:cursor-not-allowed disabled:opacity-40`}
                aria-label="Tap to speak for Person B"
              >
                {speakerBState === "listening" ? (
                  <div className="flex flex-col items-center">
                    <span className="h-4 w-4 rounded-sm bg-white" />
                  </div>
                ) : speakerBState === "processing" ? (
                  <svg className="h-8 w-8 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                ) : (
                  <svg className="h-9 w-9" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3z" />
                  </svg>
                )}
              </button>

              <div className="mt-3">
                {speakerBState === "listening" ? (
                  <p className="font-semibold text-xs text-red-400 animate-pulse">
                    🔴 Listening... ({recordingSeconds}s) · Tap to finish
                  </p>
                ) : speakerBState === "processing" ? (
                  <p className="font-semibold text-xs text-nexus-accent">⏳ Translating speech...</p>
                ) : speakerBState === "complete" ? (
                  <p className="font-semibold text-xs text-nexus-accent">✓ Translation complete</p>
                ) : (
                  <p className="text-xs text-nexus-muted">Tap microphone to speak</p>
                )}
              </div>
            </div>

            {/* Latest Translation Display */}
            {lastMsgB && (
              <div className="space-y-2 rounded-xl border border-nexus-border/60 bg-nexus-surface/40 p-3.5">
                <div className="flex items-center justify-between text-[11px] text-nexus-muted">
                  <span>Latest from Person B</span>
                  <span>{new Date(lastMsgB.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                </div>
                <p className="font-sans text-xs italic text-nexus-muted">&ldquo;{lastMsgB.original_text}&rdquo;</p>
                <div className="border-t border-nexus-border/40 pt-2">
                  <p className="font-sans text-xs font-semibold text-nexus-foreground">
                    → {lastMsgB.translated_text}
                  </p>
                </div>
                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => handleToggleAudio(lastMsgB)}
                    className="flex items-center gap-1 rounded-lg border border-nexus-border bg-nexus-surface px-2.5 py-1 text-[11px] text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                  >
                    <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                    </svg>
                    <span>{playingMessageId === lastMsgB.id && audioPlayer.isPlaying ? "Pause" : "Speak"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCopy(lastMsgB.translated_text, `b-${lastMsgB.id}`)}
                    className="flex items-center gap-1 rounded-lg border border-nexus-border bg-nexus-surface px-2.5 py-1 text-[11px] text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                  >
                    <span>{isCopiedId === `b-${lastMsgB.id}` ? "Copied" : "Copy"}</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Text Input Fallback */}
          <div className="mt-4 border-t border-nexus-border/60 pt-3">
            <button
              type="button"
              onClick={() => setShowTextB(!showTextB)}
              className="text-[11px] text-nexus-muted hover:text-nexus-accent underline"
            >
              {showTextB ? "Hide text input" : "Or type a message instead"}
            </button>
            {showTextB && (
              <div className="mt-2 flex gap-2">
                <input
                  type="text"
                  value={textInputB}
                  onChange={(e) => setTextInputB(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handleSendText("speaker_b");
                  }}
                  placeholder={`Type in ${getLanguageByCode(langB)?.name || langB}...`}
                  className="flex-1 rounded-xl border border-nexus-border bg-nexus-surface px-3 py-1.5 text-xs text-nexus-foreground focus-visible:outline-none focus-visible:border-nexus-accent"
                />
                <button
                  type="button"
                  onClick={() => handleSendText("speaker_b")}
                  disabled={!textInputB.trim() || isSendingText}
                  className="rounded-xl bg-nexus-accent px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
                >
                  Send
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Conversation Thread / Message Log */}
      <div className="rounded-2xl border border-nexus-border bg-nexus-surface/60 p-6 shadow-nexus backdrop-blur">
        <div className="flex items-center justify-between border-b border-nexus-border pb-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-nexus-foreground">
            Conversation Thread ({messages.length})
          </h3>
          <span className="text-xs text-nexus-muted">
            {langA.toUpperCase()} ⇄ {langB.toUpperCase()}
          </span>
        </div>

        {messages.length === 0 ? (
          <div className="py-10 text-center text-xs text-nexus-muted">
            No messages exchanged yet. Tap either microphone above or type a message to start the conversation!
          </div>
        ) : (
          <div className="mt-4 max-h-[420px] space-y-4 overflow-y-auto pr-2">
            {messages.map((m) => {
              const isA = m.speaker === "speaker_a";
              return (
                <div
                  key={m.id}
                  className={`flex flex-col rounded-2xl border p-4 transition-all ${
                    isA
                      ? "border-emerald-500/30 bg-emerald-500/5 mr-8 sm:mr-16"
                      : "border-nexus-accent/30 bg-nexus-accent/5 ml-8 sm:ml-16"
                  }`}
                >
                  <div className="flex items-center justify-between border-b border-nexus-border/40 pb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                          isA ? "bg-emerald-500/20 text-emerald-400" : "bg-nexus-accent/20 text-nexus-accent"
                        }`}
                      >
                        {isA ? "Person A" : "Person B"}
                      </span>
                      <span className="font-mono text-[10px] text-nexus-muted uppercase">
                        {m.source_language} ➔ {m.target_language}
                      </span>
                    </div>
                    <span className="text-[11px] text-nexus-muted">
                      {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>

                  <div className="py-2.5">
                    <p className="text-xs text-nexus-muted italic">&ldquo;{m.original_text}&rdquo;</p>
                    <p className="mt-1 text-sm font-semibold text-nexus-foreground">
                      → {m.translated_text}
                    </p>
                  </div>

                  <div className="flex items-center justify-end gap-2 border-t border-nexus-border/30 pt-2">
                    <button
                      type="button"
                      onClick={() => handleToggleAudio(m)}
                      className="flex items-center gap-1 rounded-lg border border-nexus-border bg-nexus-surface px-2.5 py-1 text-[11px] text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                    >
                      <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                      </svg>
                      <span>{playingMessageId === m.id && audioPlayer.isPlaying ? "Pause" : "Speak"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCopy(m.translated_text, m.id)}
                      className="flex items-center gap-1 rounded-lg border border-nexus-border bg-nexus-surface px-2.5 py-1 text-[11px] text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                    >
                      <span>{isCopiedId === m.id ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                </div>
              );
            })}
            <div ref={chatBottomRef} />
          </div>
        )}
      </div>

      {/* History Drawer Modal */}
      {showHistoryDrawer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl border border-nexus-border bg-nexus-surface p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-nexus-border pb-4">
              <h3 className="font-semibold text-sm sm:text-base text-nexus-foreground">
                Previous Conversation Sessions
              </h3>
              <button
                type="button"
                onClick={() => setShowHistoryDrawer(false)}
                className="rounded-lg p-1 text-nexus-muted hover:bg-nexus-border hover:text-nexus-foreground"
              >
                ✕
              </button>
            </div>

            <div className="py-3">
              <input
                type="text"
                placeholder="Search conversations by language or title..."
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void loadPastSessions();
                }}
                className="w-full rounded-xl border border-nexus-border bg-nexus-bg px-3 py-2 text-xs text-nexus-foreground focus-visible:outline-none focus-visible:border-nexus-accent"
              />
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-nexus-border/60 py-2">
              {isLoadingPastSessions ? (
                <p className="py-8 text-center text-xs text-nexus-muted">Loading past conversations...</p>
              ) : pastSessions.length === 0 ? (
                <p className="py-8 text-center text-xs text-nexus-muted">No past conversations found.</p>
              ) : (
                pastSessions.map((ps) => (
                  <div key={ps.id} className="flex flex-wrap items-center justify-between gap-3 py-3 hover:bg-nexus-bg/40 px-2 rounded-lg">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-nexus-foreground">{ps.title}</span>
                        <span className="rounded bg-nexus-accent/10 px-1.5 py-0.2 text-[10px] text-nexus-accent font-mono uppercase">
                          {ps.language_a} ⇄ {ps.language_b}
                        </span>
                      </div>
                      <p className="text-[11px] text-nexus-muted">
                        {ps.message_count} message(s) · {new Date(ps.created_at).toLocaleDateString()}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleReopenSession(ps.id)}
                        className="rounded-lg bg-nexus-accent px-3 py-1 text-xs font-semibold text-white shadow transition hover:opacity-90"
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteSession(ps.id)}
                        className="rounded-lg border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs text-red-400 transition hover:bg-red-500/20"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="flex justify-end border-t border-nexus-border pt-4">
              <button
                type="button"
                onClick={() => setShowHistoryDrawer(false)}
                className="rounded-xl border border-nexus-border bg-nexus-surface px-4 py-1.5 text-xs text-nexus-muted hover:border-nexus-accent hover:text-nexus-foreground"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
