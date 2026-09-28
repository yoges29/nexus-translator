"use client";

import { transcribeAudio } from "@/services/api";
import { getSupportedAudioMimeType, ensureValidAudioBlob } from "@/lib/audioRecorder";
import { useCallback, useEffect, useRef, useState } from "react";

export type RecordingState = "idle" | "listening" | "processing" | "complete" | "error";

interface UseVoiceRecorderOptions {
  language?: string;
  onTranscriptionComplete?: (text: string, detectedLanguage?: string | null) => void;
  onError?: (errorMessage: string) => void;
}

export function useVoiceRecorder({
  language,
  onTranscriptionComplete,
  onError,
}: UseVoiceRecorderOptions = {}) {
  const [state, setState] = useState<RecordingState>("idle");
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const cleanupStream = useCallback(() => {
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
  }, []);

  useEffect(() => {
    return () => {
      cleanupStream();
    };
  }, [cleanupStream]);

  const startRecording = useCallback(async () => {
    if (state === "listening" || state === "processing") return;

    setErrorMessage(null);
    setRecordingDuration(0);

    if (typeof window === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      const msg = "Your browser does not support voice input.";
      setErrorMessage(msg);
      setState("error");
      onError?.(msg);
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

      // Determine mime type supported by browser, preferring webm/opus, webm, mp4, wav
      const preferredMime = getSupportedAudioMimeType();
      let recorder: MediaRecorder;
      try {
        recorder = preferredMime
          ? new MediaRecorder(stream, { mimeType: preferredMime })
          : new MediaRecorder(stream);
      } catch {
        recorder = new MediaRecorder(stream);
      }

      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      const resolvedMime = recorder.mimeType || preferredMime || "audio/webm";

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        setState("processing");
        const finalMime = recorder.mimeType || resolvedMime || "audio/webm";
        const rawBlob = new Blob(audioChunksRef.current, { type: finalMime });
        const audioBlob = ensureValidAudioBlob(rawBlob, finalMime);
        cleanupStream();

        if (audioBlob.size < 100) {
          const msg = "Unable to detect audio. Please speak clearly and try again.";
          setErrorMessage(msg);
          setState("idle");
          onError?.(msg);
          return;
        }

        try {
          const result = await transcribeAudio(audioBlob, language);
          if (result.text && result.text.trim()) {
            setState("complete");
            onTranscriptionComplete?.(result.text.trim(), result.language);
            setTimeout(() => {
              setState("idle");
            }, 2500);
          } else {
            const msg = "Unable to recognize speech. Please try again.";
            setErrorMessage(msg);
            setState("idle");
            onError?.(msg);
          }
        } catch (err) {
          const msg =
            err instanceof Error
              ? err.message
              : "Unable to process your audio. Please try again.";
          setErrorMessage(msg);
          setState("error");
          onError?.(msg);
        }
      };

      recorder.start(250); // Slice every 250ms
      setState("listening");

      timerRef.current = setInterval(() => {
        setRecordingDuration((prev) => {
          if (prev >= 60) {
            // Auto stop after 60 seconds
            stopRecording();
            return 60;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (err: unknown) {
      cleanupStream();
      let friendlyMessage = "Microphone access failed. Please try again.";
      if (err instanceof DOMException) {
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          friendlyMessage = "Microphone permission is required. Please allow access in browser settings.";
        } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
          friendlyMessage = "No microphone was found on your device.";
        } else if (err.name === "NotReadableError") {
          friendlyMessage = "Microphone is currently in use by another application.";
        }
      }
      setErrorMessage(friendlyMessage);
      setState("error");
      onError?.(friendlyMessage);
    }
  }, [state, language, onTranscriptionComplete, onError, cleanupStream]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        cleanupStream();
        setState("idle");
      }
    }
  }, [cleanupStream]);

  const cancelRecording = useCallback(() => {
    cleanupStream();
    setState("idle");
    setErrorMessage(null);
    setRecordingDuration(0);
  }, [cleanupStream]);

  return {
    state,
    isRecording: state === "listening",
    isProcessing: state === "processing",
    recordingDuration,
    errorMessage,
    startRecording,
    stopRecording,
    cancelRecording,
    clearError: () => setErrorMessage(null),
  };
}
