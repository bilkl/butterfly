"""Étape 5 : le parser des expressions (Pratt)."""

import pytest

from butterfly.errors import CompilationError, Position
from butterfly.nodes import Expression, Print, to_sexpr
from butterfly.parser import analyze_syntax


def expr(source: str) -> Expression:
    statement = analyze_syntax(f"print {source};").statements[0]
    assert isinstance(statement, Print)
    return statement.values[0]


def sexpr(source: str) -> str:
    return to_sexpr(expr(source))


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # priorité : * / % avant + - avant comparaisons avant non avant et avant ou
        ("2 + 3 * 4", "(+ 2 (* 3 4))"),
        ("2 * 3 + 4", "(+ (* 2 3) 4)"),
        ("a + b < c * d", "(< (+ a b) (* c d))"),
        ("a < b and c < d", "(and (< a b) (< c d))"),
        ("a or b and c", "(or a (and b c))"),
        ("a and b or c", "(or (and a b) c)"),
        ("not a and b", "(and (not a) b)"),
        ("not a == b", "(not (== a b))"),
        ("a and not b", "(and a (not b))"),
        ("not not a", "(not (not a))"),
        # associativité à gauche
        ("a - b - c", "(- (- a b) c)"),
        ("a / b / c", "(/ (/ a b) c)"),
        ("a - b + c", "(+ (- a b) c)"),
        ("a or b or c", "(or (or a b) c)"),
        # parenthèses
        ("(2 + 3) * 4", "(* (+ 2 3) 4)"),
        ("a - (b - c)", "(- a (- b c))"),
        ("((a))", "a"),
        # moins unaire : le plus prioritaire
        ("-17 / 5", "(/ (- 17) 5)"),
        ("-a * b", "(* (- a) b)"),
        ("- -a", "(- (- a))"),
        ("2 * -3", "(* 2 (- 3))"),
        ("a - -b", "(- a (- b))"),
        # appels et valeurs
        ("min(1, 2 + 3)", "(min 1 (+ 2 3))"),
        ("abs(-7)", "(abs (- 7))"),
        ("min(max(1, 2), 3)", "(min (max 1 2) 3)"),
        ('"a" + "b"', "(+ 'a' 'b')"),
        ("true and false", "(and True False)"),
    ],
)
def test_priorites_et_associativite(source: str, expected: str) -> None:
    assert sexpr(source) == expected


def test_les_operateurs_binaires_portent_la_position_de_l_operateur() -> None:
    node = expr("a\n  + b")
    assert node.position == Position(2, 3)


@pytest.mark.parametrize("operator", ["==", "!=", "<", "<=", ">", ">="])
def test_les_comparaisons_ne_s_enchainent_pas(operator: str) -> None:
    with pytest.raises(CompilationError) as error:
        expr(f"1 {operator} 2 {operator} 3")
    first_ = error.value.errors[0]
    assert "do not chain" in first_.message
    # « print 1 OP 2 OP 3; » : the 2nd operator is at column 12 + len(OP).
    assert first_.column == 12 + len(operator)


def test_une_comparaison_entre_parentheses_peut_etre_comparee() -> None:
    assert sexpr("(1 < 2) == true") == "(== (< 1 2) True)"


@pytest.mark.parametrize("source", ["1 + not a", "a == not b", "-not a"])
def test_non_est_refuse_comme_operande_d_un_operateur_plus_fort(source: str) -> None:
    with pytest.raises(CompilationError, match="'not' must be in parentheses"):
        expr(source)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("", "expression expected, ';' found"),
        ("1 +", "expression expected, ';' found"),
        ("* 2", "expression expected, '*' found"),
        ("(1 + 2", "')' expected, ';' found"),
        ("min(1,", "expression expected, ';' found"),
        ("min(1 2)", "')' expected, '2' found"),
        ("1 2", "';' expected at the end of the statement, '2' found"),
    ],
)
def test_messages_d_erreur_des_expressions(source: str, message: str) -> None:
    with pytest.raises(CompilationError) as error:
        expr(source)
    assert error.value.errors[0].message == message


def test_l_erreur_d_une_expression_incomplete_est_signalee_sur_le_token_fautif() -> (
    None
):
    with pytest.raises(CompilationError) as error:
        analyze_syntax("let x = ;")
    assert error.value.errors[0].position == Position(1, 9)
