# The language in ten minutes

Butterfly is a **reactive** language. Next to ordinary variables, you declare cells whose value is always equal to a formula, as in a spreadsheet. This page introduces the language step by step. Every program is run when the site is built: what you read as output is the real output.

## A value that follows another

`let` creates a **source cell**: you can change it whenever you like. `bind` creates a **derived cell**: it is always equal to the result of its formula. `print` prints its values separated by a space.

```fly run
let price = 20;
let quantity = 3;
bind total = price * quantity;
print "total :", total;
quantity = 5;
print "total :", total;
price = price + 5;
print "total :", total;
```

Nobody recomputed `total`. As soon as a source changes, every derived cell that depends on it is updated, exactly once each and in the right order. You cannot assign a value to a derived cell: that would contradict its formula.

## Reacting to a change

`when` declares an **observer**: a block that runs every time the value of a cell changes.

```fly run
let temperature = 18;
bind hot = temperature > 25;

when hot {
    print "il fait chaud :", hot;
}

temperature = 22;
temperature = 27;
temperature = 30;
temperature = 20;
```

The observer spoke only twice, although the temperature changed four times. What matters is the value of `hot`: it changes only when the temperature crosses 25 degrees, in either direction. Three rules to remember:

- an observer is **not** triggered when the cell is created;
- it is triggered only if the value **really changed** (assigning `a = 2;` when `a` is already 2 does nothing);
- it can read any cell, but it **cannot modify** a top-level one, which rules out infinite loops.

## No intermediate state

When several cells depend on the same source, an observer never sees a half-updated state. Here `d` depends on `b` and `c`, which both depend on `a`:

```fly run
let a = 1;
bind b = a + 1;
bind c = a * 10;
bind d = b + c;

when d {
    print "d vaut maintenant", d;
}

a = 2;
a = 5;
```

For `a = 2;`, `d` is recomputed once, **after** `b` and `c`. The observer therefore receives 23, never 13 (the value you would get with `b` up to date but `c` not yet).

## Values and operators

Butterfly has three kinds of values: **integers** (of unlimited size), **booleans** (`true` for true, `false` for false) and **texts**. Variables have no declared type: the value carries one, and type errors are reported at run time. The logical operators are `and` (and), `or` (or) and `not` (not).

```fly run
print 2 + 3 * 4, (2 + 3) * 4;
print 17 / 5, 17 % 5, -17 / 5, -17 % 5;
print 1 < 2, not (1 < 2) or 5 >= 5;
print "but" + "terfly", "a" < "b";
print 99999999999 * 99999999999;
```

`/` is integer division rounded down, and `%` is the remainder with the same sign as the divisor (like Python's `//` and `%`). Here are the priorities, from lowest to highest:

| Level | Operators | Associativity |
|---|---|---|
| 1 | `or` | left |
| 2 | `and` | left |
| 3 | `not` | prefix |
| 4 | `==` `!=` `<` `<=` `>` `>=` | none |
| 5 | `+` `-` | left |
| 6 | `*` `/` `%` | left |
| 7 | unary `-` | prefix |

Comparisons **do not chain**: `1 < 2 < 3` is an error, and the message says how to write it.

```fly error
print 1 < 2 < 3;
```

`and` and `or` **short-circuit**: `false and (1 / 0 == 0)` is `false` without ever dividing by zero. And `==` also compares types: `true == 1` is `false`.

## Conditions and loops

`if` is "if", `else` is "else", and `for i in 1..4` is "for i in 1..4".

```fly run
let grade = 14;
if grade >= 16 {
    print "très bien";
} else if grade >= 12 {
    print "bien";
} else {
    print "à revoir";
}

for i in 1..4 {
    print i, i * i;
}
```

The upper bound of a `for` is **excluded**: `1..4` gives 1, 2, 3. The bounds are evaluated once, before the loop. The loop variable is read-only.

## Blocks and scopes

A name declared in a block no longer exists after it. Above all, a name **can never hide another**: this is stricter than Python, and it is what lets the generated Python code keep exactly the same meaning.

```fly error
let a = 1;
if true {
    let a = 2;
}
```

## Built-in functions

There are three, and they work on integers: `min`, `max` and `abs`.

```fly run
print min(4, 9), max(4, 9), abs(-7);
```

## Errors

An error gives its kind, its position, a message that says what to do, and the faulty line underlined. Butterfly reports **all** the errors at once rather than one by one.

```fly error
let a = ;
let b = 2
print c;
```

There are four kinds of errors: lexical (a character the language does not know), syntax, semantic (the program is well written but makes no sense) and runtime.

```fly error
let x = 3 @ 2;
```

```fly error
let a = 1;
bind b = a;
b = 2;
```

A runtime error gives the line **of the Butterfly program** (not the one of the generated Python), and what was already printed is kept:

```fly run
print "début";
print 1 / 0;
print "fin";
```

## What Butterfly does not do

No user-defined functions, no lists, no decimal numbers, no input or output (no files, no keyboard, no network). A program can only compute and print. This is a choice: it keeps the language small and, above all, safe for an AI to run (see the page on the [MCP server](mcp.html)).
