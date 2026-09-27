"use client";

import type { VoiceSettings } from "@/types/language";
import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "nexus_translator_voice_settings";

const DEFAULT_SETTINGS: VoiceSettings = {
  preferredVoice: "default",
  speechSpeed: 1.0,
  autoTranslateAfterSpeaking: false,
  autoPlayTranslation: false,
};

export function useVoiceSettings() {
  const [settings, setSettings] = useState<VoiceSettings>(DEFAULT_SETTINGS);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<VoiceSettings>;
        setSettings({
          ...DEFAULT_SETTINGS,
          ...parsed,
        });
      }
    } catch {
      // ignore storage access errors
    } finally {
      setIsLoaded(true);
    }
  }, []);

  const updateSettings = useCallback((newSettings: Partial<VoiceSettings>) => {
    setSettings((prev) => {
      const updated = { ...prev, ...newSettings };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch {
        // ignore
      }
      return updated;
    });
  }, []);

  return {
    settings,
    isLoaded,
    updateSettings,
  };
}
