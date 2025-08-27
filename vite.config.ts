import { defineConfig } from 'vite';
import { resolve } from 'path';
import { glob } from 'glob';

export default defineConfig(({ mode }) => {
  const isDev = mode === 'development';
  
  // Automatically find all .ts files (excluding test files)
  const entries = glob.sync('app/typescript/*.ts')
    .filter(file => !file.includes('.test.') && !file.includes('.spec.'))
    .reduce((acc, file) => {
      const name = file.split('/').pop()!.replace('.ts', '');
      acc[name] = resolve(__dirname, file);
      return acc;
    }, {} as Record<string, string>);
  
  return {
    root: 'app/typescript',
    build: {
      lib: {
        entry: entries,
        formats: ['es'],  // ES modules instead of IIFE
      },
      outDir: '../static/js/build',
      emptyOutDir: true,
      minify: !isDev,
      sourcemap: isDev ? 'inline' : false,
      rollupOptions: {
        // No externals - bundle everything including D3
        output: {
          entryFileNames: '[name].js',
          format: 'es'
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