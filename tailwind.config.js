/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        srt: {
          primary: '#7C3AED',
          secondary: '#5B21B6',
          light: '#A78BFA'
        },
        ktx: {
          primary: '#EF4444',
          secondary: '#DC2626',
          light: '#FCA5A5'
        }
      }
    }
  },
  plugins: []
}
