# Under the hood

Butterfly uses no parser-generator tool: the whole compilation chain is written by hand, in Python.

```text
source text → lexer → tokens → parser → tree → analysis → checked tree → generator → Python
```

Each stage has its input, its output and its tests. All the examples on this page are produced by the real compiler.

## 1. The lexer: from text to tokens

**Module** `butterfly/lexer.py`. It splits the text into "words" (the *tokens*), with their position. It is a **generator**: it reads the source only as it goes, so the tokens read before a lexical error are already available.

```fly tokens
soit total = price * 2; # un commentaire
```

It always reads the longest possible token: `<=` is a single token, and `1..5` gives three tokens (`1`, `..`, `5`), which is why decimal numbers do not exist.

## 2. The parser: from tokens to the tree

**Module** `butterfly/parser.py`. Statements are analysed by **recursive descent** (one method per grammar rule). Expressions are analysed by a **Pratt parser**: a table gives the priority of each operator, and adding an operator means adding one line to the table.

```fly ast
lie c = a + b * 2;
```

The `*` is deeper in the tree than the `+`: that is what gives it priority. The parser **does not stop at the first error**: it notes it, skips to the next statement, and reports all the errors at once.

## 3. Semantic analysis: what the grammar cannot see

**Module** `butterfly/semantique.py`. It checks names (declared before use, never hidden), assignments (never to a derived cell), observers and function calls. It also produces what the generator needs: the top-level cells and, for each derived cell, the cells named in its formula.

```fly analyse
soit a = 1;
soit b = 2;
lie c = a + 1;
lie d = c * b;
```

## 4. The generator: from the tree to Python

**Module** `butterfly/generateur.py`. The key point is **propagation**. Butterfly embeds no reactive engine at run time: for each assignment to a source, the compiler works out the ordered list of derived cells to recompute and of observers to notify, then writes the code that does it.

```fly python
soit price = 20;
soit quantity = 3;
lie total = price * quantity;

quand total {
    affiche "nouveau total :", total;
}

quantity = 5;
```

Read the generated code:

- each derived cell has a `_calc_…` function that is called again at each recomputation;
- before the assignment, the value of the observed cells is set aside (`_av_total`, where `av` stands for "avant", before);
- after the assignment, the affected derived cells are recomputed **in the order of their declaration**, which is a valid topological order since names are declared before use;
- finally, `_change` compares the old and the new value, and the observer `_obs_0` is called only if it changed.

All variables are prefixed with `v_`, and texts are written with `repr`: no name and no text of the program can ever produce Python that the compiler did not plan for.

## 5. The runtime: errors at run time

**Module** `butterfly/runtime.py`. Butterfly has no declared types: the values carry a type, and small functions check types at run time. Each one receives as an argument the **line of the Butterfly program** the call comes from (you can see it in the generated code above): that is how a runtime error reports the right line.

## 6. Around the compiler

| Module | Role |
|---|---|
| `compilateur.py` | the facade (`compiler`, `transpiler`, `executer`): everything else builds on it |
| `cli.py` | the command line, with its exit codes |
| `repl.py` | the interactive session |
| `formateur.py` | the canonical layout, comments and blank lines kept |
| `backend.py` | a `Protocol`: the Python generator and the formatter are two backends, a third can be added without changing anything |

The **REPL** has no state to serialise. It keeps the text of the successful entries and recompiles everything at each new entry. Since a Butterfly program is deterministic, the output of "the history plus the new entry" starts with that of the history: it is enough to display the rest.

## Design choices

| Choice | Reason |
|---|---|
| declare before use | a formula names only existing cells: no cycle is possible, and the order of declaration is a valid computation order |
| `lie` and `quand` only at top level | the dependency graph is known at compile time |
| an observer does not modify the top level | otherwise it could trigger itself forever |
| a name never hides another | Python has no block scope: the generated code keeps the same meaning this way |
| non-chaining comparisons | a clear choice, rather than an ambiguous reading of `a < b < c` |
| integers only | `1..5` (a range) and `1.5` (a decimal) can never be confused |
| no input or output | a program can do nothing but compute and print: safe to run |

## The tests

The repository has more than 360 tests, one file per stage of the chain. Three ideas make them useful:

- the **specification is executable**: a test reads its table of errors and checks each message;
- **every example** is run and its output compared to the expected output, including after going through the formatter;
- the MCP server is tested **in the same process**, then **for real**, launched as a subprocess the way a host would.
