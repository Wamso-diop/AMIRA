# Contrat front ↔ back-end Amira

Ce document décrit ce que l'extension envoie et attend. Le back-end (traduction, voix, fiabilité) est
développé à part. Son adresse est fixée à la construction, pas par l'utilisateur :
`VITE_AMIRA_API_URL=https://api.exemple.cm` dans `.env`, puis `npm run build` (l'origine est ajoutée aux
`host_permissions` du manifeste). Adresse vide = simulation.

La langue source est détectée par l'extension (`source` = `"fr"`, `"en"` ou `"ff"`). Sens possibles :
`fr → ff`, `en → ff`, `ff → fr`, `ff → en`. Jamais `fr ↔ en`.

- Interfaces TypeScript : [`src/services/api.ts`](../src/services/api.ts) (client HTTP compris)
- Simulation : [`src/services/mock.ts`](../src/services/mock.ts) (mode démonstration)

## Principes

1. **Aucun secret dans l'extension.** Pas de clé d'API. Si une authentification est nécessaire, elle se fait côté serveur (par exemple derrière une passerelle).
2. **Textes masqués.** Avant tout envoi, l'extension remplace localement montants, devises, nombres, téléphones,
   e-mails, dates, références et noms propres par des marqueurs `{N0}`, `{N1}`… Les valeurs réelles ne quittent jamais le navigateur.
3. **Repères de balises.** Une phrase découpée en balises HTML est envoyée en un seul segment, avec des repères :
   `{B0}…{/B0}` pour une balise interne (gras, lien…), `{E0}` pour un élément atomique (champ, image, saut de ligne).
4. **Le serveur doit renvoyer exactement le même ensemble de marqueurs** (l'ordre peut changer, l'imbrication `{B}` doit rester valide).
   Sinon l'extension garde le texte original et affiche ⚠. Il n'y a jamais de remplacement partiel.
5. **CORS** : le serveur doit répondre aux origines `chrome-extension://<id>`. Requêtes envoyées sans cookies (`credentials: "omit"`).
6. **Délai** : 8 s par requête côté client.

## États côté extension

| Situation | État affiché |
|---|---|
| `VITE_AMIRA_API_URL` vide | simulation, « Prêt · démo » |
| Réseau injoignable ou délai dépassé | « Hors ligne » |
| `/v1/health` ou `/v1/capabilities` en erreur | « Erreur » (code dans le Journal) |
| Tout répond | « Prêt » ; « En cours » pendant les traductions |

## Points d'accès

### `GET /v1/health`
```json
{ "ok": true, "version": "1.0.0" }
```

### `GET /v1/capabilities`
```json
{ "translate": true, "tts": true, "stt": false, "languages": ["fr", "en", "ff"], "varietes": ["ngaoundere", "garoua", "maroua"] }
```
`tts` et `stt` activent ou désactivent la lecture à voix haute et la dictée dans l'onglet Voix.

### `POST /v1/translate`
Requête :
```json
{
  "requestId": "9f1c2a7b3d4e5f60",
  "source": "fr",
  "target": "ff",
  "variety": "ngaoundere",
  "segments": [
    { "id": "s12", "text": "Votre solde est de {B0}{N0}{/B0} au {N1}.", "categoryHint": "label", "placeholders": ["{N0}", "{N1}", "{B0}", "{/B0}"] }
  ]
}
```
- `source` : `"fr" | "en" | "auto" | "ff"` — `target` : `"ff" | "fr" | "en"` — `variety` : `"ngaoundere" | "garoua" | "maroua" | null`. Le panneau ne propose plus de choix : l'extension envoie toujours `"ngaoundere"`, même quand la cible est `fr` ou `en` (le serveur l'ignore alors).
- `categoryHint` (indice, le serveur décide) : `"label" | "instruction" | "fees" | "security_warning" | "error"`.
- `placeholders` : tous les marqueurs présents dans `text` (valeurs masquées et repères de balises).
- Lots de 40 segments au plus, 2 requêtes simultanées au plus par onglet.

Réponse :
```json
{
  "requestId": "9f1c2a7b3d4e5f60",
  "engineVersion": "amira-mt-0.3",
  "latencyMs": 412,
  "segments": [
    { "id": "s12", "text": "… {B0}{N0}{/B0} … {N1}.", "status": "validated", "confidence": 0.98, "origin": "memory" }
  ]
}
```
- `status` : `"validated"` (relue par un locuteur natif), `"machine"` (automatique), `"uncertain"` (doute).
- `confidence` : 0 à 1. `origin` : `"memory" | "template" | "llm"`.

Règles d'affichage appliquées par l'extension :
| Condition | Résultat |
|---|---|
| marqueurs différents ou balises mal imbriquées | original gardé, ⚠ |
| `status: "uncertain"` | original gardé, ⚠ |
| `categoryHint` = `security_warning` et `status` ≠ `validated` | original gardé, ⚠ |
| Mode prudence actif, `status` ≠ `validated` et `confidence` < seuil (70 % par défaut) | original gardé, ⚠ |
| segment absent de la réponse | original gardé, ⚠ |
| sinon | traduction affichée |

Les segments `validated` et `machine` sont mis en cache localement (texte masqué uniquement, 1 000 entrées max).

### `POST /v1/tts`
Requête : `{ "text": "texte masqué ou non sensible", "language": "ff", "speed": 1, "segmentKey": "k3f9a01c2" }`
- `segmentKey` (facultatif) : clé stable du segment lu, la même à chaque visite de la page. C'est
  l'empreinte FNV-1a 32 bits du texte source **masqué** (repères `{B0}`/`{E0}` retirés, espaces
  normalisés, minuscules), préfixée par `k`. La segmentation est celle de la traduction : un
  locuteur natif enregistre l'audio d'un segment une fois, le serveur le range sous cette clé et le
  renvoie avec `X-Amira-Voice: recorded`. Calcul : `segmentKey()` dans `src/content/engine.ts`.
Réponse : audio binaire (`Content-Type: audio/mpeg`, `audio/ogg`…), ou `204 No Content` quand le serveur n'a pas d'audio (le panneau utilise alors la synthèse du navigateur). En-tête facultatif
`X-Amira-Voice: recorded | synthetic` → étiquette « Voix enregistrée » / « Voix de synthèse ».
Les marqueurs `{N0}` sont retirés avant l'envoi : montants et noms ne sont pas lus.

### `POST /v1/stt?language=ff` (proposition)
Corps : audio brut (`Content-Type` = type du `MediaRecorder`, ex. `audio/webm`). Réponse : `{ "text": "…" }`.
N'est appelé que si `/v1/capabilities` annonce `"stt": true`.

### `POST /v1/feedback`
```json
{ "segmentId": "s12", "originalMasked": "Votre solde est de {N0} au {N1}.", "shown": "… {N0} … {N1}.", "suggestion": "correction proposée" }
```
Boucle de validation par un locuteur natif. La suggestion est elle aussi masquée avant envoi. Réponse : `204` ou `{ "ok": true }`.

## Erreurs
Corps d'erreur attendu (tout code HTTP ≥ 400) :
```json
{ "error": { "code": "RATE_LIMITED", "message": "Trop de requêtes", "retryAfterMs": 3000 } }
```
| `code` | Comportement de l'extension |
|---|---|
| `RATE_LIMITED` (429) | nouvelle tentative automatique après `retryAfterMs` (une fois), puis erreur |
| `TIMEOUT` | une nouvelle tentative automatique, puis erreur |
| `UNAVAILABLE` (5xx) | segments en erreur, original gardé, bouton « Réessayer » |
| `BAD_REQUEST` | segments en erreur |
| `UNSUPPORTED_LANGUAGE` | segments en erreur, message dédié |

Codes ajoutés par le client (non renvoyés par le serveur) : `NOT_CONFIGURED`, `NETWORK`, `BAD_RESPONSE`.
Chaque erreur est inscrite au Journal avec `httpStatus`, `durationMs`, `requestId` et l'hôte, **jamais** le texte.

## Mode démonstration (mock)
- Ne produit **jamais** de faux fulfulde : renvoie le texte source préfixé de `⟦FF⟧`.
- Statuts déterministes (hachage du texte) : environ 60 % `machine`, 20 % `validated`, 20 % `uncertain` ; les avertissements de sécurité sont `validated`.
- Scénarios (tests automatisés, réglage interne `mockScenario`) : normal, erreur 500, 429, délai dépassé, réseau coupé, marqueurs abîmés.
- `tts` renvoie « pas d'audio » : le panneau utilise la synthèse vocale du navigateur, étiquetée « Voix de synthèse ».
