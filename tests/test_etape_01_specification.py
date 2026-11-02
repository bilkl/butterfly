"""Étape 1 : la spécification et ses programmes d'exemple.

La spécification est **exécutable** : le tableau de la section « Erreurs » est lu
par ce test, et chaque programme fautif doit produire exactement le message
annoncé.
"""

import re
from pathlib import Path

import pytest

from butterfly.compilateur import executer, verifier

RACINE = Path(__file__).resolve().parent.parent
EXEMPLES = RACINE / "exemples"
PROGRAMMES = sorted(EXEMPLES.glob("*.fly"))


def test_il_y_a_au_moins_cinq_exemples() -> None:
    assert len(PROGRAMMES) >= 5


@pytest.mark.parametrize("programme", PROGRAMMES, ids=lambda p: p.stem)
def test_chaque_exemple_a_un_fichier_attendu(programme: Path) -> None:
    assert programme.with_suffix(".attendu").is_file()


def lire_tableau_des_erreurs() -> list[tuple[str, str, str]]:
    """Les lignes ``| genre | `programme` | `message` |`` de la spécification."""
    texte = (RACINE / "specification.md").read_text(encoding="utf-8")
    section = texte.split("\n## Erreurs\n", 1)[1].split("\n## ", 1)[0]
    lignes: list[tuple[str, str, str]] = []
    for ligne in section.splitlines():
        cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if (
            len(cellules) != 3
            or cellules[0] in ("Genre", "")
            or set(cellules[0]) <= {"-"}
        ):
            continue
        programme = "\n".join(re.findall(r"`([^`]+)`", cellules[1]))
        message = re.findall(r"`([^`]+)`", cellules[2])[0]
        lignes.append((cellules[0], programme, message))
    return lignes


TABLEAU = lire_tableau_des_erreurs()


def test_le_tableau_des_erreurs_de_la_specification_a_ete_lu() -> None:
    assert len(TABLEAU) >= 6
    assert {genre for genre, _, _ in TABLEAU} >= {
        "lexicale", "syntaxe", "sémantique", "exécution",
    }  # fmt: skip


@pytest.mark.parametrize(("genre", "programme", "message"), TABLEAU)
def test_chaque_erreur_de_la_specification_produit_le_message_annonce(
    genre: str, programme: str, message: str
) -> None:
    if genre == "exécution":
        resultat = executer(programme)
        assert resultat.erreur is not None
        assert str(resultat.erreur) == message
    else:
        erreurs = verifier(programme)
        assert erreurs, f"le programme {programme!r} aurait dû être refusé"
        assert str(erreurs[0]) == message
