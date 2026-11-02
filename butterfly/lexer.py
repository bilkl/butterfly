"""Le lexer : transforme le texte source en une suite de tokens.

C'est un **générateur** : il ne lit le source qu'au fur et à mesure qu'on lui
demande des tokens. Une erreur lexicale se produit donc au moment où on arrive
à l'endroit fautif, et les tokens lus avant sont déjà disponibles.
"""

from collections.abc import Iterator

from butterfly.erreurs import ErreurLexicale, Position
from butterfly.tokens import (
    MOTS_CLES,
    SYMBOLES_DOUBLES,
    SYMBOLES_SIMPLES,
    Token,
    TypeToken,
)

CHIFFRES = "0123456789"
ESCAPES = {"n": "\n", '"': '"', "\\": "\\"}


class _Lecteur:
    """Un curseur dans le source, qui suit la ligne et la colonne."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.i = 0
        self.ligne = 1
        self.colonne = 1

    def fini(self) -> bool:
        return self.i >= len(self.source)

    def car(self, decalage: int = 0) -> str:
        """Le caractère courant (ou le suivant, etc.) ; ``""`` après la fin."""
        j = self.i + decalage
        return self.source[j] if j < len(self.source) else ""

    def avancer(self) -> str:
        c = self.source[self.i]
        self.i += 1
        if c == "\n":
            self.ligne += 1
            self.colonne = 1
        else:
            self.colonne += 1
        return c

    def position(self) -> Position:
        return Position(self.ligne, self.colonne)


def tokenize(source: str, *, commentaires: bool = False) -> Iterator[Token]:
    """Produit les tokens de ``source``, terminés par un token ``FIN``.

    Avec ``commentaires=True``, les commentaires sont produits (type
    ``COMMENTAIRE``) au lieu d'être ignorés : le formateur en a besoin.
    """
    lecteur = _Lecteur(source)
    while not lecteur.fini():
        c = lecteur.car()
        if c in " \t\r\n":
            lecteur.avancer()
            continue
        pos = lecteur.position()
        if c == "#":
            debut = lecteur.i
            while not lecteur.fini() and lecteur.car() != "\n":
                lecteur.avancer()
            if commentaires:
                yield Token(TypeToken.COMMENTAIRE, source[debut : lecteur.i], pos)
        elif c in CHIFFRES:
            yield _nombre(lecteur, pos)
        elif c.isalpha() or c == "_":
            yield _mot(lecteur, pos)
        elif c == '"':
            yield _texte(lecteur, pos)
        elif c + lecteur.car(1) in SYMBOLES_DOUBLES:
            double = c + lecteur.car(1)
            lecteur.avancer()
            lecteur.avancer()
            yield Token(SYMBOLES_DOUBLES[double], double, pos)
        elif c in SYMBOLES_SIMPLES:
            lecteur.avancer()
            yield Token(SYMBOLES_SIMPLES[c], c, pos)
        else:
            raise ErreurLexicale(f"caractère inattendu {c!r}", pos)
    yield Token(TypeToken.FIN, "", lecteur.position())


def _nombre(lecteur: _Lecteur, pos: Position) -> Token:
    debut = lecteur.i
    while lecteur.car() != "" and lecteur.car() in CHIFFRES:
        lecteur.avancer()
    # « 1..5 » est une plage ; un point isolé collé à un nombre est une erreur.
    if lecteur.car() == "." and lecteur.car(1) != ".":
        raise ErreurLexicale(
            "les nombres décimaux n'existent pas : seuls les entiers sont permis",
            lecteur.position(),
        )
    texte = lecteur.source[debut : lecteur.i]
    try:
        valeur = int(texte)
    except ValueError:  # plus de 4300 chiffres : limite de Python
        raise ErreurLexicale("nombre trop grand", pos) from None
    return Token(TypeToken.ENTIER, texte, pos, valeur)


def _mot(lecteur: _Lecteur, pos: Position) -> Token:
    debut = lecteur.i
    while lecteur.car() != "" and (lecteur.car().isalnum() or lecteur.car() == "_"):
        lecteur.avancer()
    texte = lecteur.source[debut : lecteur.i]
    return Token(MOTS_CLES.get(texte, TypeToken.IDENT), texte, pos)


def _texte(lecteur: _Lecteur, pos: Position) -> Token:
    debut = lecteur.i
    lecteur.avancer()  # le guillemet ouvrant
    morceaux: list[str] = []
    while True:
        c = lecteur.car()
        if c in ("", "\n"):
            raise ErreurLexicale(
                "texte non fermé : il manque le guillemet fermant", pos
            )
        if c == '"':
            lecteur.avancer()
            break
        if c == "\\":
            pos_echappement = lecteur.position()
            lecteur.avancer()
            suivant = lecteur.car()
            if suivant not in ESCAPES:
                raise ErreurLexicale(
                    f"échappement inconnu '\\{suivant}' (permis : \\\" \\\\ \\n)",
                    pos_echappement,
                )
            morceaux.append(ESCAPES[suivant])
            lecteur.avancer()
        else:
            morceaux.append(lecteur.avancer())
    return Token(
        TypeToken.TEXTE, lecteur.source[debut : lecteur.i], pos, "".join(morceaux)
    )
