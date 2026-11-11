// Polices locales : uniquement latin + latin-ext (contient ɓ Ɓ ɗ Ɗ ƴ Ƴ ŋ Ŋ ɲ Ɲ).
import '@fontsource/inter-tight/latin-500.css';
import '@fontsource/inter-tight/latin-ext-500.css';
import '@fontsource/inter-tight/latin-800.css';
import '@fontsource/inter-tight/latin-ext-800.css';
import '@fontsource/inter-tight/latin-900.css';
import '@fontsource/inter-tight/latin-ext-900.css';
import '@fontsource/noto-sans/latin-400.css';
import '@fontsource/noto-sans/latin-ext-400.css';
import '@fontsource/noto-sans/latin-600.css';
import '@fontsource/noto-sans/latin-ext-600.css';
import '@fontsource/noto-sans/latin-700.css';
import '@fontsource/noto-sans/latin-ext-700.css';
import './styles.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

async function boot() {
  // Hors extension (npm run dev) : faux chrome.* pour voir le panneau dans un onglet normal.
  const inExtension = typeof chrome !== 'undefined' && !!chrome.runtime?.id && !!chrome.storage?.local;
  if (!inExtension && import.meta.env.DEV) (await import('../dev/fakeChrome')).installFakeChrome();
  const { App } = await import('./App');
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
void boot();
