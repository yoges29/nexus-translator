import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        "nexus-bg": "var(--nexus-bg)",
        "nexus-foreground": "var(--nexus-foreground)",
        "nexus-panel": "var(--nexus-panel)",
        "nexus-surface": "var(--nexus-surface)",
        "nexus-border": "var(--nexus-border)",
        "nexus-muted": "var(--nexus-muted)",
        "nexus-accent": "var(--nexus-accent)",
      },
      boxShadow: {
        nexus: "0 10px 40px rgba(15, 23, 42, 0.08)",
      },
    },
  },
  plugins: [],
};
export default config;
