"""Moteur de traduction : interface minimale translate(textes, src, tgt) -> [(texte, confiance)].

Seul fichier qui importe transformers/torch, au premier chargement. Le moteur reçoit la vue {V1}, {V2}…
(markers.model_view) ; il ne voit jamais un texte refusé par la garde, ni une catégorie sensible.
Remplacer le modèle = remplacer le dossier AMIRA_MODEL_DIR, sans toucher au code.
"""
import logging
import math
import os
import threading
import time

log = logging.getLogger("amira")

MAX_INPUT_TOKENS, MAX_NEW_TOKENS = 128, 96


class EngineError(Exception):
    """Échec du moteur. Message fixe : l'exception d'origine peut contenir le texte traduit."""

    def __init__(self):
        super().__init__("échec du moteur")


def lang_id(tok, code: str) -> int:
    """Identifiant du jeton d'une langue (source ou cible) : get_lang_id (M2M100), sinon le code, puis « __code__ »."""
    get = getattr(tok, "get_lang_id", None)
    if get is not None:
        try:
            return get(code)
        except KeyError:
            pass
    for token in (code, f"__{code}__"):
        i = tok.convert_tokens_to_ids(token)
        if i is not None and i != getattr(tok, "unk_token_id", None):
            return i
    raise ValueError(f"jeton de langue introuvable dans le tokenizer : {code!r}")


def generate(tok, model, texts: list[str], src_code: str, tgt_code: str, strict: bool,
             max_time: float | None = None) -> list[tuple[str, float]]:
    """Confiance mise à 0 pour une traduction partielle : entrée tronquée, ou sortie arrêtée (max_new_tokens, max_time)."""
    import torch

    lang_id(tok, src_code)  # code inconnu du tokenizer (ex. un code à 3 lettres avec M2M100) : erreur claire, pas un KeyError
    tok.src_lang = src_code
    too_long = [len(ids) > MAX_INPUT_TOKENS for ids in tok(texts)["input_ids"]]
    enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=MAX_INPUT_TOKENS)
    with torch.inference_mode():
        out = model.generate(
            **enc,
            forced_bos_token_id=lang_id(tok, tgt_code),
            num_beams=8 if strict else 4,
            no_repeat_ngram_size=3 if strict else 0,
            max_new_tokens=MAX_NEW_TOKENS,
            max_time=max_time,  # plafond dur : la génération s'arrête à l'échéance, les phrases inachevées n'ont pas de </s>
            max_length=None,  # sinon generation_config (200) entre en conflit avec max_new_tokens
            output_scores=True,
            return_dict_in_generate=True,
        )
    decoded = tok.batch_decode(out.sequences, skip_special_tokens=True)
    # position 0 = jeton de départ du décodeur (</s> pour M2M100) : la fin se cherche après
    ended = [bool((row[1:] == tok.eos_token_id).any()) for row in out.sequences]
    # exp(score moyen par jeton) : probabilité moyenne par jeton, à calibrer
    return [(t, 0.0 if cut or not done else math.exp(s))
            for t, s, cut, done in zip(decoded, out.sequences_scores.tolist(), too_long, ended)]


class Engine:
    def __init__(self, model_dir: str, codes: dict[str, str], seconds_per_segment: float = 0.8):
        self.model_dir, self.codes = model_dir, codes
        # durée estimée d'un segment (faisceau normal), remesurée après chaque génération
        self.seconds_per_segment = seconds_per_segment
        self._lock = threading.Lock()  # un seul generate à la fois : un seul modèle en RAM
        self._tok = self._model = None
        self.loader: threading.Thread | None = None

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            if not os.path.isfile(os.path.join(self.model_dir, "config.json")):
                raise FileNotFoundError("dossier du modèle incomplet")  # avant d'importer transformers (2 à 3 s)
            os.environ["HF_HUB_OFFLINE"] = "1"  # P6 : jamais de téléchargement
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            tok = AutoTokenizer.from_pretrained(self.model_dir)
            model = AutoModelForSeq2SeqLM.from_pretrained(self.model_dir).eval()
            # échauffement : la première génération est plus lente ; /v1/ready ne passe au vert qu'après
            codes = list(self.codes.values())
            generate(tok, model, ["Bonjour."], codes[0], codes[-1], strict=False)
            self._tok, self._model = tok, model

    def start_loading(self) -> None:
        """Chargement en tâche de fond, une fois. Un échec est journalisé (sinon /v1/ready resterait à 503 sans explication)."""
        if self.loader is not None:
            return

        def load():
            try:
                self.load()
            except Exception as e:
                log.error("chargement du modèle impossible (%s) : %s", self.model_dir, type(e).__name__)

        self.loader = threading.Thread(target=load, name="amira-load", daemon=True)
        self.loader.start()

    def ready(self) -> bool:
        """Le premier appel lance le chargement : les commandes flask (export, purge) ne chargent jamais le modèle."""
        self.start_loading()
        return self._model is not None

    def translate(self, texts: list[str], src: str, tgt: str, strict: bool = False, deadline: float | None = None):
        """deadline : instant (time.perf_counter) à ne pas dépasser, attente du verrou comprise."""
        if not self._lock.acquire(timeout=-1 if deadline is None else max(deadline - time.perf_counter(), 0)):
            raise TimeoutError("moteur occupé")
        try:
            max_time = None if deadline is None else deadline - time.perf_counter()
            if max_time is not None and max_time <= 0:
                raise TimeoutError("échéance dépassée")
            t0 = time.perf_counter()
            out = generate(self._tok, self._model, texts, self.codes[src], self.codes[tgt], strict, max_time=max_time)
            # le faisceau strict (8) coûte environ deux fois le normal (4)
            measured = (time.perf_counter() - t0) / len(texts) / (2 if strict else 1)
            # plus lent que prévu : on suit aussitôt ; plus rapide : on redescend de moitié seulement
            self.seconds_per_segment = max(measured, (self.seconds_per_segment + measured) / 2)
            return out
        except TimeoutError:
            raise
        except Exception as e:
            log.error("moteur : %s", type(e).__name__)
            raise EngineError() from None
        finally:
            self._lock.release()


class FakeEngine:
    """Faux moteur des tests : fn(texte, src, tgt, strict) -> (texte, confiance). Garde la trace des appels."""

    def __init__(self, fn=None, loaded: bool = True, delay: float = 0.0, seconds_per_segment: float = 0.0):
        self.fn = fn or (lambda t, *_: (f"<<{t}>>", 0.9))
        self.loaded, self.delay, self.busy = loaded, delay, False
        self.seconds_per_segment = seconds_per_segment
        self.calls: list[tuple] = []
        self.deadlines: list[float | None] = []

    def ready(self) -> bool:
        return self.loaded

    def translate(self, texts, src, tgt, strict=False, deadline=None):
        if self.busy:
            time.sleep(max(deadline - time.perf_counter(), 0) if deadline else 0)
            raise TimeoutError("moteur occupé")
        self.calls.append((list(texts), src, tgt, strict))
        self.deadlines.append(deadline)
        time.sleep(self.delay)
        try:
            return [self.fn(t, src, tgt, strict) for t in texts]
        except Exception as e:
            log.error("moteur : %s", type(e).__name__)
            raise EngineError() from None


def from_config(cfg: dict):
    """Moteur décrit par la configuration ; chargé en tâche de fond au premier ready() (/v1/ready répond 503 d'ici là)."""
    if cfg["ENGINE"] == "memory":
        return None
    return Engine(cfg["MODEL_DIR"], cfg["LANG_CODES"], cfg["ENGINE_SEG_S"])
