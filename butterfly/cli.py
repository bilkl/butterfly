"""La ligne de commande : ``python -m butterfly <commande> programme.fly``."""

import argparse
import sys
from pathlib import Path

from butterfly import __version__
from butterfly.backend import BACKENDS
from butterfly.compilateur import compiler, executer, parser
from butterfly.erreurs import ErreurCompilation, ErreurLexicale, contexte
from butterfly.lexer import tokenize
from butterfly.noeuds import afficher_arbre
from butterfly.repl import lancer_repl

COMMANDES = {
    "run": "exécute un programme",
    "check": "vérifie un programme sans l'exécuter",
    "transpile": "affiche le code Python généré",
    "format": "réécrit le programme dans sa présentation canonique",
    "tokens": "affiche les tokens",
    "ast": "affiche l'arbre syntaxique",
    "repl": "ouvre une session interactive",
}


def lire_source(fichier: str) -> str:
    """Lit un fichier (ou l'entrée standard si ``fichier`` vaut ``-``)."""
    if fichier == "-":
        return sys.stdin.read()
    return Path(fichier).read_text(encoding="utf-8")


def construire_parser() -> argparse.ArgumentParser:
    principal = argparse.ArgumentParser(
        prog="butterfly",
        description="Butterfly : un langage réactif transpilé en Python.",
    )
    principal.add_argument(
        "--version", action="version", version=f"butterfly {__version__}"
    )
    sous = principal.add_subparsers(dest="commande", required=True, metavar="commande")
    for nom, aide in COMMANDES.items():
        p = sous.add_parser(nom, help=aide, description=aide)
        if nom != "repl":
            p.add_argument(
                "fichier", help="programme .fly, ou - pour l'entrée standard"
            )
        if nom == "format":
            p.add_argument(
                "-w", "--ecrire", action="store_true",
                help="réécrit le fichier au lieu d'afficher le résultat",
            )  # fmt: skip
    return principal


def afficher_erreurs(erreur: ErreurCompilation, source: str) -> None:
    for e in erreur.erreurs:
        print(contexte(e, source), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée. Code de retour : 0 si tout va bien, 1 sinon, 2 si le
    fichier est illisible."""
    arguments = construire_parser().parse_args(argv)
    if arguments.commande == "repl":
        lancer_repl()
        return 0
    try:
        source = lire_source(arguments.fichier)
    except (OSError, UnicodeDecodeError) as erreur:
        print(
            f"butterfly : impossible de lire {arguments.fichier} ({erreur})",
            file=sys.stderr,
        )
        return 2
    try:
        return executer_commande(arguments.commande, source, arguments)
    except ErreurCompilation as erreur:
        afficher_erreurs(erreur, source)
        return 1


def executer_commande(commande: str, source: str, arguments: argparse.Namespace) -> int:
    match commande:
        case "run":
            resultat = executer(source, sys.stdout)
            sys.stdout.flush()
            if resultat.erreur is not None:
                print(contexte(resultat.erreur, source), file=sys.stderr)
                return 1
        case "check":
            compiler(source)
            print("OK : aucun problème trouvé.")
        case "transpile":
            print(BACKENDS["python"].produire(compiler(source), source), end="")
        case "format":
            formate = BACKENDS["format"].produire(compiler(source), source)
            if arguments.ecrire and arguments.fichier != "-":
                Path(arguments.fichier).write_text(formate, encoding="utf-8")
            else:
                print(formate, end="")
        case "tokens":
            try:
                for token in tokenize(source):  # ceux lus avant l'erreur s'affichent
                    print(token)
            except ErreurLexicale as erreur:
                raise ErreurCompilation((erreur,)) from erreur
        case "ast":
            print(afficher_arbre(parser(source)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
