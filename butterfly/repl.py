"""Le REPL : une session interactive où l'état se garde d'une ligne à l'autre.

Astuce : au lieu de sérialiser l'état (cellules, formules, observateurs), la
session garde **le texte des entrées réussies** et recompile le tout à chaque
nouvelle entrée. Un programme Butterfly étant déterministe, la sortie de
« l'historique + la nouvelle entrée » commence par la sortie de l'historique :
il suffit d'afficher la suite.
"""

from collections.abc import Callable

from butterfly.compiler import execute, tokens
from butterfly.errors import (
    ButterflyError,
    CompilationError,
    SemanticError,
    context,
)
from butterfly.tokens import TypeToken

HELP = """\
Type a statement (it must end with ';' or '}') or an expression.
  let a = 2;            declares a source cell
  bind double = a * 2;  declares a derived cell
  a = 10;               changes a source: derived cells update
  double                prints an expression (without 'print' or ';')
Commands: :help  :source  :reset  :quit"""


def is_complete_input(text: str) -> bool:
    """Les accolades sont-elles équilibrées ? (sinon, on attend la suite)"""
    try:
        depth = 0
        for token in tokens(text):
            if token.type is TypeToken.LBRACE:
                depth += 1
            elif token.type is TypeToken.RBRACE:
                depth -= 1
    except CompilationError:
        return True  # l'erreur lexicale sera signalée à l'exécution
    return depth <= 0


class Session:
    """L'état d'une session : les entrées réussies et leur sortie."""

    def __init__(self) -> None:
        self.entries: list[str] = []
        self.output = ""

    def source(self, line_in: str | None = None) -> str:
        return "\n".join([*self.entries, *([line_in] if line_in else [])])

    def evaluate(self, line_in: str) -> tuple[str, ButterflyError | None]:
        """Exécute ``entree`` dans la session. Renvoie ce qu'elle affiche et
        une éventuelle erreur ; l'entrée n'est retenue que si tout va bien."""
        first_error: ButterflyError | None = None
        for candidate, retain in self._candidates(line_in):
            try:
                result = execute(self.source(candidate))
            except CompilationError as error:
                reported = error.errors[0]
                # En général, l'erreur de la forme d'origine est la bonne. Mais si
                # « affiche <entrée>; » est correct syntaxiquement et ne pèche que
                # par le sens (`x` inconnu), c'était bien une expression : son
                # message est plus utile que « '=' attendu après 'x' ».
                if first_error is None or isinstance(reported, SemanticError):
                    first_error = reported
                continue
            new = result.output[len(self.output) :]
            if result.error is not None:
                return new, result.error
            if retain:
                self.entries.append(candidate)
                self.output = result.output
            return new, None
        return "", first_error

    @staticmethod
    def _candidates(line_in: str) -> list[tuple[str, bool]]:
        """L'entrée telle quelle, puis (si elle échoue) comme une expression."""
        candidates = [(line_in, True)]
        bare = line_in.strip().rstrip(";")
        if bare and not bare.endswith("}"):
            candidates.append((f"print {bare};", False))
        return candidates

    def reset(self) -> None:
        self.entries.clear()
        self.output = ""


def run_repl(
    read_line: Callable[[str], str] = input,
    write_line: Callable[[str], None] = print,
) -> None:
    """Boucle de lecture-évaluation. ``lire`` et ``ecrire`` sont injectables pour
    pouvoir tester le REPL sans terminal."""
    session = Session()
    write_line("Butterfly: a reactive language. Type :help for help.")
    while True:
        try:
            line_in = read_line("fly> ")
        except EOFError:
            break
        while line_in.strip() and not is_complete_input(line_in):
            try:
                line_in += "\n" + read_line("...> ")
            except EOFError:
                break
        command = line_in.strip()
        if not command:
            continue
        if command in (":quit", ":q"):
            break
        if command == ":help":
            write_line(HELP)
        elif command == ":source":
            write_line(session.source() or "(empty)")
        elif command == ":reset":
            session.reset()
            write_line("session reset")
        else:
            output, error = session.evaluate(line_in)
            if output:
                write_line(output.rstrip("\n"))
            if error is not None:
                write_line(context(error, session.source(line_in)))
