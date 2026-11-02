# Sous le capot

Butterfly n'utilise aucun outil de génération de parser : toute la chaîne de compilation est écrite à la main, en Python.

```text
texte source → lexer → tokens → parser → arbre → analyse → arbre vérifié → générateur → Python
```

Chaque étage a son entrée, sa sortie, et ses tests. Tous les exemples de cette page sont produits par le vrai compilateur.

## 1. Le lexer : du texte aux tokens

**Module** `butterfly/lexer.py`. Il découpe le texte en « mots » (les *tokens*), avec leur position. C'est un **générateur** : il ne lit le source qu'au fur et à mesure, donc les tokens lus avant une erreur lexicale sont déjà disponibles.

```fly tokens
soit total = prix * 2; # un commentaire
```

Il lit toujours le plus long token possible : `<=` est un seul token, et `1..5` donne trois tokens (`1`, `..`, `5`), ce qui explique que les nombres décimaux n'existent pas.

## 2. Le parser : des tokens à l'arbre

**Module** `butterfly/parser.py`. Les instructions sont analysées par **descente récursive** (une méthode par règle de la grammaire). Les expressions le sont par un **parser de Pratt** : une table donne la priorité de chaque opérateur, et ajouter un opérateur revient à ajouter une ligne dans la table.

```fly ast
lie c = a + b * 2;
```

Le `*` est plus profond dans l'arbre que le `+` : c'est ce qui le rend prioritaire. Le parser **ne s'arrête pas à la première erreur** : il la note, saute jusqu'à l'instruction suivante, et signale toutes les erreurs d'un coup.

## 3. L'analyse sémantique : ce que la grammaire ne peut pas voir

**Module** `butterfly/semantique.py`. Elle vérifie les noms (déclarés avant usage, jamais masqués), les affectations (jamais à une cellule dérivée), les observateurs et les appels de fonctions. Elle produit aussi ce dont le générateur a besoin : les cellules du niveau supérieur et, pour chaque cellule dérivée, les cellules citées dans sa formule.

```fly analyse
soit a = 1;
soit b = 2;
lie c = a + 1;
lie d = c * b;
```

## 4. Le générateur : de l'arbre au Python

**Module** `butterfly/generateur.py`. Le point clé est la **propagation**. Butterfly n'embarque aucun moteur réactif à l'exécution : le compilateur calcule, pour chaque affectation d'une source, la liste ordonnée des cellules dérivées à recalculer et des observateurs à prévenir, puis écrit le code qui le fait.

```fly python
soit prix = 20;
soit quantite = 3;
lie total = prix * quantite;

quand total {
    affiche "nouveau total :", total;
}

quantite = 5;
```

Lisez le code généré :

- chaque cellule dérivée a une fonction `_calc_…` qu'on rappelle à chaque recalcul ;
- avant l'affectation, la valeur des cellules observées est mise de côté (`_av_total`) ;
- après l'affectation, les cellules dérivées touchées sont recalculées **dans l'ordre de leur déclaration**, qui est un ordre topologique valide puisqu'on déclare avant d'utiliser ;
- enfin, `_change` compare l'ancienne et la nouvelle valeur, et l'observateur `_obs_0` n'est appelé que si elle a changé.

Toutes les variables sont préfixées par `v_`, et les textes écrits avec `repr` : aucun nom ni aucun texte du programme ne peut jamais produire du Python que le compilateur n'a pas prévu.

## 5. Le runtime : les erreurs à l'exécution

**Module** `butterfly/runtime.py`. Butterfly n'a pas de types déclarés : ce sont les valeurs qui portent un type, et de petites fonctions vérifient les types à l'exécution. Chacune reçoit en argument la **ligne du programme Butterfly** d'où vient l'appel (on le voit dans le code généré ci-dessus) : c'est ainsi qu'une erreur d'exécution indique la bonne ligne.

## 6. Autour du compilateur

| Module | Rôle |
|---|---|
| `compilateur.py` | la façade (`compiler`, `transpiler`, `executer`) : tout le reste s'appuie dessus |
| `cli.py` | la ligne de commande, avec ses codes de retour |
| `repl.py` | la session interactive |
| `formateur.py` | la présentation canonique, commentaires et lignes vides conservés |
| `backend.py` | un `Protocol` : le générateur Python et le formateur sont deux backends, un troisième s'ajoute sans rien modifier |

Le **REPL** n'a pas d'état à sérialiser. Il garde le texte des entrées réussies et recompile le tout à chaque nouvelle entrée. Comme un programme Butterfly est déterministe, la sortie de « l'historique plus la nouvelle entrée » commence par celle de l'historique : il suffit d'afficher la suite.

## Les choix de conception

| Choix | Raison |
|---|---|
| déclarer avant d'utiliser | une formule ne cite que des cellules existantes : pas de cycle possible, et l'ordre de déclaration est un ordre de calcul valide |
| `lie` et `quand` seulement au niveau supérieur | le graphe de dépendances est connu à la compilation |
| un observateur ne modifie pas le niveau supérieur | sinon il pourrait se déclencher lui-même à l'infini |
| un nom n'en masque jamais un autre | Python n'a pas de portée de bloc : le code généré garde ainsi le même sens |
| comparaisons non chaînables | un choix net, plutôt qu'une lecture ambiguë de `a < b < c` |
| uniquement des entiers | `1..5` (plage) et `1.5` (décimal) ne se confondent jamais |
| aucune entrée-sortie | un programme ne peut rien faire d'autre que calculer et afficher : sûr à exécuter |

## Les tests

Le dépôt compte plus de 360 tests, un fichier par étape de la chaîne. Trois idées les rendent utiles :

- la **spécification est exécutable** : un test lit son tableau d'erreurs et vérifie chaque message ;
- **chaque exemple** est exécuté et sa sortie comparée à la sortie attendue, y compris après passage par le formateur ;
- le serveur MCP est testé **dans le même processus**, puis **en vrai**, lancé en sous-processus comme le ferait un hôte.
