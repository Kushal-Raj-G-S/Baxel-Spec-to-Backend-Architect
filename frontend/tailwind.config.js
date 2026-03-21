/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"]
      },
      colors: {
        ink: "#0b0d12",
        bone: "#f2f0ea",
        haze: "#e2e1dd",
        ember: "#f05d23",
        dune: "#3b3a36",
        mint: "#00c2a8",
        sand: "#f7e7ce"
      },
      backgroundImage: {
        "radial-grid": "radial-gradient(circle at 1px 1px, rgba(15, 15, 15, 0.18) 1px, transparent 0)",
        "sunset": "linear-gradient(120deg, #f7e7ce 0%, #f2f0ea 40%, #c9f2ea 100%)"
      },
      animation: {
        "float-slow": "float 10s ease-in-out infinite",
        "fade-up": "fadeUp 700ms ease-out"
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-12px)" }
        },
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        }
      }
    }
  },
  plugins: []
};
