"""MCP, étape 2 : les outils d'analyse (tokenize, parse, check).

Une erreur dans le programme analysé est une réponse **normale** (`ok: false`) :
l'outil a fait son travail en la trouvant. `is_error` est réservé aux cas où
l'outil lui-même n'a pas pu travailler.
"""

from typing import Any

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio


async def call_tool_(client: Client, tool: str, source: str) -> dict[str, Any]:
    result = await client.call_tool(tool, {"source": source})
    assert not result.is_error, result.content
    assert result.structured_content is not None
    return dict(result.structured_content)


# --- tokenize --------------------------------------------------------------------------


async def test_tokenize_renvoie_les_tokens_avec_leur_position(client: Client) -> None:
    response = await call_tool_(client, "tokenize", "let a = 1;")
    assert response["ok"] is True
    types = [t["type"] for t in response["tokens"]]
    assert types == ["LET", "IDENT", "EQ", "INTEGER", "SEMICOLON", "EOF"]
    assert response["tokens"][1] == {
        "type": "IDENT",
        "lexeme": "a",
        "line": 1,
        "column": 5,
    }


async def test_tokenize_renvoie_les_tokens_lus_avant_une_erreur_lexicale(
    client: Client,
) -> None:
    response = await call_tool_(client, "tokenize", "let a @ 1;")
    assert response["ok"] is False
    assert [t["lexeme"] for t in response["tokens"]] == ["let", "a"]
    error = response["errors"][0]
    assert (error["kind"], error["line"], error["column"]) == (
        "Lexical error",
        1,
        7,
    )


# --- parse -----------------------------------------------------------------------------


async def test_parse_renvoie_l_arbre_avec_le_type_de_chaque_noeud(
    client: Client,
) -> None:
    response = await call_tool_(client, "parse", "let a = 1 + 2;")
    assert response["ok"] is True
    declaration = response["tree"]["statements"][0]
    assert declaration["type"] == "Declaration"
    assert declaration["value"]["type"] == "Binary"
    assert declaration["value"]["operator"] == "+"
    assert (declaration["line"], declaration["column"]) == (1, 1)


async def test_parse_signale_toutes_les_erreurs_de_syntaxe(client: Client) -> None:
    response = await call_tool_(client, "parse", "let a = ;\nlet b = 2\nprint 3;")
    assert response["ok"] is False
    assert response["tree"] is None
    assert [e["line"] for e in response["errors"]] == [1, 2]
    assert all(e["kind"] == "Syntax error" for e in response["errors"])


async def test_parse_ne_fait_pas_l_analyse_semantique(client: Client) -> None:
    assert (await call_tool_(client, "parse", "print inconnu;"))["ok"] is True


# --- check -----------------------------------------------------------------------------


async def test_check_d_un_programme_correct_decrit_ses_cellules(client: Client) -> None:
    response = await call_tool_(
        client,
        "check",
        "let a = 1; let b = 2; bind c = a + b; if true { let t = 0; }",
    )
    assert response["ok"] is True
    assert response["errors"] == []
    assert response["cells"] == [
        {"name": "a", "kind": "source", "depends_on": []},
        {"name": "b", "kind": "source", "depends_on": []},
        {"name": "c", "kind": "derived", "depends_on": ["a", "b"]},
    ]


async def test_check_signale_les_erreurs_semantiques_avec_leur_contexte(
    client: Client,
) -> None:
    response = await call_tool_(
        client, "check", "let a = 1;\nbind b = a;\nb = 2;\nprint c;"
    )
    assert response["ok"] is False
    first_, second_ = response["errors"]
    assert first_["kind"] == "Semantic error"
    assert (first_["line"], first_["column"]) == (3, 1)
    assert "derived cell" in first_["message"]
    assert "3 | b = 2;" in first_["context"]
    assert "^" in first_["context"]
    assert second_["message"] == "name 'c' not declared"


async def test_check_signale_une_erreur_lexicale(client: Client) -> None:
    response = await call_tool_(client, "check", "print 1.5;")
    assert response["ok"] is False
    assert response["errors"][0]["kind"] == "Lexical error"


async def test_une_erreur_du_programme_n_est_pas_une_erreur_de_l_outil(
    client: Client,
) -> None:
    result = await client.call_tool("check", {"source": "print ;"})
    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["ok"] is False
