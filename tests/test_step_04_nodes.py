"""Étape 4 : l'arbre syntaxique."""

import dataclasses
import json

import pytest

from butterfly.errors import Position
from butterfly.nodes import (
    Integer,
    Name,
    node_to_dict,
    print_tree,
    to_sexpr,
)
from butterfly.parser import analyze_syntax


def test_un_noeud_est_immuable() -> None:
    node = Integer(1, Position(1, 1))
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.value = 2  # type: ignore[misc]


def test_le_dictionnaire_d_un_noeud_garde_son_type() -> None:
    integer = node_to_dict(Integer(1, Position(1, 5)))
    name = node_to_dict(Name("x", Position(1, 5)))
    assert integer == {"type": "Integer", "value": 1, "line": 1, "column": 5}
    assert name == {"type": "Name", "name": "x", "line": 1, "column": 5}


def test_le_dictionnaire_d_un_programme_est_du_json_valide() -> None:
    program = analyze_syntax('let a = 1 + 2;\nif a > 1 { print "oui"; }')
    text = json.dumps(node_to_dict(program))
    response = json.loads(text)
    assert response["type"] == "Program"
    declaration, if_stmt = response["statements"]
    assert declaration["type"] == "Declaration"
    assert declaration["value"]["type"] == "Binary"
    assert declaration["value"]["operator"] == "+"
    assert if_stmt["type"] == "If"
    assert if_stmt["then_block"]["statements"][0]["type"] == "Print"


def test_l_affichage_de_l_arbre_nomme_chaque_noeud() -> None:
    text = print_tree(analyze_syntax("bind b = a + 1;"))
    assert "Binding" in text
    assert "Binary" in text
    assert "operator='+'" in text
    assert "Name name='a'" in text


@pytest.mark.parametrize(
    ("source", "sexpr"),
    [
        ("1", "1"),
        ('"a"', "'a'"),
        ("true", "True"),
        ("x", "x"),
        ("-x", "(- x)"),
        ("min(1, 2)", "(min 1 2)"),
        ("a + b", "(+ a b)"),
    ],
)
def test_notation_prefixee(source: str, sexpr: str) -> None:
    program = analyze_syntax(f"print {source};")
    print_stmt = program.statements[0]
    assert to_sexpr(print_stmt.values[0]) == sexpr  # type: ignore[union-attr]
