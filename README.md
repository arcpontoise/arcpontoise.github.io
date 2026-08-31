# Site d'informations — Compagnie d'archers de Pontoise

Génération du planning hebdomadaire des créneaux à partir d'une source unique
en YAML, publiée sur GitHub Pages à chaque poussée sur `main`.

## Principe

- `data/planning.yaml` et `data/tarifs.yaml` sont les **seules sources
  de vérité**. Aucun total tarifaire n'y est saisi : `build.py` les
  calcule (en centimes) à partir du détail des parts et des remises,
  ce qui rend les erreurs d'addition impossibles. Le document transmis
  chaque saison par le capitaine est transcrit ici, puis tout le reste est
  généré.
- `scripts/build.py` valide la structure (jours, horaires, publics) puis génère
  deux pages dans `dist/` depuis la même source :
  - `index.html` (`templates/liste.html.j2`) : vue liste par jour, adaptée aux
    téléphones ;
  - `paysage.html` (`templates/paysage.html.j2`) : grille horaire de la
    semaine, jours en colonnes, pour grand écran et impression. Les créneaux
    simultanés d'une même journée sont automatiquement placés côte à côte.
- Le workflow `.github/workflows/deploy.yml` lint (`yamllint`, `ruff`),
  construit et déploie sur GitHub Pages.

## Mise à jour d'une saison

1. Créer une branche.
2. Modifier `data/planning.yaml` (créneaux, encadrants, tir libre).
3. Vérifier en local :

   ```bash
   pip install -r requirements.txt
   python scripts/build.py --check
   python scripts/build.py
   ```

4. Ouvrir `dist/index.html` dans un navigateur pour contrôle visuel.
5. Fusionner : le déploiement est automatique.

## Structure des données

Chaque créneau comporte : `jour`, `debut`, `fin` (format `HH:MM`), `intitule`,
`public` (`jeunes`, `adultes` ou `tous`), `encadrants` (liste, éventuellement
vide) et un `detail` facultatif. Le tir libre est décrit par une phrase par
jour dans la table `tir_libre`.

Toute entrée invalide fait échouer la construction : le planning publié ne peut
pas être structurellement incohérent.

## Impression

La vue paysage comporte un mode impression A4 paysage : `Ctrl+P` depuis
`paysage.html` produit la version à afficher en salle d'armes.

## Activation de GitHub Pages

Dans les réglages du dépôt : *Settings → Pages → Build and deployment*, choisir
**GitHub Actions** comme source. Le premier déploiement crée l'environnement
`github-pages`.
