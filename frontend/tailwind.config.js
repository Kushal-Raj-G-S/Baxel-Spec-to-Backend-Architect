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
        ember: "#C2D68C",
        dune: "#3b3a36",
        mint: "#869E58",
        sand: "#f7e7ce",
        olive: {
          50: "#1F261D",
          100: "#2a3a2e",
          200: "#3d4f3f",
          300: "#526652",
          400: "#6b8e23",
          500: "#869E58",
          600: "#C2D68C",
          700: "#a8c078",
          800: "#8fa864",
          900: "#768e50"
        }
      },
      backgroundImage: {
        "radial-grid": "radial-gradient(circle at 1px 1px, rgba(74, 93, 74, 0.18) 1px, transparent 0)",
        "sunset": "linear-gradient(120deg, #f5f5f0 0%, #e8e8e0 40%, #d0d0c0 100%)",
        "olive-gradient": "linear-gradient(135deg, #1a2f1a 0%, #2d3a2d 50%, #4a5d4a 100%)",
        "olive-light": "linear-gradient(180deg, #f5f5f0 0%, #e8e8e0 100%)"
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
