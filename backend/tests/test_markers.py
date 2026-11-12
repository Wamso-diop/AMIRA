"""S2 : marqueurs {N0} {B0} {/B0} {E0}. Cas du front (front/tests/unit/verify.test.ts) puis cas du serveur."""
import pytest

from amira.markers import canonicalize, from_model, markers_ok, model_view, restore, same_markers, speakable, well_nested

SRC = "Votre solde est de {B0}{N0}{/B0} au {N1}."


# --- cas du front ---------------------------------------------------------------

def test_ordre_different_accepte():
    assert same_markers("Envoyer {N0} à {N1}", "{N1} … {N0}")


@pytest.mark.parametrize("out", ["{N0}", "{N0} {N0} {N1}", "{N0} {N1} {N2}"])
def test_marqueur_perdu_double_ou_invente(out):
    assert not same_markers("{N0} et {N1}", out)


def test_balise_perdue():
    assert not same_markers("{B0}x{/B0}", "{B0}x")


def test_imbrication():
    assert well_nested("{B0}a{B1}b{/B1}{/B0}")
    assert not well_nested("{B0}a{B1}b{/B0}{/B1}")


# --- cas du serveur ----------------------------------------------------------------

@pytest.mark.parametrize("text", ["{/B0}a{B0}", "{B0}a", "a{/B0}", "{B0}a{/B1}", "{B0}{B0}a{/B0}"])
def test_mal_imbrique(text):
    assert not well_nested(text)


def test_markers_ok_exige_ensemble_et_imbrication():
    assert markers_ok(SRC, "Au {N1}, {B0}{N0}{/B0} reste.")
    assert not markers_ok(SRC, "Au {N1}, {/B0}{N0}{B0} reste.")  # même ensemble, mal imbriqué
    assert not markers_ok(SRC, "Au {N1}, {B0}{/B0} reste.")      # {N0} perdu
    assert not markers_ok(SRC, "Au {N1} {N1}, {B0}{N0}{/B0}.")   # doublon


def test_element_atomique():
    assert markers_ok("Code {E0} puis {N0}", "{N0} {E0}")
    assert not markers_ok("Code {E0} puis {N0}", "{N0}")


@pytest.mark.parametrize("src,out,ok", [
    ("Accolade {x} gardée", "{x} gardée", True),
    ("Accolade {x} gardée", "gardée", False),          # accolade inconnue perdue
    ("Accolade {x} gardée", "{y} gardée", False),      # accolade inconnue modifiée
    ("Sans accolade", "Sans {V1} accolade", False),     # marqueur du modèle resté
    ("Sans accolade", "Sans { accolade", False),        # accolade isolée ajoutée
    ("Sans accolade", "Sans {N0} accolade", False),     # marqueur inventé
    ("{N0}", "{n0}", False),                            # casse changée
    ("{N0}", "{ N0 }", False),                          # espaces ajoutés
])
def test_accolades_inconnues(src, out, ok):
    assert markers_ok(src, out) is ok


def test_canonicalize_renumerote_dans_l_ordre():
    canon, table = canonicalize("De {N3} vers {B0}{N1}{/B0} puis {N3}")
    assert canon == "De {N0} vers {B0}{N1}{/B0} puis {N0}"
    assert table == {"{N0}": "{N3}", "{N1}": "{N1}"}
    assert restore("{N1} et {N0}", table) == "{N1} et {N3}"


def test_canonicalize_identite_pour_le_front():
    canon, table = canonicalize(SRC)
    assert canon == SRC and restore(canon, table) == SRC


def test_restore_sans_collision():
    # {N0}→{N1} et {N1}→{N0} : un remplacement naïf en deux passes donnerait {N0}{N0}
    _, table = canonicalize("{N1} {N0}")
    assert restore("{N0} {N1}", table) == "{N1} {N0}"


def test_model_view_aller_retour():
    view, table = model_view(SRC)
    assert view == "Votre solde est de {V1}{V2}{V3} au {V4}."
    assert from_model(view, table) == SRC
    assert from_model("Au {V4}, {V1}{V2}{V3}.", table) == "Au {N1}, {B0}{N0}{/B0}."


def test_model_view_doublon_meme_V():
    view, table = model_view("{N0} puis {N0}")
    assert view == "{V1} puis {V1}" and from_model(view, table) == "{N0} puis {N0}"


def test_model_view_sans_marqueur():
    assert model_view("Bonjour") == ("Bonjour", {})


def test_from_model_V_inconnu_detecte():
    view, table = model_view("Payer {N0}")
    out = from_model("Payer {V1} {V2}", table)
    assert not markers_ok("Payer {N0}", out)


def test_from_model_marqueur_perdu_detecte():
    _, table = model_view(SRC)
    assert not markers_ok(SRC, from_model("Au {V4}, {V1}{V3}.", table))


def test_model_view_refuse_un_V_litteral():
    with pytest.raises(ValueError):
        model_view("Texte {V1} et {N0}")


def test_speakable():
    assert speakable("Payer {B0}{N0}{/B0} avant {E0} le {N1}.") == "Payer avant le ."
