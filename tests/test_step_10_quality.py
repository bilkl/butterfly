"""Étape 10 : qualité : formateur, backends et architecture."""

from pathlib import Path

import pytest

from butterfly.backend import BACKENDS, Backend, FormatBackend, PythonBackend
from butterfly.compiler import analyze_program, execute
from butterfly.errors import CompilationError
from butterfly.formatter import format_source
from butterfly.semantics import Analysis

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
PROGRAMS = sorted(EXAMPLES.glob("*.fly"))


# --- Le formateur ---------------------------------------------------------------------------


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda p: p.stem)
def test_formater_est_idempotent(program: Path) -> None:
    once = format_source(program.read_text(encoding="utf-8"))
    assert format_source(once) == once


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda p: p.stem)
def test_un_programme_formate_donne_la_meme_sortie(program: Path) -> None:
    expected = program.with_suffix(".expected").read_text(encoding="utf-8")
    formatted = format_source(program.read_text(encoding="utf-8"))
    assert execute(formatted).output == expected


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda p: p.stem)
def test_les_exemples_sont_deja_dans_la_presentation_canonique(program: Path) -> None:
    source = program.read_text(encoding="utf-8")
    assert format_source(source) == source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("let   a=1+2*3;print a;", "let a = 1 + 2 * 3;\nprint a;\n"),
        ("print(1);", "print 1;\n"),
        ("let a=  min(1,2) ;", "let a = min(1, 2);\n"),
        # parenthèses : seulement celles qui sont nécessaires
        ("print ((1+2))*3;", "print (1 + 2) * 3;\n"),
        ("print (1*2)+3;", "print 1 * 2 + 3;\n"),
        ("print 1-(2-3);", "print 1 - (2 - 3);\n"),
        ("print (1-2)-3;", "print 1 - 2 - 3;\n"),
        ("print -(1+2), - -3, -(-3);", "print -(1 + 2), -(-3), -(-3);\n"),
        ("print (not a) and b;", "print not a and b;\n"),
        ("print not (a and b);", "print not (a and b);\n"),
        ("print not (a==b);", "print not (a == b);\n"),
        ("print not a==b;", "print not (a == b);\n"),
        ("print (a and b) or c;", "print a and b or c;\n"),
        ("print a and (b or c);", "print a and (b or c);\n"),
        ("print (1<2)==true;", "print (1 < 2) == true;\n"),
        ("print 2*-3;", "print 2 * -3;\n"),
        ("print 1+(not a);", "print 1 + (not a);\n"),
        # textes
        (r'print "a\"b\\c\nd";', 'print "a\\"b\\\\c\\nd";\n'),
        # blocs
        ("if a {}", "if a {\n}\n"),
        (
            "if a{print 1;}else if b{print 2;}else{print 3;}",
            "if a {\n    print 1;\n} else if b {\n    print 2;\n} else {\n    print 3;\n}\n",
        ),
        ("for i in 0..n+1{}", "for i in 0..n + 1 {\n}\n"),
        ("when a{print a;}", "when a {\n    print a;\n}\n"),
        (
            "if a{if b{for i in 0..2{print i;}}}",
            "if a {\n    if b {\n        for i in 0..2 {\n"
            "            print i;\n        }\n    }\n}\n",
        ),
    ],
)  # fmt: skip
def test_presentation_canonique(source: str, expected: str) -> None:
    assert format_source(source) == expected


def test_les_commentaires_sont_conserves() -> None:
    source = (
        "# en-tête\n"
        "let a = 1;  # fin de ligne\n"
        "   # indentation corrigée\n"
        "if a > 0 {\n"
        "# dans le bloc\n"
        "print a;\n"
        "  # avant l'accolade\n"
        "}\n"
        "# pour finir\n"
    )
    assert format_source(source) == (
        "# en-tête\n"
        "let a = 1;  # fin de ligne\n"
        "# indentation corrigée\n"
        "if a > 0 {\n"
        "    # dans le bloc\n"
        "    print a;\n"
        "    # avant l'accolade\n"
        "}\n"
        "# pour finir\n"
    )


def test_un_programme_qui_n_a_que_des_commentaires_est_conserve() -> None:
    assert format_source("# rien d'autre\n") == "# rien d'autre\n"
    assert format_source("") == ""


def test_les_lignes_vides_sont_reduites_a_une_et_jamais_en_debut_de_bloc() -> None:
    source = "let a = 1;\n\n\n\nprint a;\nif true {\n\n  print 1;\n\n\n  print 2;\n}\n"
    assert format_source(source) == (
        "let a = 1;\n\nprint a;\nif true {\n    print 1;\n\n    print 2;\n}\n"
    )


def test_formater_est_idempotent_sur_du_code_desordonne() -> None:
    source = "let a=1;# c\n\n\nif a>0{#x\nprint   a ;\n}else{ }\nwhen a{ }\n"
    once = format_source(source)
    assert format_source(once) == once


def test_on_ne_formate_pas_un_programme_dont_la_syntaxe_est_fausse() -> None:
    with pytest.raises(CompilationError):
        format_source("let a = ;")


# --- Les backends ---------------------------------------------------------------------------


def test_les_backends_disponibles() -> None:
    assert set(BACKENDS) == {"python", "format"}


def test_le_backend_python_produit_du_python_et_le_backend_format_du_butterfly() -> (
    None
):
    source = "let a=1;print a;"
    analysis = analyze_program(source)
    assert "v_a = 1" in PythonBackend().produce(analysis, source)
    assert FormatBackend().produce(analysis, source) == "let a = 1;\nprint a;\n"


def test_un_nouveau_backend_s_ajoute_sans_rien_modifier() -> None:
    class CellsBackend:
        """Liste les cellules du programme : un 3e backend, écrit ici."""

        name = "cells"

        def produce(self, analysis: Analysis, source: str) -> str:
            return "\n".join(analysis.cells)

    backend: Backend = CellsBackend()  # le Protocol suffit : pas d'héritage
    output = backend.produce(
        analyze_program("let a = 1; bind b = a; if true { let t = 1; }"), ""
    )
    assert output == "a\nb"
