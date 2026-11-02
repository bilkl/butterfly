"""MCP, étape 4 : l'outil `run`, exécuté dans un sous-processus borné."""

import tempfile
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from serveur_butterfly.bac_a_sable import (
    LIMITE_SORTIE,
    environnement,
    executer_isole,
    lire_erreur_execution,
)

pytestmark = pytest.mark.anyio

EXEMPLES = Path(__file__).resolve().parent.parent / "exemples"
PROGRAMMES = sorted(EXEMPLES.glob("*.fly"))


async def run(client: Client, source: str, delai: float = 2.0) -> dict[str, Any]:
    resultat = await client.call_tool("run", {"source": source, "delai": delai})
    assert not resultat.is_error, resultat.content
    assert resultat.structured_content is not None
    return dict(resultat.structured_content)


@pytest.mark.parametrize("programme", PROGRAMMES, ids=lambda p: p.stem)
async def test_run_donne_la_sortie_attendue_de_chaque_exemple(
    client: Client, programme: Path
) -> None:
    reponse = await run(client, programme.read_text(encoding="utf-8"))
    assert reponse["statut"] == "ok"
    assert reponse["erreurs"] == []
    assert reponse["sortie"] == programme.with_suffix(".attendu").read_text(
        encoding="utf-8"
    )


async def test_une_erreur_de_compilation_n_est_pas_executee(client: Client) -> None:
    reponse = await run(client, "affiche x;")
    assert reponse["statut"] == "erreur_compilation"
    assert reponse["sortie"] == ""
    assert reponse["erreurs"][0]["message"] == "nom 'x' non déclaré"
    assert reponse["duree_secondes"] < 0.5  # aucun processus lancé


async def test_une_erreur_d_execution_est_structuree_avec_la_ligne(
    client: Client,
) -> None:
    reponse = await run(client, "affiche 1;\naffiche 1 / 0;\naffiche 3;")
    assert reponse["statut"] == "erreur_execution"
    assert reponse["sortie"] == "1\n"  # ce qui précède l'erreur est conservé
    erreur = reponse["erreurs"][0]
    assert erreur["genre"] == "Erreur d'exécution"
    assert erreur["ligne"] == 2
    assert erreur["colonne"] is None
    assert erreur["message"] == "division par zéro"


async def test_les_messages_d_erreur_ne_revelent_pas_le_dossier_temporaire(
    client: Client,
) -> None:
    reponse = await run(client, "affiche 1 / 0;")
    contexte = reponse["erreurs"][0]["contexte"]
    assert tempfile.gettempdir() not in contexte


async def test_un_programme_trop_long_est_interrompu(client: Client) -> None:
    reponse = await run(client, "pour i dans 0..100000000000 { }", delai=0.5)
    assert reponse["statut"] == "delai_depasse"
    assert reponse["duree_secondes"] < 3


async def test_une_sortie_infinie_est_tronquee_puis_le_processus_est_tue(
    client: Client,
) -> None:
    source = 'pour i dans 0..100000000 { affiche "xxxxxxxxxxxxxxxxxxxx"; }'
    reponse = await run(client, source, delai=5.0)
    assert reponse["statut"] == "sortie_tronquee"
    assert len(reponse["sortie"].encode()) <= LIMITE_SORTIE
    assert reponse["duree_secondes"] < 5


async def test_une_consommation_excessive_de_memoire_est_stoppee(
    client: Client,
) -> None:
    source = 'soit t = "aaaaaaaaaa"; pour i dans 0..60 { t = t + t; }'
    reponse = await run(client, source, delai=5.0)
    assert reponse["statut"] == "memoire_depassee"


async def test_un_texte_ne_peut_pas_faire_executer_du_python(client: Client) -> None:
    piege = r"\"); __import__('os').system('echo PWNED > /tmp/pwned_butterfly'); (\""
    reponse = await run(client, f'affiche "{piege}";')
    assert reponse["statut"] == "ok"
    assert not Path("/tmp/pwned_butterfly").exists()


async def test_les_dossiers_temporaires_sont_supprimes(client: Client) -> None:
    avant = set(Path(tempfile.gettempdir()).glob("butterfly-*"))
    await run(client, "affiche 1;")
    await run(client, "affiche 1 / 0;")
    await run(client, "pour i dans 0..100000000000 { }", delai=0.3)
    assert set(Path(tempfile.gettempdir()).glob("butterfly-*")) == avant


# --- Le bac à sable lui-même -------------------------------------------------------------


def test_le_fils_n_herite_pas_de_l_environnement_du_serveur(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRET_DU_SERVEUR", "mot-de-passe")
    assert "SECRET_DU_SERVEUR" not in environnement()


def test_un_echec_du_fils_sans_erreur_butterfly_est_classe_erreur_interne() -> None:
    # On contourne `check` : le fils reçoit un programme faux et échoue sans
    # produire d'« Erreur d'exécution ».
    resultat = executer_isole("affiche x;")
    assert resultat.statut == "erreur_interne"
    assert "nom 'x' non déclaré" in resultat.erreur


def test_lire_erreur_execution() -> None:
    texte = "Erreur d'exécution (ligne 7) : division par zéro\n  7 | affiche 1 / 0;\n"
    assert lire_erreur_execution(texte) == (7, "division par zéro")
    assert lire_erreur_execution("rien de tel") is None
