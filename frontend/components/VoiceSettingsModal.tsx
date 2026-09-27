"use client";

import type { VoiceSettings } from "@/types/language";

interface VoiceSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: VoiceSettings;
  onUpdateSettings: (newSettings: Partial<VoiceSettings>) => void;
}

const SPEECH_SPEED_OPTIONS = [
  { value: 0.75, label: "0.75x" },
  { value: 1.0, label: "1.0x" },
  { value: 1.25, label: "1.25x" },
  { value: 1.5, label: "1.5x" },
];

export function VoiceSettingsModal({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
}: VoiceSettingsModalProps) {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="voice-settings-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-fade-in"
    >
      <div
        className="w-full max-w-md rounded-3xl border border-nexus-border bg-nexus-panel p-6 shadow-2xl transition-all"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-nexus-border pb-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🎙️</span>
            <h2 id="voice-settings-title" className="text-lg font-semibold tracking-tight text-nexus-foreground">
              Voice & Audio Settings
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close voice settings"
            className="flex h-8 w-8 items-center justify-center rounded-full text-nexus-muted transition hover:bg-nexus-surface hover:text-nexus-foreground"
          >
            ✕
          </button>
        </div>

        <div className="space-y-6 pt-5">
          {/* Speech Speed */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-nexus-muted">
              Speech Speed (TTS)
            </label>
            <p className="mt-0.5 text-xs text-nexus-muted/80">
              Adjust the speaking pace for text-to-speech audio.
            </p>
            <div className="mt-3 grid grid-cols-4 gap-2">
              {SPEECH_SPEED_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => onUpdateSettings({ speechSpeed: opt.value })}
                  className={`rounded-xl py-2 text-xs font-semibold transition ${
                    settings.speechSpeed === opt.value
                      ? "bg-nexus-accent text-white shadow-nexus"
                      : "border border-nexus-border bg-nexus-surface text-nexus-muted hover:border-nexus-accent/50 hover:text-nexus-foreground"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Auto Translate After Speaking */}
          <div className="flex items-center justify-between gap-4 rounded-2xl border border-nexus-border/60 bg-nexus-surface/60 p-4">
            <div>
              <p className="text-sm font-medium text-nexus-foreground">Auto-Translate Speech</p>
              <p className="text-xs text-nexus-muted">
                Instantly translate text as soon as voice recording finishes.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={settings.autoTranslateAfterSpeaking}
              onClick={() =>
                onUpdateSettings({
                  autoTranslateAfterSpeaking: !settings.autoTranslateAfterSpeaking,
                })
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-nexus-accent ${
                settings.autoTranslateAfterSpeaking ? "bg-nexus-accent" : "bg-nexus-border"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                  settings.autoTranslateAfterSpeaking ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Auto Play Translation Audio */}
          <div className="flex items-center justify-between gap-4 rounded-2xl border border-nexus-border/60 bg-nexus-surface/60 p-4">
            <div>
              <p className="text-sm font-medium text-nexus-foreground">Auto-Read Aloud</p>
              <p className="text-xs text-nexus-muted">
                Automatically read the translated output aloud upon completion.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={settings.autoPlayTranslation}
              onClick={() =>
                onUpdateSettings({
                  autoPlayTranslation: !settings.autoPlayTranslation,
                })
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-nexus-accent ${
                settings.autoPlayTranslation ? "bg-nexus-accent" : "bg-nexus-border"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                  settings.autoPlayTranslation ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Privacy Note */}
          <div className="rounded-xl border border-nexus-border bg-nexus-surface p-3 text-xs text-nexus-muted">
            <p className="flex items-center gap-1.5 font-medium text-nexus-foreground">
              <span>🔒</span> Privacy & Security Notice
            </p>
            <p className="mt-1 leading-relaxed">
              Audio recordings are processed ephemerally for transcription and are never permanently stored on disk or shared.
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-nexus-accent px-6 py-2 text-xs font-semibold uppercase tracking-wider text-white shadow-nexus transition hover:brightness-110"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
