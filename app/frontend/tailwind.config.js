/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        eid: {
          olive: '#868C54',
          sage: '#C2C8A2',
          'light-sage': '#F0F2E8',
          'warm-gray': '#737569',
          dark: '#2C2C2A',
        },
      },
      fontFamily: {
        heading: ['Lato', 'sans-serif'],
        body: ['Arial Narrow', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
