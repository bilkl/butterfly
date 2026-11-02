"""Position dans le source et hiérarchie des erreurs de Butterfly.

Toute erreur du langage hérite de ``ErreurButterfly`` et porte une position.
Son texte suit toujours le même format :

    Erreur sémantique (ligne 3, colonne 1) : 'b' est une cellule dérivée ...

Les erreurs d'exécution n'indiquent que la ligne.
"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Position:
    """Un endroit du source : ligne et colonne, comptées à partir de 1."""

    ligne: int
    colonne: int

    def __str__(self) -> str:
        return f"ligne {self.ligne}, colonne {self.colonne}"


class ErreurButterfly(Exception):
    """Classe mère de toutes les erreurs du langage."""

    genre: ClassVar[str] = "Erreur"

    def __init__(self, message: str, position: Position | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.position = position

    @property
    def ligne(self) -> int | None:
        return None if self.position is None else self.position.ligne

    @property
    def colonne(self) -> int | None:
        return None if self.position is None else self.position.colonne

    def __str__(self) -> str:
        if self.position is None:
            return f"{self.genre} : {self.message}"
        return f"{self.genre} ({self.position}) : {self.message}"


class ErreurLexicale(ErreurButterfly):
    """Un caractère ou un texte que le lexer ne sait pas lire."""

    genre = "Erreur lexicale"


class ErreurSyntaxe(ErreurButterfly):
    """Un programme qui ne respecte pas la grammaire."""

    genre = "Erreur de syntaxe"


class ErreurSemantique(ErreurButterfly):
    """Un programme grammaticalement correct, mais qui n'a pas de sens."""

    genre = "Erreur sémantique"


class ErreurExecution(ErreurButterfly):
    """Une erreur qui se produit pendant l'exécution (seule la ligne est connue)."""

    genre = "Erreur d'exécution"

    def __init__(self, message: str, ligne: int) -> None:
        super().__init__(message, Position(ligne, 0))

    @property
    def colonne(self) -> int | None:
        return None

    def __str__(self) -> str:
        return f"{self.genre} (ligne {self.ligne}) : {self.message}"


class ErreurCompilation(Exception):
    """Toutes les erreurs trouvées dans un programme, en une seule fois.

    Le parser et l'analyse sémantique ne s'arrêtent pas à la première erreur :
    ils les collectent, pour que l'utilisateur puisse tout corriger d'un coup.
    """

    def __init__(self, erreurs: tuple[ErreurButterfly, ...]) -> None:
        super().__init__(f"{len(erreurs)} erreur(s)")
        self.erreurs = erreurs

    def __str__(self) -> str:
        return "\n".join(str(erreur) for erreur in self.erreurs)


def contexte(erreur: ErreurButterfly, source: str) -> str:
    """Le message complet, avec la ligne fautive et un repère sous la colonne.

    >>> print(contexte(ErreurSyntaxe("oups", Position(1, 3)), "ab cd"))
    Erreur de syntaxe (ligne 1, colonne 3) : oups
      1 | ab cd
        |   ^
    """
    texte = str(erreur)
    ligne = erreur.ligne
    lignes = source.splitlines()
    if ligne is None or not 1 <= ligne <= len(lignes):
        return texte
    numero = str(ligne)
    marge = " " * len(numero)
    resultat = f"{texte}\n  {numero} | {lignes[ligne - 1]}"
    colonne = erreur.colonne
    if colonne is not None:
        resultat += f"\n  {marge} | {' ' * (colonne - 1)}^"
    return resultat
