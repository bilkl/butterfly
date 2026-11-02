"""Étape 9 : la ligne de commande et le REPL."""

import io
import subprocess
import sys
from pathlib import Path

import pytest

from butterfly import __version__
from butterfly.cli import main
from butterfly.repl import Session, entree_complete, lancer_repl

RACINE = Path(__file__).resolve().parent.parent
EXEMPLES = RACINE / "exemples"


@pytest.fixture
def programme(tmp_path: Path) -> Path:
    fichier = tmp_path / "programme.fly"
    fichier.write_text("soit a = 2;\nlie b = a * 21;\naffiche b;\n", encoding="utf-8")
    return fichier


# --- La CLI --------------------------------------------------------------------------------


def test_run_execute_le_programme(
    programme: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", str(programme)]) == 0
    assert capsys.readouterr().out == "42\n"


def test_run_sur_un_exemple_donne_la_sortie_attendue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", str(EXEMPLES / "05_budget.fly")]) == 0
    attendu = (EXEMPLES / "05_budget.attendu").read_text(encoding="utf-8")
    assert capsys.readouterr().out == attendu


def test_run_garde_la_sortie_avant_une_erreur_d_execution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fichier = tmp_path / "p.fly"
    fichier.write_text("affiche 1;\naffiche 1 / 0;\n", encoding="utf-8")
    assert main(["run", str(fichier)]) == 1
    sortie = capsys.readouterr()
    assert sortie.out == "1\n"
    assert "Erreur d'exécution (ligne 2) : division par zéro" in sortie.err
    assert "2 | affiche 1 / 0;" in sortie.err


def test_check_dit_ok_ou_liste_toutes_les_erreurs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], programme: Path
) -> None:
    assert main(["check", str(programme)]) == 0
    assert "OK" in capsys.readouterr().out

    faux = tmp_path / "faux.fly"
    faux.write_text("soit a = ;\nsoit b = 2\naffiche c;\n", encoding="utf-8")
    assert main(["check", str(faux)]) == 1
    erreurs = capsys.readouterr().err
    assert "ligne 1, colonne 10" in erreurs
    assert "ligne 2, colonne 11" in erreurs  # les deux erreurs d'un coup
    assert "soit a = ;" in erreurs and "^" in erreurs  # ligne fautive et repère


def test_les_erreurs_de_syntaxe_empechent_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fichier = tmp_path / "p.fly"
    fichier.write_text("affiche 1;\nsoit = 2;\n", encoding="utf-8")
    assert main(["run", str(fichier)]) == 1
    sortie = capsys.readouterr()
    assert sortie.out == ""  # rien n'est exécuté
    assert "nom attendu" in sortie.err


def test_transpile_affiche_le_python(
    programme: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["transpile", str(programme)]) == 0
    code = capsys.readouterr().out
    assert "from butterfly.runtime import" in code
    assert "v_b = _calc_b()" in code


def test_format_affiche_le_resultat_ou_reecrit_le_fichier(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fichier = tmp_path / "p.fly"
    fichier.write_text("soit   a=1;affiche a;", encoding="utf-8")
    assert main(["format", str(fichier)]) == 0
    assert capsys.readouterr().out == "soit a = 1;\naffiche a;\n"
    assert fichier.read_text(encoding="utf-8") == "soit   a=1;affiche a;"  # intact
    assert main(["format", "-w", str(fichier)]) == 0
    assert fichier.read_text(encoding="utf-8") == "soit a = 1;\naffiche a;\n"


def test_tokens_et_ast(programme: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["tokens", str(programme)]) == 0
    assert "Token(SOIT, 'soit', 1:1)" in capsys.readouterr().out
    assert main(["ast", str(programme)]) == 0
    arbre = capsys.readouterr().out
    assert "Declaration" in arbre and "Liaison" in arbre and "Affiche" in arbre


def test_tokens_affiche_ceux_lus_avant_une_erreur_lexicale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fichier = tmp_path / "p.fly"
    fichier.write_text("soit a @ 1;", encoding="utf-8")
    assert main(["tokens", str(fichier)]) == 1
    sortie = capsys.readouterr()
    assert "Token(SOIT" in sortie.out and "Token(IDENT, 'a'" in sortie.out
    assert "caractère inattendu '@'" in sortie.err


def test_un_fichier_introuvable_donne_le_code_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", "/chemin/inexistant.fly"]) == 2
    assert "impossible de lire" in capsys.readouterr().err


def test_le_programme_peut_venir_de_l_entree_standard(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("affiche 6 * 7;"))
    assert main(["run", "-"]) == 0
    assert capsys.readouterr().out == "42\n"


def test_version_et_commande_obligatoire(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as sortie:
        main(["--version"])
    assert sortie.value.code == 0
    assert __version__ in capsys.readouterr().out
    with pytest.raises(SystemExit) as manquante:
        main([])
    assert manquante.value.code == 2


def test_python_m_butterfly_fonctionne_en_sous_processus() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "butterfly", "run", str(EXEMPLES / "02_cellules.fly")],
        capture_output=True, text=True, cwd=RACINE, check=False,
    )  # fmt: skip
    assert resultat.returncode == 0
    assert resultat.stdout == (EXEMPLES / "02_cellules.attendu").read_text(
        encoding="utf-8"
    )


# --- Le REPL -------------------------------------------------------------------------------


def jouer(*lignes: str) -> list[str]:
    """Joue une session et renvoie ce qui a été écrit (sans la bannière)."""
    entrees = iter(lignes)
    sorties: list[str] = []

    def lire(invite: str) -> str:
        try:
            return next(entrees)
        except StopIteration:
            raise EOFError from None

    lancer_repl(lire, sorties.append)
    return sorties[1:]


def test_l_etat_se_garde_d_une_ligne_a_l_autre() -> None:
    assert jouer("soit a = 2;", "lie double = a * 2;", "double", "a = 10;", "double") == [
        "4", "20",
    ]  # fmt: skip


def test_une_expression_nue_est_affichee() -> None:
    assert jouer("1 + 2", "min(4, 9)", '"a" + "b"') == ["3", "4", "ab"]


def test_les_observateurs_agissent_dans_le_repl() -> None:
    sorties = jouer(
        "soit a = 1;", 'quand a { affiche "change"; }', "a = 2;", "a = 2;", "a = 3;"
    )
    assert sorties == ["change", "change"]


def test_un_bloc_sur_plusieurs_lignes_est_lu_jusqu_au_bout() -> None:
    assert jouer("si vrai {", '  affiche "ok";', "}") == ["ok"]


def test_une_erreur_ne_casse_pas_la_session_et_n_est_pas_retenue() -> None:
    sorties = jouer("x", "soit x = 1;", "x", ":source")
    assert "nom 'x' non déclaré" in sorties[0]
    assert sorties[1] == "1"
    assert sorties[2] == "soit x = 1;"  # l'entrée fautive n'est pas dans l'historique


def test_une_erreur_d_execution_est_signalee_et_la_session_continue() -> None:
    sorties = jouer("affiche 1 / 0;", "affiche 5;")
    assert "division par zéro" in sorties[0]
    assert sorties[-1] == "5"


def test_les_commandes_du_repl() -> None:
    sorties = jouer(
        ":aide", "soit a = 1;", ":reinit", ":source", ":quitter", "affiche 9;"
    )
    assert "Commandes" in sorties[0]
    assert sorties[1] == "session réinitialisée"
    assert sorties[2] == "(vide)"
    assert len(sorties) == 3  # rien après :quitter


def test_entree_complete_compte_les_accolades() -> None:
    assert entree_complete("affiche 1;")
    assert not entree_complete("si vrai {")
    assert entree_complete("si vrai { }")
    assert entree_complete("soit a = 3 @")  # l'erreur lexicale sera signalée


def test_la_session_ne_retient_que_ce_qui_a_reussi() -> None:
    session = Session()
    assert session.evaluer("soit a = 1;") == ("", None)
    sortie, erreur = session.evaluer("a = ;")
    assert erreur is not None and sortie == ""
    assert session.entrees == ["soit a = 1;"]
