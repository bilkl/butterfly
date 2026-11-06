"""Les nœuds de l'arbre syntaxique (AST).

Un nœud par construction du langage, regroupés en deux unions : les
**expressions** (qui ont une valeur) et les **instructions** (qui font quelque
chose). Le module s'appelle ``noeuds`` et non ``ast`` pour ne pas masquer le
module ``ast`` de la bibliothèque standard.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any

from butterfly.errors import Position

# --- Expressions ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Integer:
    value: int
    position: Position


@dataclass(frozen=True, slots=True)
class Text:
    value: str
    position: Position


@dataclass(frozen=True, slots=True)
class Boolean:
    value: bool
    position: Position


@dataclass(frozen=True, slots=True)
class Name:
    name: str
    position: Position


@dataclass(frozen=True, slots=True)
class Unary:
    """``-x`` ou ``non x``. La position est celle de l'opérateur."""

    operator: str
    operand: Expression
    position: Position


@dataclass(frozen=True, slots=True)
class Binary:
    """Une opération à deux opérandes. La position est celle de l'opérateur."""

    operator: str
    left: Expression
    right: Expression
    position: Position


@dataclass(frozen=True, slots=True)
class Call:
    """Un appel de fonction prédéfinie : ``min(a, b)``."""

    name: str
    arguments: tuple[Expression, ...]
    position: Position


type Expression = Integer | Text | Boolean | Name | Unary | Binary | Call

# --- Instructions ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Declaration:
    """``soit x = e;`` : crée une cellule source (ou une variable locale)."""

    name: str
    value: Expression
    position: Position
    name_position: Position


@dataclass(frozen=True, slots=True)
class Assignment:
    """``x = e;``"""

    name: str
    value: Expression
    position: Position


@dataclass(frozen=True, slots=True)
class Block:
    """``{ ... }`` : ``position`` est l'accolade ouvrante, ``fin`` la fermante."""

    statements: tuple[Statement, ...]
    position: Position
    end: Position


@dataclass(frozen=True, slots=True)
class If:
    """``si c { ... } sinon si c2 { ... } sinon { ... }``"""

    condition: Expression
    then_block: Block
    else_branch: If | Block | None
    position: Position


@dataclass(frozen=True, slots=True)
class For:
    """``pour i dans a..b { ... }`` (borne haute exclue)."""

    variable: str
    start: Expression
    end: Expression
    body: Block
    position: Position
    variable_position: Position


@dataclass(frozen=True, slots=True)
class Print:
    """``affiche e1, e2;``"""

    values: tuple[Expression, ...]
    position: Position


type Statement = Declaration | Assignment | If | For | Print

# --- Niveau supérieur uniquement ------------------------------------------------


@dataclass(frozen=True, slots=True)
class Binding:
    """``lie y = e;`` : crée une cellule dérivée."""

    name: str
    value: Expression
    position: Position
    name_position: Position


@dataclass(frozen=True, slots=True)
class Observer:
    """``quand y { ... }`` : bloc exécuté chaque fois que ``y`` change."""

    target: str
    body: Block
    position: Position
    target_position: Position


type TopLevelStatement = Statement | Binding | Observer


@dataclass(frozen=True, slots=True)
class Program:
    statements: tuple[TopLevelStatement, ...]


type Node = Expression | TopLevelStatement | Block | Program

# --- Outils d'affichage ---------------------------------------------------------


def node_to_dict(node: object) -> Any:
    """Convertit un nœud en dictionnaire JSON, avec une clé ``"type"``.

    ``dataclasses.asdict`` perdrait le nom du nœud : ``Nom("x")`` et
    ``Texte("x")`` deviendraient presque identiques. Les positions sont mises à
    plat (``ligne`` et ``colonne``) ; les autres positions gardent leur nom.
    """
    if isinstance(node, tuple):
        return [node_to_dict(element) for element in node]
    if isinstance(node, Position):
        return {"line": node.line, "column": node.column}
    if is_dataclass(node) and not isinstance(node, type):
        result: dict[str, Any] = {"type": type(node).__name__}
        for field in fields(node):
            value = getattr(node, field.name)
            if field.name == "position":
                result["line"] = value.line
                result["column"] = value.column
            else:
                result[field.name] = node_to_dict(value)
        return result
    return node


def to_sexpr(expression: Expression) -> str:
    """Une expression en notation préfixée compacte : ``2 + 3 * 4`` donne
    ``(+ 2 (* 3 4))``. Pratique pour vérifier les priorités dans les tests."""
    match expression:
        case Integer(value=value) | Text(value=value) | Boolean(value=value):
            return repr(value)
        case Name(name=name):
            return name
        case Unary(operator=operator, operand=operand):
            return f"({operator} {to_sexpr(operand)})"
        case Binary(operator=operator, left=left, right=right):
            return f"({operator} {to_sexpr(left)} {to_sexpr(right)})"
        case Call(name=name, arguments=arguments):
            return f"({name} {' '.join(to_sexpr(a) for a in arguments)})".replace(
                " )", ")"
            )
    raise AssertionError(f"expression inconnue : {expression!r}")


def print_tree(node: object, indentation: int = 0) -> str:
    """Un affichage indenté de l'arbre, lisible par un humain."""
    margin = "  " * indentation
    if isinstance(node, tuple):
        return "\n".join(print_tree(element, indentation) for element in node)
    if is_dataclass(node) and not isinstance(node, type):
        simple: list[str] = []
        children: list[tuple[str, object]] = []
        for field in fields(node):
            value = getattr(node, field.name)
            if (
                field.name.startswith("position")
                or field.name == "end"
                and isinstance(value, Position)
            ):
                continue
            if isinstance(value, tuple) or is_dataclass(value):
                children.append((field.name, value))
            elif value is not None:
                simple.append(f"{field.name}={value!r}")
        title = f"{margin}{type(node).__name__}"
        if simple:
            title += " " + " ".join(simple)
        lines = [title]
        for name, child in children:
            if isinstance(child, tuple) and not child:
                continue
            lines.append(f"{margin}  {name}:")
            lines.append(print_tree(child, indentation + 2))
        return "\n".join(lines)
    return f"{margin}{node!r}"
