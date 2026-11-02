"""Étape 10 : qualité : formateur, backends et architecture."""

from pathlib import Path

import pytest

from butterfly.backend import BACKENDS, Backend, BackendFormat, BackendPython
from butterfly.compilateur import compiler, executer
from butterfly.erreurs import ErreurCompilation
from butterfly.formateur import formater
from butterfly.semantique import Analyse

EXEMPLES = Path(__file__).resolve().parent.parent / "exemples"
PROGRAMMES = sorted(EXEMPLES.glob("*.fly"))


# --- Le formateur ---------------------------------------------------------------------------


@pytest.mark.parametrize("programme", PROGRAMMES, ids=lambda p: p.stem)
def test_formater_est_idempotent(programme: Path) -> None:
    une_fois = formater(programme.read_text(encoding="utf-8"))
    assert formater(une_fois) == une_fois


@pytest.mark.parametrize("programme", PROGRAMMES, ids=lambda p: p.stem)
def test_un_programme_formate_donne_la_meme_sortie(programme: Path) -> None:
    attendu = programme.with_suffix(".attendu").read_text(encoding="utf-8")
    formate = formater(programme.read_text(encoding="utf-8"))
    assert executer(formate).sortie == attendu


@pytest.mark.parametrize("programme", PROGRAMMES, ids=lambda p: p.stem)
def test_les_exemples_sont_deja_dans_la_presentation_canonique(programme: Path) -> None:
    source = programme.read_text(encoding="utf-8")
    assert formater(source) == source


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("soit   a=1+2*3;affiche a;", "soit a = 1 + 2 * 3;\naffiche a;\n"),
        ("affiche(1);", "affiche 1;\n"),
        ("soit a=  min(1,2) ;", "soit a = min(1, 2);\n"),
        # parenthèses : seulement celles qui sont nécessaires
        ("affiche ((1+2))*3;", "affiche (1 + 2) * 3;\n"),
        ("affiche (1*2)+3;", "affiche 1 * 2 + 3;\n"),
        ("affiche 1-(2-3);", "affiche 1 - (2 - 3);\n"),
        ("affiche (1-2)-3;", "affiche 1 - 2 - 3;\n"),
        ("affiche -(1+2), - -3, -(-3);", "affiche -(1 + 2), -(-3), -(-3);\n"),
        ("affiche (non a) et b;", "affiche non a et b;\n"),
        ("affiche non (a et b);", "affiche non (a et b);\n"),
        ("affiche non (a==b);", "affiche non (a == b);\n"),
        ("affiche non a==b;", "affiche non (a == b);\n"),
        ("affiche (a et b) ou c;", "affiche a et b ou c;\n"),
        ("affiche a et (b ou c);", "affiche a et (b ou c);\n"),
        ("affiche (1<2)==vrai;", "affiche (1 < 2) == vrai;\n"),
        ("affiche 2*-3;", "affiche 2 * -3;\n"),
        ("affiche 1+(non a);", "affiche 1 + (non a);\n"),
        # textes
        (r'affiche "a\"b\\c\nd";', 'affiche "a\\"b\\\\c\\nd";\n'),
        # blocs
        ("si a {}", "si a {\n}\n"),
        (
            "si a{affiche 1;}sinon si b{affiche 2;}sinon{affiche 3;}",
            "si a {\n    affiche 1;\n} sinon si b {\n    affiche 2;\n} sinon {\n    affiche 3;\n}\n",
        ),
        ("pour i dans 0..n+1{}", "pour i dans 0..n + 1 {\n}\n"),
        ("quand a{affiche a;}", "quand a {\n    affiche a;\n}\n"),
        (
            "si a{si b{pour i dans 0..2{affiche i;}}}",
            "si a {\n    si b {\n        pour i dans 0..2 {\n"
            "            affiche i;\n        }\n    }\n}\n",
        ),
    ],
)  # fmt: skip
def test_presentation_canonique(source: str, attendu: str) -> None:
    assert formater(source) == attendu


def test_les_commentaires_sont_conserves() -> None:
    source = (
        "# en-tête\n"
        "soit a = 1;  # fin de ligne\n"
        "   # indentation corrigée\n"
        "si a > 0 {\n"
        "# dans le bloc\n"
        "affiche a;\n"
        "  # avant l'accolade\n"
        "}\n"
        "# pour finir\n"
    )
    assert formater(source) == (
        "# en-tête\n"
        "soit a = 1;  # fin de ligne\n"
        "# indentation corrigée\n"
        "si a > 0 {\n"
        "    # dans le bloc\n"
        "    affiche a;\n"
        "    # avant l'accolade\n"
        "}\n"
        "# pour finir\n"
    )


def test_un_programme_qui_n_a_que_des_commentaires_est_conserve() -> None:
    assert formater("# rien d'autre\n") == "# rien d'autre\n"
    assert formater("") == ""


def test_les_lignes_vides_sont_reduites_a_une_et_jamais_en_debut_de_bloc() -> None:
    source = "soit a = 1;\n\n\n\naffiche a;\nsi vrai {\n\n  affiche 1;\n\n\n  affiche 2;\n}\n"
    assert formater(source) == (
        "soit a = 1;\n\naffiche a;\nsi vrai {\n    affiche 1;\n\n    affiche 2;\n}\n"
    )


def test_formater_est_idempotent_sur_du_code_desordonne() -> None:
    source = "soit a=1;# c\n\n\nsi a>0{#x\naffiche   a ;\n}sinon{ }\nquand a{ }\n"
    une_fois = formater(source)
    assert formater(une_fois) == une_fois


def test_on_ne_formate_pas_un_programme_dont_la_syntaxe_est_fausse() -> None:
    with pytest.raises(ErreurCompilation):
        formater("soit a = ;")


# --- Les backends ---------------------------------------------------------------------------


def test_les_backends_disponibles() -> None:
    assert set(BACKENDS) == {"python", "format"}


def test_le_backend_python_produit_du_python_et_le_backend_format_du_butterfly() -> (
    None
):
    source = "soit a=1;affiche a;"
    analyse = compiler(source)
    assert "v_a = 1" in BackendPython().produire(analyse, source)
    assert BackendFormat().produire(analyse, source) == "soit a = 1;\naffiche a;\n"


def test_un_nouveau_backend_s_ajoute_sans_rien_modifier() -> None:
    class BackendCellules:
        """Liste les cellules du programme : un 3e backend, écrit ici."""

        nom = "cellules"

        def produire(self, analyse: Analyse, source: str) -> str:
            return "\n".join(analyse.cellules)

    backend: Backend = BackendCellules()  # le Protocol suffit : pas d'héritage
    sortie = backend.produire(
        compiler("soit a = 1; lie b = a; si vrai { soit t = 1; }"), ""
    )
    assert sortie == "a\nb"
