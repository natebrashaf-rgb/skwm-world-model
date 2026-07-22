import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#16324f",
        gold: "#c49a3a",
        ink: "#172033",
        mist: "#eef3f7",
        teal: "#0d9488",
        coral: "#e8635a",
        lavender: "#7c3aed",
      },
      boxShadow: {
        panel: "0 12px 30px rgba(22, 50, 79, 0.08)",
        card: "0 2px 8px rgba(22, 50, 79, 0.06)",
      },
    },
  },
  plugins: [],
};

export default config;
