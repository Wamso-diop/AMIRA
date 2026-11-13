"""Rangement des enregistrements du natif : chaque fichier relié à sa ligne gold (textes factices, pas de fulfulde)."""
import csv
import os

from tools.organize_audio import organize

HEAD = ["id", "kind", "section", "page", "fr", "en", "ff", "fr_variants", "en_variants", "ff_variants", "notes",
        "observed", "n_markers"]
GOLD = [
    ("g1", "glossaire", "deux", "two", "zwa", ""),
    ("g2", "ui", "bonjour", "hello", "alfa beta", "alfa betta"),
    ("g3", "message", "phrase", "sentence", "Gamma delta : {V1}. Epsi zeta ?", ""),
    ("g4", "message", "autre", "other", "Kappa {V1}. Epsi zeta ?", ""),
    ("g5", "ui", "mot", "word", "Omega", ""),
    ("g6", "glossaire", "mot", "word", "Omega", ""),
    ("g7", "message", "seuil", "limit", "Lambda mu {V1}.", ""),
    ("g8", "message", "valeur", "value", "Pqr stu {V1}. Vwx yz {V2} ?", ""),
    ("g9", "ui", "nom", "name", "{V1} kkk lll. Mmm nnn ooo.", ""),
]
AUDIO = ["alfa betta.m4a", "Gamma delta {} FCFA.m4a", "Epsi zeta.m4a", "Epsi zeta-1.m4a", "Omega.m4a", "Omega….m4a",
         "zwa zwa.m4a", "zwa inconnu.m4a", "Lambda mu 0 FCFA..m4a", "Rien du tout.m4a", "Lambda mu wxyz.m4a",
         "Pqr stu aaa bbb. Vwx yz ccc.m4a", "autre/alfa betta.m4a", "Ddd eee kkk lll.m4a", "Mmm nnn ooo.m4a"]


def run(tmp_path):
    gold = tmp_path / "gold.csv"
    with gold.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEAD)
        for i, kind, fr, en, ff, var in GOLD:
            w.writerow([i, kind, "", "1", fr, en, ff, "", "", var, "", "oui", "0"])
    src = tmp_path / "src"
    src.mkdir()
    for name in AUDIO:
        (src / name).parent.mkdir(exist_ok=True)
        (src / name).write_bytes(name.encode())
        if name.startswith("autre/"):  # réenregistrement : plus récent que les fichiers du dossier principal
            os.utime(src / name, (2_000_000_000, 2_000_000_000))
    out = tmp_path / "out"
    organize(src, gold, out)
    with (out / "index.csv").open(encoding="utf-8") as f:
        return out, {r["nom_origine"]: r for r in csv.DictReader(f)}


def test_chaque_audio_relie_a_sa_ligne_gold(tmp_path):
    out, idx = run(tmp_path)
    assert len(idx) == len(AUDIO) and all((out / r["fichier"]).read_bytes() == n.encode() for n, r in idx.items())
    # variante ff, phrase coupée (début), montant dit « {} FCFA » ou « 0 FCFA »
    assert (idx["alfa betta.m4a"]["ids"], idx["alfa betta.m4a"]["fichier"]) == ("g2", "interface/g2_alfa-betta_prise2.m4a")
    assert (idx["Gamma delta {} FCFA.m4a"]["ids"], idx["Gamma delta {} FCFA.m4a"]["partie"]) == ("g3", "p1")
    assert idx["Gamma delta {} FCFA.m4a"]["fichier"].startswith("messages/g3_p1_")
    assert (idx["Lambda mu 0 FCFA..m4a"]["ids"], idx["Lambda mu 0 FCFA..m4a"]["partie"]) == ("g7", "entier")


def test_morceau_commun_et_prises(tmp_path):
    _, idx = run(tmp_path)
    # fin commune à deux phrases, et sa deuxième prise
    assert idx["Epsi zeta.m4a"]["ids"] == "g3|g4" and idx["Epsi zeta.m4a"]["partie"] == "p2"
    assert idx["Epsi zeta-1.m4a"]["fichier"] == idx["Epsi zeta.m4a"]["fichier"].replace(".m4a", "_prise2.m4a")
    # même mot dans le glossaire et l'interface : rangé avec les mots ; « … » final = autre prise
    assert idx["Omega.m4a"]["fichier"] == "mots/commun_omega.m4a"
    assert idx["Omega….m4a"]["fichier"] == "mots/commun_omega_prise2.m4a"


def test_hors_gold(tmp_path):
    _, idx = run(tmp_path)
    assert idx["zwa zwa.m4a"]["fichier"] == "nombres/hors-gold_zwa-zwa.m4a"
    assert idx["zwa inconnu.m4a"]["rubrique"] == "nombres"  # au moins la moitié des mots sont des nombres
    assert (idx["Rien du tout.m4a"]["rubrique"], idx["Rien du tout.m4a"]["ids"]) == ("a_verifier", "")


def test_montant_dit_en_toutes_lettres_et_sous_dossiers(tmp_path):
    out, idx = run(tmp_path)
    # le natif dit un mot là où le gold a {V1} (ou plusieurs, une phrase entière)
    assert (idx["Lambda mu wxyz.m4a"]["ids"], idx["Lambda mu wxyz.m4a"]["partie"]) == ("g7", "entier")
    assert (idx["Pqr stu aaa bbb. Vwx yz ccc.m4a"]["ids"], idx["Pqr stu aaa bbb. Vwx yz ccc.m4a"]["partie"]) == ("g8", "entier")
    # le mot n'est pas un montant : « Rien du tout » reste à vérifier, et un mot collé au gold ne le remplace pas
    assert idx["Rien du tout.m4a"]["rubrique"] == "a_verifier"
    # sous-dossier lu ; même texte enregistré deux fois : l'enregistrement le plus récent est la première prise
    assert idx["alfa betta.m4a"]["fichier"] == "interface/g2_alfa-betta_prise2.m4a"  # le plus ancien
    assert idx["autre/alfa betta.m4a"]["fichier"] == "interface/g2_alfa-betta.m4a"
    assert (out / "interface/g2_alfa-betta.m4a").read_bytes() == b"autre/alfa betta.m4a"


def test_nom_dit_a_la_place_du_marqueur_en_debut_de_phrase(tmp_path):
    _, idx = run(tmp_path)
    # le natif dit le nom (masqué {V1} dans le gold) : début « Ddd eee kkk lll », fin « Mmm nnn ooo »
    assert (idx["Ddd eee kkk lll.m4a"]["ids"], idx["Ddd eee kkk lll.m4a"]["partie"]) == ("g9", "p1")
    assert (idx["Mmm nnn ooo.m4a"]["ids"], idx["Mmm nnn ooo.m4a"]["partie"]) == ("g9", "p2")
