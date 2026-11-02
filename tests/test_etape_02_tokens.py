"""Étape 2 : les types de token et la classe Token."""

import dataclasses

import pytest

from butterfly.erreurs import Position
from butterfly.tokens import (
    MOTS_CLES,
    SYMBOLES_DOUBLES,
    SYMBOLES_SIMPLES,
    Token,
    TypeToken,
)


def test_repr_d_un_token_donne_son_type_son_texte_et_sa_position() -> None:
    token = Token(TypeToken.IDENT, "x", Position(2, 5))
    assert repr(token) == "Token(IDENT, 'x', 2:5)"


def test_un_token_est_immuable() -> None:
    token = Token(TypeToken.ENTIER, "1", Position(1, 1), 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        token.lexeme = "2"  # type: ignore[misc]


def test_deux_tokens_identiques_sont_egaux() -> None:
    a = Token(TypeToken.PLUS, "+", Position(1, 3))
    assert a == Token(TypeToken.PLUS, "+", Position(1, 3))
    assert a != Token(TypeToken.PLUS, "+", Position(1, 4))


def test_les_mots_cles_sont_ceux_de_la_specification() -> None:
    assert set(MOTS_CLES) == {
        "soit", "lie", "quand", "si", "sinon", "pour", "dans",
        "affiche", "vrai", "faux", "et", "ou", "non",
    }  # fmt: skip


def test_tous_les_types_de_symboles_existent_dans_l_enumeration() -> None:
    utilises = {
        *MOTS_CLES.values(),
        *SYMBOLES_DOUBLES.values(),
        *SYMBOLES_SIMPLES.values(),
    }
    # Seuls les types « calculés » (valeurs, divers) n'ont pas de lexème fixe.
    sans_lexeme = {TypeToken.IDENT, TypeToken.ENTIER, TypeToken.TEXTE,
                   TypeToken.COMMENTAIRE, TypeToken.FIN}  # fmt: skip
    assert set(TypeToken) - utilises == sans_lexeme
