/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./public_html/**/*.{html,js}",
    "./static/js/**/*.js",
    "./*.html"
  ],
  theme: {
    extend: {
      colors: {
        'brand-gold': '#f0b90b',
        'brand-dark-blue': '#0b0e11',
        'brand-border': '#1f2630',
      }
    },
  },
  plugins: [],
}