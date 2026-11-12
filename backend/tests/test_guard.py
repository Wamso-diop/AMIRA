"""S3 : garde de confidentialité. Après retrait des marqueurs, aucun chiffre, devise, e-mail ni IBAN."""
import pytest

from amira.guard import check
from gold import rows, to_front

REFUSES = [
    # montants
    "Votre solde est de 25 000 FCFA",
    "Frais : 1 500 F CFA",
    "Montant : XAF 10.000",
    "Payer 10000 francs",
    "Total : 1.500,00 €",
    "Prix : $20",
    "Il reste 3,5 millions",
    # devises sans chiffre (le front aurait dû masquer le montant entier)
    "Montant en FCFA",
    "payable en fcfa",
    "en cfa uniquement",
    "en XAF",
    "en XOF",
    "cinq mille francs",
    "un franc symbolique",
    "Somme en €",
    "Somme en £",
    "Somme en ₦",
    # téléphones camerounais
    "Appelez le +237 6 99 12 34 56",
    "Appelez le 699123456",
    "Appelez le 237699123456",
    "Tél. : 6 77 00 00 00",
    "Numéro 00237 222 23 45 67",
    # e-mails
    "Écrivez à jean.dupont@banque.cm",
    "Contact : support+aide@exemple.com",
    "jean@exemple.co",
    # IBAN
    "IBAN : CM21 1000 2000 3000 4000 5000 678",
    "IBAN FR7630006000011234567890189",
    "Compte CM2110002000300040005000678",
    # chiffres isolés
    "Suivez les 5 étapes",
    "Code 0",
    # chiffres déguisés
    "Code ６９９",                      # chiffres pleine chasse
    "Code ٦٩٩",                         # chiffres arabes orientaux
    "Puissance x²",                     # exposant
    "La moitié : ½",                    # fraction
    "Chapitre Ⅻ",                       # chiffre romain Unicode
    "Écrivez à jean＠exemple.com",      # @ pleine chasse
    "Somme en F\u200bCFA",              # espace de largeur nulle
    "Payer en fran\u200bcs",            # mot coupé par un caractère invisible
    "Écrivez à jean@exem\u200bple.com", # e-mail coupé par un caractère invisible
    "Somme en ＦＣＦＡ",                # lettres pleine chasse
    # numéro caché dans un faux marqueur
    "Appelez le {N699123456}",
    "Appelez le {B0}699{/B0}",
]

ACCEPTES = [
    "Votre solde est de {B0}{N0}{/B0} au {N1}.",
    "Frais : {N0}",
    "Appelez le {N0} ou écrivez à {N1}",
    "{E0} Valider {E1}",
    "Contactez-nous par e-mail",
    "Accolade {x} gardée",
    "Bonjour",
    "",
]


@pytest.mark.parametrize("text", REFUSES)
def test_refuse(text):
    assert check(text) is False


@pytest.mark.parametrize("text", ACCEPTES)
def test_accepte(text):
    assert check(text) is True


def test_au_moins_30_cas_refuses():
    assert len(REFUSES) >= 30


def test_le_gold_passe_la_garde():
    # aucune traduction validée ne doit être refusée à tort (exemples tirés du CSV, P7)
    texts = [to_front(r[c]) for r in rows() for c in ("fr", "en", "ff")]
    assert len(texts) == 3 * len(rows()) and len(rows()) > 100
    refused = [t for t in texts if not check(t)]
    assert refused == []


def test_ne_modifie_pas_le_texte():
    text = "Frais : {N0}"
    check(text)
    assert text == "Frais : {N0}"
