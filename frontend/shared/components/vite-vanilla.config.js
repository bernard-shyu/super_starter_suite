import { defineConfig } from 'vite';
import path from 'path';

// Separate Vite config for building vanilla JS components
export default defineConfig({
  build: {
    lib: {
      entry: {
        'vanilla-workflow-progress-card': path.resolve(__dirname, 'vanilla-js/WorkflowProgressCard.js'),
        'vanilla-human-input-cli': path.resolve(__dirname, 'vanilla-js/HumanInputCLI.js'),
      },
      name: 'WorkflowUIComponents',
      fileName: (format, entryName) => `${entryName}.js`,
      formats: ['es'], // Changed from 'umd' to 'es' to support multiple entries
    },
    rollupOptions: {
      external: [],
      output: {
        globals: {},
      },
    },
    sourcemap: true,
    minify: 'terser',
    outDir: 'dist/vanilla',
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '../../'),
    },
  },
});
