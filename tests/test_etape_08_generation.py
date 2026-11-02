"""Étape 8 : la génération de Python et l'exécution des programmes."""

import io
from pathlib import Path

import pytest

from butterfly.compilateur import executer, transpiler
from butterfly.erreurs import ErreurCompilation

EXEMPLES = Path(__file__).resolve().parent.parent / "exemples"
PROGRAMMES = sorted(EXEMPLES.glob("*.fly"))


def sortie(source: str) -> str:
    resultat = executer(source)
    assert resultat.erreur is None, str(resultat.erreur)
    return resultat.sortie


def erreur_execution(source: str) -> tuple[int | None, str, str]:
    """(ligne, message, sortie affichée avant l'erreur)."""
    resultat = executer(source)
    assert resultat.erreur is not None
    return resultat.erreur.ligne, resultat.erreur.message, resultat.sortie


# --- Le test central : chaque exemple produit sa sortie attendue ----------------------


@pytest.mark.parametrize("programme", PROGRAMMES, ids=lambda p: p.stem)
def test_chaque_exemple_produit_sa_sortie_attendue(programme: Path) -> None:
    attendu = programme.with_suffix(".attendu").read_text(encoding="utf-8")
    assert sortie(programme.read_text(encoding="utf-8")) == attendu


# --- La propagation ---------------------------------------------------------------------


def test_une_cellule_derivee_suit_sa_source() -> None:
    assert (
        sortie("soit a = 1; lie b = a * 2; affiche b; a = 5; affiche b;") == "2\n10\n"
    )


def test_la_propagation_traverse_plusieurs_niveaux() -> None:
    source = (
        "soit a = 1; lie b = a + 1; lie c = b * 2; lie d = c + a; a = 10; affiche d;"
    )
    assert sortie(source) == "32\n"  # b=11, c=22, d=22+10


def test_une_cellule_independante_n_est_pas_recalculee() -> None:
    code = transpiler("soit a = 1; soit b = 1; lie c = b; a = 2;")
    assert code.count("v_c = _calc_c()") == 1  # seulement à la déclaration


def test_une_cellule_est_recalculee_une_seule_fois_par_affectation() -> None:
    source = "soit a = 1; lie b = a; lie c = a; lie d = b + c; a = 2;"
    code = transpiler(source)
    assert code.count("v_d = _calc_d()") == 2  # déclaration + une affectation


def test_un_observateur_ne_se_declenche_que_si_la_valeur_change() -> None:
    source = 'soit a = 1; quand a { affiche "chg"; } a = 1; a = 2; a = 2; a = 3;'
    assert sortie(source) == "chg\nchg\n"


def test_un_observateur_n_est_pas_declenche_a_la_creation_de_la_cellule() -> None:
    assert sortie('soit a = 1; lie b = a; quand b { affiche "non"; }') == ""


def test_un_observateur_sur_une_derivee_attend_que_sa_valeur_change() -> None:
    source = (
        "soit a = 1; lie pair = a % 2 == 0;"
        ' quand pair { affiche "pair :", pair; } a = 3; a = 4; a = 6; a = 7;'
    )
    assert sortie(source) == "pair : vrai\npair : faux\n"


def test_plusieurs_observateurs_s_executent_dans_l_ordre_de_declaration() -> None:
    source = 'soit a = 1; quand a { affiche "premier"; } quand a { affiche "second"; } a = 2;'
    assert sortie(source) == "premier\nsecond\n"


def test_un_observateur_declare_apres_une_affectation_ne_la_voit_pas() -> None:
    source = 'soit a = 1; a = 2; quand a { affiche "vu"; } a = 3;'
    assert sortie(source) == "vu\n"


def test_une_cellule_derivee_declaree_apres_une_affectation_est_a_jour() -> None:
    assert sortie("soit a = 1; a = 2; lie b = a * 10; affiche b;") == "20\n"


def test_un_observateur_lit_les_autres_cellules_et_a_ses_propres_boucles() -> None:
    source = "soit a = 0; soit b = 10; quand a { pour i dans 0..a { affiche i + b; } } a = 3;"
    assert sortie(source) == "10\n11\n12\n"


def test_une_affectation_dans_une_condition_propage() -> None:
    assert sortie("soit a = 0; lie b = a + 1; si vrai { a = 4; } affiche b;") == "5\n"


def test_l_observateur_ne_voit_jamais_d_etat_intermediaire() -> None:
    source = (
        "soit a = 1; lie b = a + 1; lie c = a * 10; lie d = b + c;"
        " quand d { affiche d; } a = 2; a = 3;"
    )
    assert sortie(source) == "23\n34\n"  # jamais 13 (b à jour, c pas encore)


# --- Les structures de contrôle ---------------------------------------------------------


def test_sinon_si_et_sinon() -> None:
    modele = (
        'si {c1} {{ affiche "a"; }} sinon si {c2} {{ affiche "b"; }}'
        ' sinon {{ affiche "c"; }}'
    )
    assert sortie(modele.format(c1="1 > 2", c2="2 > 1")) == "b\n"
    assert sortie(modele.format(c1="1 > 2", c2="2 > 3")) == "c\n"
    assert sortie(modele.format(c1="2 > 1", c2="vrai")) == "a\n"


def test_les_bornes_de_pour_sont_evaluees_une_seule_fois() -> None:
    source = "soit n = 3; pour i dans 0..n { n = n + 1; affiche i; } affiche n;"
    assert sortie(source) == "0\n1\n2\n6\n"


def test_la_borne_haute_de_pour_est_exclue_et_une_plage_vide_ne_tourne_pas() -> None:
    assert sortie("pour i dans 1..4 { affiche i; }") == "1\n2\n3\n"
    assert (
        sortie("pour i dans 5..2 { affiche i; } pour j dans 3..3 { affiche j; }") == ""
    )


def test_les_blocs_vides_sont_permis() -> None:
    assert (
        sortie("si vrai { } sinon { } pour i dans 0..3 { } soit a = 1; quand a { }")
        == ""
    )


# --- Les valeurs ---------------------------------------------------------------------------


def test_division_et_modulo_suivent_python() -> None:
    assert sortie("affiche -17 / 5, -17 % 5, 17 / -5, 17 % -5;") == "-4 3 -4 -3\n"


def test_les_entiers_sont_de_taille_illimitee() -> None:
    assert sortie("affiche 99999999999 * 99999999999;") == "9999999999800000000001\n"


def test_les_textes_se_concatenent_et_se_comparent() -> None:
    assert (
        sortie('affiche "a" + "b", "a" < "b", "x" == "x", "x" != "y";')
        == "ab vrai vrai vrai\n"
    )


def test_l_egalite_compare_les_types_donc_vrai_n_est_pas_1() -> None:
    assert (
        sortie('affiche vrai == 1, 1 == "1", 1 != "1", 0 == faux;')
        == "faux faux vrai faux\n"
    )


def test_et_et_ou_court_circuitent() -> None:
    assert (
        sortie("affiche faux et (1 / 0 == 0), vrai ou (1 / 0 == 0);") == "faux vrai\n"
    )


def test_les_booleens_et_les_textes_s_affichent_sans_guillemets() -> None:
    assert sortie('affiche vrai, faux, "bonjour", 42;') == "vrai faux bonjour 42\n"


# --- Sécurité du code généré ---------------------------------------------------------------


@pytest.mark.parametrize(
    "nom", ["print", "range", "def", "_affiche", "_calc_a", "v_a", "__import__"]
)
def test_un_nom_qui_ressemble_a_du_python_ne_casse_rien(nom: str) -> None:
    assert sortie(f"soit {nom} = 7; pour i dans 0..{nom} {{ }} affiche {nom};") == "7\n"


def test_les_noms_accentues_fonctionnent() -> None:
    assert (
        sortie("soit température = 20; lie double = température * 2; affiche double;")
        == "40\n"
    )


def test_un_texte_ne_peut_pas_injecter_du_python() -> None:
    piege = r"\"); __import__('os').system('echo PWNED'); (\""
    texte = sortie(f'affiche "{piege}";')
    assert texte == "\"); __import__('os').system('echo PWNED'); (\"\n"
    assert "PWNED" not in transpiler(f'affiche "{piege}";').replace("echo PWNED", "")


def test_les_echappements_arrivent_intacts() -> None:
    assert sortie(r'affiche "a\"b\\c\nd";') == 'a"b\\c\nd\n'


# --- Les erreurs d'exécution ---------------------------------------------------------------


def test_une_erreur_d_execution_donne_la_ligne_du_programme_butterfly() -> None:
    ligne, message, _ = erreur_execution("affiche 1;\naffiche 2;\naffiche 1 / 0;")
    assert (ligne, message) == (3, "division par zéro")


def test_ce_qui_est_affiche_avant_l_erreur_est_conserve() -> None:
    _, _, avant = erreur_execution("affiche 1;\naffiche 2;\naffiche 1 / 0;\naffiche 4;")
    assert avant == "1\n2\n"


def test_la_ligne_est_celle_de_l_operateur_dans_une_expression_multiligne() -> None:
    ligne, _, _ = erreur_execution("affiche 1 +\n  2 +\n  3 / 0;")
    assert ligne == 3


def test_une_erreur_dans_une_formule_est_signalee_a_la_ligne_de_la_formule() -> None:
    ligne, message, _ = erreur_execution("soit d = 1;\nlie q = 10 / d;\nd = 0;")
    assert (ligne, message) == (2, "division par zéro")


def test_une_erreur_dans_un_observateur_est_signalee_a_sa_ligne() -> None:
    ligne, _, _ = erreur_execution(
        "soit a = 1;\nquand a {\n  affiche 1 / 0;\n}\na = 2;"
    )
    assert ligne == 3


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("affiche 5 % 0;", "modulo par zéro"),
        (
            'affiche 1 + "a";',
            "'+' attend deux entiers ou deux textes, pas entier et texte",
        ),
        ('affiche "a" - "b";', "'-' attend deux entiers, pas texte et texte"),
        ("affiche vrai * 2;", "'*' attend deux entiers, pas booléen et entier"),
        ('affiche -"a";', "'-' attend un entier, pas un texte"),
        (
            'affiche 1 < "a";',
            "'<' compare deux entiers ou deux textes, pas entier et texte",
        ),
        (
            "affiche vrai >= faux;",
            "'>=' compare deux entiers ou deux textes, pas booléen et booléen",
        ),
        ("affiche non 3;", "booléen attendu, entier trouvé"),
        ("affiche 1 et vrai;", "booléen attendu, entier trouvé"),
        ("si 3 { }", "la condition de 'si' doit être un booléen, pas un entier"),
        (
            'pour i dans "a"..3 { }',
            "les bornes de 'pour' doivent être des entiers, pas un texte",
        ),
        ('affiche min(1, "a");', "'min' attend deux entiers, pas entier et texte"),
        ("affiche abs(vrai);", "abs attend un entier, pas un booléen"),
    ],
)
def test_les_erreurs_de_type_sont_signalees_a_l_execution(
    source: str, message: str
) -> None:
    assert erreur_execution(source)[1] == message


# --- L'API ---------------------------------------------------------------------------------


def test_on_peut_fournir_son_propre_flux_de_sortie() -> None:
    flux = io.StringIO()
    resultat = executer("affiche 1;", flux)
    assert resultat.ok
    assert resultat.sortie == ""
    assert flux.getvalue() == "1\n"


def test_le_python_genere_est_valide_et_n_importe_que_ce_qu_il_utilise() -> None:
    code = transpiler("affiche 1;")
    compile(code, "<test>", "exec")
    assert "from butterfly.runtime import _affiche\n" in code
    assert "_plus" not in code


def test_un_programme_faux_n_est_pas_transpile() -> None:
    with pytest.raises(ErreurCompilation):
        transpiler("affiche x;")
