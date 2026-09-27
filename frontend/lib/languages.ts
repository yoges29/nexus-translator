import registry from "./languages.json";
import type { Language } from "@/types/language";

const languages = registry.languages as Language[];

export function getAllLanguages(): Language[] {
  return languages;
}

export function getTranslatableLanguages(): Language[] {
  return languages.filter((lang) => lang.translationSupported);
}

export function getSourceLanguages(): Language[] {
  return languages.filter((lang) => lang.code === "auto" || lang.translationSupported);
}

export function getLanguageByCode(code: string): Language | undefined {
  return languages.find((lang) => lang.code === code);
}

export function getLanguageLabel(code: string): string {
  const language = getLanguageByCode(code);
  if (!language) return code.toUpperCase();
  return `${language.name} (${language.nativeName})`;
}
