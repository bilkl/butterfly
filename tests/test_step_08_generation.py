"""Étape 8 : la génération de Python et l'exécution des programmes."""

import io
from pathlib import Path

import pytest

from butterfly.compiler import execute, transpile
from butterfly.errors import CompilationError

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
PROGRAMS = sorted(EXAMPLES.glob("*.fly"))


def output(source: str) -> str:
    result = execute(source)
    assert result.error is None, str(result.error)
    return result.output


def execution_error(source: str) -> tuple[int | None, str, str]:
    """(ligne, message, sortie affichée avant l'erreur)."""
    result = execute(source)
    assert result.error is not None
    return result.error.line, result.error.message, result.output


# --- Le test central : chaque exemple produit sa sortie expectede ----------------------


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda p: p.stem)
def test_chaque_exemple_produit_sa_sortie_attendue(program: Path) -> None:
    expected = program.with_suffix(".expected").read_text(encoding="utf-8")
    assert output(program.read_text(encoding="utf-8")) == expected


# --- La propagation ---------------------------------------------------------------------


def test_une_cellule_derivee_suit_sa_source() -> None:
    assert output("let a = 1; bind b = a * 2; print b; a = 5; print b;") == "2\n10\n"


def test_la_propagation_traverse_plusieurs_niveaux() -> None:
    source = (
        "let a = 1; bind b = a + 1; bind c = b * 2; bind d = c + a; a = 10; print d;"
    )
    assert output(source) == "32\n"  # b=11, c=22, d=22+10


def test_une_cellule_independante_n_est_pas_recalculee() -> None:
    code = transpile("let a = 1; let b = 1; bind c = b; a = 2;")
    assert code.count("v_c = _calc_c()") == 1  # seulement à la déclaration


def test_une_cellule_est_recalculee_une_seule_fois_par_affectation() -> None:
    source = "let a = 1; bind b = a; bind c = a; bind d = b + c; a = 2;"
    code = transpile(source)
    assert code.count("v_d = _calc_d()") == 2  # déclaration + une affectation


def test_un_observateur_ne_se_declenche_que_si_la_valeur_change() -> None:
    source = 'let a = 1; when a { print "chg"; } a = 1; a = 2; a = 2; a = 3;'
    assert output(source) == "chg\nchg\n"


def test_un_observateur_n_est_pas_declenche_a_la_creation_de_la_cellule() -> None:
    assert output('let a = 1; bind b = a; when b { print "non"; }') == ""


def test_un_observateur_sur_une_derivee_attend_que_sa_valeur_change() -> None:
    source = (
        "let a = 1; bind pair = a % 2 == 0;"
        ' when pair { print "pair :", pair; } a = 3; a = 4; a = 6; a = 7;'
    )
    assert output(source) == "pair : true\npair : false\n"


def test_plusieurs_observateurs_s_executent_dans_l_ordre_de_declaration() -> None:
    source = 'let a = 1; when a { print "premier"; } when a { print "second"; } a = 2;'
    assert output(source) == "premier\nsecond\n"


def test_un_observateur_declare_apres_une_affectation_ne_la_voit_pas() -> None:
    source = 'let a = 1; a = 2; when a { print "vu"; } a = 3;'
    assert output(source) == "vu\n"


def test_une_cellule_derivee_declaree_apres_une_affectation_est_a_jour() -> None:
    assert output("let a = 1; a = 2; bind b = a * 10; print b;") == "20\n"


def test_un_observateur_lit_les_autres_cellules_et_a_ses_propres_boucles() -> None:
    source = "let a = 0; let b = 10; when a { for i in 0..a { print i + b; } } a = 3;"
    assert output(source) == "10\n11\n12\n"


def test_une_affectation_dans_une_condition_propage() -> None:
    assert output("let a = 0; bind b = a + 1; if true { a = 4; } print b;") == "5\n"


def test_l_observateur_ne_voit_jamais_d_etat_intermediaire() -> None:
    source = (
        "let a = 1; bind b = a + 1; bind c = a * 10; bind d = b + c;"
        " when d { print d; } a = 2; a = 3;"
    )
    assert output(source) == "23\n34\n"  # jamais 13 (b à jour, c pas encore)


# --- Les structures de contrôle ---------------------------------------------------------


def test_sinon_si_et_sinon() -> None:
    template = (
        'if {c1} {{ print "a"; }} else if {c2} {{ print "b"; }} else {{ print "c"; }}'
    )
    assert output(template.format(c1="1 > 2", c2="2 > 1")) == "b\n"
    assert output(template.format(c1="1 > 2", c2="2 > 3")) == "c\n"
    assert output(template.format(c1="2 > 1", c2="true")) == "a\n"


def test_les_bornes_de_pour_sont_evaluees_une_seule_fois() -> None:
    source = "let n = 3; for i in 0..n { n = n + 1; print i; } print n;"
    assert output(source) == "0\n1\n2\n6\n"


def test_la_borne_haute_de_pour_est_exclue_et_une_plage_vide_ne_tourne_pas() -> None:
    assert output("for i in 1..4 { print i; }") == "1\n2\n3\n"
    assert output("for i in 5..2 { print i; } for j in 3..3 { print j; }") == ""


def test_les_blocs_vides_sont_permis() -> None:
    assert output("if true { } else { } for i in 0..3 { } let a = 1; when a { }") == ""


# --- Les valeurs ---------------------------------------------------------------------------


def test_division_et_modulo_suivent_python() -> None:
    assert output("print -17 / 5, -17 % 5, 17 / -5, 17 % -5;") == "-4 3 -4 -3\n"


def test_les_entiers_sont_de_taille_illimitee() -> None:
    assert output("print 99999999999 * 99999999999;") == "9999999999800000000001\n"


def test_les_textes_se_concatenent_et_se_comparent() -> None:
    assert (
        output('print "a" + "b", "a" < "b", "x" == "x", "x" != "y";')
        == "ab true true true\n"
    )


def test_l_egalite_compare_les_types_donc_vrai_n_est_pas_1() -> None:
    assert (
        output('print true == 1, 1 == "1", 1 != "1", 0 == false;')
        == "false false true false\n"
    )


def test_et_et_ou_court_circuitent() -> None:
    assert (
        output("print false and (1 / 0 == 0), true or (1 / 0 == 0);") == "false true\n"
    )


def test_les_booleens_et_les_textes_s_affichent_sans_guillemets() -> None:
    assert output('print true, false, "bonjour", 42;') == "true false bonjour 42\n"


# --- Sécurité du code généré ---------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["input", "range", "def", "_print", "_calc_a", "v_a", "__import__"]
)
def test_un_nom_qui_ressemble_a_du_python_ne_casse_rien(name: str) -> None:
    assert output(f"let {name} = 7; for i in 0..{name} {{ }} print {name};") == "7\n"


def test_les_noms_accentues_fonctionnent() -> None:
    assert (
        output("let température = 20; bind double = température * 2; print double;")
        == "40\n"
    )


def test_un_texte_ne_peut_pas_injecter_du_python() -> None:
    trap = r"\"); __import__('os').system('echo PWNED'); (\""
    text = output(f'print "{trap}";')
    assert text == "\"); __import__('os').system('echo PWNED'); (\"\n"
    assert "PWNED" not in transpile(f'print "{trap}";').replace("echo PWNED", "")


def test_les_echappements_arrivent_intacts() -> None:
    assert output(r'print "a\"b\\c\nd";') == 'a"b\\c\nd\n'


# --- Les erreurs d'exécution ---------------------------------------------------------------


def test_une_erreur_d_execution_donne_la_ligne_du_programme_butterfly() -> None:
    line, message, _ = execution_error("print 1;\nprint 2;\nprint 1 / 0;")
    assert (line, message) == (3, "division by zero")


def test_ce_qui_est_affiche_avant_l_erreur_est_conserve() -> None:
    _, _, before = execution_error("print 1;\nprint 2;\nprint 1 / 0;\nprint 4;")
    assert before == "1\n2\n"


def test_la_ligne_est_celle_de_l_operateur_dans_une_expression_multiligne() -> None:
    line, _, _ = execution_error("print 1 +\n  2 +\n  3 / 0;")
    assert line == 3


def test_une_erreur_dans_une_formule_est_signalee_a_la_ligne_de_la_formule() -> None:
    line, message, _ = execution_error("let d = 1;\nbind q = 10 / d;\nd = 0;")
    assert (line, message) == (2, "division by zero")


def test_une_erreur_dans_un_observateur_est_signalee_a_sa_ligne() -> None:
    line, _, _ = execution_error("let a = 1;\nwhen a {\n  print 1 / 0;\n}\na = 2;")
    assert line == 3


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("print 5 % 0;", "modulo by zero"),
        (
            'print 1 + "a";',
            "'+' expects two integers or two texts, not integer and text",
        ),
        ('print "a" - "b";', "'-' expects two integers, not text and text"),
        ("print true * 2;", "'*' expects two integers, not boolean and integer"),
        ('print -"a";', "'-' expects an integer, not a text"),
        (
            'print 1 < "a";',
            "'<' compares two integers or two texts, not integer and text",
        ),
        (
            "print true >= false;",
            "'>=' compares two integers or two texts, not boolean and boolean",
        ),
        ("print not 3;", "boolean expected, integer found"),
        ("print 1 and true;", "boolean expected, integer found"),
        ("if 3 { }", "the condition of 'if' must be a boolean, not an integer"),
        (
            'for i in "a"..3 { }',
            "the bounds of 'for' must be integers, not a text",
        ),
        ('print min(1, "a");', "'min' expects two integers, not integer and text"),
        ("print abs(true);", "abs expects an integer, not a boolean"),
    ],
)
def test_les_erreurs_de_type_sont_signalees_a_l_execution(
    source: str, message: str
) -> None:
    assert execution_error(source)[1] == message


# --- L'API ---------------------------------------------------------------------------------


def test_on_peut_fournir_son_propre_flux_de_sortie() -> None:
    stream = io.StringIO()
    result = execute("print 1;", stream)
    assert result.ok
    assert result.output == ""
    assert stream.getvalue() == "1\n"


def test_le_python_genere_est_valide_et_n_importe_que_ce_qu_il_utilise() -> None:
    code = transpile("print 1;")
    compile(code, "<test>", "exec")
    assert "from butterfly.runtime import _print\n" in code
    assert "_plus" not in code


def test_un_programme_faux_n_est_pas_transpile() -> None:
    with pytest.raises(CompilationError):
        transpile("print x;")
