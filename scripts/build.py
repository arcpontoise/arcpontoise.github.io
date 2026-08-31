"""Génère le planning HTML à partir de data/planning.yaml.

Usage : python scripts/build.py [--check]
  --check : valide les données sans générer de sortie.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "data" / "planning.yaml"
TEMPLATES = RACINE / "templates"
DIST = RACINE / "dist"
PAGES = {"liste.html.j2": "index.html", "paysage.html.j2": "paysage.html"}

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
PUBLICS = {"jeunes", "adultes", "tous"}
HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def valider(donnees: dict[str, Any]) -> list[str]:
    """Retourne la liste des erreurs de structure du fichier de données."""
    erreurs: list[str] = []

    for cle in ("saison", "club", "note_globale", "creneaux", "tir_libre"):
        if cle not in donnees:
            erreurs.append(f"clé racine manquante : {cle}")
    if erreurs:
        return erreurs

    for i, c in enumerate(donnees["creneaux"], start=1):
        ref = f"créneau {i} ({c.get('intitule', 'sans intitulé')})"
        if c.get("jour") not in JOURS:
            erreurs.append(f"{ref} : jour invalide « {c.get('jour')} »")
        for champ in ("debut", "fin"):
            if not HEURE.match(str(c.get(champ, ""))):
                erreurs.append(f"{ref} : {champ} doit être au format HH:MM")
        horaires_valides = HEURE.match(str(c.get("debut", ""))) and HEURE.match(
            str(c.get("fin", ""))
        )
        if horaires_valides and c["debut"] >= c["fin"]:
            erreurs.append(f"{ref} : début ({c['debut']}) >= fin ({c['fin']})")
        if c.get("public") not in PUBLICS:
            erreurs.append(f"{ref} : public invalide « {c.get('public')} »")
        if not isinstance(c.get("encadrants"), list):
            erreurs.append(f"{ref} : encadrants doit être une liste (éventuellement vide)")

    for jour in donnees["tir_libre"]:
        if jour not in JOURS:
            erreurs.append(f"tir_libre : jour invalide « {jour} »")

    return erreurs


def heure_fr(valeur: str) -> str:
    """Formate « 19:30 » en « 19 h 30 » et « 14:00 » en « 14 h »."""
    heures, minutes = valeur.split(":")
    suffixe = f" h {minutes}" if minutes != "00" else " h"
    return f"{int(heures)}{suffixe}"


def en_minutes(valeur: str) -> int:
    """Convertit « HH:MM » en minutes depuis minuit."""
    heures, minutes = valeur.split(":")
    return int(heures) * 60 + int(minutes)


def repartir_couloirs(creneaux: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """Attribue à chaque créneau (trié par début) un couloir et la largeur du groupe.

    Les créneaux qui se chevauchent dans la même journée sont répartis
    côte à côte ; retourne pour chacun (index_couloir, nb_couloirs).
    """
    positions: list[tuple[int, int]] = []
    groupe: list[int] = []  # indices du groupe de chevauchement courant
    couloirs: list[int] = []  # minute de fin de chaque couloir du groupe
    fin_groupe = -1

    for i, c in enumerate(creneaux):
        debut, fin = en_minutes(c["debut"]), en_minutes(c["fin"])
        if debut >= fin_groupe:  # nouveau groupe : figer la largeur du précédent
            for j in groupe:
                positions[j] = (positions[j][0], len(couloirs))
            groupe, couloirs = [], []
        affecte = next((k for k, libre in enumerate(couloirs) if libre <= debut), None)
        if affecte is None:
            affecte = len(couloirs)
            couloirs.append(fin)
        else:
            couloirs[affecte] = fin
        positions.append((affecte, 1))
        groupe.append(i)
        fin_groupe = max(fin_groupe, fin)

    for j in groupe:
        positions[j] = (positions[j][0], len(couloirs))
    return positions


def calculer_blocs(
    creneaux: list[dict[str, Any]], debut_grille: int, duree_grille: int
) -> list[dict[str, Any]]:
    """Calcule la position de chaque créneau en pourcentage de la grille horaire."""
    blocs = []
    for c, (couloir, nb) in zip(creneaux, repartir_couloirs(creneaux), strict=True):
        haut = (en_minutes(c["debut"]) - debut_grille) / duree_grille * 100
        hauteur = (en_minutes(c["fin"]) - en_minutes(c["debut"])) / duree_grille * 100
        blocs.append(
            {
                **c,
                "haut": round(haut, 3),
                "hauteur": round(hauteur, 3),
                "gauche": round(couloir / nb * 100, 3),
                "largeur": round(100 / nb, 3),
            }
        )
    return blocs


def construire_contexte(donnees: dict[str, Any]) -> dict[str, Any]:
    """Regroupe et trie les créneaux par jour pour les templates."""
    debut_grille = min(en_minutes(c["debut"]) for c in donnees["creneaux"]) // 60 * 60
    fin_grille = -(-max(en_minutes(c["fin"]) for c in donnees["creneaux"]) // 60) * 60
    duree_grille = fin_grille - debut_grille

    jours = []
    for nom in JOURS:
        creneaux = sorted(
            (c for c in donnees["creneaux"] if c["jour"] == nom),
            key=lambda c: (c["debut"], c["fin"]),
        )
        tir_libre = donnees["tir_libre"].get(nom)
        jours.append(
            {
                "nom": nom,
                "creneaux": creneaux,
                "blocs": calculer_blocs(creneaux, debut_grille, duree_grille),
                "tir_libre": tir_libre,
            }
        )

    heures = [
        {
            "label": heure_fr(f"{m // 60:02d}:00"),
            "haut": round((m - debut_grille) / duree_grille * 100, 3),
        }
        for m in range(debut_grille, fin_grille + 1, 60)
    ]

    return {
        "saison": donnees["saison"],
        "club": donnees["club"],
        "note_globale": donnees["note_globale"],
        "jours": [j for j in jours if j["creneaux"] or j["tir_libre"]],
        "jours_complets": jours,
        "heures": heures,
        "nb_heures": duree_grille // 60,
        "date_generation": date.today().strftime("%d/%m/%Y"),
    }


def principal() -> int:
    """Point d'entrée : valide, puis génère les pages dans dist/."""
    donnees = yaml.safe_load(DONNEES.read_text(encoding="utf-8"))
    erreurs = valider(donnees)
    if erreurs:
        for erreur in erreurs:
            print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    if "--check" in sys.argv:
        print(f"OK : {len(donnees['creneaux'])} créneaux valides")
        return 0

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["heure_fr"] = heure_fr
    contexte = construire_contexte(donnees)

    DIST.mkdir(parents=True, exist_ok=True)
    for template, sortie in PAGES.items():
        html = env.get_template(template).render(contexte)
        (DIST / sortie).write_text(html, encoding="utf-8")
        print(f"Généré : {(DIST / sortie).relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
