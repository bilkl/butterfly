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

RACINE = Path(__file__).resolve().parent.parent


def en_stdio() -> Client:
    """Un client qui lance le serveur comme le ferait l'hôte : en sous-processus."""
    parametres = StdioServerParameters(
        command=sys.executable, args=["-m", "serveur_butterfly"], cwd=RACINE
    )
    return Client(parametres, read_timeout_seconds=30)


async def test_le_point_d_entree_demarre_en_stdio_et_repond() -> None:
    async with en_stdio() as client:
        assert client.server_info is not None
        assert client.server_info.name == "butterfly"
        noms = {o.name for o in (await client.list_tools()).tools}
        assert noms == {"tokenize", "parse", "check", "transpile", "format", "run"}
        reponse = await client.call_tool("check", {"source": "soit a = 1;"})
        assert reponse.structured_content is not None
        assert reponse.structured_content["ok"] is True


async def test_la_configuration_d_exemple_est_valide() -> None:
    config = json.loads((RACINE / "mcp.exemple.json").read_text(encoding="utf-8"))
    serveur = config["mcpServers"]["butterfly"]
    assert serveur["command"] == "uv"
    assert serveur["args"][-2:] == ["-m", "serveur_butterfly"]
    assert (RACINE / "serveur_butterfly" / "__main__.py").is_file()


async def structure(client: Client, outil: str, source: str) -> dict[str, Any]:
    resultat = await client.call_tool(outil, {"source": source})
    assert not resultat.is_error
    assert resultat.structured_content is not None
    return dict(resultat.structured_content)


async def test_exercice_final_une_ia_apprend_butterfly_par_le_serveur_seul() -> None:
    async with en_stdio() as client:
        # 1. Elle lit les instructions, qui la renvoient vers la spécification.
        assert client.instructions is not None
        assert "butterfly://specification" in client.instructions
        specification = (
            await client.read_resource("butterfly://specification")
        ).contents[0]
        assert "soit" in specification.text and "lie" in specification.text  # type: ignore[union-attr]
        index = (await client.read_resource("butterfly://exemples")).contents[0]
        assert "02_cellules" in index.text  # type: ignore[union-attr]
        exemple = (
            await client.read_resource("butterfly://exemples/02_cellules")
        ).contents[0]
        assert "lie total" in exemple.text  # type: ignore[union-attr]

        # 2. Premier jet : il oublie un « ; ».
        brouillon = (
            "soit a = 2;\n"
            "soit b = 3\n"
            "lie somme = a + b;\n"
            'quand somme { affiche "somme :", somme; }\n'
            "a = 10;\n"
        )
        verdict = await structure(client, "check", brouillon)
        assert verdict["ok"] is False
        erreur = verdict["erreurs"][0]
        assert erreur["ligne"] == 2 and erreur["message"].startswith("';' attendu")

        # 3. Il corrige cette ligne ; il y avait une faute de frappe plus loin.
        brouillon = brouillon.replace("soit b = 3\n", "soit b = 3;\n").replace(
            "a + b", "a + c"
        )
        verdict = await structure(client, "check", brouillon)
        assert verdict["ok"] is False
        assert verdict["erreurs"][0]["message"] == "nom 'c' non déclaré"
        assert verdict["erreurs"][0]["ligne"] == 3

        # 4. Il corrige ; le programme est valide, et il l'exécute.
        brouillon = brouillon.replace("a + c", "a + b")
        verdict = await structure(client, "check", brouillon)
        assert verdict["ok"] is True
        assert [c["nom"] for c in verdict["cellules"]] == ["a", "b", "somme"]
        execution = await structure(client, "run", brouillon)
        assert execution["statut"] == "ok"
        assert execution["sortie"] == "somme : 13\n"

        # 5. Il met en forme ; la version formatée donne la même sortie.
        formate = (await structure(client, "format", brouillon))["source"]
        assert (await structure(client, "run", formate))["sortie"] == "somme : 13\n"
