"""MCP, étape 1 : le serveur, ses outils et leurs schémas."""

import pytest
from mcp import Client

from butterfly_server.server import check_tool

pytestmark = pytest.mark.anyio

TOOLS = {"tokenize", "parse", "check", "transpile", "format", "run"}


def test_le_decorateur_rend_la_fonction_intacte() -> None:
    assert check_tool("let a = 1;")["ok"] is True


async def test_le_serveur_annonce_exactement_les_outils_attendus(
    client: Client,
) -> None:
    tools = (await client.list_tools()).tools
    assert {tool.name for tool in tools} == TOOLS


async def test_chaque_outil_a_une_description_tiree_de_sa_docstring(
    client: Client,
) -> None:
    for tool in (await client.list_tools()).tools:
        assert tool.description
        assert len(tool.description) > 60, tool.name


async def test_le_schema_des_parametres_reflete_les_annotations(client: Client) -> None:
    tools = {o.name: o for o in (await client.list_tools()).tools}
    schema = tools["check"].input_schema
    assert schema["required"] == ["source"]
    assert schema["properties"]["source"]["type"] == "string"
    assert "Butterfly" in schema["properties"]["source"]["description"]


async def test_le_delai_de_run_est_borne_par_le_schema(client: Client) -> None:
    tools = {o.name: o for o in (await client.list_tools()).tools}
    time_limit = tools["run"].input_schema["properties"]["time_limit"]
    assert (time_limit["minimum"], time_limit["maximum"], time_limit["default"]) == (
        0.1,
        5.0,
        2.0,
    )
    assert tools["run"].input_schema["required"] == ["source"]


async def test_chaque_outil_a_un_schema_de_sortie(client: Client) -> None:
    outputs = {o.name: o.output_schema for o in (await client.list_tools()).tools}
    assert set(outputs["check"]["properties"]) == {"ok", "errors", "cells"}  # type: ignore[index]
    assert set(outputs["run"]["properties"]) == {  # type: ignore[index]
        "status", "output", "errors", "duration_seconds",
    }  # fmt: skip


async def test_les_outils_d_analyse_sont_annonces_en_lecture_seule(
    client: Client,
) -> None:
    tools = {o.name: o for o in (await client.list_tools()).tools}
    for name in TOOLS - {"run"}:
        annotations = tools[name].annotations
        assert annotations is not None and annotations.read_only_hint is True, name
    run = tools["run"].annotations
    assert run is not None
    assert run.destructive_hint is False
    assert run.open_world_hint is False


async def test_les_instructions_renvoient_vers_la_specification(client: Client) -> None:
    assert client.instructions is not None
    assert "butterfly://specification" in client.instructions
    for tool in TOOLS:
        assert tool in client.instructions


async def test_le_serveur_s_annonce_sous_le_nom_butterfly(client: Client) -> None:
    assert client.server_info is not None
    assert client.server_info.name == "butterfly"


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("check", {}),  # paramètre manquant
        ("check", {"source": 42}),  # mauvais type
        ("run", {"source": "print 1;", "time_limit": 100}),  # hors bornes
        ("run", {"source": "print 1;", "time_limit": "vite"}),
    ],
)
async def test_des_arguments_invalides_sont_signales_par_is_error(
    client: Client, tool: str, arguments: dict[str, object]
) -> None:
    result = await client.call_tool(tool, arguments)
    assert result.is_error
