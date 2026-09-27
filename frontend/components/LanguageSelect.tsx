"use client";

import { getLanguageByCode } from "@/lib/languages";
import type { Language } from "@/types/language";

interface LanguageSelectProps {
  id: string;
  label: string;
  value: string;
  languages: Language[];
  onChange: (code: string) => void;
}

export function LanguageSelect({ id, label, value, languages, onChange }: LanguageSelectProps) {
  const selected = getLanguageByCode(value);

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-medium uppercase tracking-[0.18em] text-nexus-muted">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-nexus-border bg-nexus-surface px-3 py-2.5 text-sm text-nexus-foreground shadow-sm transition focus-visible:border-nexus-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nexus-accent/30"
        aria-label={label}
      >
        {languages.map((language) => (
          <option key={language.code} value={language.code}>
            {language.name} — {language.nativeName}
          </option>
        ))}
      </select>
      {selected?.direction === "rtl" ? (
        <span className="text-[11px] text-nexus-muted">Right-to-left language</span>
      ) : null}
    </div>
  );
}
