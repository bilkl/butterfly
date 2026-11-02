"""L'analyse sémantique : ce que la grammaire ne peut pas voir.

Elle vérifie que chaque nom est déclaré avant d'être utilisé, qu'aucun nom n'en
masque un autre, qu'on n'affecte que des cellules sources, qu'un observateur ne
modifie pas le niveau supérieur, et que les appels de fonctions sont corrects.

Elle **collecte toutes les erreurs** au lieu de s'arrêter à la première, et
produit un objet ``Analyse`` : les informations dont le générateur a besoin
(quelles cellules existent, de quoi dépend chaque cellule dérivée).
"""

from dataclasses import dataclass
from enum import Enum, auto
from functools import singledispatchmethod

from butterfly.erreurs import ErreurCompilation, ErreurSemantique, Position
from butterfly.noeuds import (
    Affectation,
    Affiche,
    Appel,
    Binaire,
    Bloc,
    Booleen,
    Declaration,
    Entier,
    Expression,
    Instruction,
    Liaison,
    Nom,
    Observation,
    Pour,
    Programme,
    Si,
    Texte,
    Unaire,
)

#: Les fonctions prédéfinies et leur nombre d'arguments.
FONCTIONS: dict[str, int] = {"min": 2, "max": 2, "abs": 1}


class GenreSymbole(Enum):
    SOURCE = auto()  # soit, au niveau supérieur : modifiable, suivie par les lie
    DERIVEE = auto()  # lie : toujours égale à sa formule
    LOCALE = auto()  # soit, dans un bloc
    BOUCLE = auto()  # variable d'un pour : lecture seule


@dataclass(frozen=True, slots=True)
class Symbole:
    nom: str
    genre: GenreSymbole
    haut: bool  # déclaré au niveau supérieur ?
    position: Position


@dataclass(frozen=True)
class Analyse:
    """Le résultat de l'analyse : un arbre vérifié et ce qu'on en a appris."""

    programme: Programme
    #: Les cellules du niveau supérieur (soit et lie), dans l'ordre de déclaration.
    cellules: tuple[str, ...]
    genres: dict[str, GenreSymbole]
    #: Pour chaque cellule dérivée, les cellules citées dans sa formule.
    dependances: dict[str, frozenset[str]]


class Analyseur:
    def __init__(self) -> None:
        self.portees: list[dict[str, Symbole]] = [{}]
        self.erreurs: list[ErreurSemantique] = []
        self.dans_observateur = False
        self.cellules: list[str] = []
        self.genres: dict[str, GenreSymbole] = {}
        self.dependances: dict[str, frozenset[str]] = {}

    # --- Outils -------------------------------------------------------------

    def signaler(self, message: str, position: Position) -> None:
        self.erreurs.append(ErreurSemantique(message, position))

    def chercher(self, nom: str) -> Symbole | None:
        for portee in reversed(self.portees):
            if nom in portee:
                return portee[nom]
        return None

    @property
    def haut(self) -> bool:
        return len(self.portees) == 1

    def declarer(self, nom: str, genre: GenreSymbole, position: Position) -> None:
        if nom in FONCTIONS:
            self.signaler(
                f"'{nom}' est le nom d'une fonction prédéfinie, choisissez-en un autre",
                position,
            )
        existant = self.chercher(nom)
        if existant is not None:
            self.signaler(
                f"'{nom}' est déjà déclaré (ligne {existant.position.ligne})",
                position,
            )
        self.portees[-1][nom] = Symbole(nom, genre, self.haut, position)
        if self.haut and genre in (GenreSymbole.SOURCE, GenreSymbole.DERIVEE):
            self.cellules.append(nom)
            self.genres[nom] = genre

    # --- Programme et blocs -------------------------------------------------

    def analyser(self, programme: Programme) -> Analyse:
        for instruction in programme.instructions:
            self.instruction(instruction)
        if self.erreurs:
            trie = sorted(
                self.erreurs,
                key=lambda e: (e.ligne or 0, e.colonne or 0),
            )
            raise ErreurCompilation(tuple(trie))
        return Analyse(
            programme,
            tuple(self.cellules),
            dict(self.genres),
            dict(self.dependances),
        )

    def bloc(self, bloc: Bloc) -> None:
        self.portees.append({})
        for instruction in bloc.instructions:
            self.instruction(instruction)
        self.portees.pop()

    # --- Instructions -------------------------------------------------------

    def instruction(self, instruction: Instruction | Liaison | Observation) -> None:
        match instruction:
            case Declaration(nom=nom, valeur=valeur, position_nom=position):
                self.expression(valeur)  # avant de déclarer : `soit x = x + 1` est faux
                genre = GenreSymbole.SOURCE if self.haut else GenreSymbole.LOCALE
                self.declarer(nom, genre, position)
            case Liaison(nom=nom, valeur=valeur, position_nom=position):
                citees: set[str] = set()
                self.expression(valeur, citees)
                self.declarer(nom, GenreSymbole.DERIVEE, position)
                self.dependances[nom] = frozenset(citees)
            case Affectation(nom=nom, valeur=valeur, position=position):
                self.affectation(nom, position)
                self.expression(valeur)
            case Si(condition=condition, alors=alors, sinon=sinon):
                self.expression(condition)
                self.bloc(alors)
                if isinstance(sinon, Si):
                    self.instruction(sinon)
                elif sinon is not None:
                    self.bloc(sinon)
            case Pour() as pour:
                self.pour(pour)
            case Affiche(valeurs=valeurs):
                for valeur in valeurs:
                    self.expression(valeur)
            case Observation() as observation:
                self.observation(observation)

    def affectation(self, nom: str, position: Position) -> None:
        symbole = self.chercher(nom)
        if symbole is None:
            self.signaler(f"nom '{nom}' non déclaré", position)
        elif symbole.genre is GenreSymbole.DERIVEE:
            self.signaler(
                f"'{nom}' est une cellule dérivée (lie), "
                "on ne peut pas lui affecter de valeur",
                position,
            )
        elif symbole.genre is GenreSymbole.BOUCLE:
            self.signaler(
                f"'{nom}' est une variable de boucle, "
                "on ne peut pas lui affecter de valeur",
                position,
            )
        elif self.dans_observateur and symbole.haut:
            self.signaler(
                f"'{nom}' est une cellule du niveau supérieur : "
                "un observateur (quand) ne peut pas la modifier",
                position,
            )

    def pour(self, pour: Pour) -> None:
        self.expression(pour.debut)
        self.expression(pour.fin)
        # Un seul bloc pour la variable et le corps : `soit i` dans le corps
        # est donc refusé comme une redéclaration.
        self.portees.append({})
        self.declarer(pour.variable, GenreSymbole.BOUCLE, pour.position_variable)
        for instruction in pour.corps.instructions:
            self.instruction(instruction)
        self.portees.pop()

    def observation(self, observation: Observation) -> None:
        symbole = self.portees[0].get(observation.cible)
        if symbole is None:
            if self.chercher(observation.cible) is None:
                self.signaler(
                    f"nom '{observation.cible}' non déclaré", observation.position_cible
                )
            else:
                self.signaler(
                    f"'{observation.cible}' n'est pas une cellule du niveau supérieur",
                    observation.position_cible,
                )
        ancien = self.dans_observateur
        self.dans_observateur = True
        self.bloc(observation.corps)
        self.dans_observateur = ancien

    # --- Expressions --------------------------------------------------------

    @singledispatchmethod
    def expression(
        self, expression: Expression, citees: set[str] | None = None
    ) -> None:
        raise NotImplementedError(type(expression))

    @expression.register
    def _(self, expression: Entier, citees: set[str] | None = None) -> None:
        pass

    @expression.register
    def _(self, expression: Texte, citees: set[str] | None = None) -> None:
        pass

    @expression.register
    def _(self, expression: Booleen, citees: set[str] | None = None) -> None:
        pass

    @expression.register
    def _(self, expression: Nom, citees: set[str] | None = None) -> None:
        if expression.nom in FONCTIONS:
            self.signaler(
                f"'{expression.nom}' est une fonction prédéfinie : "
                f"appelez-la avec des parenthèses, {expression.nom}(...)",
                expression.position,
            )
        elif self.chercher(expression.nom) is None:
            self.signaler(f"nom '{expression.nom}' non déclaré", expression.position)
        elif citees is not None:
            citees.add(expression.nom)

    @expression.register
    def _(self, expression: Unaire, citees: set[str] | None = None) -> None:
        self.expression(expression.operande, citees)

    @expression.register
    def _(self, expression: Binaire, citees: set[str] | None = None) -> None:
        self.expression(expression.gauche, citees)
        self.expression(expression.droite, citees)

    @expression.register
    def _(self, expression: Appel, citees: set[str] | None = None) -> None:
        attendu = FONCTIONS.get(expression.nom)
        if attendu is None:
            self.signaler(
                f"fonction '{expression.nom}' inconnue "
                f"(fonctions prédéfinies : {', '.join(FONCTIONS)})",
                expression.position,
            )
        elif len(expression.arguments) != attendu:
            pluriel = "s" if attendu > 1 else ""
            self.signaler(
                f"{expression.nom} attend {attendu} argument{pluriel}, "
                f"{len(expression.arguments)} donné(s)",
                expression.position,
            )
        for argument in expression.arguments:
            self.expression(argument, citees)


def analyser_semantique(programme: Programme) -> Analyse:
    """Vérifie ``programme`` ; lève ``ErreurCompilation`` avec toutes les erreurs."""
    return Analyseur().analyser(programme)
