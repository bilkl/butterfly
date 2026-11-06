"""Étape 7 : l'analyse sémantique."""

import pytest

from butterfly.compiler import analyze_program, check
from butterfly.errors import CompilationError
from butterfly.semantics import SymbolKind


def errors(source: str) -> list[tuple[int | None, int | None, str]]:
    return [(e.line, e.column, e.message) for e in check(source)]


def messages(source: str) -> list[str]:
    return [message for _, _, message in errors(source)]


@pytest.mark.parametrize(
    "source",
    [
        "",
        "let a = 1; print a;",
        "let a = 1; bind b = a + 1; when b { print b; }",
        "let a = 1; if a > 0 { let b = 2; print b; }",
        # un nom de bloc frère peut être réutilisé
        "if true { let t = 1; } if true { let t = 2; }",
        # la loop variable disparaît après la boucle
        "for i in 0..2 { } for i in 0..2 { }",
        "print min(1, 2), max(1, 2), abs(-1);",
        "let a = 1; when a { let local = a; print local; }",
    ],
)
def test_programmes_valides(source: str) -> None:
    assert check(source) == ()


# --- Noms --------------------------------------------------------------------------


def test_un_nom_non_declare_est_signale_a_sa_position() -> None:
    assert errors("print x;") == [(1, 7, "name 'x' not declared")]


def test_un_nom_doit_etre_declare_avant_d_etre_utilise() -> None:
    assert messages("print a; let a = 1;") == ["name 'a' not declared"]


def test_une_declaration_ne_peut_pas_se_citer_elle_meme() -> None:
    assert messages("let x = x + 1;") == ["name 'x' not declared"]


def test_un_nom_declare_dans_un_bloc_n_existe_plus_apres() -> None:
    assert messages("if true { let t = 1; }\nprint t;") == ["name 't' not declared"]


def test_la_variable_de_boucle_n_existe_plus_apres_la_boucle() -> None:
    assert messages("for i in 0..2 { }\nprint i;") == ["name 'i' not declared"]


def test_une_redeclaration_est_signalee_avec_la_ligne_de_la_premiere() -> None:
    assert errors("let a = 1;\nlet a = 2;") == [
        (2, 5, "'a' is already declared (line 1)")
    ]


def test_un_nom_ne_peut_pas_en_masquer_un_autre() -> None:
    assert messages("let a = 1; if true { let a = 2; }") == [
        "'a' is already declared (line 1)"
    ]


def test_une_variable_de_boucle_ne_peut_pas_masquer_une_cellule() -> None:
    assert messages("let i = 1; for i in 0..2 { }") == [
        "'i' is already declared (line 1)"
    ]


def test_les_noms_des_fonctions_predefinies_sont_reserves() -> None:
    assert "built-in function" in messages("let min = 1;")[0]
    assert "built-in function" in messages("bind max = 1;")[0]


def test_une_fonction_predefinie_utilisee_comme_variable_est_signalee() -> None:
    assert "with parentheses" in messages("print min;")[0]


# --- Affectations --------------------------------------------------------------------


def test_affecter_une_cellule_derivee_est_refuse() -> None:
    assert errors("let a = 1;\nbind b = a;\nb = 2;") == [
        (
            3,
            1,
            "'b' is a derived cell (bind), a value cannot be assigned to it",
        )
    ]


def test_affecter_une_variable_de_boucle_est_refuse() -> None:
    assert "loop variable" in messages("for i in 0..3 { i = 5; }")[0]


def test_affecter_un_nom_non_declare_est_refuse() -> None:
    assert messages("x = 1;") == ["name 'x' not declared"]


def test_affecter_une_variable_locale_est_permis() -> None:
    assert check("if true { let t = 1; t = 2; }") == ()


# --- Observateurs --------------------------------------------------------------------


def test_un_observateur_ne_peut_pas_affecter_une_cellule_du_niveau_superieur() -> None:
    result = messages("let a = 1; when a { a = 2; }")
    assert "an observer (when) cannot modify it" in result[0]


def test_un_observateur_peut_affecter_ses_propres_variables() -> None:
    assert check("let a = 1; when a { let t = 1; t = t + 1; }") == ()


def test_un_observateur_doit_viser_une_cellule_declaree() -> None:
    assert messages("when z { }") == ["name 'z' not declared"]


def test_un_observateur_ne_peut_pas_viser_une_variable_locale() -> None:
    assert messages("for i in 0..2 { }\nwhen i { }") == ["name 'i' not declared"]


# --- Fonctions -----------------------------------------------------------------------


def test_une_fonction_inconnue_est_signalee_avec_les_fonctions_permises() -> None:
    result = messages("print racine(4);")
    assert result == ["unknown function 'racine' (built-in functions: min, max, abs)"]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("print min(1);", "min expects 2 arguments, 1 given"),
        ("print max(1, 2, 3);", "max expects 2 arguments, 3 given"),
        ("print abs();", "abs expects 1 argument, 0 given"),
        ("print abs(1, 2);", "abs expects 1 argument, 2 given"),
    ],
)
def test_le_nombre_d_arguments_est_verifie(source: str, message: str) -> None:
    assert messages(source) == [message]


# --- Ensemble ------------------------------------------------------------------------


def test_toutes_les_erreurs_sont_collectees_et_triees_par_position() -> None:
    result = errors("print a;\nlet b = 1;\nlet b = 2;\nc = 3;")
    assert [(line, column) for line, column, _ in result] == [
        (1, 7),
        (3, 5),
        (4, 1),
    ]


def test_les_erreurs_viennent_d_une_erreur_de_compilation() -> None:
    with pytest.raises(CompilationError) as error:
        analyze_program("print x;")
    assert len(error.value.errors) == 1
    assert "Semantic error" in str(error.value)


def test_l_analyse_donne_les_cellules_et_les_dependances() -> None:
    analysis = analyze_program(
        "let a = 1; let b = 2; bind c = a + 1; bind d = c * b; if true { let t = 0; }"
    )
    assert analysis.cells == ("a", "b", "c", "d")
    assert analysis.kinds == {
        "a": SymbolKind.SOURCE,
        "b": SymbolKind.SOURCE,
        "c": SymbolKind.DERIVED,
        "d": SymbolKind.DERIVED,
    }
    assert analysis.dependencies == {"c": frozenset({"a"}), "d": frozenset({"c", "b"})}
