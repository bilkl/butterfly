# Butterfly specification

> Draft of step 1. To be reviewed, corrected and validated by the instructor before writing a single line of the compiler.

## Identity

| | |
|---|---|
| Name | Butterfly |
| Extension | `.fly` |
| Idea | Butterfly is a **reactive** language, named after the butterfly effect: changing a single value (a flap of wings) can update a whole program. Next to ordinary variables (`let`), you declare **derived cells** (`bind`) whose value is always equal to a formula, as in a spreadsheet. When a source changes, everything that depends on it updates by itself, exactly once and in the right order. **Observers** (`when`) can react to the changes. It is meant for people who want to describe *relationships* rather than recomputation steps. |
| Target | Python 3.12 |

## A program to set the tone

```
let price = 20;
let quantity = 3;
bind total = price * quantity;

when total {
    print "nouveau total :", total;
}

quantity = 5;       # prints: nouveau total : 100
price = price + 5;    # prints: nouveau total : 125
```

## Lexicon

- **Whitespace and line breaks**: ignored, except to separate two tokens. Statements end with `;`: a line break means nothing, and an expression may span several lines. Indentation is free.
- **Comments**: `#` up to the end of the line. There are no multi-line comments.
- **Numbers**: only positive **integers**, a sequence of decimal digits (`0`, `42`, `007` is 7). Negative numbers are written with the unary operator `-`. No decimals: `1.5` is a lexical error, which avoids any ambiguity with `..` (`1..5`).
- **Texts**: between double quotes, on a single line. Accepted escapes: `\"`, `\\` and `\n`. Any other `\x` is a lexical error, as is a text left unclosed at the end of the line.
- **Identifiers**: a letter (accented or not) or `_`, followed by letters, digits or `_`. Case matters (`Total` and `total` are two names). A keyword glued to other characters is an identifier: `let_x` and `else2` are identifiers, `let` is a keyword.
- **Keywords**: `let` `bind` `when` `if` `else` `for` `in` `print` `true` `false` `and` `or` `not`
- **Symbols and operators**: `+` `-` `*` `/` `%` `==` `!=` `<` `<=` `>` `>=` `=` `..` `(` `)` `{` `}` `,` `;`

The lexer always reads the **longest** possible token: `<=` is a single token, so is `..`, and `==` is told apart from `=`.

## Grammar (EBNF)

Notation: `{ x }` repeats zero or more times, `[ x ]` is optional, `|` separates choices, terminals are between quotes. The rule names are descriptive (`program`, `top_statement`, `binding`, `observer`, `statement`, `block`, …).

```ebnf
program     = { top_statement } EOF ;

(* At top level, anything may be written. *)
top_statement    = statement | binding | observer ;
binding       = "bind" IDENT "=" expression ";" ;
observer   = "when" IDENT block ;

(* In a block, only statements are written: neither "bind" nor "when". *)
statement   = declaration | assignment | if_stmt | for_stmt | print_stmt ;
declaration   = "let" IDENT "=" expression ";" ;
assignment   = IDENT "=" expression ";" ;
if_stmt            = "if" expression block [ "else" ( if_stmt | block ) ] ;
for_stmt          = "for" IDENT "in" expression ".." expression block ;
print_stmt       = "print" expression { "," expression } ";" ;
block          = "{" { statement } "}" ;

expression    = disjunction ;
disjunction   = conjunction { "or" conjunction } ;
conjunction   = negation { "and" negation } ;
negation      = "not" negation | comparison ;
comparison   = sum [ ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) sum ] ;
sum         = product { ( "+" | "-" ) product } ;
product       = unary { ( "*" | "/" | "%" ) unary } ;
unary        = "-" unary | primary ;
primary      = INTEGER | TEXT | "true" | "false" | call | IDENT | "(" expression ")" ;
call         = IDENT "(" [ expression { "," expression } ] ")" ;
```

`bind` and `when` are accepted only at **top level**: writing them in a block is a syntax error, with a message that says so.

## Operator priority and associativity

From lowest to highest priority.

| Level | Operators | Associativity |
|---|---|---|
| 1 | `or` | left |
| 2 | `and` | left |
| 3 | `not` (prefix) | right |
| 4 | `==` `!=` `<` `<=` `>` `>=` | **none** |
| 5 | `+` `-` | left |
| 6 | `*` `/` `%` | left |
| 7 | `-` (prefix) | right |

- Comparisons **do not chain**: `1 < 2 < 3` is a syntax error (write `1 < 2 and 2 < 3`).
- `not a == b` reads as `not (a == b)`, because `not` has a lower priority than comparisons.
- Unary `-` has the highest priority: `-17 / 5` reads as `(-17) / 5`.

## Semantics

### Values and types

Three kinds of values: **integers** (of unlimited size), **booleans** (`true`, `false`) and **texts**. Variables have no declared type: the value carries one, and type errors are detected at run time.

- `+` adds two integers or concatenates two texts. `-`, `*`, `/`, `%` apply to integers only.
- `/` is **integer division rounded down** and `%` is the remainder with the same sign as the divisor, like Python's `//` and `%`: `-17 / 5` is `-4` and `-17 % 5` is `3`.
- `<` `<=` `>` `>=` compare two integers or two texts (alphabetical order of code points).
- `==` and `!=` compare any values; two values of different types are always different (`1 == "1"` is `false`).
- `and`, `or`, `not` apply to booleans only. `and` and `or` **short-circuit**: `false and (1 / 0 == 0)` is `false`.

### Cells: `let` and `bind`

- `let x = e;` creates a **source cell**: `e` is evaluated right away, and `x` can be changed later by `x = e2;`.
- `bind y = e;` creates a **derived cell**: `y` is **always** equal to the value of `e`. You cannot assign a value to it.
- A name must be **declared before it is used**. A `bind` formula can therefore rely only on cells already declared, which rules out cycles.
- A name cannot be redeclared while a namesake is visible, **nor hide** a name of an enclosing block. The names of the built-in functions (`min`, `max`, `abs`) are reserved.

### Propagation

When a source receives a value (`x = e;`):

1. `e` is evaluated **once**, with the current values of the cells;
2. `x` takes that value;
3. all the derived cells that depend on `x`, directly or not, are recomputed **once each**, in the **order of their declaration** (which is a valid topological order, since names are declared before use);
4. finally, the observers concerned run (see below).

Nobody therefore sees an intermediate state: in a diamond `a → b, c → d`, `d` is recomputed once, after `b` and `c`. Propagation happens **immediately after the assignment**, including inside a loop or a condition.

### Observers: `when`

`when y { ... }` declares a block that runs **every time the value of `y` changes**: the value of `y` before the assignment is compared with its value after propagation. An assignment that changes no value (`a = 2;` when `a` was already 2) triggers nothing.

- `y` must be a cell (`let` or `bind`) declared **at top level**, before the `when`.
- The observer is **not** triggered when the cell is created, only by a later change.
- If several observers are concerned by the same assignment, they run in the order of their declaration, each once.
- An observer can read any cell, declare its own variables and use `if`, `for` and `print`. It **cannot assign** a top-level cell (that could loop forever): this is a semantic error.

### Blocks and scopes

A block opens a scope: a name declared with `let` in a block no longer exists after its `}`. The body of a loop is a new block **at each iteration**: `let square = i * i;` is therefore redeclared at each iteration without error. The name of a sibling block can be reused. A name used outside its scope is a semantic error ("name not declared").

> Python has no block scope. Since Butterfly forbids hiding a name, the generated Python keeps the same meaning; the semantic analysis only has to refuse uses outside the scope.

### Control structures

- `if c { ... } else if c2 { ... } else { ... }`: the condition must be a boolean (a runtime error otherwise). Blocks may be empty.
- `for i in a..b { ... }`: `a` and `b` are integers evaluated once, before the loop. `i` takes the values `a`, `a+1`, …, `b-1` (**upper bound excluded**). If `a >= b`, the body does not run. `i` is read-only: assigning it a value is a semantic error.

### Printing

`print e1, e2, ...;` writes the values separated by **one space**, followed by a line break. An integer is printed in decimal, a text as is (without quotes), a boolean as `true` or `false`.

### Built-in functions

| Call | Result |
|---|---|
| `min(a, b)` | the smaller of two integers |
| `max(a, b)` | the larger of two integers |
| `abs(n)` | the absolute value of an integer |

A wrong number of arguments is a semantic error; an argument that is not an integer is a runtime error. Butterfly has no user-defined functions.

### Runtime errors

Division or modulo by zero, an operand of the wrong type, a non-boolean condition, non-integer `for` bounds: the program stops with a message that gives the **line of the Butterfly program**. What was already printed stays printed.

## Example programs

Five programs, in `exemples/`, with their exact output (same name, `.attendu` extension, "attendu" meaning "expected").

| File | What it shows |
|---|---|
| `01_expressions.fly` | priorities, `not`/`and`/`or`, division and modulo of negatives, built-in functions, texts |
| `02_cells.fly` | `let`, `bind`, assignment and update of a derived cell |
| `03_diamond.fly` | diamond dependencies with no intermediate state, `when`, assignment with no change |
| `04_loop.fly` | `for` (including zero iterations), `if`/`else`, `let` in a block, observer on a threshold |
| `05_budget.fly` | a longer program: several cells, `else if`, observer, `abs` |

## Errors

Message format: `<Kind> error (line L, column C): <message>`. For runtime errors, only the line is given.

| Kind | Program | Expected message |
|---|---|---|
| lexical | `let x = 3 @ 2;` | `Lexical error (line 1, column 11): unexpected character '@'` |
| syntax | `let x = ;` | `Syntax error (line 1, column 9): expression expected, ';' found` |
| syntax | `print 1 < 2 < 3;` | `Syntax error (line 1, column 13): comparisons do not chain, use 'and'` |
| syntax | `if true { bind x = 1; }` | `Syntax error (line 1, column 11): 'bind' is only allowed at top level` |
| semantic | `bind c = a + 1;` | `Semantic error (line 1, column 10): name 'a' not declared` |
| semantic | `let a = 1;` `bind b = a;` `b = 2;` | `Semantic error (line 3, column 1): 'b' is a derived cell (bind), a value cannot be assigned to it` |
| runtime | `print 1 / 0;` | `Runtime error (line 1): division by zero` |

## Limits

No user-defined functions, no lists, no decimals, no input or output (no files, no keyboard, no network): a Butterfly program can do nothing but compute and print, which will simplify running it in isolation in the MCP project.

## Possible extensions

- Allow a `bind` formula to name a cell declared **further down**, and detect cycles (`bind a = b; bind b = a;`) during semantic analysis.
- Allow `bind` and `when` in blocks.
- Add user-defined functions.
