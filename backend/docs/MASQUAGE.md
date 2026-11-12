# Règles de masquage

Tout appelant (l'extension, ou un serveur de la banque) **masque avant d'envoyer**. Le serveur Amira ne voit jamais une donnée réelle : il refuse un segment qui en contient encore une trace (garde, `amira/guard.py`). Un appelant serveur doit appliquer les **mêmes règles** que le front (`front/src/content/mask.ts`, qui fait foi).

## Marqueurs

| Marqueur | Sens | Règle |
|---|---|---|
| `{N0}`, `{N1}`… | valeur masquée | numérotés **par segment**, dans l'ordre d'apparition, à partir de 0, chacun unique |
| `{B0}` … `{/B0}` | balise interne (gras, lien…) | bien imbriqués ; une phrase coupée en balises reste **un seul** segment |
| `{E0}`, `{E1}`… | élément atomique (champ, image, saut de ligne) | gardé tel quel |

Index : 1 à 3 chiffres seulement. `{N699123456}` n'est pas un marqueur ; la garde le refuse, car il cacherait un numéro. Le champ `placeholders` liste tous les marqueurs du texte. La valeur réelle de chaque marqueur reste chez l'appelant, qui la remet à sa place au retour.

## Ce qui doit être masqué

Ordre d'application du front (une valeur déjà masquée n'est pas remasquée) :

1. **E-mails** : `jean.dupont@banque.cm`
2. **Adresses web** : `https://…`, `www.…`
3. **Références et codes** : `TRX-2024-001`, `AB12CD34`, `#123`
4. **IBAN** : `CM21 1000 2000 3000 4000 5000 678`
5. **Téléphones** : `+237 6 99 12 34 56`, `00237…`, `699 12 34 56`, `222 23 45 67`
6. **Dates et heures** : `12/11/2026`, `2026-11-12`, `12 novembre 2026`, `14h30`
7. **Montants et devises** : `25 000 FCFA`, `XAF 10.000`, `1.500,00 €`, `$20`, `15 %`
8. **Devises seules** : `FCFA`, `F CFA`, `XAF`, `XOF`, `EUR`, `USD`, `GBP`, `NGN`, `€`, `$`, `£`
9. **Nombres** : tout nombre restant (`5 étapes`)
10. **Noms propres** : après une civilité (`M.`, `Mme`, `Dr`…), après un mot d'adresse (« Bonjour », « Cher », « bénéficiaire : »…), et les suites de mots à majuscule

Exemple : `Bonjour Mme Ada, vous avez reçu 25 000 FCFA de Jean Ndi le 12/11/2026.` devient
`Bonjour {N0}, vous avez reçu {N1} de {N2} le {N3}.`

## Ce que la garde du serveur refuse

Après retrait des marqueurs, et sur le texte normalisé (NFKC, caractères invisibles retirés) :

- **tout chiffre Unicode** : arabe, pleine chasse, arabe oriental, exposant, fraction, chiffre romain ;
- **tout symbole monétaire** (`€`, `$`, `£`, `₦`…) et les mots **FCFA, F CFA, CFA, XAF, XOF, franc(s)** ;
- **toute adresse e-mail** ;
- un **IBAN**, toujours refusé par ses chiffres de contrôle.

Un segment refusé revient `uncertain`, avec le texte reçu. Il n'est ni traduit, ni stocké, ni journalisé, et un compteur anonyme (`unmasked_total`) augmente.

### Écart connu entre le masquage du front et la garde

Le front ne masque pas **« franc(s) »** ni **« CFA »** quand ils sont écrits **sans montant** (« payable en francs CFA »). La garde les refuse quand même, comme le demande le brief. Un tel texte revient donc toujours `uncertain`, et le front garde l'original. Pour le traduire, il faudrait que le front masque aussi ces mots seuls.

## Limite connue

**Le serveur ne peut pas reconnaître un nom propre que l'appelant n'a pas masqué.** La garde attrape les chiffres, les devises et les e-mails, pas les noms. Un nom oublié par le masquage partirait au moteur et pourrait être stocké (textes sensibles sans traduction, signalements). La protection des noms repose entièrement sur l'appelant.
