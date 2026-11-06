# Butterfly

A **reactive** programming language, transpiled to Python, with its MCP server.

In Butterfly, you change a single value and everything that depends on it updates by itself: that is the butterfly effect.

```
soit price = 20;
soit quantity = 3;
lie total = price * quantity;     # total is ALWAYS price * quantity

quand total {                    # runs every time total changes
    affiche "nouveau total :", total;
}

quantity = 5;                    # prints: nouveau total : 100
price = price + 5;                 # prints: nouveau total : 125
```

- `soit` ("let") creates a source cell, which can be modified.
- `lie` ("bind") creates a derived cell, always equal to its formula.
- `quand` ("when") creates an observer, run when the value of a cell changes.

The website (guide, reference, examples and an in-browser sandbox): **https://xbkh.github.io/butterfly/**

The full specification is in [`specification.md`](specification.md).

## Installation

You need Python 3.12 or later and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/xbkh/butterfly.git
cd butterfly
uv sync
```

## Usage

```bash
uv run python -m butterfly run exemples/02_cellules.fly       # run
uv run python -m butterfly check programme.fly                # check without running
uv run python -m butterfly transpile programme.fly            # see the generated Python
uv run python -m butterfly format programme.fly               # canonical formatting
uv run python -m butterfly tokens programme.fly               # the tokens
uv run python -m butterfly ast programme.fly                  # the syntax tree
uv run python -m butterfly repl                               # interactive session
```

All errors are reported at once, with the faulty line underlined:

```
Erreur sémantique (ligne 3, colonne 1) : 'b' est une cellule dérivée (lie), on ne peut pas lui affecter de valeur
  3 | b = 2;
    | ^
```

(The language's error messages are in French. Translation: "Semantic error (line 3, column 1): 'b' is a derived cell (lie), a value cannot be assigned to it".)

## MCP server

The server lets an AI that does not know Butterfly learn it on its own: read the specification and the examples, check, fix, run.

| Tool | Role |
|---|---|
| `tokenize` | splits a program into tokens |
| `parse` | returns the syntax tree as JSON |
| `check` | checks without running, all errors at once |
| `transpile` | returns the generated Python |
| `format` | canonical layout |
| `run` | runs in a bounded process (timeout, output, memory) |

It also exposes the resources `butterfly://specification` and `butterfly://exemples`, and the prompts `ecrire_programme` and `corriger_programme`.

To plug it into Claude Code (replace the path):

```bash
claude mcp add butterfly -- uv --directory /absolute/path/to/butterfly run python -m serveur_butterfly
```

An example configuration is in [`mcp.exemple.json`](mcp.exemple.json).

## Tests and quality

```bash
uv run pytest            # 365 tests
uv run mypy butterfly serveur_butterfly tests   # strict typing
uv run ruff check .      # style
```

The specification is executable: a test reads its table of errors and checks that each faulty program produces exactly the announced message.

## Layout

```
butterfly/            the compiler: lexer, parser, semantics, generator, CLI, REPL
serveur_butterfly/    the MCP server and its sandbox
exemples/             five .fly programs and their expected output (.attendu)
specification.md      the language specification
tests/                the language and server tests
site/                 the website (build.py generates the pages from Markdown)
```

The compilation chain is written by hand:

```
text → lexer → tokens → parser → tree → analysis → checked tree → generator → Python
```
