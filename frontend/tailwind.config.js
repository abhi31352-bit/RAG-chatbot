/** @type {import('tailwindcss').Config} */
import typography from '@tailwindcss/typography'
import defaultTheme from 'tailwindcss/defaultTheme'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
      },
    },
  },
  // The message bubbles use `prose` to style rendered markdown. Without this
  // plugin the class is a no-op and answers come out as unstyled paragraphs.
  plugins: [typography],
}
