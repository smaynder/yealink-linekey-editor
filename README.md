# Yealink Linekey Editor

Deux scripts Python pour gérer rapidement les **touches programmables
(`linekey.N`)** d'un parc de téléphones Yealink (`.cfg`), sans jamais
toucher au reste des fichiers (compte SIP, VLAN, annuaire, mots de
passe, etc.) :

- `list.py` : scanne tous vos fichiers `.cfg` et génère un
  annuaire CSV (nom du poste <-> nom de fichier/adresse MAC).
- `linekey.py` : modifie les touches d'un poste désigné **par
  son nom** (plus besoin de chercher son adresse MAC).

Pensé pour la gestion en masse d'un parc de téléphones (T73U et
compatibles), avec ou sans module d'extension EXP.

## Pourquoi

Vos fichiers `.cfg` sont nommés d'après l'adresse MAC du poste (ex:
`805ec0abcdef.cfg`), ce qui n'est pas pratique à retenir ou à
retrouver. Éditer ces fichiers à la main pour changer 2-3 touches sur
50 téléphones est en plus long et source d'erreurs (mauvaise ligne,
mauvais poste, oubli d'un paramètre lié comme `.extension`). Ces
scripts automatisent tout ça : vous désignez un poste par son nom, et
seules les lignes concernées changent dans le fichier.

## Organisation attendue

Placez ce dossier **à l'intérieur** du dossier qui contient tous vos
fichiers `.cfg` :

```
dossier_postes/                  <- vos fichiers .cfg (un par poste)
├── 805ec0abcdef.cfg
├── 001565a1b2c3.cfg
├── ...
├── users.csv          <- généré automatiquement ici
└── yealink-linekey-editor/      <- ce dossier (cloné depuis GitHub)
    ├── list.py
    ├── linekey.py
    ├── backup/                 <- sauvegardes .bak (générées automatiquement)
    └── README.md
```

Les deux scripts remontent automatiquement d'un dossier (celui où ils
se trouvent eux-mêmes) pour chercher les `.cfg` — peu importe depuis où
vous les lancez.

## Fonctionnalités

- Fonctionne sur n'importe quel fichier `.cfg` Yealink existant.
- Vous désignez un poste **par son nom** (`account.1.display_name`, ou
  `account.1.label` à défaut) plutôt que par son adresse MAC. Recherche
  exacte, puis partielle, puis suggestions si faute de frappe.
- L'annuaire (`users.csv`) est régénéré automatiquement à
  chaque lancement de `linekey.py`, donc toujours à jour.
- **Détecte automatiquement** le nombre de touches présentes dans le
  fichier : 8 touches pour un poste simple, ou davantage si un module
  d'extension EXP est configuré (les touches d'extension utilisent le
  même paramètre `linekey.N.*`, avec des numéros plus élevés après la
  dernière touche physique du poste).
- Demande d'abord le **type de touche**, puis ne pose que les questions
  pertinentes pour ce type :
  - `15` Ligne (multi-appel) → `label`
  - `13` Numéro abrégé (speed dial) → `value`, `label`
  - `16` BLF / Supervision (suivez-moi, poste collègue...) → `value`,
    `label`, `extension` (fixé automatiquement à `**`)
  - `0` Vide / désactivée
- Le libellé (`label`) est du **texte libre**, sans contrainte.
- Si la touche modifiée avait déjà une configuration, propose de la
  **déplacer** vers une autre touche plutôt que de la perdre. Si vous
  déplacez, la touche cible cède à son tour sa propre ancienne config
  → nouvelle proposition de déplacement, et ainsi de suite. La chaîne
  s'arrête dès que vous répondez « non » à un déplacement : la config
  alors en cours de déplacement est définitivement supprimée.
- Vous pouvez configurer une touche qui n'existe pas encore dans le
  fichier (ex: activer une nouvelle touche sur un module d'extension) :
  elle est créée et insérée juste après les touches existantes.
- **Ne modifie jamais** le reste du fichier : commentaires, VLAN,
  annuaire, comptes SIP, mots de passe, etc. restent identiques,
  ligne pour ligne.
- Crée une sauvegarde dans `backup/<fichier>.cfg.bak` (à côté des
  scripts) avant toute écriture — toujours écrasée à l'exécution
  suivante, un seul `.bak` par fichier, pas d'accumulation.

## Prérequis

- Python 3 (aucune dépendance externe, uniquement la bibliothèque
  standard).

## Installation

Dans le dossier qui contient déjà vos fichiers `.cfg` :

```bash
git clone https://github.com/<votre-compte>/yealink-linekey-editor.git
```

## Utilisation

### 1. Générer / consulter l'annuaire (optionnel)

```bash
python3 yealink-linekey-editor/list.py
```

Affiche la liste des postes détectés et écrit `users.csv`
dans le dossier des `.cfg`. Utile pour vérifier rapidement les noms
disponibles, ou pour ouvrir le CSV dans Excel/LibreOffice. Ce n'est pas
une étape obligatoire : `linekey.py` régénère l'annuaire tout
seul à chaque exécution.

### 2. Modifier les touches d'un poste

```bash
python3 yealink-linekey-editor/linekey.py "Accueil SIEGE"
```

Plusieurs postes à la suite (le script les traite un par un, dans la
même exécution) :

```bash
python3 yealink-linekey-editor/linekey.py "Accueil SIEGE" "Bureau DGA"
```

Si le nom n'est pas encore dans l'annuaire, ou en cas de doute, vous
pouvez aussi donner directement le nom de fichier `.cfg` ou l'adresse
MAC.

### Déroulé type

1. Le script régénère l'annuaire et retrouve le fichier correspondant
   au nom donné (recherche exacte, puis partielle ; en cas de doublon
   ou d'absence, il vous demande de préciser ou propose des
   suggestions).
2. Il affiche la configuration actuelle des touches détectées dans le
   fichier.
3. Vous indiquez le numéro de la touche à modifier.
4. Vous choisissez le type de touche, puis remplissez uniquement les
   champs nécessaires pour ce type.
5. Si l'ancienne configuration de cette touche existait, vous pouvez
   la déplacer sur une autre touche (et ainsi de suite en chaîne), ou
   la supprimer en répondant « non ».
6. Vous pouvez enchaîner sur une autre touche du même fichier, ou
   passer au poste suivant.
7. Le fichier est réécrit sur place ; une sauvegarde de l'état
   précédent est conservée dans `backup/`.

### Exemple

```
Configuration actuelle des 8 touches :
  Touche 1 : Ligne  label='Ligne 1'
  Touche 2 : Ligne  label='Ligne 2'
  ...
  Touche 8 : Speed dial  label='Prestataire'  value='0699999999'

Quelle touche voulez-vous modifier (numéro) : 4

  Quel type pour cette touche ?
     1. Ligne (multi-appel)
     2. BLF / Supervision (Suivez-moi, poste collègue...)
     3. Numéro abrégé externe (speed dial)
     4. Vide / désactivée
  Votre choix [2] :
  Libellé (texte libre) [Suivez-Moi] : Renvoi Accueil
  Valeur (poste supervisé / code fonction) [*212000] : *212050
```

## Fichier d'exemple

Un fichier de config type se trouve dans `examples/` pour tester sans
risquer un fichier de production. Copiez-le **dans le dossier parent**
(celui des `.cfg`), pas dans `examples/` lui-même :

```bash
cp examples/FICHIER_TYPE_YEALINK.cfg ../test_poste.cfg
python3 list.py
python3 linekey.py "Accueil SIEGE"
```

## Limites connues

- Les scripts travaillent uniquement sur les paramètres `linekey.N.*`
  (touches de ligne / DSS keys, y compris module d'extension). Les
  `programablekey.*` (touches fixes du poste, ex: touche « Annuaire »)
  ne sont pas concernées.
- Le nom du poste est lu une seule fois par fichier (`account.1.*`) :
  si un fichier gère plusieurs comptes SIP, seul le premier est utilisé
  pour l'annuaire.
- Aucune validation métier sur les valeurs saisies (numéros, codes) :
  le script fait confiance à la saisie de l'utilisateur.

## Licence

MIT — voir [LICENSE](LICENSE).
