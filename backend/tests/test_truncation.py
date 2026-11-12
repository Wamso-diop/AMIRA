"""Audit 2 : confiance à 0 si l'entrée dépasse la limite de jetons, ou si la sortie atteint max_new_tokens sans fin."""
import pytest

torch = pytest.importorskip("torch")

from amira.engine import MAX_INPUT_TOKENS, MAX_NEW_TOKENS, generate

EOS, PAD = 2, 1
START = EOS  # comme NLLB : decoder_start_token_id = </s>, donc chaque séquence commence par </s>


class FakeTok:
    """Tokenizer factice : un jeton par mot."""
    eos_token_id, pad_token_id = EOS, PAD
    src_lang = None

    def __call__(self, texts, return_tensors=None, padding=False, truncation=False, max_length=None):
        ids = [[10 + i for i, _ in enumerate(t.split())] + [EOS] for t in texts]
        if truncation:
            ids = [x[:max_length] for x in ids]
        if return_tensors is None:
            return {"input_ids": ids}
        width = max(map(len, ids))
        return {"input_ids": torch.tensor([x + [PAD] * (width - len(x)) for x in ids])}

    def convert_tokens_to_ids(self, code):
        return 99

    def batch_decode(self, sequences, skip_special_tokens=True):
        return [" ".join(f"m{int(t)}" for t in row if int(t) not in (EOS, PAD, 99)) for row in sequences]


class FakeModel:
    """Sorties choisies par le test : une liste de séquences (sans le jeton de début)."""

    def __init__(self, rows):
        self.rows = rows

    def generate(self, **kw):
        width = max(map(len, self.rows)) + 1
        seqs = torch.tensor([[START] + r + [PAD] * (width - 1 - len(r)) for r in self.rows])
        return type("Out", (), {"sequences": seqs, "sequences_scores": torch.tensor([-0.1] * len(self.rows))})()


def run(texts, rows):
    return generate(FakeTok(), FakeModel(rows), texts, "fra_Latn", "fuv_Latn", strict=False)


def test_sortie_normale_garde_sa_confiance():
    ((_, conf),) = run(["Bonjour à tous"], [[50, 51, EOS]])
    assert conf == pytest.approx(0.905, abs=0.01)


def test_entree_au_dela_de_la_limite():
    long = " ".join(["mot"] * MAX_INPUT_TOKENS)  # + </s> = limite + 1
    short = " ".join(["mot"] * (MAX_INPUT_TOKENS - 1))  # + </s> = limite exacte
    (_, c_long), (_, c_short) = run([long, short], [[50, EOS], [50, EOS]])
    assert c_long == 0.0 and c_short > 0


def test_sortie_coupee_a_max_new_tokens_sans_fin():
    cut = [50 + i % 30 for i in range(MAX_NEW_TOKENS)]  # aucun </s> : la génération a été arrêtée par la limite
    ended = [50 + i % 30 for i in range(MAX_NEW_TOKENS - 1)] + [EOS]  # même longueur, mais finie
    (_, c_cut), (_, c_ended) = run(["Texte un", "Texte deux"], [cut, ended])
    assert c_cut == 0.0 and c_ended > 0


@pytest.mark.model
def test_vrai_modele_texte_trop_long():
    from pathlib import Path

    from amira.engine import NllbEngine

    e = NllbEngine(str(Path(__file__).parents[1] / "models" / "nllb_ff"), {"fr": "fra_Latn", "ff": "fuv_Latn"})
    e.load()
    long = ("Votre demande de virement a été reçue et sera traitée dans les meilleurs délais par nos services. " * 8)[:1000]
    ((_, conf),) = e.translate([long], "fr", "ff")
    assert conf == 0.0


def test_generate_transmet_max_time():
    seen = {}

    class Recorder(FakeModel):
        def generate(self, **kw):
            seen.update(kw)
            return super().generate(**kw)

    generate(FakeTok(), Recorder([[50, EOS]]), ["Texte"], "fra_Latn", "fuv_Latn", strict=False, max_time=1.5)
    assert seen["max_time"] == 1.5
