"""Étape 3 : le lexer."""

import pytest

from butterfly.erreurs import ErreurLexicale, Position
from butterfly.lexer import tokenize
from butterfly.tokens import TypeToken

T = TypeToken


def types(source: str) -> list[TypeToken]:
    return [t.type for t in tokenize(source)]


def test_une_source_vide_ne_donne_que_le_token_fin() -> None:
    assert types("") == [T.FIN]
    assert types("   \n\t ") == [T.FIN]


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("soit x = 1;", [T.SOIT, T.IDENT, T.EGAL, T.ENTIER, T.POINT_VIRGULE, T.FIN]),
        ("1..5", [T.ENTIER, T.POINT_POINT, T.ENTIER, T.FIN]),
        ("a<=b", [T.IDENT, T.INF_EGAL, T.IDENT, T.FIN]),
        ("a<b", [T.IDENT, T.INF, T.IDENT, T.FIN]),
        ("a==b!=c", [T.IDENT, T.EGAL_EGAL, T.IDENT, T.DIFFERENT, T.IDENT, T.FIN]),
        ("a = b", [T.IDENT, T.EGAL, T.IDENT, T.FIN]),
        ("(a, b) {}", [T.PAREN_G, T.IDENT, T.VIRGULE, T.IDENT, T.PAREN_D,
                       T.ACC_G, T.ACC_D, T.FIN]),
        ("+ - * / %", [T.PLUS, T.MOINS, T.ETOILE, T.SLASH, T.POURCENT, T.FIN]),
        ("vrai faux et ou non", [T.VRAI, T.FAUX, T.ET, T.OU, T.NON, T.FIN]),
    ],
)  # fmt: skip
def test_types_des_tokens(source: str, attendu: list[TypeToken]) -> None:
    assert types(source) == attendu


@pytest.mark.parametrize("mot", ["soit_x", "sinon2", "si_", "_si", "lies", "Soit"])
def test_un_mot_cle_colle_a_d_autres_caracteres_est_un_identifiant(mot: str) -> None:
    assert types(mot) == [T.IDENT, T.FIN]


def test_les_identifiants_accentues_sont_permis() -> None:
    tokens = list(tokenize("température été_2"))
    assert [t.lexeme for t in tokens[:2]] == ["température", "été_2"]
    assert all(t.type is T.IDENT for t in tokens[:2])


def test_un_entier_porte_sa_valeur_et_les_zeros_de_tete_sont_permis() -> None:
    token = next(tokenize("007"))
    assert token.type is T.ENTIER
    assert token.valeur == 7
    assert token.lexeme == "007"


def test_un_nombre_decimal_est_une_erreur_lexicale() -> None:
    with pytest.raises(ErreurLexicale, match="décimaux") as erreur:
        list(tokenize("affiche 1.5;"))
    assert erreur.value.position == Position(1, 10)


def test_un_nombre_trop_grand_est_une_erreur_lexicale() -> None:
    with pytest.raises(ErreurLexicale, match="trop grand"):
        list(tokenize("9" * 5000))


def test_un_texte_porte_sa_valeur_sans_guillemets() -> None:
    token = next(tokenize('"bonjour"'))
    assert token.type is T.TEXTE
    assert token.valeur == "bonjour"
    assert token.lexeme == '"bonjour"'


def test_les_echappements_sont_resolus() -> None:
    token = next(tokenize(r'"a\"b\\c\nd"'))
    assert token.valeur == 'a"b\\c\nd'


def test_un_echappement_inconnu_est_une_erreur_signalee_sur_l_antislash() -> None:
    with pytest.raises(ErreurLexicale, match="échappement inconnu") as erreur:
        list(tokenize(r'"ab\t"'))
    assert erreur.value.position == Position(1, 4)


@pytest.mark.parametrize("source", ['"ouvert', '"ouvert\nsuite"'])
def test_un_texte_non_ferme_est_signale_a_son_guillemet_ouvrant(source: str) -> None:
    with pytest.raises(ErreurLexicale, match="non fermé") as erreur:
        list(tokenize(source))
    assert erreur.value.position == Position(1, 1)


@pytest.mark.parametrize(("source", "caractere"), [("a @ b", "@"), ("x ! y", "!"),
                                                    ("$", "$"), ("a . b", ".")])  # fmt: skip
def test_un_caractere_inattendu_est_signale_avec_sa_position(
    source: str, caractere: str
) -> None:
    with pytest.raises(ErreurLexicale, match="caractère inattendu") as erreur:
        list(tokenize(source))
    assert repr(caractere) in str(erreur.value)
    assert erreur.value.position == Position(1, source.index(caractere) + 1)


def test_les_commentaires_sont_ignores_par_defaut() -> None:
    assert types("a # un commentaire\nb") == [T.IDENT, T.IDENT, T.FIN]


def test_les_commentaires_sont_produits_a_la_demande() -> None:
    tokens = list(tokenize("a # note", commentaires=True))
    assert [t.type for t in tokens] == [T.IDENT, T.COMMENTAIRE, T.FIN]
    assert tokens[1].lexeme == "# note"


def test_les_positions_suivent_les_lignes_et_les_colonnes() -> None:
    tokens = list(tokenize("soit a = 1;\n  affiche a;"))
    assert tokens[0].position == Position(1, 1)
    assert tokens[1].position == Position(1, 6)
    affiche = next(t for t in tokens if t.type is T.AFFICHE)
    assert affiche.position == Position(2, 3)
    assert tokens[-1].type is T.FIN
    assert tokens[-1].position == Position(2, 13)  # juste après le dernier ';'


def test_le_lexer_est_paresseux_et_les_tokens_avant_l_erreur_sont_disponibles() -> None:
    flux = tokenize("a b @ c")
    assert next(flux).lexeme == "a"
    assert next(flux).lexeme == "b"
    with pytest.raises(ErreurLexicale):
        next(flux)


def test_les_fins_de_ligne_windows_sont_acceptees() -> None:
    assert types("a\r\nb\r\n") == [T.IDENT, T.IDENT, T.FIN]
