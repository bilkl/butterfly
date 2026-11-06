"""Étape 1 : la spécification et ses programmes d'exemple.

La spécification est **exécutable** : le tableau de la section « Errors » est lu
par ce test, et chaque programme fautif doit produire exactement le message
annoncé.
"""

import re
from pathlib import Path

import pytest

from butterfly.compiler import check, execute

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
PROGRAMS = sorted(EXAMPLES.glob("*.fly"))


def test_il_y_a_au_moins_cinq_exemples() -> None:
    assert len(PROGRAMS) >= 5


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda p: p.stem)
def test_chaque_exemple_a_un_fichier_attendu(program: Path) -> None:
    assert program.with_suffix(".expected").is_file()


def read_errors_table() -> list[tuple[str, str, str]]:
    """Les lignes ``| kind | `programme` | `message` |`` de la spécification."""
    text = (ROOT / "specification.md").read_text(encoding="utf-8")
    section = text.split("\n## Errors\n", 1)[1].split("\n## ", 1)[0]
    lines: list[tuple[str, str, str]] = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in ("Kind", "") or set(cells[0]) <= {"-"}:
            continue
        program = "\n".join(re.findall(r"`([^`]+)`", cells[1]))
        message = re.findall(r"`([^`]+)`", cells[2])[0]
        lines.append((cells[0], program, message))
    return lines


TABLE = read_errors_table()


def test_le_tableau_des_erreurs_de_la_specification_a_ete_lu() -> None:
    assert len(TABLE) >= 6
    assert {kind for kind, _, _ in TABLE} >= {
        "lexical", "syntax", "semantic", "runtime",
    }  # fmt: skip


@pytest.mark.parametrize(("kind", "program", "message"), TABLE)
def test_chaque_erreur_de_la_specification_produit_le_message_annonce(
    kind: str, program: str, message: str
) -> None:
    if kind == "runtime":
        result = execute(program)
        assert result.error is not None
        assert str(result.error) == message
    else:
        errors = check(program)
        assert errors, f"le programme {program!r} aurait dû être refusé"
        assert str(errors[0]) == message
