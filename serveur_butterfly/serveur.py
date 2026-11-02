"""Le serveur MCP de Butterfly.

Il donne à une IA qui ne connaît pas Butterfly les moyens de l'apprendre seule :
lire sa spécification et ses exemples (resources), découper, analyser, vérifier,
transpiler, formater et exécuter un programme (outils), et suivre une méthode
(prompts). Les outils ne réimplémentent rien : ils appellent la façade du
langage (``butterfly.compilateur``) et convertissent le résultat.

Pas de ``from __future__ import annotations`` ici : le SDK inspecte les
annotations à l'exécution pour construire les schémas des outils.
"""

import time
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from mcp_types import ToolAnnotations
from pydantic import Field

from butterfly.compilateur import compiler, parser, transpiler, verifier
from butterfly.erreurs import ErreurCompilation, ErreurLexicale
from butterfly.formateur import formater
from butterfly.lexer import tokenize
from butterfly.noeuds import noeud_vers_dict
from serveur_butterfly.bac_a_sable import executer_isole, lire_erreur_execution
from serveur_butterfly.conversion import (
    cellules_json,
    erreur_json,
    erreurs_json,
    token_json,
)
from serveur_butterfly.schemas import (
    ErreurJSON,
    ResultatCheck,
    ResultatFormat,
    ResultatParse,
    ResultatRun,
    ResultatTokenize,
    ResultatTranspile,
    Statut,
    TokenJSON,
)

RACINE = Path(__file__).resolve().parent.parent
SPECIFICATION = RACINE / "specification.md"
EXEMPLES = RACINE / "exemples"

INSTRUCTIONS = """\
Ce serveur te donne accès à Butterfly, un langage de programmation réactif que tu \
ne connais pas encore (fichiers .fly). Dans Butterfly, une cellule dérivée (`lie`) \
vaut toujours sa formule : quand une cellule source (`soit`) change, tout ce qui en \
dépend se met à jour tout seul.

Procède ainsi :
1. Lis la resource `butterfly://specification` : lexique, grammaire, priorités, \
sémantique. Puis lis au moins un exemple (liste dans `butterfly://exemples`).
2. Écris ton programme.
3. Appelle `check` : il renvoie TOUTES les erreurs d'un coup, chacune avec sa ligne, \
sa colonne et la ligne fautive soulignée. Corrige-les et recommence jusqu'à `ok`.
4. Appelle `run` et compare la sortie à ce que tu attendais.
5. Termine par `format` pour obtenir la présentation canonique.

Outils : `tokenize` (les mots), `parse` (l'arbre), `check` (vérifie sans exécuter), \
`transpile` (le Python généré), `format`, `run` (exécute, dans un processus borné). \
Une erreur dans TON programme est une réponse normale (`ok: false`), pas un échec de \
l'outil.\
"""

mcp = MCPServer("butterfly", instructions=INSTRUCTIONS)

LECTURE_SEULE = ToolAnnotations(
    read_only_hint=True, idempotent_hint=True, open_world_hint=False
)

Source = Annotated[
    str, Field(description="Code source d'un programme Butterfly (.fly)")
]


# --- Outils d'analyse ---------------------------------------------------------


@mcp.tool(name="tokenize", annotations=LECTURE_SEULE)
def outil_tokenize(source: Source) -> ResultatTokenize:
    """Découpe un programme Butterfly en tokens (mots-clés, noms, nombres, symboles),
    avec leur ligne et leur colonne. En cas d'erreur lexicale (caractère inconnu,
    texte non fermé, nombre décimal), renvoie les tokens lus avant l'erreur."""
    tokens: list[TokenJSON] = []
    try:
        for token in tokenize(source):
            tokens.append(token_json(token))
    except ErreurLexicale as erreur:
        return {"ok": False, "tokens": tokens, "erreurs": [erreur_json(erreur, source)]}
    return {"ok": True, "tokens": tokens, "erreurs": []}


@mcp.tool(name="parse", annotations=LECTURE_SEULE)
def outil_parse(source: Source) -> ResultatParse:
    """Analyse la SYNTAXE d'un programme Butterfly et renvoie son arbre syntaxique
    en JSON (chaque nœud a une clé "type"). Ne fait pas l'analyse sémantique : un
    nom non déclaré n'est pas détecté ici, utilise `check` pour cela. Signale toutes
    les erreurs de syntaxe trouvées."""
    try:
        programme = parser(source)
    except ErreurCompilation as erreur:
        return {
            "ok": False,
            "arbre": None,
            "erreurs": erreurs_json(erreur.erreurs, source),
        }
    return {"ok": True, "arbre": noeud_vers_dict(programme), "erreurs": []}


@mcp.tool(name="check", annotations=LECTURE_SEULE)
def outil_check(source: Source) -> ResultatCheck:
    """Vérifie un programme Butterfly SANS l'exécuter : syntaxe, noms déclarés avant
    usage, cellules dérivées non modifiées, appels de fonctions. Renvoie toutes les
    erreurs d'un coup (genre, message, ligne, colonne, ligne fautive soulignée).
    Si tout va bien, renvoie aussi les cellules du programme."""
    try:
        analyse = compiler(source)
    except ErreurCompilation as erreur:
        return {
            "ok": False,
            "erreurs": erreurs_json(erreur.erreurs, source),
            "cellules": [],
        }
    return {"ok": True, "erreurs": [], "cellules": cellules_json(analyse)}


# --- Outils de transformation -------------------------------------------------


@mcp.tool(name="transpile", annotations=LECTURE_SEULE)
def outil_transpile(source: Source) -> ResultatTranspile:
    """Traduit un programme Butterfly en Python (le code est exécutable avec le
    paquet `butterfly`). Utile pour comprendre comment les cellules dérivées et les
    observateurs sont propagés. Renvoie les erreurs si le programme est faux."""
    try:
        return {"ok": True, "python": transpiler(source), "erreurs": []}
    except ErreurCompilation as erreur:
        return {
            "ok": False,
            "python": None,
            "erreurs": erreurs_json(erreur.erreurs, source),
        }


@mcp.tool(name="format", annotations=LECTURE_SEULE)
def outil_format(source: Source) -> ResultatFormat:
    """Réécrit un programme Butterfly dans sa présentation canonique (indentation de
    4 espaces, parenthèses minimales, commentaires conservés). Le résultat donne la
    même sortie que l'original. Ne nécessite que la syntaxe correcte."""
    try:
        return {"ok": True, "source": formater(source), "erreurs": []}
    except ErreurCompilation as erreur:
        return {
            "ok": False,
            "source": None,
            "erreurs": erreurs_json(erreur.erreurs, source),
        }


# --- L'outil d'exécution ------------------------------------------------------


@mcp.tool(
    name="run",
    annotations=ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def outil_run(
    source: Source,
    delai: Annotated[
        float,
        Field(ge=0.1, le=5.0, description="Durée maximale d'exécution, en secondes"),
    ] = 2.0,
) -> ResultatRun:
    """Exécute un programme Butterfly et renvoie ce qu'il affiche. Le programme est
    d'abord vérifié (erreurs de compilation signalées sans exécution), puis exécuté
    dans un processus séparé, limité en temps, en sortie (64 Kio) et en mémoire.
    Statuts : ok, erreur_compilation, erreur_execution (avec la ligne), delai_depasse,
    sortie_tronquee, memoire_depassee, erreur_interne. Ce qui a été affiché avant une
    erreur d'exécution est conservé dans `sortie`."""
    debut = time.monotonic()
    erreurs = verifier(source)
    if erreurs:
        return _reponse_run(
            "erreur_compilation", "", erreurs_json(erreurs, source), debut
        )
    isole = executer_isole(source, delai)
    statut: Statut = isole.statut
    erreurs_run: list[ErreurJSON] = []
    if statut == "erreur_execution":
        trouvee = lire_erreur_execution(isole.erreur)
        if trouvee is not None:
            ligne, message = trouvee
            erreurs_run.append(
                {
                    "genre": "Erreur d'exécution",
                    "message": message,
                    "ligne": ligne,
                    "colonne": None,
                    "contexte": isole.erreur.strip(),
                }
            )
    elif statut == "erreur_interne":
        erreurs_run.append(
            {
                "genre": "Erreur interne",
                "message": "l'exécution a échoué sans erreur Butterfly identifiable",
                "ligne": None,
                "colonne": None,
                "contexte": isole.erreur.strip()[-2000:],
            }
        )
    return _reponse_run(statut, isole.sortie, erreurs_run, debut)


def _reponse_run(
    statut: Statut, sortie: str, erreurs: list[ErreurJSON], debut: float
) -> ResultatRun:
    return {
        "statut": statut,
        "sortie": sortie,
        "erreurs": erreurs,
        "duree_secondes": round(time.monotonic() - debut, 3),
    }


# --- Resources ----------------------------------------------------------------


def exemples_disponibles() -> dict[str, Path]:
    """La liste FERMÉE des exemples : nom → fichier. Un nom reçu de l'IA n'est
    jamais utilisé pour construire un chemin, seulement cherché dans cette liste."""
    return {fichier.stem: fichier for fichier in sorted(EXEMPLES.glob("*.fly"))}


def _exemple(nom: str) -> Path:
    fichier = exemples_disponibles().get(nom)
    if fichier is None:
        raise ResourceNotFoundError(f"exemple inconnu : {nom!r}")
    return fichier


def _description(fichier: Path) -> str:
    """La première ligne de commentaire du programme, sans le « # »."""
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if ligne.startswith("#"):
            return ligne.lstrip("# ").strip()
    return ""


@mcp.resource(
    "butterfly://specification",
    name="specification",
    description=(
        "Spécification complète de Butterfly : lexique, grammaire EBNF, priorités des "
        "opérateurs, sémantique (cellules, propagation, observateurs), erreurs. À lire "
        "en premier."
    ),
    mime_type="text/markdown",
)
def specification() -> str:
    return SPECIFICATION.read_text(encoding="utf-8")


@mcp.resource(
    "butterfly://exemples",
    name="index_exemples",
    description="La liste des programmes d'exemple, avec leur URI et leur description.",
    mime_type="text/markdown",
)
def index_exemples() -> str:
    lignes = ["# Programmes d'exemple Butterfly", ""]
    for nom, fichier in exemples_disponibles().items():
        lignes.append(
            f"- `{nom}` : {_description(fichier)}\n"
            f"  - programme : `butterfly://exemples/{nom}`\n"
            f"  - sortie attendue : `butterfly://exemples/{nom}/attendu`"
        )
    return "\n".join(lignes) + "\n"


@mcp.resource(
    "butterfly://exemples/{nom}",
    name="exemple",
    description="Code source d'un programme d'exemple (voir butterfly://exemples).",
    mime_type="text/plain",
)
def exemple(nom: str) -> str:
    return _exemple(nom).read_text(encoding="utf-8")


@mcp.resource(
    "butterfly://exemples/{nom}/attendu",
    name="exemple_attendu",
    description="La sortie exacte d'un programme d'exemple.",
    mime_type="text/plain",
)
def exemple_attendu(nom: str) -> str:
    return _exemple(nom).with_suffix(".attendu").read_text(encoding="utf-8")


# --- Prompts ------------------------------------------------------------------


@mcp.prompt(
    name="ecrire_programme",
    description=(
        "Écrire, vérifier et exécuter un programme Butterfly pour une tâche donnée."
    ),
)
def ecrire_programme(
    tache: Annotated[str, Field(description="Ce que le programme doit faire")],
) -> str:
    return f"""\
Écris un programme dans le langage Butterfly qui réalise la tâche suivante :

{tache}

Tu ne connais pas Butterfly. Procède ainsi :
1. Lis la resource butterfly://specification, puis au moins un exemple (la liste est
   dans butterfly://exemples).
2. Écris le programme. Rappel : `soit` crée une cellule modifiable, `lie` une cellule
   toujours égale à sa formule, `quand` un observateur ; on déclare avant d'utiliser.
3. Appelle l'outil `check`. S'il signale des erreurs, corrige-les (chacune donne sa
   ligne et sa colonne) et recommence jusqu'à `ok`.
4. Appelle l'outil `run`, et compare la sortie à ce que tu attendais. Si ce n'est pas
   le cas, explique pourquoi et corrige.
5. Termine par `format`, puis donne le programme final et sa sortie.
"""


@mcp.prompt(
    name="corriger_programme",
    description="Corriger un programme Butterfly d'après les erreurs signalées.",
)
def corriger_programme(
    source: Annotated[str, Field(description="Le programme à corriger")],
    erreurs: Annotated[
        str, Field(description="Les erreurs signalées (message de check ou de run)")
    ],
) -> str:
    return f"""\
Ce programme Butterfly contient des erreurs :

```
{source}
```

Erreurs signalées :

```
{erreurs}
```

Corrige-le. Si tu as un doute sur une règle du langage, consulte la resource
butterfly://specification. Vérifie ta correction avec l'outil `check` (jusqu'à `ok`),
puis exécute-la avec `run`. Explique en une phrase chaque correction.
"""
