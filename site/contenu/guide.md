# Guide d'utilisation

Ce guide explique comment installer Butterfly, lancer un programme et utiliser les outils fournis. Pour apprendre le langage lui-même, voir [Le langage](langage.html).

## Installer

Il faut Python 3.12 ou plus et [uv](https://docs.astral.sh/uv/), qui gère l'environnement et les dépendances.

```bash
git clone https://github.com/bilkl/butterfly.git
cd butterfly
uv sync
```

Vérifiez l'installation :

```bash
uv run python -m butterfly --version
```

Si vous préférez ne rien installer, le [bac à sable](playground.html) exécute Butterfly dans votre navigateur.

## Votre premier programme

Écrivez ceci dans un fichier `bonjour.fly` :

```fly run
soit nom = "monde";
affiche "Bonjour,", nom;
```

Puis exécutez-le :

```bash
uv run python -m butterfly run bonjour.fly
```

## Les commandes

Toutes les commandes prennent un fichier `.fly`, ou `-` pour lire le programme sur l'entrée standard.

| Commande | Ce qu'elle fait |
|---|---|
| `run` | exécute le programme |
| `check` | vérifie le programme sans l'exécuter, et signale toutes les erreurs |
| `transpile` | affiche le code Python généré |
| `format` | affiche le programme dans sa présentation canonique (`-w` réécrit le fichier) |
| `tokens` | affiche les tokens, avec leur position |
| `ast` | affiche l'arbre syntaxique |
| `repl` | ouvre une session interactive |

Par exemple, pour reformater un fichier en place :

```bash
uv run python -m butterfly format -w bonjour.fly
```

Le code de retour est `0` si tout va bien, `1` si le programme a une erreur, et `2` si le fichier est illisible.

## Comprendre un message d'erreur

Chaque message indique le genre de l'erreur, sa position, ce qui ne va pas, puis la ligne fautive avec un repère sous la colonne :

```fly erreur
soit total = 0;
si total > 10 {
    affiche total;
}
affiche resultat;
```

Quelques messages fréquents et leur remède :

| Message | Ce qu'il faut faire |
|---|---|
| `';' attendu à la fin de l'instruction` | ajouter le `;` oublié (le repère est juste après la dernière instruction) |
| `nom 'x' non déclaré` | déclarer `x` avec `soit` ou `lie` **avant** de l'utiliser |
| `'x' est une cellule dérivée (lie)` | une cellule `lie` ne se modifie pas : modifiez ses sources |
| `'x' est déjà déclaré` | choisir un autre nom : un nom ne peut pas en masquer un autre |
| `les comparaisons ne s'enchaînent pas` | écrire `a < b et b < c` |
| `division par zéro` | tester le diviseur avant de diviser |

## Le REPL

Le REPL garde l'état d'une ligne à l'autre. Une expression seule est affichée directement, et une entrée sur plusieurs lignes est lue jusqu'à l'accolade fermante.

```repl
soit a = 2;
lie double = a * 2;
double
a = 10;
double
1 + 2
quand double { affiche "double change :", double; }
a = 11;
```

Les commandes `:aide`, `:source` (le programme accumulé), `:reinit` et `:quitter` sont disponibles.

## Utiliser Butterfly depuis Python

La façade `butterfly.compilateur` est tout ce qu'il faut :

```python
from butterfly.compilateur import executer

resultat = executer("soit a = 2; affiche a * 21;")
print(resultat.sortie)  # 42
print(resultat.ok)  # True
```

Une erreur d'exécution est renvoyée dans `resultat.erreur`, avec ce qui a été affiché avant. Une erreur de compilation lève `ErreurCompilation`, qui contient toutes les erreurs trouvées.

## Lancer les tests

```bash
uv run pytest                                   # tous les tests
uv run mypy butterfly serveur_butterfly tests   # typage strict
uv run ruff check .                             # style
```

La spécification est exécutable : un test lit le tableau d'erreurs de la [référence](reference.html) et vérifie que chaque programme fautif produit exactement le message annoncé.

## Brancher une IA

Le dépôt contient un serveur MCP qui permet à une IA d'apprendre Butterfly, de vérifier ses programmes et de les exécuter. Tout est expliqué sur la page [Serveur MCP](mcp.html).
