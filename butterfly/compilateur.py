"""La façade : tout ce qu'il faut savoir pour utiliser Butterfly en Python.

    from butterfly.compilateur import executer
    resultat = executer("soit a = 2; affiche a * 21;")
    print(resultat.sortie)   # 42

Les outils en ligne de commande, le REPL et le serveur MCP n'utilisent que ces
fonctions : ils ne réimplémentent rien.
"""

import contextlib
import io
from dataclasses import dataclass
from typing import TextIO

from butterfly.erreurs import ErreurButterfly, ErreurCompilation, ErreurExecution
from butterfly.generateur import generer_python
from butterfly.noeuds import Programme
from butterfly.parser import analyser_syntaxe, lister_tokens
from butterfly.semantique import Analyse, analyser_semantique
from butterfly.tokens import Token


@dataclass(frozen=True)
class Resultat:
    """Ce qu'a produit l'exécution d'un programme."""

    sortie: str  # vide si on a fourni son propre flux de sortie
    erreur: ErreurExecution | None = None

    @property
    def ok(self) -> bool:
        return self.erreur is None


def tokens(source: str) -> list[Token]:
    """Les tokens de ``source`` (lève ``ErreurCompilation`` si lexicale)."""
    return lister_tokens(source)


def parser(source: str) -> Programme:
    """L'arbre syntaxique, sans l'analyse sémantique."""
    return analyser_syntaxe(source)


def compiler(source: str) -> Analyse:
    """Lexer, parser et analyse sémantique. Lève ``ErreurCompilation``."""
    return analyser_semantique(analyser_syntaxe(source))


def verifier(source: str) -> tuple[ErreurButterfly, ...]:
    """Toutes les erreurs du programme (un tuple vide si tout va bien)."""
    try:
        compiler(source)
    except ErreurCompilation as erreur:
        return erreur.erreurs
    return ()


def transpiler(source: str) -> str:
    """Le texte Python correspondant au programme."""
    return generer_python(compiler(source))


def executer(source: str, sortie: TextIO | None = None) -> Resultat:
    """Compile et exécute le programme.

    Sans ``sortie``, l'affichage est capturé et renvoyé dans le résultat. Avec un
    flux (par exemple ``sys.stdout``), il y est écrit au fur et à mesure. Une
    erreur d'exécution est renvoyée dans le résultat : ce qui a été affiché
    avant l'erreur est conservé.
    """
    code = compile(transpiler(source), "<butterfly>", "exec")
    capture = io.StringIO()
    erreur: ErreurExecution | None = None
    with contextlib.redirect_stdout(sortie if sortie is not None else capture):
        try:
            exec(code, {"__name__": "__butterfly__"})
        except ErreurExecution as exc:
            erreur = exc
    return Resultat(capture.getvalue(), erreur)
