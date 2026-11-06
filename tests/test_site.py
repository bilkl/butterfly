"""Le site se construit, et ses pages sont cohérentes."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "site" / "dist"
PAGES = [
    "index", "language", "guide", "reference", "examples", "playground", "mcp", "internals",
]  # fmt: skip


@pytest.fixture(scope="module")
def site() -> Path:
    result = subprocess.run(
        [sys.executable, str(ROOT / "site" / "build.py")],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr
    return DIST


@pytest.mark.parametrize("page", PAGES)
def test_chaque_page_existe_sans_marqueur_oublie(site: Path, page: str) -> None:
    content = (site / f"{page}.html").read_text(encoding="utf-8")
    assert "<h1" in content
    assert "@@" not in content  # tous les marqueurs ont été remplacés


@pytest.mark.parametrize("page", PAGES)
def test_les_liens_internes_pointent_vers_des_fichiers_existants(
    site: Path, page: str
) -> None:
    content = (site / f"{page}.html").read_text(encoding="utf-8")
    for link in re.findall(r'(?:href|src)="([^"#:]+?)(?:#[^"]*)?"', content):
        if link.startswith(("http", "mailto")):
            continue
        assert (site / link).exists(), f"{page}.html : lien cassé vers {link}"


def test_les_exemples_du_texte_montrent_la_vraie_sortie(site: Path) -> None:
    language = (site / "language.html").read_text(encoding="utf-8")
    assert "total : 60" in language
    assert "total : 100" in language
    assert "il fait chaud : true" in language
    assert "division by zero" in language


def test_le_code_est_colore_par_le_lexer_du_langage(site: Path) -> None:
    home = (site / "index.html").read_text(encoding="utf-8")
    assert '<span class="src">let</span>' in home
    assert '<span class="der">bind</span>' in home
    assert '<span class="obs">when</span>' in home


def test_le_playground_dispose_du_compilateur_en_archive(site: Path) -> None:
    import zipfile

    with zipfile.ZipFile(site / "butterfly.zip") as archive:
        names = set(archive.namelist())
    assert {
        "butterfly/compiler.py",
        "butterfly/lexer.py",
        "butterfly/runtime.py",
    } <= names
    assert not any("__pycache__" in name for name in names)


def test_la_page_de_reference_vient_de_la_specification(site: Path) -> None:
    reference = (site / "reference.html").read_text(encoding="utf-8")
    assert "Language reference" in reference
    assert "Grammar (EBNF)" in reference
    assert "Draft of step 1" not in reference
