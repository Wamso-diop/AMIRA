# BRIEF BACKEND AMIRA, version 2

À placer dans `backend/BRIEF.md`. Premier message à donner à Claude Code :
« Lis backend/BRIEF.md en entier. Ne code rien avant d'avoir exécuté les étapes 0 à 3 de la section 3 et de m'avoir montré la spécification et le plan. »

---

## 1. Où on en est (à vérifier, ne rien supposer)

- Dépôt `AMIRA/` avec `front/` (terminé, testé) et `backend/` (à construire).
- **Le contrat est figé** : `front/docs/API.md` et `front/src/services/api.ts` font foi. Le document « Back-end Amira : API Flask » (arborescence `amira/`, routes `/v1/...`, format d'erreur, CORS) reste valable. Ce brief y ajoute la sécurité, les tests, le moteur réel et l'ordre de travail. Ne renomme, ne retire et ne change aucun champ.
- **Moteur** : NLLB-200-distilled-600M, affiné en deux étapes sur du fulfulde. Codes de langue `fra_Latn`, `eng_Latn`, `fuv_Latn` (le fulfulde du Nigeria sert de proxy à celui de l'Adamaoua). Il a été entraîné avec des marqueurs `{V1}`, `{V2}`. **Il n'a jamais vu `{N0}`, `{B0}`, `{/B0}`, `{E0}`.**
- **Qualité mesurée** : chrF++ 44,7 sur 29 entrées de test, donc indicatif. Le modèle confond parfois « frais » et « argent » et recopie parfois de l'anglais. Il n'est **pas fiable** : c'est le repli derrière la mémoire validée, jamais la source des avertissements de sécurité ni des frais.
- **Mémoire validée** : `data/gold_fulfulde.csv`, 103 entrées relues par un locuteur natif (colonnes `id, kind, section, page, fr, en, ff, fr_variants, en_variants, ff_variants, notes, observed, n_markers`, marqueurs au format `{V1}`). Le fichier va encore changer : l'import doit pouvoir être rejoué sans doublons.
- **Pas de réentraînement dans cette tâche.** Le dossier du modèle sera remplacé plus tard sans toucher au code.
- **Licence** : NLLB-200 est sous licence non commerciale. Acceptable pour le hackathon, pas pour une banque. À consigner dans `LICENSES.md`, avec la licence de chaque jeu de données d'entraînement.

## 2. Principes non négociables

- **P1** Aucune donnée réelle (montant, nom, numéro, e-mail, IBAN) n'atteint le moteur, la base, les journaux ni le réseau.
- **P2** `validated` n'existe que pour une entrée de la mémoire relue par un natif. Jamais pour une sortie du moteur.
- **P3** `categoryHint` = `security_warning` ou `fees` : mémoire validée uniquement. Pas de moteur, même avec une confiance élevée.
- **P4** Chaque marqueur revient intact, le même nombre de fois. Le moteur n'a pas le droit d'ajouter un chiffre.
- **P5** Dans le doute : `uncertain`, avec le texte source masqué tel que le contrat le prévoit (le front garde l'original).
- **P6** Le service fonctionne sans Internet. Aucun appel sortant pendant `translate`, `tts` et `feedback`.
- **P7** Aucun texte en fulfulde écrit à la main dans le code ou dans les tests. Les tests lisent leurs exemples dans le CSV gold ou dans des fixtures de données.

## 3. Méthode et skills

Pour chaque étape, dans cet ordre :

1. **Une fois, au début** : `/ponytail lite`, puis `/constraints` (contenu en section 6), puis `/spec` (depuis ce brief, que je relis), puis `/plan`.
2. **Pour chaque étape S0 à S11** : écrire le test d'abord avec `/test` (il doit échouer), puis `/build`, puis `/review` et `/ponytail-review`.
3. **À la fin** : `/code-simplify`, `/ponytail-audit`, `/ponytail-debt` (chaque raccourci porte un commentaire `shortcut:`), puis `/ship`.

Règles de travail :
- **Une étape à la fois.** À la fin de chaque étape : résumé de ce qui a changé, résultat des tests, risques restants. Puis **attendre mon « go »**.
- Un commit par étape (message court et clair). Aucun test échoué n'est ignoré ou désactivé.
- Ponytail en mode `lite` : bibliothèque standard d'abord (`sqlite3`, `logging`, `hmac`, `json`, `re`, `unicodedata`). Dépendances autorisées : Flask, python-dotenv, gunicorn, pytest, et `transformers`/`torch` uniquement dans `engine.py`. Pas d'ORM, pas de file de tâches, pas de micro-services. **Mais le code de sécurité (garde, marqueurs, statuts) ne se raccourcit jamais pour être plus court.**
- Les tests n'ont pas besoin du réseau. Les tests qui chargent le vrai modèle sont marqués `@pytest.mark.model` et peuvent être ignorés par défaut.

## 4. Pas à pas

### S0. Vérifier l'environnement (aucun code applicatif)
- Le dossier du modèle (`backend/models/nllb_ff`, variable `AMIRA_MODEL_DIR`) doit contenir : `config.json`, `generation_config.json`, `tokenizer.json`, `tokenizer_config.json` et **un seul fichier de poids nommé `model.safetensors`** (environ 2,4 Go).
- État actuel connu : le fichier de poids s'appelle `model-001.safetensors` et `gold_fulfulde.csv` se trouve dans le dossier du modèle. **Ne déplace et ne renomme rien sans me le dire** : propose les commandes et attends. Si le fichier de poids fait nettement moins de 2,4 Go, des parties manquent : arrête-toi.
- Écrire `tools/check_model.py` : charge le modèle, traduit 5 phrases françaises absentes du gold (`num_beams=4`), affiche texte, confiance et durée. Contrôle d'intégrité : « Votre solde est insuffisant. » avait donné `Ceede moɗon mari cikay.` dans Colab. Une différence se signale, elle ne se corrige pas.
- Mesurer RAM utilisée et latence CPU pour 1 puis 8 segments, et les noter dans `docs/PERF.md`.
- Critère de fin : le modèle se charge depuis le disque et répond ; mesures notées.

### S1. Contrat et squelette
- `docs/openapi.yaml` (3.1), écrit **d'après `api.ts` avant tout code**. Les tests de réponse sont validés contre ce fichier.
- `create_app()`, configuration par variables d'environnement (`.env.example`), erreurs au format `{"error":{"code","message","retryAfterMs"?}}`, CORS limité à `chrome-extension://` avec l'en-tête `X-Amira-Voice` exposé.
- Routes : `/v1/health` (vivant, immédiat), `/v1/ready` (503 tant que le modèle et la base ne sont pas chargés), `/v1/capabilities`.
- Tests : format des erreurs, CORS et préflight, 404 en JSON, 413, `ready` avant et après chargement.

### S2. Marqueurs (`markers.py`)
- `same_markers`, `well_nested`, `markers_ok` (spécification du document front).
- `canonicalize(masked)` : renumérote les `{N}` dans l'ordre d'apparition pour la clé de mémoire, et garde la table pour restaurer les numéros d'origine. **Vérifier dans `front/src/content/` comment les `{N}` sont numérotés** (par segment, ordre d'apparition ?).
- `model_view(masked)` : renomme **tous** les marqueurs distincts (`{N0}`, `{B0}`, `{/B0}`, `{E0}`) en `{V1}`, `{V2}`… pour le modèle, avec la table inverse. `from_model(text, table)` fait l'inverse.
- Tests : imbrication, doublons, renumérotation, aller-retour identique, marqueur ajouté ou perdu par le moteur détecté, accolades inconnues.

### S3. Garde de confidentialité (`guard.py`)
- Après retrait des marqueurs, refuser : tout chiffre, devise (FCFA, XAF, CFA, francs, €, $), adresse e-mail, code de type IBAN.
- Un segment refusé : réponse `uncertain` avec le texte tel que reçu. **Il n'est ni transmis au moteur, ni cherché en mémoire, ni stocké, ni journalisé.** Un compteur anonyme `unmasked_total` augmente. Le reste du lot continue.
- Tests : 30 cas ou plus (montants, téléphones camerounais, e-mails, IBAN, « 5 étapes »). Une chaîne « canari » refusée n'apparaît nulle part (moteur espion, base, journaux, exceptions).

### S4. Base et mémoire validée (`db.py`, `tools/import_gold.py`)
- SQLite via `sqlite3`, requêtes paramétrées uniquement. Tables : `translations`, `feedback`, `unmatched`, `recordings`, `missing_audio`, `audit`. SQL standard (portable vers PostgreSQL).
- `tools/import_gold.py`, **idempotent** : lit le CSV, convertit `{V1}` en `{N0}`, `{V2}` en `{N1}`…, indexe `fr`, `en` et leurs variantes pour les sens `fr>ff` et `en>ff`, et `ff` et ses variantes pour `ff>fr` et `ff>en`. Refuse toute ligne dont les marqueurs diffèrent entre source et traduction. Rapport : importées, refusées, conflits (même clé, traduction différente : la priorité va à `ui` et `message` sur `glossaire`). Ne modifie jamais le CSV.
- Tests : import des 103 lignes avec le nombre attendu de refus, deux imports successifs donnent la même base, conversion des marqueurs, sens inverse, conflit signalé.

### S5. Traduction par la mémoire seule (`translator.py`, sans moteur)
- Ordre pour chaque segment : forme (`id` texte, `text` ≤ 1000 caractères) → garde → mémoire (si trouvée et `markers_ok` : `validated`, `origin: "memory"`) → catégorie sensible sans mémoire : `uncertain` et ajout à `unmatched` → sinon `uncertain`.
- Un segment en sortie pour chaque segment en entrée, même `id`, même ordre.
- Sens : `fr↔en` refusé avec `UNSUPPORTED_LANGUAGE`. Variété ignorée si la cible n'est pas `ff`. `source: "auto"` accepté (détection minimale fr/en, sinon `UNSUPPORTED_LANGUAGE`).
- Tests : chaque règle ci-dessus, avec des exemples tirés du CSV.

### S6. Moteur (`engine.py`)
- NLLB local par `transformers`, import paresseux, CPU par défaut, `torch.inference_mode()`, **un seul chargement**, verrou autour de `generate`. Codes `fra_Latn`, `eng_Latn`, `fuv_Latn`, `forced_bos_token_id` sur la cible, `num_beams=4`, `max_new_tokens=96`, entrée tronquée à 128 jetons. Confiance = `exp(sequences_scores)` (probabilité moyenne par jeton, à calibrer).
- Entrée du modèle via `model_view`, sortie via `from_model`.
- Une sortie est acceptée seulement si : `markers_ok`, aucun chiffre ajouté, non vide, différente de la source, confiance ≥ `MIN_CONFIDENCE` (0,5 au départ, configurable). Une seconde tentative stricte, sinon `uncertain`. Statut `machine`, `origin: "llm"`.
- Sens `ff>fr` et `ff>en` : seuil plus haut (0,7), qualité non mesurée, jamais pour les catégories sensibles.
- Budget de 6 s par requête : si dépassé, les segments restants sont `uncertain`, pas d'erreur globale.
- Une interface minimale (`translate(textes, src, tgt) -> [(texte, confiance)]`) et un faux moteur pour les tests. Pas d'autre abstraction.
- Tests avec faux moteur : marqueur perdu, chiffre inventé, sortie vide, sortie identique, confiance basse, exception (le texte ne fuit pas dans le message d'erreur), délai dépassé. Un test `@pytest.mark.model` vérifie le chargement réel.

### S7. Statuts et catégories sensibles
- `security_warning` et `fees` sans mémoire : le moteur n'est jamais appelé (test avec moteur espion).
- `validated` impossible sans entrée de mémoire.
- Tests de bout en bout du traducteur avec mémoire + faux moteur, validés contre `openapi.yaml`.

### S8. Voix, feedback et administration
- `/v1/tts` : enregistrement natif → sinon `note_missing` puis `synthesize()` qui renvoie `None` (aucune synthèse fulfulde disponible) → `204`. En-tête `X-Amira-Voice: recorded` quand c'est un enregistrement.
- `segmentKey` : FNV-1a 32 bits identique à `front/src/content/engine.ts`. **Demande-moi 5 paires (texte masqué, clé) produites par le front** pour un test d'égalité.
- `/v1/feedback` : garde, puis file `pending`. **Ne crée jamais une entrée `validated`.**
- `/v1/admin/*` : jeton comparé avec `hmac.compare_digest`, journal d'audit (qui, quand, quoi). Liste des signalements, des textes non reconnus (`unmatched`) et des audios manquants ; `PUT` d'une traduction validée (refusée si `markers_ok` échoue) ; dépôt d'audio.
- Dépôt d'audio : nom de fichier dérivé de la clé après validation `^k[0-9a-f]{8}$` (pas de traversée de répertoire), types MIME audio autorisés seulement, taille maximale 5 Mo.
- Tests : 401 sans jeton, tentative de traversée, mauvais type MIME, trop gros, feedback jamais `validated`.

### S9. Sécurité transversale
- **Journaux** : méthode, chemin, statut, durée, `requestId`, compteurs. Jamais de texte, même masqué, ni de corps de requête. Les messages d'exception ne contiennent aucun texte utilisateur. Débogage désactivé hors développement.
- **Pas de réseau** : test qui interdit toute connexion sortante (`socket.connect` levant une erreur) pendant `translate`, `tts` et `feedback`.
- **Limites** : 40 segments, 1000 caractères par segment, 256 Ko par requête JSON, 5 Mo pour l'audio. Limiteur de débit en mémoire par IP avec `429` et `retryAfterMs`. En-têtes `X-Content-Type-Options: nosniff` et `Cache-Control: no-store` sur `translate`.
- **Dépendances** : versions figées, `pip-audit` exécuté, conteneur sans droits administrateur.
- **Rétention** : purge de `pending` et `unmatched` au-delà de 90 jours (commande `flask purge`).
- Tests : chaîne « canari » absente des journaux, de la base, des exceptions et de l'entrée du moteur.

### S10. Performance et robustesse
- Mesurer un lot de 40 segments mêlant mémoire et moteur (médiane et p95). Cible : moins de 6 s, car le front attend 8 s. Si c'est dépassé : la mémoire d'abord, puis un cache de sorties machine (clé canonique, texte masqué seulement), puis CTranslate2 **seulement si une mesure montre un gain**. Noter les résultats dans `docs/PERF.md`.
- Un seul worker gunicorn avec des threads (le modèle n'est chargé qu'une fois en RAM). Test de 4 requêtes simultanées. Échauffement avec une phrase au démarrage.

### S11. Livraison
- `Dockerfile` (utilisateur non root, modèle monté en lecture seule), `docker-compose.yml` avec réseau `internal: true` et volume pour `data/`.
- `README.md` (lancer, tester, brancher le front, en moins de 10 lignes), `LICENSES.md`, `docs/MASQUAGE.md` (règles de masquage à respecter par un appelant serveur), `docs/EXPLOITATION.md` (remplacer le modèle, recharger la mémoire, sauvegarder la base, purger).
- Test de bout en bout : extension reconstruite avec `VITE_AMIRA_API_URL`, pastille « Prêt » sans « démo », traduction d'une page de test, lecture d'un avertissement.
- Puis `/code-simplify`, `/ponytail-audit`, `/ponytail-debt`, `/ship`.

## 5. À ne pas faire
- Réentraîner ou convertir le modèle, ou écrire du fulfulde dans le code.
- Produire `validated` sans mémoire, ou envoyer un catégorie sensible au moteur.
- Journaliser ou stocker un texte non masqué, ou un texte quelconque dans les journaux.
- Changer le contrat du front, ou ajouter une dépendance qui n'est pas indispensable.

## 6. Contenu de `CONSTRAINTS.md`
```
1. Aucune donnée réelle ne sort du navigateur ; le serveur la refuse si elle arrive.
2. « validated » = relu par un natif, et rien d'autre.
3. Avertissements de sécurité et frais : mémoire uniquement.
4. Marqueurs intacts, même nombre, ou on déclare le doute.
5. Aucun texte dans les journaux, les exceptions ou les métriques.
6. Aucun appel sortant dans translate, tts, feedback.
7. Tout nouveau comportement est précédé d'un test qui échoue.
8. Réponses conformes à docs/openapi.yaml.
9. Une étape à la fois, validée par un humain.
10. Le moins de code possible, sauf pour le code de sécurité.
```

## 7. Terminé quand
- Tous les tests passent, `/ponytail-audit` n'a aucun problème de priorité haute, `/ship` donne « on livre ».
- Latence d'un lot de 40 mesurée et notée. Limites connues écrites : le serveur ne peut pas reconnaître un nom propre que le front n'a pas masqué ; la qualité du modèle n'est mesurée que sur 29 entrées.