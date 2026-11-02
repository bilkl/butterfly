"""Étape 5 : le parser des expressions (Pratt)."""

import pytest

from butterfly.erreurs import ErreurCompilation, Position
from butterfly.noeuds import Affiche, Expression, en_sexpr
from butterfly.parser import analyser_syntaxe


def expr(source: str) -> Expression:
    instruction = analyser_syntaxe(f"affiche {source};").instructions[0]
    assert isinstance(instruction, Affiche)
    return instruction.valeurs[0]


def sexpr(source: str) -> str:
    return en_sexpr(expr(source))


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        # priorité : * / % avant + - avant comparaisons avant non avant et avant ou
        ("2 + 3 * 4", "(+ 2 (* 3 4))"),
        ("2 * 3 + 4", "(+ (* 2 3) 4)"),
        ("a + b < c * d", "(< (+ a b) (* c d))"),
        ("a < b et c < d", "(et (< a b) (< c d))"),
        ("a ou b et c", "(ou a (et b c))"),
        ("a et b ou c", "(ou (et a b) c)"),
        ("non a et b", "(et (non a) b)"),
        ("non a == b", "(non (== a b))"),
        ("a et non b", "(et a (non b))"),
        ("non non a", "(non (non a))"),
        # associativité à gauche
        ("a - b - c", "(- (- a b) c)"),
        ("a / b / c", "(/ (/ a b) c)"),
        ("a - b + c", "(+ (- a b) c)"),
        ("a ou b ou c", "(ou (ou a b) c)"),
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
        ("vrai et faux", "(et True False)"),
    ],
)
def test_priorites_et_associativite(source: str, attendu: str) -> None:
    assert sexpr(source) == attendu


def test_les_operateurs_binaires_portent_la_position_de_l_operateur() -> None:
    noeud = expr("a\n  + b")
    assert noeud.position == Position(2, 3)


@pytest.mark.parametrize("operateur", ["==", "!=", "<", "<=", ">", ">="])
def test_les_comparaisons_ne_s_enchainent_pas(operateur: str) -> None:
    with pytest.raises(ErreurCompilation) as erreur:
        expr(f"1 {operateur} 2 {operateur} 3")
    premiere = erreur.value.erreurs[0]
    assert "ne s'enchaînent pas" in premiere.message
    # « affiche 1 OP 2 OP 3; » : le 2e opérateur est à la colonne 14 + len(OP).
    assert premiere.colonne == 14 + len(operateur)


def test_une_comparaison_entre_parentheses_peut_etre_comparee() -> None:
    assert sexpr("(1 < 2) == vrai") == "(== (< 1 2) True)"


@pytest.mark.parametrize("source", ["1 + non a", "a == non b", "-non a"])
def test_non_est_refuse_comme_operande_d_un_operateur_plus_fort(source: str) -> None:
    with pytest.raises(ErreurCompilation, match="'non' doit être entre parenthèses"):
        expr(source)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("", "expression attendue, ';' trouvé"),
        ("1 +", "expression attendue, ';' trouvé"),
        ("* 2", "expression attendue, '*' trouvé"),
        ("(1 + 2", "')' attendu, ';' trouvé"),
        ("min(1,", "expression attendue, ';' trouvé"),
        ("min(1 2)", "')' attendu, '2' trouvé"),
        ("1 2", "';' attendu à la fin de l'instruction, '2' trouvé"),
    ],
)
def test_messages_d_erreur_des_expressions(source: str, message: str) -> None:
    with pytest.raises(ErreurCompilation) as erreur:
        expr(source)
    assert erreur.value.erreurs[0].message == message


def test_l_erreur_d_une_expression_incomplete_est_signalee_sur_le_token_fautif() -> (
    None
):
    with pytest.raises(ErreurCompilation) as erreur:
        analyser_syntaxe("soit x = ;")
    assert erreur.value.erreurs[0].position == Position(1, 10)
