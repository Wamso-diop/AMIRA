import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// Construit le guide d'installation (guide.html) dans ../backend/guide/ : le serveur Amira le sert à /guide/,
// et `python demo.py` l'ouvre. Rien n'y est externe : polices et images sont dans le dossier.
export default defineConfig({
  base: './',
  publicDir: false,
  build: {
    outDir: resolve(__dirname, '../backend/guide'),
    emptyOutDir: true,
    rollupOptions: { input: resolve(__dirname, 'guide.html') },
  },
});
