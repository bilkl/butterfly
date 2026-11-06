"""MCP, étape 6 : intégration : le vrai point d'entrée, et l'exercice final.

L'« exercice final » du projet : une IA qui ne connaît pas Butterfly doit écrire,
vérifier, corriger et exécuter un programme, **uniquement** via le serveur. Ici,
l'IA est scriptée, mais elle se comporte comme la vraie : elle lit les
instructions, la spécification, un exemple, puis se corrige d'après les erreurs.
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp import Client, StdioServerParameters

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parent.parent


def over_stdio() -> Client:
    """Un client qui lance le serveur comme le ferait l'hôte : en sous-processus."""
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "butterfly_server"], cwd=ROOT
    )
    return Client(parameters, read_timeout_seconds=30)


async def test_le_point_d_entree_demarre_en_stdio_et_repond() -> None:
    async with over_stdio() as client:
        assert client.server_info is not None
        assert client.server_info.name == "butterfly"
        names = {o.name for o in (await client.list_tools()).tools}
        assert names == {"tokenize", "parse", "check", "transpile", "format", "run"}
        response = await client.call_tool("check", {"source": "let a = 1;"})
        assert response.structured_content is not None
        assert response.structured_content["ok"] is True


async def test_la_configuration_d_exemple_est_valide() -> None:
    config = json.loads((ROOT / "mcp.example.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["butterfly"]
    assert server["command"] == "uv"
    assert server["args"][-2:] == ["-m", "butterfly_server"]
    assert (ROOT / "butterfly_server" / "__main__.py").is_file()


async def structure(client: Client, tool: str, source: str) -> dict[str, Any]:
    result = await client.call_tool(tool, {"source": source})
    assert not result.is_error
    assert result.structured_content is not None
    return dict(result.structured_content)


async def test_exercice_final_une_ia_apprend_butterfly_par_le_serveur_seul() -> None:
    async with over_stdio() as client:
        # 1. Elle lit les instructions, qui la renvoient vers la spécification.
        assert client.instructions is not None
        assert "butterfly://specification" in client.instructions
        specification = (
            await client.read_resource("butterfly://specification")
        ).contents[0]
        assert "let" in specification.text and "bind" in specification.text  # type: ignore[union-attr]
        index = (await client.read_resource("butterfly://examples")).contents[0]
        assert "02_cells" in index.text  # type: ignore[union-attr]
        example = (
            await client.read_resource("butterfly://examples/02_cells")
        ).contents[0]
        assert "bind total" in example.text  # type: ignore[union-attr]

        # 2. Premier jet : il oublie un « ; ».
        draft = (
            "let a = 2;\n"
            "let b = 3\n"
            "bind sum = a + b;\n"
            'when sum { print "somme :", sum; }\n'
            "a = 10;\n"
        )
        verdict = await structure(client, "check", draft)
        assert verdict["ok"] is False
        error = verdict["errors"][0]
        assert error["line"] == 2 and error["message"].startswith("';' expected")

        # 3. Il corrige cette ligne ; il y avait une faute de frappe plus loin.
        draft = draft.replace("let b = 3\n", "let b = 3;\n").replace("a + b", "a + c")
        verdict = await structure(client, "check", draft)
        assert verdict["ok"] is False
        assert verdict["errors"][0]["message"] == "name 'c' not declared"
        assert verdict["errors"][0]["line"] == 3

        # 4. Il corrige ; le programme est valide, et il l'exécute.
        draft = draft.replace("a + c", "a + b")
        verdict = await structure(client, "check", draft)
        assert verdict["ok"] is True
        assert [c["name"] for c in verdict["cells"]] == ["a", "b", "sum"]
        execution_result = await structure(client, "run", draft)
        assert execution_result["status"] == "ok"
        assert execution_result["output"] == "somme : 13\n"

        # 5. Il met en forme ; la version formatée donne la même sortie.
        formatted = (await structure(client, "format", draft))["source"]
        assert (await structure(client, "run", formatted))["output"] == "somme : 13\n"
