# Spec : back-end Amira (API Flask)

Statut : **à relire par un humain avant toute ligne de code.**
Sources : brief back-end (2026-11-12), `backend/README.md` (§4), `front/docs/API.md`, `front/src/services/api.ts`.
Règles : [CONSTRAINTS.md](CONSTRAINTS.md). En cas de conflit, le contrat du front l'emporte, puis CONSTRAINTS.md, puis ce document.

## 1. Objectif

Une API Flask sans état, dans `backend/`, qui :
- traduit des textes **déjà masqués** par l'extension : `fr → ff`, `en → ff`, `ff → fr`, `ff → en` ;
- sert d'abord les traductions **validées par des locuteurs natifs** (mémoire), et le moteur local seulement en dehors des catégories sensibles ;
- renvoie l'audio enregistré par un natif (`/v1/tts`), sinon `204` ;
- reçoit les signalements (`/v1/feedback`) dans une file de relecture, et offre aux natifs des outils internes (`/v1/admin`).

Utilisateurs : l'extension Chrome (public), les locuteurs natifs (admin), plus tard un serveur de la banque qui masque avec les mêmes règles (`docs/MASQUAGE.md`).

Réussite : la pastille du front affiche « Prêt » (sans « démo »), une page de test est traduite, chaque marqueur revient intact, et aucune donnée réelle ni aucun texte n'atteint le moteur, la base ou les journaux sans avoir passé la garde.

## 2. Hypothèses (à corriger maintenant)

1. **Variété du fichier gold** : `gold_fulfulde.csv` n'a pas de colonne variété. Ses 103 entrées sont importées en `ngaoundere` (Adamaoua).
2. **Relecteur du fichier gold** : il a été écrit par un natif. L'import crée donc des entrées `validated`, avec `validated_by` = le nom passé en argument (`--by "<nom>"`, obligatoire) et une ligne d'audit.
3. **Un fichier gold donne quatre sens** : chaque ligne crée `fr→ff`, `en→ff`, `ff→fr` et `ff→en`. Les colonnes `*_variants` (séparées par `|` ou `;`) ajoutent des clés sources de plus vers la même traduction ; pour la cible, seule la colonne principale sert.
4. **`source: "auto"`** : le contrat l'accepte, l'extension ne l'envoie plus. Le serveur ne détecte pas la langue : chaque segment revient `uncertain` (P5), sans appeler le moteur.
5. **Segment refusé par la garde dans `/v1/tts` et `/v1/feedback`** : réponse `204`, rien n'est stocké ni journalisé, le compteur `unmasked_total` augmente. Pas d'erreur, pour ne pas renseigner un appelant sur ce que la garde attrape.
6. **Délai du moteur dépassé (6 s)** : les segments non traités reviennent `uncertain` ; ceux servis par la mémoire restent `validated`. Pas d'erreur `TIMEOUT` (le front perdrait tout le lot).
7. **Moteur** : `facebook/nllb-200-distilled-600M` (≈ 2,5 Go, CPU), code `fuv_Latn` pour `ff` (fulfulde du Nigeria, le plus proche de l'Adamaoua dans NLLB). Le moteur ignore la variété ; elle sert seulement à la clé de mémoire. Le modèle n'est **pas** encore téléchargé sur cette machine.
8. **Voix de synthèse** : aucune pour le fulfulde. `/v1/tts` renvoie l'enregistrement d'un natif ou `204`. `tts: true` dans les capacités (les enregistrements existent), `stt: false` (point d'accès présent, renvoie `BAD_REQUEST` tant que désactivé).
9. **Rotation du jeton admin** : `AMIRA_ADMIN_TOKENS` accepte plusieurs jetons séparés par des virgules ; on ajoute le nouveau, puis on retire l'ancien.
10. **Seuil `ff → fr/en`** : 0,7 au départ (contre 0,5 vers `ff`), réglable.

## 3. Pile technique

Python 3.12. `requirements.txt` figé (`==`) : Flask, gunicorn, python-dotenv, pytest ; `transformers` + `torch` (CPU) **importés uniquement dans `amira/engine.py`**. Tout le reste : `sqlite3`, `logging`, `hmac`, `json`, `re`, `unicodedata`, `ipaddress`, `concurrent.futures`, `csv`.

## 4. Commandes

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                                  # puis AMIRA_ADMIN_TOKENS
flask --app amira run --port 5000                     # développement (moteur factice si AMIRA_ENGINE=fake)
pytest -q -m "not slow"                               # après chaque modification (< 10 s)
pytest -q && pip-audit -r requirements.txt            # fin de tâche
pytest -q -m slow                                     # vrai modèle : mesure d'un lot de 40 (médiane, p95)
python tools/import_gold.py ~/Téléchargements/gold_fulfulde.csv --by "<nom du natif>"
gunicorn -w 1 --threads 4 -b 0.0.0.0:8000 --timeout 30 wsgi:app   # production : UN worker
docker compose up                                     # réseau internal: true
```

## 5. Arborescence

Celle de `backend/README.md` §4.1, plus `guard.py` et `engine.py`. Rien d'autre.

```
backend/
├── CONSTRAINTS.md  SPEC.md  README.md  LICENSES.md
├── requirements.txt  .env.example  wsgi.py  Dockerfile  docker-compose.yml
├── docs/openapi.yaml       contrat 3.1, écrit AVANT le code
├── docs/MASQUAGE.md        règles de masquage pour un appelant serveur
├── tools/import_gold.py    import du fichier gold
├── amira/
│   ├── __init__.py         create_app() : config, CORS, erreurs, journaux, limiteur, blueprints
│   ├── config.py           variables d'environnement uniquement
│   ├── errors.py           ApiError → {error:{code,message,retryAfterMs?}}
│   ├── cors.py
│   ├── markers.py          markers_ok, well_nested, speakable, normalize_key
│   ├── guard.py            garde de confidentialité
│   ├── engine.py           translate(textes, src, tgt) → [(texte, confiance)] ; seul fichier qui importe le modèle
│   ├── db.py               SQLite, SQL standard
│   ├── services/translator.py  voice.py  stt.py
│   └── routes/public.py  admin.py
└── tests/
```

## 6. Comportement

### 6.1 Chaîne d'un segment (`/v1/translate`)

1. **Requête** : `source`/`target` dans la config, sinon `UNSUPPORTED_LANGUAGE` ; `fr↔en` et `source == target` refusés. 1 à 40 segments ; chaque segment a `id` (texte) et `text` (texte, ≤ 1000 caractères), sinon `BAD_REQUEST` pour la requête entière. `variety` ignorée si `target != "ff"`.
2. **Garde** (`guard.check(text) -> bool`) : marqueurs `{N0}` `{B0}` `{/B0}` `{E0}` retirés, puis refus si le reste contient un chiffre (tout `\d` Unicode), une devise (`FCFA`, `XAF`, `CFA`, `francs?`, `€`, `$`), un e-mail ou un motif IBAN (`[A-Z]{2}\d{2}[A-Z0-9 ]{10,}`). Refusé → `{text: <reçu>, status: uncertain, confidence: 0, origin: "llm"}`, rien n'est transmis, stocké ni journalisé, `unmasked_total += 1`. Le lot continue.
3. **Clé de mémoire** = `normalize_key(text)` : NFC, minuscules, espaces simples, ponctuation finale retirée, **tous les marqueurs conservés** ; plus `source`, `target`, et `variety` si `target == "ff"`.
4. **Mémoire** : trouvée et `markers_ok(text, entrée)` → `validated`, `confidence: 1`, `origin: "memory"`. Marqueurs différents → entrée ignorée, `memory_bad_markers += 1`, alerte au journal (clé hachée, pas de texte).
5. **Catégorie sensible** (`security_warning`, `fees`) sans mémoire → `uncertain` avec le texte source, moteur **non appelé**, `unmatched(clé, texte masqué, demandes += 1)`.
6. **Moteur** (tous les segments restants en un seul appel, délai 6 s). Sortie acceptée si : `markers_ok`, aucun chiffre hors marqueurs, non vide, différente de la source (après `normalize_key`), confiance ≥ seuil du sens. Sinon une seconde tentative `strict=True` pour ces segments seulement, sinon `uncertain` + texte source. Acceptée → `machine`, `origin: "llm"`.
7. **Réponse** : mêmes `id`, même ordre, un segment par segment reçu ; `requestId` renvoyé tel quel ; `engineVersion` ; `latencyMs`.

`origin: "template"` n'est jamais produit (pas de gabarits pour l'instant ; le contrat l'autorise).

### 6.2 Autres points d'accès publics

| Point d'accès | Comportement |
|---|---|
| `GET /v1/health` | `{ok: true, version}` ; vivant, ne touche ni modèle ni base |
| `GET /v1/ready` (ajout) | `200 {ok: true}` si modèle et base chargés, sinon `503` `UNAVAILABLE` |
| `GET /v1/capabilities` | champs du contrat, depuis la config ; ajout : `directions: ["fr-ff", …]` |
| `POST /v1/tts` | `speakable(text)` → garde → enregistrement natif (`segmentKey`, `language`) avec `X-Amira-Voice: recorded`, sinon `missing_audio += 1` et `204` |
| `POST /v1/stt` | `BAD_REQUEST` tant que `AMIRA_STT_ENABLED=false` |
| `POST /v1/feedback` | 4 champs texte obligatoires ; garde sur chacun ; écrit dans `feedback` (`pending`) ; `204` |

### 6.3 Admin (`/v1/admin`, jamais appelé par l'extension)

Accès : `Authorization: Bearer <jeton>` comparé avec `hmac.compare_digest` à chaque jeton de `AMIRA_ADMIN_TOKENS`, **et** adresse cliente dans `AMIRA_ADMIN_NETWORKS` (par défaut `127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`). Sinon `401`. Toute écriture exige `validatedBy` (nom du natif) et ajoute une ligne `audit(qui, quand, action, clé)`.

Points d'accès du README §4.7, plus :
- `GET /v1/admin/unmatched` : textes sensibles sans mémoire, les plus demandés d'abord ;
- `GET|PUT /v1/admin/memory?format=csv|json` : export / import de la mémoire (mêmes contrôles que `PUT translations`) ;
- `POST /v1/admin/purge` : purge `feedback` (pending) et `unmatched` plus vieux que `AMIRA_RETENTION_DAYS` (90). La purge tourne aussi au démarrage.

`PUT /v1/admin/translations` : garde sur la source **et** la traduction, `markers_ok` obligatoire, sinon `400`.

### 6.4 Données (SQLite, SQL standard)

Tables du README §4.8 (`translations` sans ligne `machine` : on ne stocke pas les sorties du moteur), plus :
`unmatched(key, source, target, variety, text_masked, requests, last_at)`, `audit(id, at, who, action, key)`, `counters(name, value)` (`unmasked_total`, `memory_bad_markers`).
`translations.key` = clé normalisée ; `source_masked` garde le texte d'origine pour l'export.

### 6.5 Transverse

- **Journaux** : une ligne par requête : méthode, chemin, statut, durée, `requestId`, compteurs du lot (`n`, `memory`, `machine`, `uncertain`, `refused`). Jamais de texte ni de corps. Les exceptions sont journalisées par type et ligne, sans message.
- **CORS** : README §4.2 ; en production `AMIRA_ALLOWED_ORIGINS` est obligatoire (refus de démarrer sinon, hors `AMIRA_ENV=development`).
- **`AMIRA_API_KEYS`** (facultatif) : si défini, une requête sans origine d'extension autorisée doit porter `X-Amira-Key` valide, sinon `401`.
- **Limiteur** : seau à jetons par adresse en mémoire (un seul worker), `429` + `retryAfterMs`. `shortcut: en mémoire, à remplacer par les quotas de la passerelle de la banque.`
- **Limites** : `MAX_CONTENT_LENGTH` 5 Mo ; JSON > 256 Ko → `413 BAD_REQUEST`.
- **Moteur distant** : aucun. S'il en vient un : `AMIRA_REMOTE_ENGINE=1` + `AMIRA_REMOTE_HOSTS`, texte gardé uniquement.
- **Debug** : `debug` forcé à `False` sauf `AMIRA_ENV=development`.

## 7. Style de code

```python
def check(text: str) -> bool:
    """True si le texte peut quitter la garde : aucun chiffre, devise, e-mail ni IBAN hors marqueurs."""
    rest = MARKER_RE.sub(" ", text)
    return not (DIGIT_RE.search(rest) or CURRENCY_RE.search(rest) or EMAIL_RE.search(rest) or IBAN_RE.search(rest))
```

Fonctions courtes, modules au lieu de classes, pas de couche d'abstraction. Messages d'erreur en français, sans texte utilisateur. Aucun fulfulde dans le code ni dans les tests : les tests utilisent des textes neutres (`"Bonjour {N0}"`) et un moteur factice qui renvoie `"<<" + texte + ">>"`.

## 8. Tests

pytest, dans `backend/tests/`, écrits **avant** le code. Le moteur est injecté (`app.config["ENGINE"]`) : factice ou espion dans tous les tests sauf ceux marqués `slow`.

| Brief | Fichier | Contenu |
|---|---|---|
| a | `test_markers.py` | cas du front + `{B0}` mal imbriqué, doublon, marqueur absent |
| b | `test_guard.py` | 30 cas paramétrés ; espion : aucun refusé n'atteint moteur, base, journaux |
| c | `test_privacy.py` | canari dans journaux, base, exception, entrée moteur ; moteur qui lève |
| d | `test_offline.py` | `socket.socket.connect` bloqué ; translate, tts, feedback passent |
| e | `test_engine_checks.py` | marqueur perdu, chiffre inventé, vide, identique, confiance basse, délai → `uncertain` ; correct → `machine` |
| f | `test_sensitive.py` | sensible sans mémoire : espion jamais appelé, `unmatched` alimenté |
| g | `test_status.py`, `test_admin.py` | `validated` impossible sans mémoire ; feedback jamais `validated` ; 401 sans jeton / hors réseau |
| h | `test_contract.py` | chaque réponse validée contre `docs/openapi.yaml` ; erreurs ; CORS ; `X-Amira-Voice` exposé ; fr↔en ; variété ignorée ; limites ; 429 |
| i | `test_import_gold.py` | 103 entrées, `{V1}→{N0}`, lignes invalides refusées, rapport |
| — | `test_no_fulfulde.py` | aucune valeur `ff` du CSV dans `amira/` ni `tests/` |
| j | `test_perf.py` (`slow`) | lot de 40, vrai modèle, médiane et p95 ; mesure notée dans CONSTRAINTS.md |
| k | manuel | extension reconstruite, « Prêt », page traduite, avertissement lu ; noté dans le README |

## 9. Limites

- **Toujours** : garde avant toute écriture, tout appel au moteur, toute ligne de journal ; `markers_ok` avant toute réponse ; tests avant le code.
- **Demander d'abord** : nouvelle dépendance ; changement de schéma SQLite ; tout champ ajouté au contrat au-delà de `/v1/ready` et `capabilities.directions` ; changer de modèle.
- **Jamais** : `validated` sans natif ; texte dans les journaux ; fulfulde écrit à la main ; appel sortant pendant une requête ; modifier le contrat existant.

## 10. Terminé quand

- `pytest -q` passe (lents compris), `pip-audit` sans vulnérabilité.
- Mesure réelle du lot de 40 notée (cible p95 < 6 s ; sinon mémoire d'abord, puis CTranslate2).
- Bout en bout validé avec l'extension (pastille « Prêt »).
- README (≤ 10 lignes pour lancer, tester, brancher), `LICENSES.md`, `docs/MASQUAGE.md`, `docs/openapi.yaml` à jour.
- `/ponytail-audit` sans problème de priorité haute ; `/ponytail-debt` lisible.

## 11. Questions ouvertes

1. **Validation contre openapi.yaml sans nouvelle dépendance** : il faut lire du YAML et valider un schéma JSON. Deux options :
   - (a) **recommandée, la plus courte** : ajouter `PyYAML` et `jsonschema` en dépendances de test seulement (`requirements-dev.txt`) ;
   - (b) écrire `openapi.yaml` en YAML de style JSON (lisible par `json.load`) et un petit validateur maison dans `tests/` (≈ 30 lignes).
2. **Modèle** : il faut télécharger NLLB-600M une fois (≈ 2,5 Go, réseau requis à ce moment-là seulement). La machine n'a qu'environ 1 Go de RAM libre en ce moment : le test `slow` risque d'échouer ici. Où le lancer ?
3. **Jeux de données `FredMike23/english-FULFULDE-ADAMAOUA` et `french-FULFULDE-ADAMAOUA`** (présents dans le cache Hugging Face) : servent-ils à l'entraînement ou à la calibration ? Leur licence doit figurer dans `LICENSES.md`.
4. **Hypothèses 1 à 5** ci-dessus : à confirmer, en particulier le nom du natif à inscrire pour l'import gold.
