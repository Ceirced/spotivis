import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig(({ mode }) => {
  const isDev = mode === 'development';
  
  return {
    root: 'app/typescript',
    build: {
      lib: {
        entry: {
          'combined-graph': resolve(__dirname, 'app/typescript/combined-graph.ts'),
        },
        formats: ['iife'],
        name: 'SpotiVis'
      },
      outDir: '../static/js/build',
      emptyOutDir: true,  // Safe to empty since it's only for builds
      minify: !isDev,  // Minify only in production
      sourcemap: isDev ? 'inline' : false,  // Inline sourcemaps for dev
    rollupOptions: {
      output: {
        entryFileNames: '[name].js',
        format: 'iife',
        globals: {
          d3: 'd3'
        }
      }
    }
  },
    resolve: {
      alias: {
        '@': resolve(__dirname, 'app')
      }
    }
  };
});