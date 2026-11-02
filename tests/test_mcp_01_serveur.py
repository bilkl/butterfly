"""MCP, étape 1 : le serveur, ses outils et leurs schémas."""

import pytest
from mcp import Client

from serveur_butterfly.serveur import outil_check

pytestmark = pytest.mark.anyio

OUTILS = {"tokenize", "parse", "check", "transpile", "format", "run"}


def test_le_decorateur_rend_la_fonction_intacte() -> None:
    assert outil_check("soit a = 1;")["ok"] is True


async def test_le_serveur_annonce_exactement_les_outils_attendus(
    client: Client,
) -> None:
    outils = (await client.list_tools()).tools
    assert {outil.name for outil in outils} == OUTILS


async def test_chaque_outil_a_une_description_tiree_de_sa_docstring(
    client: Client,
) -> None:
    for outil in (await client.list_tools()).tools:
        assert outil.description
        assert len(outil.description) > 60, outil.name


async def test_le_schema_des_parametres_reflete_les_annotations(client: Client) -> None:
    outils = {o.name: o for o in (await client.list_tools()).tools}
    schema = outils["check"].input_schema
    assert schema["required"] == ["source"]
    assert schema["properties"]["source"]["type"] == "string"
    assert "Butterfly" in schema["properties"]["source"]["description"]


async def test_le_delai_de_run_est_borne_par_le_schema(client: Client) -> None:
    outils = {o.name: o for o in (await client.list_tools()).tools}
    delai = outils["run"].input_schema["properties"]["delai"]
    assert (delai["minimum"], delai["maximum"], delai["default"]) == (0.1, 5.0, 2.0)
    assert outils["run"].input_schema["required"] == ["source"]


async def test_chaque_outil_a_un_schema_de_sortie(client: Client) -> None:
    sorties = {o.name: o.output_schema for o in (await client.list_tools()).tools}
    assert set(sorties["check"]["properties"]) == {"ok", "erreurs", "cellules"}  # type: ignore[index]
    assert set(sorties["run"]["properties"]) == {  # type: ignore[index]
        "statut", "sortie", "erreurs", "duree_secondes",
    }  # fmt: skip


async def test_les_outils_d_analyse_sont_annonces_en_lecture_seule(
    client: Client,
) -> None:
    outils = {o.name: o for o in (await client.list_tools()).tools}
    for nom in OUTILS - {"run"}:
        annotations = outils[nom].annotations
        assert annotations is not None and annotations.read_only_hint is True, nom
    run = outils["run"].annotations
    assert run is not None
    assert run.destructive_hint is False
    assert run.open_world_hint is False


async def test_les_instructions_renvoient_vers_la_specification(client: Client) -> None:
    assert client.instructions is not None
    assert "butterfly://specification" in client.instructions
    for outil in OUTILS:
        assert outil in client.instructions


async def test_le_serveur_s_annonce_sous_le_nom_butterfly(client: Client) -> None:
    assert client.server_info is not None
    assert client.server_info.name == "butterfly"


@pytest.mark.parametrize(
    ("outil", "arguments"),
    [
        ("check", {}),  # paramètre manquant
        ("check", {"source": 42}),  # mauvais type
        ("run", {"source": "affiche 1;", "delai": 100}),  # hors bornes
        ("run", {"source": "affiche 1;", "delai": "vite"}),
    ],
)
async def test_des_arguments_invalides_sont_signales_par_is_error(
    client: Client, outil: str, arguments: dict[str, object]
) -> None:
    resultat = await client.call_tool(outil, arguments)
    assert resultat.is_error
