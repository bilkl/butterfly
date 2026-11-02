// Le playground : le vrai compilateur Butterfly, exécuté dans le navigateur
// par Pyodide (Python compilé en WebAssembly).
(function () {
  var editeur = document.getElementById("editeur");
  if (!editeur) return;

  var statut = document.getElementById("statut");
  var executer = document.getElementById("executer");
  var choix = document.getElementById("choix-exemple");
  var sortie = document.querySelector("#panneau-sortie code");
  var python = document.querySelector("#panneau-python code");
  var exemples = JSON.parse(document.getElementById("exemples").textContent);

  // --- Choix d'un exemple, et partage par l'adresse (#code=...) -----------------
  var vide = document.createElement("option");
  vide.value = "";
  vide.textContent = "(mon programme)";
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
    var initial = exemples.length > 2 ? 2 : 0; // le losange
    editeur.value = exemples[initial].source;
    choix.value = String(initial);
  }
  // Un lien « Essayer ce programme » ouvert dans la page déjà chargée.
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

  // --- Onglets ------------------------------------------------------------------
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

  // --- Chargement du compilateur ----------------------------------------------------
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
    echec("Impossible de charger Python (Pyodide) : vérifiez la connexion, puis rechargez la page.");
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
          statut.textContent = "Prêt.";
        });
    })
    .catch(function (erreur) { echec("Le chargement a échoué : " + erreur); });

  function exécuter() {
    if (!lancer) return;
    var resultat = JSON.parse(lancer(editeur.value));
    if (!resultat.ok) {
      sortie.textContent = resultat.erreurs.join("\n");
      python.textContent = "";
      statut.textContent = resultat.erreurs.length + " erreur(s) dans le programme.";
      montrer(true);
      return;
    }
    var texte = resultat.sortie;
    if (resultat.erreur) {
      var avant = texte.replace(/\n$/, "");
      texte = (avant ? avant + "\n" : "") + resultat.erreur;
    }
    sortie.textContent = texte || "(le programme n'a rien affiché)";
    python.textContent = resultat.python;
    statut.textContent = resultat.erreur ? "Erreur d'exécution." : "Exécuté.";
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
