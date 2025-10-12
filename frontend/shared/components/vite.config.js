import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Simple configuration for building vanilla JS components individually
// This avoids the multi-entry UMD limitation
export default defineConfig({
  plugins: [react()],
  build: {
    // Note: For now, the vanilla JS components are distributed as-is
    // They can be bundled by consuming applications or used directly
    sourcemap: false,
    minify: false, // Keep readable for development
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '../../'),
    },
  },
});

// Build Instructions:
// The vanilla JS components are designed to be:
// 1. Used directly in browser environments without bundling
// 2. Bundled by consuming applications that have their own build setup
// 3. Framework-agnostic and zero-dependency for maximum compatibility
//
// React components are imported directly:
// import WorkflowProgressCard from "./shared/components/WorkflowProgressCard.jsx";
// import WorkflowMultiStepAccordion from "./shared/components/WorkflowMultiStepAccordion.jsx";
// import HumanInputCLI from "./shared/components/HumanInputCLI.jsx";
