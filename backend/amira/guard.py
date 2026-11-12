"""Garde de confidentialité (P1). Le front masque montants, numéros, e-mails et noms ; le serveur refuse
tout segment où il en reste une trace, avant toute recherche, tout stockage, tout journal et tout moteur.

Limite connue : un nom propre que le front n'a pas masqué ne se reconnaît pas ici.
"""
import re
import unicodedata

# Marqueurs du front, numérotés par segment : jamais plus de 3 chiffres. Un {N699123456} cacherait un numéro.
FRONT_MARKER_RE = re.compile(r"\{/?[NBE]\d{1,3}\}")
CURRENCY_RE = re.compile(r"\b(?:f\s*cfa|cfa|xaf|xof|francs?)\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def check(text: str) -> bool:
    """True si le texte peut passer : ni chiffre, ni devise, ni e-mail hors des marqueurs.
    IBAN : il porte toujours des chiffres de contrôle, donc la règle des chiffres le refuse (tests dédiés)."""
    # NFKC : chiffres et lettres pleine chasse, ＠ ; puis on retire les caractères invisibles (« F », espace de largeur nulle, « CFA »)
    norm = unicodedata.normalize("NFKC", text)
    norm = "".join(c for c in norm if unicodedata.category(c) != "Cf")
    rest = FRONT_MARKER_RE.sub(" ", norm)
    # avant et après NFKC : NFKC change « Ⅻ » en lettres « XII »
    chars = FRONT_MARKER_RE.sub(" ", text) + rest
    # Nd, No, Nl : tous les chiffres Unicode (arabes orientaux, exposants, fractions, chiffres romains) ; Sc : €, $, £, ₦…
    if any(unicodedata.category(c) in ("Nd", "No", "Nl", "Sc") for c in chars):
        return False
    return not (CURRENCY_RE.search(rest) or EMAIL_RE.search(rest))
