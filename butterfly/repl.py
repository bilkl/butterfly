"""Le REPL : une session interactive où l'état se garde d'une ligne à l'autre.

Astuce : au lieu de sérialiser l'état (cellules, formules, observateurs), la
session garde **le texte des entrées réussies** et recompile le tout à chaque
nouvelle entrée. Un programme Butterfly étant déterministe, la sortie de
« l'historique + la nouvelle entrée » commence par la sortie de l'historique :
il suffit d'afficher la suite.
"""

from collections.abc import Callable

from butterfly.compilateur import executer, tokens
from butterfly.erreurs import (
    ErreurButterfly,
    ErreurCompilation,
    ErreurSemantique,
    contexte,
)
from butterfly.tokens import TypeToken

AIDE = """\
Tapez une instruction (elle doit finir par ';' ou '}') ou une expression.
  soit a = 2;           déclare une cellule source
  lie double = a * 2;   déclare une cellule dérivée
  a = 10;               modifie une source : les dérivées se mettent à jour
  double                affiche une expression (sans 'affiche' ni ';')
Commandes : :aide  :source  :reinit  :quitter"""


def entree_complete(texte: str) -> bool:
    """Les accolades sont-elles équilibrées ? (sinon, on attend la suite)"""
    try:
        profondeur = 0
        for token in tokens(texte):
            if token.type is TypeToken.ACC_G:
                profondeur += 1
            elif token.type is TypeToken.ACC_D:
                profondeur -= 1
    except ErreurCompilation:
        return True  # l'erreur lexicale sera signalée à l'exécution
    return profondeur <= 0


class Session:
    """L'état d'une session : les entrées réussies et leur sortie."""

    def __init__(self) -> None:
        self.entrees: list[str] = []
        self.sortie = ""

    def source(self, entree: str | None = None) -> str:
        return "\n".join([*self.entrees, *([entree] if entree else [])])

    def evaluer(self, entree: str) -> tuple[str, ErreurButterfly | None]:
        """Exécute ``entree`` dans la session. Renvoie ce qu'elle affiche et
        une éventuelle erreur ; l'entrée n'est retenue que si tout va bien."""
        premiere_erreur: ErreurButterfly | None = None
        for candidat, retenir in self._candidats(entree):
            try:
                resultat = executer(self.source(candidat))
            except ErreurCompilation as erreur:
                signalee = erreur.erreurs[0]
                # En général, l'erreur de la forme d'origine est la bonne. Mais si
                # « affiche <entrée>; » est correct syntaxiquement et ne pèche que
                # par le sens (`x` inconnu), c'était bien une expression : son
                # message est plus utile que « '=' attendu après 'x' ».
                if premiere_erreur is None or isinstance(signalee, ErreurSemantique):
                    premiere_erreur = signalee
                continue
            nouveau = resultat.sortie[len(self.sortie) :]
            if resultat.erreur is not None:
                return nouveau, resultat.erreur
            if retenir:
                self.entrees.append(candidat)
                self.sortie = resultat.sortie
            return nouveau, None
        return "", premiere_erreur

    @staticmethod
    def _candidats(entree: str) -> list[tuple[str, bool]]:
        """L'entrée telle quelle, puis (si elle échoue) comme une expression."""
        candidats = [(entree, True)]
        nue = entree.strip().rstrip(";")
        if nue and not nue.endswith("}"):
            candidats.append((f"affiche {nue};", False))
        return candidats

    def reinitialiser(self) -> None:
        self.entrees.clear()
        self.sortie = ""


def lancer_repl(
    lire: Callable[[str], str] = input,
    ecrire: Callable[[str], None] = print,
) -> None:
    """Boucle de lecture-évaluation. ``lire`` et ``ecrire`` sont injectables pour
    pouvoir tester le REPL sans terminal."""
    session = Session()
    ecrire("Butterfly : un langage réactif. Tapez :aide pour de l'aide.")
    while True:
        try:
            entree = lire("fly> ")
        except EOFError:
            break
        while entree.strip() and not entree_complete(entree):
            try:
                entree += "\n" + lire("...> ")
            except EOFError:
                break
        commande = entree.strip()
        if not commande:
            continue
        if commande in (":quitter", ":q"):
            break
        if commande == ":aide":
            ecrire(AIDE)
        elif commande == ":source":
            ecrire(session.source() or "(vide)")
        elif commande == ":reinit":
            session.reinitialiser()
            ecrire("session réinitialisée")
        else:
            sortie, erreur = session.evaluer(entree)
            if sortie:
                ecrire(sortie.rstrip("\n"))
            if erreur is not None:
                ecrire(contexte(erreur, session.source(entree)))
