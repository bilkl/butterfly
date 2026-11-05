# The language in ten minutes

Butterfly is a **reactive** language. Next to ordinary variables, you declare cells whose value is always equal to a formula, as in a spreadsheet. This page introduces the language step by step. Every program is run when the site is built: what you read as output is the real output.

The keywords (`soit`, `lie`, `quand`, `si`, `pour`, `affiche`…) and the error messages are in French: Butterfly is a French-flavoured language. Each one is translated where it first appears.

## A value that follows another

`soit` ("let") creates a **source cell**: you can change it whenever you like. `lie` ("bind") creates a **derived cell**: it is always equal to the result of its formula. `affiche` ("show") prints its values separated by a space.

```fly run
soit prix = 20;
soit quantite = 3;
lie total = prix * quantite;
affiche "total :", total;
quantite = 5;
affiche "total :", total;
prix = prix + 5;
affiche "total :", total;
```

Nobody recomputed `total`. As soon as a source changes, every derived cell that depends on it is updated, exactly once each and in the right order. You cannot assign a value to a derived cell: that would contradict its formula.

## Reacting to a change

`quand` ("when") declares an **observer**: a block that runs every time the value of a cell changes.

```fly run
soit temperature = 18;
lie chaud = temperature > 25;

quand chaud {
    affiche "il fait chaud :", chaud;
}

temperature = 22;
temperature = 27;
temperature = 30;
temperature = 20;
```

The observer spoke only twice, although the temperature changed four times. What matters is the value of `chaud` ("hot"): it changes only when the temperature crosses 25 degrees, in either direction. Three rules to remember:

- an observer is **not** triggered when the cell is created;
- it is triggered only if the value **really changed** (assigning `a = 2;` when `a` is already 2 does nothing);
- it can read any cell, but it **cannot modify** a top-level one, which rules out infinite loops.

## No intermediate state

When several cells depend on the same source, an observer never sees a half-updated state. Here `d` depends on `b` and `c`, which both depend on `a`:

```fly run
soit a = 1;
lie b = a + 1;
lie c = a * 10;
lie d = b + c;

quand d {
    affiche "d vaut maintenant", d;
}

a = 2;
a = 5;
```

For `a = 2;`, `d` is recomputed once, **after** `b` and `c`. The observer therefore receives 23, never 13 (the value you would get with `b` up to date but `c` not yet).

## Values and operators

Butterfly has three kinds of values: **integers** (of unlimited size), **booleans** (`vrai` for true, `faux` for false) and **texts**. Variables have no declared type: the value carries one, and type errors are reported at run time. The logical operators are `et` (and), `ou` (or) and `non` (not).

```fly run
affiche 2 + 3 * 4, (2 + 3) * 4;
affiche 17 / 5, 17 % 5, -17 / 5, -17 % 5;
affiche 1 < 2, non (1 < 2) ou 5 >= 5;
affiche "but" + "terfly", "a" < "b";
affiche 99999999999 * 99999999999;
```

`/` is integer division rounded down, and `%` is the remainder with the same sign as the divisor (like Python's `//` and `%`). Here are the priorities, from lowest to highest:

| Level | Operators | Associativity |
|---|---|---|
| 1 | `ou` | left |
| 2 | `et` | left |
| 3 | `non` | prefix |
| 4 | `==` `!=` `<` `<=` `>` `>=` | none |
| 5 | `+` `-` | left |
| 6 | `*` `/` `%` | left |
| 7 | unary `-` | prefix |

Comparisons **do not chain**: `1 < 2 < 3` is an error, and the message says how to write it (the message reads: "comparisons do not chain, use 'et'").

```fly erreur
affiche 1 < 2 < 3;
```

`et` and `ou` **short-circuit**: `faux et (1 / 0 == 0)` is `faux` without ever dividing by zero. And `==` also compares types: `vrai == 1` is `faux`.

## Conditions and loops

`si` is "if", `sinon` is "else", and `pour i dans 1..4` is "for i in 1..4".

```fly run
soit note = 14;
si note >= 16 {
    affiche "très bien";
} sinon si note >= 12 {
    affiche "bien";
} sinon {
    affiche "à revoir";
}

pour i dans 1..4 {
    affiche i, i * i;
}
```

The upper bound of a `pour` is **excluded**: `1..4` gives 1, 2, 3. The bounds are evaluated once, before the loop. The loop variable is read-only.

## Blocks and scopes

A name declared in a block no longer exists after it. Above all, a name **can never hide another**: this is stricter than Python, and it is what lets the generated Python code keep exactly the same meaning.

```fly erreur
soit a = 1;
si vrai {
    soit a = 2;
}
```

The message says: "'a' is already declared".

## Built-in functions

There are three, and they work on integers: `min`, `max` and `abs`.

```fly run
affiche min(4, 9), max(4, 9), abs(-7);
```

## Errors

An error gives its kind, its position, a message that says what to do, and the faulty line underlined. Butterfly reports **all** the errors at once rather than one by one.

```fly erreur
soit a = ;
soit b = 2
affiche c;
```

The three messages above read: "expression expected, ';' found", "';' expected at the end of the statement" and "name 'c' not declared".

There are four kinds of errors: lexical (a character the language does not know), syntax, semantic (the program is well written but makes no sense) and runtime.

```fly erreur
soit x = 3 @ 2;
```

("unexpected character '@'")

```fly erreur
soit a = 1;
lie b = a;
b = 2;
```

("'b' is a derived cell (lie), a value cannot be assigned to it")

A runtime error gives the line **of the Butterfly program** (not the one of the generated Python), and what was already printed is kept:

```fly run
affiche "début";
affiche 1 / 0;
affiche "fin";
```

The error here is "division by zero".

## What Butterfly does not do

No user-defined functions, no lists, no decimal numbers, no input or output (no files, no keyboard, no network). A program can only compute and print. This is a choice: it keeps the language small and, above all, safe for an AI to run (see the page on the [MCP server](mcp.html)).
