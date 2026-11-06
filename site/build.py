"""Builds the Butterfly website in ``site/dist/`` (English at the root, French in ``fr/``).

    uv run python site/build.py

Pages are written in Markdown (``site/content/<language>/``). The build turns them
into HTML and makes **the real compiler** work on the examples of the text:

- ```fly```: a program, coloured by Butterfly's own lexer;
- ```fly run```: the program **and its real output** (the build runs the code);
- ```fly error```: the program and the real error message;
- ```fly tokens```, ```fly ast```, ```fly analyse```, ```fly python```: the real
  stages of the compiler on that program;
- ```repl```: a real REPL session, replayed.

An error in an example fails the build: the documentation cannot lie about what
the language does.
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

LANGUAGES = ("en", "fr")
PAGES = [
    "index", "language", "guide", "reference", "examples", "playground", "mcp", "internals",
]  # fmt: skip

#: The texts of the interface, per language.
UI: dict[str, dict[str, str]] = {
    "en": {
        "switch": "Français", "switch_title": "Lire ce site en français",
        "skip": "Skip to content", "home_aria": "Butterfly, home", "nav_aria": "Site pages",
        "theme": "Switch theme", "on_this_page": "On this page",
        "footer": "Butterfly, a reactive language transpiled to Python. Project of the Advanced Python course.",
        "source": "Source code on GitHub", "try_program": "Try this program",
        "home_title": "Butterfly: a reactive language",
        "cells": "cells", "depends_on": "depends on", "nothing": "(nothing)",
        "nav_index": "Home", "nav_language": "The language", "nav_guide": "Guide",
        "nav_reference": "Reference", "nav_examples": "Examples", "nav_playground": "Try it",
        "nav_mcp": "MCP server", "nav_internals": "Under the hood",
        "d_index": "Butterfly is a reactive language transpiled to Python: change a value, and everything that depends on it updates by itself.",
        "d_language": "Discover Butterfly step by step: cells, observers, operators, errors.",
        "d_guide": "Install Butterfly, run a program, use the CLI and the REPL.",
        "d_reference": "Lexicon, grammar, priorities and semantics of Butterfly.",
        "d_examples": "The five example programs of Butterfly, with their real output.",
        "d_playground": "Write and run a Butterfly program right in your browser.",
        "d_mcp": "The Butterfly MCP server: an AI learns the language there, writes it and runs it.",
        "d_internals": "How Butterfly works: lexer, parser, analysis, Python generation.",
        "examples_title": "Examples",
        "examples_intro": "These five programs are the ones of the specification. Each one is run when the site is built: the output shown is the real compiler's, and it is compared to the expected output stored in the repository.",
        "playground_title": "Try it",
    },
    "fr": {
        "switch": "English", "switch_title": "Read this site in English",
        "skip": "Aller au contenu", "home_aria": "Butterfly, accueil", "nav_aria": "Pages du site",
        "theme": "Changer de thème", "on_this_page": "Sur cette page",
        "footer": "Butterfly, un langage réactif transpilé en Python. Projet du cours Python avancé.",
        "source": "Code source sur GitHub", "try_program": "Essayer ce programme",
        "home_title": "Butterfly : un langage réactif",
        "cells": "cellules", "depends_on": "dépend de", "nothing": "(rien)",
        "nav_index": "Accueil", "nav_language": "Le langage", "nav_guide": "Guide",
        "nav_reference": "Référence", "nav_examples": "Exemples", "nav_playground": "Essayer",
        "nav_mcp": "Serveur MCP", "nav_internals": "Sous le capot",
        "d_index": "Butterfly est un langage réactif transpilé en Python : on change une valeur, tout ce qui en dépend se met à jour tout seul.",
        "d_language": "Découvrir Butterfly pas à pas : cellules, observateurs, opérateurs, erreurs.",
        "d_guide": "Installer Butterfly, lancer un programme, utiliser la CLI et le REPL.",
        "d_reference": "Lexique, grammaire, priorités et sémantique de Butterfly.",
        "d_examples": "Les cinq programmes d'exemple de Butterfly, avec leur vraie sortie.",
        "d_playground": "Écrivez et exécutez un programme Butterfly directement dans le navigateur.",
        "d_mcp": "Le serveur MCP de Butterfly : une IA y apprend le langage, l'écrit et l'exécute.",
        "d_internals": "Comment Butterfly fonctionne : lexer, parser, analyse, génération de Python.",
        "examples_title": "Exemples",
        "examples_intro": "Ces cinq programmes sont ceux de la spécification. Chacun est exécuté à la construction du site : la sortie affichée est celle du vrai compilateur, comparée à la sortie attendue stockée dans le dépôt.",
        "playground_title": "Essayer",
    },
}  # fmt: skip

#: Title and description of each example in French (English comes from the files).
EXAMPLE_TEXT_FR = {
    "01_expressions": (
        "Expressions",
        "Expressions, priorités et fonctions prédéfinies.",
    ),
    "02_cells": ("Cellules", "Une cellule dérivée (bind) suit ses sources (let)."),
    "03_diamond": (
        "Losange",
        "Un losange de dépendances : b et c dépendent de a, d dépend de b et c. "
        "L'observateur ne voit jamais d'état intermédiaire (b à jour, c pas encore).",
    ),
    "04_loop": (
        "Boucle",
        "Une boucle alimente des cellules ; un observateur réagit au franchissement d'un seuil.",
    ),
    "05_budget": (
        "Budget",
        "Budget mensuel : des dépenses qui changent et une alerte sur ce qui reste.",
    ),
}

#: The language being built (the Markdown blocks do not receive it as an argument).
current_language = "en"

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


# --- Coloring: Butterfly's real lexer -------------------------------------------------


def colorize(source: str) -> str:
    """The program as HTML, coloured from the tokens of Butterfly's lexer."""
    try:
        tokens = list(tokenize(source, comments=True))
    except LexicalError:
        return html.escape(source)  # a deliberately wrong example
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


# --- The code blocks of the Markdown ---------------------------------------------------


def pre(content: str, css_class: str = "") -> str:
    return f'<pre class="code {css_class}"><code>{content}</code></pre>'.replace(
        "  >", ">"
    )


def failure(message: str, source: str) -> SystemExit:
    return SystemExit(f"BUILD ERROR: {message}\n--- program ---\n{source}")


def real_output(source: str) -> tuple[str, str | None]:
    """Really runs the program: (output, possible runtime error)."""
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
    label = UI[current_language]["try_program"]
    return f'<a class="essayer" href="{link}">{label}</a>'


def transcribe_repl(code: str) -> str:
    """Replays a real REPL session and returns the conversation."""
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
        if banner[0]:  # the welcome message is not shown
            banner[0] = False
            return
        lines.extend(text.splitlines())

    run_repl(read_line, write_line)
    return "\n".join(lines)


def process_block(language: str, options: list[str], code: str) -> str:
    """The HTML of a code block, according to its language and options."""
    ui = UI[current_language]
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
                raise failure("the `fly error` block produces no error", code)
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
        lines = [f"{ui['cells']}: {', '.join(analysis.cells)}"]
        for name, deps in analysis.dependencies.items():
            names = ", ".join(sorted(deps)) or ui["nothing"]
            lines.append(f"{name} {ui['depends_on']}: {names}")
        text = "\n".join(lines)
    else:
        raise failure(f"unknown block option: {mode!r}", code)
    return f'<div class="essai">{pre(colorize(code))}{pre(html.escape(text), "sortie")}</div>'


FENCE = re.compile(r"^```(?P<info>[^\n]*)\n(?P<code>.*?)\n```[ \t]*$", re.M | re.S)


def render_markdown(text: str) -> tuple[str, str]:
    """The Markdown as HTML (the code blocks being handled by the compiler)
    and the table of contents."""
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


def root_prefix(language: str) -> str:
    """The path from a page to the root of the site (the French pages are in ``fr/``)."""
    return "" if language == "en" else "../"


def title_and_body(text: str) -> tuple[str, str]:
    first_, _, remainder = text.partition("\n")
    if not first_.startswith("# "):
        raise SystemExit('a page must start with a "# …" title')
    return first_[2:].strip(), remainder.lstrip("\n")


def navigation(language: str, current_page: str) -> str:
    links = []
    for slug in PAGES:
        active = ' aria-current="page"' if slug == current_page else ""
        label = UI[language][f"nav_{slug}"]
        links.append(f'<a href="{slug}.html"{active}>{label}</a>')
    return "\n".join(links)


def other_language(language: str) -> str:
    return "fr" if language == "en" else "en"


def counterpart_url(language: str, slug: str) -> str:
    """The same page in the other language, relative to the current page."""
    return f"fr/{slug}.html" if language == "en" else f"../{slug}.html"


def wrap_page(
    language: str, slug: str, title: str, description: str, body: str, css_class: str
) -> str:
    ui = UI[language]
    template = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    page_title = ui["home_title"] if slug == "index" else f"{title}: Butterfly"
    if language == "fr" and slug != "index":
        page_title = f"{title} : Butterfly"
    other = other_language(language)
    other_url = counterpart_url(language, slug)
    alternate = (
        f'  <link rel="alternate" hreflang="{other}" href="{other_url}">\n'
        f'  <link rel="alternate" hreflang="{language}" href="{slug}.html">'
    )
    switch = (
        f'<a class="lang" href="{other_url}" hreflang="{other}" lang="{other}" '
        f'data-lang="{other}" title="{html.escape(ui["switch_title"], quote=True)}">'
        f"{ui['switch']}</a>"
    )
    replacements = {
        "@@LANG@@": language,
        "@@ALTERNATE@@": alternate,
        "@@LANG_SWITCH@@": switch,
        "@@ROOT@@": root_prefix(language),
        "@@T_SKIP@@": ui["skip"],
        "@@T_HOME_ARIA@@": ui["home_aria"],
        "@@T_NAV_ARIA@@": ui["nav_aria"],
        "@@T_THEME@@": ui["theme"],
        "@@T_FOOTER@@": ui["footer"],
        "@@T_SOURCE@@": ui["source"],
        "@@TITRE@@": html.escape(page_title),
        "@@DESCRIPTION@@": html.escape(description, quote=True),
        "@@NAV@@": navigation(language, slug),
        "@@CLASSE@@": css_class,
        "@@CORPS@@": body,
        "@@DEPOT@@": REPOSITORY,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def document_page(language: str, slug: str, text: str) -> str:
    title, body_md = title_and_body(text)
    body, toc = render_markdown(body_md)
    label = UI[language]["on_this_page"]
    aside = f'<aside class="toc" aria-label="{label}">{toc}</aside>' if toc else ""
    content = (
        '<div class="doc-grid"><article class="doc">'
        f"<h1>{html.escape(title)}</h1>{body}</article>{aside}</div>"
    )
    return wrap_page(
        language, slug, title, UI[language][f"d_{slug}"], content, "page-doc"
    )


def reference_text(language: str) -> str:
    """The language reference: the specification of the repository (English) or its
    French translation, without the draft note."""
    if language == "fr":
        return (CONTENT / "fr" / "reference.md").read_text(encoding="utf-8")
    text = (ROOT / "specification.md").read_text(encoding="utf-8")
    text = re.sub(r"^> Draft of step 1.*\n\n?", "", text, flags=re.M)
    text = text.replace("# Butterfly specification", "# Language reference", 1)
    return text


def example_description(source: str) -> str:
    for line in source.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


def available_examples(language: str) -> list[dict[str, str]]:
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
        description = example_description(source)
        if language == "fr":
            title, description = EXAMPLE_TEXT_FR[file_path.stem]
        examples.append(
            {"name": file_path.stem, "title": title, "source": source,
             "description": description}
        )  # fmt: skip
    return examples


def examples_page(language: str, examples: list[dict[str, str]]) -> str:
    ui = UI[language]
    lines = [f"# {ui['examples_title']}", "", ui["examples_intro"], ""]
    for example in examples:
        lines += [f"## {example['title']}", "", example["description"], ""]
        lines += ["```fly run", example["source"].rstrip("\n"), "```", ""]
    return "\n".join(lines)


def home_page(language: str, examples: list[dict[str, str]]) -> str:
    template = (TEMPLATES / language / "index.html").read_text(encoding="utf-8")
    diamond = next(e for e in examples if e["name"] == "03_diamond")
    budget = next(e for e in examples if e["name"] == "05_budget")
    hero_program = "\n".join(
        line
        for line in diamond["source"].splitlines()
        if not line.startswith("#") and not line.startswith("print d;")
    )
    hero_program = re.sub(r"\n(?:a = \d+;\n?)+$", "\n", hero_program).strip("\n")
    output, _ = real_output(budget["source"])
    replacements = {
        "@@ROOT@@": root_prefix(language),
        "@@PROGRAMME_HERO@@": colorize(hero_program),
        "@@PROGRAMME_BUDGET@@": colorize(budget["source"].rstrip("\n")),
        "@@SORTIE_BUDGET@@": html.escape(output.rstrip("\n")),
        "@@LIEN_BUDGET@@": playground_link(budget["source"]),
        "@@DEPOT@@": REPOSITORY,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return wrap_page(
        language,
        "index",
        "Butterfly",
        UI[language]["d_index"],
        template,
        "page-accueil",
    )


def playground_page(language: str, examples: list[dict[str, str]]) -> str:
    template = (TEMPLATES / language / "playground.html").read_text(encoding="utf-8")
    data = json.dumps(examples, ensure_ascii=False).replace("</", "<\\/")
    template = template.replace("@@EXEMPLES_JSON@@", data)
    template = template.replace("@@ROOT@@", root_prefix(language))
    return wrap_page(
        language,
        "playground",
        UI[language]["playground_title"],
        UI[language]["d_playground"],
        template,
        "page-playground",
    )


# --- Assembly --------------------------------------------------------------------------


def compiler_archive() -> None:
    """The ``butterfly`` package as a zip: the playground runs it with Pyodide."""
    with zipfile.ZipFile(DIST / "butterfly.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted((ROOT / "butterfly").glob("*.py")):
            archive.write(file_path, f"butterfly/{file_path.name}")


def build_language(language: str) -> int:
    """Builds the pages of one language and returns their number."""
    global current_language
    current_language = language
    folder = DIST if language == "en" else DIST / language
    folder.mkdir(parents=True, exist_ok=True)
    examples = available_examples(language)
    pages: dict[str, str] = {
        "index": home_page(language, examples),
        "playground": playground_page(language, examples),
        "examples": document_page(
            language, "examples", examples_page(language, examples)
        ),
        "reference": document_page(language, "reference", reference_text(language)),
    }
    for slug in ("language", "guide", "mcp", "internals"):
        text = (CONTENT / language / f"{slug}.md").read_text(encoding="utf-8")
        pages[slug] = document_page(language, slug, text)
    for slug, content in pages.items():
        (folder / f"{slug}.html").write_text(content, encoding="utf-8")
    return len(pages)


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(STATIC, DIST / "static")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    count = sum(build_language(language) for language in LANGUAGES)
    compiler_archive()
    print(f"site built: {count} pages in {DIST.relative_to(ROOT)}/")


if __name__ == "__main__":
    build()
