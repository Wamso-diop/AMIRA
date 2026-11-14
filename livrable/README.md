# Dossier livrable : Amira

**Le document à envoyer au jury est `Amira-Dossier-de-candidature.docx`.** C'est le livrable de l'épreuve de présélection du SAFINUM Innovate Challenge : il ne contient que ce que le règlement demande et les détails utiles au jury.

| Section du document | Livrable demandé par le règlement |
|---|---|
| 1. Description de la solution | Description succincte de la solution et du problème qu'elle résout |
| 2. Prototype et démonstration reproductible | Prototype fonctionnel ou démonstration technique reproductible |
| 3. Note technique | Architecture, modalités d'intégration, dépendances, limites connues |
| 4. Langues et validation linguistique | Langue(s) prise(s) en charge et méthode de validation linguistique |
| 5. Composants et licences | Déclaration des composants utilisés et de la contribution propre |
| 6. Configuration, intégration et exploitation | Documentation du projet |
| 7. Passage à l'échelle | Ajout de nouvelles langues et limites |

**L'extension à installer dans le navigateur** est dans `Amira-Extension.zip` (7,2 Mo compressé, 9,3 Mo déplié : moins de 10 Mo). Elle **agit seule** : la mémoire validée et 130 voix de natifs sont dans le paquet. `Amira-Prototype.zip` (7,8 Mo) y ajoute le serveur, qui renforce l'extension en traduisant ce que la mémoire ne connaît pas.

La **vidéo de démonstration** (trois minutes au maximum) est un livrable séparé : elle n'est pas dans ce dossier.

## Régénérer le document

Le document est produit par script, dans la charte graphique d'Amira (aubergine, rose, jaune, vert, bleu ; Inter Tight et Noto Sans ; formes en biseau). Depuis `front/` (Node.js 20 ou plus, Python 3, après `npm install`) :

```bash
npm run livrable            # figures (schémas, bandeaux, couverture) puis document Word
npm run livrable:captures   # refait les captures RÉELLES (serveur lancé par `python demo.py`, extension/ construite)
```

Le texte est dans `front/scripts/livrable_docx.py` ; les figures sont dessinées par `front/scripts/livrable-figures.mjs` (`front/docs/figures/`). Les captures montrent la vraie extension traduisant une page de démonstration reconstituée avec des libellés de l'environnement de test.

Pour un rendu identique à la charte, installer les polices libres **Inter Tight** et **Noto Sans** ; sans elles, Word les remplace par des polices voisines (les figures, elles, sont des images et ne changent pas).
