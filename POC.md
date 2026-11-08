# Maquette des quatre versions du site

Démonstration temporaire pour choisir l'allure du futur site : le site actuel
et trois pistes graphiques, sur toutes les pages. Elle peut être publiée sur
`https://arcpontoise.github.io/` pour être montrée au bureau, tant que
`arcpontoise.fr` sert encore le WordPress. **Elle doit être retirée avant la
bascule du domaine**, une fois la piste retenue intégrée proprement.

| Version | Esprit |
| --- | --- |
| Actuel | Le site tel qu'il est publié |
| A · Héritage | Couleurs de la charte, grande photo d'accueil en parallaxe |
| B · Sport | Fond bleu nuit, accent jaune, mise en page en tuiles |
| C · Éditorial | Fond blanc, grands titres, filets fins, ton magazine |

Une barre en bas de chaque page change de version ; le choix est retenu d'une
page à l'autre. Un lien peut imposer une version, par exemple
`https://arcpontoise.github.io/?version=b`.

## Photos

Aucune photo de personne n'entre dans ce dépôt public :

- la photo d'accueil est celle du WordPress actuel (une archère de dos), en
  deux calques comme dans le thème Hestia : `static/images/accueil-*.webp` ;
- toutes les autres sont les **couvertures des galeries publiées dans drop**,
  lues en direct par le composant `<arc-couverture>`
  (`static/js/arc-galerie.js`). La couverture est la première photo de la
  galerie : changer l'ordre dans l'administration de drop change l'image.
  Les cartes d'actualités prennent la couverture de la galerie de l'article.

## Essai en local ou sur le réseau local

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
SITE_URL="http://$(hostname).local:8000" python scripts/build.py
(cd dist && python3 -m http.server 8000)
```

`SITE_URL` garde les liens du menu commun sur la maquette (adresses en
`https://`, `localhost`, adresses privées et noms du réseau local acceptés,
voir le README de la charte).

## Effets au défilement

Version A : les deux calques de la photo d'accueil glissent à des vitesses
différentes, la bande « Mesdames, Messieurs, je vous salue » défile en
parallaxe et les sections apparaissent en fondu (aussi en version C). Tout est
en CSS, sans JavaScript : un navigateur qui ne gère pas ces effets, ou un
visiteur qui a demandé moins d'animations, voit la page immobile.

## Retirer la maquette

Supprimer `POC.md`, `static/js/poc-theme.js`, `static/css/poc-*.css`,
`static/fonts/space-grotesk-*` et `OFL-Space-Grotesk.txt` si la piste B n'est
pas retenue, les trois lignes `poc` de `gabarits/base.html.j2` (et `'self'`
dans `font-src` si plus aucune police n'est servie par le site), puis rendre à
`gabarits/accueil.html.j2` la seule version retenue.
