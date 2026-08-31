"""Génère le site statique (planning, tarifs, calculateur) depuis data/.

Usage : python scripts/build.py [--check]
  --check : valide les données sans générer de sortie.

Les montants sont manipulés en centimes (entiers) : aucun total n'est
saisi dans les données, tout est calculé ici.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

RACINE = Path(__file__).resolve().parent.parent
TEMPLATES = RACINE / "templates"
DIST = RACINE / "dist"

# template -> chemin de sortie dans dist/
PAGES = {
    "accueil.html.j2": "index.html",
    "planning/liste.html.j2": "planning/index.html",
    "planning/paysage.html.j2": "planning/paysage.html",
    "planning/embarque.html.j2": "planning/embarque.html",
    "tarifs/tableau.html.j2": "tarifs/index.html",
    "plaquette/page.html.j2": "plaquette/index.html",
    "tarifs/calculateur.html.j2": "calculateur/index.html",
}

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
PUBLICS = {"jeunes", "adultes", "tous"}
HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
PARTS = ("ffta", "evenement_exceptionnel", "ligue", "departement")


# ---------------------------------------------------------------- utilitaires


def heure_fr(valeur: str) -> str:
    """Formate « 19:30 » en « 19 h 30 » et « 14:00 » en « 14 h »."""
    heures, minutes = valeur.split(":")
    suffixe = f" h {minutes}" if minutes != "00" else " h"
    return f"{int(heures)}{suffixe}"


def en_minutes(valeur: str) -> int:
    """Convertit « HH:MM » en minutes depuis minuit."""
    heures, minutes = valeur.split(":")
    return int(heures) * 60 + int(minutes)


def texte_riche(valeur: str) -> Markup:
    """Convertit un texte YAML en paragraphes HTML.

    Dans les données, une ligne vide sépare deux paragraphes. Avec le
    style plié « >- », les lignes d'un même paragraphe peuvent être
    coupées librement dans le fichier sans effet sur le rendu.
    """
    paragraphes = [p.strip() for p in valeur.strip().splitlines() if p.strip()]
    return Markup("".join(f"<p>{escape(p)}</p>" for p in paragraphes))


def qr_svg(lien: str) -> Markup:
    """Génère un QR code SVG inline, aux couleurs de la charte."""
    import segno

    return Markup(
        segno.make(lien, error="m").svg_inline(
            dark="#1b2b5a", border=1, svgclass=None, omitsize=True
        )
    )


def en_centimes(valeur: Any) -> int:
    """Convertit un montant YAML en euros vers des centimes entiers."""
    return round(float(valeur) * 100)


def euros_fr(centimes: int) -> str:
    """Formate 14860 centimes en « 148,60 »."""
    return f"{centimes // 100},{centimes % 100:02d}"


# ------------------------------------------------------------------- planning


def valider_planning(donnees: dict[str, Any]) -> list[str]:
    """Retourne la liste des erreurs de structure du planning."""
    erreurs: list[str] = []
    for cle in ("saison", "club", "note_globale", "creneaux", "tir_libre"):
        if cle not in donnees:
            erreurs.append(f"planning : clé racine manquante : {cle}")
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


def poids_contenu(c: dict[str, Any]) -> int:
    """Estime la place nécessaire à un créneau (longueur du texte affiché)."""
    return (
        len(c["intitule"])
        + len(c.get("detail") or "")
        + sum(len(e) + 2 for e in c["encadrants"])
        + 14  # horaire
    )


def repartir_couloirs(creneaux: list[dict[str, Any]]) -> list[tuple[float, float, int]]:
    """Répartit les créneaux qui se chevauchent en couloirs côte à côte.

    Retourne pour chaque créneau (gauche, largeur) en pourcentage de la
    colonne, et le nombre de couloirs de son groupe. Les largeurs sont
    proportionnelles au contenu, avec un plancher, pour qu'un créneau
    chargé ne soit pas étranglé par un créneau court.
    """
    plancher = 26.0
    resultats: list[tuple[float, float, int]] = [(0.0, 100.0, 1)] * len(creneaux)
    groupe: list[tuple[int, int]] = []  # (index créneau, index couloir)
    couloirs: list[int] = []  # minute de fin de chaque couloir
    fin_groupe = -1

    def clore_groupe() -> None:
        nb = len(couloirs)
        if not groupe:
            return
        if nb == 1:
            return  # valeurs par défaut déjà en place
        poids = [0] * nb
        for i, couloir in groupe:
            poids[couloir] = max(poids[couloir], poids_contenu(creneaux[i]))
        parts = [p / sum(poids) * 100 for p in poids]
        etroits = [k for k, p in enumerate(parts) if p < plancher]
        reste = 100 - plancher * len(etroits)
        total_larges = sum(p for k, p in enumerate(parts) if k not in etroits)
        parts = [
            plancher if k in etroits else p / total_larges * reste for k, p in enumerate(parts)
        ]
        gauches = [sum(parts[:k]) for k in range(nb)]
        for i, couloir in groupe:
            resultats[i] = (round(gauches[couloir], 3), round(parts[couloir], 3), nb)

    for i, c in enumerate(creneaux):
        debut, fin = en_minutes(c["debut"]), en_minutes(c["fin"])
        if debut >= fin_groupe:
            clore_groupe()
            groupe, couloirs = [], []
        affecte = next((k for k, libre in enumerate(couloirs) if libre <= debut), None)
        if affecte is None:
            affecte = len(couloirs)
            couloirs.append(fin)
        else:
            couloirs[affecte] = fin
        groupe.append((i, affecte))
        fin_groupe = max(fin_groupe, fin)

    clore_groupe()
    return resultats


def calculer_blocs(
    creneaux: list[dict[str, Any]], debut_grille: int, duree_grille: int
) -> list[dict[str, Any]]:
    """Calcule la position de chaque créneau en pourcentage de la grille horaire."""
    blocs = []
    for c, (gauche, largeur, nb) in zip(creneaux, repartir_couloirs(creneaux), strict=True):
        haut = (en_minutes(c["debut"]) - debut_grille) / duree_grille * 100
        hauteur = (en_minutes(c["fin"]) - en_minutes(c["debut"])) / duree_grille * 100
        blocs.append(
            {
                **c,
                "haut": round(haut, 3),
                "hauteur": round(hauteur, 3),
                "gauche": gauche,
                "largeur": largeur,
                "compact": nb > 1,
            }
        )
    return blocs


def contexte_planning(donnees: dict[str, Any]) -> dict[str, Any]:
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
        jours.append(
            {
                "nom": nom,
                "creneaux": creneaux,
                "blocs": calculer_blocs(creneaux, debut_grille, duree_grille),
                "tir_libre": donnees["tir_libre"].get(nom),
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
        "jours_grille": [j for j in jours if j["creneaux"]],
        "jours_hors_grille": [j for j in jours if not j["creneaux"] and j["tir_libre"]],
        "heures": heures,
        "nb_heures": duree_grille // 60,
    }


# --------------------------------------------------------------------- tarifs


def valider_tarifs(donnees: dict[str, Any]) -> list[str]:
    """Retourne la liste des erreurs de structure des tarifs."""
    erreurs: list[str] = []
    for cle in ("saison_tarifs", "part_compagnie", "remises_famille", "categories", "supplements"):
        if cle not in donnees:
            erreurs.append(f"tarifs : clé racine manquante : {cle}")
    if erreurs:
        return erreurs

    identifiants = [c.get("id") for c in donnees["categories"]]
    if len(identifiants) != len(set(identifiants)):
        erreurs.append("tarifs : identifiants de catégories non uniques")

    for c in donnees["categories"]:
        ref = f"catégorie {c.get('id', '?')}"
        for part in PARTS:
            try:
                if en_centimes(c.get(part)) < 0:
                    erreurs.append(f"{ref} : {part} négatif")
            except (TypeError, ValueError):
                erreurs.append(f"{ref} : {part} manquant ou non numérique")

    for rang, pct in donnees["remises_famille"].items():
        if not (isinstance(rang, int) and rang >= 2 and 0 < pct < 100):
            erreurs.append(f"tarifs : remise invalide pour le rang « {rang} » ({pct})")

    for s in donnees["supplements"]:
        for champ in ("titre", "libelle"):
            if not s.get(champ):
                erreurs.append(f"supplément {s.get('id', '?')} : {champ} manquant")
        try:
            if en_centimes(s.get("montant")) < 0:
                erreurs.append(f"supplément {s.get('id', '?')} : montant négatif")
        except (TypeError, ValueError):
            erreurs.append(f"supplément {s.get('id', '?')} : montant manquant ou non numérique")
    return erreurs


def contexte_tarifs(donnees: dict[str, Any]) -> dict[str, Any]:
    """Calcule les totaux et remises, en centimes, pour le tableau et le calculateur."""
    part_compagnie = en_centimes(donnees["part_compagnie"])
    remises = dict(sorted(donnees["remises_famille"].items()))

    lignes = []
    categories_js = []
    for c in donnees["categories"]:
        parts = {p: en_centimes(c[p]) for p in PARTS}
        hors_compagnie = sum(parts.values())
        seul = hors_compagnie + part_compagnie
        rangs = [
            euros_fr(hors_compagnie + part_compagnie - part_compagnie * pct // 100)
            for pct in remises.values()
        ]
        lignes.append(
            {
                **c,
                "ffta": euros_fr(parts["ffta"]),
                "evenement": euros_fr(parts["evenement_exceptionnel"]),
                "ligue": euros_fr(parts["ligue"]),
                "departement": euros_fr(parts["departement"]),
                "part_compagnie": euros_fr(part_compagnie),
                "seul": euros_fr(seul),
                "rangs": rangs,
            }
        )
        categories_js.append(
            {"id": c["id"], "libelle": c["libelle"], "hors_compagnie": hors_compagnie}
        )

    supplements = [
        {
            **s,
            "montant_fmt": euros_fr(en_centimes(s["montant"])),
        }
        for s in donnees["supplements"]
    ]
    supplements_js = [
        {
            "id": s["id"],
            "libelle_court": s.get("titre") or s["libelle"].split("—")[0].strip(),
            "montant": en_centimes(s["montant"]),
        }
        for s in donnees["supplements"]
    ]

    donnees_calculateur = json.dumps(
        {
            "part_compagnie": part_compagnie,
            "remises": {str(rang): pct for rang, pct in remises.items()},
            "categories": categories_js,
            "supplements": supplements_js,
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return {
        "totaux_categories": {
            c["id"]: sum(en_centimes(c[p]) for p in PARTS) + part_compagnie
            for c in donnees["categories"]
        },
        "saison_tarifs": donnees["saison_tarifs"],
        "part_compagnie_fmt": euros_fr(part_compagnie),
        "remises_famille": remises,
        "remise_max": max(remises.values()),
        "lignes_tarifs": lignes,
        "supplements": supplements,
        "donnees_calculateur": donnees_calculateur,
    }


def generer_pdf(source: Path, sortie: Path) -> None:
    """Rend une page HTML en PDF via WeasyPrint (importé par l'appelant)."""
    from weasyprint import HTML

    HTML(filename=str(source)).write_pdf(str(sortie))
    print(f"Généré : {sortie.relative_to(RACINE)}")


def verifier_styles(html: str, nom: str) -> list[str]:
    """Vérifie l'équilibre des accolades de chaque bloc <style> d'une page."""
    erreurs = []
    for i, bloc in enumerate(re.findall(r"<style>(.*?)</style>", html, re.S), start=1):
        if bloc.count("{") != bloc.count("}"):
            erreurs.append(
                f"{nom} : bloc <style> n°{i} déséquilibré "
                f"({bloc.count('{')} ouvrantes, {bloc.count('}')} fermantes)"
            )
    return erreurs


# ------------------------------------------------------------------ plaquette


def valider_plaquette(
    plq: dict[str, Any], planning: dict[str, Any], tarifs: dict[str, Any]
) -> list[str]:
    """Vérifie les références croisées de la plaquette vers planning et tarifs."""
    erreurs: list[str] = []
    for cle in ("accroche", "qu_est_ce", "presentation", "contacts", "reseaux", "groupes"):
        if cle not in plq:
            erreurs.append(f"plaquette : clé racine manquante : {cle}")
    if erreurs:
        return erreurs

    creneaux_connus = {(c["jour"], c["debut"]) for c in planning["creneaux"]}
    categories_connues = {c["id"] for c in tarifs["categories"]}

    for g in plq["groupes"]:
        ref = f"groupe {g.get('id', '?')}"
        for r in g.get("creneaux", []):
            if (r.get("jour"), r.get("debut")) not in creneaux_connus:
                erreurs.append(
                    f"{ref} : créneau introuvable dans le planning "
                    f"({r.get('jour')} {r.get('debut')})"
                )
        for licence in g.get("licences", []):
            if licence.get("categorie") not in categories_connues:
                erreurs.append(
                    f"{ref} : catégorie tarifaire inconnue « {licence.get('categorie')} »"
                )
        if "formation" in g and en_centimes(g["formation"]) < 0:
            erreurs.append(f"{ref} : formation négative")
    return erreurs


def contexte_plaquette(
    plq: dict[str, Any], planning: dict[str, Any], totaux: dict[str, int]
) -> dict[str, Any]:
    """Résout les références des groupes vers les créneaux et les coûts."""
    par_cle = {(c["jour"], c["debut"]): c for c in planning["creneaux"]}
    groupes = []
    for g in plq["groupes"]:
        formation = en_centimes(g.get("formation", 0))
        couts = [
            {
                "libelle": licence["libelle"],
                "montant": euros_fr(totaux[licence["categorie"]] + formation),
            }
            for licence in g.get("licences", [])
        ]
        groupes.append(
            {
                **g,
                "creneaux_resolus": [
                    par_cle[(r["jour"], r["debut"])] for r in g.get("creneaux", [])
                ],
                "couts": couts,
                "formation_fmt": euros_fr(formation) if formation else None,
            }
        )
    return {"plaquette": {**plq, "groupes": groupes}}


# ---------------------------------------------------------------------- build


def principal() -> int:
    """Point d'entrée : valide les deux sources, puis génère dist/."""
    planning = yaml.safe_load((RACINE / "data" / "planning.yaml").read_text(encoding="utf-8"))
    tarifs = yaml.safe_load((RACINE / "data" / "tarifs.yaml").read_text(encoding="utf-8"))
    plq = yaml.safe_load((RACINE / "data" / "plaquette.yaml").read_text(encoding="utf-8"))

    erreurs = (
        valider_planning(planning)
        + valider_tarifs(tarifs)
        + valider_plaquette(plq, planning, tarifs)
    )
    if erreurs:
        for erreur in erreurs:
            print(f"ERREUR : {erreur}", file=sys.stderr)
        return 1

    if "--check" in sys.argv:
        print(
            f"OK : {len(planning['creneaux'])} créneaux, "
            f"{len(tarifs['categories'])} catégories tarifaires"
        )
        return 0

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["heure_fr"] = heure_fr
    env.filters["texte_riche"] = texte_riche
    env.filters["qr_svg"] = qr_svg

    if (RACINE / "static").is_dir():
        shutil.copytree(RACINE / "static", DIST / "static", dirs_exist_ok=True)

    contexte_t = contexte_tarifs(tarifs)
    commun = {
        **contexte_planning(planning),
        **contexte_t,
        **contexte_plaquette(plq, planning, contexte_t["totaux_categories"]),
        "date_generation": date.today().strftime("%d/%m/%Y"),
        "logo_existe": (RACINE / "static" / "img" / "logo.jpg").is_file(),
        "pdf_planning": f"planning-{planning['saison']}.pdf",
        "pdf_plaquette": f"plaquette-{planning['saison']}.pdf",
        "label_existe": (RACINE / "static" / "img" / "label-ambition.png").is_file(),
        "pdf_disponible": importlib.util.find_spec("weasyprint") is not None,
    }

    for template, sortie in PAGES.items():
        profondeur = sortie.count("/")
        contexte = {
            **commun,
            "prefixe": "../" * profondeur,
            "page": sortie.split("/")[0].removesuffix(".html") or "accueil",
        }
        if contexte["page"] == "index":
            contexte["page"] = "accueil"
        destination = DIST / sortie
        destination.parent.mkdir(parents=True, exist_ok=True)
        html = env.get_template(template).render(contexte)
        problemes = verifier_styles(html, sortie)
        if problemes:
            for probleme in problemes:
                print(f"ERREUR : {probleme}", file=sys.stderr)
            return 1
        destination.write_text(html, encoding="utf-8")
        print(f"Généré : {destination.relative_to(RACINE)}")

    if commun["pdf_disponible"]:
        generer_pdf(
            DIST / "planning" / "paysage.html",
            DIST / "planning" / commun["pdf_planning"],
        )
        generer_pdf(
            DIST / "plaquette" / "index.html",
            DIST / "plaquette" / commun["pdf_plaquette"],
        )
    return 0


if __name__ == "__main__":
    sys.exit(principal())
