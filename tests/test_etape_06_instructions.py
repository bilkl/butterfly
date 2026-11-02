"""Étape 6 : le parser des instructions, avec récupération d'erreurs."""

import pytest

from butterfly.erreurs import ErreurCompilation, Position
from butterfly.noeuds import (
    Affectation,
    Affiche,
    Bloc,
    Declaration,
    Liaison,
    Observation,
    Pour,
    Programme,
    Si,
)
from butterfly.parser import analyser_syntaxe


def erreurs(source: str) -> list[tuple[int | None, int | None, str]]:
    with pytest.raises(ErreurCompilation) as erreur:
        analyser_syntaxe(source)
    return [(e.ligne, e.colonne, e.message) for e in erreur.value.erreurs]


def test_un_programme_vide_est_valide() -> None:
    assert analyser_syntaxe("") == Programme(())
    assert analyser_syntaxe("# juste un commentaire\n") == Programme(())


def test_chaque_instruction_donne_le_bon_noeud() -> None:
    programme = analyser_syntaxe(
        """
        soit a = 1;
        lie b = a + 1;
        quand b { affiche b; }
        a = 2;
        si a > 1 { affiche a; }
        pour i dans 0..3 { affiche i; }
        affiche a, b;
        """
    )
    assert [type(i) for i in programme.instructions] == [
        Declaration, Liaison, Observation, Affectation, Si, Pour, Affiche,
    ]  # fmt: skip


def test_une_declaration_garde_la_position_du_nom() -> None:
    declaration = analyser_syntaxe("soit total = 1;").instructions[0]
    assert isinstance(declaration, Declaration)
    assert declaration.nom == "total"
    assert declaration.position == Position(1, 1)
    assert declaration.position_nom == Position(1, 6)


def test_un_bloc_vide_est_permis() -> None:
    si = analyser_syntaxe("si vrai { }").instructions[0]
    assert isinstance(si, Si)
    assert si.alors.instructions == ()


def test_sinon_si_et_sinon_s_enchainent() -> None:
    si = analyser_syntaxe(
        "si a { } sinon si b { affiche 1; } sinon { affiche 2; }"
    ).instructions[0]
    assert isinstance(si, Si)
    assert isinstance(si.sinon, Si)
    assert isinstance(si.sinon.sinon, Bloc)


def test_le_bloc_garde_la_position_de_ses_accolades() -> None:
    si = analyser_syntaxe("si vrai {\n}").instructions[0]
    assert isinstance(si, Si)
    assert si.alors.position == Position(1, 9)
    assert si.alors.fin == Position(2, 1)


def test_affiche_accepte_plusieurs_valeurs() -> None:
    affiche = analyser_syntaxe('affiche 1, "a", vrai;').instructions[0]
    assert isinstance(affiche, Affiche)
    assert len(affiche.valeurs) == 3


def test_pour_borne_haute_peut_etre_une_expression() -> None:
    pour = analyser_syntaxe("pour i dans a + 1..b * 2 { }").instructions[0]
    assert isinstance(pour, Pour)
    assert pour.variable == "i"


# --- Erreurs ---------------------------------------------------------------------


@pytest.mark.parametrize("mot", ["lie", "quand"])
def test_lie_et_quand_sont_refuses_dans_un_bloc(mot: str) -> None:
    source = (
        f"si vrai {{ {mot} x = 1; }}"
        if mot == "lie"
        else f"si vrai {{ {mot} x {{ }} }}"
    )
    premiere = erreurs(source)[0]
    assert premiere[:2] == (1, 11)
    assert premiere[2] == f"'{mot}' n'est permis qu'au niveau supérieur"


def test_un_point_virgule_oublie_est_signale_juste_apres_la_derniere_instruction() -> (
    None
):
    assert erreurs("soit a = 1\nsoit b = 2;") == [
        (1, 11, "';' attendu à la fin de l'instruction, 'soit' trouvé"),
    ]


def test_un_point_virgule_oublie_en_fin_de_programme() -> None:
    assert erreurs("affiche 1")[0][2].startswith("';' attendu")


def test_les_erreurs_sont_collectees_en_une_seule_fois() -> None:
    resultat = erreurs("soit a = ;\nsoit b = 2;\nsoit c = ;\naffiche ;")
    assert [(ligne, colonne) for ligne, colonne, _ in resultat] == [
        (1, 10),
        (3, 10),
        (4, 9),
    ]


def test_apres_une_erreur_le_parser_reprend_a_l_instruction_suivante() -> None:
    # La 2e ligne est correcte : elle ne doit pas produire d'erreur en plus.
    assert len(erreurs("soit a = ;\nsoit b = 2;")) == 1


def test_une_erreur_dans_un_bloc_n_empeche_pas_de_lire_la_suite() -> None:
    resultat = erreurs("si vrai {\n  soit a = ;\n  affiche 1;\n}\nsoit b = ;")
    assert [ligne for ligne, _, _ in resultat] == [2, 5]


def test_une_accolade_non_fermee_est_signalee_en_fin_de_programme() -> None:
    resultat = erreurs("si vrai { affiche 1;")
    assert resultat[-1][2] == "'}' attendu, fin de programme trouvé"


def test_une_accolade_fermante_en_trop_est_signalee() -> None:
    assert erreurs("affiche 1; }")[0][2] == "instruction attendue, '}' trouvé"


def test_un_appel_hors_expression_est_signale() -> None:
    assert erreurs("foo(1);")[0][2] == "'=' attendu après 'foo', '(' trouvé"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("soit = 1;", "nom attendu, '=' trouvé"),
        ("soit 5 = 1;", "nom attendu, '5' trouvé"),
        ("soit x 1;", "'=' attendu, '1' trouvé"),
        ("pour i 0..3 { }", "'dans' attendu, '0' trouvé"),
        ("pour i dans 0 3 { }", "'..' attendu, '3' trouvé"),
        ("si vrai affiche 1;", "'{' attendu, 'affiche' trouvé"),
        ("quand { }", "nom de cellule attendu, '{' trouvé"),
        ("5;", "instruction attendue, '5' trouvé"),
    ],
)
def test_messages_d_erreur_des_instructions(source: str, message: str) -> None:
    assert erreurs(source)[0][2] == message


def test_une_erreur_lexicale_arrete_tout_et_est_la_seule_signalee() -> None:
    resultat = erreurs("soit a = 1;\nsoit b = 2 @ 3;")
    assert resultat == [(2, 12, "caractère inattendu '@'")]
