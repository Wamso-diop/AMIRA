import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';

// Panneau latéral (React) + service worker. Le script de contenu est construit à part
// (vite.content.config.ts) car il doit être un fichier IIFE autonome.
export default defineConfig({
  plugins: [react()],
  base: './',
  // dist/ est vidé par le script de construction : pas ici, pour que le mode surveillance ne
  // supprime pas content.js construit à côté.
  server: { open: '/dev.html', watch: { ignored: ['**/dist/**', '**/tests/**'] } },
  build: {
    outDir: 'dist',
    emptyOutDir: false,
    rollupOptions: {
      input: {
        sidepanel: resolve(__dirname, 'sidepanel.html'),
        background: resolve(__dirname, 'src/background/index.ts'),
      },
      output: {
        entryFileNames: (chunk) => (chunk.name === 'background' ? 'background.js' : 'assets/[name]-[hash].js'),
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.ts'],
  },
} as never);
