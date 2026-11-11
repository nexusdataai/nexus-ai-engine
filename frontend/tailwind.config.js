/**
 * Tailwind is wired to the design tokens in src/styles/tokens.css.
 * Add colours there first, then expose them here. Never add raw hex values.
 * Same token set as the Nexus AI ontology product and website.
 */
const token = (name) => `hsl(var(--${name}))`;

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      fontSize: {
        "2xs": ["0.75rem", { lineHeight: "1rem" }],
        xs: ["0.75rem", { lineHeight: "1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.875rem", { lineHeight: "1.375rem" }],
        md: ["0.9375rem", { lineHeight: "1.5rem" }],
        lg: ["1.0625rem", { lineHeight: "1.5rem", letterSpacing: "-0.01em" }],
        xl: ["1.25rem", { lineHeight: "1.75rem", letterSpacing: "-0.02em" }],
        "2xl": ["1.5rem", { lineHeight: "2rem", letterSpacing: "-0.025em" }],
        "3xl": ["1.875rem", { lineHeight: "2.25rem", letterSpacing: "-0.03em" }],
        "4xl": ["2.375rem", { lineHeight: "2.625rem", letterSpacing: "-0.035em" }],
      },
      borderRadius: {
        xl: "calc(var(--radius) + 4px)",
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      colors: {
        border: token("border"),
        "border-strong": token("border-strong"),
        input: token("input"),
        ring: token("ring"),
        background: token("background"),
        foreground: token("foreground"),
        "subtle-foreground": token("subtle-foreground"),
        surface: { 2: token("surface-2"), 3: token("surface-3") },
        primary: { DEFAULT: token("primary"), foreground: token("primary-foreground") },
        brand: { DEFAULT: token("brand"), hi: token("brand-hi"), lo: token("brand-lo") },
        secondary: { DEFAULT: token("secondary"), foreground: token("secondary-foreground") },
        destructive: { DEFAULT: token("destructive"), foreground: token("destructive-foreground") },
        success: { DEFAULT: token("success"), foreground: token("success-foreground") },
        warning: { DEFAULT: token("warning"), foreground: token("warning-foreground") },
        info: { DEFAULT: token("info"), foreground: token("info-foreground") },
        muted: { DEFAULT: token("muted"), foreground: token("muted-foreground") },
        accent: { DEFAULT: token("accent"), foreground: token("accent-foreground") },
        popover: { DEFAULT: token("popover"), foreground: token("popover-foreground") },
        card: { DEFAULT: token("card"), foreground: token("card-foreground") },
        chart: {
          1: token("chart-1"), 2: token("chart-2"), 3: token("chart-3"),
          4: token("chart-4"), 5: token("chart-5"), 6: token("chart-6"),
        },
        sidebar: { DEFAULT: token("sidebar"), foreground: token("sidebar-fg"), border: token("sidebar-border") },
        header: { DEFAULT: token("header") },
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      transitionTimingFunction: {
        brand: "var(--ease)",
        "brand-out": "var(--ease-out)",
      },
      transitionDuration: { fast: "120ms", DEFAULT: "200ms", slow: "420ms" },
      animation: {
        "fade-in": "fade-in var(--dur) var(--ease) both",
        "fade-up": "fade-up var(--dur-slow) var(--ease-out) both",
        "scale-in": "scale-in var(--dur) var(--ease-out) both",
        "slide-in-right": "slide-in-right var(--dur-slow) var(--ease-out) both",
      },
    },
  },
  plugins: [],
};
