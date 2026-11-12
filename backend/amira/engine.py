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


class EngineError(Exception):
    """Échec du moteur. Message fixe : l'exception d'origine peut contenir le texte traduit."""

    def __init__(self):
        super().__init__("échec du moteur")


def generate(tok, model, texts: list[str], src_code: str, tgt_code: str, strict: bool) -> list[tuple[str, float]]:
    import torch

    tok.src_lang = src_code
    enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=128)
    with torch.inference_mode():
        out = model.generate(
            **enc,
            forced_bos_token_id=tok.convert_tokens_to_ids(tgt_code),
            num_beams=8 if strict else 4,
            no_repeat_ngram_size=3 if strict else 0,
            max_new_tokens=96,
            max_length=None,  # sinon generation_config (200) entre en conflit avec max_new_tokens
            output_scores=True,
            return_dict_in_generate=True,
        )
    decoded = tok.batch_decode(out.sequences, skip_special_tokens=True)
    # exp(score moyen par jeton) : probabilité moyenne par jeton, à calibrer
    return [(t, math.exp(s)) for t, s in zip(decoded, out.sequences_scores.tolist())]


class NllbEngine:
    def __init__(self, model_dir: str, codes: dict[str, str]):
        self.model_dir, self.codes = model_dir, codes
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

    def translate(self, texts: list[str], src: str, tgt: str, strict: bool = False, timeout: float = -1):
        if not self._lock.acquire(timeout=timeout):
            raise TimeoutError("moteur occupé")
        try:
            return generate(self._tok, self._model, texts, self.codes[src], self.codes[tgt], strict)
        except Exception as e:
            log.error("moteur : %s", type(e).__name__)
            raise EngineError() from None
        finally:
            self._lock.release()


class FakeEngine:
    """Faux moteur des tests : fn(texte, src, tgt, strict) -> (texte, confiance). Garde la trace des appels."""

    def __init__(self, fn=None, loaded: bool = True, delay: float = 0.0):
        self.fn = fn or (lambda t, *_: (f"<<{t}>>", 0.9))
        self.loaded, self.delay, self.busy = loaded, delay, False
        self.calls: list[tuple] = []

    def ready(self) -> bool:
        return self.loaded

    def translate(self, texts, src, tgt, strict=False, timeout=-1):
        if self.busy:
            time.sleep(max(timeout, 0))
            raise TimeoutError("moteur occupé")
        self.calls.append((list(texts), src, tgt, strict))
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
    return NllbEngine(cfg["MODEL_DIR"], cfg["LANG_CODES"])
