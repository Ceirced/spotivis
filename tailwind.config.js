/** @type {import('tailwindcss').Config} */

const defaultTheme = require('tailwindcss/defaultTheme');

module.exports = {
  content: [
    './app/templates/**/*.html',
    './app/static/**/*.js',
    './app/static/**/*.svg',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter var', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        background: {
          light: '#f4f4f5',
          dark: '#000000'
        },
        text: {
          light: '#000000',
          dark: '#ffffff'
        },
      },
    },
  },
};
