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
          navy: '#0F172A',
          blue: '#0284C7',
          'blue-soft': '#F0F9FF',
          'blue-gray': '#F8FAFC',
        },
        gov: {
          50: '#f0f5fa',
          100: '#e1ecf5',
          200: '#c3d9eb',
          300: '#95bedc',
          400: '#619ecb',
          500: '#3c82b5',
          600: '#2c6797',
          700: '#24527b',
          800: '#204767',
          900: '#1e3c56',
          950: '#142738',
        },
        india: {
          saffron: '#FF9933',
          navy: '#000080',
          green: '#138808',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
