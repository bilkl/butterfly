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

from butterfly.errors import ButterflyError, CompilationError, ExecutionError
from butterfly.generator import generate_python
from butterfly.nodes import Program
from butterfly.parser import analyze_syntax, list_tokens
from butterfly.semantics import Analysis, analyze_semantics
from butterfly.tokens import Token


@dataclass(frozen=True)
class Result:
    """Ce qu'a produit l'exécution d'un programme."""

    output: str  # vide si on a fourni son propre flux de sortie
    error: ExecutionError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def tokens(source: str) -> list[Token]:
    """Les tokens de ``source`` (lève ``ErreurCompilation`` si lexicale)."""
    return list_tokens(source)


def parser(source: str) -> Program:
    """L'arbre syntaxique, sans l'analyse sémantique."""
    return analyze_syntax(source)


def analyze_program(source: str) -> Analysis:
    """Lexer, parser et analyse sémantique. Lève ``ErreurCompilation``."""
    return analyze_semantics(analyze_syntax(source))


def check(source: str) -> tuple[ButterflyError, ...]:
    """Toutes les erreurs du programme (un tuple vide si tout va bien)."""
    try:
        analyze_program(source)
    except CompilationError as error:
        return error.errors
    return ()


def transpile(source: str) -> str:
    """Le texte Python correspondant au programme."""
    return generate_python(analyze_program(source))


def execute(source: str, output: TextIO | None = None) -> Result:
    """Compile et exécute le programme.

    Sans ``sortie``, l'affichage est capturé et renvoyé dans le résultat. Avec un
    flux (par exemple ``sys.stdout``), il y est écrit au fur et à mesure. Une
    erreur d'exécution est renvoyée dans le résultat : ce qui a été affiché
    avant l'erreur est conservé.
    """
    code = compile(transpile(source), "<butterfly>", "exec")
    capture = io.StringIO()
    error: ExecutionError | None = None
    with contextlib.redirect_stdout(output if output is not None else capture):
        try:
            exec(code, {"__name__": "__butterfly__"})
        except ExecutionError as exc:
            error = exc
    return Result(capture.getvalue(), error)
