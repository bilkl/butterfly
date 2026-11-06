"""Le runtime : les petites fonctions que le Python généré appelle.

Butterfly n'a pas de types déclarés : ce sont les valeurs qui portent un type, et
ces fonctions vérifient les types **à l'exécution**. Chacune reçoit la ligne du
programme Butterfly d'où vient l'appel, pour que les erreurs d'exécution
indiquent la ligne **du programme d'origine** et non celle du Python généré.

Les fonctions commencent par ``_`` pour ne jamais entrer en conflit avec un nom
de variable du programme (toutes les variables sont préfixées par ``v_``).
"""

from butterfly.errors import ExecutionError


def _type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    return "text"


def _a(value: object) -> str:
    """The type of a value with its article: « an integer », « a text »."""
    name = _type(value)
    return f"an {name}" if name == "integer" else f"a {name}"


def _text(value: object) -> str:
    """How a value is printed: ``true``, ``false``, an integer or a text."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _print(*values: object) -> None:
    print(" ".join(_text(value) for value in values))


# --- Égalité -----------------------------------------------------------------


def _eq(a: object, b: object) -> bool:
    """Deux valeurs de types différents sont toujours différentes
    (en Python, ``True == 1``, mais en Butterfly ``vrai == 1`` est faux)."""
    return type(a) is type(b) and a == b


def _changed(before: object, after: object) -> bool:
    """La valeur d'une cellule a-t-elle changé ? (sert à déclencher ``quand``)"""
    return not _eq(before, after)


# --- Contrôles de type -------------------------------------------------------


def _boolean(value: object, line: int) -> bool:
    if type(value) is not bool:
        raise ExecutionError(f"boolean expected, {_type(value)} found", line)
    return value


def _condition(value: object, line: int) -> bool:
    if type(value) is not bool:
        raise ExecutionError(
            f"the condition of 'if' must be a boolean, not {_a(value)}", line
        )
    return value


def _bound(value: object, line: int) -> int:
    if type(value) is not int:
        raise ExecutionError(
            f"the bounds of 'for' must be integers, not {_a(value)}",
            line,
        )
    return value


def _two_integers(symbol: str, a: object, b: object, line: int) -> tuple[int, int]:
    if type(a) is not int or type(b) is not int:
        raise ExecutionError(
            f"'{symbol}' expects two integers, not {_type(a)} and {_type(b)}", line
        )
    return a, b


# --- Arithmétique ------------------------------------------------------------


def _add(a: object, b: object, line: int) -> int | str:
    if type(a) is int and type(b) is int:
        return a + b
    if type(a) is str and type(b) is str:
        return a + b
    raise ExecutionError(
        f"'+' expects two integers or two texts, not {_type(a)} and {_type(b)}", line
    )


def _sub(a: object, b: object, line: int) -> int:
    x, y = _two_integers("-", a, b, line)
    return x - y


def _mul(a: object, b: object, line: int) -> int:
    x, y = _two_integers("*", a, b, line)
    return x * y


def _div(a: object, b: object, line: int) -> int:
    x, y = _two_integers("/", a, b, line)
    if y == 0:
        raise ExecutionError("division by zero", line)
    return x // y


def _mod(a: object, b: object, line: int) -> int:
    x, y = _two_integers("%", a, b, line)
    if y == 0:
        raise ExecutionError("modulo by zero", line)
    return x % y


def _neg(a: object, line: int) -> int:
    if type(a) is not int:
        raise ExecutionError(f"'-' expects an integer, not {_a(a)}", line)
    return -a


# --- Comparaisons ------------------------------------------------------------


def _comparable(symbol: str, a: object, b: object, line: int) -> None:
    same_types = type(a) is type(b) and type(a) in (int, str)
    if not same_types:
        raise ExecutionError(
            f"'{symbol}' compares two integers or two texts, "
            f"not {_type(a)} and {_type(b)}",
            line,
        )


def _lt(a: int | str, b: int | str, line: int) -> bool:
    _comparable("<", a, b, line)
    return a < b  # type: ignore[operator]


def _le(a: int | str, b: int | str, line: int) -> bool:
    _comparable("<=", a, b, line)
    return a <= b  # type: ignore[operator]


def _gt(a: int | str, b: int | str, line: int) -> bool:
    _comparable(">", a, b, line)
    return a > b  # type: ignore[operator]


def _ge(a: int | str, b: int | str, line: int) -> bool:
    _comparable(">=", a, b, line)
    return a >= b  # type: ignore[operator]


# --- Fonctions prédéfinies ---------------------------------------------------


def _min(a: object, b: object, line: int) -> int:
    x, y = _two_integers("min", a, b, line)
    return min(x, y)


def _max(a: object, b: object, line: int) -> int:
    x, y = _two_integers("max", a, b, line)
    return max(x, y)


def _abs(a: object, line: int) -> int:
    if type(a) is not int:
        raise ExecutionError(f"abs expects an integer, not {_a(a)}", line)
    return abs(a)
