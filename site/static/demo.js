// La démonstration de l'accueil : le losange a → b, c → d du programme affiché.
// Elle reproduit la sémantique du langage : une affectation recalcule chaque
// cellule dérivée une seule fois, dans l'ordre, puis prévient l'observateur
// seulement si la valeur de d a changé.
(function () {
  var racine = document.getElementById("demo");
  if (!racine) return;

  var entree = document.getElementById("entree-a");
  var journal = document.getElementById("journal");
  var reduit = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var etat = { a: 1 };

  function calculer(a) {
    var b = a + 1;
    var c = a * 10;
    return { a: a, b: b, c: c, d: b + c };
  }
  var valeurs = calculer(etat.a);

  function afficher(nom) {
    document.getElementById("val-" + nom).textContent = String(valeurs[nom]);
  }
  function eclat(nom) {
    var cellule = document.getElementById("cell-" + nom);
    cellule.classList.remove("flash");
    void cellule.getBoundingClientRect(); // relance l'animation
    cellule.classList.add("flash");
  }
  function lien(id, actif) {
    document.getElementById(id).classList.toggle("actif", actif);
  }
  function ligne(texte, silence) {
    var li = document.createElement("li");
    li.textContent = texte;
    if (silence) li.className = "silence";
    journal.appendChild(li);
    journal.scrollTop = journal.scrollHeight;
  }
  function apres(delai, fonction) {
    if (reduit) fonction();
    else window.setTimeout(fonction, delai);
  }

  function changer(nouveau) {
    if (!Number.isFinite(nouveau)) return;
    nouveau = Math.max(-99, Math.min(99, Math.round(nouveau)));
    entree.value = String(nouveau);
    if (nouveau === valeurs.a) {
      ligne("a vaut déjà " + nouveau + " : rien ne change, l'observateur reste silencieux.", true);
      return;
    }
    var avantD = valeurs.d;
    var suivant = calculer(nouveau);
    valeurs.a = suivant.a;
    afficher("a"); eclat("a");
    lien("lien-ab", true); lien("lien-ac", true);
    apres(350, function () {
      valeurs.b = suivant.b; valeurs.c = suivant.c;
      afficher("b"); afficher("c"); eclat("b"); eclat("c");
      lien("lien-bd", true); lien("lien-cd", true);
    });
    apres(700, function () {
      valeurs.d = suivant.d;
      afficher("d"); eclat("d");
    });
    apres(1050, function () {
      ["lien-ab", "lien-ac", "lien-bd", "lien-cd"].forEach(function (id) { lien(id, false); });
      if (valeurs.d !== avantD) ligne("d vaut maintenant " + valeurs.d);
    });
  }

  document.getElementById("plus").addEventListener("click", function () { changer(valeurs.a + 1); });
  document.getElementById("moins").addEventListener("click", function () { changer(valeurs.a - 1); });
  entree.addEventListener("change", function () { changer(Number(entree.value)); });
})();
