#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Édition ciblée des touches programmables (linekey.N) dans un fichier de
config Yealink existant — SANS toucher au reste du fichier.

S'ADAPTE AUTOMATIQUEMENT au nombre de touches présentes dans le fichier :
  - un poste "simple" (ex: 8 touches) et un poste avec module(s) d'extension
    EXP (qui ajoute des touches au-delà de la dernière touche physique du
    poste, ex: linekey.9, linekey.10 ... jusqu'à linekey.60+ par module)
    sont tous les deux gérés sans configuration préalable : le script lit
    simplement tous les "linekey.N.*" réellement présents dans le fichier.
  - vous pouvez aussi créer une touche qui n'existe pas encore dans le
    fichier (ex: ajouter linekey.25 sur un poste équipé d'un module EXP).

Fonctionnement :
  - vous choisissez le numéro de la touche à modifier
  - vous choisissez d'abord le TYPE de touche :
        15 = Ligne            -> demande : label
        13 = Numéro abrégé    -> demande : value, label
        16 = BLF / Supervision-> demande : value, label (+ extension = ** auto)
        0  = Vide
  - label = texte libre, sans contrainte
  - si la touche modifiée avait déjà une config, on vous propose de la
    DÉPLACER vers une autre touche. Si vous déplacez, la touche cible cède
    à son tour SA propre ancienne config -> on redemande où la déplacer,
    etc. La chaîne s'arrête dès que vous répondez "non" -> suppression
    définitive de la config alors en cours de déplacement.

Ce script cherche les fichiers .cfg dans le dossier PARENT (un cran en
arrière par rapport à l'emplacement de ce script), et vous désignez le
poste à modifier par son NOM (ex: "Accueil SIEGE"), pas par son adresse
MAC. Le nom est retrouvé via l'annuaire users.csv, généré (ou mis à
jour automatiquement) par list.py.

Usage :
    python3 linekey.py "Accueil SIEGE"
    python3 linekey.py "Accueil SIEGE" "Bureau DGA"

Vous pouvez aussi, si besoin, donner directement le nom de fichier .cfg
ou l'adresse MAC (utile si le nom n'est pas encore dans l'annuaire).

Les sauvegardes (.bak) sont créées dans le dossier backup/, à côté de
ce script.
"""

import sys
import re
import shutil
import argparse
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path

import list as annuaire

SCRIPT_DIR = Path(__file__).resolve().parent
CFG_DIR = SCRIPT_DIR.parent  # les .cfg sont un dossier en arrière
BACKUP_DIR = SCRIPT_DIR / "backup"
BACKUP_DIR.mkdir(exist_ok=True)
CSV_PATH = CFG_DIR / "users.csv"

LINEKEY_RE = re.compile(r"^\s*linekey\.(\d+)\.(\w+)\s*=\s*(.*?)\s*$")
MAX_KEY_NUMBER = 300  # garde-fou (3 modules EXP50 x 60 touches + marge)

MENU = {
    "1": ("Ligne (multi-appel)", 15),
    "2": ("BLF / Supervision (Suivez-moi, poste collègue...)", 16),
    "3": ("Numéro abrégé externe (speed dial)", 13),
    "4": ("Vide / désactivée", 0),
}
TYPE_TO_MENU = {15: "1", 16: "2", 13: "3", 0: "4"}
BLF_PICKUP_CODE = "**"


# ----------------------------------------------------------------------------
# Utilitaires de saisie
# ----------------------------------------------------------------------------
def ask(prompt, default=None):
    suffix = f" [{default}]" if default not in (None, "") else ""
    val = input(f"{prompt}{suffix} : ").strip()
    return val if val else (default or "")


def ask_yes_no(prompt, default_yes=False):
    default = "o" if default_yes else "n"
    val = ask(f"{prompt} (o/n)", default=default).lower()
    return val in ("o", "oui", "y", "yes")


def ask_int_in_range(prompt, lo, hi, exclude=None):
    exclude = exclude or set()
    while True:
        val = input(f"{prompt} : ").strip()
        if val.isdigit() and lo <= int(val) <= hi and int(val) not in exclude:
            return int(val)
        msg = f"-> Entrez un numéro entre {lo} et {hi}"
        if exclude:
            msg += f", différent de {sorted(exclude)}"
        print(msg + ".")


# ----------------------------------------------------------------------------
# Lecture / analyse du fichier
# ----------------------------------------------------------------------------
def parse_file(lines):
    """Détecte dynamiquement toutes les touches linekey.N présentes,
    quel que soit N (poste seul ou avec module(s) d'extension)."""
    keys = defaultdict(lambda: {"raw": [], "attrs": {}})
    for line in lines:
        m = LINEKEY_RE.match(line)
        if m:
            n = int(m.group(1))
            attr, val = m.group(2), m.group(3)
            keys[n]["raw"].append(line)
            keys[n]["attrs"][attr] = val
    return keys


def is_empty(attrs):
    t = attrs.get("type")
    return (not attrs) or t in (None, "", "0")


def summarize(n, attrs):
    if is_empty(attrs):
        return f"  Touche {n} : vide / non configurée"
    t = attrs.get("type", "?")
    label = attrs.get("label", "")
    value = attrs.get("value", "")
    type_name = {"15": "Ligne", "16": "BLF/Supervision", "13": "Speed dial"}.get(t, f"type {t}")
    extra = f"  value='{value}'" if value else ""
    return f"  Touche {n} : {type_name}  label='{label}'{extra}"


def print_overview(state, existing_numbers):
    if not existing_numbers:
        print("\nAucune touche linekey détectée dans ce fichier (fichier vierge de ce côté).")
        return
    lo, hi = min(existing_numbers), max(existing_numbers)
    module_note = ""
    if hi > 21:
        module_note = "  (numéros au-delà des touches physiques = module(s) d'extension EXP)"
    print(f"\nTouches détectées dans ce fichier : {lo} à {hi}{module_note}")
    print("Configuration actuelle :")
    for n in sorted(existing_numbers):
        print(summarize(n, state[n]))


# ----------------------------------------------------------------------------
# Saisie du type + champs associés
# ----------------------------------------------------------------------------
def ask_type_and_fields(current_attrs):
    cur_type = current_attrs.get("type")
    try:
        cur_type_code = int(cur_type)
    except (TypeError, ValueError):
        cur_type_code = None
    default_choice = TYPE_TO_MENU.get(cur_type_code, "1")

    print("\n  Quel type pour cette touche ?")
    for k, (label, _) in MENU.items():
        print(f"     {k}. {label}")
    choice = ask("  Votre choix", default=default_choice)
    if choice not in MENU:
        print("  -> choix invalide, valeur par défaut utilisée.")
        choice = default_choice
    _, type_code = MENU[choice]

    label = current_attrs.get("label", "")
    value = current_attrs.get("value", "")

    if type_code == 0:
        return {"type": "0", "label": "", "value": ""}

    label = ask("  Libellé (texte libre)", default=label)

    if type_code == 16:
        value = ask("  Valeur (poste supervisé / code fonction)", default=value)
    elif type_code == 13:
        value = ask("  Numéro à composer", default=value)
    else:
        value = ""  # type 15 : pas de value

    return {"type": str(type_code), "label": label, "value": value}


def build_new_block(n, attrs):
    type_code = int(attrs.get("type") or 0)
    label = attrs.get("label", "")
    value = attrs.get("value", "")

    lines = [f"linekey.{n}.line = 1\n", f"linekey.{n}.type = {type_code}\n"]
    if type_code == 0:
        lines.append(f"linekey.{n}.label = \n")
        return lines
    if type_code == 15:
        lines.append(f"linekey.{n}.label = {label}\n")
    elif type_code == 16:
        lines.append(f"linekey.{n}.value = {value}\n")
        lines.append(f"linekey.{n}.label = {label}\n")
        lines.append(f"linekey.{n}.extension = {BLF_PICKUP_CODE}\n")
    elif type_code == 13:
        lines.append(f"linekey.{n}.value = {value}\n")
        lines.append(f"linekey.{n}.label = {label}\n")
    return lines


# ----------------------------------------------------------------------------
# Résolution nom de poste -> fichier .cfg (via l'annuaire)
# ----------------------------------------------------------------------------
def resolve_query(query, rows, cfg_dir):
    """Retrouve le fichier .cfg correspondant à `query`, qui peut être un nom
    de poste (usage normal), un nom de fichier .cfg, ou une adresse MAC."""

    # 1) Cas de secours : l'utilisateur a donné directement un nom de fichier
    #    ou une adresse MAC qui existe telle quelle dans le dossier.
    for candidate in (query, f"{query}.cfg"):
        p = cfg_dir / candidate
        if p.exists():
            return p

    # 2) Recherche par nom dans l'annuaire (correspondance exacte, sans
    #    tenir compte de la casse).
    key = query.strip().lower()
    exact = [r for r in rows if r["nom"].strip().lower() == key]
    if len(exact) == 1:
        return cfg_dir / exact[0]["fichier"]
    if len(exact) > 1:
        return _choose_among(query, exact, cfg_dir)

    # 3) Recherche partielle (le nom saisi est contenu dans le nom du poste).
    partial = [r for r in rows if key in r["nom"].strip().lower()]
    if len(partial) == 1:
        print(f"  (trouvé par correspondance partielle : '{partial[0]['nom']}')")
        return cfg_dir / partial[0]["fichier"]
    if len(partial) > 1:
        return _choose_among(query, partial, cfg_dir)

    # 4) Rien trouvé : on propose des suggestions proches (fautes de frappe).
    print(f"\nAucun poste trouvé pour '{query}'.")
    close = get_close_matches(query, [r["nom"] for r in rows], n=5, cutoff=0.4)
    if close:
        print("   Vouliez-vous dire : " + ", ".join(close) + " ?")
    else:
        print("   Vérifiez l'orthographe, ou lancez list.py pour voir "
              "la liste des postes disponibles.")
    return None


def _choose_among(query, matches, cfg_dir):
    print(f"\nPlusieurs postes correspondent à '{query}' :")
    for i, m in enumerate(matches, 1):
        print(f"   {i}. {m['nom']}  ({m['fichier']})")
    idx = ask_int_in_range("Lequel voulez-vous modifier (numéro de la liste)", 1, len(matches))
    return cfg_dir / matches[idx - 1]["fichier"]


# ----------------------------------------------------------------------------
# Traitement d'un fichier
# ----------------------------------------------------------------------------
def process_file(path):
    print("\n" + "=" * 60)
    print(f" Fichier : {path.name}")
    print("=" * 60)

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    keys = parse_file(lines)
    existing_numbers = set(keys.keys())
    state = defaultdict(dict, {n: dict(keys[n]["attrs"]) for n in existing_numbers})
    touched = set()

    while True:
        print_overview(state, existing_numbers | touched)
        n = ask_int_in_range(
            "\nQuelle touche voulez-vous modifier (numéro)", 1, MAX_KEY_NUMBER
        )
        if n not in existing_numbers and n not in touched:
            print(f"  (la touche {n} n'existe pas encore dans ce fichier, elle sera créée)")

        old_attrs = dict(state[n])
        new_attrs = ask_type_and_fields(old_attrs)
        state[n] = new_attrs
        touched.add(n)

        # --- Cascade de déplacement de l'ancienne config ---
        carried = old_attrs
        carried_from = n
        visited = {n}
        while not is_empty(carried):
            if not ask_yes_no(
                f"\nLa touche {carried_from} avait une ancienne config "
                f"({summarize(carried_from, carried).strip()}). "
                f"Voulez-vous la déplacer sur une autre touche ?",
                default_yes=False,
            ):
                print(f"  -> Ancienne config de la touche {carried_from} supprimée.")
                break
            target = ask_int_in_range(
                "  Vers quelle touche voulez-vous la déplacer", 1, MAX_KEY_NUMBER,
                exclude=visited,
            )
            if target not in existing_numbers and target not in touched:
                print(f"  (la touche {target} n'existe pas encore dans ce fichier, elle sera créée)")
            visited.add(target)
            next_carried = dict(state[target])
            state[target] = carried
            touched.add(target)
            print(f"  -> Config déplacée sur la touche {target}.")
            carried = next_carried
            carried_from = target

        if not ask_yes_no("\nModifier une autre touche sur ce fichier ?", default_yes=False):
            break

    # --- Reconstruction du fichier : seules les touches "touched" changent ---
    new_blocks = {n: build_new_block(n, state[n]) for n in touched}
    output = []
    inserted = set()
    last_linekey_pos = None  # position d'insertion pour les touches toutes neuves

    for line in lines:
        m = LINEKEY_RE.match(line)
        if m:
            n = int(m.group(1))
            if n in touched:
                if n not in inserted:
                    output.extend(new_blocks[n])
                    inserted.add(n)
                last_linekey_pos = len(output)
                continue
            else:
                output.append(line)
                last_linekey_pos = len(output)
                continue
        output.append(line)

    # Touches nouvelles (n'existaient pas du tout dans le fichier d'origine)
    missing = [n for n in touched if n not in inserted]
    if missing:
        insertion_point = last_linekey_pos if last_linekey_pos is not None else len(output)
        new_lines = []
        for n in sorted(missing):
            new_lines.append(f"\n# --- Touche {n} (ajoutée) ---\n")
            new_lines.extend(new_blocks[n])
        output[insertion_point:insertion_point] = new_lines

    backup_path = BACKUP_DIR / (path.name + ".bak")
    shutil.copy2(path, backup_path)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(output)

    print(f"\n{path.name} mis à jour (touches modifiées : {sorted(touched)})")
    print(f"   Sauvegarde de l'original : backup/{backup_path.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Modifie les touches linekey.N d'un ou plusieurs postes Yealink, "
        "désignés par leur nom (users.csv)."
    )
    parser.add_argument(
        "noms",
        nargs="+",
        help='Nom(s) de poste (ex: "Accueil SIEGE"), ou à défaut nom de '
        "fichier .cfg / adresse MAC.",
    )
    args = parser.parse_args()

    if not CFG_DIR.exists():
        print(f"Dossier introuvable : {CFG_DIR}")
        sys.exit(1)

    # L'annuaire est reconstruit à chaque exécution pour rester à jour,
    # et le CSV est (re)généré au passage pour référence.
    rows = annuaire.build_index(CFG_DIR)
    if rows:
        annuaire.write_csv(rows, CSV_PATH)
        print(f"(Annuaire à jour : {CSV_PATH.name} - {len(rows)} poste(s) détecté(s))")
    else:
        print(f"Aucun fichier .cfg trouvé dans {CFG_DIR}")

    for query in args.noms:
        path = resolve_query(query, rows, CFG_DIR)
        if path is None:
            continue
        try:
            process_file(path)
        except FileNotFoundError:
            print(f"Fichier introuvable : {path} (ignoré)")
        except (KeyboardInterrupt, EOFError):
            print("\nInterrompu par l'utilisateur.")
            sys.exit(1)


if __name__ == "__main__":
    main()
