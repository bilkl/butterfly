# Le serveur MCP

Butterfly est un langage que **aucune IA ne connaît**. Le serveur MCP lui donne les moyens de l'apprendre toute seule : lire la spécification et les exemples, vérifier ses programmes, se corriger d'après les erreurs, puis les exécuter. L'IA n'a besoin de rien d'autre que ce serveur.

[MCP](https://modelcontextprotocol.io) (Model Context Protocol) est un protocole ouvert qui permet à une application d'IA (Claude Code, Claude Desktop, un éditeur…) de se brancher sur des serveurs qui lui offrent des outils, des documents et des consignes.

## Brancher le serveur

Depuis un clone du dépôt, avec [uv](https://docs.astral.sh/uv/) :

```bash
claude mcp add butterfly -- uv --directory /chemin/absolu/vers/butterfly run python -m serveur_butterfly
```

Pour Claude Desktop, ou dans un fichier `.mcp.json` de projet, la configuration est la suivante (remplacez le chemin) :

```json
{
  "mcpServers": {
    "butterfly": {
      "command": "uv",
      "args": ["--directory", "/chemin/absolu/vers/butterfly",
               "run", "python", "-m", "serveur_butterfly"]
    }
  }
}
```

Pour explorer le serveur sans IA, avec l'outil graphique officiel (il faut Node.js) :

```bash
npx @modelcontextprotocol/inspector uv run python -m serveur_butterfly
```

## Les outils

| Outil | Ce qu'il fait |
|---|---|
| `tokenize` | découpe le programme en tokens (en cas d'erreur lexicale, renvoie ceux lus avant) |
| `parse` | analyse la syntaxe et renvoie l'arbre en JSON (chaque nœud a une clé `type`) |
| `check` | vérifie le programme sans l'exécuter, et renvoie **toutes** les erreurs d'un coup |
| `transpile` | renvoie le code Python généré |
| `format` | renvoie la présentation canonique, commentaires conservés |
| `run` | exécute le programme dans un processus borné |

Les cinq premiers sont annoncés **en lecture seule** : un hôte peut les appeler sans demander la permission à l'utilisateur.

Une erreur **dans le programme** de l'IA est une réponse normale (`ok: false`, avec la liste des erreurs). Le champ `is_error` du protocole est réservé aux cas où l'outil lui-même n'a pas pu travailler, par exemple un argument invalide. Chaque erreur contient son genre, son message, sa ligne, sa colonne et un `contexte` : le message complet avec la ligne fautive soulignée.

## Les resources et les prompts

| URI | Contenu |
|---|---|
| `butterfly://specification` | la spécification complète (lexique, grammaire, sémantique, erreurs) |
| `butterfly://exemples` | la liste des programmes d'exemple |
| `butterfly://exemples/{nom}` | le code d'un exemple |
| `butterfly://exemples/{nom}/attendu` | la sortie exacte de cet exemple |

Deux **prompts**, que l'utilisateur choisit dans son application : `ecrire_programme` (une méthode complète, de la lecture de la spécification à l'exécution) et `corriger_programme` (corriger un programme d'après les erreurs signalées).

## Une session type

Voici le scénario qui est rejoué par un test du dépôt, avec une IA scriptée qui ne connaît Butterfly que par le serveur :

1. Elle lit les **instructions du serveur**, qui la renvoient vers `butterfly://specification`, puis un exemple.
2. Premier jet : elle oublie un `;`. `check` répond `ok: false` avec l'erreur à la **ligne 2**.
3. Elle corrige. `check` signale alors une faute de frappe : `nom 'c' non déclaré`, **ligne 3**.
4. Elle corrige encore. `check` répond `ok: true` et décrit les cellules du programme. `run` renvoie `statut: ok` et la sortie `somme : 13`.
5. Elle appelle `format`, et la version formatée donne la même sortie.

## Pourquoi `run` est sûr

Exécuter un programme écrit par une IA, c'est exécuter du code que personne n'a relu. Le serveur combine des protections techniques et la conception du langage.

| Risque | Protection |
|---|---|
| boucle infinie | délai maximal (de 0,1 à 5 secondes), puis le processus est tué |
| sortie infinie | lecture bornée à 64 Kio, puis le processus est tué |
| mémoire excessive | limite d'espace d'adressage posée par le processus fils |
| plantage du serveur | le programme tourne dans un **processus séparé**, jamais dans le serveur |
| fichiers qui traînent | dossier temporaire supprimé quoi qu'il arrive |
| lecture du canal MCP | l'entrée standard du fils est fermée |
| variables d'environnement | le fils n'hérite d'aucune variable du serveur |

Ce tableau ne protège pas l'accès aux fichiers ou au réseau. Ce qui le fait, c'est le langage : **un programme Butterfly ne peut ni lire de fichier, ni ouvrir de connexion, ni importer un module**. Et le générateur ne laisse passer aucun texte du programme dans le code Python : les textes sont écrits avec `repr`, et toutes les variables sont préfixées par `v_`. Un test vérifie qu'un texte contenant `__import__('os').system(...)` s'affiche tel quel, sans rien exécuter.

Un langage qui offrirait une fonction `lis_fichier(...)` demanderait un vrai bac à sable : un conteneur, un utilisateur dédié, un filtrage des appels système.

## Les statuts de `run`

| Statut | Signification |
|---|---|
| `ok` | le programme s'est terminé normalement |
| `erreur_compilation` | le programme est faux : il n'a pas été exécuté, les erreurs sont détaillées |
| `erreur_execution` | une erreur à l'exécution, avec sa ligne ; la sortie précédente est conservée |
| `delai_depasse` | le programme a dépassé le délai |
| `sortie_tronquee` | le programme a affiché trop de texte |
| `memoire_depassee` | le programme a consommé trop de mémoire |
| `erreur_interne` | l'exécution a échoué sans erreur Butterfly identifiable |
