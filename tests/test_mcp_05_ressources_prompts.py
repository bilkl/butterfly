"""MCP, étape 5 : resources (spécification, exemples) et prompts."""

from pathlib import Path

import pytest
from mcp import Client, MCPError

from serveur_butterfly.serveur import exemples_disponibles

pytestmark = pytest.mark.anyio

RACINE = Path(__file__).resolve().parent.parent
NOMS = sorted(p.stem for p in (RACINE / "exemples").glob("*.fly"))


async def lire(client: Client, uri: str) -> str:
    contenu = (await client.read_resource(uri)).contents[0]
    texte = getattr(contenu, "text", None)
    assert isinstance(texte, str)
    return texte


async def test_les_resources_fixes_sont_annoncees(client: Client) -> None:
    ressources = {str(r.uri): r for r in (await client.list_resources()).resources}
    assert set(ressources) == {"butterfly://specification", "butterfly://exemples"}
    assert ressources["butterfly://specification"].mime_type == "text/markdown"
    assert ressources["butterfly://specification"].description


async def test_les_modeles_d_uri_sont_annonces(client: Client) -> None:
    modeles = (await client.list_resource_templates()).resource_templates
    assert {m.uri_template for m in modeles} == {
        "butterfly://exemples/{nom}",
        "butterfly://exemples/{nom}/attendu",
    }


async def test_la_specification_est_lisible(client: Client) -> None:
    texte = await lire(client, "butterfly://specification")
    assert texte == (RACINE / "specification.md").read_text(encoding="utf-8")
    assert "Grammar (EBNF)" in texte


async def test_l_index_liste_chaque_exemple_avec_sa_description(client: Client) -> None:
    index = await lire(client, "butterfly://exemples")
    for nom in NOMS:
        assert f"butterfly://exemples/{nom}" in index
        assert f"butterfly://exemples/{nom}/attendu" in index
    assert "A derived cell (lie) follows its sources" in index


@pytest.mark.parametrize("nom", NOMS)
async def test_chaque_exemple_et_sa_sortie_sont_lisibles(
    client: Client, nom: str
) -> None:
    programme = await lire(client, f"butterfly://exemples/{nom}")
    attendu = await lire(client, f"butterfly://exemples/{nom}/attendu")
    assert programme == (RACINE / "exemples" / f"{nom}.fly").read_text(encoding="utf-8")
    assert attendu == (RACINE / "exemples" / f"{nom}.attendu").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "uri",
    [
        "butterfly://exemples/inconnu",
        "butterfly://exemples/inconnu/attendu",
        "butterfly://exemples/../specification",
        "butterfly://exemples/..%2Fspecification",
        "butterfly://exemples/%2E%2E%2F%2E%2E%2Fetc%2Fpasswd",
        "butterfly://exemples//etc/passwd",
        "butterfly://exemples/01_expressions%00",
    ],
)
async def test_un_nom_hors_de_la_liste_est_refuse(client: Client, uri: str) -> None:
    with pytest.raises(MCPError):
        await client.read_resource(uri)


def test_la_liste_des_exemples_est_fermee() -> None:
    assert set(exemples_disponibles()) == set(NOMS)
    assert "../specification" not in exemples_disponibles()


async def test_les_prompts_sont_annonces(client: Client) -> None:
    prompts = {p.name: p for p in (await client.list_prompts()).prompts}
    assert set(prompts) == {"ecrire_programme", "corriger_programme"}
    assert [a.name for a in prompts["ecrire_programme"].arguments or []] == ["tache"]
    assert [a.name for a in prompts["corriger_programme"].arguments or []] == [
        "source",
        "erreurs",
    ]


async def test_le_prompt_ecrire_programme_decrit_la_methode(client: Client) -> None:
    prompt = await client.get_prompt(
        "ecrire_programme", {"tache": "compter jusqu'à trois"}
    )
    texte = prompt.messages[0].content.text  # type: ignore[union-attr]
    assert "compter jusqu'à trois" in texte
    for attendu in ("butterfly://specification", "check", "run", "format"):
        assert attendu in texte


async def test_le_prompt_corriger_programme_contient_le_code_et_les_erreurs(
    client: Client,
) -> None:
    prompt = await client.get_prompt(
        "corriger_programme", {"source": "affiche x;", "erreurs": "nom 'x' non déclaré"}
    )
    texte = prompt.messages[0].content.text  # type: ignore[union-attr]
    assert "affiche x;" in texte
    assert "nom 'x' non déclaré" in texte
