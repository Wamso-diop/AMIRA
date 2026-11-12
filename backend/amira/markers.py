"""Marqueurs Amira : {N0} (valeur masquée), {B0}…{/B0} (balise interne), {E0} (élément atomique).

Même règle que le front (front/src/content/verify.ts) : même ensemble de marqueurs, chacun le même nombre
de fois, {B} bien imbriqués. Le serveur est plus strict : toute autre accolade doit aussi revenir intacte.
"""
import re
from collections import Counter

MARKER_RE = re.compile(r"\{/?[NBE]\d+\}")
TAG_RE = re.compile(r"\{(/?)B(\d+)\}")
N_RE = re.compile(r"\{N\d+\}")
V_RE = re.compile(r"\{V\d+\}")
BRACE_RE = re.compile(r"\{[^{}]*\}")


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
    """Règle du front, plus : les autres accolades (texte, {V1} oublié, accolade isolée) reviennent à l'identique."""
    return (
        same_markers(source, translated)
        and well_nested(translated)
        and Counter(BRACE_RE.findall(source)) == Counter(BRACE_RE.findall(translated))
        and source.count("{") == translated.count("{")
        and source.count("}") == translated.count("}")
    )


def canonicalize(masked: str) -> tuple[str, dict[str, str]]:
    """Renumérote les {N} dans l'ordre d'apparition, pour la clé de mémoire.
    Renvoie (texte canonique, table canonique → origine). Le front numérote déjà ainsi : identité."""
    to_canon: dict[str, str] = {}
    for m in N_RE.findall(masked):
        to_canon.setdefault(m, f"{{N{len(to_canon)}}}")
    canon = N_RE.sub(lambda m: to_canon[m.group()], masked)
    return canon, {c: o for o, c in to_canon.items()}


def restore(text: str, table: dict[str, str]) -> str:
    """Remet les numéros d'origine, en une seule passe (pas de collision {N0}↔{N1})."""
    return N_RE.sub(lambda m: table.get(m.group(), m.group()), text)


def model_view(masked: str) -> tuple[str, dict[str, str]]:
    """Le modèle n'a appris que {V1}, {V2}… : chaque marqueur distinct devient un {Vk}, dans l'ordre d'apparition.
    Renvoie (vue du modèle, table {Vk} → marqueur). Un {Vk} déjà présent dans le texte rendrait l'inverse ambigu."""
    if V_RE.search(masked):
        raise ValueError("marqueur {V} littéral dans le texte")
    to_v: dict[str, str] = {}
    for m in MARKER_RE.findall(masked):
        to_v.setdefault(m, f"{{V{len(to_v) + 1}}}")
    view = MARKER_RE.sub(lambda m: to_v[m.group()], masked)
    return view, {v: m for m, v in to_v.items()}


def from_model(text: str, table: dict[str, str]) -> str:
    """Inverse de model_view. Un {Vk} inconnu reste tel quel : markers_ok le refusera."""
    return V_RE.sub(lambda m: table.get(m.group(), m.group()), text)


def speakable(text: str) -> str:
    """Texte lisible à voix haute : marqueurs retirés (le front le fait déjà, par sécurité)."""
    return re.sub(r"\s+", " ", MARKER_RE.sub(" ", text)).strip()
