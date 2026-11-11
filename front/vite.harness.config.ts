import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// Banc d'essai pour Playwright : le moteur du script de contenu branché sur le mock, sans chrome.*.
export default defineConfig({
  build: {
    outDir: 'tests/e2e/.harness',
    emptyOutDir: true,
    lib: { entry: resolve(__dirname, 'src/content/harness.ts'), name: 'AmiraHarness', formats: ['iife'], fileName: () => 'harness.js' },
  },
});
