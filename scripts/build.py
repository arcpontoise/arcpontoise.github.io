"""Génère le site vitrine de la Compagnie d'archers de Pontoise dans dist/.

Sources :
- contenu/pages/*.md : pages fixes (en-tête YAML : titre, url, menu, gabarit...) ;
- contenu/articles/AAAA-MM-JJ-slug/index.md : articles, avec leurs fichiers
  (images, PDF) dans le même dossier ;
- donnees/*.yaml : encadrants, foire aux questions, Roy et bureau, redirections ;
- static/ : feuille de style et scripts propres au site.

La charte graphique (CSS, polices, menu commun) est chargée en direct depuis
CHARTE_URL ; les galeries photo sont lues en direct depuis GALERIES_URL.
La mesure d'audience (Matomo) est autorisée sur STATS_URL, la même adresse
que dans static/js/stats.js.

Usage :
    python scripts/build.py            # génère dist/
    python scripts/build.py --check    # valide le contenu sans rien écrire
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from xml.sax.saxutils import escape

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markdown_it import MarkdownIt
from markupsafe import Markup
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.footnote import footnote_plugin

RACINE = Path(__file__).resolve().parent.parent
CONTENU = RACINE / "contenu"
DONNEES = RACINE / "donnees"
GABARITS = RACINE / "gabarits"
STATIC = RACINE / "static"
DIST = RACINE / "dist"

SITE_URL = os.environ.get("SITE_URL", "https://arcpontoise.fr").rstrip("/")
CHARTE = os.environ.get("CHARTE_URL", "https://charte.arcpontoise.fr").rstrip("/")
GALERIES = os.environ.get("GALERIES_URL", "https://photos.arcpontoise.fr").rstrip("/")
STATS = os.environ.get("STATS_URL", "https://stats.arcpontoise.fr").rstrip("/")

MENU_IDS = {"accueil", "compagnie", "pratiquer", "inscrire", "competitions", "archers", "contact"}
GABARITS_PAGE = {
    "page", "accueil", "equipe", "faq", "articles", "galeries",
    "rubrique", "frise", "roys", "acces",
}  # fmt: skip
DOSSIER_ARTICLE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([a-z0-9][a-z0-9-]*)$")
SLUG_GALERIE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
URL_PAGE = re.compile(r"^/(?:[a-z0-9][a-z0-9-]*/)*$")
IMAGE_PAGE = re.compile(r"^/images/[a-z0-9][a-z0-9-]*\.(?:webp|jpg|png|svg)$")
CHAMPS_PAGE = {
    "titre", "url", "menu", "description", "gabarit", "ordre", "galerie", "image", "cartes",
}  # fmt: skip
ROLES_BUREAU = ("capitaine", "secretaire", "tresorier", "porte_drapeau")
CHAMPS_CARTE = {"titre", "latitude", "longitude", "adresse", "texte"}
CHAMPS_ARTICLE = {"titre", "date", "resume", "image", "galerie", "brouillon"}
TAILLE_RESUME = 220


class ErreurContenu(ValueError):
    """Contenu invalide : message affiché tel quel."""


def slugify(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-")


def creer_markdown() -> MarkdownIt:
    # Raw HTML is disabled: the content is plain Markdown only
    md = MarkdownIt("commonmark", {"html": False, "typographer": False, "linkify": False})
    md.enable(["table", "strikethrough"])
    md.use(footnote_plugin)
    md.use(anchors_plugin, min_level=2, max_level=4, slug_func=slugify)
    return md


MARKDOWN = creer_markdown()


def rendre(texte: str) -> Markup:
    return Markup(MARKDOWN.render(texte))  # noqa: S704 - HTML produced by markdown-it, raw HTML disabled


def texte_brut(texte: str) -> str:
    """Plain text of some Markdown, for summaries and feeds."""
    rendu = MARKDOWN.render(texte)
    rendu = re.sub(r'<sup class="footnote-ref">.*?</sup>', "", rendu)
    brut = html.unescape(re.sub(r"<[^>]+>", " ", rendu))
    return re.sub(r"\s+", " ", brut).strip()


def resumer(texte: str) -> str:
    premier = next(
        (bloc for bloc in texte.split("\n\n") if bloc.strip() and not bloc.startswith("#")), ""
    )
    brut = texte_brut(premier)
    if len(brut) <= TAILLE_RESUME:
        return brut
    coupe = brut[:TAILLE_RESUME].rsplit(" ", 1)[0]
    return f"{coupe.rstrip(',;:')}…"


def lire_markdown(chemin: Path) -> tuple[dict[str, Any], str]:
    texte = chemin.read_text(encoding="utf-8")
    if not texte.startswith("---\n"):
        raise ErreurContenu(f"{chemin} : en-tête YAML (---) manquant")
    try:
        _, entete, corps = texte.split("---\n", 2)
        meta = yaml.safe_load(entete) or {}
    except (ValueError, yaml.YAMLError) as exc:
        raise ErreurContenu(f"{chemin} : en-tête YAML invalide ({exc})") from exc
    if not isinstance(meta, dict):
        raise ErreurContenu(f"{chemin} : l'en-tête doit être une liste de champs")
    return meta, corps.strip() + "\n"


def texte_requis(meta: dict, champ: str, ou: Path) -> str:
    valeur = meta.get(champ)
    if not isinstance(valeur, str) or not valeur.strip():
        raise ErreurContenu(f"{ou} : champ « {champ} » obligatoire")
    return valeur.strip()


@dataclass
class Page:
    source: Path
    titre: str
    url: str
    menu: str
    gabarit: str
    description: str
    corps: str
    ordre: int = 100
    galerie: str | None = None
    image: str | None = None
    cartes: list[dict] = field(default_factory=list)


@dataclass
class Article:
    source: Path
    slug: str
    titre: str
    date: dt.date
    resume: str
    corps: str
    image: str | None
    galerie: str | None
    brouillon: bool
    fichiers: list[Path] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"/articles/{self.slug}/"


def lire_pages() -> list[Page]:
    pages = []
    for chemin in sorted((CONTENU / "pages").glob("*.md")):
        meta, corps = lire_markdown(chemin)
        inconnus = set(meta) - CHAMPS_PAGE
        if inconnus:
            raise ErreurContenu(f"{chemin} : champs inconnus {sorted(inconnus)}")
        url = texte_requis(meta, "url", chemin)
        if not URL_PAGE.match(url):
            raise ErreurContenu(f"{chemin} : url « {url} » invalide (ex. /pratiquer/parcours/)")
        menu = texte_requis(meta, "menu", chemin)
        if menu not in MENU_IDS:
            raise ErreurContenu(
                f"{chemin} : menu « {menu} » inconnu ({', '.join(sorted(MENU_IDS))})"
            )
        gabarit = meta.get("gabarit", "page")
        if gabarit not in GABARITS_PAGE:
            raise ErreurContenu(f"{chemin} : gabarit « {gabarit} » inconnu")
        titre = texte_requis(meta, "titre", chemin)
        description = str(meta.get("description") or "").strip() or resumer(corps)
        ordre = meta.get("ordre", 100)
        if not isinstance(ordre, int):
            raise ErreurContenu(f"{chemin} : « ordre » est un nombre entier")
        galerie = meta.get("galerie")
        if galerie is not None and not SLUG_GALERIE.match(str(galerie)):
            raise ErreurContenu(f"{chemin} : galerie « {galerie} » invalide")
        image = meta.get("image")
        if image is not None:
            image = str(image)
            if not IMAGE_PAGE.match(image) or not (STATIC / image.lstrip("/")).is_file():
                raise ErreurContenu(f"{chemin} : image « {image} » introuvable dans static/images/")
        cartes = lire_cartes(meta.get("cartes") or [], chemin)
        pages.append(
            Page(
                chemin,
                titre,
                url,
                menu,
                gabarit,
                description,
                corps,
                ordre,
                str(galerie) if galerie else None,
                image,
                cartes,
            )  # fmt: skip
        )
    urls = [p.url for p in pages]
    doublons = {u for u in urls if urls.count(u) > 1}
    if doublons:
        raise ErreurContenu(f"pages : plusieurs pages pour {sorted(doublons)}")
    return pages


def lire_cartes(cartes: Any, chemin: Path) -> list[dict]:
    """Places of a page (plan d'accès): title, coordinates, address and Markdown text."""
    if not isinstance(cartes, list):
        raise ErreurContenu(f"{chemin} : « cartes » est une liste")
    for carte in cartes:
        if not isinstance(carte, dict) or set(carte) - CHAMPS_CARTE:
            raise ErreurContenu(f"{chemin} : carte invalide, champs {sorted(CHAMPS_CARTE)}")
        texte_requis(carte, "titre", chemin)
        for axe, limite in (("latitude", 90), ("longitude", 180)):
            valeur = carte.get(axe)
            if not isinstance(valeur, (int, float)) or not -limite <= valeur <= limite:
                raise ErreurContenu(f"{chemin} : « {axe} » de la carte invalide")
        carte["html"] = rendre(str(carte.get("texte") or ""))
    return cartes


def sous_pages(page: Page, pages: list[Page]) -> list[Page]:
    """Direct children of a page, from their URL, in their « ordre »."""
    enfants = [
        p
        for p in pages
        if p.url.startswith(page.url) and p.url.count("/") == page.url.count("/") + 1
    ]
    return sorted(enfants, key=lambda p: (p.ordre, p.titre))


def lire_articles() -> list[Article]:
    articles = []
    for dossier in sorted((CONTENU / "articles").iterdir()):
        if not dossier.is_dir():
            continue
        nom = DOSSIER_ARTICLE.match(dossier.name)
        if not nom:
            raise ErreurContenu(
                f"{dossier} : le dossier doit s'appeler AAAA-MM-JJ-titre-en-minuscules"
            )
        chemin = dossier / "index.md"
        if not chemin.is_file():
            raise ErreurContenu(f"{dossier} : fichier index.md manquant")
        meta, corps = lire_markdown(chemin)
        inconnus = set(meta) - CHAMPS_ARTICLE
        if inconnus:
            raise ErreurContenu(f"{chemin} : champs inconnus {sorted(inconnus)}")
        date = meta.get("date")
        if not isinstance(date, dt.date) or date.isoformat() != nom.group(1):
            raise ErreurContenu(
                f"{chemin} : « date » doit valoir {nom.group(1)}, comme le nom du dossier"
            )
        image = meta.get("image")
        if image is not None and not (dossier / str(image)).is_file():
            raise ErreurContenu(f"{chemin} : image « {image} » introuvable dans le dossier")
        galerie = meta.get("galerie")
        if galerie is not None and not SLUG_GALERIE.match(str(galerie)):
            raise ErreurContenu(f"{chemin} : galerie « {galerie} » invalide")
        brouillon = meta.get("brouillon", False)
        if not isinstance(brouillon, bool):
            raise ErreurContenu(f"{chemin} : « brouillon » vaut true ou false")
        for cible in re.findall(r"\]\((?!https?://|mailto:|/|#)([^)\s]+)\)", corps):
            if not (dossier / cible.split("#")[0]).is_file():
                raise ErreurContenu(f"{chemin} : fichier « {cible} » introuvable dans le dossier")
        resume = str(meta.get("resume") or "").strip() or resumer(corps)
        fichiers = [f for f in sorted(dossier.iterdir()) if f.is_file() and f.name != "index.md"]
        articles.append(
            Article(
                chemin,
                nom.group(2),
                texte_requis(meta, "titre", chemin),
                date,
                resume,
                corps,
                str(image) if image else None,
                str(galerie) if galerie else None,
                brouillon,
                fichiers,
            )
        )
    slugs = [a.slug for a in articles]
    doublons = {s for s in slugs if slugs.count(s) > 1}
    if doublons:
        raise ErreurContenu(f"articles : plusieurs articles pour {sorted(doublons)}")
    return sorted(articles, key=lambda a: (a.date, a.slug), reverse=True)


def lire_yaml(nom: str) -> Any:
    return yaml.safe_load((DONNEES / nom).read_text(encoding="utf-8"))


def lire_equipe() -> list[dict]:
    equipe = lire_yaml("equipe.yaml") or []
    for membre in equipe:
        if not isinstance(membre, dict) or not str(membre.get("nom", "")).strip():
            raise ErreurContenu("donnees/equipe.yaml : chaque encadrant a un « nom »")
        lignes = str(membre.get("presentation", "")).strip().splitlines()
        membre["points"] = [
            rendre(ligne).removeprefix("<p>").removesuffix("</p>\n") for ligne in lignes
        ]
        membre["ancre"] = slugify(membre["nom"])
        membre["initiales"] = "".join(mot[0] for mot in membre["nom"].split()[:2]).upper()
    return equipe


def lire_faq() -> list[dict]:
    faq = lire_yaml("faq.yaml") or []
    for entree in faq:
        if not entree.get("question") or not entree.get("reponse"):
            raise ErreurContenu(
                "donnees/faq.yaml : chaque entrée a une « question » et une « reponse »"
            )
        entree["html"] = rendre(entree["reponse"])
        entree["ancre"] = slugify(entree["question"])
    return faq


def lire_roys() -> list[dict]:
    """Roy and bureau of the compagnie, grouped by decade (page /les-roy-et-le-bureau/).

    The bureau of a year is flagged « inchange » when it is the same as the
    previous year's, so the page only details the changes.
    """
    decennies: list[dict] = []
    precedent = None
    for entree in lire_yaml("roys.yaml") or []:
        if not isinstance(entree, dict):
            raise ErreurContenu("donnees/roys.yaml : chaque entrée est une liste de champs")
        if "annee" in entree:
            annee = entree["annee"]
            for champ in ("date", "roy", "roitelet", "petit_prince", *ROLES_BUREAU):
                entree.setdefault(champ, "")
            bureau = tuple(entree[c] for c in ROLES_BUREAU)
            entree["inchange"] = bureau == precedent
            precedent = bureau
        elif entree.get("evenement"):
            trouve = re.search(r"\d{4}", str(entree["evenement"]))
            if not trouve:
                raise ErreurContenu(f"donnees/roys.yaml : année introuvable dans {entree}")
            annee = int(trouve.group())
            entree["lignes"] = str(entree.get("texte") or "").strip().splitlines()
            entree["annee"] = None
        else:
            raise ErreurContenu(
                "donnees/roys.yaml : chaque entrée a une « annee » ou un « evenement »"
            )
        if not isinstance(annee, int):
            raise ErreurContenu(f"donnees/roys.yaml : année invalide {annee!r}")
        titre = f"Années {annee // 10 * 10}"
        if not decennies or decennies[-1]["titre"] != titre:
            decennies.append({"titre": titre, "ancre": slugify(titre), "entrees": []})
        decennies[-1]["entrees"].append(entree)
    return decennies


def lire_redirections(pages: list[Page], articles: list[Article]) -> dict[str, str]:
    redirections = lire_yaml("redirections.yaml") or {}
    connues = {p.url for p in pages} | {a.url for a in articles} | {"/articles/"}
    for ancienne, nouvelle in redirections.items():
        if not URL_PAGE.match(ancienne):
            raise ErreurContenu(f"redirections.yaml : « {ancienne} » doit être un chemin /.../")
        if ancienne in connues:
            raise ErreurContenu(f"redirections.yaml : « {ancienne} » est une page existante")
        cible = nouvelle.split("#")[0]
        if not nouvelle.startswith("https://") and cible not in connues:
            raise ErreurContenu(f"redirections.yaml : cible « {nouvelle} » inconnue")
    return redirections


def ecrire(chemin: Path, contenu: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")


def date_fr(jour: dt.date) -> str:
    mois = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]  # fmt: skip
    return f"{jour.day}{'er' if jour.day == 1 else ''} {mois[jour.month - 1]} {jour.year}"


def fil_ariane(url: str, pages_par_url: dict[str, Page]) -> list[tuple[str, str]]:
    """Parent pages of a page, from its URL (/pratiquer/tir-en-salle/ -> Pratiquer)."""
    parties = url.strip("/").split("/")[:-1]
    fil = []
    for i in range(1, len(parties) + 1):
        parent = "/" + "/".join(parties[:i]) + "/"
        if parent in pages_par_url:
            fil.append((parent, pages_par_url[parent].titre))
    return fil


def flux_atom(articles: list[Article], maintenant: dt.datetime) -> str:
    entrees = []
    for article in articles[:20]:
        url = SITE_URL + article.url
        publie = dt.datetime.combine(article.date, dt.time(12), dt.UTC).isoformat()
        entrees.append(
            f"<entry><title>{escape(article.titre)}</title>"
            f'<link href="{url}"/><id>{url}</id>'
            f"<updated>{publie}</updated><published>{publie}</published>"
            f"<summary>{escape(article.resume)}</summary></entry>"
        )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="fr">'
        "<title>Compagnie d'archers de Pontoise - Actualités</title>"
        f'<link href="{SITE_URL}/articles/"/>'
        f'<link rel="self" href="{SITE_URL}/articles/flux.xml"/>'
        f"<id>{SITE_URL}/articles/</id>"
        f"<updated>{maintenant.isoformat()}</updated>"
        "<author><name>Compagnie d'archers de Pontoise</name></author>"
        + "".join(entrees)
        + "</feed>\n"
    )


def plan_xml(urls: list[str]) -> str:
    lignes = "".join(f"<url><loc>{escape(SITE_URL + u)}</loc></url>" for u in urls)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{lignes}</urlset>\n'
    )


def generer() -> int:
    pages = lire_pages()
    articles = lire_articles()
    publies = [a for a in articles if not a.brouillon]
    equipe = lire_equipe()
    roys = lire_roys()
    faq = lire_faq()
    redirections = lire_redirections(pages, publies)
    if "--check" in sys.argv:
        print(
            f"OK : {len(pages)} pages, {len(publies)} articles publiés, "
            f"{len(redirections)} redirections"
        )
        return 0

    env = Environment(
        loader=FileSystemLoader(GABARITS),
        undefined=StrictUndefined,
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["date_fr"] = date_fr
    commun = {
        "charte": CHARTE,
        "galeries": GALERIES,
        "stats": STATS,
        "site_url": SITE_URL,
        "annee": dt.date.today().year,
    }
    pages_par_url = {p.url: p for p in pages}

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(STATIC, DIST)

    def page_html(gabarit: str, url: str, **contexte: Any) -> None:
        html = env.get_template(gabarit).render(**commun, url=url, **contexte)
        ecrire(DIST / url.lstrip("/") / "index.html", html)

    for page in pages:
        page_html(
            f"{page.gabarit}.html.j2",
            page.url,
            page=page,
            contenu=rendre(page.corps),
            fil=fil_ariane(page.url, pages_par_url),
            articles=publies,
            equipe=equipe,
            roys=roys,
            enfants=sous_pages(page, pages),
            faq=faq,
        )

    for article in publies:
        page_html("article.html.j2", article.url, article=article, contenu=rendre(article.corps))
        for fichier in article.fichiers:
            shutil.copy2(fichier, DIST / "articles" / article.slug / fichier.name)

    for ancienne, nouvelle in redirections.items():
        # Site-relative target: the redirect works on any domain (preview or final)
        html = env.get_template("redirection.html.j2").render(
            **commun, cible=nouvelle, canonique=urljoin(SITE_URL, nouvelle)
        )
        ecrire(DIST / ancienne.lstrip("/") / "index.html", html)

    ecrire(DIST / "404.html", env.get_template("404.html.j2").render(**commun, url="/404.html"))
    maintenant = dt.datetime.now(dt.UTC).replace(microsecond=0)
    ecrire(DIST / "articles" / "flux.xml", flux_atom(publies, maintenant))
    ecrire(DIST / "sitemap.xml", plan_xml([p.url for p in pages] + [a.url for a in publies]))
    ecrire(DIST / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    brouillons = len(articles) - len(publies)
    print(
        f"Généré : {len(pages)} pages, {len(publies)} articles"
        + (f" ({brouillons} brouillon(s) ignoré(s))" if brouillons else "")
        + f", {len(redirections)} redirections"
    )
    return 0


def principal() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="valider le contenu sans rien écrire")
    parser.parse_args()
    try:
        return generer()
    except ErreurContenu as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(principal())
