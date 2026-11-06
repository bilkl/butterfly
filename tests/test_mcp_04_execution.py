"""MCP, étape 4 : l'outil `run`, exécuté dans un sous-processus borné."""

import tempfile
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from butterfly_server.sandbox import (
    OUTPUT_LIMIT,
    environment,
    execute_isolated,
    read_execution_error,
)

pytestmark = pytest.mark.anyio

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
PROGRAMS = sorted(EXAMPLES.glob("*.fly"))


async def run(client: Client, source: str, time_limit: float = 2.0) -> dict[str, Any]:
    result = await client.call_tool("run", {"source": source, "time_limit": time_limit})
    assert not result.is_error, result.content
    assert result.structured_content is not None
    return dict(result.structured_content)


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda p: p.stem)
async def test_run_donne_la_sortie_attendue_de_chaque_exemple(
    client: Client, program: Path
) -> None:
    response = await run(client, program.read_text(encoding="utf-8"))
    assert response["status"] == "ok"
    assert response["errors"] == []
    assert response["output"] == program.with_suffix(".expected").read_text(
        encoding="utf-8"
    )


async def test_une_erreur_de_compilation_n_est_pas_executee(client: Client) -> None:
    response = await run(client, "print x;")
    assert response["status"] == "compilation_error"
    assert response["output"] == ""
    assert response["errors"][0]["message"] == "name 'x' not declared"
    assert response["duration_seconds"] < 0.5  # aucun processus lancé


async def test_une_erreur_d_execution_est_structuree_avec_la_ligne(
    client: Client,
) -> None:
    response = await run(client, "print 1;\nprint 1 / 0;\nprint 3;")
    assert response["status"] == "execution_error"
    assert response["output"] == "1\n"  # ce qui précède l'erreur est conservé
    error = response["errors"][0]
    assert error["kind"] == "Runtime error"
    assert error["line"] == 2
    assert error["column"] is None
    assert error["message"] == "division by zero"


async def test_les_messages_d_erreur_ne_revelent_pas_le_dossier_temporaire(
    client: Client,
) -> None:
    response = await run(client, "print 1 / 0;")
    context = response["errors"][0]["context"]
    assert tempfile.gettempdir() not in context


async def test_un_programme_trop_long_est_interrompu(client: Client) -> None:
    response = await run(client, "for i in 0..100000000000 { }", time_limit=0.5)
    assert response["status"] == "timeout"
    assert response["duration_seconds"] < 3


async def test_une_sortie_infinie_est_tronquee_puis_le_processus_est_tue(
    client: Client,
) -> None:
    source = 'for i in 0..100000000 { print "xxxxxxxxxxxxxxxxxxxx"; }'
    response = await run(client, source, time_limit=5.0)
    assert response["status"] == "output_truncated"
    assert len(response["output"].encode()) <= OUTPUT_LIMIT
    assert response["duration_seconds"] < 5


async def test_une_consommation_excessive_de_memoire_est_stoppee(
    client: Client,
) -> None:
    source = 'let t = "aaaaaaaaaa"; for i in 0..60 { t = t + t; }'
    response = await run(client, source, time_limit=5.0)
    assert response["status"] == "memory_exceeded"


async def test_un_texte_ne_peut_pas_faire_executer_du_python(client: Client) -> None:
    trap = r"\"); __import__('os').system('echo PWNED > /tmp/pwned_butterfly'); (\""
    response = await run(client, f'print "{trap}";')
    assert response["status"] == "ok"
    assert not Path("/tmp/pwned_butterfly").exists()


async def test_les_dossiers_temporaires_sont_supprimes(client: Client) -> None:
    before = set(Path(tempfile.gettempdir()).glob("butterfly-*"))
    await run(client, "print 1;")
    await run(client, "print 1 / 0;")
    await run(client, "for i in 0..100000000000 { }", time_limit=0.3)
    assert set(Path(tempfile.gettempdir()).glob("butterfly-*")) == before


# --- Le bac à sable lui-même -------------------------------------------------------------


def test_le_fils_n_herite_pas_de_l_environnement_du_serveur(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_DU_SERVEUR", "mot-de-passe")
    assert "SECRET_DU_SERVEUR" not in environment()


def test_un_echec_du_fils_sans_erreur_butterfly_est_classe_erreur_interne() -> None:
    # On contourne `check` : le fils reçoit un programme faux et échoue sans
    # produire d'« Runtime error ».
    result = execute_isolated("print x;")
    assert result.status == "internal_error"
    assert "name 'x' not declared" in result.error


def test_lire_erreur_execution() -> None:
    text = "Runtime error (line 7): division by zero\n  7 | print 1 / 0;\n"
    assert read_execution_error(text) == (7, "division by zero")
    assert read_execution_error("rien de tel") is None
