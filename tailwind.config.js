/** @type {import('tailwindcss').Config} */

const defaultTheme = require('tailwindcss/defaultTheme');

let colors =
  'red|yellow|green|blue|indigo|purple|pink|rose|violet|green|orange|gray|stone|black';
module.exports = {
  content: [
    './app/templates/**/*.html',
    './app/static/**/*.js',
    './app/static/**/*.svg',
  ],
  safelist: [
    {
      pattern: /row-start-+/, // needed for the year grid since the start of the year is not static
    },
    {
      pattern: new RegExp(`bg-(${colors})-500`),
    },
    {
      pattern: new RegExp(`border-(${colors})-(200|300|500)`),
    },
    {
      pattern: new RegExp(`border-(${colors})-(600)`),
      variants: ['hover'],
    },
    {
      pattern: new RegExp(`text-(${colors})-(600)`),
      variants: ['hover'],
    },
    {
      pattern: new RegExp(`text-(${colors})-(200|500)`),
    },
    {
      pattern: new RegExp(`(from)-(${colors})-(300|500)`),
    },
    {
      pattern: new RegExp(`to-(${colors})-(300|500)`),
    },
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter var', ...defaultTheme.fontFamily.sans],
      },
      spacing: {
        'grid-gap': '8px',
        'grid-gap-lg': '20px',
      },
      colors: {
        primary: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
      },
    },
  },
  plugins: [require('daisyui')],
  daisyui: {
    themes: false, // false: only light + dark | true: all themes | array: specific themes like this ["light", "dark", "cupcake"]
    darkTheme: 'dark', // name of one of the included themes for dark mode
    base: false, // applies background color and foreground color for root element by default
    styled: true, // include daisyUI colors and design decisions for all components
    utils: true, // adds responsive and modifier utility classes
    prefix: '', // prefix for daisyUI classnames (components, modifiers and responsive class names. Not colors)
    logs: true, // Shows info about daisyUI version and used config in the console when building your CSS
    themeRoot: ':root', // The element that receives theme color CSS variables
  },
};
