/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        teal: {
          950: '#0a2e2e',
          900: '#0d3b3b',
          800: '#145050',
          700: '#1a6464',
          600: '#1f7a7a',
        },
        gold: {
          DEFAULT: '#c8a45e',
          light: '#ddc07a',
          dark: '#a8853e',
        },
        cream: {
          DEFAULT: '#faf6f0',
          dark: '#f0e8d8',
        },
      },
      fontFamily: {
        serif: ['"DM Serif Display"', 'Georgia', 'serif'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
