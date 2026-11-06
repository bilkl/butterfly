# The MCP server

Butterfly is a language that **no AI knows**. The MCP server gives it the means to learn it on its own: read the specification and the examples, check its programs, correct itself from the errors, then run them. The AI needs nothing else but this server.

[MCP](https://modelcontextprotocol.io) (Model Context Protocol) is an open protocol that lets an AI application (Claude Code, Claude Desktop, an editor…) plug into servers that offer it tools, documents and instructions.

## Plugging in the server

From a clone of the repository, with [uv](https://docs.astral.sh/uv/):

```bash
claude mcp add butterfly -- uv --directory /absolute/path/to/butterfly run python -m butterfly_server
```

For Claude Desktop, or in a project `.mcp.json` file, the configuration is the following (replace the path):

```json
{
  "mcpServers": {
    "butterfly": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/butterfly",
               "run", "python", "-m", "butterfly_server"]
    }
  }
}
```

To explore the server without an AI, with the official graphical tool (it needs Node.js):

```bash
npx @modelcontextprotocol/inspector uv run python -m butterfly_server
```

## The tools

| Tool | What it does |
|---|---|
| `tokenize` | splits the program into tokens (on a lexical error, returns those read before it) |
| `parse` | analyses the syntax and returns the tree as JSON (each node has a `type` key) |
| `check` | checks the program without running it, and returns **all** the errors at once |
| `transpile` | returns the generated Python code |
| `format` | returns the canonical layout, comments kept |
| `run` | runs the program in a bounded process |

The first five are announced as **read-only**: a host can call them without asking the user for permission.

An error **in the AI's program** is a normal answer (`ok: false`, with the list of errors). The protocol's `is_error` field is reserved for cases where the tool itself could not work, for example an invalid argument. Each error contains its kind, its message, its line, its column and a `context` field: the full message with the faulty line underlined.

## Resources and prompts

| URI | Content |
|---|---|
| `butterfly://specification` | the full specification (lexicon, grammar, semantics, errors) |
| `butterfly://examples` | the list of example programs |
| `butterfly://examples/{name}` | the code of an example |
| `butterfly://examples/{name}/expected` | the exact output of that example |

Two **prompts**, which the user picks in their application: `write_program` (write a program: a complete method, from reading the specification to running it) and `fix_program` (fix a program from the reported errors).

## A typical session

This is the scenario replayed by a test in the repository, with a scripted AI that knows Butterfly only through the server:

1. It reads the **server instructions**, which send it to `butterfly://specification`, then to an example.
2. First draft: it forgets a `;`. `check` answers `ok: false` with the error on **line 2**.
3. It fixes it. `check` then reports a typo: `name 'c' not declared`, on **line 3**.
4. It fixes that too. `check` answers `ok: true` and describes the cells of the program. `run` returns `status: ok` and the output `somme : 13`.
5. It calls `format`, and the formatted version gives the same output.

## Why `run` is safe

Running a program written by an AI means running code nobody has read. The server combines technical protections with the design of the language.

| Risk | Protection |
|---|---|
| infinite loop | maximum delay (0.1 to 5 seconds), then the process is killed |
| infinite output | reading bounded to 64 KiB, then the process is killed |
| excessive memory | address-space limit set by the child process |
| server crash | the program runs in a **separate process**, never in the server |
| leftover files | temporary folder deleted whatever happens |
| reading the MCP channel | the child's standard input is closed |
| environment variables | the child inherits no variable from the server |

This table does not protect file or network access. What does is the language: **a Butterfly program can neither read a file, nor open a connection, nor import a module**. And the generator lets no text of the program through into the Python code: texts are written with `repr`, and every variable is prefixed with `v_`. A test checks that a text containing `__import__('os').system(...)` is printed as is, without running anything.

A language that offered a `read_file(...)` function would need a real sandbox: a container, a dedicated user, system-call filtering.

## The statuses of `run`

| Status | Meaning |
|---|---|
| `ok` | the program ended normally |
| `compilation_error` | the program is wrong: it was not run, the errors are detailed |
| `execution_error` | an error at run time, with its line; the previous output is kept |
| `timeout` | the program exceeded the time limit |
| `output_truncated` | the program printed too much text |
| `memory_exceeded` | the program used too much memory |
| `internal_error` | the run failed without an identifiable Butterfly error |
