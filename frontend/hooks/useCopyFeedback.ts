"use client";

import { useCallback, useState } from "react";

export function useCopyFeedback(timeoutMs = 2000) {
  const [copiedField, setCopiedField] = useState<"source" | "target" | null>(null);

  const copy = useCallback(
    async (text: string, field: "source" | "target") => {
      if (!text.trim()) return;
      try {
        await navigator.clipboard.writeText(text);
        setCopiedField(field);
        window.setTimeout(() => setCopiedField(null), timeoutMs);
      } catch {
        setCopiedField(null);
      }
    },
    [timeoutMs],
  );

  return { copiedField, copy };
}
