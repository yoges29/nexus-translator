"use client";

import { synthesizeSpeech } from "@/services/api";
import { useCallback, useEffect, useRef, useState } from "react";

export type AudioPlayerState = "idle" | "loading" | "playing" | "paused" | "error";

interface UseAudioPlayerOptions {
  onError?: (error: string) => void;
}

export function useAudioPlayer({ onError }: UseAudioPlayerOptions = {}) {
  const [state, setState] = useState<AudioPlayerState>("idle");
  const [currentText, setCurrentText] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const audioElementRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const speechUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const cleanupAudio = useCallback(() => {
    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current.src = "";
      audioElementRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      speechUtteranceRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      cleanupAudio();
    };
  }, [cleanupAudio]);

  const speakWithBrowserFallback = useCallback(
    (text: string, language: string, speed: number = 1.0) => {
      if (typeof window === "undefined" || !window.speechSynthesis) {
        const msg = "Text-to-speech is not supported in this browser.";
        setErrorMessage(msg);
        setState("error");
        onError?.(msg);
        return;
      }

      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = language;
      utterance.rate = Math.max(0.75, Math.min(1.5, speed));

      utterance.onstart = () => {
        setState("playing");
      };
      utterance.onend = () => {
        setState("idle");
        speechUtteranceRef.current = null;
      };
      utterance.onerror = (event) => {
        if (event.error !== "canceled") {
          const msg = "Speech playback encountered an error.";
          setErrorMessage(msg);
          setState("error");
          onError?.(msg);
        } else {
          setState("idle");
        }
      };

      speechUtteranceRef.current = utterance;
      window.speechSynthesis.speak(utterance);
    },
    [onError],
  );

  const play = useCallback(
    async (text: string, language: string, speed: number = 1.0, voice?: string) => {
      const cleaned = text.trim();
      if (!cleaned) return;

      // If already playing this text and paused, resume
      if (currentText === cleaned && state === "paused") {
        resume();
        return;
      }

      cleanupAudio();
      setCurrentText(cleaned);
      setState("loading");
      setErrorMessage(null);

      try {
        const audioBlob = await synthesizeSpeech({
          text: cleaned,
          language,
          speed,
          voice,
        });

        const url = URL.createObjectURL(audioBlob);
        audioUrlRef.current = url;

        const audio = new Audio(url);
        audio.playbackRate = speed;
        audioElementRef.current = audio;

        audio.onplay = () => setState("playing");
        audio.onpause = () => {
          if (audio.ended || audio.currentTime === 0) {
            setState("idle");
          } else {
            setState("paused");
          }
        };
        audio.onended = () => {
          setState("idle");
          cleanupAudio();
        };
        audio.onerror = () => {
          // Fall back to browser SpeechSynthesis
          speakWithBrowserFallback(cleaned, language, speed);
        };

        await audio.play();
      } catch (err) {
        // Fall back gracefully to browser SpeechSynthesis
        speakWithBrowserFallback(cleaned, language, speed);
      }
    },
    [currentText, state, cleanupAudio, speakWithBrowserFallback],
  );

  const pause = useCallback(() => {
    if (audioElementRef.current && state === "playing") {
      audioElementRef.current.pause();
      setState("paused");
    } else if (typeof window !== "undefined" && window.speechSynthesis && state === "playing") {
      window.speechSynthesis.pause();
      setState("paused");
    }
  }, [state]);

  const resume = useCallback(() => {
    if (audioElementRef.current && state === "paused") {
      void audioElementRef.current.play();
      setState("playing");
    } else if (typeof window !== "undefined" && window.speechSynthesis && state === "paused") {
      window.speechSynthesis.resume();
      setState("playing");
    }
  }, [state]);

  const stop = useCallback(() => {
    cleanupAudio();
    setState("idle");
  }, [cleanupAudio]);

  const togglePlay = useCallback(
    (text: string, language: string, speed: number = 1.0, voice?: string) => {
      if (state === "playing") {
        pause();
      } else if (state === "paused") {
        resume();
      } else {
        void play(text, language, speed, voice);
      }
    },
    [state, play, pause, resume],
  );

  return {
    state,
    isPlaying: state === "playing",
    isPaused: state === "paused",
    isLoading: state === "loading",
    errorMessage,
    play,
    pause,
    resume,
    stop,
    togglePlay,
    clearError: () => setErrorMessage(null),
  };
}
