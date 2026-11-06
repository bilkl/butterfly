"""The site builds, in English and in French, and its pages are consistent."""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "site" / "dist"
PAGES = [
    "index", "language", "guide", "reference", "examples", "playground", "mcp", "internals",
]  # fmt: skip
LANGUAGES = ["en", "fr"]
CASES = [(lang, page) for lang in LANGUAGES for page in PAGES]


def folder(site: Path, lang: str) -> Path:
    return site if lang == "en" else site / lang


@pytest.fixture(scope="module")
def site() -> Path:
    result = subprocess.run(
        [sys.executable, str(ROOT / "site" / "build.py")],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr
    return DIST


@pytest.mark.parametrize(("lang", "page"), CASES)
def test_each_page_exists_with_no_forgotten_marker(
    site: Path, lang: str, page: str
) -> None:
    content = (folder(site, lang) / f"{page}.html").read_text(encoding="utf-8")
    assert "<h1" in content
    assert "@@" not in content  # every marker was replaced
    assert f'<html lang="{lang}">' in content


@pytest.mark.parametrize(("lang", "page"), CASES)
def test_internal_links_point_to_existing_files(
    site: Path, lang: str, page: str
) -> None:
    where = folder(site, lang)
    content = (where / f"{page}.html").read_text(encoding="utf-8")
    for link in re.findall(r'(?:href|src)="([^"#:]+?)(?:#[^"]*)?"', content):
        if link.startswith(("http", "mailto")):
            continue
        assert (where / link).exists(), f"{lang}/{page}.html: broken link to {link}"


@pytest.mark.parametrize(("lang", "page"), CASES)
def test_the_language_switch_points_to_the_same_page_in_the_other_language(
    site: Path, lang: str, page: str
) -> None:
    content = (folder(site, lang) / f"{page}.html").read_text(encoding="utf-8")
    found = re.search(r'<a class="lang" href="([^"]+)"[^>]*data-lang="(\w+)"', content)
    assert found is not None
    target = (folder(site, lang) / found.group(1)).resolve()
    other = "fr" if lang == "en" else "en"
    assert found.group(2) == other
    assert target == (folder(site, other) / f"{page}.html").resolve()
    assert f'hreflang="{other}"' in content


def test_the_examples_of_the_text_show_the_real_output(site: Path) -> None:
    language = (site / "language.html").read_text(encoding="utf-8")
    assert "total: 60" in language
    assert "total: 100" in language
    assert "it is hot: true" in language
    assert "division by zero" in language
    french = (site / "fr" / "language.html").read_text(encoding="utf-8")
    assert "total : 60" in french
    assert "il fait chaud : true" in french


def test_the_code_is_colored_by_the_language_lexer(site: Path) -> None:
    for lang in LANGUAGES:
        home = (folder(site, lang) / "index.html").read_text(encoding="utf-8")
        assert '<span class="src">let</span>' in home
        assert '<span class="der">bind</span>' in home
        assert '<span class="obs">when</span>' in home


def test_the_playground_has_the_compiler_as_an_archive(site: Path) -> None:
    with zipfile.ZipFile(site / "butterfly.zip") as archive:
        names = set(archive.namelist())
    assert {
        "butterfly/compiler.py",
        "butterfly/lexer.py",
        "butterfly/runtime.py",
    } <= names
    assert not any("__pycache__" in name for name in names)


def test_the_french_playground_loads_the_archive_from_the_root(site: Path) -> None:
    french = (site / "fr" / "playground.html").read_text(encoding="utf-8")
    assert 'data-root="../"' in french
    assert 'src="../static/playground.js"' in french


def test_the_reference_page_comes_from_the_specification(site: Path) -> None:
    reference = (site / "reference.html").read_text(encoding="utf-8")
    assert "Language reference" in reference
    assert "Grammar (EBNF)" in reference
    assert "Draft of step 1" not in reference
    french = (site / "fr" / "reference.html").read_text(encoding="utf-8")
    assert "Référence du langage" in french
    assert "Grammaire (EBNF)" in french


def error_table(text: str) -> list[tuple[str, str]]:
    """The (program, message) pairs of the table of errors of a specification."""
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] in {"lexical", "syntax", "semantic", "runtime"}:
            rows.append((cells[1], cells[2]))
    return rows


def test_the_french_table_of_errors_is_the_one_of_the_specification() -> None:
    english = (ROOT / "specification.md").read_text(encoding="utf-8")
    french = (ROOT / "site" / "content" / "fr" / "reference.md").read_text(
        encoding="utf-8"
    )
    assert len(error_table(english)) >= 6
    assert error_table(french) == error_table(english)
