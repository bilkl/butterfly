"""Étape 7 : l'analyse sémantique."""

import pytest

from butterfly.compilateur import compiler, verifier
from butterfly.erreurs import ErreurCompilation
from butterfly.semantique import GenreSymbole


def erreurs(source: str) -> list[tuple[int | None, int | None, str]]:
    return [(e.ligne, e.colonne, e.message) for e in verifier(source)]


def messages(source: str) -> list[str]:
    return [message for _, _, message in erreurs(source)]


@pytest.mark.parametrize(
    "source",
    [
        "",
        "soit a = 1; affiche a;",
        "soit a = 1; lie b = a + 1; quand b { affiche b; }",
        "soit a = 1; si a > 0 { soit b = 2; affiche b; }",
        # un nom de bloc frère peut être réutilisé
        "si vrai { soit t = 1; } si vrai { soit t = 2; }",
        # la variable de boucle disparaît après la boucle
        "pour i dans 0..2 { } pour i dans 0..2 { }",
        "affiche min(1, 2), max(1, 2), abs(-1);",
        "soit a = 1; quand a { soit local = a; affiche local; }",
    ],
)
def test_programmes_valides(source: str) -> None:
    assert verifier(source) == ()


# --- Noms --------------------------------------------------------------------------


def test_un_nom_non_declare_est_signale_a_sa_position() -> None:
    assert erreurs("affiche x;") == [(1, 9, "nom 'x' non déclaré")]


def test_un_nom_doit_etre_declare_avant_d_etre_utilise() -> None:
    assert messages("affiche a; soit a = 1;") == ["nom 'a' non déclaré"]


def test_une_declaration_ne_peut_pas_se_citer_elle_meme() -> None:
    assert messages("soit x = x + 1;") == ["nom 'x' non déclaré"]


def test_un_nom_declare_dans_un_bloc_n_existe_plus_apres() -> None:
    assert messages("si vrai { soit t = 1; }\naffiche t;") == ["nom 't' non déclaré"]


def test_la_variable_de_boucle_n_existe_plus_apres_la_boucle() -> None:
    assert messages("pour i dans 0..2 { }\naffiche i;") == ["nom 'i' non déclaré"]


def test_une_redeclaration_est_signalee_avec_la_ligne_de_la_premiere() -> None:
    assert erreurs("soit a = 1;\nsoit a = 2;") == [
        (2, 6, "'a' est déjà déclaré (ligne 1)")
    ]


def test_un_nom_ne_peut_pas_en_masquer_un_autre() -> None:
    assert messages("soit a = 1; si vrai { soit a = 2; }") == [
        "'a' est déjà déclaré (ligne 1)"
    ]


def test_une_variable_de_boucle_ne_peut_pas_masquer_une_cellule() -> None:
    assert messages("soit i = 1; pour i dans 0..2 { }") == [
        "'i' est déjà déclaré (ligne 1)"
    ]


def test_les_noms_des_fonctions_predefinies_sont_reserves() -> None:
    assert "fonction prédéfinie" in messages("soit min = 1;")[0]
    assert "fonction prédéfinie" in messages("lie max = 1;")[0]


def test_une_fonction_predefinie_utilisee_comme_variable_est_signalee() -> None:
    assert "avec des parenthèses" in messages("affiche min;")[0]


# --- Affectations --------------------------------------------------------------------


def test_affecter_une_cellule_derivee_est_refuse() -> None:
    assert erreurs("soit a = 1;\nlie b = a;\nb = 2;") == [
        (
            3,
            1,
            "'b' est une cellule dérivée (lie), on ne peut pas lui affecter de valeur",
        )
    ]


def test_affecter_une_variable_de_boucle_est_refuse() -> None:
    assert "variable de boucle" in messages("pour i dans 0..3 { i = 5; }")[0]


def test_affecter_un_nom_non_declare_est_refuse() -> None:
    assert messages("x = 1;") == ["nom 'x' non déclaré"]


def test_affecter_une_variable_locale_est_permis() -> None:
    assert verifier("si vrai { soit t = 1; t = 2; }") == ()


# --- Observateurs --------------------------------------------------------------------


def test_un_observateur_ne_peut_pas_affecter_une_cellule_du_niveau_superieur() -> None:
    resultat = messages("soit a = 1; quand a { a = 2; }")
    assert "un observateur (quand) ne peut pas la modifier" in resultat[0]


def test_un_observateur_peut_affecter_ses_propres_variables() -> None:
    assert verifier("soit a = 1; quand a { soit t = 1; t = t + 1; }") == ()


def test_un_observateur_doit_viser_une_cellule_declaree() -> None:
    assert messages("quand z { }") == ["nom 'z' non déclaré"]


def test_un_observateur_ne_peut_pas_viser_une_variable_locale() -> None:
    assert messages("pour i dans 0..2 { }\nquand i { }") == ["nom 'i' non déclaré"]


# --- Fonctions -----------------------------------------------------------------------


def test_une_fonction_inconnue_est_signalee_avec_les_fonctions_permises() -> None:
    resultat = messages("affiche racine(4);")
    assert resultat == [
        "fonction 'racine' inconnue (fonctions prédéfinies : min, max, abs)"
    ]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("affiche min(1);", "min attend 2 arguments, 1 donné(s)"),
        ("affiche max(1, 2, 3);", "max attend 2 arguments, 3 donné(s)"),
        ("affiche abs();", "abs attend 1 argument, 0 donné(s)"),
        ("affiche abs(1, 2);", "abs attend 1 argument, 2 donné(s)"),
    ],
)
def test_le_nombre_d_arguments_est_verifie(source: str, message: str) -> None:
    assert messages(source) == [message]


# --- Ensemble ------------------------------------------------------------------------


def test_toutes_les_erreurs_sont_collectees_et_triees_par_position() -> None:
    resultat = erreurs("affiche a;\nsoit b = 1;\nsoit b = 2;\nc = 3;")
    assert [(ligne, colonne) for ligne, colonne, _ in resultat] == [
        (1, 9),
        (3, 6),
        (4, 1),
    ]


def test_les_erreurs_viennent_d_une_erreur_de_compilation() -> None:
    with pytest.raises(ErreurCompilation) as erreur:
        compiler("affiche x;")
    assert len(erreur.value.erreurs) == 1
    assert "Erreur sémantique" in str(erreur.value)


def test_l_analyse_donne_les_cellules_et_les_dependances() -> None:
    analyse = compiler(
        "soit a = 1; soit b = 2; lie c = a + 1; lie d = c * b; si vrai { soit t = 0; }"
    )
    assert analyse.cellules == ("a", "b", "c", "d")
    assert analyse.genres == {
        "a": GenreSymbole.SOURCE,
        "b": GenreSymbole.SOURCE,
        "c": GenreSymbole.DERIVEE,
        "d": GenreSymbole.DERIVEE,
    }
    assert analyse.dependances == {"c": frozenset({"a"}), "d": frozenset({"c", "b"})}
