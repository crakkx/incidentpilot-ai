import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        confidence: {
          high: "#15803d",
          medium: "#b45309",
          low: "#b91c1c",
        },
      },
    },
  },
  plugins: [],
};

export default config;
