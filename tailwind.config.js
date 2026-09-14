module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js'
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f2f9f1',
          100: '#e1f0de',
          500: '#15803d',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
        },
        accent: {
          500: '#f59e0b',
          600: '#d97706',
        }
      }
    }
  },
  plugins: []
}
