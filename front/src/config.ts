/**
 * Adresse du back-end Amira, fixée à la construction (pas un réglage utilisateur).
 * Le développeur du back-end la renseigne dans `.env` :  VITE_AMIRA_API_URL=https://api.exemple.cm
 * puis lance `npm run build`. Tant qu'elle est vide, l'extension utilise la simulation (⟦FF⟧).
 */
export const API_URL: string = (import.meta.env.VITE_AMIRA_API_URL ?? '').trim().replace(/\/+$/, '');
/**
 * Mode autonome (`VITE_AMIRA_MODE=embedded`) : la mémoire validée et les voix sont dans l'extension, qui agit seule.
 * Avec une adresse de serveur en plus (build « hybride »), le serveur n'est consulté que pour ce que la mémoire ne connaît pas.
 */
export const EMBEDDED: boolean = import.meta.env.VITE_AMIRA_MODE === 'embedded';
export const USE_MOCK = !EMBEDDED && API_URL === '';
