"use client";

import { getLanguageLabel } from "@/lib/languages";
import { deleteHistoryItem, fetchHistory } from "@/services/api";
import type { HistoryItem } from "@/types/language";
import { useCallback, useEffect, useState } from "react";

interface HistoryPanelProps {
  refreshToken: number;
  onReuse: (item: HistoryItem) => void;
}

export function HistoryPanel({ refreshToken, onReuse }: HistoryPanelProps) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHistory();
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load history.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory, refreshToken]);

  const handleDelete = async (id: number) => {
    try {
      await deleteHistoryItem(id);
      setItems((current) => current.filter((item) => item.id !== id));
      if (expandedId === id) setExpandedId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete item.");
    }
  };

  return (
    <section aria-label="Translation history" className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-tight text-nexus-foreground">History</h2>
        <button
          type="button"
          onClick={() => void loadHistory()}
          className="rounded-lg border border-nexus-border px-3 py-1.5 text-xs uppercase tracking-wide text-nexus-muted transition hover:border-nexus-accent hover:text-nexus-accent"
        >
          Refresh
        </button>
      </div>

      {loading ? <p className="text-sm text-nexus-muted animate-pulse">Loading history...</p> : null}
      {error ? (
        <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-300">
          {error}
        </p>
      ) : null}

      {!loading && items.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-nexus-border px-4 py-8 text-center text-sm text-nexus-muted">
          No translations saved yet. Translate something to see it here.
        </p>
      ) : null}

      <ul className="space-y-3">
        {items.map((item) => {
          const isExpanded = expandedId === item.id;
          const isVoice = item.input_method === "voice";
          return (
            <li
              key={item.id}
              className="rounded-2xl border border-nexus-border bg-nexus-panel p-4 shadow-nexus transition hover:border-nexus-accent/40"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                        isVoice
                          ? "bg-purple-500/15 text-purple-600 dark:text-purple-300"
                          : "bg-nexus-surface text-nexus-muted border border-nexus-border"
                      }`}
                    >
                      <span>{isVoice ? "🎤 Voice" : "📝 Text"}</span>
                    </span>

                    {item.translation_style && item.translation_style !== "general" ? (
                      <span className="inline-flex rounded-full bg-nexus-accent/10 px-2 py-0.5 text-[10px] font-medium text-nexus-accent capitalize">
                        {item.translation_style}
                      </span>
                    ) : null}

                    {item.detected_language ? (
                      <span className="inline-flex rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                        Auto: {item.detected_language.toUpperCase()}
                      </span>
                    ) : null}
                  </div>

                  <p className="mt-2 text-xs uppercase tracking-[0.16em] text-nexus-muted">
                    {getLanguageLabel(item.source_language)} → {getLanguageLabel(item.target_language)}
                  </p>
                  <p className="mt-0.5 text-[11px] text-nexus-muted">
                    {new Date(item.created_at).toLocaleString()}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setExpandedId(isExpanded ? null : item.id)}
                    className="rounded-lg border border-nexus-border px-3 py-1 text-xs uppercase tracking-wide text-nexus-muted hover:border-nexus-accent hover:text-nexus-accent"
                  >
                    {isExpanded ? "Hide" : "View"}
                  </button>
                  <button
                    type="button"
                    onClick={() => onReuse(item)}
                    className="rounded-lg border border-nexus-border px-3 py-1 text-xs uppercase tracking-wide text-nexus-muted hover:border-nexus-accent hover:text-nexus-accent"
                  >
                    Reuse
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDelete(item.id)}
                    className="rounded-lg border border-red-500/40 px-3 py-1 text-xs uppercase tracking-wide text-red-500 hover:bg-red-500/10"
                  >
                    Delete
                  </button>
                </div>
              </div>

              {isExpanded ? (
                <div className="mt-4 grid gap-3 border-t border-nexus-border pt-4 text-sm lg:grid-cols-2">
                  <div>
                    <p className="mb-1 text-xs uppercase tracking-wide text-nexus-muted">Original</p>
                    <p className="whitespace-pre-wrap text-nexus-foreground">{item.original_text}</p>
                  </div>
                  <div>
                    <p className="mb-1 text-xs uppercase tracking-wide text-nexus-muted">Translation</p>
                    <p className="whitespace-pre-wrap text-nexus-foreground">{item.translated_text}</p>
                  </div>
                </div>
              ) : (
                <p className="mt-3 line-clamp-2 text-sm text-nexus-muted">{item.original_text}</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

