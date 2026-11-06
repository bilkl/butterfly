"""La ligne de commande : ``python -m butterfly <commande> programme.fly``."""

import argparse
import sys
from pathlib import Path

from butterfly import __version__
from butterfly.backend import BACKENDS
from butterfly.compiler import analyze_program, execute, parser
from butterfly.errors import CompilationError, LexicalError, context
from butterfly.lexer import tokenize
from butterfly.nodes import print_tree
from butterfly.repl import run_repl

COMMANDS = {
    "run": "runs a program",
    "check": "checks a program without running it",
    "transpile": "prints the generated Python code",
    "format": "rewrites the program in its canonical layout",
    "tokens": "prints the tokens",
    "ast": "prints the syntax tree",
    "repl": "opens an interactive session",
}


def read_source(file_path: str) -> str:
    """Lit un fichier (ou l'entrée standard si ``fichier`` vaut ``-``)."""
    if file_path == "-":
        return sys.stdin.read()
    return Path(file_path).read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    main_parser = argparse.ArgumentParser(
        prog="butterfly",
        description="Butterfly: a reactive language transpiled to Python.",
    )
    main_parser.add_argument(
        "--version", action="version", version=f"butterfly {__version__}"
    )
    subparsers = main_parser.add_subparsers(
        dest="command", required=True, metavar="command"
    )
    for name, help_text in COMMANDS.items():
        p = subparsers.add_parser(name, help=help_text, description=help_text)
        if name != "repl":
            p.add_argument("file_path", help=".fly program, or - for standard input")
        if name == "format":
            p.add_argument(
                "-w", "--write", action="store_true",
                help="rewrites the file instead of printing the result",
            )  # fmt: skip
    return main_parser


def print_errors(error: CompilationError, source: str) -> None:
    for e in error.errors:
        print(context(e, source), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée. Code de retour : 0 si tout va bien, 1 sinon, 2 si le
    fichier est illisible."""
    arguments = build_parser().parse_args(argv)
    if arguments.command == "repl":
        run_repl()
        return 0
    try:
        source = read_source(arguments.file_path)
    except (OSError, UnicodeDecodeError) as error:
        print(
            f"butterfly: cannot read {arguments.file_path} ({error})",
            file=sys.stderr,
        )
        return 2
    try:
        return run_command(arguments.command, source, arguments)
    except CompilationError as error:
        print_errors(error, source)
        return 1


def run_command(command: str, source: str, arguments: argparse.Namespace) -> int:
    match command:
        case "run":
            result = execute(source, sys.stdout)
            sys.stdout.flush()
            if result.error is not None:
                print(context(result.error, source), file=sys.stderr)
                return 1
        case "check":
            analyze_program(source)
            print("OK: no problem found.")
        case "transpile":
            print(BACKENDS["python"].produce(analyze_program(source), source), end="")
        case "format":
            formatted = BACKENDS["format"].produce(analyze_program(source), source)
            if arguments.write and arguments.file_path != "-":
                Path(arguments.file_path).write_text(formatted, encoding="utf-8")
            else:
                print(formatted, end="")
        case "tokens":
            try:
                for token in tokenize(source):  # ceux lus avant l'erreur s'affichent
                    print(token)
            except LexicalError as error:
                raise CompilationError((error,)) from error
        case "ast":
            print(print_tree(parser(source)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
