import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "ks-bg":           "var(--ks-bg)",
        "ks-surface":      "var(--ks-surface)",
        "ks-surface-2":    "var(--ks-surface-2)",
        "ks-hover":        "var(--ks-hover)",
        "ks-border":       "var(--ks-border)",
        "ks-border-sub":   "var(--ks-border-sub)",
        "ks-text":         "var(--ks-text)",
        "ks-text2":        "var(--ks-text2)",
        "ks-text3":        "var(--ks-text3)",
      },
    },
  },
  plugins: [],
};

export default config;
