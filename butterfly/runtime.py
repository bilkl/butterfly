"""Le runtime : les petites fonctions que le Python généré appelle.

Butterfly n'a pas de types déclarés : ce sont les valeurs qui portent un type, et
ces fonctions vérifient les types **à l'exécution**. Chacune reçoit la ligne du
programme Butterfly d'où vient l'appel, pour que les erreurs d'exécution
indiquent la ligne **du programme d'origine** et non celle du Python généré.

Les fonctions commencent par ``_`` pour ne jamais entrer en conflit avec un nom
de variable du programme (toutes les variables sont préfixées par ``v_``).
"""

from butterfly.erreurs import ErreurExecution


def _type(valeur: object) -> str:
    if isinstance(valeur, bool):
        return "booléen"
    if isinstance(valeur, int):
        return "entier"
    return "texte"


def _texte(valeur: object) -> str:
    """Comment une valeur s'affiche : ``vrai``, ``faux``, un entier ou un texte."""
    if valeur is True:
        return "vrai"
    if valeur is False:
        return "faux"
    return str(valeur)


def _affiche(*valeurs: object) -> None:
    print(" ".join(_texte(valeur) for valeur in valeurs))


# --- Égalité -----------------------------------------------------------------


def _egal(a: object, b: object) -> bool:
    """Deux valeurs de types différents sont toujours différentes
    (en Python, ``True == 1``, mais en Butterfly ``vrai == 1`` est faux)."""
    return type(a) is type(b) and a == b


def _change(avant: object, apres: object) -> bool:
    """La valeur d'une cellule a-t-elle changé ? (sert à déclencher ``quand``)"""
    return not _egal(avant, apres)


# --- Contrôles de type -------------------------------------------------------


def _booleen(valeur: object, ligne: int) -> bool:
    if type(valeur) is not bool:
        raise ErreurExecution(f"booléen attendu, {_type(valeur)} trouvé", ligne)
    return valeur


def _condition(valeur: object, ligne: int) -> bool:
    if type(valeur) is not bool:
        raise ErreurExecution(
            f"la condition de 'si' doit être un booléen, pas un {_type(valeur)}", ligne
        )
    return valeur


def _borne(valeur: object, ligne: int) -> int:
    if type(valeur) is not int:
        raise ErreurExecution(
            f"les bornes de 'pour' doivent être des entiers, pas un {_type(valeur)}",
            ligne,
        )
    return valeur


def _deux_entiers(symbole: str, a: object, b: object, ligne: int) -> tuple[int, int]:
    if type(a) is not int or type(b) is not int:
        raise ErreurExecution(
            f"'{symbole}' attend deux entiers, pas {_type(a)} et {_type(b)}", ligne
        )
    return a, b


# --- Arithmétique ------------------------------------------------------------


def _plus(a: object, b: object, ligne: int) -> int | str:
    if type(a) is int and type(b) is int:
        return a + b
    if type(a) is str and type(b) is str:
        return a + b
    raise ErreurExecution(
        f"'+' attend deux entiers ou deux textes, pas {_type(a)} et {_type(b)}", ligne
    )


def _moins(a: object, b: object, ligne: int) -> int:
    x, y = _deux_entiers("-", a, b, ligne)
    return x - y


def _fois(a: object, b: object, ligne: int) -> int:
    x, y = _deux_entiers("*", a, b, ligne)
    return x * y


def _divise(a: object, b: object, ligne: int) -> int:
    x, y = _deux_entiers("/", a, b, ligne)
    if y == 0:
        raise ErreurExecution("division par zéro", ligne)
    return x // y


def _reste(a: object, b: object, ligne: int) -> int:
    x, y = _deux_entiers("%", a, b, ligne)
    if y == 0:
        raise ErreurExecution("modulo par zéro", ligne)
    return x % y


def _neg(a: object, ligne: int) -> int:
    if type(a) is not int:
        raise ErreurExecution(f"'-' attend un entier, pas un {_type(a)}", ligne)
    return -a


# --- Comparaisons ------------------------------------------------------------


def _comparable(symbole: str, a: object, b: object, ligne: int) -> None:
    memes_types = type(a) is type(b) and type(a) in (int, str)
    if not memes_types:
        raise ErreurExecution(
            f"'{symbole}' compare deux entiers ou deux textes, "
            f"pas {_type(a)} et {_type(b)}",
            ligne,
        )


def _inf(a: int | str, b: int | str, ligne: int) -> bool:
    _comparable("<", a, b, ligne)
    return a < b  # type: ignore[operator]


def _inf_egal(a: int | str, b: int | str, ligne: int) -> bool:
    _comparable("<=", a, b, ligne)
    return a <= b  # type: ignore[operator]


def _sup(a: int | str, b: int | str, ligne: int) -> bool:
    _comparable(">", a, b, ligne)
    return a > b  # type: ignore[operator]


def _sup_egal(a: int | str, b: int | str, ligne: int) -> bool:
    _comparable(">=", a, b, ligne)
    return a >= b  # type: ignore[operator]


# --- Fonctions prédéfinies ---------------------------------------------------


def _min(a: object, b: object, ligne: int) -> int:
    x, y = _deux_entiers("min", a, b, ligne)
    return min(x, y)


def _max(a: object, b: object, ligne: int) -> int:
    x, y = _deux_entiers("max", a, b, ligne)
    return max(x, y)


def _abs(a: object, ligne: int) -> int:
    if type(a) is not int:
        raise ErreurExecution(f"abs attend un entier, pas un {_type(a)}", ligne)
    return abs(a)
