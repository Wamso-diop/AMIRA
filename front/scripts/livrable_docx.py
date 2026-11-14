#!/usr/bin/env python3
"""Génère livrable/Amira-Dossier-de-candidature.docx : le document remis au jury de l'épreuve SAFINUM.

Aucune bibliothèque externe : le fichier Word (OpenXML) est écrit directement.
Usage (depuis front/) : node scripts/livrable-figures.mjs && python3 scripts/livrable_docx.py
Charte Amira : aubergine #481C4B, rose #E01D5B, jaune #EFD109, vert #2DCF42, bleu #2BB1EB ; Inter Tight (titres), Noto Sans (texte) ;
formes à coins coupés, ni ombres ni dégradés.
"""
import re
import struct
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

FRONT = Path(__file__).resolve().parents[1]
OUT = FRONT.parent / "livrable" / "Amira-Dossier-de-candidature.docx"
FIG = FRONT / "docs" / "figures"
ASSETS = FRONT / "src" / "assets"

AUB, ROSE, ROSE_T, JAUNE, VERT, BLEU, DOUX, CLAIR = "481C4B", "E01D5B", "C2134C", "EFD109", "2DCF42", "2BB1EB", "F7F2F7", "FBF3FA"
HEAD, BODY, MONO = "Inter Tight", "Noto Sans", "Consolas"
TEXT_W = 9638  # largeur utile en twips : A4 (11906) moins deux marges de 1134

body: list[str] = []
images: list[tuple[str, Path]] = []  # (rId, chemin)
nums: list[int] = []  # listes numérotées : une instance par liste, pour repartir de 1


def x(s: str) -> str:
    return escape(s, {'"': "&quot;"})


def rpr(bold=False, italic=False, code=False, color=None, size=None, font=None, fill=None) -> str:
    p = ""
    if font or code:
        f = font or MONO
        p += f'<w:rFonts w:ascii="{f}" w:hAnsi="{f}" w:cs="{f}"/>'
    if bold:
        p += "<w:b/>"
    if italic:
        p += "<w:i/>"
    if color:
        p += f'<w:color w:val="{color}"/>'
    if size:
        p += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    if fill or code:
        p += f'<w:shd w:val="clear" w:color="auto" w:fill="{fill or DOUX}"/>'
    return f"<w:rPr>{p}</w:rPr>" if p else ""


def runs(text: str, size=None, color=None, bold=False, font=None) -> str:
    """Mini-balisage : **gras**, `code`, *italique*."""
    out = []
    for tok in re.split(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)", text):
        if not tok:
            continue
        if tok.startswith("**"):
            t, kw = tok[2:-2], dict(bold=True)
        elif tok.startswith("`"):
            t, kw = tok[1:-1], dict(code=True, size=(size - 2 if size else 18))
        elif tok.startswith("*") and len(tok) > 2:
            t, kw = tok[1:-1], dict(italic=True)
        else:
            t, kw = tok, {}
        kw.setdefault("size", size)
        kw["color"] = color
        kw["bold"] = kw.get("bold", bold)
        kw["font"] = font if not kw.get("code") else None
        out.append(f'<w:r>{rpr(**kw)}<w:t xml:space="preserve">{x(t)}</w:t></w:r>')
    return "".join(out)


def para(text="", style=None, extra="", **kw) -> str:
    ppr = (f'<w:pStyle w:val="{style}"/>' if style else "") + extra
    return f'<w:p>{"<w:pPr>" + ppr + "</w:pPr>" if ppr else ""}{runs(text, **kw)}</w:p>'


def H1(t, n=None):
    """Titre de section : bandeau illustré (figure) puis le titre lui-même, pour garder le plan de navigation de Word."""
    if n:
        body.append(f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="360" w:after="60"/></w:pPr><w:r>{drawing(FIG / f"banner-{n}.png", 17.0, f"Section {n} sur 7")}</w:r></w:p>')
    body.append(para(t, "Heading1"))
def H2(t): body.append(para(t, "Heading2"))
def H3(t): body.append(para(t, "Heading3"))
def P(t): body.append(para(t))
def CALL(t): body.append(para(t, "Callout"))


def CODE(t: str):
    for line in t.strip("\n").split("\n"):
        body.append(f'<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr><w:r><w:t xml:space="preserve">{x(line) or " "}</w:t></w:r></w:p>')
    body.append('<w:p><w:pPr><w:spacing w:after="60" w:line="40" w:lineRule="exact"/></w:pPr></w:p>')


def B(items):
    for it in items:
        body.append(para(it, "ListParagraph", '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'))


def N(items):
    nid = 10 + len(nums)
    nums.append(nid)
    for it in items:
        body.append(para(it, "ListParagraph", f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{nid}"/></w:numPr>'))


def png_size(p: Path):
    return struct.unpack(">II", p.read_bytes()[16:24])


def drawing(path: Path, width_cm: float, alt: str, full_page: bool = False) -> str:
    rid = f"rIdImg{len(images) + 1}"
    images.append((rid, path))
    w, h = png_size(path)
    cx = int(width_cm * 360000)
    cy = int(cx * h / w)
    if full_page:  # A4 : 21 x 29,7 cm ; on garde 0,1 cm de marge pour ne pas créer une page blanche
        cx, cy = int(21.0 * 360000), int(29.55 * 360000)
    n = len(images)
    return (f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{n}" name="Image {n}" descr="{x(alt)}"/><wp:cNvGraphicFramePr/>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{n}" name="Image {n}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            '</a:graphicData></a:graphic></wp:inline></w:drawing>')


def IMG(path: Path, width_cm: float, alt: str, caption: str | None = None):
    keep = "<w:keepNext/>" if caption else ""  # légende : on garde figure et légende ensemble ; sinon la figure peut finir la page
    body.append(f'<w:p><w:pPr>{keep}<w:spacing w:before="100" w:after="60"/><w:jc w:val="center"/></w:pPr><w:r>{drawing(path, width_cm, alt)}</w:r></w:p>')
    if caption:
        body.append(para(caption, "Caption"))


def cell(text: str, w: int, head=False, fill=None, last=False) -> str:
    shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{AUB if head else fill}"/>' if (head or fill) else ""
    paras = text.split("\n")
    inner = "".join(para(t, "TableText", "", size=17, color=CLAIR if head else None, bold=head, font=HEAD if head else None) for t in paras)
    return f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shd}</w:tcPr>{inner}</w:tc>'


def T(headers, rows, widths):
    tot = sum(widths)
    cw = [round(TEXT_W * w / tot) for w in widths]
    cw[-1] += TEXT_W - sum(cw)
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in cw)
    tbl = (f'<w:tbl><w:tblPr><w:tblW w:w="{TEXT_W}" w:type="dxa"/>'
           f'<w:tblBorders><w:top w:val="single" w:sz="6" w:space="0" w:color="{AUB}"/><w:bottom w:val="single" w:sz="6" w:space="0" w:color="{AUB}"/>'
           '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="D9C9DA"/></w:tblBorders><w:tblLayout w:type="fixed"/>'
           '<w:tblCellMar><w:top w:w="55" w:type="dxa"/><w:left w:w="90" w:type="dxa"/><w:bottom w:w="55" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar></w:tblPr>'
           f"<w:tblGrid>{grid}</w:tblGrid>")
    tbl += '<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>' + "".join(cell(h, w, head=True) for h, w in zip(headers, cw)) + "</w:tr>"
    for i, r in enumerate(rows):
        tbl += '<w:tr><w:trPr><w:cantSplit/></w:trPr>' + "".join(cell(c, w, fill=DOUX if i % 2 else None) for c, w in zip(r, cw)) + "</w:tr>"
    body.append(tbl + "</w:tbl>")
    body.append('<w:p><w:pPr><w:spacing w:after="80" w:line="60" w:lineRule="exact"/></w:pPr></w:p>')


# ----------------------------------------------------------------------------------------------------------------------
# Couverture (pleine page, section sans marges) puis corps du document
# ----------------------------------------------------------------------------------------------------------------------
def cover():
    """Couverture : image pleine page (figure dessinée dans la charte), dans une section sans marges."""
    body.append(f'<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r>{drawing(FIG / "cover.png", 21.0, "Couverture : Dossier de candidature Amira", full_page=True)}</w:r></w:p>')
    body.append('<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/><w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="0" w:right="0" w:bottom="0" w:left="0" w:header="0" w:footer="0" w:gutter="0"/></w:sectPr></w:pPr></w:p>')


cover()

# ---- Sommaire -------------------------------------------------------------------------------------------------------
body.append(para("Sommaire", "Heading2"))
T(["", "Section", "Ce qu'on y trouve"], [
    ["1", "**Description de la solution**", "Le problème, la réponse d'Amira, ce que le jury peut vérifier"],
    ["2", "**Prototype et démonstration reproductible**", "Lancer, installer, parcours de test, contenu inédit"],
    ["3", "**Note technique**", "Architecture, intégration, API, sécurité, performances, limites"],
    ["4", "**Langues et validation linguistique**", "Langue prise en charge, méthode de validation"],
    ["5", "**Composants et licences**", "Contribution propre, composants tiers, modèle, licences"],
    ["6", "**Configuration, intégration et exploitation**", "Configuration, intégration finale, ajout d'une langue"],
    ["7", "**Passage à l'échelle**", "Nouvelles langues, limites et réponses"],
], [5, 38, 57])

# ---- 1. Description -------------------------------------------------------------------------------------------------
H1("1. Description de la solution", 1)
H2("Notre réponse : Amira")
P("**Amira** est une extension de navigateur (Chrome) accompagnée d'un serveur de traduction indépendant. Elle lit la page déjà affichée par le service financier "
  "et la rend compréhensible en **fulfulde** (variété de l'Adamaoua), à l'écrit et à l'oral. Le sens inverse (fulfulde vers français ou anglais) fonctionne aussi.")
IMG(FIG / "hero.png", 17.0, "La même page bancaire avant et après un clic sur Traduire : les libellés passent en fulfulde, les montants ne changent pas", "Captures réelles : l'extension Amira traduit une page de démonstration reconstituée avec des libellés de l'environnement de test.")
H2("Le problème")
P("Les applications bancaires, les plateformes de paiement et les services de microfinance sont presque toujours proposés en français ou en anglais. "
  "Une personne qui maîtrise peu ces langues peut lire un montant, mais pas toujours comprendre les frais, une condition, un message d'erreur ou un avertissement de sécurité. "
  "Refaire chaque service dans chaque langue nationale est long et coûteux : il faut une technologie qui **s'adapte aux services existants, sans modifier leur code**.")
H2("Comment ça marche")
N(["**Amira découpe la page** en passages (une phrase, un libellé, un bouton) sans casser la mise en page.",
   "**Elle masque les valeurs sensibles sur l'ordinateur** : montants, devises, numéros, dates, e-mails, références, IBAN et noms deviennent des marqueurs (`{N0}`, `{N1}`…). Seul le texte masqué quitte la page.",
   "**Le serveur répond dans cet ordre** : une garde refuse tout texte qui contiendrait encore une valeur sensible, puis la **mémoire validée par un locuteur natif**, puis, seulement si rien n'est connu, le **modèle de traduction** sous contrôle.",
   "**Amira vérifie le résultat** : chaque marqueur doit être présent, une seule fois. Sinon, **le texte d'origine reste affiché**.",
   "**Elle remet les vraies valeurs à leur place** et affiche la traduction avec un badge qui dit d'où elle vient (validée, automatique, à vérifier)."])
IMG(FIG / "gestes.png", 13.0, "Le panneau Amira en quatre gestes : traduire, écouter, savoir à qui se fier, lire les erreurs", "Le panneau Amira en quatre gestes (captures réelles).")
H2("Ce que le jury peut vérifier")
T(["Fonctionnalité demandée", "Ce qu'Amira montre"], [
    ["Adaptation linguistique de l'interface", "Un clic sur **Traduire** : textes, instructions et messages passent en fulfulde, sur place, sans recharger."],
    ["Parcours financier", "Consultation du solde et des frais, préparation d'un transfert, lecture du récapitulatif."],
    ["Préservation des informations financières", "Montants, frais, bénéficiaires, conditions et avertissements gardent leur exactitude ; frais et avertissements de sécurité ne s'affichent traduits que dans leur **version validée**."],
    ["Fonctionnement indépendant", "Aucune ligne du service n'est modifiée : Amira agit par-dessus la page, sur l'environnement de test fourni."],
    ["Contenu inédit", "Un nouveau message qui apparaît pendant la démonstration est repéré, traduit ou, en cas de doute, laissé en original."],
], [30, 70])
H2("Ce qui rend Amira différente")
B(["**Elle fonctionne sur le service tel qu'il est** : aucune intégration à demander à la banque.",
   "**Un montant ne passe jamais par la traduction** : masquage local non désactivable, double garde sur le serveur.",
   "**Elle préfère ne pas traduire que mal traduire** : au moindre doute, l'original reste affiché.",
   "**La qualité linguistique repose sur des personnes** : aucun mot de fulfulde n'est écrit ni deviné par notre code ; tout vient d'un fichier relu par un locuteur natif.",
   "**Elle parle** : voix de locuteurs natifs, étiquetées ; lecture automatique des erreurs ; badges de fiabilité lisibles sans les couleurs ; taille du texte, contraste et clavier réglables.",
   "**Elle s'installe chez la banque** : Flask et SQLite, aucun service externe. **Une langue de plus, c'est un dossier de plus.**"])
H2("Chiffres clés")
IMG(FIG / "chiffres.png", 17.0, "Chiffres clés : 189 lignes validées, 183 avec voix, 539 tests, 6,2 s au p95, 0 connexion sortante")
CALL("**Lecture honnête.** La mémoire validée couvre l'environnement de test. Pour tout texte inconnu, le modèle traduit sous contrôle et marque le résultat « automatique » : sa qualité n'est pas celle d'un locuteur natif.")

# ---- 2. Prototype ---------------------------------------------------------------------------------------------------
H1("2. Prototype et démonstration reproductible", 2)
H2("2.1 Prérequis")
T(["Élément", "Version", "Remarque"], [
    ["Google Chrome ou Chromium", "116 ou plus récent", "Le panneau latéral l'exige ; autres navigateurs non testés"],
    ["Python", "3.10 ou plus récent", "Seulement pour le serveur, facultatif (pas de Node.js)"],
    ["Internet", "—", "Seulement pour installer Flask la première fois et ouvrir la page de test ; le serveur Amira n'appelle rien vers l'extérieur"],
], [28, 22, 50])
H2("2.2 Lancer le serveur (une commande, facultatif)")
P("L'extension **agit seule** : sa mémoire validée et 130 voix de natifs sont dans le paquet (section 2.3). Le serveur est un renfort : il traduit en plus ce que la mémoire ne connaît pas (modèle).")
CODE("cd backend\npython demo.py          # Windows : py demo.py")
B(["La première fois, le script crée son environnement et installe Flask (quelques secondes). Il charge la mémoire validée et les voix, puis affiche `Amira (ff) prête sur http://127.0.0.1:5000`.",
   "**Il ouvre aussitôt un guide animé dans le navigateur** (`http://127.0.0.1:5000/guide/`) qui montre les étapes suivantes. Sans écran : `python demo.py --no-browser`."])
H2("2.3 Installer l'extension dans Chrome")
N(["Ouvrir `chrome://extensions` et activer **Mode développeur**.",
   "Cliquer sur **Charger l'extension non empaquetée** et choisir le dossier `extension/` du projet, ou le contenu de `Amira-Extension.zip` une fois extrait (7,2 Mo compressé, 9,3 Mo déplié). Rien à compiler.",
   "Épingler Amira (icône puzzle, puis punaise).",
   "**Sans serveur**, la pastille indique « Prêt · autonome » : la page est traduite par la mémoire validée et lue avec la voix des natifs. Avec le serveur lancé, elle indique « Prêt »."])
H2("2.4 Parcours de test")
P("Ouvrir https://safinum.cm/hackathon-test puis cliquer sur l'icône Amira : **la pastille doit indiquer « Prêt »**. Cliquer sur **Traduire**.")
T(["Étape du parcours de l'épreuve", "Ce qu'on observe"], [
    ["Consultation d'un solde", "Libellés en fulfulde ; **le montant reste identique, chiffre pour chiffre**."],
    ["Consultation des frais", "Libellés de frais traduits seulement s'ils sont **validés par un natif** ; sinon l'original reste, avec une marque."],
    ["Préparation d'un transfert", "Champs et consignes traduits. **Amira ne clique, ne remplit et ne soumet rien.**"],
    ["Récapitulatif avant confirmation", "Total, bénéficiaire et conditions exacts. **Voir l'original** rétablit la page en un clic."],
    ["Erreur ou avertissement de sécurité", "Erreurs connues traduites et **lues automatiquement** (voix d'un natif) ; avertissement de sécurité affiché traduit dans sa version validée seulement."],
    ["Contenu inédit", "Voir ci-dessous."],
], [32, 68])
H3("Introduire un contenu inédit")
P("Dans la console du navigateur (F12), ou dans le panneau (onglet **Traduire**, zone « Traducteur rapide ») :")
CODE("document.body.insertAdjacentHTML('beforeend',\n  '<p role=\"alert\">Votre demande est en cours de traitement.</p>');")
P("Le message est repéré dès qu'il apparaît, envoyé **masqué**, puis traduit par le modèle (badge « automatique ») ou laissé en original (badge « à vérifier ») si la confiance est trop faible. "
  "Un avertissement de sécurité ou des frais **absents de la mémoire validée** ne sont pas traduits par le modèle : l'original reste jusqu'à validation par un locuteur natif. **Sans serveur (mode autonome), il n'y a pas de modèle : tout texte absent de la mémoire reste en original.**")
IMG(FIG / "erreur.png", 17.0, "Une erreur apparaît sur la page : Amira la traduit puis la lit avec la voix d'un locuteur natif", "Capture réelle : une erreur apparue après coup est traduite, puis lue (voix enregistrée, lecture automatique active par défaut).")
H2("2.5 Avec le modèle de traduction (facultatif, hors dépôt)")
P("Sans le modèle, Amira sert la **mémoire validée seule** (mode le plus sûr, celui de la démonstration par défaut). Pour activer le modèle (environ 1,9 Go) :")
N(["Depuis `backend/` : `.venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 && .venv/bin/pip install -r requirements.txt -c constraints.txt`.",
   "Placer les 7 fichiers du modèle dans `backend/models/m2m_ff/` (liste et empreinte SHA-256 : `backend/docs/MODEL.md`) ; vérifier avec `sha256sum models/m2m_ff/model.safetensors`.",
   "Relancer `python demo.py` : le message de démarrage indique « modèle M2M100 + mémoire validée »."])
H2("2.6 Reproduire les tests")
T(["Ce qu'on vérifie", "Commande", "Résultat attendu"], [
    ["Serveur", "`cd backend && .venv/bin/pytest`", "435 tests verts"],
    ["Serveur, vrai modèle", "`.venv/bin/pytest -m model`", "11 tests verts"],
    ["Extension, unitaires", "`cd front && npm install && npm test`", "69 tests verts"],
    ["Extension, navigateur réel", "`npm run test:e2e`", "8 tests verts (six types de pages, panne du serveur, changement de langue)"],
    ["Parcours complet", "`bash backend/tools/e2e_extension.sh`", "pastille, page traduite, texte inédit, erreurs lues, 0 connexion sortante"],
], [24, 40, 36])

# ---- 3. Note technique ----------------------------------------------------------------------------------------------
H1("3. Note technique", 3)
H2("3.1 Principes de conception")
B(["**Fonctionner sans modifier le service** : Amira agit sur la page affichée, pas sur son code.",
   "**Masquer avant d'envoyer** : aucune valeur financière ne quitte la page.",
   "**Valider avant de traduire** : la mémoire d'un locuteur natif passe avant le modèle.",
   "**Préférer l'original au doute** : marqueur perdu, statut incertain, erreur réseau, l'original reste affiché.",
   "**Aucun service externe** : le serveur est autonome.   **Une langue = un dossier.**"])
H2("3.2 Architecture")
IMG(FIG / "architecture.png", 16.4, "Schéma d'architecture : page du service, extension Amira (script de contenu, panneau, service worker) et API Amira")
T(["Composant", "Rôle", "Emplacement"], [
    ["Script de contenu", "Découpe la page, masque, applique et vérifie les traductions, observe les nouveaux textes", "`front/src/content/`"],
    ["Panneau latéral", "Traduire, écouter, régler, consulter le journal et signaler", "`front/src/panel/`"],
    ["Service worker", "Cache local, nouvelles tentatives, appels à l'API, journal sans données", "`front/src/background/`"],
    ["API Amira", "Garde, mémoire validée, moteur de traduction, voix, signalements", "`backend/amira/`"],
    ["Une langue", "Fiche, mémoire validée, enregistrements des natifs", "`backend/languages/<code>/`"],
], [20, 52, 28])
P("Extension : **Manifest V3** (React 18, TypeScript, Vite). Serveur : **Flask** et **SQLite**. Moteur : **M2M100** (CPU).")
H2("3.3 Le trajet d'un texte")
IMG(FIG / "masquage.png", 16.4, "Trajet d'un texte : masqué sur l'ordinateur, traduit par le serveur, vérifié, valeurs remises")
IMG(FIG / "pipeline.png", 17.0, "Les six étapes de décision du serveur pour chaque passage")
IMG(FIG / "statuts.png", 17.0, "Trois statuts de fiabilité, de formes différentes : validée (cercle), automatique (losange), à vérifier (triangle)")
H2("3.4 Modalités d'intégration")
B(["**A. Extension de navigateur, sans intégration côté service (prototype).** Le service ne reçoit ni script, ni balise, ni modification. **L'extension agit seule** : mémoire validée et voix des natifs sont dans le paquet (moins de 10 Mo). Si une adresse de serveur est fixée à sa construction, elle ne le consulte que pour ce que la mémoire ne connaît pas ; elle ne contacte rien d'autre.",
   "**B. Déploiement chez l'opérateur.** Serveur Amira dans le réseau interne, sans accès à Internet, derrière une passerelle (TLS, authentification, quotas) ; supervision par `/v1/health` et `/v1/ready`. En production, `AMIRA_ALLOWED_ORIGINS` est obligatoire.",
   "**C. Appel de serveur à serveur.** Un serveur de l'opérateur appelle l'API en appliquant les **mêmes règles de masquage** que l'extension ; si `AMIRA_API_KEYS` est défini, l'en-tête `X-Amira-Key` est exigé."])
IMG(FIG / "deploiement.png", 17.0, "Déploiement chez un opérateur : utilisateur, passerelle, serveur Amira en réseau interne")
P("**Ce que le service cible doit fournir : rien.** Amira a été testée sur des pages simples, une application d'une seule page, une fenêtre modale, une notification éphémère, une iframe avec shadow DOM et un site qui change de langue.")
H2("3.5 Contrat d'API")
T(["Point d'accès", "Rôle"], [
    ["`GET /v1/health`, `GET /v1/ready`", "Le service vit ; prêt quand le modèle et la base sont chargés (503 avant)"],
    ["`GET /v1/capabilities`", "Langues, variétés, voix disponibles"],
    ["`POST /v1/translate`", "Traduit 1 à 40 passages masqués (1 000 caractères au plus chacun) : `status`, `confidence`, `origin` pour chacun"],
    ["`POST /v1/tts`", "Voix d'un passage : enregistrement d'un natif (`audio/mp4`) ou `204` s'il n'y en a pas"],
    ["`POST /v1/feedback`", "Signalement d'une traduction avec correction proposée (masquée)"],
    ["`/v1/admin/*`", "Outils des locuteurs natifs (jeton obligatoire, écritures auditées)"],
], [34, 66])
P("Sens autorisés : `fr>ff`, `en>ff`, `ff>fr`, `ff>en` ; jamais `fr>en`. Contrat complet : `backend/docs/openapi.yaml`, vérifié par les tests.")
H2("3.6 Sécurité et préservation des informations financières")
T(["Risque", "Mesure"], [
    ["Fuite d'une valeur financière", "Masquage local non désactivable, puis garde du serveur (chiffres Unicode, devises, e-mails, IBAN)"],
    ["Montant ou condition altérés", "Marqueurs vérifiés sur le serveur puis sur la page ; sinon original conservé"],
    ["Avertissement de sécurité ou frais mal traduits", "Jamais traduits par le modèle : version validée seulement"],
    ["Texte conservé dans les journaux", "Journaux sans texte (méthode, chemin, code, durée, compteurs) ; signalements et textes non reconnus purgés après 90 jours"],
    ["Appel sortant du serveur", "Aucun : test avec connexions sortantes interdites, et 0 connexion mesurée sur le parcours complet"],
    ["Abus de l'API", "Limite de débit (600 requêtes par minute et par adresse), clés d'API, origines autorisées, tailles limitées"],
    ["Accès aux outils des natifs", "Jeton `Bearer`, réseau interne seulement, audit de chaque écriture"],
    ["Lecture de ce que fait l'utilisateur", "Amira ne lit ni cookies, ni jetons, ni saisies ; elle ne clique, ne remplit et ne soumet rien"],
    ["Permissions de l'extension", "`sidePanel`, `storage`, `scripting`, `activeTab` ; sites : `safinum.cm` et le serveur ; autres sites demandés à l'utilisateur, une fois"],
], [30, 70])
H2("3.7 Performances mesurées")
P("Machine : Intel Core i7-6820HQ (4 cœurs), 15,8 Go de RAM, **processeur seul**. Requêtes complètes, cache vide, 10 essais.")
IMG(FIG / "perf.png", 17.0, "Durées médianes et p95 par scénario, avec le budget du serveur (6 s) et la limite du front (8 s)")
P("Les textes **connus** sont servis en quelques millisecondes. Le moteur traite ce qui tient dans le budget de 6 s ; le reste revient `uncertain`, et les visites suivantes complètent grâce au cache. Mémoire vive avec le modèle : environ 2,7 Go au maximum. Le front coupe à 8 s : le p95 reste en dessous.")
H2("3.8 Limites connues")
B(["**Navigateurs** : testé sur Chrome et Chromium ; tests de bout en bout sous Linux seulement.",
   "**Qualité du modèle** : il n'est pas un locuteur natif. Sur 56 phrases de référence, 17 (30,4 %) sont identiques à la référence humaine après normalisation de la casse et de la ponctuation finale ; ses sorties restent donc marquées « automatique ». Les seuils de confiance (0,5 vers le fulfulde, 0,7 depuis le fulfulde) ne sont pas calibrés avec un natif.",
   "**Textes sensibles inédits** : un avertissement de sécurité ou des frais absents de la mémoire restent en original (choix de sécurité).",
   "**Noms propres** : le serveur ne peut pas reconnaître un nom que l'extension n'a pas masqué.",
   "**Débit du moteur** : sur processeur seul, environ 4 à 8 passages inconnus par requête ; les pages riches se complètent sur plusieurs visites.",
   "**Voix** : les navigateurs n'ont pas de voix fulfulde ; 6 lignes de la mémoire sur 189 n'ont pas encore d'enregistrement. Le paquet autonome embarque 130 passages (en priorité les messages d'erreur et d'avertissement) pour tenir dans 10 Mo ; le serveur, lui, sert toutes les voix.",
   "**Mode autonome** : sans serveur, pas de modèle ; un texte inconnu reste en original, et le signalement d'une traduction exige un serveur.",
   "**Interface** : le panneau est en français et en anglais ; texte dessiné dans des images non traduit ; dictée vocale prévue mais désactivée."])

# ---- 4. Langues et validation ---------------------------------------------------------------------------------------
H1("4. Langues prises en charge et validation linguistique", 4)
H2("4.1 Langue prise en charge")
T(["Élément", "Valeur"], [
    ["Langue nationale", "**Fulfulde** (code `ff`)"],
    ["Variété", "Fulfulde de l'**Adamaoua** (Ngaoundéré) ; les fiches prévoient aussi Garoua et Maroua"],
    ["Sens de traduction", "français → fulfulde, anglais → fulfulde, **fulfulde → français, fulfulde → anglais**"],
    ["Détection", "Langue de la page détectée automatiquement (fulfulde reconnu à ses lettres propres ɓ ɗ ƴ ŋ)"],
    ["Voix", "Enregistrements de locuteurs natifs, phrase par phrase"],
], [26, 74])
P("**Aucun mot de fulfulde n'est écrit, généré ni deviné par notre code.** Tout vient d'un fichier relu par un locuteur natif ; un test automatique vérifie qu'aucun texte fulfulde n'est codé en dur.")
H2("4.2 Méthode de validation")
T(["Source", "Nature", "Statut"], [
    ["**Mémoire validée** (`gold.csv`)", "189 lignes associant français, anglais et fulfulde ; 81 lignes lues sur la page de test, les autres anticipent d'autres écrans", "Écrite et relue par un **locuteur natif de l'équipe** ; seule source dite **validée**"],
    ["**Voix des natifs**", "183 lignes sur 189 ont un enregistrement", "Voix du locuteur natif, jouée telle quelle"],
    ["**Modèle de traduction**", "M2M100 affiné pour le fulfulde, pour les textes que la mémoire ne connaît pas", "**Automatique** : jamais présenté comme validé"],
], [24, 46, 30])
IMG(FIG / "validation.png", 17.0, "Circuit de validation : texte connu, inconnu courant, inconnu sensible, validation par le locuteur natif, boucle de signalement")
P("**En pratique.** Le serveur tient deux listes de travail pour les natifs : textes sensibles demandés sans traduction, passages à enregistrer. Toute écriture est inscrite dans un journal d'audit.")
T(["Ce qui ne doit jamais changer", "Mesure"], [
    ["Un **montant**, une devise, un numéro, une date", "Jamais traduits : masqués puis remis à l'identique ; une ligne de mémoire qui traduirait un nombre est refusée à l'import"],
    ["Une **condition** ou un frais", "Version validée seulement"],
    ["Un **avertissement de sécurité**", "Version validée seulement ; sinon l'original reste"],
    ["Le **bénéficiaire** (nom, numéro)", "Valeurs masquées puis remises ; le serveur ne les voit jamais"],
    ["Le **sens général**", "Un marqueur perdu, ajouté ou dupliqué par le modèle fait garder l'original"],
], [36, 64])
H2("4.3 Exemples de lignes validées")
T(["Français", "Fulfulde validé"], [
    ["Votre compte", "Siggorɗe maaɗa"],
    ["Solde disponible", "Ceede ɗe a mari jonta"],
    ["Effectuer un transfert", "Neldugo ceede"],
    ["Transfert impossible pour le moment. Veuillez réessayer plus tard.", "Neldol fotay jonta. Fuɗɗutu fahin ɓaawo."],
    ["Alerte de sécurité : vérifiez le numéro du bénéficiaire avant de continuer.", "Hakkiil jam : laarta limgal jaɓɓoowo hideko tokkitinugo."],
], [50, 50])
H2("4.4 Ce que nous ne prétendons pas")
B(["**La traduction automatique n'est pas de la traduction native** : elle est toujours marquée et ne traduit jamais un avertissement de sécurité ni des frais.",
   "**La couverture validée est celle de l'environnement de test** et d'écrans anticipés ; tout autre texte dépend du modèle.",
   "**Une seconde relecture indépendante** (idéalement d'une autre variété) est la première amélioration à apporter."])
H2("4.5 Protocole de vérification pour des personnes compétentes")
N(["Relire la mémoire : `backend/languages/ff/gold.csv` (colonnes `fr`, `en`, `ff`, variantes, écran d'origine).",
   "Contrôler en priorité les lignes de type `message` (erreurs, avertissements) et les libellés de frais et de sécurité.",
   "Tester en direct : cliquer sur Traduire et comparer chaque libellé au fichier ; les badges disent la source.",
   "Introduire un contenu inédit (section 2.4) : le résultat doit être marqué « automatique » ou laissé en original.",
   "Signaler un défaut depuis l'onglet Journal : il est inscrit pour validation, sans texte réel."])

# ---- 5. Composants et licences --------------------------------------------------------------------------------------
H1("5. Déclaration des composants et licences", 5)
H2("5.1 Notre contribution technique propre")
T(["Réalisation", "Description"], [
    ["**Moteur de masquage**", "Reconnaît montants, devises, numéros, dates, e-mails, références, IBAN et noms ; marqueurs numérotés ; restitution des valeurs"],
    ["**Découpage et observation de page**", "Passages cohérents malgré les balises imbriquées ; pages simples, application d'une seule page, modales, iframes, shadow DOM ; repère les textes apparus après le chargement"],
    ["**Vérification**", "Contrôle des marqueurs, balises, statuts et seuils ; retour à l'original au moindre doute"],
    ["**Garde et chaîne de décision du serveur**", "Refus de toute trace de valeur sensible ; garde, mémoire validée, catégories sensibles, cache, moteur contrôlé, incertain"],
    ["**Mémoire validée et voix**", "Format du fichier de mémoire, import avec refus argumentés, rechargement à chaud ; pipeline des enregistrements et clé stable par passage"],
    ["**Panneau, API et architecture**", "Panneau latéral accessible, contrat d'API vérifié par les tests, « une langue = un dossier », guide d'installation animé"],
    ["**Affinage du modèle**", "Adaptation de M2M100 au fulfulde de l'Adamaoua en deux étapes (hors dépôt)"],
], [30, 70])
P("Ordre de grandeur : environ 5 400 lignes pour l'extension, 2 000 pour le serveur et ses outils, 3 700 de tests.")
H2("5.2 Composants tiers")
T(["Composant", "Version", "Licence", "Usage"], [
    ["React, React DOM", "18.3.1", "MIT", "Interface du panneau"],
    ["Inter Tight, Noto Sans (@fontsource)", "5.3.0", "SIL OFL 1.1", "Polices, embarquées (aucun CDN)"],
    ["Flask (Werkzeug, Jinja2, click…)", "3.1.3", "BSD-3-Clause", "Serveur web"],
    ["gunicorn", "27.0.0", "MIT", "Service durable"],
    ["python-dotenv", "1.2.4", "BSD-3-Clause", "Configuration"],
    ["SQLite", "bibliothèque standard de Python", "domaine public", "Base de données"],
    ["Transformers (tokenizers, safetensors, huggingface_hub)", "5.22.2", "Apache-2.0", "Exécution du modèle (hors ligne)"],
    ["sentencepiece", "0.2.3", "Apache-2.0", "Tokenizer de M2M100"],
    ["PyTorch (CPU), NumPy", "2.15.0 ; 2.5.4", "BSD-3-Clause", "Calcul du modèle"],
], [34, 18, 18, 30])
P("Outils de développement et de test, non livrés en production : Vite, TypeScript, Vitest, Playwright, sharp (MIT ou Apache-2.0) ; pytest, PyYAML, jsonschema (MIT) ; pip-audit (Apache-2.0). "
  "Versions exactes : `backend/requirements.txt`, `backend/constraints.txt`, `front/package.json` ; relevés : `backend/LICENSES.md`.")
H2("5.3 Modèle de traduction et données")
T(["Élément", "Origine", "Licence"], [
    ["**Modèle livré : M2M100, version 418M**, affiné pour le fulfulde", "Modèle de base publié par Meta (`huggingface.co/facebook/m2m100_418M`) ; affinage par l'équipe", "**MIT, vérifiée**"],
    ["Affinage, étape 1", "Jeu de données `FredMike23/french-FULFULDE-ADAMAOUA` (Hugging Face)", "**MIT, vérifiée**"],
    ["Affinage, étape 2 et mémoire validée", "Textes de l'environnement de test, traduits et corrigés par le locuteur natif de l'équipe", "Création de l'équipe"],
    ["Enregistrements des natifs", "Locuteur natif de l'équipe", "Création de l'équipe"],
], [34, 44, 22])
CALL("**Licence MIT du modèle.** Elle autorise l'usage, **y compris commercial**, la modification et la distribution, **à condition de conserver la mention de la licence** (avis de droit d'auteur et texte de la licence MIT). Cette mention figure dans `backend/LICENSES.md`. Le modèle affiné n'est pas dans le dépôt (1,9 Go) ; son empreinte SHA-256 est dans `backend/docs/MODEL.md`.")
H2("5.4 Services externes")
P("**Aucun** dans le produit livré : le serveur n'appelle aucun service externe et l'extension ne contacte que l'adresse du serveur fixée à sa construction. "
  "Pendant l'installation, `pip` télécharge Flask depuis le dépôt public des paquets Python ; la page de test du concours est servie par `safinum.cm`.")

# ---- 6. Configuration, intégration, exploitation ---------------------------------------------------------------------
H1("6. Configuration, intégration et exploitation", 6)
H2("6.1 Configuration du serveur")
P("Toute la configuration passe par des variables `AMIRA_*` (fichier `.env`, jamais commité ; modèle : `backend/.env.example`).")
T(["Variable", "Défaut", "Rôle"], [
    ["`AMIRA_ENV`", "`production`", "`development` ouvre le CORS à toute extension ; **hors développement, `AMIRA_ALLOWED_ORIGINS` est obligatoire**"],
    ["`AMIRA_ALLOWED_ORIGINS`", "vide", "Identifiant de l'extension publiée : `chrome-extension://<id>`"],
    ["`AMIRA_LANGUAGE`", "`ff`", "Langue cible de l'installation : un dossier `languages/<code>/`"],
    ["`AMIRA_ENGINE`", "`m2m100`", "`m2m100` (modèle local) ou `memory` (mémoire validée seule)"],
    ["`AMIRA_MODEL_DIR`", "`models/m2m_ff`", "Dossier du modèle"],
    ["`AMIRA_GOLD_VALIDATOR`", "vide", "Si défini, le CSV de mémoire est rechargé dès qu'il change, sans redémarrer"],
    ["`AMIRA_MIN_CONFIDENCE`, `_FROM_FF`", "0,5 ; 0,7", "Seuils de confiance vers / depuis la langue cible"],
    ["`AMIRA_ENGINE_BUDGET_S`", "6", "Budget du moteur par requête (le front coupe à 8 s)"],
    ["`AMIRA_ADMIN_TOKENS`", "vide", "Jetons des outils des natifs ; **vide = administration fermée**"],
    ["`AMIRA_API_KEYS`", "vide", "Si défini, tout appel sans origine d'extension autorisée doit porter `X-Amira-Key`"],
    ["`AMIRA_RATE_LIMIT_PER_MIN`", "600", "Requêtes par minute et par adresse"],
    ["`AMIRA_TRUSTED_PROXIES`", "0", "Proxys de confiance devant le service ; à régler **seulement** si le service n'est joignable que par eux"],
    ["`AMIRA_DB_PATH`, `AMIRA_RECORDINGS_DIR`", "`data/…`, `media/…`", "Base SQLite et enregistrements servis"],
], [30, 18, 52])
P("**Extension** : `VITE_AMIRA_API_URL` (adresse du serveur, **fixée à la construction** ; sans elle, l'extension fonctionne en simulation) et `VITE_AMIRA_LANGUAGE` (langue cible, `ff` par défaut).")
H2("6.2 Installation complète du serveur")
CODE("cd backend\npython3 -m venv .venv\n.venv/bin/pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0\n.venv/bin/pip install -r requirements-dev.txt -c constraints.txt\ncp .env.example .env\n.venv/bin/python -m tools.import_gold languages/ff/gold.csv --validator natif-1\n.venv/bin/gunicorn -w 1 --threads 4 -b 127.0.0.1:5000 wsgi:app")
H2("6.3 Intégration finale chez un opérateur")
N(["**Serveur** : installer comme ci-dessus sur une machine du réseau interne, sans accès à Internet ; placer le modèle et vérifier son SHA-256.",
   "**Configuration** : `AMIRA_ENV=production`, `AMIRA_ALLOWED_ORIGINS=chrome-extension://<id>`, `AMIRA_ADMIN_TOKENS`, `AMIRA_API_KEYS` si des serveurs appellent l'API, `AMIRA_TRUSTED_PROXIES` selon la passerelle.",
   "**Passerelle** : TLS, authentification et quotas devant `127.0.0.1:5000` ; le serveur ne doit être joignable que par elle.",
   "**Extension** : `VITE_AMIRA_API_URL=https://amira.interne.exemple npm run build`, puis publier `dist/` ; les sites du service sont autorisés par l'utilisateur, une fois.",
   "**Supervision** : surveiller `/v1/health` et `/v1/ready`.",
   "**Mémoire** : charger la mémoire validée ; `AMIRA_GOLD_VALIDATOR` permet les mises à jour sans redémarrage.",
   "**Vérification** : `bash backend/tools/e2e_extension.sh` (pastille, page traduite, texte inédit, lecture, aucune connexion sortante, journal sans texte)."])
H2("6.4 Exploitation")
B(["**Déploiement** : gunicorn, un seul processus et 4 threads (le modèle, environ 2,7 Go au maximum, n'est chargé qu'une fois) ; `/v1/ready` répond 503 pendant le chargement.",
   "**Remplacer le modèle** : placer le dossier, `python -m tools.check_model --model <dossier>` (comparaison à la référence d'intégrité de la machine), vérifier le SHA-256, pointer `AMIRA_MODEL_DIR`, redémarrer, relancer `pytest -m model`.",
   "**Mettre à jour la mémoire** : éditer le CSV ; avec `AMIRA_GOLD_VALIDATOR`, le serveur le recharge (un CSV mal formé est ignoré, l'ancienne mémoire reste).",
   "**Sauvegarder** : `sqlite3 data/amira.sqlite3 \".backup <destination>\"` (cohérent pendant que le service tourne) et copier le dossier des enregistrements.",
   "**Purger** : `flask --app amira purge` ; la purge tourne aussi à chaque démarrage (90 jours par défaut)."])
H2("6.5 Ajouter une langue")
P("Une installation sert **une langue cible**. Tout ce qui en dépend vit dans **un dossier** côté serveur et **un fichier** côté extension ; le moteur, la garde, le masquage et l'API ne changent pas. Remplacer `xx` par le code de la langue (2 ou 3 lettres, ISO 639).")
IMG(FIG / "langue.png", 17.0, "Ajouter une langue en six étapes")
N(["**Créer le squelette**, depuis `backend/` : `python -m tools.new_language xx --variety nord,sud`. La mémoire est vide : rien n'est écrit dans la langue.",
   "**Faire écrire la mémoire par un locuteur natif** : `languages/xx/gold.csv`, mêmes colonnes que celui du fulfulde ; valeurs variables `{V1}`, `{V2}` identiques dans les trois langues ; un nombre n'est jamais traduit. `python -m tools.import_gold languages/xx/gold.csv --validator <nom> --language xx` liste les lignes refusées avec la raison.",
   "**Le modèle (facultatif)** : déposer le modèle M2M100 affiné dans `backend/models/m2m_xx/` ; son tokenizer doit connaître le code de la langue, sinon le moteur refuse de charger avec une erreur claire. **Sans modèle, Amira sert la mémoire validée seule** et garde l'original pour le reste.",
   "**Les voix (facultatif)** : `python -m tools.organize_audio <dossier> languages/xx/gold.csv languages/xx/audio --language xx`, puis `python -m tools.import_audio languages/xx/audio languages/xx/gold.csv --validator <nom> --language xx`.",
   "**L'extension**, depuis `front/` : une entrée dans `src/languages.ts` (code, noms, préfixes de l'attribut `lang`, lettres propres, variété par défaut), `translate.target` et `translate.varieties.<variété>` dans `src/locales/fr.json` et `en.json`, puis `VITE_AMIRA_LANGUAGE=xx npm run build`.",
   "**Lancer et vérifier** : `AMIRA_LANGUAGE=xx python demo.py --language xx`, puis `pytest` et `npm test` ; un test sert une langue ajoutée de bout en bout."])
CALL("**Règles à ne pas contourner.** Aucun mot de la langue n'est écrit, généré ou deviné par le code : tout vient d'un locuteur natif. Une traduction n'est `validated` que si elle vient de la mémoire. Une langue par installation : pour en servir deux, deux serveurs et deux extensions. Le panneau n'est traduit qu'avec un natif.")

# ---- 7. Passage à l'échelle -----------------------------------------------------------------------------------------
H1("7. Passage à l'échelle", 7)
H2("7.1 Étendre à de nouvelles langues")
P("**Ce qui existe.** Ajouter une langue consiste à créer un dossier côté serveur et à ajouter une entrée côté extension (section 6.5). Un test vérifie qu'une langue ajoutée est servie de bout en bout, sans toucher au moteur, à la garde ni à l'API.")
T(["Besoin", "Pourquoi", "Effort"], [
    ["**Un ou plusieurs locuteurs natifs**", "Écrire et relire la mémoire validée ; aucune traduction n'est inventée", "Le facteur limitant : le squelette prend une demi-journée, la validation prend le temps du locuteur"],
    ["**Une mémoire validée** (`gold.csv`)", "Source des traductions `validées` ; couvre d'abord l'environnement cible", "Quelques centaines de lignes pour un premier service"],
    ["**Des voix** (facultatif)", "Voix de natifs, faute de voix de synthèse dans les navigateurs", "Une séance d'enregistrement par langue"],
    ["**Un modèle qui connaît la langue** (facultatif)", "Traduire au-delà de la mémoire ; le tokenizer doit connaître le code de la langue", "Affinage ou modèle existant"],
    ["**Une entrée dans `languages.ts`**", "Lettres propres, noms, variété", "Quelques lignes"],
], [30, 44, 26])
IMG(FIG / "langues.png", 17.0, "Pétales de langues : le fulfulde est actif, les autres langues nationales sont à venir")
P("**Langues envisagées.** Ghomálá', ewondo, duala, bassa, bulu et pidgin sont prévus par le projet ; **aucune n'est validée à ce jour**. À notre connaissance, M2M100 ne les connaît pas : chacune démarrerait **en mémoire validée seule** (le mode le plus sûr), avec un modèle affiné à fournir pour traduire au-delà de la mémoire.")
CALL("**Ordre proposé.** Une langue à la fois, en commençant par celle pour laquelle un locuteur natif est disponible pour valider chaque ligne, puis un second relecteur indépendant. Une langue sans validation n'est pas publiée.")
H2("7.2 Ce qui est limité aujourd'hui, et la réponse")
T(["Limite actuelle", "Conséquence", "Réponse prévue"], [
    ["**Débit du moteur sur processeur seul** (environ 4 à 8 passages inconnus par requête)", "Une page riche se complète sur plusieurs visites", "Processeur graphique, ou moteur quantifié (gain annoncé de 3 à 4 fois sur processeur ; décision à rouvrir)"],
    ["**Un seul modèle chargé par processus**", "Les requêtes simultanées se partagent le moteur", "Plusieurs serveurs derrière la passerelle ; la mémoire validée répond en quelques millisecondes"],
    ["**SQLite**", "Une seule machine écrit", "Schéma en SQL standard : passage à PostgreSQL prévu"],
    ["**Limiteur de débit et cache en mémoire d'un processus**", "Non partagés entre serveurs", "Quotas de la passerelle ; cache partagé si nécessaire"],
    ["**Administration par API**", "Les natifs n'ont pas d'écran dédié", "Interface web de validation pour les natifs"],
], [32, 30, 38])


# ----------------------------------------------------------------------------------------------------------------------
# Assemblage du paquet OpenXML
# ----------------------------------------------------------------------------------------------------------------------
NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"')
HDR = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

final_sect = (f'<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="11906" w:h="16838"/>'
              '<w:pgMar w:top="1134" w:right="1134" w:bottom="1247" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr>')
document = f'{HDR}<w:document {NS}><w:body>{"".join(body)}{final_sect}</w:body></w:document>'


def style(sid, name, based="Normal", ppr="", rpr_="", nxt=None, ui=None):
    return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/>' + (f'<w:basedOn w:val="{based}"/>' if based else "")
            + (f'<w:next w:val="{nxt}"/>' if nxt else "") + '<w:qFormat/>' + (f"<w:pPr>{ppr}</w:pPr>" if ppr else "") + (f"<w:rPr>{rpr_}</w:rPr>" if rpr_ else "") + "</w:style>")


def rf(f): return f'<w:rFonts w:ascii="{f}" w:hAnsi="{f}" w:cs="{f}" w:eastAsia="{f}"/>'


styles = (f'{HDR}<w:styles {NS}><w:docDefaults><w:rPrDefault><w:rPr>{rf(BODY)}<w:color w:val="{AUB}"/><w:sz w:val="19"/><w:szCs w:val="19"/><w:lang w:val="fr-FR" w:eastAsia="fr-FR" w:bidi="ar-SA"/></w:rPr></w:rPrDefault>'
          '<w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="269" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
          + style("Heading1", "heading 1",
                  ppr='<w:keepNext/><w:keepLines/><w:spacing w:before="120" w:after="180" w:line="228" w:lineRule="auto"/><w:outlineLvl w:val="0"/>',
                  rpr_=f'{rf(HEAD)}<w:b/><w:color w:val="{AUB}"/><w:sz w:val="52"/><w:szCs w:val="52"/>', nxt="Normal")
          + style("Heading2", "heading 2",
                  ppr=f'<w:keepNext/><w:keepLines/><w:pBdr><w:left w:val="single" w:sz="24" w:space="8" w:color="{ROSE}"/></w:pBdr><w:spacing w:before="300" w:after="110" w:line="240" w:lineRule="auto"/><w:ind w:left="170"/><w:outlineLvl w:val="1"/>',
                  rpr_=f'{rf(HEAD)}<w:b/><w:color w:val="{AUB}"/><w:sz w:val="27"/><w:szCs w:val="27"/>', nxt="Normal")
          + style("Heading3", "heading 3", ppr='<w:keepNext/><w:keepLines/><w:spacing w:before="200" w:after="70" w:line="240" w:lineRule="auto"/><w:outlineLvl w:val="2"/>',
                  rpr_=f'{rf(HEAD)}<w:b/><w:color w:val="{ROSE_T}"/><w:sz w:val="22"/><w:szCs w:val="22"/>', nxt="Normal")
          + style("ListParagraph", "List Paragraph", ppr='<w:spacing w:after="60"/><w:ind w:left="400" w:hanging="260"/>')
          + style("Code", "Code", ppr=f'<w:keepLines/><w:pBdr><w:left w:val="single" w:sz="18" w:space="6" w:color="{ROSE}"/></w:pBdr><w:shd w:val="clear" w:color="auto" w:fill="{DOUX}"/><w:spacing w:after="0" w:line="252" w:lineRule="auto"/><w:ind w:left="160"/>',
                  rpr_=f'{rf(MONO)}<w:sz w:val="17"/><w:szCs w:val="17"/>')
          + style("Callout", "Callout", ppr=f'<w:keepLines/><w:pBdr><w:left w:val="single" w:sz="36" w:space="8" w:color="{JAUNE}"/></w:pBdr><w:shd w:val="clear" w:color="auto" w:fill="{DOUX}"/><w:spacing w:before="120" w:after="160"/><w:ind w:left="200" w:right="60"/>')
          + style("TableText", "Table Text", ppr='<w:spacing w:before="0" w:after="30" w:line="250" w:lineRule="auto"/>', rpr_='<w:sz w:val="17"/><w:szCs w:val="17"/>')
          + style("Caption", "caption", ppr='<w:spacing w:before="0" w:after="140"/><w:jc w:val="center"/>', rpr_=f'<w:i/><w:color w:val="{ROSE_T}"/><w:sz w:val="17"/><w:szCs w:val="17"/>')
          + style("Footer", "footer", ppr=f'<w:pBdr><w:top w:val="single" w:sz="6" w:space="4" w:color="{ROSE}"/></w:pBdr><w:tabs><w:tab w:val="right" w:pos="{TEXT_W}"/></w:tabs><w:spacing w:after="0"/>', rpr_='<w:sz w:val="15"/><w:szCs w:val="15"/>')
          + '</w:styles>')

bullet_lvl = (f'<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="■"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="400" w:hanging="260"/></w:pPr>'
              f'<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:color w:val="{ROSE}"/><w:sz w:val="14"/></w:rPr></w:lvl>')
dec_lvl = (f'<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="400" w:hanging="300"/></w:pPr>'
           f'<w:rPr><w:b/><w:color w:val="{ROSE_T}"/></w:rPr></w:lvl>')
numbering = (f'{HDR}<w:numbering {NS}><w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/>{bullet_lvl}</w:abstractNum>'
             f'<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="singleLevel"/>{dec_lvl}</w:abstractNum>'
             '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
             + "".join(f'<w:num w:numId="{n}"><w:abstractNumId w:val="1"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>' for n in nums)
             + "</w:numbering>")

footer = (f'{HDR}<w:ftr {NS}><w:p><w:pPr><w:pStyle w:val="Footer"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t>Amira</w:t></w:r><w:r><w:t xml:space="preserve"> · Dossier de candidature · SAFINUM Innovate Challenge</w:t></w:r>'
          '<w:r><w:tab/></w:r><w:r><w:t xml:space="preserve">Page </w:t></w:r><w:fldSimple w:instr=" PAGE "><w:r><w:rPr><w:b/></w:rPr><w:t>1</w:t></w:r></w:fldSimple></w:p></w:ftr>')

font_table = (f'{HDR}<w:fonts {NS}>'
              f'<w:font w:name="{HEAD}"><w:altName w:val="Arial"/><w:family w:val="swiss"/><w:pitch w:val="variable"/></w:font>'
              f'<w:font w:name="{BODY}"><w:altName w:val="Calibri"/><w:family w:val="swiss"/><w:pitch w:val="variable"/></w:font>'
              f'<w:font w:name="{MONO}"><w:altName w:val="Courier New"/><w:family w:val="modern"/><w:pitch w:val="fixed"/></w:font></w:fonts>')
settings = (f'{HDR}<w:settings {NS}><w:defaultTabStop w:val="720"/><w:characterSpacingControl w:val="doNotCompress"/>'
            '<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>')

rels = (f'{HDR}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rIdNum" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
        '<Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
        '<Relationship Id="rIdFonts" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>'
        '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
        + "".join(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{rid}.png"/>' for rid, _ in images)
        + "</Relationships>")
content_types = (f'{HDR}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                 '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                 '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
                 '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
                 '<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>'
                 '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                 '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                 '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>')
root_rels = (f'{HDR}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
             '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
             '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>')
core = (f'{HDR}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Amira : dossier de candidature</dc:title>'
        '<dc:subject>SAFINUM Innovate Challenge, épreuve de présélection</dc:subject><dc:creator>Équipe Amira</dc:creator><dc:language>fr-FR</dc:language>'
        '<dcterms:created xsi:type="dcterms:W3CDTF">2026-11-14T00:00:00Z</dcterms:created></cp:coreProperties>')
app = f'{HDR}<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Amira</Application></Properties>'

OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", root_rels)
    z.writestr("word/document.xml", document)
    z.writestr("word/_rels/document.xml.rels", rels)
    z.writestr("word/styles.xml", styles)
    z.writestr("word/numbering.xml", numbering)
    z.writestr("word/settings.xml", settings)
    z.writestr("word/fontTable.xml", font_table)
    z.writestr("word/footer1.xml", footer)
    z.writestr("docProps/core.xml", core)
    z.writestr("docProps/app.xml", app)
    for rid, path in images:
        z.writestr(f"word/media/{rid}.png", path.read_bytes())
print(f"{OUT} : {OUT.stat().st_size // 1024} Ko, {len(images)} images")
