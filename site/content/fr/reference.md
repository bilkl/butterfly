# Référence du langage

## Identité

| | |
|---|---|
| Nom | Butterfly |
| Extension | `.fly` |
| Idée | Butterfly est un langage **réactif**, nommé d'après l'effet papillon : changer une seule valeur (un battement d'ailes) peut mettre à jour tout un programme. À côté des variables ordinaires (`let`), on déclare des **cellules dérivées** (`bind`) dont la valeur est toujours égale à une formule, comme dans un tableur. Quand une source change, tout ce qui en dépend se met à jour tout seul, une seule fois et dans le bon ordre. Des **observateurs** (`when`) peuvent réagir aux changements. Il s'adresse à qui veut décrire des *relations* plutôt que des étapes de recalcul. |
| Cible | Python 3.12 |

## Un programme pour donner le ton

```
let price = 20;
let quantity = 3;
bind total = price * quantity;

when total {
    print "new total:", total;
}

quantity = 5;       # prints: new total: 100
price = price + 5;  # prints: new total: 125
```

## Lexique

- **Blancs et sauts de ligne** : ignorés, sauf pour séparer deux tokens. Les instructions se terminent par `;` : un saut de ligne ne signifie rien, et une expression peut s'étendre sur plusieurs lignes. L'indentation est libre.
- **Commentaires** : `#` jusqu'à la fin de la ligne. Il n'y a pas de commentaire multiligne.
- **Nombres** : seulement des **entiers** positifs, suite de chiffres décimaux (`0`, `42`, `007` vaut 7). Les négatifs s'écrivent avec l'opérateur unaire `-`. Pas de décimaux : `1.5` est une erreur lexicale, ce qui évite toute ambiguïté avec `..` (`1..5`).
- **Textes** : entre guillemets doubles, sur une seule ligne. Échappements acceptés : `\"`, `\\` et `\n`. Tout autre `\x` est une erreur lexicale, de même qu'un texte non fermé en fin de ligne.
- **Identifiants** : une lettre (accentuée ou non) ou `_`, suivie de lettres, chiffres ou `_`. La casse compte (`Total` et `total` sont deux noms). Un mot-clé collé à d'autres caractères est un identifiant : `let_x` et `else2` sont des identifiants, `let` est un mot-clé.
- **Mots-clés** : `let` `bind` `when` `if` `else` `for` `in` `print` `true` `false` `and` `or` `not`
- **Symboles et opérateurs** : `+` `-` `*` `/` `%` `==` `!=` `<` `<=` `>` `>=` `=` `..` `(` `)` `{` `}` `,` `;`

Le lexer lit toujours le **plus long** token possible : `<=` est un seul token, `..` aussi, et `==` se distingue de `=`.

## Grammaire (EBNF)

Notation : `{ x }` répète zéro fois ou plus, `[ x ]` est facultatif, `|` sépare les choix, les terminaux sont entre guillemets. Les noms des règles sont descriptifs (`program`, `top_statement`, `binding`, `observer`, `statement`, `block`, …).

```ebnf
program     = { top_statement } EOF ;

(* Au niveau supérieur, on peut tout écrire. *)
top_statement    = statement | binding | observer ;
binding       = "bind" IDENT "=" expression ";" ;
observer   = "when" IDENT block ;

(* Dans un bloc, on n'écrit que des instructions : ni "bind", ni "when". *)
statement   = declaration | assignment | if_stmt | for_stmt | print_stmt ;
declaration   = "let" IDENT "=" expression ";" ;
assignment   = IDENT "=" expression ";" ;
if_stmt            = "if" expression block [ "else" ( if_stmt | block ) ] ;
for_stmt          = "for" IDENT "in" expression ".." expression block ;
print_stmt       = "print" expression { "," expression } ";" ;
block          = "{" { statement } "}" ;

expression    = disjunction ;
disjunction   = conjunction { "or" conjunction } ;
conjunction   = negation { "and" negation } ;
negation      = "not" negation | comparison ;
comparison   = sum [ ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) sum ] ;
sum         = product { ( "+" | "-" ) product } ;
product       = unary { ( "*" | "/" | "%" ) unary } ;
unary        = "-" unary | primary ;
primary      = INTEGER | TEXT | "true" | "false" | call | IDENT | "(" expression ")" ;
call         = IDENT "(" [ expression { "," expression } ] ")" ;
```

`bind` et `when` ne sont acceptés qu'au **niveau supérieur** : les écrire dans un bloc est une erreur de syntaxe, avec un message qui le dit.

## Priorité et associativité des opérateurs

Du moins prioritaire au plus prioritaire.

| Niveau | Opérateurs | Associativité |
|---|---|---|
| 1 | `or` | gauche |
| 2 | `and` | gauche |
| 3 | `not` (préfixe) | droite |
| 4 | `==` `!=` `<` `<=` `>` `>=` | **aucune** |
| 5 | `+` `-` | gauche |
| 6 | `*` `/` `%` | gauche |
| 7 | `-` (préfixe) | droite |

- Les comparaisons **ne s'enchaînent pas** : `1 < 2 < 3` est une erreur de syntaxe (écrire `1 < 2 and 2 < 3`).
- `not a == b` se lit `not (a == b)`, car `not` est moins prioritaire que les comparaisons.
- Le `-` unaire est le plus prioritaire : `-17 / 5` se lit `(-17) / 5`.

## Sémantique

### Valeurs et types

Trois sortes de valeurs : les **entiers** (de taille illimitée), les **booléens** (`true`, `false`) et les **textes**. Les variables n'ont pas de type déclaré : c'est la valeur qui en porte un, et les erreurs de type sont détectées à l'exécution.

- `+` additionne deux entiers ou concatène deux textes. `-`, `*`, `/`, `%` ne s'appliquent qu'à des entiers.
- `/` est la **division entière arrondie vers le bas** et `%` le reste de même signe que le diviseur, comme `//` et `%` de Python : `-17 / 5` vaut `-4` et `-17 % 5` vaut `3`.
- `<` `<=` `>` `>=` comparent deux entiers ou deux textes (ordre alphabétique des points de code).
- `==` et `!=` comparent n'importe quelles valeurs ; deux valeurs de types différents sont toujours différentes (`1 == "1"` vaut `false`).
- `and`, `or`, `not` ne s'appliquent qu'à des booléens. `and` et `or` **court-circuitent** : `false and (1 / 0 == 0)` vaut `false`.

### Cellules : `let` et `bind`

- `let x = e;` crée une **cellule source** : `e` est évaluée tout de suite, et `x` peut être modifiée plus tard par `x = e2;`.
- `bind y = e;` crée une **cellule dérivée** : `y` vaut **toujours** la valeur de `e`. On ne peut pas lui affecter de valeur.
- Un nom doit être **déclaré avant d'être utilisé**. Une formule `bind` ne peut donc s'appuyer que sur des cellules déjà déclarées, ce qui exclut les cycles.
- Un nom ne peut pas être redéclaré tant qu'un homonyme est visible, **ni masquer** un nom d'un bloc englobant. Les noms des fonctions prédéfinies (`min`, `max`, `abs`) sont réservés.

### Propagation

Quand une source reçoit une valeur (`x = e;`) :

1. `e` est évaluée **une seule fois**, avec les valeurs courantes des cellules ;
2. `x` prend cette valeur ;
3. toutes les cellules dérivées qui dépendent de `x`, directement ou non, sont recalculées **une seule fois chacune**, dans l'**ordre de leur déclaration** (qui est un ordre topologique valide, puisqu'on déclare avant d'utiliser) ;
4. enfin, les observateurs concernés s'exécutent (voir ci-dessous).

Personne ne voit donc d'état intermédiaire : dans un losange `a → b, c → d`, `d` est recalculée une fois, après `b` et `c`. La propagation a lieu **immédiatement après l'affectation**, y compris dans une boucle ou une condition.

### Observateurs : `when`

`when y { ... }` déclare un bloc qui s'exécute **chaque fois que la valeur de `y` change** : on compare la valeur de `y` avant l'affectation et après la propagation. Une affectation qui ne change aucune valeur (`a = 2;` quand `a` valait déjà 2) ne déclenche rien.

- `y` doit être une cellule (`let` ou `bind`) déclarée **au niveau supérieur**, avant le `when`.
- L'observateur n'est **pas** déclenché à la création de la cellule, seulement par un changement ultérieur.
- Si plusieurs observateurs sont concernés par la même affectation, ils s'exécutent dans l'ordre de leur déclaration, chacun une fois.
- Un observateur peut lire n'importe quelle cellule, déclarer ses propres variables et utiliser `if`, `for` et `print`. Il ne peut **pas affecter** une cellule du niveau supérieur (cela pourrait boucler indéfiniment) : c'est une erreur sémantique.

### Blocs et portées

Un bloc ouvre une portée : un nom déclaré avec `let` dans un bloc n'existe plus après son `}`. Le corps d'une boucle est un nouveau bloc **à chaque tour** : `let square = i * i;` y est donc redéclaré à chaque tour sans erreur. Le nom d'un bloc frère peut être réutilisé. Un nom utilisé hors de sa portée est une erreur sémantique (« name not declared »).

> Python n'a pas de portée de bloc. Comme Butterfly interdit de masquer un nom, le Python généré garde le même sens ; l'analyse sémantique doit seulement refuser les usages hors portée.

### Structures de contrôle

- `if c { ... } else if c2 { ... } else { ... }` : la condition doit être un booléen (erreur d'exécution sinon). Les blocs peuvent être vides.
- `for i in a..b { ... }` : `a` et `b` sont des entiers évalués une fois, avant la boucle. `i` prend les valeurs `a`, `a+1`, …, `b-1` (**borne haute exclue**). Si `a >= b`, le corps ne s'exécute pas. `i` est en lecture seule : lui affecter une valeur est une erreur sémantique.

### Affichage

`print e1, e2, ...;` écrit les valeurs séparées par **une espace**, suivies d'un saut de ligne. Un entier s'affiche en décimal, un texte tel quel (sans guillemets), un booléen `true` ou `false`.

### Fonctions prédéfinies

| Appel | Résultat |
|---|---|
| `min(a, b)` | le plus petit de deux entiers |
| `max(a, b)` | le plus grand de deux entiers |
| `abs(n)` | la valeur absolue d'un entier |

Un mauvais nombre d'arguments est une erreur sémantique ; un argument qui n'est pas un entier est une erreur d'exécution. Butterfly n'a pas de fonctions définies par l'utilisateur.

### Erreurs d'exécution

La division ou le modulo par zéro, un opérande du mauvais type, une condition non booléenne, des bornes de `for` non entières : le programme s'arrête avec un message qui donne la **ligne du programme Butterfly**. Le contenu déjà affiché reste affiché.

## Programmes d'exemple

Cinq programmes, dans `examples/`, avec leur sortie exacte (même nom, extension `.expected`).

| Fichier | Ce qu'il montre |
|---|---|
| `01_expressions.fly` | priorités, `not`/`and`/`or`, division et modulo de négatifs, fonctions prédéfinies, textes |
| `02_cells.fly` | `let`, `bind`, affectation et mise à jour d'une cellule dérivée |
| `03_diamond.fly` | dépendances en losange sans état intermédiaire, `when`, affectation sans changement |
| `04_loop.fly` | `for` (dont zéro tour), `if`/`else`, `let` dans un bloc, observateur sur un seuil |
| `05_budget.fly` | programme plus long : plusieurs cellules, `else if`, observateur, `abs` |

## Erreurs

Format des messages : `<Genre> error (line L, column C): <message>`. Pour les erreurs d'exécution, seule la ligne est donnée. Les messages sont en anglais, comme le langage.

| Genre | Programme | Message attendu |
|---|---|---|
| lexical | `let x = 3 @ 2;` | `Lexical error (line 1, column 11): unexpected character '@'` |
| syntax | `let x = ;` | `Syntax error (line 1, column 9): expression expected, ';' found` |
| syntax | `print 1 < 2 < 3;` | `Syntax error (line 1, column 13): comparisons do not chain, use 'and'` |
| syntax | `if true { bind x = 1; }` | `Syntax error (line 1, column 11): 'bind' is only allowed at top level` |
| semantic | `bind c = a + 1;` | `Semantic error (line 1, column 10): name 'a' not declared` |
| semantic | `let a = 1;` `bind b = a;` `b = 2;` | `Semantic error (line 3, column 1): 'b' is a derived cell (bind), a value cannot be assigned to it` |
| runtime | `print 1 / 0;` | `Runtime error (line 1): division by zero` |

## Limites

Pas de fonctions définies par l'utilisateur, pas de listes, pas de décimaux, pas d'entrées-sorties (ni fichiers, ni clavier, ni réseau) : un programme Butterfly ne peut rien faire d'autre que calculer et afficher, ce qui simplifie l'exécution en isolation du projet MCP.

## Pistes d'extension

- Autoriser une formule `bind` à citer une cellule déclarée **plus loin**, et détecter les cycles (`bind a = b; bind b = a;`) pendant l'analyse sémantique.
- Autoriser `bind` et `when` dans des blocs.
- Ajouter des fonctions définies par l'utilisateur.
