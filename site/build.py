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

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from butterfly.compilateur import compiler, executer, parser, transpiler, verifier  # noqa: E402
from butterfly.erreurs import ErreurCompilation, ErreurLexicale, contexte  # noqa: E402
from butterfly.lexer import tokenize  # noqa: E402
from butterfly.noeuds import afficher_arbre  # noqa: E402
from butterfly.repl import lancer_repl  # noqa: E402
from butterfly.tokens import TypeToken  # noqa: E402

SITE = RACINE / "site"
CONTENU = SITE / "contenu"
STATIC = SITE / "static"
TEMPLATES = SITE / "templates"
DIST = SITE / "dist"
EXEMPLES = RACINE / "exemples"
DEPOT = "https://github.com/bilkl/butterfly"

#: (fichier, libellé dans la navigation)
PAGES = [
    ("index", "Accueil"),
    ("langage", "Le langage"),
    ("guide", "Guide"),
    ("reference", "Référence"),
    ("exemples", "Exemples"),
    ("playground", "Essayer"),
    ("mcp", "Serveur MCP"),
    ("compilateur", "Sous le capot"),
]

T = TypeToken
CLASSES = {
    T.SOIT: "src",
    T.LIE: "der",
    T.QUAND: "obs",
    T.SI: "kw", T.SINON: "kw", T.POUR: "kw", T.DANS: "kw", T.AFFICHE: "kw",
    T.VRAI: "kw", T.FAUX: "kw", T.ET: "kw", T.OU: "kw", T.NON: "kw",
    T.ENTIER: "num",
    T.TEXTE: "str",
    T.COMMENTAIRE: "com",
}  # fmt: skip


# --- Coloration : le vrai lexer de Butterfly ----------------------------------------


def colorer(source: str) -> str:
    """Le programme en HTML, coloré d'après les tokens du lexer de Butterfly."""
    try:
        tokens = list(tokenize(source, commentaires=True))
    except ErreurLexicale:
        return html.escape(source)  # un exemple volontairement faux
    debuts = [0]
    for i, caractere in enumerate(source):
        if caractere == "\n":
            debuts.append(i + 1)
    morceaux: list[str] = []
    curseur = 0
    for token in tokens:
        if token.type is T.FIN:
            break
        debut = debuts[token.position.ligne - 1] + token.position.colonne - 1
        fin = debut + len(token.lexeme)
        morceaux.append(html.escape(source[curseur:debut]))
        texte = html.escape(source[debut:fin])
        classe = CLASSES.get(token.type)
        morceaux.append(f'<span class="{classe}">{texte}</span>' if classe else texte)
        curseur = fin
    morceaux.append(html.escape(source[curseur:]))
    return "".join(morceaux)


# --- Les blocs de code du Markdown ----------------------------------------------------


def pre(contenu: str, classe: str = "") -> str:
    return f'<pre class="code {classe}"><code>{contenu}</code></pre>'.replace(
        "  >", ">"
    )


def echec(message: str, source: str) -> SystemExit:
    return SystemExit(f"ERREUR DE BUILD : {message}\n--- programme ---\n{source}")


def sortie_reelle(source: str) -> tuple[str, str | None]:
    """Exécute vraiment le programme : (sortie, erreur d'exécution éventuelle)."""
    try:
        resultat = executer(source)
    except ErreurCompilation as erreur:
        raise echec(f"le bloc `fly run` ne compile pas :\n{erreur}", source) from erreur
    erreur_texte = contexte(resultat.erreur, source) if resultat.erreur else None
    return resultat.sortie, erreur_texte


def lien_playground(source: str) -> str:
    lien = "playground.html#code=" + quote(source, safe="")
    return f'<a class="essayer" href="{lien}">Essayer ce programme</a>'


def transcrire_repl(code: str) -> str:
    """Rejoue une vraie session du REPL et renvoie la conversation."""
    entrees = iter(code.splitlines())
    lignes: list[str] = []
    banniere = [True]

    def lire(invite: str) -> str:
        try:
            ligne = next(entrees)
        except StopIteration:
            raise EOFError from None
        lignes.append(f"{invite}{ligne}")
        return ligne

    def ecrire(texte: str) -> None:
        if banniere[0]:  # le message d'accueil n'est pas montré
            banniere[0] = False
            return
        lignes.extend(texte.splitlines())

    lancer_repl(lire, ecrire)
    return "\n".join(lignes)


def traiter_bloc(langue: str, options: list[str], code: str) -> str:
    """Le HTML d'un bloc de code, selon sa langue et ses options."""
    if langue == "repl":
        return pre(html.escape(transcrire_repl(code)), "repl")
    if langue != "fly":
        return pre(html.escape(code), f"lang-{langue}" if langue else "")
    mode = options[0] if options else ""
    if mode == "":
        return pre(colorer(code))
    if mode == "run":
        sortie, erreur = sortie_reelle(code)
        blocs = pre(colorer(code))
        if sortie:
            blocs += pre(html.escape(sortie.rstrip("\n")), "sortie")
        if erreur:
            blocs += pre(html.escape(erreur), "sortie erreur")
        return f'<div class="essai">{blocs}{lien_playground(code)}</div>'
    if mode == "erreur":
        erreurs = verifier(code)
        if erreurs:
            texte = "\n".join(contexte(e, code) for e in erreurs)
        else:
            _, texte_erreur = sortie_reelle(code)
            if texte_erreur is None:
                raise echec("le bloc `fly erreur` ne produit aucune erreur", code)
            texte = texte_erreur
        return f'<div class="essai">{pre(colorer(code))}{pre(html.escape(texte), "sortie erreur")}</div>'
    if mode == "tokens":
        texte = "\n".join(repr(t) for t in tokenize(code))
    elif mode == "ast":
        texte = afficher_arbre(parser(code))
    elif mode == "python":
        texte = transpiler(code)
    elif mode == "analyse":
        analyse = compiler(code)
        lignes = [f"cellules : {', '.join(analyse.cellules)}"]
        for nom, deps in analyse.dependances.items():
            lignes.append(f"{nom} dépend de : {', '.join(sorted(deps)) or '(rien)'}")
        texte = "\n".join(lignes)
    else:
        raise echec(f"option de bloc inconnue : {mode!r}", code)
    return f'<div class="essai">{pre(colorer(code))}{pre(html.escape(texte), "sortie")}</div>'


FENCE = re.compile(r"^```(?P<info>[^\n]*)\n(?P<code>.*?)\n```[ \t]*$", re.M | re.S)


def rendre_markdown(texte: str) -> tuple[str, str]:
    """Le Markdown en HTML (les blocs de code étant traités par le compilateur)
    et la table des matières."""
    blocs: list[str] = []

    def remplacer(trouve: re.Match[str]) -> str:
        mots = trouve.group("info").split()
        langue = mots[0] if mots else ""
        blocs.append(traiter_bloc(langue, mots[1:], trouve.group("code")))
        return f"\n\n@@BLOC{len(blocs) - 1}@@\n\n"

    texte = FENCE.sub(remplacer, texte)
    md = markdown.Markdown(
        extensions=["tables", "toc", "sane_lists"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
    )
    corps = md.convert(texte)
    for i, bloc in enumerate(blocs):
        corps = corps.replace(f"<p>@@BLOC{i}@@</p>", bloc)
    return corps, getattr(md, "toc", "")


# --- Pages -----------------------------------------------------------------------------


def titre_et_corps(texte: str) -> tuple[str, str]:
    premiere, _, reste = texte.partition("\n")
    if not premiere.startswith("# "):
        raise SystemExit("une page doit commencer par un titre « # … »")
    return premiere[2:].strip(), reste.lstrip("\n")


def navigation(courante: str) -> str:
    liens = []
    for slug, libelle in PAGES:
        actif = ' aria-current="page"' if slug == courante else ""
        liens.append(f'<a href="{slug}.html"{actif}>{libelle}</a>')
    return "\n".join(liens)


def habiller(slug: str, titre: str, description: str, corps: str, classe: str) -> str:
    modele = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    titre_page = (
        "Butterfly : un langage réactif" if slug == "index" else f"{titre} : Butterfly"
    )
    remplacements = {
        "@@TITRE@@": html.escape(titre_page),
        "@@DESCRIPTION@@": html.escape(description, quote=True),
        "@@NAV@@": navigation(slug),
        "@@CLASSE@@": classe,
        "@@CORPS@@": corps,
        "@@DEPOT@@": DEPOT,
    }
    for cle, valeur in remplacements.items():
        modele = modele.replace(cle, valeur)
    return modele


def page_document(slug: str, texte: str, description: str) -> str:
    titre, corps_md = titre_et_corps(texte)
    corps, toc = rendre_markdown(corps_md)
    aside = (
        f'<aside class="toc" aria-label="Sur cette page">{toc}</aside>' if toc else ""
    )
    contenu = (
        '<div class="doc-grid"><article class="doc">'
        f"<h1>{html.escape(titre)}</h1>{corps}</article>{aside}</div>"
    )
    return habiller(slug, titre, description, contenu, "page-doc")


def texte_reference() -> str:
    """La spécification du dépôt, sans la note de brouillon."""
    texte = (RACINE / "specification.md").read_text(encoding="utf-8")
    texte = re.sub(r"^> Brouillon de l'étape 1.*\n\n?", "", texte, flags=re.M)
    texte = texte.replace("# Spécification de Butterfly", "# Référence du langage", 1)
    return texte


def description_exemple(source: str) -> str:
    for ligne in source.splitlines():
        if ligne.startswith("#"):
            return ligne.lstrip("# ").strip()
    return ""


def exemples_disponibles() -> list[dict[str, str]]:
    exemples = []
    for fichier in sorted(EXEMPLES.glob("*.fly")):
        source = fichier.read_text(encoding="utf-8")
        attendu = fichier.with_suffix(".attendu").read_text(encoding="utf-8")
        sortie, erreur = sortie_reelle(source)
        if erreur or sortie != attendu:
            raise echec(f"{fichier.name} ne produit pas sa sortie attendue", source)
        titre = fichier.stem.split("_", 1)[1].replace("_", " ").capitalize()
        exemples.append(
            {"nom": fichier.stem, "titre": titre, "source": source,
             "description": description_exemple(source)}
        )  # fmt: skip
    return exemples


def page_exemples(exemples: list[dict[str, str]]) -> str:
    lignes = [
        "# Exemples",
        "",
        "Ces cinq programmes sont ceux de la spécification. Chacun est exécuté à la "
        "construction du site : la sortie affichée est celle du vrai compilateur, "
        "et elle est comparée à la sortie attendue du dépôt.",
        "",
    ]
    for exemple in exemples:
        lignes += [f"## {exemple['titre']}", "", exemple["description"], ""]
        lignes += ["```fly run", exemple["source"].rstrip("\n"), "```", ""]
    return "\n".join(lignes)


def page_accueil(exemples: list[dict[str, str]]) -> str:
    modele = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    losange = next(e for e in exemples if e["nom"] == "03_losange")
    budget = next(e for e in exemples if e["nom"] == "05_budget")
    programme_hero = "\n".join(
        ligne
        for ligne in losange["source"].splitlines()
        if not ligne.startswith("#") and not ligne.startswith("affiche d;")
    )
    programme_hero = re.sub(r"\n(?:a = \d+;\n?)+$", "\n", programme_hero).strip("\n")
    sortie, _ = sortie_reelle(budget["source"])
    remplacements = {
        "@@PROGRAMME_HERO@@": colorer(programme_hero),
        "@@PROGRAMME_BUDGET@@": colorer(budget["source"].rstrip("\n")),
        "@@SORTIE_BUDGET@@": html.escape(sortie.rstrip("\n")),
        "@@LIEN_BUDGET@@": lien_playground(budget["source"]),
        "@@DEPOT@@": DEPOT,
    }
    for cle, valeur in remplacements.items():
        modele = modele.replace(cle, valeur)
    return habiller(
        "index",
        "Butterfly",
        "Butterfly est un langage réactif transpilé en Python : on change une valeur, "
        "tout ce qui en dépend se met à jour tout seul.",
        modele,
        "page-accueil",
    )


def page_playground(exemples: list[dict[str, str]]) -> str:
    modele = (TEMPLATES / "playground.html").read_text(encoding="utf-8")
    donnees = json.dumps(exemples, ensure_ascii=False).replace("</", "<\\/")
    modele = modele.replace("@@EXEMPLES_JSON@@", donnees)
    return habiller(
        "playground",
        "Essayer",
        "Écrivez et exécutez un programme Butterfly directement dans le navigateur.",
        modele,
        "page-playground",
    )


# --- Assemblage ------------------------------------------------------------------------


def archive_du_compilateur() -> None:
    """Le paquet ``butterfly`` en zip : le playground l'exécute avec Pyodide."""
    with zipfile.ZipFile(DIST / "butterfly.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for fichier in sorted((RACINE / "butterfly").glob("*.py")):
            archive.write(fichier, f"butterfly/{fichier.name}")


def construire() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copytree(STATIC, DIST / "static")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    exemples = exemples_disponibles()
    pages: dict[str, str] = {
        "index": page_accueil(exemples),
        "playground": page_playground(exemples),
        "exemples": page_document(
            "exemples",
            page_exemples(exemples),
            "Les cinq programmes d'exemple de Butterfly, avec leur vraie sortie.",
        ),
        "reference": page_document(
            "reference",
            texte_reference(),
            "Lexique, grammaire, priorités et sémantique de Butterfly.",
        ),
    }
    descriptions = {
        "langage": "Découvrir Butterfly pas à pas : cellules, observateurs, opérateurs, erreurs.",
        "guide": "Installer Butterfly, lancer un programme, utiliser la CLI et le REPL.",
        "mcp": "Le serveur MCP de Butterfly : une IA y apprend le langage, l'écrit et l'exécute.",
        "compilateur": "Comment Butterfly fonctionne : lexer, parser, analyse, génération de Python.",
    }
    for slug, description in descriptions.items():
        texte = (CONTENU / f"{slug}.md").read_text(encoding="utf-8")
        pages[slug] = page_document(slug, texte, description)

    for slug, contenu in pages.items():
        (DIST / f"{slug}.html").write_text(contenu, encoding="utf-8")
    archive_du_compilateur()
    print(f"site construit : {len(pages)} pages dans {DIST.relative_to(RACINE)}/")


if __name__ == "__main__":
    construire()
