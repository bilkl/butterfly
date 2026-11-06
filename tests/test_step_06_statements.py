"""Étape 6 : le parser des instructions, avec récupération d'erreurs."""

import pytest

from butterfly.errors import CompilationError, Position
from butterfly.nodes import (
    Assignment,
    Binding,
    Block,
    Declaration,
    For,
    If,
    Observer,
    Print,
    Program,
)
from butterfly.parser import analyze_syntax


def errors(source: str) -> list[tuple[int | None, int | None, str]]:
    with pytest.raises(CompilationError) as error:
        analyze_syntax(source)
    return [(e.line, e.column, e.message) for e in error.value.errors]


def test_un_programme_vide_est_valide() -> None:
    assert analyze_syntax("") == Program(())
    assert analyze_syntax("# juste un commentaire\n") == Program(())


def test_chaque_instruction_donne_le_bon_noeud() -> None:
    program = analyze_syntax(
        """
        let a = 1;
        bind b = a + 1;
        when b { print b; }
        a = 2;
        if a > 1 { print a; }
        for i in 0..3 { print i; }
        print a, b;
        """
    )
    assert [type(i) for i in program.statements] == [
        Declaration, Binding, Observer, Assignment, If, For, Print,
    ]  # fmt: skip


def test_une_declaration_garde_la_position_du_nom() -> None:
    declaration = analyze_syntax("let total = 1;").statements[0]
    assert isinstance(declaration, Declaration)
    assert declaration.name == "total"
    assert declaration.position == Position(1, 1)
    assert declaration.name_position == Position(1, 5)


def test_un_bloc_vide_est_permis() -> None:
    if_stmt = analyze_syntax("if true { }").statements[0]
    assert isinstance(if_stmt, If)
    assert if_stmt.then_block.statements == ()


def test_sinon_si_et_sinon_s_enchainent() -> None:
    if_stmt = analyze_syntax(
        "if a { } else if b { print 1; } else { print 2; }"
    ).statements[0]
    assert isinstance(if_stmt, If)
    assert isinstance(if_stmt.else_branch, If)
    assert isinstance(if_stmt.else_branch.else_branch, Block)


def test_le_bloc_garde_la_position_de_ses_accolades() -> None:
    if_stmt = analyze_syntax("if true {\n}").statements[0]
    assert isinstance(if_stmt, If)
    assert if_stmt.then_block.position == Position(1, 9)
    assert if_stmt.then_block.end == Position(2, 1)


def test_affiche_accepte_plusieurs_valeurs() -> None:
    print_stmt = analyze_syntax('print 1, "a", true;').statements[0]
    assert isinstance(print_stmt, Print)
    assert len(print_stmt.values) == 3


def test_pour_borne_haute_peut_etre_une_expression() -> None:
    for_stmt = analyze_syntax("for i in a + 1..b * 2 { }").statements[0]
    assert isinstance(for_stmt, For)
    assert for_stmt.variable == "i"


# --- Erreurs ---------------------------------------------------------------------


@pytest.mark.parametrize("word", ["bind", "when"])
def test_lie_et_quand_sont_refuses_dans_un_bloc(word: str) -> None:
    source = (
        f"if true {{ {word} x = 1; }}"
        if word == "bind"
        else f"if true {{ {word} x {{ }} }}"
    )
    first_ = errors(source)[0]
    assert first_[:2] == (1, 11)
    assert first_[2] == f"'{word}' is only allowed at top level"


def test_un_point_virgule_oublie_est_signale_juste_apres_la_derniere_instruction() -> (
    None
):
    assert errors("let a = 1\nlet b = 2;") == [
        (1, 10, "';' expected at the end of the statement, 'let' found"),
    ]


def test_un_point_virgule_oublie_en_fin_de_programme() -> None:
    assert errors("print 1")[0][2].startswith("';' expected")


def test_les_erreurs_sont_collectees_en_une_seule_fois() -> None:
    result = errors("let a = ;\nlet b = 2;\nlet c = ;\nprint ;")
    assert [(line, column) for line, column, _ in result] == [
        (1, 9),
        (3, 9),
        (4, 7),
    ]


def test_apres_une_erreur_le_parser_reprend_a_l_instruction_suivante() -> None:
    # La 2e ligne est correcte : elle ne doit pas produire d'erreur en plus.
    assert len(errors("let a = ;\nlet b = 2;")) == 1


def test_une_erreur_dans_un_bloc_n_empeche_pas_de_lire_la_suite() -> None:
    result = errors("if true {\n  let a = ;\n  print 1;\n}\nlet b = ;")
    assert [line for line, _, _ in result] == [2, 5]


def test_une_accolade_non_fermee_est_signalee_en_fin_de_programme() -> None:
    result = errors("if true { print 1;")
    assert result[-1][2] == "'}' expected, end of program found"


def test_une_accolade_fermante_en_trop_est_signalee() -> None:
    assert errors("print 1; }")[0][2] == "statement expected, '}' found"


def test_un_appel_hors_expression_est_signale() -> None:
    assert errors("foo(1);")[0][2] == "'=' expected after 'foo', '(' found"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("let = 1;", "name expected, '=' found"),
        ("let 5 = 1;", "name expected, '5' found"),
        ("let x 1;", "'=' expected, '1' found"),
        ("for i 0..3 { }", "'in' expected, '0' found"),
        ("for i in 0 3 { }", "'..' expected, '3' found"),
        ("if true print 1;", "'{' expected, 'print' found"),
        ("when { }", "cell name expected, '{' found"),
        ("5;", "statement expected, '5' found"),
    ],
)
def test_messages_d_erreur_des_instructions(source: str, message: str) -> None:
    assert errors(source)[0][2] == message


def test_une_erreur_lexicale_arrete_tout_et_est_la_seule_signalee() -> None:
    result = errors("let a = 1;\nlet b = 2 @ 3;")
    assert result == [(2, 11, "unexpected character '@'")]
