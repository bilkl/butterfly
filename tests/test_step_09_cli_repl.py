"""Étape 9 : la ligne de commande et le REPL."""

import io
import subprocess
import sys
from pathlib import Path

import pytest

from butterfly import __version__
from butterfly.cli import main
from butterfly.repl import Session, is_complete_input, run_repl

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.fixture
def program(tmp_path: Path) -> Path:
    file_path = tmp_path / "programme.fly"
    file_path.write_text("let a = 2;\nbind b = a * 21;\nprint b;\n", encoding="utf-8")
    return file_path


# --- La CLI --------------------------------------------------------------------------------


def test_run_execute_le_programme(
    program: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", str(program)]) == 0
    assert capsys.readouterr().out == "42\n"


def test_run_sur_un_exemple_donne_la_sortie_attendue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", str(EXAMPLES / "05_budget.fly")]) == 0
    expected = (EXAMPLES / "05_budget.expected").read_text(encoding="utf-8")
    assert capsys.readouterr().out == expected


def test_run_garde_la_sortie_avant_une_erreur_d_execution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file_path = tmp_path / "p.fly"
    file_path.write_text("print 1;\nprint 1 / 0;\n", encoding="utf-8")
    assert main(["run", str(file_path)]) == 1
    output = capsys.readouterr()
    assert output.out == "1\n"
    assert "Runtime error (line 2): division by zero" in output.err
    assert "2 | print 1 / 0;" in output.err


def test_check_dit_ok_ou_liste_toutes_les_erreurs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], program: Path
) -> None:
    assert main(["check", str(program)]) == 0
    assert "OK" in capsys.readouterr().out

    faux = tmp_path / "faux.fly"
    faux.write_text("let a = ;\nlet b = 2\nprint c;\n", encoding="utf-8")
    assert main(["check", str(faux)]) == 1
    errors = capsys.readouterr().err
    assert "line 1, column 9" in errors
    assert "line 2, column 10" in errors  # les deux erreurs d'un coup
    assert "let a = ;" in errors and "^" in errors  # ligne fautive et repère


def test_les_erreurs_de_syntaxe_empechent_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file_path = tmp_path / "p.fly"
    file_path.write_text("print 1;\nlet = 2;\n", encoding="utf-8")
    assert main(["run", str(file_path)]) == 1
    output = capsys.readouterr()
    assert output.out == ""  # rien n'est exécuté
    assert "name expected" in output.err


def test_transpile_affiche_le_python(
    program: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["transpile", str(program)]) == 0
    code = capsys.readouterr().out
    assert "from butterfly.runtime import" in code
    assert "v_b = _calc_b()" in code


def test_format_affiche_le_resultat_ou_reecrit_le_fichier(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file_path = tmp_path / "p.fly"
    file_path.write_text("let   a=1;print a;", encoding="utf-8")
    assert main(["format", str(file_path)]) == 0
    assert capsys.readouterr().out == "let a = 1;\nprint a;\n"
    assert file_path.read_text(encoding="utf-8") == "let   a=1;print a;"  # intact
    assert main(["format", "-w", str(file_path)]) == 0
    assert file_path.read_text(encoding="utf-8") == "let a = 1;\nprint a;\n"


def test_tokens_et_ast(program: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["tokens", str(program)]) == 0
    assert "Token(LET, 'let', 1:1)" in capsys.readouterr().out
    assert main(["ast", str(program)]) == 0
    tree = capsys.readouterr().out
    assert "Declaration" in tree and "Binding" in tree and "Print" in tree


def test_tokens_affiche_ceux_lus_avant_une_erreur_lexicale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file_path = tmp_path / "p.fly"
    file_path.write_text("let a @ 1;", encoding="utf-8")
    assert main(["tokens", str(file_path)]) == 1
    output = capsys.readouterr()
    assert "Token(LET" in output.out and "Token(IDENT, 'a'" in output.out
    assert "unexpected character '@'" in output.err


def test_un_fichier_introuvable_donne_le_code_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", "/chemin/inexistant.fly"]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_le_programme_peut_venir_de_l_entree_standard(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("print 6 * 7;"))
    assert main(["run", "-"]) == 0
    assert capsys.readouterr().out == "42\n"


def test_version_et_commande_obligatoire(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as output:
        main(["--version"])
    assert output.value.code == 0
    assert __version__ in capsys.readouterr().out
    with pytest.raises(SystemExit) as missing:
        main([])
    assert missing.value.code == 2


def test_python_m_butterfly_fonctionne_en_sous_processus() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "butterfly", "run", str(EXAMPLES / "02_cells.fly")],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )  # fmt: skip
    assert result.returncode == 0
    assert result.stdout == (EXAMPLES / "02_cells.expected").read_text(encoding="utf-8")


# --- Le REPL -------------------------------------------------------------------------------


def play(*lines: str) -> list[str]:
    """Joue une session et renvoie ce qui a été écrit (sans la bannière)."""
    entries = iter(lines)
    outputs: list[str] = []

    def read_line(prompt_text: str) -> str:
        try:
            return next(entries)
        except StopIteration:
            raise EOFError from None

    run_repl(read_line, outputs.append)
    return outputs[1:]


def test_l_etat_se_garde_d_une_ligne_a_l_autre() -> None:
    assert play("let a = 2;", "bind double = a * 2;", "double", "a = 10;", "double") == [
        "4", "20",
    ]  # fmt: skip


def test_une_expression_nue_est_affichee() -> None:
    assert play("1 + 2", "min(4, 9)", '"a" + "b"') == ["3", "4", "ab"]


def test_les_observateurs_agissent_dans_le_repl() -> None:
    outputs = play(
        "let a = 1;", 'when a { print "change"; }', "a = 2;", "a = 2;", "a = 3;"
    )
    assert outputs == ["change", "change"]


def test_un_bloc_sur_plusieurs_lignes_est_lu_jusqu_au_bout() -> None:
    assert play("if true {", '  print "ok";', "}") == ["ok"]


def test_une_erreur_ne_casse_pas_la_session_et_n_est_pas_retenue() -> None:
    outputs = play("x", "let x = 1;", "x", ":source")
    assert "name 'x' not declared" in outputs[0]
    assert outputs[1] == "1"
    assert outputs[2] == "let x = 1;"  # l'entrée fautive n'est pas dans l'historique


def test_une_erreur_d_execution_est_signalee_et_la_session_continue() -> None:
    outputs = play("print 1 / 0;", "print 5;")
    assert "division by zero" in outputs[0]
    assert outputs[-1] == "5"


def test_les_commandes_du_repl() -> None:
    outputs = play(":help", "let a = 1;", ":reset", ":source", ":quit", "print 9;")
    assert "Commands" in outputs[0]
    assert outputs[1] == "session reset"
    assert outputs[2] == "(empty)"
    assert len(outputs) == 3  # rien après :quit


def test_entree_complete_compte_les_accolades() -> None:
    assert is_complete_input("print 1;")
    assert not is_complete_input("if true {")
    assert is_complete_input("if true { }")
    assert is_complete_input("let a = 3 @")  # l'erreur lexicale sera signalée


def test_la_session_ne_retient_que_ce_qui_a_reussi() -> None:
    session = Session()
    assert session.evaluate("let a = 1;") == ("", None)
    output, error = session.evaluate("a = ;")
    assert error is not None and output == ""
    assert session.entries == ["let a = 1;"]
