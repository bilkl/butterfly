// Theme button: light, dark, or the system setting.
(function () {
  var bouton = document.querySelector(".theme");
  if (!bouton) return;
  function courant() {
    var force = document.documentElement.dataset.theme;
    if (force) return force;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  bouton.addEventListener("click", function () {
    var suivant = courant() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = suivant;
    try { localStorage.setItem("theme", suivant); } catch (e) { /* storage unavailable */ }
  });
})();
