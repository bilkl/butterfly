"""Étape 3 : le lexer."""

import pytest

from butterfly.errors import LexicalError, Position
from butterfly.lexer import tokenize
from butterfly.tokens import TypeToken

T = TypeToken


def types(source: str) -> list[TypeToken]:
    return [t.type for t in tokenize(source)]


def test_une_source_vide_ne_donne_que_le_token_fin() -> None:
    assert types("") == [T.EOF]
    assert types("   \n\t ") == [T.EOF]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("let x = 1;", [T.LET, T.IDENT, T.EQ, T.INTEGER, T.SEMICOLON, T.EOF]),
        ("1..5", [T.INTEGER, T.DOT_DOT, T.INTEGER, T.EOF]),
        ("a<=b", [T.IDENT, T.LT_EQ, T.IDENT, T.EOF]),
        ("a<b", [T.IDENT, T.LT, T.IDENT, T.EOF]),
        ("a==b!=c", [T.IDENT, T.EQ_EQ, T.IDENT, T.NOT_EQ, T.IDENT, T.EOF]),
        ("a = b", [T.IDENT, T.EQ, T.IDENT, T.EOF]),
        ("(a, b) {}", [T.LPAREN, T.IDENT, T.COMMA, T.IDENT, T.RPAREN,
                       T.LBRACE, T.RBRACE, T.EOF]),
        ("+ - * / %", [T.PLUS, T.MINUS, T.STAR, T.SLASH, T.PERCENT, T.EOF]),
        ("true false and or not", [T.TRUE, T.FALSE, T.AND, T.OR, T.NOT, T.EOF]),
    ],
)  # fmt: skip
def test_types_des_tokens(source: str, expected: list[TypeToken]) -> None:
    assert types(source) == expected


@pytest.mark.parametrize("word", ["let_x", "else2", "if_", "_if", "binds", "Let"])
def test_un_mot_cle_colle_a_d_autres_caracteres_est_un_identifiant(word: str) -> None:
    assert types(word) == [T.IDENT, T.EOF]


def test_les_identifiants_accentues_sont_permis() -> None:
    tokens = list(tokenize("température été_2"))
    assert [t.lexeme for t in tokens[:2]] == ["température", "été_2"]
    assert all(t.type is T.IDENT for t in tokens[:2])


def test_un_entier_porte_sa_valeur_et_les_zeros_de_tete_sont_permis() -> None:
    token = next(tokenize("007"))
    assert token.type is T.INTEGER
    assert token.value == 7
    assert token.lexeme == "007"


def test_un_nombre_decimal_est_une_erreur_lexicale() -> None:
    with pytest.raises(LexicalError, match="decimal numbers") as error:
        list(tokenize("print 1.5;"))
    assert error.value.position == Position(1, 8)


def test_un_nombre_trop_grand_est_une_erreur_lexicale() -> None:
    with pytest.raises(LexicalError, match="too large"):
        list(tokenize("9" * 5000))


def test_un_texte_porte_sa_valeur_sans_guillemets() -> None:
    token = next(tokenize('"bonjour"'))
    assert token.type is T.TEXT
    assert token.value == "bonjour"
    assert token.lexeme == '"bonjour"'


def test_les_echappements_sont_resolus() -> None:
    token = next(tokenize(r'"a\"b\\c\nd"'))
    assert token.value == 'a"b\\c\nd'


def test_un_echappement_inconnu_est_une_erreur_signalee_sur_l_antislash() -> None:
    with pytest.raises(LexicalError, match="unknown escape") as error:
        list(tokenize(r'"ab\t"'))
    assert error.value.position == Position(1, 4)


@pytest.mark.parametrize("source", ['"ouvert', '"ouvert\nsuite"'])
def test_un_texte_non_ferme_est_signale_a_son_guillemet_ouvrant(source: str) -> None:
    with pytest.raises(LexicalError, match="unclosed text") as error:
        list(tokenize(source))
    assert error.value.position == Position(1, 1)


@pytest.mark.parametrize(("source", "character"), [("a @ b", "@"), ("x ! y", "!"),
                                                    ("$", "$"), ("a . b", ".")])  # fmt: skip
def test_un_caractere_inattendu_est_signale_avec_sa_position(
    source: str, character: str
) -> None:
    with pytest.raises(LexicalError, match="unexpected character") as error:
        list(tokenize(source))
    assert repr(character) in str(error.value)
    assert error.value.position == Position(1, source.index(character) + 1)


def test_les_commentaires_sont_ignores_par_defaut() -> None:
    assert types("a # un commentaire\nb") == [T.IDENT, T.IDENT, T.EOF]


def test_les_commentaires_sont_produits_a_la_demande() -> None:
    tokens = list(tokenize("a # note", comments=True))
    assert [t.type for t in tokens] == [T.IDENT, T.COMMENT, T.EOF]
    assert tokens[1].lexeme == "# note"


def test_les_positions_suivent_les_lignes_et_les_colonnes() -> None:
    tokens = list(tokenize("let a = 1;\n  print a;"))
    assert tokens[0].position == Position(1, 1)
    assert tokens[1].position == Position(1, 5)
    print_stmt = next(t for t in tokens if t.type is T.PRINT)
    assert print_stmt.position == Position(2, 3)
    assert tokens[-1].type is T.EOF
    assert tokens[-1].position == Position(2, 11)  # juste après le dernier ';'


def test_le_lexer_est_paresseux_et_les_tokens_avant_l_erreur_sont_disponibles() -> None:
    stream = tokenize("a b @ c")
    assert next(stream).lexeme == "a"
    assert next(stream).lexeme == "b"
    with pytest.raises(LexicalError):
        next(stream)


def test_les_fins_de_ligne_windows_sont_acceptees() -> None:
    assert types("a\r\nb\r\n") == [T.IDENT, T.IDENT, T.EOF]
