# Spec : back-end Amira (API Flask)

Statut : **à relire par un humain avant toute ligne de code.**
Sources : le brief initial (version 2, non conservé dans le dépôt), `README.md` §4, `front/docs/API.md`, `front/src/services/api.ts`.
Règles : [CONSTRAINTS.md](CONSTRAINTS.md). En cas de conflit : le contrat du front, puis CONSTRAINTS.md, puis ce document.

## 1. Objectif

Une API Flask sans état, dans `backend/`, qui :
- traduit des textes **déjà masqués** par l'extension : `fr → ff`, `en → ff`, `ff → fr`, `ff → en` ;
- sert d'abord la **mémoire validée** par des natifs (`data/gold_fulfulde.csv`, puis l'admin), et le modèle NLLB affiné seulement comme repli, jamais pour `security_warning` ni `fees` ;
- renvoie l'audio d'un natif (`/v1/tts`), sinon `204` ;
- reçoit les signalements (`/v1/feedback`) dans une file `pending`, et offre aux natifs des outils internes (`/v1/admin`).

Réussite : la pastille du front affiche « Prêt » (sans « démo ») ; une page de test est traduite ; chaque marqueur revient intact ; aucune donnée réelle ni aucun texte n'atteint le moteur, la base ou les journaux sans avoir passé la garde.

## 2. Ce qui a été vérifié (S0, sans code)

| Point | Constat |
|---|---|
| Dossier du modèle | `backend/model_stage2/`, et non `backend/models/nllb_ff` comme le demande le brief |
| Poids | `model-001.safetensors`, 2 460 354 912 octets (≈ 2,46 Go) : taille attendue, pas de partie manquante apparente. À renommer en `model.safetensors` |
| Autres fichiers | `config.json` (M2M100, transformers 5.22.2), `generation_config.json` (`num_beams` 4, `forced_bos_token_id` 256059), `tokenizer.json`, `tokenizer_config.json` (NllbTokenizer) : présents |
| CSV gold | `model_stage2/gold_fulfulde.csv`, 103 lignes. Il diffère de `~/Téléchargements/gold_fulfulde.csv` (le premier octet de l'en-tête change, probablement une marque BOM) : c'est le plus récent qui fait foi |
| Git | **les poids ne sont pas ignorés par `.gitignore`** : un `git add backend/` les commiterait (2,4 Go) |
| Python | 3.12.3 ; Flask, torch et transformers ne sont pas installés |
| RAM | 15,8 Go au total, ≈ 1,9 Go disponibles en ce moment. Le modèle en float32 en demande environ 2,5 à 3 Go : il faut fermer des applications avant S0 |
| Numérotation `{N}` côté front | `front/src/content/mask.ts` : `{N0}`, `{N1}`… par segment, dans l'ordre d'apparition, chacun unique (renumérotés à travers les `{B}` par `maskAroundMarkers`) |

## 3. Hypothèses (à corriger maintenant)

1. **Variété du gold** : `ngaoundere` (le CSV n'a pas de colonne variété).
2. **Auteur des validations du gold** : `--validator natif-1` (obligatoire), inscrit dans `validated_by` et dans `audit`. *(Confirmé.)*
3. **Variantes** : `fr_variants`, `en_variants` et `ff_variants` sont des clés sources supplémentaires qui pointent vers la traduction principale. Séparateur `|` (à vérifier sur les 10 lignes concernées en S4).
4. **Garde dans `/v1/tts` et `/v1/feedback`** : un texte refusé reçoit `204`, rien n'est stocké, `unmasked_total` augmente.
5. **Délai de 6 s dépassé** : les segments restants reviennent `uncertain`, ceux servis par la mémoire restent `validated`.
6. **`source: "auto"`** : détection minimale par mots outils fr/en (une vingtaine de mots par langue, comptés sur l'ensemble du lot). Sinon `UNSUPPORTED_LANGUAGE`.
7. **Aucune voix de synthèse** : `tts: true` (enregistrements de natifs), `stt: false`.
8. **Rotation du jeton admin** : `AMIRA_ADMIN_TOKENS` accepte plusieurs jetons séparés par des virgules.

## 4. Pile technique

Python 3.12. `requirements.txt` figé (`==`) : Flask, gunicorn, python-dotenv, pytest ; `transformers` + `torch` (CPU) **importés uniquement dans `amira/engine.py`, et seulement au premier appel**. Le reste vient de la bibliothèque standard.

## 5. Commandes

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                                     # puis AMIRA_ADMIN_TOKENS
python tools/check_model.py                              # S0 : chargement, 5 phrases, RAM, latence
python -m tools.import_gold data/gold_fulfulde.csv --validator natif-1   # rejouable
flask --app amira run --port 5000                        # AMIRA_ENGINE=fake pour travailler sans modèle
flask --app amira purge                                  # rétention (90 jours)
pytest -q                                                # tout sauf le vrai modèle
pytest -q -m model                                       # vrai modèle (chargement, lot de 40)
pip-audit -r requirements.txt -r requirements-dev.txt
gunicorn -w 1 --threads 4 -b 0.0.0.0:8000 --timeout 30 wsgi:app
python demo.py                                          # démonstration locale, sans configuration
```

## 6. Arborescence

L'arborescence de `README.md` §4.1, plus `guard.py` et `engine.py`, et rien d'autre.

```
backend/
├── CONSTRAINTS.md SPEC.md README.md LICENSES.md
├── requirements.txt .env.example wsgi.py demo.py
├── languages/<code>/               une langue : language.json, gold.csv (mémoire validée), audio/, check_model.json
├── models/nllb_ff/                 AMIRA_MODEL_DIR (ignoré par git, monté en lecture seule)
├── docs/openapi.yaml PERF.md MASQUAGE.md EXPLOITATION.md
├── tools/check_model.py import_gold.py
├── amira/
│   ├── __init__.py config.py errors.py cors.py
│   ├── markers.py   same_markers, well_nested, markers_ok, canonicalize, model_view, from_model, speakable, segment_key
│   ├── guard.py     check(text) -> bool
│   ├── engine.py    translate(textes, src, tgt) -> [(texte, confiance)] ; FakeEngine pour les tests
│   ├── db.py        sqlite3, requêtes paramétrées, SQL standard
│   ├── services/translator.py voice.py stt.py
│   └── routes/public.py admin.py
└── tests/
```

## 7. Comportement

### 7.1 Marqueurs (`markers.py`)

- `markers_ok(src, out)` = même multiensemble de `{N}`, `{B}`, `{/B}`, `{E}` et `{B}` bien imbriqués dans `out`.
- `canonicalize(masked) -> (canon, table)` : renumérote les `{N}` dans l'ordre d'apparition (`{N0}`, `{N1}`…). `table` sert à restaurer les numéros d'origine dans la traduction de la mémoire. Pour une entrée du front c'est l'identité, mais un appelant serveur peut numéroter autrement.
- `model_view(masked) -> (vue, table)` : chaque marqueur distinct devient `{V1}`, `{V2}`… dans l'ordre d'apparition (le modèle n'a appris que ce format). `from_model(text, table)` fait l'inverse ; un `{Vk}` inconnu ou une accolade parasite fait échouer `markers_ok`.
- Les accolades qui ne sont pas des marqueurs sont du texte : elles doivent revenir telles quelles. Si elles ne reviennent pas, le segment est `uncertain`.

### 7.2 Garde (`guard.py`)

Texte normalisé (NFKC, caractères invisibles retirés), marqueurs du front retirés (index de 1 à 3 chiffres seulement : `{N699123456}` ne cache pas un numéro). Refusé s'il contient : un chiffre Unicode (catégories Nd, No, Nl, avant et après NFKC), un symbole monétaire (Sc : `€`, `$`, `£`, `₦`…), une devise (`FCFA`, `F CFA`, `CFA`, `XAF`, `XOF`, `franc(s)`) ou un e-mail. Un IBAN porte toujours des chiffres de contrôle : la règle des chiffres le refuse. Un segment refusé renvoie `{text: <reçu>, status: "uncertain", confidence: 0, origin: "llm"}`. Il n'est ni cherché en mémoire, ni transmis, ni stocké, ni journalisé. `unmasked_total += 1`, et le lot continue.

### 7.3 Chaîne d'un segment (`/v1/translate`)

1. **Requête** : `source` et `target` doivent faire partie des langues de la configuration, sinon `UNSUPPORTED_LANGUAGE`. `fr↔en` et `source == target` sont refusés. `auto` passe par la détection (hypothèse 6). La requête contient de 1 à 40 segments ; chacun a un `id` (texte) et un `text` (texte, ≤ 1000 caractères), sinon `BAD_REQUEST`. `variety` vaut `None` si `target != "ff"`.
2. **Garde** (§7.2).
3. **Clé** = `normalize(canon)` : NFC, minuscules, espaces simples, ponctuation finale retirée, marqueurs conservés. S'y ajoutent le sens et la variété.
4. **Mémoire** : si la clé est trouvée et que `markers_ok` passe après restauration des numéros, le segment est `validated`, `confidence: 1`, `origin: "memory"`. Si les marqueurs diffèrent, l'entrée est ignorée, `memory_bad_markers += 1`, et le journal reçoit une alerte avec la clé hachée.
5. **Catégorie sensible** (`security_warning`, `fees`) sans mémoire : `uncertain`, avec le texte source. Le moteur **n'est pas appelé** ; `unmatched` reçoit `+1` demande.
6. **Moteur** : tous les segments restants en un appel, à travers `model_view`/`from_model`. La sortie est acceptée si `markers_ok`, aucun chiffre hors marqueurs, non vide, différente de la source, et confiance ≥ seuil (0,5 vers `ff`, 0,7 depuis `ff`). Sinon, une seconde tentative stricte pour ces segments seulement, puis `uncertain`. Une sortie acceptée est `machine`, avec `origin: "llm"`. Le budget est de 6 s par requête.
7. **Réponse** : mêmes `id`, même ordre, un segment par segment reçu ; `requestId` renvoyé tel quel. En-têtes `X-Content-Type-Options: nosniff` et `Cache-Control: no-store`.

`origin: "template"` n'est jamais produit (le contrat l'autorise).

### 7.4 Moteur (`engine.py`)

Le chargement commence au premier `ready()` (`wsgi.py` l'appelle au démarrage ; les commandes `flask` ne chargent jamais le modèle). `transformers` est importé à ce moment-là, sur CPU, sous `torch.inference_mode()`. Le modèle est chargé une seule fois, et `generate` est protégé par un verrou. Paramètres : codes `fra_Latn`, `eng_Latn` et `fuv_Latn` (configurables), `forced_bos_token_id` sur la cible, `num_beams=4`, `max_new_tokens=96`, entrée tronquée à 128 jetons. Confiance = `exp(sequences_scores)`. La tentative stricte utilise `num_beams=8` et `no_repeat_ngram_size=3`. Une exception levée par le moteur est remplacée par `EngineError("échec du moteur")`, sans texte, et tous les segments concernés deviennent `uncertain`.

### 7.5 Autres points d'accès

| Point d'accès | Comportement |
|---|---|
| `GET /v1/health` | `{ok: true, version}`, immédiat |
| `GET /v1/ready` (ajout) | `200 {ok: true}` si le modèle et la base sont chargés, sinon `503 UNAVAILABLE`. Avec `AMIRA_ENGINE=memory`, la base suffit |
| `GET /v1/capabilities` | les champs du contrat, tirés de la configuration |
| `POST /v1/tts` | `speakable` → garde → enregistrement (`X-Amira-Voice: recorded`) ; sinon `note_missing` + `synthesize()` → `None` → `204` |
| `POST /v1/stt` | `BAD_REQUEST` tant qu'il est désactivé |
| `POST /v1/feedback` | `segmentId` au format `^[A-Za-z0-9_-]{1,64}$` (un identifiant, hors garde) ; garde sur `originalMasked`, `shown`, `suggestion` (≤ 1000 caractères) ; écriture `pending`, `204` |

### 7.6 Admin (`/v1/admin`, jamais appelé par l'extension)

Accès : `Authorization: Bearer <jeton>`, comparé avec `hmac.compare_digest` à chaque jeton de `AMIRA_ADMIN_TOKENS`, **et** adresse cliente dans `AMIRA_ADMIN_NETWORKS` (réseaux privés par défaut). Sinon `401`. Toute écriture exige `validatedBy` et ajoute une ligne `audit(at, who, action, key)`.

Points d'accès : ceux de `README.md` §4.7 (sauf `GET /translations?status=machine` : les sorties du moteur ne sont jamais stockées), plus `GET /unmatched`. Mémoire admin (décision du 2026-11-12) : `PUT /translations` crée une entrée `ref = 'admin'` ; **l'import du gold ne touche jamais une entrée admin** et signale chaque conflit (même clé, texte différent) sans trancher ; `flask export-admin <fichier.csv>` écrit les entrées admin au format du CSV gold (`{N0}` → `{V1}`, `{B}`/`{E}` inchangés), réimportable tel quel. L'extension n'appelle jamais l'admin : pas d'en-têtes CORS sur `/v1/admin`. `PUT /translations` passe par la garde et `markers_ok`, sinon `400`. Pour le dépôt d'audio, la clé doit correspondre à `^k[0-9a-f]{8}$`, le type MIME doit être audio (`mpeg`, `ogg`, `webm`, `wav`, `mp4`) et la taille ≤ 5 Mo. Le chemin est construit par le serveur à partir de la clé.

### 7.7 Données (SQLite)

- `translations` : `key`, `source`, `target`, `variety`, `source_masked`, `text`, `kind`, `validated_by`, `updated_at`. Clé primaire : `(source, target, variety, key)`. Les sorties du moteur n'y sont jamais écrites.
- Autres tables : `feedback`, `recordings`, `missing_audio` (selon le README), `unmatched(key, source, target, variety, text_masked, requests, last_at)`, `audit`, `counters(name, value)`.
- `variety` vaut `''` (et non `NULL`) quand la cible n'est pas `ff`, pour que la clé primaire fonctionne de la même façon dans SQLite et PostgreSQL.

### 7.8 Import du gold (`tools/import_gold.py`)

Le script est idempotent (UPSERT sur la clé) et ne modifie jamais le CSV. Il convertit `{Vk}` en `{N(k-1)}`, puis indexe :
- `fr` + `fr_variants` → `ff` (sens `fr>ff`) ;
- `en` + `en_variants` → `ff` (sens `en>ff`) ;
- `ff` + `ff_variants` → `fr` et `en` (sens `ff>fr` et `ff>en`).

Une ligne dont les marqueurs diffèrent entre la source et la traduction est refusée. En cas de conflit (même clé, traductions différentes), `ui` et `message` passent devant `glossaire`, et le conflit est signalé. Le rapport donne le nombre d'entrées importées, de lignes refusées et de conflits.

### 7.9 Transverse

- **Journaux** : une ligne par requête : méthode, chemin, statut, durée, `requestId`, et les compteurs `n`, `memory`, `machine`, `uncertain`, `refused`. Ni texte ni corps de requête. Une exception est journalisée par son type et son emplacement, sans son message.
- **CORS** : seulement `chrome-extension://`. `AMIRA_ALLOWED_ORIGINS` est obligatoire hors développement : sans lui, le service refuse de démarrer. `X-Amira-Voice` est exposé.
- **`AMIRA_API_KEYS`** (facultatif) : une requête sans origine d'extension autorisée doit porter un `X-Amira-Key` valide.
- **Limites** : 5 Mo par corps ; JSON > 256 Ko → `413` (`request.max_content_length`, qui couvre aussi un corps sans `Content-Length`). Limiteur : 600 requêtes par minute et par adresse par défaut (`AMIRA_RATE_LIMIT_PER_MIN`), sauf `/health` et `/ready`. En-têtes `nosniff` et `no-store` sur toutes les réponses. Le limiteur est un seau à jetons par IP, en mémoire, avec `429` et `retryAfterMs` (`shortcut:` en mémoire, à remplacer par les quotas de la passerelle de la banque).
- **Rétention** : `flask purge` et purge au démarrage pour `feedback` (`pending`) et `unmatched` au-delà de `AMIRA_RETENTION_DAYS` (90).
- **Débogage** : forcé à `False` sauf avec `AMIRA_ENV=development`.
- **Proxy** : `AMIRA_TRUSTED_PROXIES=n` (0 par défaut) active `ProxyFix(x_for=n)` ; sinon `X-Forwarded-For` est ignoré. Le limiteur et les réseaux admin (validés au démarrage) utilisent l'adresse réelle.
- **Troncature** : confiance mise à 0 si l'entrée dépasse 128 jetons ou si la sortie atteint 96 jetons sans `</s>`.

## 8. Style de code

```python
def check(text: str) -> bool:
    """True si le texte peut quitter la garde : ni chiffre, ni devise, ni e-mail, ni IBAN hors marqueurs."""
    rest = MARKER_RE.sub(" ", text)
    return not (DIGIT_RE.search(rest) or CURRENCY_RE.search(rest) or EMAIL_RE.search(rest) or IBAN_RE.search(rest))
```

Fonctions courtes, des modules plutôt que des classes, pas de couche d'abstraction. Messages d'erreur en français, sans texte utilisateur. Les tests prennent leurs exemples fulfulde dans le CSV (P7). Le faux moteur renvoie le texte source entouré de `<<…>>`, ou une sortie dégradée choisie par le test.

## 9. Tests

Les tests utilisent pytest, sont écrits **avant** le code et vivent dans `backend/tests/`. Le moteur est injecté par `create_app(engine=…)`. Les tests marqués `@pytest.mark.model` sont ignorés par défaut (`addopts = -m "not model"`).

| Étape | Fichier | Contenu |
|---|---|---|
| S1 | `test_app.py` | format des erreurs, 404 JSON, 413, CORS et préflight, `ready` avant et après chargement |
| S2 | `test_markers.py` | imbrication, doublons, renumérotation, aller-retour `model_view`, marqueur ajouté ou perdu, accolades inconnues |
| S3 | `test_guard.py` | 30 cas ou plus ; canari absent du moteur espion, de la base, des journaux et des exceptions |
| S4 | `test_import_gold.py` | 103 lignes, refus attendus, double import identique, `{V1}→{N0}`, sens inverse, conflit |
| S5 | `test_translate_memory.py` | forme, garde, mémoire, sensible → `unmatched`, ordre et `id`, fr↔en, variété, `auto` |
| S6 | `test_engine.py` | faux moteur : marqueur perdu, chiffre inventé, vide, identique, confiance basse, exception sans texte, délai ; `model` : chargement réel |
| S7 | `test_status.py` | espion jamais appelé pour les sensibles ; `validated` impossible sans mémoire ; réponses validées contre `openapi.yaml` |
| S8 | `test_voice.py`, `test_admin.py`, `test_feedback.py` | 5 paires `segmentKey` du front, 401, traversée, MIME, taille, feedback jamais `validated` |
| S9 | `test_privacy.py`, `test_offline.py`, `test_limits.py` | canari partout ; `socket.connect` interdit ; 40, 1000, 256 Ko, 429, en-têtes |
| S10 | `test_perf.py` (`model`) | lot de 40 (médiane, p95), 4 requêtes simultanées |
| — | `test_no_fulfulde.py` | aucune valeur `ff` du CSV dans `amira/` ni dans `tests/*.py` |

## 10. Limites

- **Toujours** : la garde passe avant toute écriture, tout appel au moteur et toute ligne de journal ; `markers_ok` passe avant toute réponse ; le test est écrit avant le code ; un commit par étape, puis on attend le « go ».
- **Demander d'abord** : déplacer ou renommer le modèle ou le CSV ; ajouter une dépendance ; ajouter un champ au contrat au-delà de `/v1/ready`.
- **Jamais** : réentraîner ou convertir le modèle ; `validated` sans mémoire ; un texte dans les journaux ; du fulfulde dans le code ; un appel sortant pendant une requête ; modifier le contrat existant.

## 11. Terminé quand

- `pytest -q` et `pytest -q -m model` passent, et `pip-audit` est propre.
- Le lot de 40 est mesuré et noté dans `docs/PERF.md` (cible p95 < 6 s).
- Le parcours de bout en bout avec l'extension fonctionne (pastille « Prêt »).
- README (≤ 10 lignes), `LICENSES.md`, `docs/MASQUAGE.md`, `docs/EXPLOITATION.md` et `docs/openapi.yaml` sont à jour. Les limites connues sont écrites : un nom propre non masqué par le front, et une qualité mesurée sur 29 entrées seulement.
- `/ponytail-audit` ne signale aucun problème de priorité haute, et `/ship` donne « on livre ».

## 12. Questions ouvertes

1. ~~Validation contre `openapi.yaml`~~ **Tranché** : PyYAML et jsonschema dans `requirements-dev.txt` seulement (versions figées, `pip-audit`, hors production). `openapi.yaml` est écrit en vrai YAML. L'exception est notée dans `docs/EXPLOITATION.md`.
2. ~~Licences~~ **Tranché** : la liste est donnée par l'humain (voir `LICENSES.md`, S11).
3. **Paires `segmentKey`** (S8) : il me faudra 5 paires (texte masqué, clé) produites par le front.
