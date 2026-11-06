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
