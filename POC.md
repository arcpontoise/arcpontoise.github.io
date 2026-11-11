# Maquette des versions du site

Démonstration temporaire pour choisir l'allure du futur site : le site actuel
et quatre pistes graphiques, sur toutes les pages. Elle peut être publiée sur
`https://arcpontoise.github.io/` pour être montrée au bureau, tant que
`arcpontoise.fr` sert encore le WordPress. **Elle doit être retirée avant la
bascule du domaine**, une fois la piste retenue intégrée proprement.

| Version | Esprit |
| --- | --- |
| Actuel | Le site tel qu'il est publié |
| A · Héritage | Couleurs de la charte, grande photo d'accueil en parallaxe |
| B · Sport | Fond bleu nuit, accent jaune, mise en page en tuiles |
| C · Éditorial | Fond blanc, grands titres, filets fins, ton magazine |
| D · Sport + Héritage | Tout le site en B ; en haut de l'accueil, la grande photo et les chiffres clés de A |

La version D répond au retour sur la maquette : l'allure B pour tout le site,
mais l'en-tête de l'accueil de A (photo, titre, chiffres clés), jugé moins
« fabriqué » que le bloc d'accueil de B. Elle n'a pas de feuille de style
propre au-delà de `static/css/poc-d.css`, qui recolore ce haut de page : toutes
les règles de B s'appliquent aussi à D.

Une barre en bas de chaque page change de version ; le choix est retenu d'une
page à l'autre. Un lien peut imposer une version, par exemple
`https://arcpontoise.github.io/?version=b`.

## Photos

Aucune photo de personne reconnaissable n'entre dans ce dépôt public :

- les photos d'archers de dos au crépuscule, sans visage reconnaissable,
  sont dans `static/images/` (`accueil-crepuscule.webp`,
  `terrain-crepuscule.webp`) ;
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

Version A : la photo d'accueil glisse moins vite que la page, la bande
« Mesdames, Messieurs, je vous salue » défile en parallaxe et les sections
apparaissent en fondu (aussi en version C). Tout est en CSS, sans
JavaScript : un navigateur qui ne gère pas ces effets, ou un visiteur qui a
demandé moins d'animations, voit la page immobile.

## Retirer la maquette

Supprimer `POC.md`, `static/js/poc-theme.js`, `static/css/poc-*.css`,
`static/fonts/space-grotesk-*` et `OFL-Space-Grotesk.txt` si ni B ni D ne
sont retenues, les lignes `poc` de `gabarits/base.html.j2` (feuilles
`poc-*.css` et script `poc-theme.js` ; et `'self'` dans `font-src` si plus
aucune police n'est servie par le site), puis rendre à
`gabarits/accueil.html.j2` la seule version retenue. Si D est retenue, ses
règles sont celles de `poc-b.css` et `poc-d.css`, à fondre dans la feuille du
site.
