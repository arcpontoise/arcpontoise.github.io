// Photo galleries of the club, read live from the galleries host (drop).
//
// <arc-galerie source="https://photos.arcpontoise.fr" galerie="2024-ecouen">
//   shows one gallery: thumbnails, then a full-size viewer (<dialog>).
// <arc-galeries source="https://photos.arcpontoise.fr">
//   lists the published galleries; each links to ?galerie=<slug> on the
//   same page, which then shows that gallery.
// <arc-couverture source="https://photos.arcpontoise.fr" galerie="2024-ecouen">
//   shows the cover of one gallery (see below).
//
// The DOM is built with createElement/textContent only: titles, texts and
// file names from the JSON never go through innerHTML.

(() => {
  "use strict";

  const SLUG = /^[a-z0-9][a-z0-9-]{0,79}$/;
  const FILE = /^[a-z0-9][a-z0-9_-]{0,119}\.webp$/;

  function el(tag, attributes = {}, children = []) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attributes)) {
      node.setAttribute(name, value);
    }
    node.append(...children);
    return node;
  }

  function formatDate(iso) {
    const date = new Date(`${iso}T12:00:00`);
    return Number.isNaN(date.getTime())
      ? ""
      : date.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
  }

  async function fetchJson(url) {
    const response = await fetch(url, { credentials: "omit" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }

  function image(base, rendition, alt, loading = "lazy") {
    if (!rendition || !FILE.test(rendition.fichier)) {
      return null;
    }
    return el("img", {
      src: `${base}/${rendition.fichier}`,
      alt: alt || "",
      width: String(rendition.largeur),
      height: String(rendition.hauteur),
      loading,
      decoding: "async",
    });
  }

  function viewer(base, photos) {
    const picture = el("img", { alt: "" });
    const counter = el("span", { "aria-live": "polite" });
    const previous = el("button", { type: "button" }, ["Précédente"]);
    const next = el("button", { type: "button" }, ["Suivante"]);
    const close = el("button", { type: "button" }, ["Fermer"]);
    const dialog = el("dialog", { class: "galerie-visionneuse", "aria-label": "Photo en grand" }, [
      picture,
      el("div", { class: "galerie-commandes" }, [previous, counter, next, close]),
    ]);
    let index = 0;

    function show(position) {
      index = (position + photos.length) % photos.length;
      const photo = photos[index];
      picture.src = `${base}/${photo.image.fichier}`;
      picture.alt = photo.alt || "";
      counter.textContent = `${index + 1} / ${photos.length}`;
    }

    previous.addEventListener("click", () => show(index - 1));
    next.addEventListener("click", () => show(index + 1));
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") show(index - 1);
      if (event.key === "ArrowRight") show(index + 1);
    });
    // Click on the backdrop closes the viewer
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    return { dialog, open: (position) => { show(position); dialog.showModal(); } };
  }

  async function renderGallery(host, source, slug, withTitle) {
    const base = `${source}/${slug}`;
    const data = await fetchJson(`${base}/galerie.json`);
    const photos = (data.photos || []).filter((p) => p.image && FILE.test(p.image.fichier));
    const { dialog, open } = viewer(base, photos);
    const grid = el("div", { class: "galerie-grille" });
    photos.forEach((photo, position) => {
      const thumbnail = image(base, photo.vignette, photo.alt);
      if (!thumbnail) return;
      const button = el("button", { type: "button", "aria-label": `Agrandir la photo ${position + 1}` }, [
        thumbnail,
      ]);
      button.addEventListener("click", () => open(position));
      grid.append(button);
    });
    const parts = [];
    if (withTitle) {
      parts.push(el("h2", {}, [data.titre || ""]));
      parts.push(el("p", { class: "discret" }, [formatDate(data.date)]));
      if (data.texte) parts.push(el("p", {}, [data.texte]));
    }
    host.replaceChildren(...parts, grid, dialog);
  }

  function unavailable(host) {
    host.replaceChildren(el("p", { class: "discret" }, ["Les photos sont momentanément indisponibles."]));
  }

  class ArcGalerie extends HTMLElement {
    connectedCallback() {
      const source = (this.getAttribute("source") || "").replace(/\/$/, "");
      const slug = this.getAttribute("galerie") || "";
      if (!source || !SLUG.test(slug)) return;
      renderGallery(this, source, slug, false).catch(() => unavailable(this));
    }
  }

  class ArcGaleries extends HTMLElement {
    connectedCallback() {
      const source = (this.getAttribute("source") || "").replace(/\/$/, "");
      if (!source) return;
      const requested = new URLSearchParams(window.location.search).get("galerie");
      if (requested && SLUG.test(requested)) {
        const back = el("p", {}, [el("a", { href: window.location.pathname }, ["← Toutes les galeries"])]);
        const holder = el("div");
        this.replaceChildren(back, holder);
        renderGallery(holder, source, requested, true).catch(() => unavailable(holder));
        return;
      }
      this.list(source).catch(() => unavailable(this));
    }

    async list(source) {
      const data = await fetchJson(`${source}/galeries.json`);
      const cards = (data.galeries || [])
        .filter((g) => SLUG.test(g.slug))
        .map((gallery) => {
          const cover = image(`${source}/${gallery.slug}`, gallery.couverture, gallery.couverture?.alt);
          const link = el("a", { href: `?galerie=${gallery.slug}` }, [
            ...(cover ? [cover] : []),
            el("h2", {}, [gallery.titre || ""]),
            el("p", { class: "discret" }, [`${formatDate(gallery.date)} - ${gallery.nombre} photo(s)`]),
          ]);
          return el("article", {}, [link]);
        });
      this.replaceChildren(
        cards.length
          ? el("div", { class: "galerie-liste" }, cards)
          : el("p", {}, ["Aucune galerie publiée pour l'instant."]),
      );
    }
  }

  // <arc-couverture source="..." galerie="2024-ecouen" taille="image">
  //   shows the cover (first photo) of a published gallery: the order set in
  //   the drop admin decides the picture. taille="vignette" for 480 px.
  //   Nothing is shown when the gallery is missing or the host unreachable.
  let indexCache = null;

  function galleryIndex(source) {
    if (!indexCache) {
      indexCache = fetchJson(`${source}/galeries.json`).then((data) => data.galeries || []);
    }
    return indexCache;
  }

  class ArcCouverture extends HTMLElement {
    async connectedCallback() {
      const source = (this.getAttribute("source") || "").replace(/\/$/, "");
      const slug = this.getAttribute("galerie") || "";
      if (!source || !SLUG.test(slug) || this.querySelector("img")) return;
      try {
        const gallery = (await galleryIndex(source)).find((g) => g.slug === slug);
        const cover = gallery?.couverture;
        if (!cover || !FILE.test(cover.fichier)) return;
        const large = this.getAttribute("taille") !== "vignette";
        const file = large ? cover.fichier.replace(/-480\.webp$/, "-1600.webp") : cover.fichier;
        this.append(
          el("img", {
            src: `${source}/${slug}/${file}`,
            alt: this.getAttribute("alt") ?? cover.alt ?? "",
            loading: this.getAttribute("loading") || "lazy",
            decoding: "async",
          }),
        );
      } catch {
        // Host unreachable: the element stays empty, its background shows
      }
    }
  }

  if (!customElements.get("arc-galerie")) customElements.define("arc-galerie", ArcGalerie);
  if (!customElements.get("arc-couverture")) customElements.define("arc-couverture", ArcCouverture);
  if (!customElements.get("arc-galeries")) customElements.define("arc-galeries", ArcGaleries);
})();
