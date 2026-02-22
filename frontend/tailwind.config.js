/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          navy: '#0D4E81',
          cyan: '#009EFA',
          indigo: '#343A68',
          plum: '#52336F',
          magenta: '#7B3D87',
          teal: '#5693A5',
          lavender: '#A6B3E8',
          lavender2: '#A9B4E8'
        }
      }
    },
  },
  plugins: [],
}