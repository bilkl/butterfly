"""Conversion des objets du langage en réponses JSON pour l'IA."""

from collections.abc import Iterable

from butterfly.erreurs import ErreurButterfly, contexte
from butterfly.semantique import Analyse, GenreSymbole
from butterfly.tokens import Token
from serveur_butterfly.schemas import CelluleJSON, ErreurJSON, TokenJSON


def erreur_json(erreur: ErreurButterfly, source: str) -> ErreurJSON:
    return {
        "genre": erreur.genre,
        "message": erreur.message,
        "ligne": erreur.ligne,
        "colonne": erreur.colonne,
        "contexte": contexte(erreur, source),
    }


def erreurs_json(erreurs: Iterable[ErreurButterfly], source: str) -> list[ErreurJSON]:
    """Une entrée par erreur (une ``ErreurCompilation`` en contient plusieurs)."""
    return [erreur_json(erreur, source) for erreur in erreurs]


def token_json(token: Token) -> TokenJSON:
    return {
        "type": token.type.name,
        "lexeme": token.lexeme,
        "ligne": token.position.ligne,
        "colonne": token.position.colonne,
    }


def cellules_json(analyse: Analyse) -> list[CelluleJSON]:
    cellules: list[CelluleJSON] = []
    for nom in analyse.cellules:
        derivee = analyse.genres[nom] is GenreSymbole.DERIVEE
        cellules.append(
            {
                "nom": nom,
                "genre": "derivee" if derivee else "source",
                "depend_de": sorted(analyse.dependances.get(nom, ())),
            }
        )
    return cellules
