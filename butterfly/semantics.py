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

from butterfly.errors import CompilationError, Position, SemanticError
from butterfly.nodes import (
    Assignment,
    Binary,
    Binding,
    Block,
    Boolean,
    Call,
    Declaration,
    Expression,
    For,
    If,
    Integer,
    Name,
    Observer,
    Print,
    Program,
    Statement,
    Text,
    Unary,
)

#: Les fonctions prédéfinies et leur nombre d'arguments.
FUNCTIONS: dict[str, int] = {"min": 2, "max": 2, "abs": 1}


class SymbolKind(Enum):
    SOURCE = auto()  # soit, au niveau supérieur : modifiable, suivie par les lie
    DERIVED = auto()  # lie : toujours égale à sa formule
    LOCAL = auto()  # soit, dans un bloc
    LOOP = auto()  # variable d'un pour : lecture seule


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str
    kind: SymbolKind
    top: bool  # déclaré au niveau supérieur ?
    position: Position


@dataclass(frozen=True)
class Analysis:
    """Le résultat de l'analyse : un arbre vérifié et ce qu'on en a appris."""

    program: Program
    #: Les cellules du niveau supérieur (soit et lie), dans l'ordre de déclaration.
    cells: tuple[str, ...]
    kinds: dict[str, SymbolKind]
    #: Pour chaque cellule dérivée, les cellules citées dans sa formule.
    dependencies: dict[str, frozenset[str]]


class Analyzer:
    def __init__(self) -> None:
        self.scopes: list[dict[str, Symbol]] = [{}]
        self.errors: list[SemanticError] = []
        self.inside_observer = False
        self.cells: list[str] = []
        self.kinds: dict[str, SymbolKind] = {}
        self.dependencies: dict[str, frozenset[str]] = {}

    # --- Outils -------------------------------------------------------------

    def report(self, message: str, position: Position) -> None:
        self.errors.append(SemanticError(message, position))

    def look_up(self, name: str) -> Symbol | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    @property
    def top(self) -> bool:
        return len(self.scopes) == 1

    def declare(self, name: str, kind: SymbolKind, position: Position) -> None:
        if name in FUNCTIONS:
            self.report(
                f"'{name}' is the name of a built-in function, choose another one",
                position,
            )
        existing = self.look_up(name)
        if existing is not None:
            self.report(
                f"'{name}' is already declared (line {existing.position.line})",
                position,
            )
        self.scopes[-1][name] = Symbol(name, kind, self.top, position)
        if self.top and kind in (SymbolKind.SOURCE, SymbolKind.DERIVED):
            self.cells.append(name)
            self.kinds[name] = kind

    # --- Programme et blocs -------------------------------------------------

    def analyze(self, program: Program) -> Analysis:
        for statement in program.statements:
            self.statement(statement)
        if self.errors:
            sorted_errors = sorted(
                self.errors,
                key=lambda e: (e.line or 0, e.column or 0),
            )
            raise CompilationError(tuple(sorted_errors))
        return Analysis(
            program,
            tuple(self.cells),
            dict(self.kinds),
            dict(self.dependencies),
        )

    def block(self, block: Block) -> None:
        self.scopes.append({})
        for statement in block.statements:
            self.statement(statement)
        self.scopes.pop()

    # --- Instructions -------------------------------------------------------

    def statement(self, statement: Statement | Binding | Observer) -> None:
        match statement:
            case Declaration(name=name, value=value, name_position=position):
                self.expression(value)  # avant de déclarer : `soit x = x + 1` est faux
                kind = SymbolKind.SOURCE if self.top else SymbolKind.LOCAL
                self.declare(name, kind, position)
            case Binding(name=name, value=value, name_position=position):
                cited: set[str] = set()
                self.expression(value, cited)
                self.declare(name, SymbolKind.DERIVED, position)
                self.dependencies[name] = frozenset(cited)
            case Assignment(name=name, value=value, position=position):
                self.assignment(name, position)
                self.expression(value)
            case If(
                condition=condition, then_block=then_block, else_branch=else_branch
            ):
                self.expression(condition)
                self.block(then_block)
                if isinstance(else_branch, If):
                    self.statement(else_branch)
                elif else_branch is not None:
                    self.block(else_branch)
            case For() as for_stmt:
                self.for_stmt(for_stmt)
            case Print(values=values):
                for value in values:
                    self.expression(value)
            case Observer() as observer:
                self.observer(observer)

    def assignment(self, name: str, position: Position) -> None:
        symbol = self.look_up(name)
        if symbol is None:
            self.report(f"name '{name}' not declared", position)
        elif symbol.kind is SymbolKind.DERIVED:
            self.report(
                f"'{name}' is a derived cell (bind), a value cannot be assigned to it",
                position,
            )
        elif symbol.kind is SymbolKind.LOOP:
            self.report(
                f"'{name}' is a loop variable, a value cannot be assigned to it",
                position,
            )
        elif self.inside_observer and symbol.top:
            self.report(
                f"'{name}' is a top-level cell: an observer (when) cannot modify it",
                position,
            )

    def for_stmt(self, for_stmt: For) -> None:
        self.expression(for_stmt.start)
        self.expression(for_stmt.end)
        # Un seul bloc pour la variable et le corps : `soit i` dans le corps
        # est donc refusé comme une redéclaration.
        self.scopes.append({})
        self.declare(for_stmt.variable, SymbolKind.LOOP, for_stmt.variable_position)
        for statement in for_stmt.body.statements:
            self.statement(statement)
        self.scopes.pop()

    def observer(self, observer: Observer) -> None:
        symbol = self.scopes[0].get(observer.target)
        if symbol is None:
            if self.look_up(observer.target) is None:
                self.report(
                    f"name '{observer.target}' not declared", observer.target_position
                )
            else:
                self.report(
                    f"'{observer.target}' is not a top-level cell",
                    observer.target_position,
                )
        old = self.inside_observer
        self.inside_observer = True
        self.block(observer.body)
        self.inside_observer = old

    # --- Expressions --------------------------------------------------------

    @singledispatchmethod
    def expression(self, expression: Expression, cited: set[str] | None = None) -> None:
        raise NotImplementedError(type(expression))

    @expression.register
    def _(self, expression: Integer, cited: set[str] | None = None) -> None:
        pass

    @expression.register
    def _(self, expression: Text, cited: set[str] | None = None) -> None:
        pass

    @expression.register
    def _(self, expression: Boolean, cited: set[str] | None = None) -> None:
        pass

    @expression.register
    def _(self, expression: Name, cited: set[str] | None = None) -> None:
        if expression.name in FUNCTIONS:
            self.report(
                f"'{expression.name}' is a built-in function: "
                f"call it with parentheses, {expression.name}(...)",
                expression.position,
            )
        elif self.look_up(expression.name) is None:
            self.report(f"name '{expression.name}' not declared", expression.position)
        elif cited is not None:
            cited.add(expression.name)

    @expression.register
    def _(self, expression: Unary, cited: set[str] | None = None) -> None:
        self.expression(expression.operand, cited)

    @expression.register
    def _(self, expression: Binary, cited: set[str] | None = None) -> None:
        self.expression(expression.left, cited)
        self.expression(expression.right, cited)

    @expression.register
    def _(self, expression: Call, cited: set[str] | None = None) -> None:
        expected = FUNCTIONS.get(expression.name)
        if expected is None:
            self.report(
                f"unknown function '{expression.name}' "
                f"(built-in functions: {', '.join(FUNCTIONS)})",
                expression.position,
            )
        elif len(expression.arguments) != expected:
            plural = "s" if expected > 1 else ""
            self.report(
                f"{expression.name} expects {expected} argument{plural}, "
                f"{len(expression.arguments)} given",
                expression.position,
            )
        for argument in expression.arguments:
            self.expression(argument, cited)


def analyze_semantics(program: Program) -> Analysis:
    """Vérifie ``programme`` ; lève ``ErreurCompilation`` avec toutes les erreurs."""
    return Analyzer().analyze(program)
