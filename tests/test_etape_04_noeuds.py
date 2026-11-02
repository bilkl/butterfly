"""Étape 4 : l'arbre syntaxique."""

import dataclasses
import json

import pytest

from butterfly.erreurs import Position
from butterfly.noeuds import (
    Entier,
    Nom,
    afficher_arbre,
    en_sexpr,
    noeud_vers_dict,
)
from butterfly.parser import analyser_syntaxe


def test_un_noeud_est_immuable() -> None:
    noeud = Entier(1, Position(1, 1))
    with pytest.raises(dataclasses.FrozenInstanceError):
        noeud.valeur = 2  # type: ignore[misc]


def test_le_dictionnaire_d_un_noeud_garde_son_type() -> None:
    entier = noeud_vers_dict(Entier(1, Position(1, 5)))
    nom = noeud_vers_dict(Nom("x", Position(1, 5)))
    assert entier == {"type": "Entier", "valeur": 1, "ligne": 1, "colonne": 5}
    assert nom == {"type": "Nom", "nom": "x", "ligne": 1, "colonne": 5}


def test_le_dictionnaire_d_un_programme_est_du_json_valide() -> None:
    programme = analyser_syntaxe('soit a = 1 + 2;\nsi a > 1 { affiche "oui"; }')
    texte = json.dumps(noeud_vers_dict(programme))
    reponse = json.loads(texte)
    assert reponse["type"] == "Programme"
    declaration, si = reponse["instructions"]
    assert declaration["type"] == "Declaration"
    assert declaration["valeur"]["type"] == "Binaire"
    assert declaration["valeur"]["operateur"] == "+"
    assert si["type"] == "Si"
    assert si["alors"]["instructions"][0]["type"] == "Affiche"


def test_l_affichage_de_l_arbre_nomme_chaque_noeud() -> None:
    texte = afficher_arbre(analyser_syntaxe("lie b = a + 1;"))
    assert "Liaison" in texte
    assert "Binaire" in texte
    assert "operateur='+'" in texte
    assert "Nom nom='a'" in texte


@pytest.mark.parametrize(
    ("source", "sexpr"),
    [
        ("1", "1"),
        ('"a"', "'a'"),
        ("vrai", "True"),
        ("x", "x"),
        ("-x", "(- x)"),
        ("min(1, 2)", "(min 1 2)"),
        ("a + b", "(+ a b)"),
    ],
)
def test_notation_prefixee(source: str, sexpr: str) -> None:
    programme = analyser_syntaxe(f"affiche {source};")
    affiche = programme.instructions[0]
    assert en_sexpr(affiche.valeurs[0]) == sexpr  # type: ignore[union-attr]
