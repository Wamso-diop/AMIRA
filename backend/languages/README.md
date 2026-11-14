# Ajouter une langue à Amira

Une installation d'Amira sert **une langue cible** (aujourd'hui `ff`, le fulfulde de l'Adamaoua), depuis et vers le français et l'anglais. Tout ce qui dépend de la langue vit dans **un dossier** côté serveur et **un fichier** côté extension. Le moteur, la garde, le masquage et l'API ne changent pas.

```
backend/languages/<code>/
├── language.json      nom, variétés, dossier du modèle  ← la fiche
├── gold.csv           la mémoire validée par un locuteur natif     ← le contenu
├── audio/             les enregistrements des natifs (optionnel)
└── check_model.json   phrases de contrôle du modèle (optionnel)
front/src/languages.ts une entrée (lettres propres, noms, variété)  ← le seul fichier du front
```

## En six étapes (environ une demi-heure, hors traduction)

Remplacer `xx` par le code de la langue (2 ou 3 lettres, ISO 639).

1. **Créer le squelette** (depuis `backend/`) :
   `python -m tools.new_language xx --variety nord,sud`
   La première variété est celle demandée par défaut. Rien n'est écrit dans la langue : la mémoire est vide.

2. **Faire écrire la mémoire par un locuteur natif** : `languages/xx/gold.csv`, mêmes colonnes que `languages/ff/gold.csv` (`id, kind, section, page, fr, en, xx, fr_variants, en_variants, xx_variants, …`).
   - Les valeurs variables s'écrivent `{V1}`, `{V2}` (montant, nom, date) : elles doivent être identiques dans les trois langues.
   - Un nombre n'est jamais traduit : la ligne serait refusée.
   - Les lignes refusées sont listées avec la raison par `python -m tools.import_gold languages/xx/gold.csv --validator <nom du natif> --language xx`.

3. **Le modèle (facultatif)** : déposer le modèle M2M100 affiné dans `backend/models/m2m_xx/` (le chemin est dans `language.json`). Le tokenizer doit connaître le code de la langue (jeton `__xx__`) : sinon le moteur refuse de charger avec une erreur claire. **Sans modèle, Amira sert la mémoire validée seule** et garde l'original pour tout le reste : c'est le comportement le plus sûr, et celui de `python demo.py`.

4. **Les voix (facultatif)** : déposer les `.m4a` du natif nommés par le texte qu'il dit, puis
   `python -m tools.organize_audio <dossier des .m4a> languages/xx/gold.csv languages/xx/audio --language xx`
   `python -m tools.import_audio languages/xx/audio languages/xx/gold.csv --validator <nom> --language xx`

5. **L'extension** (depuis `front/`) :
   - ajouter une entrée dans `src/languages.ts` (un exemple est en commentaire) : code, noms en français et en anglais, préfixes de l'attribut `lang`, **lettres que n'ont ni le français ni l'anglais** (elles servent à reconnaître une page écrite dans la langue), variété par défaut ;
   - dans `src/locales/fr.json` et `en.json` : `translate.target` (nom affiché) et `translate.varieties.<variété>` ;
   - construire : `VITE_AMIRA_LANGUAGE=xx npm run build`.

6. **Lancer et vérifier** :
   `AMIRA_LANGUAGE=xx python demo.py --language xx` (Windows : `set AMIRA_LANGUAGE=xx` puis la commande), puis `pytest` côté serveur et `npm test` côté front. `tests/test_new_language.py` et `tests/unit/languages.test.ts` vérifient qu'une langue est complète.

## Règles à ne pas contourner

- **Aucun mot de la langue n'est écrit, généré ou deviné par le code ou par nous.** Tout vient du CSV d'un locuteur natif (`tests/test_no_fulfulde.py` le vérifie pour le fulfulde).
- Une traduction n'est `validated` que si elle vient de la mémoire. Une sortie du modèle est `machine`, et l'original reste affiché en dessous des seuils de confiance.
- **Une langue par installation.** Pour en servir deux, lancer deux serveurs avec chacun son `AMIRA_LANGUAGE` et sa base, et construire deux extensions. L'import de la mémoire d'une langue ne touche jamais celle d'une autre dans la même base.
- Le panneau lui-même (`front/src/locales/xx.json`) n'est traduit qu'avec un natif ; sans lui, il reste en français ou en anglais.

## Où le code lit tout cela

| Besoin | Fichier |
|---|---|
| Sens autorisés, modèle, variétés, chemin de la mémoire | `backend/amira/config.py` (`load_language`) |
| Import de la mémoire, de l'audio | `backend/tools/import_gold.py`, `import_audio.py`, `organize_audio.py` (option `--language`) |
| Langue de la page, sens de traduction, voix | `front/src/languages.ts` |
