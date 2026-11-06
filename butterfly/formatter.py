"""Le formateur : réécrit un programme Butterfly dans une présentation canonique.

C'est un second « backend » : au lieu de produire du Python, il reproduit du
Butterfly, avec quatre espaces d'indentation, un espace autour des opérateurs et
seulement les parenthèses nécessaires. Il conserve les commentaires et une ligne
vide entre deux blocs d'instructions, et il est **idempotent** : formater un
programme déjà formaté ne change rien.
"""

from collections import deque

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
from butterfly.parser import Parser, list_tokens
from butterfly.tokens import Token, TypeToken

INDENTATION = "    "

#: Priorité de chaque opérateur, pour savoir quand une parenthèse est nécessaire.
PRIORITY = {
    "or": 1,
    "and": 2,
    "not": 3,
    "==": 4, "!=": 4, "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5,
    "*": 6, "/": 6, "%": 6,
}  # fmt: skip
PRIORITY_UNARY = 7
PRIORITY_PRIMARY = 8


def priority(expression: Expression) -> int:
    match expression:
        case Binary(operator=operator):
            return PRIORITY[operator]
        case Unary(operator="not"):
            return PRIORITY["not"]
        case Unary():
            return PRIORITY_UNARY
        case _:
            return PRIORITY_PRIMARY


def butterfly_text(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def render_expression(expression: Expression) -> str:
    """L'expression en texte, avec les parenthèses strictement nécessaires."""
    match expression:
        case Integer(value=value):
            return str(value)
        case Text(value=value):
            return butterfly_text(value)
        case Boolean(value=value):
            return "true" if value else "false"
        case Name(name=name):
            return name
        case Call(name=name, arguments=arguments):
            return f"{name}({', '.join(render_expression(a) for a in arguments)})"
        case Unary(operator="not", operand=operand):
            inner = render_expression(operand)
            # `non a == b` serait correct, mais `non (a == b)` se lit sans effort :
            # on garde les parenthèses autour de tout opérande binaire.
            if isinstance(operand, Binary):
                inner = f"({inner})"
            return f"not {inner}"
        case Unary(operand=operand):
            inner = render_expression(operand)
            if priority(operand) < PRIORITY_PRIMARY:
                inner = f"({inner})"
            return f"-{inner}"
        case Binary(operator=operator, left=left, right=right):
            p = PRIORITY[operator]
            comparison = p == 4
            left_text = render_expression(left)
            right_text = render_expression(right)
            # À gauche : les opérateurs de même priorité s'enchaînent (associativité
            # à gauche), sauf les comparaisons qui ne s'enchaînent jamais.
            if priority(left) < p or (comparison and priority(left) == p):
                left_text = f"({left_text})"
            # À droite : même priorité = parenthèses (a - (b - c)).
            if priority(right) <= p:
                right_text = f"({right_text})"
            # `non` ne peut pas être l'opérande direct d'un opérateur plus fort.
            return f"{left_text} {operator} {right_text}"
    raise AssertionError(f"expression inconnue : {expression!r}")


class Formatter:
    """Écrit un programme ligne par ligne, en replaçant les commentaires."""

    def __init__(self, source: str, program: Program, comments: list[Token]):
        self.source_lines = source.splitlines()
        self.program = program
        self.comments: deque[Token] = deque(
            sorted(comments, key=lambda t: t.position.line)
        )
        self.output: list[str] = []
        self.first = True  # premier élément du bloc courant ?

    # --- Lignes, commentaires et lignes vides -------------------------------

    def _at_end_of_line(self, comment: Token) -> bool:
        """Le commentaire suit-il du code sur sa ligne ?"""
        line = self.source_lines[comment.position.line - 1]
        return line[: comment.position.column - 1].strip() != ""

    def _blank_before(self, line: int) -> None:
        """Conserve (une seule) ligne vide si le source en avait une avant."""
        if not self.first and line >= 2 and self.source_lines[line - 2].strip() == "":
            self.output.append("")

    def _comment_only(self, indentation: int) -> None:
        comment = self.comments.popleft()
        self._blank_before(comment.position.line)
        self.output.append(INDENTATION * indentation + comment.lexeme.rstrip())
        self.first = False

    def _comments_before(self, line: int, indentation: int) -> None:
        while self.comments and self.comments[0].position.line < line:
            self._comment_only(indentation)

    def _start(self, line: int, indentation: int) -> None:
        """À appeler avant chaque instruction : commentaires et ligne vide."""
        self._comments_before(line, indentation)
        self._blank_before(line)

    def _line(self, indentation: int, text: str, source_line: int) -> None:
        suffix = ""
        if (
            self.comments
            and self.comments[0].position.line == source_line
            and self._at_end_of_line(self.comments[0])
        ):
            suffix = "  " + self.comments.popleft().lexeme.rstrip()
        self.output.append(INDENTATION * indentation + text + suffix)
        self.first = False

    # --- Programme et instructions ------------------------------------------

    def render(self) -> str:
        for statement in self.program.statements:
            self.statement(statement, 0)
        while self.comments:
            self._comment_only(0)
        return "\n".join(self.output) + "\n" if self.output else ""

    def body(self, block: Block, indentation: int) -> None:
        """Les instructions d'un bloc, et les commentaires avant son ``}``."""
        self.first = True
        for statement in block.statements:
            self.statement(statement, indentation)
        self._comments_before(block.end.line, indentation)

    def statement(
        self, statement: Statement | TopLevelStatement, indentation: int
    ) -> None:
        line = statement.position.line
        self._start(line, indentation)
        match statement:
            case Declaration(name=name, value=value):
                self._line(
                    indentation, f"let {name} = {render_expression(value)};", line
                )
            case Binding(name=name, value=value):
                self._line(
                    indentation, f"bind {name} = {render_expression(value)};", line
                )
            case Assignment(name=name, value=value):
                self._line(indentation, f"{name} = {render_expression(value)};", line)
            case Print(values=values):
                items_list = ", ".join(render_expression(v) for v in values)
                self._line(indentation, f"print {items_list};", line)
            case Observer(target=target, body=body):
                self._line(indentation, f"when {target} {{", line)
                self.body(body, indentation + 1)
                self._line(indentation, "}", body.end.line)
            case For() as for_stmt:
                start = render_expression(for_stmt.start)
                end = render_expression(for_stmt.end)
                self._line(
                    indentation, f"for {for_stmt.variable} in {start}..{end} {{", line
                )
                self.body(for_stmt.body, indentation + 1)
                self._line(indentation, "}", for_stmt.body.end.line)
            case If() as if_stmt:
                self.if_stmt(if_stmt, indentation, "if")

    def if_stmt(self, if_stmt: If, indentation: int, word: str) -> None:
        condition = render_expression(if_stmt.condition)
        self._line(indentation, f"{word} {condition} {{", if_stmt.position.line)
        self.body(if_stmt.then_block, indentation + 1)
        rest = if_stmt.else_branch
        closing_line = if_stmt.then_block.end.line
        if isinstance(rest, If):
            # Le « } » fermant est fusionné avec le « sinon si » suivant.
            self.if_stmt(rest, indentation, "} else if")
        elif isinstance(rest, Block):
            self._line(indentation, "} else {", closing_line)
            self.body(rest, indentation + 1)
            self._line(indentation, "}", rest.end.line)
        else:
            self._line(indentation, "}", closing_line)


def format_program(source: str, program: Program, comments: list[Token]) -> str:
    return Formatter(source, program, comments).render()


def format_source(source: str) -> str:
    """Le programme ``source``, réécrit dans sa présentation canonique.

    Lève ``ErreurCompilation`` si le programme a des erreurs de syntaxe : on ne
    formate pas un programme qu'on ne comprend pas. (L'analyse sémantique n'est
    pas nécessaire.)
    """
    tokens = list_tokens(source, comments=True)
    program = Parser(tokens).program()
    comments = [t for t in tokens if t.type is TypeToken.COMMENT]
    return format_program(source, program, comments)
