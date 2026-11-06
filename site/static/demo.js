// The home page demo: the diamond a → b, c → d of the program shown.
// It reproduces the semantics of the language: an assignment recomputes each
// derived cell exactly once, in order, then notifies the observer only if the
// value of d has changed.
(function () {
  var FR = document.documentElement.lang === "fr";
  var root = document.getElementById("demo");
  if (!root) return;

  var input = document.getElementById("entree-a");
  var log = document.getElementById("journal");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var state = { a: 1 };

  function compute(a) {
    var b = a + 1;
    var c = a * 10;
    return { a: a, b: b, c: c, d: b + c };
  }
  var values = compute(state.a);

  function show(name) {
    document.getElementById("val-" + name).textContent = String(values[name]);
  }
  function flash(name) {
    var cell = document.getElementById("cell-" + name);
    cell.classList.remove("flash");
    void cell.getBoundingClientRect(); // restart the animation
    cell.classList.add("flash");
  }
  function link(id, active) {
    document.getElementById(id).classList.toggle("actif", active);
  }
  function line(text, quiet) {
    var li = document.createElement("li");
    li.textContent = text;
    if (quiet) li.className = "silence";
    log.appendChild(li);
    log.scrollTop = log.scrollHeight;
  }
  function after(delay, fn) {
    if (reduced) fn();
    else window.setTimeout(fn, delay);
  }

  function change(next) {
    if (!Number.isFinite(next)) return;
    next = Math.max(-99, Math.min(99, Math.round(next)));
    input.value = String(next);
    if (next === values.a) {
      line(FR ? "a vaut déjà " + next + " : rien ne change, l'observateur reste silencieux." : "a is already " + next + ": nothing changes, the observer stays silent.", true);
      return;
    }
    var beforeD = values.d;
    var following = compute(next);
    values.a = following.a;
    show("a"); flash("a");
    link("lien-ab", true); link("lien-ac", true);
    after(350, function () {
      values.b = following.b; values.c = following.c;
      show("b"); show("c"); flash("b"); flash("c");
      link("lien-bd", true); link("lien-cd", true);
    });
    after(700, function () {
      values.d = following.d;
      show("d"); flash("d");
    });
    after(1050, function () {
      ["lien-ab", "lien-ac", "lien-bd", "lien-cd"].forEach(function (id) { link(id, false); });
      if (values.d !== beforeD) line("d is now " + values.d);
    });
  }

  document.getElementById("plus").addEventListener("click", function () { change(values.a + 1); });
  document.getElementById("moins").addEventListener("click", function () { change(values.a - 1); });
  input.addEventListener("change", function () { change(Number(input.value)); });
})();
