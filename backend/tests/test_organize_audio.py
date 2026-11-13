"""Rangement des enregistrements du natif : chaque fichier relié à sa ligne gold (textes factices, pas de fulfulde)."""
import csv

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
]
AUDIO = ["alfa betta.m4a", "Gamma delta {} FCFA.m4a", "Epsi zeta.m4a", "Epsi zeta-1.m4a", "Omega.m4a", "Omega….m4a",
         "zwa zwa.m4a", "zwa inconnu.m4a", "Lambda mu 0 FCFA..m4a", "Rien du tout.m4a"]


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
        (src / name).write_bytes(name.encode())
    out = tmp_path / "out"
    organize(src, gold, out)
    with (out / "index.csv").open(encoding="utf-8") as f:
        return out, {r["nom_origine"]: r for r in csv.DictReader(f)}


def test_chaque_audio_relie_a_sa_ligne_gold(tmp_path):
    out, idx = run(tmp_path)
    assert len(idx) == len(AUDIO) and all((out / r["fichier"]).read_bytes() == n.encode() for n, r in idx.items())
    # variante ff, phrase coupée (début), montant dit « {} FCFA » ou « 0 FCFA »
    assert (idx["alfa betta.m4a"]["ids"], idx["alfa betta.m4a"]["fichier"]) == ("g2", "interface/g2_alfa-betta.m4a")
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
