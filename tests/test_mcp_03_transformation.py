"""MCP, étape 3 : les outils de transformation (transpile, format)."""

from typing import Any

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio


async def call_tool_(client: Client, tool: str, source: str) -> dict[str, Any]:
    result = await client.call_tool(tool, {"source": source})
    assert not result.is_error, result.content
    assert result.structured_content is not None
    return dict(result.structured_content)


async def test_transpile_renvoie_du_python_valide(client: Client) -> None:
    response = await call_tool_(
        client, "transpile", "let a = 2; bind b = a * 2; print b;"
    )
    assert response["ok"] is True
    assert response["errors"] == []
    compile(response["python"], "<test>", "exec")
    assert "v_b = _calc_b()" in response["python"]


async def test_transpile_d_un_programme_faux_renvoie_les_erreurs(
    client: Client,
) -> None:
    response = await call_tool_(client, "transpile", "print x;")
    assert response["ok"] is False
    assert response["python"] is None
    assert response["errors"][0]["message"] == "name 'x' not declared"


async def test_format_renvoie_la_presentation_canonique(client: Client) -> None:
    response = await call_tool_(client, "format", "let   a=1;if a>0{print a;}")
    assert response["ok"] is True
    assert response["source"] == "let a = 1;\nif a > 0 {\n    print a;\n}\n"


async def test_format_conserve_les_commentaires(client: Client) -> None:
    response = await call_tool_(client, "format", "# titre\nlet a = 1;   # note\n")
    assert response["source"] == "# titre\nlet a = 1;  # note\n"


async def test_format_n_exige_que_la_syntaxe(client: Client) -> None:
    response = await call_tool_(client, "format", "print inconnu;")
    assert response["ok"] is True  # le sens n'est pas vérifié


async def test_format_d_une_syntaxe_fausse_renvoie_les_erreurs(client: Client) -> None:
    response = await call_tool_(client, "format", "let a = ;")
    assert response["ok"] is False
    assert response["source"] is None
    assert response["errors"][0]["kind"] == "Syntax error"
