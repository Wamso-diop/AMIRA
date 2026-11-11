/**
 * Adresse du back-end Amira, fixée à la construction (pas un réglage utilisateur).
 * Le développeur du back-end la renseigne dans `.env` :  VITE_AMIRA_API_URL=https://api.exemple.cm
 * puis lance `npm run build`. Tant qu'elle est vide, l'extension utilise la simulation (⟦FF⟧).
 */
export const API_URL: string = (import.meta.env.VITE_AMIRA_API_URL ?? '').trim().replace(/\/+$/, '');
export const USE_MOCK = API_URL === '';
