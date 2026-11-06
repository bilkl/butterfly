"""Le parser : transforme les tokens en arbre syntaxique.

- Les **instructions** sont analysées par descente récursive : une méthode par
  règle de la grammaire.
- Les **expressions** sont analysées par un parser de Pratt : une table donne la
  priorité de chaque opérateur, et ajouter un opérateur revient à ajouter une
  ligne dans la table.
- Le parser **ne s'arrête pas à la première erreur** : il la note, se
  resynchronise sur l'instruction suivante, et signale toutes les erreurs en une
  seule fois.
"""

from collections.abc import Callable

from butterfly.errors import (
    ButterflyError,
    CompilationError,
    LexicalError,
    ParseError,
    Position,
)
from butterfly.lexer import tokenize
from butterfly.nodes import (
    Assignment,
    Binary,
    Binding,
    Block,
    Boolean,
    Call,
    Declaration,
    Expression,
    For,
    If,
    Integer,
    Name,
    Observer,
    Print,
    Program,
    Statement,
    Text,
    TopLevelStatement,
    Unary,
)
from butterfly.tokens import Token, TypeToken

T = TypeToken

#: Priorité de chaque opérateur binaire (plus grand = plus prioritaire).
PRIORITIES: dict[TypeToken, tuple[int, str]] = {
    T.OR: (10, "or"),
    T.AND: (20, "and"),
    T.EQ_EQ: (40, "=="),
    T.NOT_EQ: (40, "!="),
    T.LT: (40, "<"),
    T.LT_EQ: (40, "<="),
    T.GT: (40, ">"),
    T.GT_EQ: (40, ">="),
    T.PLUS: (50, "+"),
    T.MINUS: (50, "-"),
    T.STAR: (60, "*"),
    T.SLASH: (60, "/"),
    T.PERCENT: (60, "%"),
}
PRIORITY_NOT = 30
PRIORITY_COMPARISON = 40
PRIORITY_UNARY_MINUS = 70
COMPARATORS = frozenset(t for t, (p, _) in PRIORITIES.items() if p == 40)

#: Les mots-clés qui commencent une instruction : points de resynchronisation.
STATEMENT_STARTS = frozenset({T.LET, T.BIND, T.WHEN, T.IF, T.FOR, T.PRINT})


class Parser:
    """Un parser sur une liste de tokens (les commentaires sont ignorés)."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = [t for t in tokens if t.type is not T.COMMENT]
        self.i = 0
        self.errors: list[ButterflyError] = []

    # --- Outils -------------------------------------------------------------

    def current(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> Token:
        token = self.tokens[self.i]
        if token.type is not T.EOF:
            self.i += 1
        return token

    def check(self, *types: TypeToken) -> bool:
        return self.current().type in types

    @staticmethod
    def describe(token: Token) -> str:
        return "end of program" if token.type is T.EOF else f"'{token.lexeme}'"

    def error(self, message: str, position: Position | None = None) -> ParseError:
        return ParseError(message, position or self.current().position)

    def consume(self, expected_type: TypeToken, expected: str) -> Token:
        if self.check(expected_type):
            return self.advance()
        raise self.error(f"{expected} expected, {self.describe(self.current())} found")

    def semicolon(self) -> None:
        """Consomme le ``;`` final. S'il manque, l'erreur est signalée **juste
        après** le dernier token de l'instruction, là où il aurait dû être."""
        if self.check(T.SEMICOLON):
            self.advance()
            return
        previous = self.tokens[self.i - 1]
        end = Position(
            previous.position.line,
            previous.position.column + len(previous.lexeme),
        )
        raise self.error(
            "';' expected at the end of the statement, "
            f"{self.describe(self.current())} found",
            end,
        )

    # --- Récupération d'erreurs ---------------------------------------------

    def _with_recovery[R](self, analysis: Callable[[], R]) -> R | None:
        """Lance ``analyse`` ; en cas d'erreur, la note et se resynchronise."""
        start = self.i
        try:
            return analysis()
        except ParseError as error:
            self.errors.append(error)
            self._resynchronize(start)
            return None

    def _resynchronize(self, start: int) -> None:
        """Saute les tokens jusqu'au début de l'instruction suivante."""
        if self.i == start:  # garantit qu'on avance toujours
            self.advance()
        while not self.check(T.EOF):
            current_type = self.current().type
            if current_type is T.SEMICOLON:
                self.advance()
                return
            if current_type is T.RBRACE or current_type in STATEMENT_STARTS:
                return
            self.advance()

    # --- Programme et instructions ------------------------------------------

    def program(self) -> Program:
        statements: list[TopLevelStatement] = []
        while not self.check(T.EOF):
            statement = self._with_recovery(self.top_level_statement)
            if statement is not None:
                statements.append(statement)
        if self.errors:
            raise CompilationError(tuple(self.errors))
        return Program(tuple(statements))

    def top_level_statement(self) -> TopLevelStatement:
        """Au niveau supérieur, ``lie`` et ``quand`` sont permis."""
        if self.check(T.BIND):
            return self.binding()
        if self.check(T.WHEN):
            return self.observer()
        return self.statement()

    def statement(self) -> Statement:
        token = self.current()
        match token.type:
            case T.LET:
                return self.declaration()
            case T.IF:
                return self.if_stmt()
            case T.FOR:
                return self.for_stmt()
            case T.PRINT:
                return self.print_stmt()
            case T.IDENT:
                return self.assignment()
            case T.BIND | T.WHEN:
                raise self.error(f"'{token.lexeme}' is only allowed at top level")
            case _:
                raise self.error(f"statement expected, {self.describe(token)} found")

    def declaration(self) -> Declaration:
        word = self.advance()
        name = self.consume(T.IDENT, "name")
        self.consume(T.EQ, "'='")
        value = self.expression()
        self.semicolon()
        return Declaration(name.lexeme, value, word.position, name.position)

    def binding(self) -> Binding:
        word = self.advance()
        name = self.consume(T.IDENT, "name")
        self.consume(T.EQ, "'='")
        value = self.expression()
        self.semicolon()
        return Binding(name.lexeme, value, word.position, name.position)

    def observer(self) -> Observer:
        word = self.advance()
        target = self.consume(T.IDENT, "cell name")
        body = self.block()
        return Observer(target.lexeme, body, word.position, target.position)

    def assignment(self) -> Assignment:
        name = self.advance()
        if not self.check(T.EQ):
            raise self.error(
                f"'=' expected after {self.describe(name)}, "
                f"{self.describe(self.current())} found"
            )
        self.advance()
        value = self.expression()
        self.semicolon()
        return Assignment(name.lexeme, value, name.position)

    def if_stmt(self) -> If:
        word = self.advance()
        condition = self.expression()
        then_block = self.block()
        else_branch: If | Block | None = None
        if self.check(T.ELSE):
            self.advance()
            else_branch = self.if_stmt() if self.check(T.IF) else self.block()
        return If(condition, then_block, else_branch, word.position)

    def for_stmt(self) -> For:
        word = self.advance()
        variable = self.consume(T.IDENT, "variable name")
        self.consume(T.IN, "'in'")
        start = self.expression()
        self.consume(T.DOT_DOT, "'..'")
        end = self.expression()
        body = self.block()
        return For(variable.lexeme, start, end, body, word.position, variable.position)

    def print_stmt(self) -> Print:
        word = self.advance()
        values = [self.expression()]
        while self.check(T.COMMA):
            self.advance()
            values.append(self.expression())
        self.semicolon()
        return Print(tuple(values), word.position)

    def block(self) -> Block:
        opening = self.consume(T.LBRACE, "'{'")
        statements: list[Statement] = []
        while not self.check(T.RBRACE, T.EOF):
            statement = self._with_recovery(self.statement)
            if statement is not None:
                statements.append(statement)
        closing = self.consume(T.RBRACE, "'}'")
        return Block(tuple(statements), opening.position, closing.position)

    # --- Expressions (parser de Pratt) --------------------------------------

    def expression(self, min_priority: int = 0) -> Expression:
        """Analyse une expression, en ne consommant que les opérateurs dont la
        priorité est au moins ``priorite_min``."""
        left = self.prefix_expression(min_priority)
        while True:
            operator = self.current()
            info = PRIORITIES.get(operator.type)
            if info is None or info[0] < min_priority:
                return left
            priority, symbol = info
            self.advance()
            # Associativité à gauche : l'opérande de droite ne peut contenir que
            # des opérateurs *strictement* plus prioritaires.
            right = self.expression(priority + 1)
            left = Binary(symbol, left, right, operator.position)
            if priority == PRIORITY_COMPARISON and self.check(*COMPARATORS):
                raise self.error("comparisons do not chain, use 'and'")

    def prefix_expression(self, min_priority: int) -> Expression:
        token = self.current()
        if token.type is T.MINUS:
            self.advance()
            operand = self.expression(PRIORITY_UNARY_MINUS)
            return Unary("-", operand, token.position)
        if token.type is T.NOT:
            if min_priority > PRIORITY_NOT:
                raise self.error("'not' must be in parentheses here")
            self.advance()
            return Unary("not", self.expression(PRIORITY_NOT), token.position)
        return self.primary()

    def primary(self) -> Expression:
        token = self.current()
        match token.type:
            case T.INTEGER:
                self.advance()
                assert isinstance(token.value, int)
                return Integer(token.value, token.position)
            case T.TEXT:
                self.advance()
                assert isinstance(token.value, str)
                return Text(token.value, token.position)
            case T.TRUE | T.FALSE:
                self.advance()
                return Boolean(token.type is T.TRUE, token.position)
            case T.IDENT:
                self.advance()
                if self.check(T.LPAREN):
                    return self.call(token)
                return Name(token.lexeme, token.position)
            case T.LPAREN:
                self.advance()
                inner = self.expression()
                self.consume(T.RPAREN, "')'")
                return inner
            case _:
                raise self.error(f"expression expected, {self.describe(token)} found")

    def call(self, name: Token) -> Call:
        self.advance()  # la parenthèse ouvrante
        arguments: list[Expression] = []
        if not self.check(T.RPAREN):
            arguments.append(self.expression())
            while self.check(T.COMMA):
                self.advance()
                arguments.append(self.expression())
        self.consume(T.RPAREN, "')'")
        return Call(name.lexeme, tuple(arguments), name.position)


def list_tokens(source: str, *, comments: bool = False) -> list[Token]:
    """Tous les tokens de ``source`` ; une erreur lexicale devient une
    ``ErreurCompilation``."""
    try:
        return list(tokenize(source, comments=comments))
    except LexicalError as error:
        raise CompilationError((error,)) from error


def analyze_syntax(source: str) -> Program:
    """Le texte source devient un arbre, ou lève ``ErreurCompilation``."""
    return Parser(list_tokens(source)).program()
