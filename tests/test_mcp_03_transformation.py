"""MCP, étape 3 : les outils de transformation (transpile, format)."""

from typing import Any

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio


async def appeler(client: Client, outil: str, source: str) -> dict[str, Any]:
    resultat = await client.call_tool(outil, {"source": source})
    assert not resultat.is_error, resultat.content
    assert resultat.structured_content is not None
    return dict(resultat.structured_content)


async def test_transpile_renvoie_du_python_valide(client: Client) -> None:
    reponse = await appeler(
        client, "transpile", "soit a = 2; lie b = a * 2; affiche b;"
    )
    assert reponse["ok"] is True
    assert reponse["erreurs"] == []
    compile(reponse["python"], "<test>", "exec")
    assert "v_b = _calc_b()" in reponse["python"]


async def test_transpile_d_un_programme_faux_renvoie_les_erreurs(
    client: Client,
) -> None:
    reponse = await appeler(client, "transpile", "affiche x;")
    assert reponse["ok"] is False
    assert reponse["python"] is None
    assert reponse["erreurs"][0]["message"] == "nom 'x' non déclaré"


async def test_format_renvoie_la_presentation_canonique(client: Client) -> None:
    reponse = await appeler(client, "format", "soit   a=1;si a>0{affiche a;}")
    assert reponse["ok"] is True
    assert reponse["source"] == "soit a = 1;\nsi a > 0 {\n    affiche a;\n}\n"


async def test_format_conserve_les_commentaires(client: Client) -> None:
    reponse = await appeler(client, "format", "# titre\nsoit a = 1;   # note\n")
    assert reponse["source"] == "# titre\nsoit a = 1;  # note\n"


async def test_format_n_exige_que_la_syntaxe(client: Client) -> None:
    reponse = await appeler(client, "format", "affiche inconnu;")
    assert reponse["ok"] is True  # le sens n'est pas vérifié


async def test_format_d_une_syntaxe_fausse_renvoie_les_erreurs(client: Client) -> None:
    reponse = await appeler(client, "format", "soit a = ;")
    assert reponse["ok"] is False
    assert reponse["source"] is None
    assert reponse["erreurs"][0]["genre"] == "Erreur de syntaxe"
