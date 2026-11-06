"""MCP, étape 5 : resources (spécification, exemples) et prompts."""

from pathlib import Path

import pytest
from mcp import Client, MCPError

from butterfly_server.server import available_examples

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parent.parent
NAMES = sorted(p.stem for p in (ROOT / "examples").glob("*.fly"))


async def read_line(client: Client, uri: str) -> str:
    content = (await client.read_resource(uri)).contents[0]
    text = getattr(content, "text", None)
    assert isinstance(text, str)
    return text


async def test_les_resources_fixes_sont_annoncees(client: Client) -> None:
    resources = {str(r.uri): r for r in (await client.list_resources()).resources}
    assert set(resources) == {"butterfly://specification", "butterfly://examples"}
    assert resources["butterfly://specification"].mime_type == "text/markdown"
    assert resources["butterfly://specification"].description


async def test_les_modeles_d_uri_sont_annonces(client: Client) -> None:
    templates = (await client.list_resource_templates()).resource_templates
    assert {m.uri_template for m in templates} == {
        "butterfly://examples/{name}",
        "butterfly://examples/{name}/expected",
    }


async def test_la_specification_est_lisible(client: Client) -> None:
    text = await read_line(client, "butterfly://specification")
    assert text == (ROOT / "specification.md").read_text(encoding="utf-8")
    assert "Grammar (EBNF)" in text


async def test_l_index_liste_chaque_exemple_avec_sa_description(client: Client) -> None:
    index = await read_line(client, "butterfly://examples")
    for name in NAMES:
        assert f"butterfly://examples/{name}" in index
        assert f"butterfly://examples/{name}/expected" in index
    assert "A derived cell (bind) follows its sources" in index


@pytest.mark.parametrize("name", NAMES)
async def test_chaque_exemple_et_sa_sortie_sont_lisibles(
    client: Client, name: str
) -> None:
    program = await read_line(client, f"butterfly://examples/{name}")
    expected = await read_line(client, f"butterfly://examples/{name}/expected")
    assert program == (ROOT / "examples" / f"{name}.fly").read_text(encoding="utf-8")
    assert expected == (ROOT / "examples" / f"{name}.expected").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "uri",
    [
        "butterfly://examples/inconnu",
        "butterfly://examples/inconnu/expected",
        "butterfly://examples/../specification",
        "butterfly://examples/..%2Fspecification",
        "butterfly://examples/%2E%2E%2F%2E%2E%2Fetc%2Fpasswd",
        "butterfly://examples//etc/passwd",
        "butterfly://examples/01_expressions%00",
    ],
)
async def test_un_nom_hors_de_la_liste_est_refuse(client: Client, uri: str) -> None:
    with pytest.raises(MCPError):
        await client.read_resource(uri)


def test_la_liste_des_exemples_est_fermee() -> None:
    assert set(available_examples()) == set(NAMES)
    assert "../specification" not in available_examples()


async def test_les_prompts_sont_annonces(client: Client) -> None:
    prompts = {p.name: p for p in (await client.list_prompts()).prompts}
    assert set(prompts) == {"write_program", "fix_program"}
    assert [a.name for a in prompts["write_program"].arguments or []] == ["task"]
    assert [a.name for a in prompts["fix_program"].arguments or []] == [
        "source",
        "errors",
    ]


async def test_le_prompt_ecrire_programme_decrit_la_methode(client: Client) -> None:
    prompt = await client.get_prompt("write_program", {"task": "compter jusqu'à trois"})
    text = prompt.messages[0].content.text  # type: ignore[union-attr]
    assert "compter jusqu'à trois" in text
    for expected in ("butterfly://specification", "check", "run", "format"):
        assert expected in text


async def test_le_prompt_corriger_programme_contient_le_code_et_les_erreurs(
    client: Client,
) -> None:
    prompt = await client.get_prompt(
        "fix_program", {"source": "print x;", "errors": "name 'x' not declared"}
    )
    text = prompt.messages[0].content.text  # type: ignore[union-attr]
    assert "print x;" in text
    assert "name 'x' not declared" in text
