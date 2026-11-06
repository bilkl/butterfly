# Butterfly specification

> Draft of step 1. To be reviewed, corrected and validated by the instructor before writing a single line of the compiler.

The keywords of the language (`soit`, `lie`, `quand`…) and its error messages are in French. This document is in English; each keyword is translated where it is introduced.

## Identity

| | |
|---|---|
| Name | Butterfly |
| Extension | `.fly` |
| Idea | Butterfly is a **reactive** language, named after the butterfly effect: changing a single value (a flap of wings) can update a whole program. Next to ordinary variables (`soit`, "let"), you declare **derived cells** (`lie`, "bind") whose value is always equal to a formula, as in a spreadsheet. When a source changes, everything that depends on it updates by itself, exactly once and in the right order. **Observers** (`quand`, "when") can react to the changes. It is meant for people who want to describe *relationships* rather than recomputation steps. |
| Target | Python 3.12 |

## A program to set the tone

```
soit price = 20;
soit quantity = 3;
lie total = price * quantity;

quand total {
    affiche "nouveau total :", total;
}

quantity = 5;       # prints: nouveau total : 100
price = price + 5;    # prints: nouveau total : 125
```

## Lexicon

- **Whitespace and line breaks**: ignored, except to separate two tokens. Statements end with `;`: a line break means nothing, and an expression may span several lines. Indentation is free.
- **Comments**: `#` up to the end of the line. There are no multi-line comments.
- **Numbers**: only positive **integers**, a sequence of decimal digits (`0`, `42`, `007` is 7). Negative numbers are written with the unary operator `-`. No decimals: `1.5` is a lexical error, which avoids any ambiguity with `..` (`1..5`).
- **Texts**: between double quotes, on a single line. Accepted escapes: `\"`, `\\` and `\n`. Any other `\x` is a lexical error, as is a text left unclosed at the end of the line.
- **Identifiers**: a letter (accented or not) or `_`, followed by letters, digits or `_`. Case matters (`Total` and `total` are two names). A keyword glued to other characters is an identifier: `soit_x` and `sinon2` are identifiers, `soit` is a keyword.
- **Keywords**: `soit` (let) `lie` (bind) `quand` (when) `si` (if) `sinon` (else) `pour` (for) `dans` (in) `affiche` (show) `vrai` (true) `faux` (false) `et` (and) `ou` (or) `non` (not)
- **Symbols and operators**: `+` `-` `*` `/` `%` `==` `!=` `<` `<=` `>` `>=` `=` `..` `(` `)` `{` `}` `,` `;`

The lexer always reads the **longest** possible token: `<=` is a single token, so is `..`, and `==` is told apart from `=`.

## Grammar (EBNF)

Notation: `{ x }` repeats zero or more times, `[ x ]` is optional, `|` separates choices, terminals are between quotes. The rule names are French, like the keywords (`programme` is the program, `instr_haut` a top-level statement, `liaison` a binding, `observation` an observer, `declaration` a declaration, `affectation` an assignment, `bloc` a block, `disjonction` an "or" expression, `conjonction` an "and" expression, `negation` a negation, `comparaison` a comparison, `somme` a sum, `produit` a product, `unaire` a unary expression, `primaire` a primary expression, `appel` a call).

```ebnf
programme     = { instr_haut } FIN ;

(* At top level, anything may be written. *)
instr_haut    = instruction | liaison | observation ;
liaison       = "lie" IDENT "=" expression ";" ;
observation   = "quand" IDENT bloc ;

(* In a block, only statements are written: neither "lie" nor "quand". *)
instruction   = declaration | affectation | si | pour | affiche ;
declaration   = "soit" IDENT "=" expression ";" ;
affectation   = IDENT "=" expression ";" ;
si            = "si" expression bloc [ "sinon" ( si | bloc ) ] ;
pour          = "pour" IDENT "dans" expression ".." expression bloc ;
affiche       = "affiche" expression { "," expression } ";" ;
bloc          = "{" { instruction } "}" ;

expression    = disjonction ;
disjonction   = conjonction { "ou" conjonction } ;
conjonction   = negation { "et" negation } ;
negation      = "non" negation | comparaison ;
comparaison   = somme [ ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) somme ] ;
somme         = produit { ( "+" | "-" ) produit } ;
produit       = unaire { ( "*" | "/" | "%" ) unaire } ;
unaire        = "-" unaire | primaire ;
primaire      = ENTIER | TEXTE | "vrai" | "faux" | appel | IDENT | "(" expression ")" ;
appel         = IDENT "(" [ expression { "," expression } ] ")" ;
```

`lie` and `quand` are accepted only at **top level**: writing them in a block is a syntax error, with a message that says so.

## Operator priority and associativity

From lowest to highest priority.

| Level | Operators | Associativity |
|---|---|---|
| 1 | `ou` | left |
| 2 | `et` | left |
| 3 | `non` (prefix) | right |
| 4 | `==` `!=` `<` `<=` `>` `>=` | **none** |
| 5 | `+` `-` | left |
| 6 | `*` `/` `%` | left |
| 7 | `-` (prefix) | right |

- Comparisons **do not chain**: `1 < 2 < 3` is a syntax error (write `1 < 2 et 2 < 3`).
- `non a == b` reads as `non (a == b)`, because `non` has a lower priority than comparisons.
- Unary `-` has the highest priority: `-17 / 5` reads as `(-17) / 5`.

## Semantics

### Values and types

Three kinds of values: **integers** (of unlimited size), **booleans** (`vrai`, `faux`) and **texts**. Variables have no declared type: the value carries one, and type errors are detected at run time.

- `+` adds two integers or concatenates two texts. `-`, `*`, `/`, `%` apply to integers only.
- `/` is **integer division rounded down** and `%` is the remainder with the same sign as the divisor, like Python's `//` and `%`: `-17 / 5` is `-4` and `-17 % 5` is `3`.
- `<` `<=` `>` `>=` compare two integers or two texts (alphabetical order of code points).
- `==` and `!=` compare any values; two values of different types are always different (`1 == "1"` is `faux`).
- `et`, `ou`, `non` apply to booleans only. `et` and `ou` **short-circuit**: `faux et (1 / 0 == 0)` is `faux`.

### Cells: `soit` and `lie`

- `soit x = e;` creates a **source cell**: `e` is evaluated right away, and `x` can be changed later by `x = e2;`.
- `lie y = e;` creates a **derived cell**: `y` is **always** equal to the value of `e`. You cannot assign a value to it.
- A name must be **declared before it is used**. A `lie` formula can therefore rely only on cells already declared, which rules out cycles.
- A name cannot be redeclared while a namesake is visible, **nor hide** a name of an enclosing block. The names of the built-in functions (`min`, `max`, `abs`) are reserved.

### Propagation

When a source receives a value (`x = e;`):

1. `e` is evaluated **once**, with the current values of the cells;
2. `x` takes that value;
3. all the derived cells that depend on `x`, directly or not, are recomputed **once each**, in the **order of their declaration** (which is a valid topological order, since names are declared before use);
4. finally, the observers concerned run (see below).

Nobody therefore sees an intermediate state: in a diamond `a → b, c → d`, `d` is recomputed once, after `b` and `c`. Propagation happens **immediately after the assignment**, including inside a loop or a condition.

### Observers: `quand`

`quand y { ... }` declares a block that runs **every time the value of `y` changes**: the value of `y` before the assignment is compared with its value after propagation. An assignment that changes no value (`a = 2;` when `a` was already 2) triggers nothing.

- `y` must be a cell (`soit` or `lie`) declared **at top level**, before the `quand`.
- The observer is **not** triggered when the cell is created, only by a later change.
- If several observers are concerned by the same assignment, they run in the order of their declaration, each once.
- An observer can read any cell, declare its own variables and use `si`, `pour` and `affiche`. It **cannot assign** a top-level cell (that could loop forever): this is a semantic error.

### Blocks and scopes

A block opens a scope: a name declared with `soit` in a block no longer exists after its `}`. The body of a loop is a new block **at each iteration**: `soit square = i * i;` is therefore redeclared at each iteration without error. The name of a sibling block can be reused. A name used outside its scope is a semantic error ("name not declared").

> Python has no block scope. Since Butterfly forbids hiding a name, the generated Python keeps the same meaning; the semantic analysis only has to refuse uses outside the scope.

### Control structures

- `si c { ... } sinon si c2 { ... } sinon { ... }`: the condition must be a boolean (a runtime error otherwise). Blocks may be empty.
- `pour i dans a..b { ... }`: `a` and `b` are integers evaluated once, before the loop. `i` takes the values `a`, `a+1`, …, `b-1` (**upper bound excluded**). If `a >= b`, the body does not run. `i` is read-only: assigning it a value is a semantic error.

### Printing

`affiche e1, e2, ...;` writes the values separated by **one space**, followed by a line break. An integer is printed in decimal, a text as is (without quotes), a boolean as `vrai` or `faux`.

### Built-in functions

| Call | Result |
|---|---|
| `min(a, b)` | the smaller of two integers |
| `max(a, b)` | the larger of two integers |
| `abs(n)` | the absolute value of an integer |

A wrong number of arguments is a semantic error; an argument that is not an integer is a runtime error. Butterfly has no user-defined functions.

### Runtime errors

Division or modulo by zero, an operand of the wrong type, a non-boolean condition, non-integer `pour` bounds: the program stops with a message that gives the **line of the Butterfly program**. What was already printed stays printed.

## Example programs

Five programs, in `exemples/`, with their exact output (same name, `.attendu` extension, "attendu" meaning "expected").

| File | What it shows |
|---|---|
| `01_expressions.fly` | priorities, `non`/`et`/`ou`, division and modulo of negatives, built-in functions, texts |
| `02_cellules.fly` | `soit`, `lie`, assignment and update of a derived cell |
| `03_losange.fly` | diamond dependencies with no intermediate state, `quand`, assignment with no change |
| `04_boucle.fly` | `pour` (including zero iterations), `si`/`sinon`, `soit` in a block, observer on a threshold |
| `05_budget.fly` | a longer program: several cells, `sinon si`, observer, `abs` |

## Errors

Message format: `Erreur <kind> (ligne L, colonne C) : <message>` (French for "Error <kind> (line L, column C): <message>"). For runtime errors, only the line is given. The messages themselves are in French; their meaning is given below the table.

| Kind | Program | Expected message |
|---|---|---|
| lexical | `soit x = 3 @ 2;` | `Erreur lexicale (ligne 1, colonne 12) : caractère inattendu '@'` |
| syntax | `soit x = ;` | `Erreur de syntaxe (ligne 1, colonne 10) : expression attendue, ';' trouvé` |
| syntax | `affiche 1 < 2 < 3;` | `Erreur de syntaxe (ligne 1, colonne 15) : les comparaisons ne s'enchaînent pas, utilisez 'et'` |
| syntax | `si vrai { lie x = 1; }` | `Erreur de syntaxe (ligne 1, colonne 11) : 'lie' n'est permis qu'au niveau supérieur` |
| semantic | `lie c = a + 1;` | `Erreur sémantique (ligne 1, colonne 9) : nom 'a' non déclaré` |
| semantic | `soit a = 1;` `lie b = a;` `b = 2;` | `Erreur sémantique (ligne 3, colonne 1) : 'b' est une cellule dérivée (lie), on ne peut pas lui affecter de valeur` |
| runtime | `affiche 1 / 0;` | `Erreur d'exécution (ligne 1) : division par zéro` |

In English, in the same order: "unexpected character '@'"; "expression expected, ';' found"; "comparisons do not chain, use 'et'"; "'lie' is allowed only at top level"; "name 'a' not declared"; "'b' is a derived cell (lie), a value cannot be assigned to it"; "division by zero".

## Limits

No user-defined functions, no lists, no decimals, no input or output (no files, no keyboard, no network): a Butterfly program can do nothing but compute and print, which will simplify running it in isolation in the MCP project.

## Possible extensions

- Allow a `lie` formula to name a cell declared **further down**, and detect cycles (`lie a = b; lie b = a;`) during semantic analysis.
- Allow `lie` and `quand` in blocks.
- Add user-defined functions.
