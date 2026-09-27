"use client";

import { useEffect, useRef, useState } from "react";
import {
  getLanguageLabel,
  getSourceLanguages,
  getTranslatableLanguages,
} from "@/lib/languages";
import {
  deleteDocument,
  getDocumentDownloadUrl,
  listDocuments,
  translateDocument,
} from "@/services/api";
import type { DocumentItem } from "@/types/language";
import { LanguageSelect } from "./LanguageSelect";

interface DocumentTranslatorProps {
  onHistoryRefresh?: () => void;
}

const MAX_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024; // 20MB
const ALLOWED_EXTENSIONS = ["pdf", "docx", "txt"];

type ProgressStep =
  | "idle"
  | "uploading"
  | "extracting"
  | "detecting"
  | "translating"
  | "generating";

export function DocumentTranslator({ onHistoryRefresh }: DocumentTranslatorProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetLanguage, setTargetLanguage] = useState<string>("en");
  const [sourceLanguage, setSourceLanguage] = useState<string>("auto");
  const [translationStyle, setTranslationStyle] = useState<"general" | "formal" | "casual">("general");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [progressStep, setProgressStep] = useState<ProgressStep>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DocumentItem | null>(null);

  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [recentDocs, setRecentDocs] = useState<DocumentItem[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const progressTimerRef = useRef<NodeJS.Timeout[]>([]);

  const sourceLanguages = getSourceLanguages();
  const translatableLanguages = getTranslatableLanguages();

  const loadRecentDocuments = async () => {
    setIsLoadingDocs(true);
    try {
      const res = await listDocuments();
      setRecentDocs(res.items);
    } catch {
      // ignore background listing error
    } finally {
      setIsLoadingDocs(false);
    }
  };

  useEffect(() => {
    loadRecentDocuments();
    return () => {
      progressTimerRef.current.forEach(clearTimeout);
    };
  }, []);

  const validateAndSetFile = (file: File) => {
    setError(null);
    setResult(null);

    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file type ".${ext}". Please upload a PDF (.pdf), Word (.docx), or TXT (.txt) document.`);
      return;
    }

    if (file.size > MAX_DOCUMENT_SIZE_BYTES) {
      setError("Document size exceeds the 20MB maximum limit. Please select a smaller document.");
      return;
    }

    setSelectedFile(file);
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

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setResult(null);
    setError(null);
    setProgressStep("idle");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const startProgressSimulation = () => {
    progressTimerRef.current.forEach(clearTimeout);
    progressTimerRef.current = [];

    setProgressStep("uploading");

    const t1 = setTimeout(() => setProgressStep("extracting"), 800);
    const t2 = setTimeout(() => setProgressStep("detecting"), 1800);
    const t3 = setTimeout(() => setProgressStep("translating"), 2800);
    const t4 = setTimeout(() => setProgressStep("generating"), 4200);

    progressTimerRef.current = [t1, t2, t3, t4];
  };

  const handleTranslateDocument = async () => {
    if (!selectedFile) {
      setError("Please select a PDF, DOCX, or TXT document first.");
      return;
    }

    setIsLoading(true);
    setError(null);
    startProgressSimulation();

    try {
      const res = await translateDocument({
        file: selectedFile,
        targetLanguage,
        sourceLanguage,
        translationStyle,
        filename: selectedFile.name,
      });

      setResult(res);
      await loadRecentDocuments();
      if (onHistoryRefresh) {
        onHistoryRefresh();
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Document translation failed. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
      setProgressStep("idle");
      progressTimerRef.current.forEach(clearTimeout);
    }
  };

  const handleDeleteDoc = async (id: number) => {
    try {
      await deleteDocument(id);
      if (result && result.id === id) {
        setResult(null);
      }
      await loadRecentDocuments();
      if (onHistoryRefresh) {
        onHistoryRefresh();
      }
    } catch {
      setError("Failed to delete document.");
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getDocTypeIcon = (type: string) => {
    const t = type.toLowerCase();
    if (t === "pdf") {
      return (
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/10 font-mono text-xs font-bold text-red-400">
          PDF
        </span>
      );
    }
    if (t === "docx") {
      return (
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 font-mono text-xs font-bold text-indigo-400">
          DOCX
        </span>
      );
    }
    return (
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10 font-mono text-xs font-bold text-blue-400">
        TXT
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-nexus-border bg-nexus-surface/60 p-5 shadow-nexus backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-nexus-foreground sm:text-xl">
              Document Translator
            </h2>
            <p className="mt-1 text-xs text-nexus-muted sm:text-sm">
              Translate PDF, Word DOCX, and TXT documents while preserving paragraph layout, tables, headings, and formatting.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-nexus-muted">
            <span className="inline-flex items-center rounded-full border border-nexus-border bg-nexus-surface px-2.5 py-1 font-mono text-[11px]">
              PDF · DOCX · TXT · Max 20MB
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: Upload & Controls */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Upload Zone */}
        <div className="flex flex-col gap-4">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword,text/plain"
            className="hidden"
            onChange={handleFileChange}
            id="document-file-input"
          />

          {!selectedFile ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`group flex min-h-[260px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-all ${
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
              aria-label="Upload Document Area"
            >
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-nexus-accent/10 text-nexus-accent transition group-hover:scale-110">
                <svg
                  className="h-7 w-7"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium text-nexus-foreground">
                <span className="text-nexus-accent underline">Click to upload</span> or drag and drop
              </p>
              <p className="mt-1 text-xs text-nexus-muted">
                PDF (.pdf), Word (.docx), or Plain Text (.txt) up to 20MB
              </p>
            </div>
          ) : (
            <div className="flex min-h-[260px] flex-col justify-between rounded-2xl border border-nexus-border bg-nexus-surface/60 p-6">
              <div className="flex items-start gap-4">
                {getDocTypeIcon(selectedFile.name.split(".").pop() || "txt")}
                <div className="flex-1 overflow-hidden">
                  <h4 className="truncate font-semibold text-nexus-foreground">
                    {selectedFile.name}
                  </h4>
                  <p className="mt-1 text-xs text-nexus-muted">
                    Size: {formatFileSize(selectedFile.size)} · Type:{" "}
                    {selectedFile.name.split(".").pop()?.toUpperCase()}
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-nexus-border/60 bg-nexus-surface/40 p-3 text-xs text-nexus-muted">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  <span>Document loaded and ready for processing</span>
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t border-nexus-border/60 pt-4">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-lg border border-nexus-border bg-nexus-surface px-3 py-1.5 text-xs font-medium text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                >
                  Choose Different File
                </button>
                <button
                  type="button"
                  onClick={handleRemoveFile}
                  className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 transition hover:bg-red-500/20"
                >
                  Remove
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right: Language Controls & Translate Action */}
        <div className="flex flex-col justify-between gap-6 rounded-2xl border border-nexus-border bg-nexus-surface/60 p-5 backdrop-blur">
          <div className="space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-nexus-accent">
              Translation Settings
            </h3>

            <div className="grid gap-4 sm:grid-cols-2">
              <LanguageSelect
                id="doc-source-language-select"
                label="Source Language"
                value={sourceLanguage}
                languages={sourceLanguages}
                onChange={setSourceLanguage}
              />

              <LanguageSelect
                id="doc-target-language-select"
                label="Target Language"
                value={targetLanguage}
                languages={translatableLanguages}
                onChange={setTargetLanguage}
              />
            </div>

            <div>
              <label
                htmlFor="doc-translation-style"
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

            {/* Dynamic Progress indicator during translation */}
            {isLoading && (
              <div className="space-y-3 rounded-xl border border-nexus-accent/30 bg-nexus-accent/10 p-4">
                <div className="flex items-center gap-3">
                  <svg className="h-5 w-5 animate-spin text-nexus-accent" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span className="text-xs font-semibold capitalize text-nexus-accent">
                    {progressStep === "uploading" && "Uploading document..."}
                    {progressStep === "extracting" && "Extracting text & running OCR on scanned pages..."}
                    {progressStep === "detecting" && "Detecting source language..."}
                    {progressStep === "translating" && "Translating paragraphs..."}
                    {progressStep === "generating" && "Generating formatted document..."}
                    {progressStep === "idle" && "Processing document..."}
                  </span>
                </div>
                <div className="flex gap-1.5">
                  {(["uploading", "extracting", "detecting", "translating", "generating"] as const).map(
                    (step, idx) => (
                      <div
                        key={step}
                        className={`h-1.5 flex-1 rounded-full transition-colors ${
                          idx <= ["uploading", "extracting", "detecting", "translating", "generating"].indexOf(progressStep)
                            ? "bg-nexus-accent"
                            : "bg-nexus-border"
                        }`}
                      />
                    )
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="pt-2">
            <button
              type="button"
              onClick={handleTranslateDocument}
              disabled={!selectedFile || isLoading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-nexus-accent py-3 text-sm font-semibold text-white shadow-nexus transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isLoading ? (
                <span>Translating Document...</span>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  <span>Translate Document</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Completion Panel */}
      {result && (
        <div className="space-y-4 rounded-2xl border border-nexus-border bg-nexus-surface/80 p-6 shadow-nexus backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-nexus-border pb-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-400">
                Status: Completed
              </span>
              <span className="text-xs text-nexus-muted">
                Source: <span className="font-semibold text-nexus-foreground">{getLanguageLabel(result.source_language)}</span>
              </span>
              <span className="text-xs text-nexus-muted">
                Target: <span className="font-semibold text-nexus-accent">{getLanguageLabel(result.target_language)}</span>
              </span>
              {result.page_count > 1 && (
                <span className="text-xs text-nexus-muted">
                  Pages: <span className="font-semibold text-nexus-foreground">{result.page_count}</span>
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <a
                href={getDocumentDownloadUrl(result.id)}
                download={result.download_filename}
                className="inline-flex items-center gap-1.5 rounded-xl bg-nexus-accent px-4 py-2 text-xs font-semibold text-white shadow transition hover:opacity-90"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download
              </a>
              <button
                type="button"
                onClick={() => handleDeleteDoc(result.id)}
                className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs font-semibold text-red-400 transition hover:bg-red-500/20"
              >
                Delete
              </button>
            </div>
          </div>

          {/* Sample Previews */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-nexus-border bg-nexus-surface/50 p-4">
              <span className="text-xs font-semibold uppercase tracking-wider text-nexus-muted">
                Original Preview Sample
              </span>
              <p className="mt-2 line-clamp-4 font-sans text-xs leading-relaxed text-nexus-muted">
                {result.original_text_sample || "No sample text available."}
              </p>
            </div>
            <div className="rounded-xl border border-nexus-border bg-nexus-surface/50 p-4">
              <span className="text-xs font-semibold uppercase tracking-wider text-nexus-accent">
                Translated Preview Sample
              </span>
              <p className="mt-2 line-clamp-4 font-sans text-xs leading-relaxed text-nexus-foreground">
                {result.translated_text_sample || "No sample translation available."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Document History Table */}
      <div className="space-y-4 rounded-2xl border border-nexus-border bg-nexus-surface/60 p-6 shadow-nexus backdrop-blur">
        <div className="flex items-center justify-between border-b border-nexus-border pb-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-nexus-foreground">
            Document History ({recentDocs.length})
          </h3>
          <button
            type="button"
            onClick={loadRecentDocuments}
            className="text-xs text-nexus-muted hover:text-nexus-accent"
          >
            Refresh
          </button>
        </div>

        {isLoadingDocs && recentDocs.length === 0 ? (
          <p className="py-6 text-center text-xs text-nexus-muted">Loading documents...</p>
        ) : recentDocs.length === 0 ? (
          <p className="py-6 text-center text-xs text-nexus-muted">
            No translated documents yet. Upload a PDF, DOCX, or TXT document above to get started.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-nexus-foreground">
              <thead>
                <tr className="border-b border-nexus-border text-nexus-muted">
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium">Document Name</th>
                  <th className="pb-2 font-medium">Languages</th>
                  <th className="pb-2 font-medium">Size</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-nexus-border/60">
                {recentDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-nexus-surface/40">
                    <td className="py-3">
                      {getDocTypeIcon(doc.document_type)}
                    </td>
                    <td className="py-3 font-medium">
                      <div className="max-w-[180px] truncate sm:max-w-xs">{doc.filename}</div>
                    </td>
                    <td className="py-3 text-nexus-muted">
                      {doc.source_language.toUpperCase()} ➔ {doc.target_language.toUpperCase()}
                    </td>
                    <td className="py-3 text-nexus-muted">
                      {formatFileSize(doc.file_size)}
                    </td>
                    <td className="py-3">
                      <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                        {doc.status}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <div className="inline-flex items-center gap-2">
                        <a
                          href={getDocumentDownloadUrl(doc.id)}
                          download={doc.download_filename}
                          className="rounded border border-nexus-border bg-nexus-surface px-2.5 py-1 text-[11px] font-medium text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
                        >
                          Download
                        </a>
                        <button
                          type="button"
                          onClick={() => handleDeleteDoc(doc.id)}
                          className="rounded border border-red-500/20 bg-red-500/10 px-2 py-1 text-[11px] font-medium text-red-400 transition hover:bg-red-500/20"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
