/** @type {import('tailwindcss').Config} */
// Linear-inspired design tokens (per /DESIGN.md)
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Linear backgrounds (dark-mode-native)
        bg: {
          black: "#08090a", // marketing background
          panel: "#0f1011", // sidebar / panel
          surface: "#191a1b", // elevated cards / dropdowns
          surface2: "#28282c", // hover / slightly elevated
        },
        // Text tiers
        ink: {
          primary: "#f7f8f8", // near-white (not pure white)
          secondary: "#d0d6e0",
          muted: "#8a8f98",
          subtle: "#62666d",
        },
        // Brand indigo-violet (only chromatic accent in the system)
        brand: {
          DEFAULT: "#5e6ad2",
          accent: "#7170ff",
          hover: "#828fff",
        },
        // Status
        success: "#10b981",
        warning: "#f59e0b",
        error: "#ef4444",
        info: "#3b82f6",
        // Borders are usually rgba — exposed as utilities below via CSS vars
      },
      fontFamily: {
        sans: [
          "Inter Variable",
          "Inter",
          "SF Pro Display",
          "-apple-system",
          "system-ui",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ["Berkeley Mono", "ui-monospace", "SF Mono", "Menlo", "monospace"],
      },
      fontWeight: {
        // Linear's signature weight (between regular and medium)
        signature: "510",
        emphasis: "590",
      },
      letterSpacing: {
        // Display tightening
        "display-xl": "-0.022em", // ~ -1.584px @ 72px
        "display-lg": "-0.022em", // ~ -1.408px @ 64px
        display: "-0.022em", // ~ -1.056px @ 48px
        "heading-1": "-0.022em",
        "heading-2": "-0.012em",
        "heading-3": "-0.012em",
        body: "-0.011em",
      },
      borderRadius: {
        DEFAULT: "6px", // Linear button standard
        card: "8px",
        panel: "12px",
        large: "22px",
      },
      boxShadow: {
        // Linear depth tiers
        focus: "0 4px 12px rgba(0,0,0,0.1)",
        elevated: "0 2px 4px rgba(0,0,0,0.4)",
        ring: "0 0 0 1px rgba(0,0,0,0.2)",
        dialog:
          "0 8px 2px rgba(0,0,0,0), 0 5px 2px rgba(0,0,0,0.01), 0 3px 2px rgba(0,0,0,0.04), 0 1px 1px rgba(0,0,0,0.07)",
        inset: "inset 0 0 12px rgba(0,0,0,0.2)",
      },
    },
  },
  plugins: [],
};
