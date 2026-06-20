/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // trajectory direction palette
        leap: "#16a34a",
        forward: "#2563eb",
        lateral: "#64748b",
        stall: "#a16207",
        backward: "#dc2626",
      },
    },
  },
  plugins: [],
};
