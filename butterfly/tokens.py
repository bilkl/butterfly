"""Les « mots » de Butterfly : types de token et classe ``Token``."""

from dataclasses import dataclass
from enum import Enum, auto

from butterfly.erreurs import Position


class TypeToken(Enum):
    """Tous les types de token du langage."""

    # Mots-clés
    SOIT = auto()
    LIE = auto()
    QUAND = auto()
    SI = auto()
    SINON = auto()
    POUR = auto()
    DANS = auto()
    AFFICHE = auto()
    VRAI = auto()
    FAUX = auto()
    ET = auto()
    OU = auto()
    NON = auto()
    # Valeurs et noms
    IDENT = auto()
    ENTIER = auto()
    TEXTE = auto()
    # Opérateurs et ponctuation
    PLUS = auto()
    MOINS = auto()
    ETOILE = auto()
    SLASH = auto()
    POURCENT = auto()
    EGAL_EGAL = auto()
    DIFFERENT = auto()
    INF = auto()
    INF_EGAL = auto()
    SUP = auto()
    SUP_EGAL = auto()
    EGAL = auto()
    POINT_POINT = auto()
    PAREN_G = auto()
    PAREN_D = auto()
    ACC_G = auto()
    ACC_D = auto()
    VIRGULE = auto()
    POINT_VIRGULE = auto()
    # Divers
    COMMENTAIRE = auto()  # produit seulement à la demande (formateur)
    FIN = auto()


MOTS_CLES: dict[str, TypeToken] = {
    "soit": TypeToken.SOIT,
    "lie": TypeToken.LIE,
    "quand": TypeToken.QUAND,
    "si": TypeToken.SI,
    "sinon": TypeToken.SINON,
    "pour": TypeToken.POUR,
    "dans": TypeToken.DANS,
    "affiche": TypeToken.AFFICHE,
    "vrai": TypeToken.VRAI,
    "faux": TypeToken.FAUX,
    "et": TypeToken.ET,
    "ou": TypeToken.OU,
    "non": TypeToken.NON,
}

SYMBOLES_DOUBLES: dict[str, TypeToken] = {
    "==": TypeToken.EGAL_EGAL,
    "!=": TypeToken.DIFFERENT,
    "<=": TypeToken.INF_EGAL,
    ">=": TypeToken.SUP_EGAL,
    "..": TypeToken.POINT_POINT,
}

SYMBOLES_SIMPLES: dict[str, TypeToken] = {
    "+": TypeToken.PLUS,
    "-": TypeToken.MOINS,
    "*": TypeToken.ETOILE,
    "/": TypeToken.SLASH,
    "%": TypeToken.POURCENT,
    "<": TypeToken.INF,
    ">": TypeToken.SUP,
    "=": TypeToken.EGAL,
    "(": TypeToken.PAREN_G,
    ")": TypeToken.PAREN_D,
    "{": TypeToken.ACC_G,
    "}": TypeToken.ACC_D,
    ",": TypeToken.VIRGULE,
    ";": TypeToken.POINT_VIRGULE,
}


@dataclass(frozen=True, slots=True, repr=False)
class Token:
    """Un mot du programme : son type, son texte exact et sa position.

    ``valeur`` contient la valeur déjà décodée d'un ``ENTIER`` (un ``int``) ou
    d'un ``TEXTE`` (le texte sans guillemets, échappements résolus).
    """

    type: TypeToken
    lexeme: str
    position: Position
    valeur: int | str | None = None

    def __repr__(self) -> str:
        p = self.position
        return f"Token({self.type.name}, {self.lexeme!r}, {p.ligne}:{p.colonne})"
