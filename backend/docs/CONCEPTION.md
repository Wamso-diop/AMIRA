# Back-end Amira : API Flask (document de conception initial)

> Document écrit avant l'implémentation, gardé pour l'historique. Les extraits de code ci-dessous ne sont plus à jour : le code fait foi (`amira/`), avec [SPEC.md](../SPEC.md) et [openapi.yaml](openapi.yaml).

Ce document s'adresse au développeur du back-end. Il explique :

1. [ce qui a été fait côté front](#1-ce-qui-est-fait-côté-front) et ce que le front attend du serveur ;
2. [ce qui a changé](#2-ce-qui-a-changé-depuis-le-premier-cahier-des-charges-du-serveur) depuis le premier cahier des charges du serveur ;
3. [comment construire l'application Flask](#4-construire-lapplication-flask) qui expose tous les points d'accès ;
4. [comment la brancher au front et la vérifier](#6-brancher-le-front-sur-flask).

Le contrat exact, champ par champ, reste [front/docs/API.md](../front/docs/API.md). En cas de doute, c'est le code du client qui fait foi : [front/src/services/api.ts](../front/src/services/api.ts).

---

## 1. Ce qui est fait côté front

Le dossier `front/` contient une **extension Chrome (Manifest V3)** terminée et testée. Elle fonctionne aujourd'hui avec une **simulation** intégrée (le texte revient préfixé de `⟦FF⟧`, la pastille affiche « Prêt · démo »). Dès qu'une adresse de serveur est fournie à la construction, elle appelle l'application Flask **directement**, sans passerelle ni intermédiaire.

| Partie | Ce qu'elle fait | Conséquence pour le serveur |
|---|---|---|
| **Découpage** | La page est découpée en passages (une phrase, un libellé, un bouton). Une phrase découpée en balises `<b>`, `<a>`… reste **un seul** passage, avec des repères `{B0}…{/B0}` et `{E0}`. | Le serveur reçoit des phrases entières, avec des repères à conserver. |
| **Masquage local** | Avant tout envoi : montants, devises, nombres, téléphones, e-mails, dates, références, IBAN et noms propres deviennent `{N0}`, `{N1}`… | **Le serveur ne voit jamais un montant, un nom ou un numéro.** Il doit rendre tous les marqueurs intacts. |
| **Détection de langue** | Langue de la page détectée seule : `fr`, `en` ou `ff`. | `source` vaut `fr`, `en` ou `ff`. |
| **Vérification au retour** | Marqueurs différents, balises mal imbriquées, statut `uncertain`, avertissement de sécurité non validé, confiance trop basse en mode prudence : **l'original reste affiché** avec ⚠. | Un statut honnête (`validated` / `machine` / `uncertain`) vaut mieux qu'une traduction forcée. |
| **Cache local** | Les segments `validated` et `machine` sont gardés dans le navigateur (1 000 au plus, textes masqués). | Le serveur n'est pas rappelé pour un texte déjà traduit. |
| **Contenu inédit** | Un texte qui apparaît après le chargement (erreur, alerte, nouvelle étape) est envoyé seul, aussitôt. | Beaucoup de petites requêtes, de 1 à 40 segments. |
| **Voix** | Onglet Voix : lire la page, les messages importants, ou des **passages choisis en les touchant sur la page**. Une requête `/v1/tts` par passage, avec une clé stable `segmentKey`. | Le serveur renvoie l'enregistrement d'un natif s'il existe, sinon une voix de synthèse, sinon `204`. |
| **Signalements** | Onglet Journal : l'utilisateur signale une traduction et propose une correction, elle aussi masquée. | `/v1/feedback` alimente la validation par les natifs. |
| **Dictée** | Prévue dans l'onglet Voix, **cachée tant que `stt` vaut `false`**. | Facultatif. |
| **État du serveur** | Pastille Prêt / En cours / Hors ligne / Erreur, à partir de `/v1/health` et `/v1/capabilities`. | Ces deux points d'accès doivent être rapides et toujours disponibles. |

Ce que le front **ne fait pas** et attend du serveur : la traduction elle-même, la voix en fulfulde, la mémoire des traductions validées et le circuit de validation par des locuteurs natifs.

---

## 2. Ce qui a changé depuis le premier cahier des charges du serveur

Le premier cahier des charges parlait d'« un serveur » dont l'adresse se réglait dans le panneau. Voici ce qui est différent aujourd'hui.

| # | Avant | Maintenant | Ce que ça change pour toi |
|---|---|---|---|
| 1 | « Un serveur », technologie non précisée | **Une application Flask**, dans `backend/` du même dépôt git que le front | Tout est décrit ci-dessous. Le `.gitignore` racine couvre déjà Flask (`.venv/`, `instance/`, `media/`, `.env`…). |
| 2 | Adresse du serveur saisie dans le panneau, avec une section « Avancé » (URL, mode démo, scénarios, vider le cache) | Adresse **fixée à la construction** : `VITE_AMIRA_API_URL` dans `front/.env`. Section « Avancé » supprimée. | Pour changer de serveur, il faut reconstruire l'extension. La construction ajoute l'origine du serveur aux autorisations Chrome. |
| 3 | Choix manuel de la langue source et cible | Langue **détectée automatiquement**. Sens possibles : `fr → ff`, `en → ff`, **`ff → fr`**, **`ff → en`**. Jamais `fr ↔ en`. | Le serveur doit aussi savoir traduire **depuis** le fulfulde. Il refuse `fr ↔ en` avec `UNSUPPORTED_LANGUAGE`. `source: "auto"` reste accepté par le contrat, mais l'extension ne l'envoie plus. |
| 4 | Choix de la variété (Ngaoundéré, Garoua, Maroua) dans le panneau | **Choix retiré du panneau.** L'extension envoie toujours `variety: "ngaoundere"`, **même quand la cible est `fr` ou `en`**. | Utiliser la variété seulement si `target == "ff"`, l'ignorer sinon. `/v1/capabilities` peut toujours lister les variétés. |
| 5 | `/v1/tts` : `{ text, language, speed }` | Nouveau champ facultatif **`segmentKey`**. Une requête par passage. Réponse **`204`** acceptée. | Ranger les enregistrements des natifs par `segmentKey` et les renvoyer avec `X-Amira-Voice: recorded`. Répondre `204` quand il n'y a pas d'audio. |
| 6 | Lecture de toute la page seulement | Lecture de la page, des messages importants ou d'une **sélection de passages** | Les clés `segmentKey` demandées sans enregistrement disent aux natifs **quoi enregistrer en priorité** (voir §4.6). |
| 7 | Champ « Noms à toujours masquer » | Retiré du panneau | Aucun impact : le masquage reste local et automatique. |

Le reste du contrat n'a pas changé : `/v1/health`, `/v1/capabilities`, `/v1/translate`, `/v1/stt`, `/v1/feedback`, le format des erreurs, le délai de 8 s et les lots de 40 segments.

---

## 3. Vue d'ensemble

```
Extension Chrome (front/)                         Application Flask (backend/)
───────────────────────────                       ─────────────────────────────────────────
service worker ── GET  /v1/health ─────────────►  état
               ── GET  /v1/capabilities ───────►  ce qui est disponible (traduction, voix, dictée)
               ── POST /v1/translate ──────────►  mémoire validée → moteur → contrôle des marqueurs
               ── POST /v1/tts ────────────────►  enregistrement natif → synthèse → 204
               ── POST /v1/stt?language=ff ────►  dictée (facultatif)
               ── POST /v1/feedback ───────────►  file de relecture pour les natifs

Outils internes des locuteurs natifs (jamais appelés par l'extension, protégés par jeton)
               ── /v1/admin/... ───────────────►  relire, valider, enregistrer l'audio
```

**Règle d'or du serveur : ne jamais rendre un marqueur en moins, en plus ou en double.** Le front vérifie de toute façon, mais chaque marqueur abîmé fait perdre une traduction à l'utilisateur.

---

## 4. Construire l'application Flask

### 4.1 Arborescence proposée

```
backend/
├── README.md               ce document
├── requirements.txt
├── .env.example            variables à copier dans .env (jamais commité)
├── wsgi.py                 point d'entrée pour gunicorn
├── amira/
│   ├── __init__.py         create_app() : configuration, CORS, erreurs, blueprints
│   ├── config.py           lecture des variables d'environnement
│   ├── errors.py           ApiError + format d'erreur attendu par le front
│   ├── cors.py             en-têtes pour chrome-extension://
│   ├── markers.py          contrôle des marqueurs {N0} {B0} {/B0} {E0}
│   ├── db.py               SQLite (instance/amira.sqlite3)
│   ├── services/
│   │   ├── translator.py   mémoire validée → moteur de traduction
│   │   ├── voice.py        enregistrements natifs → synthèse
│   │   └── stt.py          dictée (facultatif)
│   └── routes/
│       ├── public.py       /v1/health, capabilities, translate, tts, stt, feedback
│       └── admin.py        /v1/admin/... (locuteurs natifs)
├── instance/               base SQLite (ignorée par git)
├── media/recordings/       audio des natifs (ignoré par git)
└── tests/                  pytest
```

`requirements.txt` minimal :

```
Flask>=3.0
python-dotenv>=1.0
gunicorn>=22.0
pytest>=8.0
```

`.env.example` :

```
# Jeton des outils internes des locuteurs natifs (/v1/admin). Jamais dans l'extension.
AMIRA_ADMIN_TOKEN=change-moi
# Origines autorisées, séparées par des virgules. Vide = toute extension chrome-extension:// (développement).
AMIRA_ALLOWED_ORIGINS=
AMIRA_DB_PATH=instance/amira.sqlite3
AMIRA_RECORDINGS_DIR=media/recordings
AMIRA_ENGINE_VERSION=amira-mt-0.1
# Fonctions annoncées dans /v1/capabilities
AMIRA_TTS_ENABLED=true
AMIRA_STT_ENABLED=false
```

### 4.2 Application, erreurs et CORS

`amira/__init__.py`

```python
from flask import Flask
from dotenv import load_dotenv

from .config import Config
from .cors import register_cors
from .errors import register_errors
from .db import init_db
from .routes.public import public
from .routes.admin import admin


def create_app(config: type = Config) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(config)
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 Mo (audio de dictée compris)
    init_db(app)
    register_cors(app)
    register_errors(app)
    app.register_blueprint(public, url_prefix="/v1")
    app.register_blueprint(admin, url_prefix="/v1/admin")
    return app
```

`amira/errors.py` : **toute** erreur doit avoir ce format, sinon le front affiche un code générique.

```python
from flask import jsonify


class ApiError(Exception):
    """Codes lus par le front : RATE_LIMITED, UNAVAILABLE, TIMEOUT, BAD_REQUEST, UNSUPPORTED_LANGUAGE."""

    def __init__(self, code: str, message: str, status: int = 400, retry_after_ms: int | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.retry_after_ms = code, message, status, retry_after_ms


def _body(code, message, retry_after_ms=None):
    err = {"code": code, "message": message[:200]}
    if retry_after_ms is not None:
        err["retryAfterMs"] = retry_after_ms
    return jsonify({"error": err})


def register_errors(app):
    @app.errorhandler(ApiError)
    def api_error(e: ApiError):
        return _body(e.code, e.message, e.retry_after_ms), e.status

    @app.errorhandler(404)
    def not_found(_):
        return _body("BAD_REQUEST", "Point d'accès inconnu"), 404

    @app.errorhandler(413)
    def too_large(_):
        return _body("BAD_REQUEST", "Requête trop volumineuse"), 413

    @app.errorhandler(Exception)
    def unexpected(e):
        app.logger.exception("Erreur interne")  # pas de texte utilisateur dans les journaux
        return _body("UNAVAILABLE", "Service momentanément indisponible"), 500
```

`amira/cors.py`

```python
from flask import current_app, request


def register_cors(app):
    @app.after_request
    def cors(resp):
        origin = request.headers.get("Origin", "")
        allowed = [o.strip() for o in current_app.config["ALLOWED_ORIGINS"].split(",") if o.strip()]
        if origin.startswith("chrome-extension://") and (not allowed or origin in allowed):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
            # sans cette ligne, le front ne peut pas lire l'étiquette « Voix enregistrée »
            resp.headers["Access-Control-Expose-Headers"] = "X-Amira-Voice"
            resp.headers["Access-Control-Max-Age"] = "600"
        return resp
```

Notes :
- Flask répond seul aux requêtes `OPTIONS` (préflight), et `after_request` y ajoute les en-têtes.
- L'identifiant d'une extension chargée « non empaquetée » **change d'une machine à l'autre**. En développement, laisser `AMIRA_ALLOWED_ORIGINS` vide. En production, y mettre l'identifiant de l'extension publiée.
- L'extension envoie ses requêtes **sans cookies** (`credentials: "omit"`) : pas de session Flask, pas de `Allow-Credentials`.

### 4.3 Contrôle des marqueurs (`amira/markers.py`)

C'est la même règle que celle du front. Le serveur l'applique **avant** de répondre, pour corriger ou déclasser une traduction plutôt que de la faire rejeter.

```python
import re
from collections import Counter

MARKER_RE = re.compile(r"\{/?[NBE]\d+\}")
TAG_RE = re.compile(r"\{(/?)B(\d+)\}")


def same_markers(source: str, translated: str) -> bool:
    """Même ensemble de marqueurs, chacun le même nombre de fois (l'ordre peut changer)."""
    return Counter(MARKER_RE.findall(source)) == Counter(MARKER_RE.findall(translated))


def well_nested(text: str) -> bool:
    """{B0}…{/B0} correctement ouverts, fermés et imbriqués."""
    stack = []
    for closing, n in TAG_RE.findall(text):
        if not closing:
            stack.append(n)
        elif not stack or stack.pop() != n:
            return False
    return not stack


def markers_ok(source: str, translated: str) -> bool:
    return same_markers(source, translated) and well_nested(translated)


def speakable(text: str) -> str:
    """Texte lisible à voix haute : marqueurs retirés (le front le fait déjà, par sécurité)."""
    return re.sub(r"\s+", " ", MARKER_RE.sub(" ", text)).strip()
```

### 4.4 Points d'accès publics (`amira/routes/public.py`)

| Méthode | Chemin | Appelé quand | Réponse |
|---|---|---|---|
| `GET` | `/v1/health` | ouverture du panneau, toutes les 20 s au plus | `{"ok": true, "version": "…"}` |
| `GET` | `/v1/capabilities` | juste après `health` | fonctions disponibles |
| `POST` | `/v1/translate` | traduction de la page, contenu inédit, traducteur rapide | segments traduits avec statut |
| `POST` | `/v1/tts` | chaque passage lu (page, sélection, messages, avertissements) | audio, ou `204` |
| `POST` | `/v1/stt?language=ff` | dictée, seulement si `stt: true` | `{"text": "…"}` |
| `POST` | `/v1/feedback` | signalement depuis l'onglet Journal | `204` |

```python
import time
from flask import Blueprint, Response, current_app, request, send_file

from ..errors import ApiError
from ..markers import speakable
from ..services import translator, voice, stt as stt_service
from ..db import save_feedback

public = Blueprint("public", __name__)

LANGS = {"fr", "en", "ff"}
CATEGORIES = {"label", "instruction", "fees", "security_warning", "error"}


def _json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("BAD_REQUEST", "Corps JSON attendu")
    return data


@public.get("/health")
def health():
    return {"ok": True, "version": current_app.config["ENGINE_VERSION"]}


@public.get("/capabilities")
def capabilities():
    cfg = current_app.config
    return {
        "translate": True,
        "tts": cfg["TTS_ENABLED"],
        "stt": cfg["STT_ENABLED"],
        "languages": ["fr", "en", "ff"],
        "varietes": ["ngaoundere", "garoua", "maroua"],
    }


@public.post("/translate")
def translate():
    t0 = time.perf_counter()
    req = _json()
    source, target = req.get("source"), req.get("target")
    segments = req.get("segments")
    if source == "auto":
        source = None  # à détecter côté serveur si besoin ; l'extension ne l'envoie plus
    if target not in LANGS or (source is not None and source not in LANGS):
        raise ApiError("UNSUPPORTED_LANGUAGE", "Langue non prise en charge")
    if source == target or {source, target} == {"fr", "en"}:
        raise ApiError("UNSUPPORTED_LANGUAGE", "Sens de traduction non pris en charge")
    if not isinstance(segments, list) or not 1 <= len(segments) <= 40:
        raise ApiError("BAD_REQUEST", "Entre 1 et 40 segments par requête")

    # la variété ne compte que vers le fulfulde (l'extension envoie toujours "ngaoundere")
    variety = req.get("variety") if target == "ff" else None
    out = []
    for seg in segments:
        if not isinstance(seg, dict) or not isinstance(seg.get("id"), str) or not isinstance(seg.get("text"), str):
            raise ApiError("BAD_REQUEST", "Segment mal formé")
        category = seg.get("categoryHint") if seg.get("categoryHint") in CATEGORIES else None
        out.append(translator.translate_segment(seg["id"], seg["text"], source, target, variety, category))

    return {
        "requestId": req.get("requestId", ""),
        "engineVersion": current_app.config["ENGINE_VERSION"],
        "latencyMs": round((time.perf_counter() - t0) * 1000),
        "segments": out,
    }


@public.post("/tts")
def tts():
    if not current_app.config["TTS_ENABLED"]:
        raise ApiError("BAD_REQUEST", "Voix désactivée")
    req = _json()
    text = speakable(str(req.get("text", "")))
    language = req.get("language")
    key = req.get("segmentKey")
    speed = float(req.get("speed") or 1)
    if language not in LANGS or not text:
        raise ApiError("BAD_REQUEST", "Texte ou langue manquant")

    # 1. enregistrement d'un locuteur natif pour ce passage
    rec = voice.find_recording(key, language)
    if rec:
        resp = send_file(rec["path"], mimetype=rec["mime"])
        resp.headers["X-Amira-Voice"] = "recorded"
        return resp
    # 2. passage demandé sans enregistrement : il entre dans la liste « à enregistrer »
    voice.note_missing(key, language, text)
    # 3. voix de synthèse du serveur, si elle existe pour cette langue
    audio = voice.synthesize(text, language, speed)  # (bytes, mime) ou None
    if audio:
        data, mime = audio
        return Response(data, mimetype=mime, headers={"X-Amira-Voice": "synthetic"})
    # 4. rien : le panneau utilise la synthèse du navigateur (« Voix de synthèse »)
    return "", 204


@public.post("/stt")
def stt():
    if not current_app.config["STT_ENABLED"]:
        raise ApiError("BAD_REQUEST", "Dictée désactivée")
    language = request.args.get("language", "ff")
    audio = request.get_data()
    if not audio:
        raise ApiError("BAD_REQUEST", "Audio manquant")
    return {"text": stt_service.transcribe(audio, request.mimetype, language)}


@public.post("/feedback")
def feedback():
    req = _json()
    for field in ("segmentId", "originalMasked", "shown", "suggestion"):
        if not isinstance(req.get(field), str):
            raise ApiError("BAD_REQUEST", f"Champ manquant : {field}")
    save_feedback(req["segmentId"], req["originalMasked"], req["shown"], req["suggestion"])
    return "", 204
```

### 4.5 Le service de traduction (`amira/services/translator.py`)

L'ordre à suivre pour chaque segment :

```python
from ..markers import markers_ok
from ..db import find_validated

# Seuil en dessous duquel une traduction automatique est déclarée « uncertain »
MIN_CONFIDENCE = 0.5


def translate_segment(seg_id, masked, source, target, variety, category):
    # 1. Mémoire : traduction déjà validée par un locuteur natif pour ce texte masqué exact
    hit = find_validated(source, target, variety, masked)
    if hit:
        return {"id": seg_id, "text": hit["text"], "status": "validated", "confidence": 1.0, "origin": "memory"}

    # 2. Moteur de traduction (modèle, service de traduction automatique…), au choix de l'équipe back-end.
    #    Il reçoit le texte masqué et doit garder les marqueurs tels quels.
    text, confidence, origin = engine_translate(masked, source, target, variety, category)

    # 3. Contrôle des marqueurs : une seule nouvelle tentative, puis on déclare le doute
    if not markers_ok(masked, text):
        text, confidence, origin = engine_translate(masked, source, target, variety, category, strict=True)
    if not markers_ok(masked, text):
        return {"id": seg_id, "text": masked, "status": "uncertain", "confidence": 0.0, "origin": origin}

    # 4. Statut honnête
    status = "machine" if confidence >= MIN_CONFIDENCE else "uncertain"
    return {"id": seg_id, "text": text, "status": status, "confidence": round(confidence, 2), "origin": origin}
```

Règles à respecter :
- **`id` identique** à celui reçu, **un segment en sortie pour chaque segment en entrée**. Un segment absent est gardé en original par le front.
- **`status: "validated"` seulement après relecture par un locuteur natif.** Jamais pour une sortie de moteur.
- **Avertissements de sécurité** (`categoryHint: "security_warning"`) : le front n'affiche que la version `validated`. Ce sont **les premiers textes à faire valider** par les natifs.
- **`origin`** : `"memory"` (mémoire validée), `"template"` (gabarit, par exemple « Frais : {N0} »), `"llm"` (moteur).
- **Le front a un délai de 8 s par requête.** Un lot de 40 segments doit tenir dans ce temps : traduire les segments du lot en parallèle si le moteur est lent.
- Ne pas écrire de traduction en fulfulde « à la main » dans le code : elles viennent du moteur, puis de la validation par les natifs.

### 4.6 Voix et enregistrements des natifs (`amira/services/voice.py`)

- **`segmentKey`** = `"k"` + empreinte FNV-1a 32 bits (8 caractères hexadécimaux) du **texte source masqué** : repères `{B0}` `{/B0}` `{E0}` remplacés par un espace, espaces normalisés, minuscules. Elle est **identique d'une visite à l'autre** et d'un utilisateur à l'autre. Calcul côté front : `segmentKey()` dans [front/src/content/engine.ts](../front/src/content/engine.ts). Équivalent Python, utile pour préparer des enregistrements à l'avance :

  ```python
  import re

  def segment_key(masked_source: str) -> str:
      s = re.sub(r"\{/?[BE]\d+\}", " ", masked_source)
      s = re.sub(r"\s+", " ", s).strip().lower()
      h = 0x811C9DC5
      for ch in s:
          h ^= ord(ch)  # le front prend des unités UTF-16 : identique hors caractères hors BMP
          h = (h * 0x01000193) & 0xFFFFFFFF
      return f"k{h:08x}"
  ```

- **`text`** reçu par `/v1/tts` : la **traduction affichée** (masquée) quand la page est traduite, sinon le **texte de la page** (masqué). Les marqueurs `{N0}` sont déjà retirés : montants et noms ne sont pas lus.
- **`find_recording(key, language)`** : cherche dans `media/recordings/` un fichier enregistré pour cette clé et cette langue.
- **`note_missing(key, language, text)`** : compte les passages demandés sans enregistrement. Cette liste, triée par nombre de demandes, dit aux natifs **quoi enregistrer en priorité**.
- **`synthesize(...)`** : renvoie `None` tant qu'aucune voix de synthèse fulfulde n'est disponible. Le serveur répond alors `204` et le navigateur lit avec sa propre voix, étiquetée « Voix de synthèse ».

### 4.7 Outils internes des locuteurs natifs (`amira/routes/admin.py`)

Ces points d'accès ne sont **jamais appelés par l'extension**. Ils servent à la validation linguistique (un livrable demandé par le règlement du concours). Ils sont protégés par l'en-tête `Authorization: Bearer <AMIRA_ADMIN_TOKEN>`, et ce jeton ne va **jamais** dans l'extension.

| Méthode | Chemin | Rôle |
|---|---|---|
| `GET` | `/v1/admin/feedback?status=pending` | signalements à relire |
| `POST` | `/v1/admin/feedback/<id>/resolve` | marquer un signalement traité |
| `GET` | `/v1/admin/translations?status=machine` | traductions automatiques à relire (avertissements de sécurité en premier) |
| `PUT` | `/v1/admin/translations` | enregistrer une traduction **validée** : `{source, target, variety, sourceMasked, text, validatedBy}`. Elle sert ensuite à tous les utilisateurs (`origin: "memory"`). |
| `GET` | `/v1/admin/recordings/missing?language=ff` | passages à enregistrer, les plus demandés d'abord |
| `PUT` | `/v1/admin/recordings/<segmentKey>?language=ff` | déposer l'audio d'un natif (corps = audio brut, `Content-Type` = type du fichier) |
| `DELETE` | `/v1/admin/recordings/<segmentKey>?language=ff` | retirer un enregistrement |

```python
import hmac
from functools import wraps
from flask import Blueprint, current_app, request

from ..errors import ApiError

admin = Blueprint("admin", __name__)


@admin.before_request
def require_token():
    expected = current_app.config["ADMIN_TOKEN"]
    given = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(given, expected):
        raise ApiError("BAD_REQUEST", "Accès refusé", status=401)
```

`PUT /v1/admin/translations` doit refuser (`400`) une traduction dont les marqueurs ne correspondent pas à `sourceMasked` (`markers_ok`).

### 4.8 Données (`amira/db.py`, SQLite)

```sql
CREATE TABLE IF NOT EXISTS translations (
  source TEXT, target TEXT, variety TEXT, source_masked TEXT,
  text TEXT NOT NULL, status TEXT NOT NULL,          -- validated | machine
  validated_by TEXT, updated_at TEXT,
  PRIMARY KEY (source, target, variety, source_masked)
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  segment_id TEXT, original_masked TEXT, shown TEXT, suggestion TEXT,
  status TEXT DEFAULT 'pending', created_at TEXT
);
CREATE TABLE IF NOT EXISTS recordings (
  segment_key TEXT, language TEXT, path TEXT, mime TEXT, speaker TEXT, created_at TEXT,
  PRIMARY KEY (segment_key, language)
);
CREATE TABLE IF NOT EXISTS missing_audio (
  segment_key TEXT, language TEXT, text TEXT, requests INTEGER DEFAULT 1, last_at TEXT,
  PRIMARY KEY (segment_key, language)
);
```

Pour la variété : `variety` vaut `NULL` quand la cible n'est pas `ff`. Tous les textes stockés sont **masqués** : la base ne contient ni montant, ni nom, ni numéro.

### 4.9 Sécurité

- **Aucun secret dans l'extension.** Le seul secret est `AMIRA_ADMIN_TOKEN`, côté serveur.
- **Journaux** : méthode, chemin, statut, durée, `requestId`. **Pas le texte des segments**, même masqué.
- **Limites** : 40 segments par requête, 5 Mo par corps. En cas de surcharge, répondre `429` avec `retryAfterMs` : le front réessaie une fois après ce délai.
- **HTTPS obligatoire** hors développement (`http://localhost` reste accepté pour les tests).
- Le serveur ne reçoit jamais de données bancaires : s'il voit un montant ou un nom en clair dans un segment, c'est un défaut du masquage côté front. **Le signaler**, ne pas le stocker.

---

## 5. Lancer le serveur

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # puis changer AMIRA_ADMIN_TOKEN

flask --app amira run --port 5000 --debug          # développement
gunicorn -w 2 -b 0.0.0.0:8000 --timeout 30 wsgi:app # production (derrière HTTPS)
```

`wsgi.py` :

```python
from amira import create_app

app = create_app()
```

---

## 6. Brancher le front sur Flask

```bash
cd front
echo "VITE_AMIRA_API_URL=http://localhost:5000" > .env
npm run build      # ajoute http://localhost:5000/* aux autorisations de l'extension
```

Ensuite, dans `chrome://extensions`, cliquer sur ↻ sous Amira. La pastille doit passer de « Prêt · démo » à **« Prêt »**.

| Ce que montre la pastille | Cause probable |
|---|---|
| « Prêt · démo » | `VITE_AMIRA_API_URL` vide ou extension pas reconstruite |
| « Hors ligne » | serveur arrêté, mauvaise adresse, ou réponse au-delà de 8 s |
| « Erreur » | `/v1/health` ou `/v1/capabilities` renvoie une erreur (code visible dans l'onglet Journal) |
| Onglet Voix grisé | `/v1/capabilities` renvoie `"tts": false` |

## 7. Vérifier à la main

```bash
API=http://localhost:5000

curl -s $API/v1/health
curl -s $API/v1/capabilities

curl -s $API/v1/translate -H 'Content-Type: application/json' -d '{
  "requestId": "test1", "source": "fr", "target": "ff", "variety": "ngaoundere",
  "segments": [{ "id": "s1", "text": "Votre solde est de {B0}{N0}{/B0} au {N1}.",
                 "categoryHint": "label", "placeholders": ["{N0}", "{N1}", "{B0}", "{/B0}"] }]
}'

# sens refusé : doit renvoyer UNSUPPORTED_LANGUAGE
curl -s $API/v1/translate -H 'Content-Type: application/json' \
  -d '{"requestId":"t2","source":"fr","target":"en","variety":null,"segments":[{"id":"s1","text":"Bonjour","placeholders":[]}]}'

# voix : 204 tant qu'il n'y a ni enregistrement ni synthèse
curl -si $API/v1/tts -H 'Content-Type: application/json' \
  -d '{"text":"Votre solde est de au","language":"ff","speed":1,"segmentKey":"k3f9a01c2"}' | head -5

curl -si $API/v1/feedback -H 'Content-Type: application/json' \
  -d '{"segmentId":"s1","originalMasked":"Frais : {N0}","shown":"… {N0}","suggestion":"…"}' | head -1

# préflight CORS : doit renvoyer Access-Control-Allow-Origin et Expose-Headers
curl -si -X OPTIONS $API/v1/translate -H 'Origin: chrome-extension://abc' \
  -H 'Access-Control-Request-Method: POST' | grep -i access-control
```

## 8. Liste de contrôle avant la démonstration

- [ ] `/v1/health` et `/v1/capabilities` répondent en moins d'une seconde.
- [ ] Chaque segment reçu revient avec le **même `id`** et **exactement les mêmes marqueurs**.
- [ ] `fr → ff`, `en → ff`, `ff → fr` et `ff → en` fonctionnent. `fr ↔ en` renvoie `UNSUPPORTED_LANGUAGE`.
- [ ] `variety` est ignorée quand la cible n'est pas `ff`.
- [ ] Un lot de 40 segments répond en moins de 8 s.
- [ ] Les avertissements de sécurité du parcours de test sont **validés** par un locuteur natif.
- [ ] Les erreurs ont la forme `{"error": {"code", "message", "retryAfterMs"?}}`.
- [ ] `/v1/tts` renvoie l'audio d'un natif avec `X-Amira-Voice: recorded`, sinon `204`.
- [ ] Les en-têtes CORS sont présents, `X-Amira-Voice` compris.
- [ ] Aucun texte de segment dans les journaux du serveur.
- [ ] Pastille « Prêt » (sans « démo ») dans l'extension reconstruite.
