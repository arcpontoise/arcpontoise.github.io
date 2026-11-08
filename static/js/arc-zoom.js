// Images of the text pages open full size in a viewer (<dialog>) on click.
//
// Each image of a .texte block is wrapped in a button, so the viewer also
// opens with the keyboard. Images already inside a link are left alone.

(() => {
  "use strict";

  function el(tag, attributes = {}, children = []) {
    const node = document.createElement(tag);
    for (const [name, value] of Object.entries(attributes)) {
      node.setAttribute(name, value);
    }
    node.append(...children);
    return node;
  }

  function init() {
    const images = [...document.querySelectorAll(".texte img")].filter((img) => !img.closest("a, button"));
    if (!images.length) return;

    const picture = el("img", { class: "zoom-image", alt: "" });
    const close = el("button", { type: "button" }, ["Fermer"]);
    const dialog = el("dialog", { class: "galerie-visionneuse", "aria-label": "Image en grand" }, [
      picture,
      el("div", { class: "galerie-commandes zoom-commandes" }, [close]),
    ]);
    close.addEventListener("click", () => dialog.close());
    // Click on the backdrop or on the picture closes the viewer
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog || event.target === picture) dialog.close();
    });
    document.body.append(dialog);

    for (const img of images) {
      const button = el("button", {
        type: "button",
        class: "zoom",
        "aria-label": `Agrandir l'image : ${img.alt || "sans description"}`,
      });
      img.replaceWith(button);
      button.append(img);
      button.addEventListener("click", () => {
        picture.src = img.currentSrc || img.src;
        picture.alt = img.alt;
        dialog.showModal();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
