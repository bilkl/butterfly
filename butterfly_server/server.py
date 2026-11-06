"""The Butterfly MCP server.

It gives an AI that does not know Butterfly the means to learn it on its own:
read its specification and examples (resources); tokenize, parse, check,
transpile, format and run a program (tools); and follow a method (prompts).
The tools reimplement nothing: they call the language facade
(``butterfly.compiler``) and convert the result.

No ``from __future__ import annotations`` here: the SDK inspects the
annotations at run time to build the tool schemas.
"""

import time
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from mcp_types import ToolAnnotations
from pydantic import Field

from butterfly.compiler import analyze_program, check, parser, transpile
from butterfly.errors import CompilationError, LexicalError
from butterfly.formatter import format_source
from butterfly.lexer import tokenize
from butterfly.nodes import node_to_dict
from butterfly_server.conversion import (
    cells_json,
    error_json,
    errors_json,
    token_json,
)
from butterfly_server.sandbox import execute_isolated, read_execution_error
from butterfly_server.schemas import (
    CheckResult,
    ErrorJSON,
    FormatResult,
    ParseResult,
    RunResult,
    Status,
    TokenizeResult,
    TokenJSON,
    TranspileResult,
)

ROOT = Path(__file__).resolve().parent.parent
SPECIFICATION = ROOT / "specification.md"
EXAMPLES = ROOT / "examples"

INSTRUCTIONS = """\
This server gives you access to Butterfly, a reactive programming language you do \
not know yet (.fly files). In Butterfly, a derived cell (`bind`) is always equal to \
its formula: when a source cell (`let`) changes, everything that depends on it \
updates by itself.

Proceed as follows:
1. Read the resource `butterfly://specification`: lexicon, grammar, priorities, \
semantics. Then read at least one example (the list is in `butterfly://examples`).
2. Write your program.
3. Call `check`: it returns ALL the errors at once, each with its line, its column \
and the faulty line underlined. Fix them and start again until `ok`.
4. Call `run` and compare the output with what you expected.
5. Finish with `format` to get the canonical layout.

Tools: `tokenize` (the words), `parse` (the tree), `check` (checks without running), \
`transpile` (the generated Python), `format`, `run` (runs, in a bounded process). \
An error in YOUR program is a normal answer (`ok: false`), not a failure of the \
tool.\
"""

mcp = MCPServer("butterfly", instructions=INSTRUCTIONS)

READ_ONLY = ToolAnnotations(
    read_only_hint=True, idempotent_hint=True, open_world_hint=False
)

Source = Annotated[str, Field(description="Source code of a Butterfly program (.fly)")]


# --- Analysis tools -----------------------------------------------------------


@mcp.tool(name="tokenize", annotations=READ_ONLY)
def tokenize_tool(source: Source) -> TokenizeResult:
    """Splits a Butterfly program into tokens (keywords, names, numbers, symbols),
    with their line and column. On a lexical error (unknown character, unclosed
    text, decimal number), returns the tokens read before the error."""
    tokens: list[TokenJSON] = []
    try:
        for token in tokenize(source):
            tokens.append(token_json(token))
    except LexicalError as error:
        return {"ok": False, "tokens": tokens, "errors": [error_json(error, source)]}
    return {"ok": True, "tokens": tokens, "errors": []}


@mcp.tool(name="parse", annotations=READ_ONLY)
def parse_tool(source: Source) -> ParseResult:
    """Parses the SYNTAX of a Butterfly program and returns its syntax tree as
    JSON (each node has a "type" key). Does not do the semantic analysis: an
    undeclared name is not detected here, use `check` for that. Reports all the
    syntax errors found."""
    try:
        program = parser(source)
    except CompilationError as error:
        return {
            "ok": False,
            "tree": None,
            "errors": errors_json(error.errors, source),
        }
    return {"ok": True, "tree": node_to_dict(program), "errors": []}


@mcp.tool(name="check", annotations=READ_ONLY)
def check_tool(source: Source) -> CheckResult:
    """Checks a Butterfly program WITHOUT running it: syntax, names declared before
    use, derived cells not modified, function calls. Returns all the errors at once
    (kind, message, line, column, faulty line underlined). If all is well, also
    returns the cells of the program."""
    try:
        analysis = analyze_program(source)
    except CompilationError as error:
        return {
            "ok": False,
            "errors": errors_json(error.errors, source),
            "cells": [],
        }
    return {"ok": True, "errors": [], "cells": cells_json(analysis)}


# --- Transformation tools -----------------------------------------------------


@mcp.tool(name="transpile", annotations=READ_ONLY)
def transpile_tool(source: Source) -> TranspileResult:
    """Translates a Butterfly program to Python (the code can be run with the
    `butterfly` package). Useful to understand how derived cells and observers are
    propagated. Returns the errors if the program is wrong."""
    try:
        return {"ok": True, "python": transpile(source), "errors": []}
    except CompilationError as error:
        return {
            "ok": False,
            "python": None,
            "errors": errors_json(error.errors, source),
        }


@mcp.tool(name="format", annotations=READ_ONLY)
def format_tool(source: Source) -> FormatResult:
    """Rewrites a Butterfly program in its canonical layout (4-space indentation,
    minimal parentheses, comments kept). The result gives the same output as the
    original. Needs only correct syntax."""
    try:
        return {"ok": True, "source": format_source(source), "errors": []}
    except CompilationError as error:
        return {
            "ok": False,
            "source": None,
            "errors": errors_json(error.errors, source),
        }


# --- The run tool -------------------------------------------------------------


@mcp.tool(
    name="run",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def run_tool(
    source: Source,
    time_limit: Annotated[
        float,
        Field(ge=0.1, le=5.0, description="Maximum run time, in seconds"),
    ] = 2.0,
) -> RunResult:
    """Runs a Butterfly program and returns what it prints. The program is first
    checked (compilation errors are reported without running), then run in a
    separate process, limited in time, output (64 KiB) and memory. Statuses: ok,
    compilation_error, execution_error (with the line), timeout, output_truncated,
    memory_exceeded, internal_error. What was printed before a runtime error is kept
    in `output`."""
    start = time.monotonic()
    errors = check(source)
    if errors:
        return _run_response(
            "compilation_error", "", errors_json(errors, source), start
        )
    isolated = execute_isolated(source, time_limit)
    status: Status = isolated.status
    run_errors: list[ErrorJSON] = []
    if status == "execution_error":
        found_one = read_execution_error(isolated.error)
        if found_one is not None:
            line, message = found_one
            run_errors.append(
                {
                    "kind": "Runtime error",
                    "message": message,
                    "line": line,
                    "column": None,
                    "context": isolated.error.strip(),
                }
            )
    elif status == "internal_error":
        run_errors.append(
            {
                "kind": "Internal error",
                "message": "the run failed without an identifiable Butterfly error",
                "line": None,
                "column": None,
                "context": isolated.error.strip()[-2000:],
            }
        )
    return _run_response(status, isolated.output, run_errors, start)


def _run_response(
    status: Status, output: str, errors: list[ErrorJSON], start: float
) -> RunResult:
    return {
        "status": status,
        "output": output,
        "errors": errors,
        "duration_seconds": round(time.monotonic() - start, 3),
    }


# --- Resources ----------------------------------------------------------------


def available_examples() -> dict[str, Path]:
    """The CLOSED list of examples: name → file. A name received from the AI is
    never used to build a path, only looked up in this list."""
    return {file_path.stem: file_path for file_path in sorted(EXAMPLES.glob("*.fly"))}


def _example(name: str) -> Path:
    file_path = available_examples().get(name)
    if file_path is None:
        raise ResourceNotFoundError(f"unknown example: {name!r}")
    return file_path


def _description(file_path: Path) -> str:
    """The first comment line of the program, without the "#"."""
    for line in file_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


@mcp.resource(
    "butterfly://specification",
    name="specification",
    description=(
        "Full specification of Butterfly: lexicon, EBNF grammar, operator priorities, "
        "semantics (cells, propagation, observers), errors. Read it first."
    ),
    mime_type="text/markdown",
)
def specification() -> str:
    return SPECIFICATION.read_text(encoding="utf-8")


@mcp.resource(
    "butterfly://examples",
    name="examples_index",
    description="The list of example programs, with their URI and description.",
    mime_type="text/markdown",
)
def examples_index() -> str:
    lines = ["# Butterfly example programs", ""]
    for name, file_path in available_examples().items():
        lines.append(
            f"- `{name}`: {_description(file_path)}\n"
            f"  - program: `butterfly://examples/{name}`\n"
            f"  - expected output: `butterfly://examples/{name}/expected`"
        )
    return "\n".join(lines) + "\n"


@mcp.resource(
    "butterfly://examples/{name}",
    name="example",
    description="Source code of an example program (see butterfly://examples).",
    mime_type="text/plain",
)
def example(name: str) -> str:
    return _example(name).read_text(encoding="utf-8")


@mcp.resource(
    "butterfly://examples/{name}/expected",
    name="expected_example",
    description="The exact output of an example program.",
    mime_type="text/plain",
)
def expected_example(name: str) -> str:
    return _example(name).with_suffix(".expected").read_text(encoding="utf-8")


# --- Prompts ------------------------------------------------------------------


@mcp.prompt(
    name="write_program",
    description=("Write, check and run a Butterfly program for a given task."),
)
def write_program(
    task: Annotated[str, Field(description="What the program must do")],
) -> str:
    return f"""\
Write a program in the Butterfly language that does the following task:

{task}

You do not know Butterfly. Proceed as follows:
1. Read the resource butterfly://specification, then at least one example (the list
   is in butterfly://examples).
2. Write the program. Reminder: `let` creates a modifiable cell, `bind` a cell always
   equal to its formula, `when` an observer; names are declared before use.
3. Call the `check` tool. If it reports errors, fix them (each gives its line and
   column) and start again until `ok`.
4. Call the `run` tool, and compare the output with what you expected. If it differs,
   explain why and fix it.
5. Finish with `format`, then give the final program and its output.
"""


@mcp.prompt(
    name="fix_program",
    description="Fix a Butterfly program from the reported errors.",
)
def fix_program(
    source: Annotated[str, Field(description="The program to fix")],
    errors: Annotated[
        str, Field(description="The reported errors (message from check or run)")
    ],
) -> str:
    return f"""\
This Butterfly program contains errors:

```
{source}
```

Reported errors:

```
{errors}
```

Fix it. If you doubt a rule of the language, consult the resource
butterfly://specification. Check your fix with the `check` tool (until `ok`),
then run it with `run`. Explain each fix in one sentence.
"""
