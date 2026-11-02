"""Le site se construit, et ses pages sont cohérentes."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DIST = RACINE / "site" / "dist"
PAGES = [
    "index", "langage", "guide", "reference", "exemples", "playground", "mcp", "compilateur",
]  # fmt: skip


@pytest.fixture(scope="module")
def site() -> Path:
    resultat = subprocess.run(
        [sys.executable, str(RACINE / "site" / "build.py")],
        capture_output=True, text=True, cwd=RACINE, check=False,
    )  # fmt: skip
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    return DIST


@pytest.mark.parametrize("page", PAGES)
def test_chaque_page_existe_sans_marqueur_oublie(site: Path, page: str) -> None:
    contenu = (site / f"{page}.html").read_text(encoding="utf-8")
    assert "<h1" in contenu
    assert "@@" not in contenu  # tous les marqueurs ont été remplacés


@pytest.mark.parametrize("page", PAGES)
def test_les_liens_internes_pointent_vers_des_fichiers_existants(
    site: Path, page: str
) -> None:
    contenu = (site / f"{page}.html").read_text(encoding="utf-8")
    for lien in re.findall(r'(?:href|src)="([^"#:]+?)(?:#[^"]*)?"', contenu):
        if lien.startswith(("http", "mailto")):
            continue
        assert (site / lien).exists(), f"{page}.html : lien cassé vers {lien}"


def test_les_exemples_du_texte_montrent_la_vraie_sortie(site: Path) -> None:
    langage = (site / "langage.html").read_text(encoding="utf-8")
    assert "total : 60" in langage
    assert "total : 100" in langage
    assert "il fait chaud : vrai" in langage
    assert "division par zéro" in langage


def test_le_code_est_colore_par_le_lexer_du_langage(site: Path) -> None:
    accueil = (site / "index.html").read_text(encoding="utf-8")
    assert '<span class="src">soit</span>' in accueil
    assert '<span class="der">lie</span>' in accueil
    assert '<span class="obs">quand</span>' in accueil


def test_le_playground_dispose_du_compilateur_en_archive(site: Path) -> None:
    import zipfile

    with zipfile.ZipFile(site / "butterfly.zip") as archive:
        noms = set(archive.namelist())
    assert {
        "butterfly/compilateur.py",
        "butterfly/lexer.py",
        "butterfly/runtime.py",
    } <= noms
    assert not any("__pycache__" in nom for nom in noms)


def test_la_page_de_reference_vient_de_la_specification(site: Path) -> None:
    reference = (site / "reference.html").read_text(encoding="utf-8")
    assert "Référence du langage" in reference
    assert "Grammaire (EBNF)" in reference
    assert "Brouillon" not in reference
