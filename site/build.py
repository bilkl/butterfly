"""Construit le site de Butterfly dans ``site/dist/``.

    uv run python site/build.py

Les pages sont écrites en Markdown (``site/contenu/``). Le build les transforme
en HTML et fait travailler **le vrai compilateur** sur les exemples du texte :

- ```fly``` : un programme, coloré par le lexer de Butterfly lui-même ;
- ```fly run``` : le programme **et sa vraie sortie** (le build exécute le code) ;
- ```fly erreur``` : le programme et le vrai message d'erreur ;
- ```fly tokens```, ```fly ast```, ```fly analyse```, ```fly python``` : les
  vraies étapes du compilateur sur ce programme ;
- ```repl``` : une vraie session du REPL, rejouée.

Une erreur dans un exemple fait échouer le build : la documentation ne peut pas
mentir sur ce que fait le langage.
"""

import html
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

import markdown

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from butterfly.compiler import analyze_program, check, execute, parser, transpile  # noqa: E402
from butterfly.errors import CompilationError, LexicalError, context  # noqa: E402
from butterfly.lexer import tokenize  # noqa: E402
from butterfly.nodes import print_tree  # noqa: E402
from butterfly.repl import run_repl  # noqa: E402
from butterfly.tokens import TypeToken  # noqa: E402

SITE = ROOT / "site"
CONTENT = SITE / "content"
STATIC = SITE / "static"
TEMPLATES = SITE / "templates"
DIST = SITE / "dist"
EXAMPLES = ROOT / "examples"
REPOSITORY = "https://github.com/xbkh/butterfly"

#: (file, label in the navigation)
PAGES = [
    ("index", "Home"),
    ("language", "The language"),
    ("guide", "Guide"),
    ("reference", "Reference"),
    ("examples", "Examples"),
    ("playground", "Try it"),
    ("mcp", "MCP server"),
    ("internals", "Under the hood"),
]

T = TypeToken
CLASSES = {
    T.LET: "src",
    T.BIND: "der",
    T.WHEN: "obs",
    T.IF: "kw", T.ELSE: "kw", T.FOR: "kw", T.IN: "kw", T.PRINT: "kw",
    T.TRUE: "kw", T.FALSE: "kw", T.AND: "kw", T.OR: "kw", T.NOT: "kw",
    T.INTEGER: "num",
    T.TEXT: "str",
    T.COMMENT: "com",
}  # fmt: skip


# --- Coloration : le vrai lexer de Butterfly ----------------------------------------


def colorize(source: str) -> str:
    """Le programme en HTML, coloré d'après les tokens du lexer de Butterfly."""
    try:
        tokens = list(tokenize(source, comments=True))
    except LexicalError:
        return html.escape(source)  # un exemple volontairement faux
    starts = [0]
    for i, character in enumerate(source):
        if character == "\n":
            starts.append(i + 1)
    pieces: list[str] = []
    cursor = 0
    for token in tokens:
        if token.type is T.EOF:
            break
        start = starts[token.position.line - 1] + token.position.column - 1
        end = start + len(token.lexeme)
        pieces.append(html.escape(source[cursor:start]))
        text = html.escape(source[start:end])
        css_class = CLASSES.get(token.type)
        pieces.append(f'<span class="{css_class}">{text}</span>' if css_class else text)
        cursor = end
    pieces.append(html.escape(source[cursor:]))
    return "".join(pieces)


# --- Les blocs de code du Markdown ----------------------------------------------------


def pre(content: str, css_class: str = "") -> str:
    return f'<pre class="code {css_class}"><code>{content}</code></pre>'.replace(
        "  >", ">"
    )


def failure(message: str, source: str) -> SystemExit:
    return SystemExit(f"BUILD ERROR: {message}\n--- program ---\n{source}")


def real_output(source: str) -> tuple[str, str | None]:
    """Exécute vraiment le programme : (sortie, erreur d'exécution éventuelle)."""
    try:
        result = execute(source)
    except CompilationError as error:
        raise failure(
            f"the `fly run` block does not compile:\n{error}", source
        ) from error
    error_text = context(result.error, source) if result.error else None
    return result.output, error_text


def playground_link(source: str) -> str:
    link = "playground.html#code=" + quote(source, safe="")
    return f'<a class="essayer" href="{link}">Try this program</a>'


def transcribe_repl(code: str) -> str:
    """Rejoue une vraie session du REPL et renvoie la conversation."""
    entries = iter(code.splitlines())
    lines: list[str] = []
    banner = [True]

    def read_line(prompt_text: str) -> str:
        try:
            line = next(entries)
        except StopIteration:
            raise EOFError from None
        lines.append(f"{prompt_text}{line}")
        return line

    def write_line(text: str) -> None:
        if banner[0]:  # le message d'accueil n'est pas montré
            banner[0] = False
            return
        lines.extend(text.splitlines())

    run_repl(read_line, write_line)
    return "\n".join(lines)


def process_block(language: str, options: list[str], code: str) -> str:
    """Le HTML d'un bloc de code, selon sa langue et ses options."""
    if language == "repl":
        return pre(html.escape(transcribe_repl(code)), "repl")
    if language != "fly":
        return pre(html.escape(code), f"lang-{language}" if language else "")
    mode = options[0] if options else ""
    if mode == "":
        return pre(colorize(code))
    if mode == "run":
        output, error = real_output(code)
        blocks = pre(colorize(code))
        if output:
            blocks += pre(html.escape(output.rstrip("\n")), "sortie")
        if error:
            blocks += pre(html.escape(error), "sortie erreur")
        return f'<div class="essai">{blocks}{playground_link(code)}</div>'
    if mode == "error":
        errors = check(code)
        if errors:
            text = "\n".join(context(e, code) for e in errors)
        else:
            _, error_message = real_output(code)
            if error_message is None:
                raise failure("the `fly erreur` block produces no error", code)
            text = error_message
        return f'<div class="essai">{pre(colorize(code))}{pre(html.escape(text), "sortie erreur")}</div>'
    if mode == "tokens":
        text = "\n".join(repr(t) for t in tokenize(code))
    elif mode == "ast":
        text = print_tree(parser(code))
    elif mode == "python":
        text = transpile(code)
    elif mode == "analyse":
        analysis = analyze_program(code)
        lines = [f"cells: {', '.join(analysis.cells)}"]
        for name, deps in analysis.dependencies.items():
            lines.append(f"{name} depends on: {', '.join(sorted(deps)) or '(nothing)'}")
        text = "\n".join(lines)
    else:
        raise failure(f"unknown block option : {mode!r}", code)
    return f'<div class="essai">{pre(colorize(code))}{pre(html.escape(text), "sortie")}</div>'


FENCE = re.compile(r"^```(?P<info>[^\n]*)\n(?P<code>.*?)\n```[ \t]*$", re.M | re.S)


def render_markdown(text: str) -> tuple[str, str]:
    """Le Markdown en HTML (les blocs de code étant traités par le compilateur)
    et la table des matières."""
    blocks: list[str] = []

    def substitute(found: re.Match[str]) -> str:
        words = found.group("info").split()
        language = words[0] if words else ""
        blocks.append(process_block(language, words[1:], found.group("code")))
        return f"\n\n@@BLOC{len(blocks) - 1}@@\n\n"

    text = FENCE.sub(substitute, text)
    md = markdown.Markdown(
        extensions=["tables", "toc", "sane_lists"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
    )
    body = md.convert(text)
    for i, block in enumerate(blocks):
        body = body.replace(f"<p>@@BLOC{i}@@</p>", block)
    return body, getattr(md, "toc", "")


# --- Pages -----------------------------------------------------------------------------


def title_and_body(text: str) -> tuple[str, str]:
    first_, _, remainder = text.partition("\n")
    if not first_.startswith("# "):
        raise SystemExit('a page must start with a "# …" title')
    return first_[2:].strip(), remainder.lstrip("\n")


def navigation(current_page: str) -> str:
    links = []
    for slug, label in PAGES:
        active = ' aria-current="page"' if slug == current_page else ""
        links.append(f'<a href="{slug}.html"{active}>{label}</a>')
    return "\n".join(links)


def wrap_page(
    slug: str, title: str, description: str, body: str, css_class: str
) -> str:
    template = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    page_title = (
        "Butterfly: a reactive language" if slug == "index" else f"{title}: Butterfly"
    )
    replacements = {
        "@@TITRE@@": html.escape(page_title),
        "@@DESCRIPTION@@": html.escape(description, quote=True),
        "@@NAV@@": navigation(slug),
        "@@CLASSE@@": css_class,
        "@@CORPS@@": body,
        "@@DEPOT@@": REPOSITORY,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def document_page(slug: str, text: str, description: str) -> str:
    title, body_md = title_and_body(text)
    body, toc = render_markdown(body_md)
    aside = f'<aside class="toc" aria-label="On this page">{toc}</aside>' if toc else ""
    content = (
        '<div class="doc-grid"><article class="doc">'
        f"<h1>{html.escape(title)}</h1>{body}</article>{aside}</div>"
    )
    return wrap_page(slug, title, description, content, "page-doc")


def reference_text() -> str:
    """The repository specification, without the draft note."""
    text = (ROOT / "specification.md").read_text(encoding="utf-8")
    text = re.sub(r"^> Draft of step 1.*\n\n?", "", text, flags=re.M)
    text = text.replace("# Butterfly specification", "# Language reference", 1)
    return text


def example_description(source: str) -> str:
    for line in source.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


def available_examples() -> list[dict[str, str]]:
    examples = []
    for file_path in sorted(EXAMPLES.glob("*.fly")):
        source = file_path.read_text(encoding="utf-8")
        expected = file_path.with_suffix(".expected").read_text(encoding="utf-8")
        output, error = real_output(source)
        if error or output != expected:
            raise failure(
                f"{file_path.name} does not produce its expected output", source
            )
        title = file_path.stem.split("_", 1)[1].replace("_", " ").capitalize()
        examples.append(
            {"nom": file_path.stem, "titre": title, "source": source,
             "description": example_description(source)}
        )  # fmt: skip
    return examples


def examples_page(examples: list[dict[str, str]]) -> str:
    lines = [
        "# Examples",
        "",
        "These five programs are the ones of the specification. Each one is run when "
        "the site is built: the output shown is the real compiler's, and it is "
        "compared to the expected output stored in the repository.",
        "",
    ]
    for example in examples:
        lines += [f"## {example['titre']}", "", example["description"], ""]
        lines += ["```fly run", example["source"].rstrip("\n"), "```", ""]
    return "\n".join(lines)


def home_page(examples: list[dict[str, str]]) -> str:
    template = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    diamond = next(e for e in examples if e["nom"] == "03_diamond")
    budget = next(e for e in examples if e["nom"] == "05_budget")
    hero_program = "\n".join(
        line
        for line in diamond["source"].splitlines()
        if not line.startswith("#") and not line.startswith("affiche d;")
    )
    hero_program = re.sub(r"\n(?:a = \d+;\n?)+$", "\n", hero_program).strip("\n")
    output, _ = real_output(budget["source"])
    replacements = {
        "@@PROGRAMME_HERO@@": colorize(hero_program),
        "@@PROGRAMME_BUDGET@@": colorize(budget["source"].rstrip("\n")),
        "@@SORTIE_BUDGET@@": html.escape(output.rstrip("\n")),
        "@@LIEN_BUDGET@@": playground_link(budget["source"]),
        "@@DEPOT@@": REPOSITORY,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return wrap_page(
        "index",
        "Butterfly",
        "Butterfly is a reactive language transpiled to Python: change a value, "
        "and everything that depends on it updates by itself.",
        template,
        "page-accueil",
    )


def playground_page(examples: list[dict[str, str]]) -> str:
    template = (TEMPLATES / "playground.html").read_text(encoding="utf-8")
    data = json.dumps(examples, ensure_ascii=False).replace("</", "<\\/")
    template = template.replace("@@EXEMPLES_JSON@@", data)
    return wrap_page(
        "playground",
        "Try it",
        "Write and run a Butterfly program right in your browser.",
        template,
        "page-playground",
    )


# --- Assemblage ------------------------------------------------------------------------


def compiler_archive() -> None:
    """Le paquet ``butterfly`` en zip : le playground l'exécute avec Pyodide."""
    with zipfile.ZipFile(DIST / "butterfly.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted((ROOT / "butterfly").glob("*.py")):
            archive.write(file_path, f"butterfly/{file_path.name}")


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(STATIC, DIST / "static")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    examples = available_examples()
    pages: dict[str, str] = {
        "index": home_page(examples),
        "playground": playground_page(examples),
        "examples": document_page(
            "examples",
            examples_page(examples),
            "The five example programs of Butterfly, with their real output.",
        ),
        "reference": document_page(
            "reference",
            reference_text(),
            "Lexicon, grammar, priorities and semantics of Butterfly.",
        ),
    }
    descriptions = {
        "language": "Discover Butterfly step by step: cells, observers, operators, errors.",
        "guide": "Install Butterfly, run a program, use the CLI and the REPL.",
        "mcp": "The Butterfly MCP server: an AI learns the language there, writes it and runs it.",
        "internals": "How Butterfly works: lexer, parser, analysis, Python generation.",
    }
    for slug, description in descriptions.items():
        text = (CONTENT / f"{slug}.md").read_text(encoding="utf-8")
        pages[slug] = document_page(slug, text, description)

    for slug, content in pages.items():
        (DIST / f"{slug}.html").write_text(content, encoding="utf-8")
    compiler_archive()
    print(f"site built: {len(pages)} pages in {DIST.relative_to(ROOT)}/")


if __name__ == "__main__":
    build()
