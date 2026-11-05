# User guide

This guide explains how to install Butterfly, run a program and use the tools that come with it. To learn the language itself, see [The language](langage.html).

## Install

You need Python 3.12 or later and [uv](https://docs.astral.sh/uv/), which manages the environment and the dependencies.

```bash
git clone https://github.com/xbkh/butterfly.git
cd butterfly
uv sync
```

Check the installation:

```bash
uv run python -m butterfly --version
```

If you would rather install nothing, the [sandbox](playground.html) runs Butterfly in your browser.

## Your first program

Write this in a file named `bonjour.fly` ("hello"):

```fly run
soit nom = "monde";
affiche "Bonjour,", nom;
```

Then run it:

```bash
uv run python -m butterfly run bonjour.fly
```

## The commands

Every command takes a `.fly` file, or `-` to read the program from standard input.

| Command | What it does |
|---|---|
| `run` | runs the program |
| `check` | checks the program without running it, and reports all the errors |
| `transpile` | prints the generated Python code |
| `format` | prints the program in its canonical layout (`-w` rewrites the file) |
| `tokens` | prints the tokens, with their position |
| `ast` | prints the syntax tree |
| `repl` | opens an interactive session |

For example, to reformat a file in place:

```bash
uv run python -m butterfly format -w bonjour.fly
```

The exit code is `0` if all is well, `1` if the program has an error, and `2` if the file cannot be read.

## Understanding an error message

Each message gives the kind of the error, its position and what is wrong, then the faulty line with a marker under the column. The messages themselves are in French:

```fly erreur
soit total = 0;
si total > 10 {
    affiche total;
}
affiche resultat;
```

Some frequent messages and their remedy:

| Message | Meaning and what to do |
|---|---|
| `';' attendu à la fin de l'instruction` | `';'` expected at the end of the statement: add the forgotten `;` (the marker is just after the last statement) |
| `nom 'x' non déclaré` | name `x` not declared: declare `x` with `soit` or `lie` **before** using it |
| `'x' est une cellule dérivée (lie)` | `x` is a derived cell: a `lie` cell is not modified, change its sources instead |
| `'x' est déjà déclaré` | `x` is already declared: choose another name, a name cannot hide another |
| `les comparaisons ne s'enchaînent pas` | comparisons do not chain: write `a < b et b < c` |
| `division par zéro` | division by zero: test the divisor before dividing |

## The REPL

The REPL keeps its state from one line to the next. A lone expression is printed directly, and an entry spanning several lines is read up to the closing brace.

```repl
soit a = 2;
lie double = a * 2;
double
a = 10;
double
1 + 2
quand double { affiche "double change :", double; }
a = 11;
```

The commands `:aide` (help), `:source` (the program accumulated so far), `:reinit` (reset) and `:quitter` (quit) are available.

## Using Butterfly from Python

The `butterfly.compilateur` facade is all you need:

```python
from butterfly.compilateur import executer

resultat = executer("soit a = 2; affiche a * 21;")
print(resultat.sortie)  # 42
print(resultat.ok)  # True
```

A runtime error is returned in `resultat.erreur`, along with what was printed before it. A compilation error raises `ErreurCompilation`, which holds all the errors found.

## Running the tests

```bash
uv run pytest                                   # all the tests
uv run mypy butterfly serveur_butterfly tests   # strict typing
uv run ruff check .                             # style
```

The specification is executable: a test reads the table of errors in the [reference](reference.html) and checks that each faulty program produces exactly the announced message.

## Plugging in an AI

The repository contains an MCP server that lets an AI learn Butterfly, check its programs and run them. Everything is explained on the [MCP server](mcp.html) page.
