/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: { primary: { DEFAULT: '#2563eb', 50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 600: '#2563eb', 700: '#1d4ed8' } },
      fontFamily: { sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'] }
    }
  },
  plugins: []
}
