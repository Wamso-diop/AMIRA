"""M2M100 : codes fr/en/ff, jeton de langue, et (marqueur model) le vrai modèle local."""
import pytest

from amira import config
from amira.engine import lang_id
from gold import rows


class Tok:
    unk_token_id = 3

    def __init__(self, vocab, get_lang_id=None):
        self.vocab = vocab
        if get_lang_id:
            self.get_lang_id = get_lang_id

    def convert_tokens_to_ids(self, t):
        return self.vocab.get(t, self.unk_token_id)


def test_codes_et_dossier_par_defaut():
    cfg = config.load({"AMIRA_ENV": "development"})
    assert cfg["LANG_CODES"] == {"fr": "fr", "en": "en", "ff": "ff"} and cfg["MODEL_DIR"] == "models/m2m_ff"
    assert cfg["ENGINE"] == "m2m100"


def test_ancienne_valeur_nllb_refusee():
    with pytest.raises(RuntimeError, match="m2m100 ou memory"):
        config.load({"AMIRA_ENV": "development", "AMIRA_ENGINE": "nllb"})


def test_jeton_de_langue_ordre_de_recherche():
    assert lang_id(Tok({}, get_lang_id=lambda c: 7), "ff") == 7  # get_lang_id d'abord
    assert lang_id(Tok({"xx": 5}), "xx") == 5  # puis le code
    assert lang_id(Tok({"__ff__": 9}), "ff") == 9  # puis « __code__ »


def test_jeton_de_langue_introuvable():
    def absent(_):
        raise KeyError

    with pytest.raises(ValueError, match="introuvable"):
        lang_id(Tok({}, get_lang_id=absent), "zz")
    with pytest.raises(ValueError, match="'zz'"):
        lang_id(Tok({}), "zz")


# --- vrai modèle (pytest -m model, dossier : AMIRA_MODEL_DIR) -------------------------

@pytest.fixture(scope="module")
def engine():
    from real_engine import real_engine

    e = real_engine()
    e.load()  # HF_HUB_OFFLINE est forcé par le moteur : aucun téléchargement
    return e


@pytest.mark.model
def test_chargement(engine):
    assert engine.ready() and type(engine._model).__name__ == "M2M100ForConditionalGeneration"


@pytest.mark.model
def test_jeton_ff_valide(engine):
    tok = engine._tok
    for code in ("fr", "en", "ff"):
        i = lang_id(tok, code)
        assert i != tok.unk_token_id and tok.convert_ids_to_tokens(i) == f"__{code}__"


@pytest.mark.model
def test_aucune_lettre_du_gold_inconnue_du_tokenizer(engine):
    tok = engine._tok
    letters = "ɓɗƴŋƁƊƳŊ"
    assert tok.unk_token_id not in tok(letters)["input_ids"]
    for r in rows():
        text = r["ff"].replace("{V", "{")
        assert tok.unk_token_id not in tok(text)["input_ids"], r["id"]


@pytest.mark.model
def test_marqueurs_conserves_et_sortie_non_vide(engine):
    texts = ["Votre solde est de {V1}.", "Virement de {V1} vers le compte {V2} effectué."]
    for text, (out, _conf) in zip(texts, engine.translate(texts, "fr", "ff")):
        assert out.strip()
        for m in ("{V1}", "{V2}"):
            assert (m in out) == (m in text), (text, out)


def test_code_source_inconnu_erreur_claire():
    from amira.engine import generate

    with pytest.raises(ValueError, match="'fra'"):
        generate(Tok({"__ff__": 9}), None, ["x"], "fra", "ff", strict=False)
