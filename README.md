# Butterfly

Un langage de programmation **réactif**, transpilé en Python, avec son serveur MCP.

Dans Butterfly, on change une seule valeur et tout ce qui en dépend se met à jour tout seul : c'est l'effet papillon.

```
soit prix = 20;
soit quantite = 3;
lie total = prix * quantite;     # total vaut TOUJOURS prix * quantite

quand total {                    # s'exécute chaque fois que total change
    affiche "nouveau total :", total;
}

quantite = 5;                    # affiche : nouveau total : 100
prix = prix + 5;                 # affiche : nouveau total : 125
```

- `soit` crée une cellule source, que l'on peut modifier.
- `lie` crée une cellule dérivée, toujours égale à sa formule.
- `quand` crée un observateur, exécuté quand la valeur d'une cellule change.

Le site (guide, référence, exemples et bac à sable dans le navigateur) : **https://bilkl.github.io/butterfly/**

La spécification complète est dans [`specification.md`](specification.md).

## Installation

Il faut Python 3.12 ou plus et [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/bilkl/butterfly.git
cd butterfly
uv sync
```

## Utilisation

```bash
uv run python -m butterfly run exemples/02_cellules.fly       # exécuter
uv run python -m butterfly check programme.fly                # vérifier sans exécuter
uv run python -m butterfly transpile programme.fly            # voir le Python généré
uv run python -m butterfly format programme.fly               # mise en forme canonique
uv run python -m butterfly tokens programme.fly               # les tokens
uv run python -m butterfly ast programme.fly                  # l'arbre syntaxique
uv run python -m butterfly repl                               # session interactive
```

Les erreurs sont toutes signalées d'un coup, avec la ligne fautive soulignée :

```
Erreur sémantique (ligne 3, colonne 1) : 'b' est une cellule dérivée (lie), on ne peut pas lui affecter de valeur
  3 | b = 2;
    | ^
```

## Serveur MCP

Le serveur permet à une IA qui ne connaît pas Butterfly de l'apprendre seule : lire la spécification et les exemples, vérifier, corriger, exécuter.

| Outil | Rôle |
|---|---|
| `tokenize` | découpe un programme en tokens |
| `parse` | renvoie l'arbre syntaxique en JSON |
| `check` | vérifie sans exécuter, toutes les erreurs d'un coup |
| `transpile` | renvoie le Python généré |
| `format` | présentation canonique |
| `run` | exécute dans un processus borné (délai, sortie, mémoire) |

Il expose aussi les resources `butterfly://specification` et `butterfly://exemples`, et les prompts `ecrire_programme` et `corriger_programme`.

Pour le brancher sur Claude Code (remplacer le chemin) :

```bash
claude mcp add butterfly -- uv --directory /chemin/absolu/vers/butterfly run python -m serveur_butterfly
```

Un exemple de configuration est dans [`mcp.exemple.json`](mcp.exemple.json).

## Tests et qualité

```bash
uv run pytest            # 365 tests
uv run mypy butterfly serveur_butterfly tests   # typage strict
uv run ruff check .      # style
```

La spécification est exécutable : un test lit son tableau d'erreurs et vérifie que chaque programme fautif produit exactement le message annoncé.

## Organisation

```
butterfly/            le compilateur : lexer, parser, sémantique, générateur, CLI, REPL
serveur_butterfly/    le serveur MCP et son bac à sable
exemples/             cinq programmes .fly et leur sortie attendue (.attendu)
specification.md      la spécification du langage
tests/                les tests du langage et du serveur
site/                 le site web (build.py génère les pages depuis le Markdown)
```

La chaîne de compilation est écrite à la main :

```
texte → lexer → tokens → parser → arbre → analyse → arbre vérifié → générateur → Python
```
