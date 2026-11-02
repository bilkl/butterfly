"""Les nœuds de l'arbre syntaxique (AST).

Un nœud par construction du langage, regroupés en deux unions : les
**expressions** (qui ont une valeur) et les **instructions** (qui font quelque
chose). Le module s'appelle ``noeuds`` et non ``ast`` pour ne pas masquer le
module ``ast`` de la bibliothèque standard.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any

from butterfly.erreurs import Position

# --- Expressions ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Entier:
    valeur: int
    position: Position


@dataclass(frozen=True, slots=True)
class Texte:
    valeur: str
    position: Position


@dataclass(frozen=True, slots=True)
class Booleen:
    valeur: bool
    position: Position


@dataclass(frozen=True, slots=True)
class Nom:
    nom: str
    position: Position


@dataclass(frozen=True, slots=True)
class Unaire:
    """``-x`` ou ``non x``. La position est celle de l'opérateur."""

    operateur: str
    operande: Expression
    position: Position


@dataclass(frozen=True, slots=True)
class Binaire:
    """Une opération à deux opérandes. La position est celle de l'opérateur."""

    operateur: str
    gauche: Expression
    droite: Expression
    position: Position


@dataclass(frozen=True, slots=True)
class Appel:
    """Un appel de fonction prédéfinie : ``min(a, b)``."""

    nom: str
    arguments: tuple[Expression, ...]
    position: Position


type Expression = Entier | Texte | Booleen | Nom | Unaire | Binaire | Appel

# --- Instructions ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Declaration:
    """``soit x = e;`` : crée une cellule source (ou une variable locale)."""

    nom: str
    valeur: Expression
    position: Position
    position_nom: Position


@dataclass(frozen=True, slots=True)
class Affectation:
    """``x = e;``"""

    nom: str
    valeur: Expression
    position: Position


@dataclass(frozen=True, slots=True)
class Bloc:
    """``{ ... }`` : ``position`` est l'accolade ouvrante, ``fin`` la fermante."""

    instructions: tuple[Instruction, ...]
    position: Position
    fin: Position


@dataclass(frozen=True, slots=True)
class Si:
    """``si c { ... } sinon si c2 { ... } sinon { ... }``"""

    condition: Expression
    alors: Bloc
    sinon: Si | Bloc | None
    position: Position


@dataclass(frozen=True, slots=True)
class Pour:
    """``pour i dans a..b { ... }`` (borne haute exclue)."""

    variable: str
    debut: Expression
    fin: Expression
    corps: Bloc
    position: Position
    position_variable: Position


@dataclass(frozen=True, slots=True)
class Affiche:
    """``affiche e1, e2;``"""

    valeurs: tuple[Expression, ...]
    position: Position


type Instruction = Declaration | Affectation | Si | Pour | Affiche

# --- Niveau supérieur uniquement ------------------------------------------------


@dataclass(frozen=True, slots=True)
class Liaison:
    """``lie y = e;`` : crée une cellule dérivée."""

    nom: str
    valeur: Expression
    position: Position
    position_nom: Position


@dataclass(frozen=True, slots=True)
class Observation:
    """``quand y { ... }`` : bloc exécuté chaque fois que ``y`` change."""

    cible: str
    corps: Bloc
    position: Position
    position_cible: Position


type InstructionHaute = Instruction | Liaison | Observation


@dataclass(frozen=True, slots=True)
class Programme:
    instructions: tuple[InstructionHaute, ...]


type Noeud = Expression | InstructionHaute | Bloc | Programme

# --- Outils d'affichage ---------------------------------------------------------


def noeud_vers_dict(noeud: object) -> Any:
    """Convertit un nœud en dictionnaire JSON, avec une clé ``"type"``.

    ``dataclasses.asdict`` perdrait le nom du nœud : ``Nom("x")`` et
    ``Texte("x")`` deviendraient presque identiques. Les positions sont mises à
    plat (``ligne`` et ``colonne``) ; les autres positions gardent leur nom.
    """
    if isinstance(noeud, tuple):
        return [noeud_vers_dict(element) for element in noeud]
    if isinstance(noeud, Position):
        return {"ligne": noeud.ligne, "colonne": noeud.colonne}
    if is_dataclass(noeud) and not isinstance(noeud, type):
        resultat: dict[str, Any] = {"type": type(noeud).__name__}
        for champ in fields(noeud):
            valeur = getattr(noeud, champ.name)
            if champ.name == "position":
                resultat["ligne"] = valeur.ligne
                resultat["colonne"] = valeur.colonne
            else:
                resultat[champ.name] = noeud_vers_dict(valeur)
        return resultat
    return noeud


def en_sexpr(expression: Expression) -> str:
    """Une expression en notation préfixée compacte : ``2 + 3 * 4`` donne
    ``(+ 2 (* 3 4))``. Pratique pour vérifier les priorités dans les tests."""
    match expression:
        case Entier(valeur=valeur) | Texte(valeur=valeur) | Booleen(valeur=valeur):
            return repr(valeur)
        case Nom(nom=nom):
            return nom
        case Unaire(operateur=operateur, operande=operande):
            return f"({operateur} {en_sexpr(operande)})"
        case Binaire(operateur=operateur, gauche=gauche, droite=droite):
            return f"({operateur} {en_sexpr(gauche)} {en_sexpr(droite)})"
        case Appel(nom=nom, arguments=arguments):
            return f"({nom} {' '.join(en_sexpr(a) for a in arguments)})".replace(
                " )", ")"
            )
    raise AssertionError(f"expression inconnue : {expression!r}")


def afficher_arbre(noeud: object, indentation: int = 0) -> str:
    """Un affichage indenté de l'arbre, lisible par un humain."""
    marge = "  " * indentation
    if isinstance(noeud, tuple):
        return "\n".join(afficher_arbre(element, indentation) for element in noeud)
    if is_dataclass(noeud) and not isinstance(noeud, type):
        simples: list[str] = []
        enfants: list[tuple[str, object]] = []
        for champ in fields(noeud):
            valeur = getattr(noeud, champ.name)
            if (
                champ.name.startswith("position")
                or champ.name == "fin"
                and isinstance(valeur, Position)
            ):
                continue
            if isinstance(valeur, tuple) or is_dataclass(valeur):
                enfants.append((champ.name, valeur))
            elif valeur is not None:
                simples.append(f"{champ.name}={valeur!r}")
        titre = f"{marge}{type(noeud).__name__}"
        if simples:
            titre += " " + " ".join(simples)
        lignes = [titre]
        for nom, enfant in enfants:
            if isinstance(enfant, tuple) and not enfant:
                continue
            lignes.append(f"{marge}  {nom}:")
            lignes.append(afficher_arbre(enfant, indentation + 2))
        return "\n".join(lignes)
    return f"{marge}{noeud!r}"
