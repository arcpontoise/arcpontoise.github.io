# Site vitrine de la Compagnie d'archers de Pontoise

Site public de la compagnie, futur `arcpontoise.fr` : présentation, pratiques,
actualités, encadrants, questions fréquentes, galeries photo. Il remplace le
site WordPress.

Le site est généré par `scripts/build.py` (Python, Jinja2, Markdown) puis
publié sur GitHub Pages par la CI. Il ne contient aucun code exécuté côté
serveur.

## Ce qui vient d'ailleurs

| Élément | Source | Mise à jour |
| --- | --- | --- |
| Couleurs, polices, en-tête, menu commun | [charte](https://github.com/arcpontoise/charte), chargée depuis `https://charte.arcpontoise.fr` | En direct, sans rebuild |
| Galeries photo | Administration de drop, lues depuis `https://photos.arcpontoise.fr` | En direct, sans rebuild |
| Formulaire de contact | drop, `https://contact.arcpontoise.fr` | Lien dans le menu |
| Planning, tarifs, plaquette | [infos](https://github.com/arcpontoise/infos) | Lien dans le menu |
| Palmarès | [palmares](https://github.com/arcpontoise/palmares) | Lien dans le menu |

## Arborescence

| Chemin | Rôle |
| --- | --- |
| `contenu/pages/*.md` | Pages fixes (accueil, histoire, pratiques...) |
| `contenu/articles/AAAA-MM-JJ-slug/` | Un article : `index.md` et ses fichiers (images, PDF) |
| `donnees/equipe.yaml` | Encadrants (page `/team/`) |
| `donnees/faq.yaml` | Questions fréquentes |
| `donnees/redirections.yaml` | Anciennes adresses WordPress vers les nouvelles |
| `gabarits/` | Gabarits Jinja2 des pages |
| `static/` | Feuille de style, composant des galeries, illustrations |
| `scripts/build.py` | Génération et validation du site |

## Rédiger un article

1. Créer une branche : `git switch main && git pull && git switch -c article/titre-court`.
2. Créer le dossier `contenu/articles/AAAA-MM-JJ-titre-court/` (date de
   publication, puis l'adresse de l'article en minuscules et tirets) et son
   fichier `index.md` :

   ```markdown
   ---
   titre: Championnat départemental salle
   date: 2026-05-14
   resume: Trois podiums pour la compagnie à Osny.
   galerie: 2026-championnat-departemental
   ---

   Texte de l'article en Markdown...

   ## Un intertitre

   Un [lien](https://contact.arcpontoise.fr/), une liste :

   - premier point ;
   - second point.
   ```

3. Vérifier en local (voir plus bas), puis pousser la branche et ouvrir une
   pull request. Une fois le contrôle `lint` au vert, la fusion publie
   l'article.

L'article est publié à l'adresse `/articles/titre-court/`, apparaît sur la
page d'accueil, dans la liste des actualités et dans le flux
`/articles/flux.xml`.

### Champs de l'en-tête

| Champ | Obligatoire | Rôle |
| --- | --- | --- |
| `titre` | oui | Titre de l'article |
| `date` | oui | Date de publication, identique à celle du nom du dossier |
| `resume` | non | Résumé des listes et du flux ; à défaut, début du premier paragraphe |
| `galerie` | non | Adresse d'une galerie publiée dans drop, affichée sous l'article |
| `image` | non | Illustration en tête d'article, fichier du dossier de l'article |
| `brouillon` | non | `true` : l'article n'est pas publié |

Le HTML brut n'est pas interprété : tout s'écrit en Markdown (gras, liens,
listes, tableaux, notes de bas de page `[^1]`).

### Photos et images

- **Photos de personnes** (concours, événements, jeunes) : jamais dans ce
  dépôt. Elles sont publiées en galerie depuis l'administration de drop, puis
  affichées sous l'article avec le champ `galerie`. Un dépôt Git public garde
  tout fichier dans son historique : une photo ne pourrait plus en être
  retirée à la demande d'une personne photographiée.
- **Illustrations sans personne** (plan, affiche, schéma, logo) : dans le
  dossier de l'article, en JPEG, PNG ou WebP de taille raisonnable (moins
  de 300 Ko), sans métadonnées. Les insérer avec `![description](fichier.jpg)`.
- Les documents (mandat de concours en PDF...) se placent aussi dans le
  dossier de l'article et se lient par leur nom : `[mandat](mandat.pdf)`.

## Pages, encadrants, questions fréquentes

- Une page de `contenu/pages/` déclare son adresse (`url`), l'entrée du menu
  commun mise en évidence (`menu` : `accueil`, `compagnie`, `pratiquer`...)
  et, si besoin, un `gabarit` particulier (`accueil`, `equipe`, `faq`,
  `articles`, `galeries`).
- Les encadrants et les questions fréquentes se modifient dans `donnees/`.
- Supprimer ou renommer une page impose d'ajouter son ancienne adresse dans
  `donnees/redirections.yaml`.

## Vérifier en local

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python scripts/build.py --check       # validate the content only
python scripts/build.py               # generate dist/
(cd dist && python3 -m http.server 8000)
```

Le site est alors visible sur <http://localhost:8000/>. La validation refuse
notamment un en-tête incomplet, une date différente de celle du dossier, un
fichier lié introuvable ou une redirection vers une page inexistante.

Contrôles lancés par la CI (job `lint`, obligatoire avant fusion) :

```bash
yamllint .
ruff check scripts && ruff format --check scripts
python scripts/build.py --check
npm ci && npm run lint:css && npm run lint:js && npm run lint:md
```

## Sécurité

- **Aucun code serveur** ; le contenu est du Markdown sans HTML brut.
- **Politique de sécurité du contenu** (balise `meta` de chaque page) : seuls
  ce site, la charte et l'hôte des galeries sont autorisés ; aucun script ni
  style en ligne.
- **Composant des galeries** (`static/js/arc-galerie.js`) : construit la
  page avec les fonctions du navigateur, sans jamais interpréter de HTML venu
  des listes JSON.
- **Aucun cookie, aucun traceur** : voir la page des mentions légales.

## Bascule de `arcpontoise.fr`

Le site est d'abord publié sur `https://arcpontoise.github.io/`, à côté du
WordPress. Le jour de la bascule (étapes 2 et 3 au même moment : dès que le
domaine est déclaré, `arcpontoise.github.io` redirige vers `arcpontoise.fr`) :

1. Remplacer `SITE_URL` par `https://arcpontoise.fr` dans
   `.github/workflows/deploy.yml`.
2. Dans les réglages Pages du dépôt, déclarer le domaine `arcpontoise.fr` ;
   le palmarès passe alors automatiquement à `arcpontoise.fr/palmares/`.
3. Faire pointer le DNS de `arcpontoise.fr` vers GitHub Pages (enregistrements
   A et AAAA de l'apex, `www` en CNAME), en gardant les enregistrements de
   messagerie (MX, SPF, DKIM).
4. Mettre à jour les liens du menu commun (`menu.yaml` de la charte) qui
   pointent vers `arcpontoise.github.io/palmares/`.
