"use client";

import { ARTranslator } from "@/components/ARTranslator";
import { CameraTranslator } from "@/components/CameraTranslator";
import { ConversationTranslator } from "@/components/ConversationTranslator";
import { DocumentTranslator } from "@/components/DocumentTranslator";
import { HistoryPanel } from "@/components/HistoryPanel";
import { ImageTranslator } from "@/components/ImageTranslator";
import { RealTimeVoiceTranslator } from "@/components/RealTimeVoiceTranslator";
import { ThemeToggle } from "@/components/ThemeToggle";
import { TranslatorWorkspace } from "@/components/TranslatorWorkspace";
import type { HistoryItem } from "@/types/language";
import { useState } from "react";

type Tab =
  | "translator"
  | "conversation"
  | "voice"
  | "image"
  | "camera"
  | "ar"
  | "documents"
  | "history";

const TABS: { id: Tab; label: string; icon: string; badge?: string }[] = [
  { id: "translator", label: "Text Translator", icon: "🔤" },
  { id: "conversation", label: "Conversation", icon: "💬" },
  { id: "voice", label: "Real-Time Voice", icon: "🎙️", badge: "Stage 4" },
  { id: "image", label: "Image OCR", icon: "🖼️", badge: "Stage 3" },
  { id: "camera", label: "Camera", icon: "📷", badge: "Stage 3" },
  { id: "ar", label: "AR Viewport", icon: "🥽", badge: "Stage 3" },
  { id: "documents", label: "Documents", icon: "📄", badge: "Stage 3" },
  { id: "history", label: "History", icon: "🕒" },
];

const MULTILINGUAL_CHAIN = [
  { lang: "English", code: "en", sample: "Good morning", flag: "🇬🇧" },
  { lang: "Tamil", code: "ta", sample: "காலை வணக்கம்", flag: "🇮🇳" },
  { lang: "Hindi", code: "hi", sample: "सुप्रभात", flag: "🇮🇳" },
  { lang: "Japanese", code: "ja", sample: "おはようございます", flag: "🇯🇵" },
  { lang: "French", code: "fr", sample: "Bonjour", flag: "🇫🇷" },
];

export function NexusApp() {
  const [tab, setTab] = useState<Tab>("translator");
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0);
  const [reusePayload, setReusePayload] = useState<{
    source: string;
    target: string;
    sourceText: string;
    translatedText: string;
  } | null>(null);

  const scrollToWorkspace = (targetTab: Tab = "translator") => {
    setTab(targetTab);
    const element = document.getElementById("translator-workspace");
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  };

  const handleTrySample = () => {
    setReusePayload({
      source: "en",
      target: "es",
      sourceText: "Good morning team, let's schedule our project review for today.",
      translatedText: "Buenos días equipo, programemos la revisión de nuestro proyecto para hoy.",
    });
    scrollToWorkspace("translator");
  };

  return (
    <div className="min-h-screen bg-nexus-bg text-nexus-foreground selection:bg-blue-500/20">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 border-b border-nexus-border bg-nexus-panel/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 to-sky-400 text-white shadow-md">
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m5 8 6 6" />
                <path d="m4 14 6-6 2-3" />
                <path d="M2 5h12" />
                <path d="M7 2h1" />
                <path d="m22 22-5-10-5 10" />
                <path d="M14 18h6" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold tracking-tight sm:text-lg">NEXUS TRANSLATOR</span>
                <span className="hidden rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold text-blue-600 dark:text-blue-400 sm:inline-block">
                  AI ENGINE
                </span>
              </div>
            </div>
          </div>

          <nav className="hidden items-center gap-6 md:flex" aria-label="Quick Navigation">
            <a href="#overview" className="text-xs font-medium uppercase tracking-wider text-nexus-muted transition hover:text-nexus-foreground">
              Overview
            </a>
            <a href="#features" className="text-xs font-medium uppercase tracking-wider text-nexus-muted transition hover:text-nexus-foreground">
              Features
            </a>
            <a href="#how-it-works" className="text-xs font-medium uppercase tracking-wider text-nexus-muted transition hover:text-nexus-foreground">
              How It Works
            </a>
            <a href="#technology" className="text-xs font-medium uppercase tracking-wider text-nexus-muted transition hover:text-nexus-foreground">
              Technology
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => scrollToWorkspace("translator")}
              className="hidden rounded-full bg-nexus-accent px-4 py-1.5 text-xs font-semibold text-white shadow-nexus transition hover:opacity-90 sm:inline-flex sm:items-center sm:gap-1.5"
            >
              <span>Workspace</span>
              <span>↓</span>
            </button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section id="overview" className="relative overflow-hidden border-b border-nexus-border/60 py-16 sm:py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            {/* AI Identity Badge */}
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/25 bg-blue-500/10 px-3.5 py-1 text-xs font-semibold text-blue-600 dark:text-blue-400 shadow-sm">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500"></span>
              </span>
              AI-Powered Multilingual Translation
            </div>

            {/* Main Headline */}
            <h1 className="mt-6 text-2xl font-extrabold tracking-tight sm:text-4xl md:text-5xl lg:text-6xl">
              <span className="block text-nexus-foreground">NEXUS TRANSLATOR</span>
              <span className="mt-2 block bg-gradient-to-r from-blue-600 via-indigo-500 to-sky-500 bg-clip-text text-transparent dark:from-blue-400 dark:via-indigo-300 dark:to-sky-400">
                One platform. Every language.
              </span>
            </h1>

            {/* Short Description */}
            <p className="mt-5 text-base leading-relaxed text-nexus-muted sm:text-lg">
              Translate conversations, documents and mixed-language text with intelligent multilingual processing.
            </p>

            {/* Action Buttons */}
            <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
              <button
                type="button"
                onClick={() => scrollToWorkspace("translator")}
                className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 px-7 py-3 text-sm font-semibold text-white shadow-nexus-lg transition hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                <span>Start Translating</span>
                <span className="transition-transform group-hover:translate-x-0.5">→</span>
              </button>

              <a
                href="#features"
                className="inline-flex items-center gap-1.5 rounded-full border border-nexus-border bg-nexus-panel/80 px-6 py-3 text-sm font-semibold text-nexus-foreground transition hover:border-nexus-accent hover:text-nexus-accent"
              >
                <span>Explore Features</span>
                <span>↓</span>
              </a>
            </div>

            {/* AI Identity Feature Pills */}
            <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs font-medium text-nexus-muted">
              <span className="inline-flex items-center gap-1.5">
                <span className="text-emerald-500">✓</span> Automatic Language Detection
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="text-emerald-500">✓</span> Mixed-Language Processing
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="text-emerald-500">✓</span> Multiple Translation Styles
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="text-emerald-500">✓</span> Voice & OCR Support
              </span>
            </div>
          </div>

          {/* Multilingual Communication Representation (Language Flow Chips) */}
          <div className="mt-14">
            <div className="mb-3 text-center text-xs font-semibold uppercase tracking-wider text-nexus-muted">
              Fluid Cross-Lingual Communication Flow
            </div>
            <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3">
              {MULTILINGUAL_CHAIN.map((item, idx) => (
                <div key={item.code} className="flex items-center gap-2 sm:gap-3">
                  <div className="group flex items-center gap-2 rounded-xl border border-nexus-border bg-nexus-panel px-3.5 py-2 shadow-sm transition hover:border-blue-500/50 hover:shadow-nexus">
                    <span className="text-base">{item.flag}</span>
                    <div className="text-left">
                      <div className="text-[10px] uppercase font-semibold tracking-wider text-nexus-muted">
                        {item.lang}
                      </div>
                      <div className="text-xs font-medium text-nexus-foreground">
                        {item.sample}
                      </div>
                    </div>
                  </div>
                  {idx < MULTILINGUAL_CHAIN.length - 1 && (
                    <span className="text-sm font-bold text-nexus-muted/60">→</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Translator Pipeline Preview Card */}
          <div className="mx-auto mt-14 max-w-4xl">
            <div className="rounded-2xl border border-nexus-border bg-nexus-panel p-5 shadow-nexus-lg sm:p-6">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-nexus-border/60 pb-3">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
                  <span className="text-xs font-semibold uppercase tracking-wider text-nexus-foreground">
                    Interactive Translation Pipeline Preview
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-nexus-muted">
                  <span className="rounded bg-nexus-surface px-2 py-0.5 font-mono text-[11px]">
                    Neural Engine Active
                  </span>
                  <span>•</span>
                  <span>Low Latency</span>
                </div>
              </div>

              <div className="grid grid-cols-1 items-stretch gap-4 md:grid-cols-7">
                {/* Input Card */}
                <div className="flex flex-col justify-between rounded-xl border border-nexus-border/80 bg-nexus-surface p-4 md:col-span-3">
                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-nexus-muted">
                        Source Input
                      </span>
                      <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-600 dark:text-blue-400">
                        English (en)
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed text-nexus-foreground">
                      &quot;Good morning team, let&apos;s schedule our project review for today.&quot;
                    </p>
                  </div>
                  <div className="mt-3 text-[11px] text-nexus-muted">
                    Auto-detected • Input: Text / Voice
                  </div>
                </div>

                {/* Pipeline Arrow / Badge */}
                <div className="flex flex-col items-center justify-center gap-1 py-2 md:col-span-1">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400 shadow-sm">
                    <span className="text-sm font-bold">⚡</span>
                  </div>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-nexus-muted">
                    AI Translate
                  </span>
                </div>

                {/* Output Card */}
                <div className="flex flex-col justify-between rounded-xl border border-blue-500/30 bg-blue-500/[0.03] p-4 md:col-span-3">
                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">
                        Target Output
                      </span>
                      <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] font-medium text-blue-600 dark:text-blue-400">
                        Spanish (es)
                      </span>
                    </div>
                    <p className="text-sm font-medium leading-relaxed text-nexus-foreground">
                      &quot;Buenos días equipo, programemos la revisión de nuestro proyecto para hoy.&quot;
                    </p>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-[11px] text-nexus-muted">
                    <span>Style: Formal • Accurate</span>
                    <button
                      type="button"
                      onClick={handleTrySample}
                      className="font-medium text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      Try this in Workspace →
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Live Interactive Workspace Section */}
      <section id="translator-workspace" className="py-12 sm:py-16">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-nexus-border pb-5">
            <div>
              <p className="text-xs uppercase font-semibold tracking-[0.3em] text-nexus-accent">
                Unified Translation Studio
              </p>
              <h2 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">
                Interactive Workspace
              </h2>
              <p className="mt-1 text-sm text-nexus-muted">
                Switch seamlessly between text, real-time conversation, streaming voice, camera, and document translation.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
              <span className="text-xs font-medium text-nexus-muted">Ready for input</span>
            </div>
          </div>

          {/* Redesigned Tab Navigation Bar */}
          <nav aria-label="Workspace Modes" className="mb-8 flex flex-wrap gap-2">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={`relative flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-nexus-accent ${
                  tab === item.id
                    ? "bg-nexus-accent text-white shadow-nexus"
                    : "border border-nexus-border bg-nexus-panel text-nexus-muted hover:border-nexus-accent/60 hover:text-nexus-foreground"
                }`}
                aria-current={tab === item.id ? "page" : undefined}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
                {item.badge && (
                  <span
                    className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                      tab === item.id
                        ? "bg-white/20 text-white"
                        : "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            ))}
          </nav>

          {/* Active Workspace Component Mounting (100% Functionality Preserved) */}
          <div className="rounded-2xl border border-nexus-border bg-nexus-panel p-4 shadow-nexus-lg sm:p-6 lg:p-8">
            {tab === "translator" && (
              <TranslatorWorkspace
                onHistoryRefresh={() => setHistoryRefreshToken((value) => value + 1)}
                externalReuse={reusePayload}
                onReuseApplied={() => setReusePayload(null)}
              />
            )}
            {tab === "conversation" && (
              <ConversationTranslator
                onHistoryRefresh={() => setHistoryRefreshToken((value) => value + 1)}
              />
            )}
            {tab === "voice" && (
              <RealTimeVoiceTranslator
                onHistoryRefresh={() => setHistoryRefreshToken((value) => value + 1)}
              />
            )}
            {tab === "image" && (
              <ImageTranslator
                onHistoryRefresh={() => setHistoryRefreshToken((value) => value + 1)}
              />
            )}
            {tab === "camera" && (
              <CameraTranslator
                onHistoryRefresh={() => setHistoryRefreshToken((value) => value + 1)}
              />
            )}
            {tab === "ar" && (
              <ARTranslator
                onHistoryRefresh={() => setHistoryRefreshToken((value) => value + 1)}
                onExit={() => setTab("camera")}
              />
            )}
            {tab === "documents" && (
              <DocumentTranslator
                onHistoryRefresh={() => setHistoryRefreshToken((value) => value + 1)}
              />
            )}
            {tab === "history" && (
              <HistoryPanel
                refreshToken={historyRefreshToken}
                onReuse={(item: HistoryItem) => {
                  setReusePayload({
                    source: item.source_language,
                    target: item.target_language,
                    sourceText: item.original_text,
                    translatedText: item.translated_text,
                  });
                  setTab("translator");
                  scrollToWorkspace("translator");
                }}
              />
            )}
          </div>
        </div>
      </section>

      {/* Built for Real-World Communication (Features Section) */}
      <section id="features" className="border-t border-nexus-border bg-nexus-surface/50 py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-nexus-accent">
              Core Capabilities
            </p>
            <h2 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">
              Built for Real-World Communication
            </h2>
            <p className="mt-3 text-sm text-nexus-muted sm:text-base">
              Engineered to handle diverse real-world language hurdles: from code-mixing to multi-page documents and live voice.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {/* Feature 1 */}
            <div className="group rounded-2xl border border-nexus-border bg-nexus-panel p-6 shadow-sm transition hover:border-nexus-accent/50 hover:shadow-nexus">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-500/10 text-xl text-blue-600 dark:text-blue-400">
                🌐
              </div>
              <h3 className="mt-4 text-base font-bold text-nexus-foreground">
                AI Translation
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-nexus-muted">
                Translate between multiple supported world and regional languages with high contextual fidelity and low latency.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="group rounded-2xl border border-nexus-border bg-nexus-panel p-6 shadow-sm transition hover:border-nexus-accent/50 hover:shadow-nexus">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-500/10 text-xl text-blue-600 dark:text-blue-400">
                🔍
              </div>
              <h3 className="mt-4 text-base font-bold text-nexus-foreground">
                Smart Detection
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-nexus-muted">
                Automatically identify the language of your input text across diverse alphabets and scripts in real time.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="group rounded-2xl border border-nexus-border bg-nexus-panel p-6 shadow-sm transition hover:border-nexus-accent/50 hover:shadow-nexus">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-500/10 text-xl text-blue-600 dark:text-blue-400">
                🧩
              </div>
              <h3 className="mt-4 text-base font-bold text-nexus-foreground">
                Mixed-Language Support
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-nexus-muted">
                Process text containing multiple languages or colloquial code-mixing (such as Tanglish and Hinglish) with linguistic parsing.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="group rounded-2xl border border-nexus-border bg-nexus-panel p-6 shadow-sm transition hover:border-nexus-accent/50 hover:shadow-nexus">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-500/10 text-xl text-blue-600 dark:text-blue-400">
                🎙️
              </div>
              <h3 className="mt-4 text-base font-bold text-nexus-foreground">
                Voice & OCR
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-nexus-muted">
                Translate spoken audio streams, camera viewports, and complex PDF/Word documents with layout preservation.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="border-t border-nexus-border py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-nexus-accent">
              Simple 3-Step Process
            </p>
            <h2 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">
              How It Works
            </h2>
            <p className="mt-3 text-sm text-nexus-muted">
              Fast, intuitive workflow designed for frictionless cross-border communication.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 gap-8 md:grid-cols-3">
            {/* Step 1 */}
            <div className="relative rounded-2xl border border-nexus-border bg-nexus-panel p-6 shadow-sm">
              <div className="font-mono text-3xl font-black text-nexus-accent/40">
                01
              </div>
              <h3 className="mt-3 text-lg font-bold text-nexus-foreground">
                Enter your text
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-nexus-muted">
                Type directly into the editor, stream voice from your microphone, or upload documents and images.
              </p>
            </div>

            {/* Step 2 */}
            <div className="relative rounded-2xl border border-nexus-border bg-nexus-panel p-6 shadow-sm">
              <div className="font-mono text-3xl font-black text-nexus-accent/40">
                02
              </div>
              <h3 className="mt-3 text-lg font-bold text-nexus-foreground">
                Choose your language and style
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-nexus-muted">
                Select your source and target languages, and choose from General, Formal, or Casual stylistic tones.
              </p>
            </div>

            {/* Step 3 */}
            <div className="relative rounded-2xl border border-nexus-border bg-nexus-panel p-6 shadow-sm">
              <div className="font-mono text-3xl font-black text-nexus-accent/40">
                03
              </div>
              <h3 className="mt-3 text-lg font-bold text-nexus-foreground">
                Get your AI translation
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-nexus-muted">
                Receive instant translation results, listen with speech synthesis, or review alternative phrasings.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Technology Section */}
      <section id="technology" className="border-t border-nexus-border bg-nexus-surface/40 py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-nexus-accent">
              Architecture
            </p>
            <h2 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">
              Engineered With Modern Technologies
            </h2>
            <p className="mt-3 text-sm text-nexus-muted">
              The production-grade stack powering Nexus Translator.
            </p>
          </div>

          <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {/* Tech 1 */}
            <div className="rounded-xl border border-nexus-border bg-nexus-panel p-5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-nexus-muted">
                Frontend
              </span>
              <h4 className="mt-1 text-base font-bold text-nexus-foreground">Next.js 14</h4>
              <p className="mt-2 text-xs text-nexus-muted">
                React 18, TypeScript, TailwindCSS, and client-side audio streaming.
              </p>
            </div>

            {/* Tech 2 */}
            <div className="rounded-xl border border-nexus-border bg-nexus-panel p-5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-nexus-muted">
                Backend
              </span>
              <h4 className="mt-1 text-base font-bold text-nexus-foreground">FastAPI</h4>
              <p className="mt-2 text-xs text-nexus-muted">
                Python 3.12, Uvicorn ASGI, AsyncIO, and Starlette WebSockets.
              </p>
            </div>

            {/* Tech 3 */}
            <div className="rounded-xl border border-nexus-border bg-nexus-panel p-5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-nexus-muted">
                AI / Translation
              </span>
              <h4 className="mt-1 text-base font-bold text-nexus-foreground">LibreTranslate & RapidOCR</h4>
              <p className="mt-2 text-xs text-nexus-muted">
                Neural machine translation, ONNX OCR, gTTS, and hybrid fallback.
              </p>
            </div>

            {/* Tech 4 */}
            <div className="rounded-xl border border-nexus-border bg-nexus-panel p-5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-nexus-muted">
                Database
              </span>
              <h4 className="mt-1 text-base font-bold text-nexus-foreground">PostgreSQL / SQLite</h4>
              <p className="mt-2 text-xs text-nexus-muted">
                SQLAlchemy 2.0 ORM with automated local fallback persistence.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-nexus-border bg-nexus-panel py-12">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold tracking-tight">NEXUS TRANSLATOR</span>
              </div>
              <p className="mt-1 text-xs text-nexus-muted">
                &quot;Connecting languages through technology.&quot;
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-6 text-xs text-nexus-muted">
              <button
                type="button"
                onClick={() => scrollToWorkspace("translator")}
                className="hover:text-nexus-foreground transition"
              >
                Translator
              </button>
              <a href="#features" className="hover:text-nexus-foreground transition">
                Features
              </a>
              <a href="#how-it-works" className="hover:text-nexus-foreground transition">
                How It Works
              </a>
              <a href="#technology" className="hover:text-nexus-foreground transition">
                Technology
              </a>
              <a
                href="#overview"
                className="font-medium text-nexus-accent hover:underline"
              >
                Back to top ↑
              </a>
            </div>
          </div>

          <div className="mt-8 border-t border-nexus-border/60 pt-6 text-center text-xs text-nexus-muted/80">
            © 2026 Nexus Translator • Precision Multilingual AI Engine
          </div>
        </div>
      </footer>
    </div>
  );
}
