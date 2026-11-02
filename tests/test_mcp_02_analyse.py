"""MCP, étape 2 : les outils d'analyse (tokenize, parse, check).

Une erreur dans le programme analysé est une réponse **normale** (`ok: false`) :
l'outil a fait son travail en la trouvant. `is_error` est réservé aux cas où
l'outil lui-même n'a pas pu travailler.
"""

from typing import Any

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio


async def appeler(client: Client, outil: str, source: str) -> dict[str, Any]:
    resultat = await client.call_tool(outil, {"source": source})
    assert not resultat.is_error, resultat.content
    assert resultat.structured_content is not None
    return dict(resultat.structured_content)


# --- tokenize --------------------------------------------------------------------------


async def test_tokenize_renvoie_les_tokens_avec_leur_position(client: Client) -> None:
    reponse = await appeler(client, "tokenize", "soit a = 1;")
    assert reponse["ok"] is True
    types = [t["type"] for t in reponse["tokens"]]
    assert types == ["SOIT", "IDENT", "EGAL", "ENTIER", "POINT_VIRGULE", "FIN"]
    assert reponse["tokens"][1] == {
        "type": "IDENT",
        "lexeme": "a",
        "ligne": 1,
        "colonne": 6,
    }


async def test_tokenize_renvoie_les_tokens_lus_avant_une_erreur_lexicale(
    client: Client,
) -> None:
    reponse = await appeler(client, "tokenize", "soit a @ 1;")
    assert reponse["ok"] is False
    assert [t["lexeme"] for t in reponse["tokens"]] == ["soit", "a"]
    erreur = reponse["erreurs"][0]
    assert (erreur["genre"], erreur["ligne"], erreur["colonne"]) == (
        "Erreur lexicale",
        1,
        8,
    )


# --- parse -----------------------------------------------------------------------------


async def test_parse_renvoie_l_arbre_avec_le_type_de_chaque_noeud(
    client: Client,
) -> None:
    reponse = await appeler(client, "parse", "soit a = 1 + 2;")
    assert reponse["ok"] is True
    declaration = reponse["arbre"]["instructions"][0]
    assert declaration["type"] == "Declaration"
    assert declaration["valeur"]["type"] == "Binaire"
    assert declaration["valeur"]["operateur"] == "+"
    assert (declaration["ligne"], declaration["colonne"]) == (1, 1)


async def test_parse_signale_toutes_les_erreurs_de_syntaxe(client: Client) -> None:
    reponse = await appeler(client, "parse", "soit a = ;\nsoit b = 2\naffiche 3;")
    assert reponse["ok"] is False
    assert reponse["arbre"] is None
    assert [e["ligne"] for e in reponse["erreurs"]] == [1, 2]
    assert all(e["genre"] == "Erreur de syntaxe" for e in reponse["erreurs"])


async def test_parse_ne_fait_pas_l_analyse_semantique(client: Client) -> None:
    assert (await appeler(client, "parse", "affiche inconnu;"))["ok"] is True


# --- check -----------------------------------------------------------------------------


async def test_check_d_un_programme_correct_decrit_ses_cellules(client: Client) -> None:
    reponse = await appeler(
        client,
        "check",
        "soit a = 1; soit b = 2; lie c = a + b; si vrai { soit t = 0; }",
    )
    assert reponse["ok"] is True
    assert reponse["erreurs"] == []
    assert reponse["cellules"] == [
        {"nom": "a", "genre": "source", "depend_de": []},
        {"nom": "b", "genre": "source", "depend_de": []},
        {"nom": "c", "genre": "derivee", "depend_de": ["a", "b"]},
    ]


async def test_check_signale_les_erreurs_semantiques_avec_leur_contexte(
    client: Client,
) -> None:
    reponse = await appeler(
        client, "check", "soit a = 1;\nlie b = a;\nb = 2;\naffiche c;"
    )
    assert reponse["ok"] is False
    premiere, seconde = reponse["erreurs"]
    assert premiere["genre"] == "Erreur sémantique"
    assert (premiere["ligne"], premiere["colonne"]) == (3, 1)
    assert "cellule dérivée" in premiere["message"]
    assert "3 | b = 2;" in premiere["contexte"]
    assert "^" in premiere["contexte"]
    assert seconde["message"] == "nom 'c' non déclaré"


async def test_check_signale_une_erreur_lexicale(client: Client) -> None:
    reponse = await appeler(client, "check", "affiche 1.5;")
    assert reponse["ok"] is False
    assert reponse["erreurs"][0]["genre"] == "Erreur lexicale"


async def test_une_erreur_du_programme_n_est_pas_une_erreur_de_l_outil(
    client: Client,
) -> None:
    resultat = await client.call_tool("check", {"source": "affiche ;"})
    assert resultat.is_error is False
    assert resultat.structured_content is not None
    assert resultat.structured_content["ok"] is False
