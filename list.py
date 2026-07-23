#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scanne tous les fichiers .cfg Yealink présents dans le dossier PARENT de ce
script (là où sont rangés vos fichiers nommés par adresse MAC, ex:
805ec0abcdef.cfg) et génère un annuaire CSV faisant correspondre :

    nom du poste (account.1.display_name, ou account.1.label à défaut)
        <->
    nom du fichier .cfg (adresse MAC)

Ce fichier CSV (users.csv) est ensuite utilisé par linekey.py pour que
vous puissiez désigner un poste par son nom plutôt que par son adresse MAC.

Organisation attendue :

    dossier_postes/                <- vos fichiers .cfg (un par poste)
    ├── 805ec0abcdef.cfg
    ├── 001565a1b2c3.cfg
    ├── ...
    ├── users.csv                  <- généré ici automatiquement
    └── yealink-linekey-editor/    <- ce dossier (scripts, README...)
        ├── list.py
        └── linekey.py

Usage :
    python3 list.py
"""

import re
import csv
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CFG_DIR = SCRIPT_DIR.parent  # les .cfg sont un dossier en arrière
CSV_PATH = CFG_DIR / "users.csv"

NAME_RE = re.compile(r"^\s*account\.1\.(display_name|label)\s*=\s*(.*?)\s*$")


def extract_name(cfg_path):
    """Cherche account.1.display_name en priorité, sinon account.1.label."""
    display_name, label = None, None
    try:
        with open(cfg_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = NAME_RE.match(line)
                if m:
                    attr, val = m.group(1), m.group(2)
                    if attr == "display_name" and not display_name:
                        display_name = val
                    elif attr == "label" and not label:
                        label = val
    except OSError:
        return None
    return display_name or label or None


def build_index(cfg_dir):
    """Retourne une liste de dicts {'nom':..., 'fichier':...} pour chaque .cfg
    trouvé directement dans cfg_dir (pas de recherche récursive dans les
    sous-dossiers, pour ne pas remonter les .cfg d'exemple du projet)."""
    rows = []
    for cfg_path in sorted(cfg_dir.glob("*.cfg")):
        name = extract_name(cfg_path)
        if not name:
            name = f"(nom introuvable) {cfg_path.stem}"
        rows.append({"nom": name, "fichier": cfg_path.name})
    return rows


def write_csv(rows, csv_path):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["nom", "fichier"])
        writer.writeheader()
        for row in sorted(rows, key=lambda r: r["nom"].lower()):
            writer.writerow(row)


def main():
    if not CFG_DIR.exists():
        print(f"Dossier introuvable : {CFG_DIR}")
        sys.exit(1)

    rows = build_index(CFG_DIR)
    if not rows:
        print(f"Aucun fichier .cfg trouvé dans {CFG_DIR}")
        sys.exit(0)

    write_csv(rows, CSV_PATH)

    print(f"{len(rows)} fichier(s) .cfg trouvé(s) dans {CFG_DIR}")
    print(f"Annuaire généré : {CSV_PATH}\n")
    for row in sorted(rows, key=lambda r: r["nom"].lower()):
        print(f"  {row['nom']:<35} -> {row['fichier']}")

    # Signale les noms en double (même display_name sur plusieurs fichiers)
    seen = {}
    for row in rows:
        seen.setdefault(row["nom"], []).append(row["fichier"])
    duplicates = {n: files for n, files in seen.items() if len(files) > 1}
    if duplicates:
        print("\nAttention, plusieurs fichiers partagent le même nom :")
        for n, files in duplicates.items():
            print(f"   '{n}' -> {', '.join(files)}")
        print("   (linekey.py vous demandera de préciser lequel)")


if __name__ == "__main__":
    main()
