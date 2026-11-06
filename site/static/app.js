// Theme button: light, dark, or the system setting.
(function () {
  var button = document.querySelector(".theme");
  if (!button) return;
  function current() {
    var forced = document.documentElement.dataset.theme;
    if (forced) return forced;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  button.addEventListener("click", function () {
    var next = current() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch (e) { /* storage unavailable */ }
  });
})();

// Language switch: remember the choice, and open the site in the remembered language.
(function () {
  var link = document.querySelector("a.lang");
  if (!link) return;
  var here = document.documentElement.lang;
  var stored = null;
  try { stored = localStorage.getItem("lang"); } catch (e) { /* storage unavailable */ }
  function target() { return link.getAttribute("href") + window.location.hash; }
  if (stored && stored !== here && stored === link.dataset.lang) {
    window.location.replace(target());
    return;
  }
  link.addEventListener("click", function () {
    try { localStorage.setItem("lang", link.dataset.lang); } catch (e) { /* storage unavailable */ }
    link.setAttribute("href", target());
  });
})();
