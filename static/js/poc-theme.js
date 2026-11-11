// POC: switch the whole site between the current look and four proposals.
//
// Loaded without defer in <head>, so the chosen version is applied before
// the first paint. The version comes from ?version=a|b|c|d|actuel, then from
// the last choice (localStorage), and is set as <html data-theme="...">.
// A small bar at the bottom of every page switches between versions.

(() => {
  "use strict";

  const VERSIONS = [
    { id: "actuel", libelle: "Actuel" },
    { id: "a", libelle: "A · Héritage" },
    { id: "b", libelle: "B · Sport" },
    { id: "c", libelle: "C · Éditorial" },
    { id: "d", libelle: "D · Sport + Héritage" },
  ];
  const KEY = "poc-version";
  const ids = VERSIONS.map((v) => v.id);

  function stored() {
    try {
      return window.localStorage.getItem(KEY);
    } catch {
      return null;
    }
  }

  function store(value) {
    try {
      window.localStorage.setItem(KEY, value);
    } catch {
      // Private browsing or blocked storage: the choice lasts for this page only
    }
  }

  const requested = new URLSearchParams(window.location.search).get("version");
  let current = ids.includes(requested) ? requested : stored();
  if (!ids.includes(current)) {
    current = "actuel";
  }
  if (requested === current) {
    store(current);
  }
  document.documentElement.dataset.theme = current;

  function apply(id) {
    current = id;
    document.documentElement.dataset.theme = id;
    store(id);
    for (const button of document.querySelectorAll(".poc-bascule button")) {
      button.setAttribute("aria-pressed", String(button.dataset.version === id));
    }
  }

  function buildBar() {
    const bar = document.createElement("nav");
    bar.className = "poc-bascule";
    bar.setAttribute("aria-label", "Version du site (maquette)");
    const label = document.createElement("span");
    label.textContent = "Version";
    bar.append(label);
    for (const version of VERSIONS) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.version = version.id;
      button.textContent = version.libelle;
      button.setAttribute("aria-pressed", String(version.id === current));
      button.addEventListener("click", () => apply(version.id));
      bar.append(button);
    }
    document.body.append(bar);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildBar);
  } else {
    buildBar();
  }
})();
