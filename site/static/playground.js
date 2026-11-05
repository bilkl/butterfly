// The playground: the real Butterfly compiler, run in the browser by Pyodide
// (Python compiled to WebAssembly).
(function () {
  var editeur = document.getElementById("editeur");
  if (!editeur) return;

  var statut = document.getElementById("statut");
  var executer = document.getElementById("executer");
  var choix = document.getElementById("choix-exemple");
  var sortie = document.querySelector("#panneau-sortie code");
  var python = document.querySelector("#panneau-python code");
  var exemples = JSON.parse(document.getElementById("exemples").textContent);

  // --- Picking an example, and sharing through the address (#code=...) ----------
  var vide = document.createElement("option");
  vide.value = "";
  vide.textContent = "(my program)";
  choix.appendChild(vide);
  exemples.forEach(function (exemple, i) {
    var option = document.createElement("option");
    option.value = String(i);
    option.textContent = exemple.titre + " : " + exemple.description;
    choix.appendChild(option);
  });

  function codeDepuisAdresse() {
    var m = /^#code=(.*)$/.exec(window.location.hash);
    if (!m) return null;
    try { return decodeURIComponent(m[1]); } catch (e) { return null; }
  }
  var depart = codeDepuisAdresse();
  if (depart !== null) {
    editeur.value = depart;
  } else {
    var initial = exemples.length > 2 ? 2 : 0; // the diamond
    editeur.value = exemples[initial].source;
    choix.value = String(initial);
  }
  // A "Try this program" link opened in the already loaded page.
  window.addEventListener("hashchange", function () {
    var code = codeDepuisAdresse();
    if (code !== null) {
      editeur.value = code;
      choix.value = "";
    }
  });
  choix.addEventListener("change", function () {
    if (choix.value !== "") editeur.value = exemples[Number(choix.value)].source;
  });

  // --- Tabs ---------------------------------------------------------------------
  var ongletSortie = document.getElementById("onglet-sortie");
  var ongletPython = document.getElementById("onglet-python");
  var panneauSortie = document.getElementById("panneau-sortie");
  var panneauPython = document.getElementById("panneau-python");
  function montrer(sortieVisible) {
    ongletSortie.setAttribute("aria-selected", String(sortieVisible));
    ongletPython.setAttribute("aria-selected", String(!sortieVisible));
    panneauSortie.hidden = !sortieVisible;
    panneauPython.hidden = sortieVisible;
  }
  ongletSortie.addEventListener("click", function () { montrer(true); });
  ongletPython.addEventListener("click", function () { montrer(false); });

  // --- Loading the compiler -----------------------------------------------------------
  var lancer = null;
  var SCRIPT = [
    "import json",
    "from butterfly.compilateur import executer, transpiler, verifier",
    "from butterfly.erreurs import contexte",
    "def lancer(source):",
    "    erreurs = verifier(source)",
    "    if erreurs:",
    "        return json.dumps({'ok': False, 'erreurs': [contexte(e, source) for e in erreurs]})",
    "    r = executer(source)",
    "    return json.dumps({",
    "        'ok': True, 'sortie': r.sortie, 'python': transpiler(source),",
    "        'erreur': contexte(r.erreur, source) if r.erreur else None})",
  ].join("\n");

  function echec(message) {
    statut.textContent = message;
    sortie.textContent = message;
  }

  if (typeof loadPyodide !== "function") {
    echec("Could not load Python (Pyodide): check your connection, then reload the page.");
    return;
  }

  loadPyodide()
    .then(function (pyodide) {
      return fetch("butterfly.zip")
        .then(function (reponse) { return reponse.arrayBuffer(); })
        .then(function (zip) {
          pyodide.unpackArchive(zip, "zip");
          pyodide.runPython(SCRIPT);
          lancer = pyodide.globals.get("lancer");
          executer.disabled = false;
          statut.textContent = "Ready.";
        });
    })
    .catch(function (erreur) { echec("Loading failed: " + erreur); });

  function exécuter() {
    if (!lancer) return;
    var resultat = JSON.parse(lancer(editeur.value));
    if (!resultat.ok) {
      sortie.textContent = resultat.erreurs.join("\n");
      python.textContent = "";
      statut.textContent = resultat.erreurs.length + " error(s) in the program.";
      montrer(true);
      return;
    }
    var texte = resultat.sortie;
    if (resultat.erreur) {
      var avant = texte.replace(/\n$/, "");
      texte = (avant ? avant + "\n" : "") + resultat.erreur;
    }
    sortie.textContent = texte || "(the program printed nothing)";
    python.textContent = resultat.python;
    statut.textContent = resultat.erreur ? "Runtime error." : "Done.";
    montrer(true);
  }
  executer.addEventListener("click", exécuter);
  editeur.addEventListener("keydown", function (evenement) {
    if ((evenement.ctrlKey || evenement.metaKey) && evenement.key === "Enter") {
      evenement.preventDefault();
      exécuter();
    }
  });
})();
