# Spécification de Butterfly

> Brouillon de l'étape 1. À relire, à corriger et à faire valider par l'enseignant avant d'écrire la moindre ligne du compilateur.

## Identité

| | |
|---|---|
| Nom | Butterfly |
| Extension | `.fly` |
| Idée | Butterfly est un langage **réactif**, nommé d'après l'effet papillon : changer une seule valeur (un battement d'ailes) peut mettre à jour tout un programme. À côté des variables ordinaires (`soit`), on déclare des **cellules dérivées** (`lie`) dont la valeur est toujours égale à une formule, comme dans un tableur. Quand une source change, tout ce qui en dépend se met à jour tout seul, une seule fois et dans le bon ordre. Des **observateurs** (`quand`) peuvent réagir aux changements. Il s'adresse à qui veut décrire des *relations* plutôt que des étapes de recalcul. |
| Cible | Python 3.12 |

## Un programme pour donner le ton

```
soit prix = 20;
soit quantite = 3;
lie total = prix * quantite;

quand total {
    affiche "nouveau total :", total;
}

quantite = 5;       # affiche : nouveau total : 100
prix = prix + 5;    # affiche : nouveau total : 125
```

## Lexique

- **Blancs et sauts de ligne** : ignorés, sauf pour séparer deux tokens. Les instructions se terminent par `;` : un saut de ligne ne signifie rien, et une expression peut s'étendre sur plusieurs lignes. L'indentation est libre.
- **Commentaires** : `#` jusqu'à la fin de la ligne. Il n'y a pas de commentaire multiligne.
- **Nombres** : seulement des **entiers** positifs, suite de chiffres décimaux (`0`, `42`, `007` vaut 7). Les négatifs s'écrivent avec l'opérateur unaire `-`. Pas de décimaux : `1.5` est une erreur lexicale, ce qui évite toute ambiguïté avec `..` (`1..5`).
- **Textes** : entre guillemets doubles, sur une seule ligne. Échappements acceptés : `\"`, `\\` et `\n`. Tout autre `\x` est une erreur lexicale, de même qu'un texte non fermé en fin de ligne.
- **Identifiants** : une lettre (accentuée ou non) ou `_`, suivie de lettres, chiffres ou `_`. La casse compte (`Total` et `total` sont deux noms). Un mot-clé collé à d'autres caractères est un identifiant : `soit_x` et `sinon2` sont des identifiants, `soit` est un mot-clé.
- **Mots-clés** : `soit` `lie` `quand` `si` `sinon` `pour` `dans` `affiche` `vrai` `faux` `et` `ou` `non`
- **Symboles et opérateurs** : `+` `-` `*` `/` `%` `==` `!=` `<` `<=` `>` `>=` `=` `..` `(` `)` `{` `}` `,` `;`

Le lexer lit toujours le **plus long** token possible : `<=` est un seul token, `..` aussi, et `==` se distingue de `=`.

## Grammaire (EBNF)

Notation : `{ x }` répète zéro fois ou plus, `[ x ]` est facultatif, `|` sépare les choix, les terminaux sont entre guillemets.

```ebnf
programme     = { instr_haut } FIN ;

(* Au niveau supérieur, on peut tout écrire. *)
instr_haut    = instruction | liaison | observation ;
liaison       = "lie" IDENT "=" expression ";" ;
observation   = "quand" IDENT bloc ;

(* Dans un bloc, on n'écrit que des instructions : ni "lie", ni "quand". *)
instruction   = declaration | affectation | si | pour | affiche ;
declaration   = "soit" IDENT "=" expression ";" ;
affectation   = IDENT "=" expression ";" ;
si            = "si" expression bloc [ "sinon" ( si | bloc ) ] ;
pour          = "pour" IDENT "dans" expression ".." expression bloc ;
affiche       = "affiche" expression { "," expression } ";" ;
bloc          = "{" { instruction } "}" ;

expression    = disjonction ;
disjonction   = conjonction { "ou" conjonction } ;
conjonction   = negation { "et" negation } ;
negation      = "non" negation | comparaison ;
comparaison   = somme [ ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) somme ] ;
somme         = produit { ( "+" | "-" ) produit } ;
produit       = unaire { ( "*" | "/" | "%" ) unaire } ;
unaire        = "-" unaire | primaire ;
primaire      = ENTIER | TEXTE | "vrai" | "faux" | appel | IDENT | "(" expression ")" ;
appel         = IDENT "(" [ expression { "," expression } ] ")" ;
```

`lie` et `quand` ne sont acceptés qu'au **niveau supérieur** : les écrire dans un bloc est une erreur de syntaxe, avec un message qui le dit.

## Priorité et associativité des opérateurs

Du moins prioritaire au plus prioritaire.

| Niveau | Opérateurs | Associativité |
|---|---|---|
| 1 | `ou` | gauche |
| 2 | `et` | gauche |
| 3 | `non` (préfixe) | droite |
| 4 | `==` `!=` `<` `<=` `>` `>=` | **aucune** |
| 5 | `+` `-` | gauche |
| 6 | `*` `/` `%` | gauche |
| 7 | `-` (préfixe) | droite |

- Les comparaisons **ne s'enchaînent pas** : `1 < 2 < 3` est une erreur de syntaxe (écrire `1 < 2 et 2 < 3`).
- `non a == b` se lit `non (a == b)`, car `non` est moins prioritaire que les comparaisons.
- Le `-` unaire est le plus prioritaire : `-17 / 5` se lit `(-17) / 5`.

## Sémantique

### Valeurs et types

Trois sortes de valeurs : les **entiers** (de taille illimitée), les **booléens** (`vrai`, `faux`) et les **textes**. Les variables n'ont pas de type déclaré : c'est la valeur qui en porte un, et les erreurs de type sont détectées à l'exécution.

- `+` additionne deux entiers ou concatène deux textes. `-`, `*`, `/`, `%` ne s'appliquent qu'à des entiers.
- `/` est la **division entière arrondie vers le bas** et `%` le reste de même signe que le diviseur, comme `//` et `%` de Python : `-17 / 5` vaut `-4` et `-17 % 5` vaut `3`.
- `<` `<=` `>` `>=` comparent deux entiers ou deux textes (ordre alphabétique des points de code).
- `==` et `!=` comparent n'importe quelles valeurs ; deux valeurs de types différents sont toujours différentes (`1 == "1"` vaut `faux`).
- `et`, `ou`, `non` ne s'appliquent qu'à des booléens. `et` et `ou` **court-circuitent** : `faux et (1 / 0 == 0)` vaut `faux`.

### Cellules : `soit` et `lie`

- `soit x = e;` crée une **cellule source** : `e` est évaluée tout de suite, et `x` peut être modifiée plus tard par `x = e2;`.
- `lie y = e;` crée une **cellule dérivée** : `y` vaut **toujours** la valeur de `e`. On ne peut pas lui affecter de valeur.
- Un nom doit être **déclaré avant d'être utilisé**. Une formule `lie` ne peut donc s'appuyer que sur des cellules déjà déclarées, ce qui exclut les cycles.
- Un nom ne peut pas être redéclaré tant qu'un homonyme est visible, **ni masquer** un nom d'un bloc englobant. Les noms des fonctions prédéfinies (`min`, `max`, `abs`) sont réservés.

### Propagation

Quand une source reçoit une valeur (`x = e;`) :

1. `e` est évaluée **une seule fois**, avec les valeurs courantes des cellules ;
2. `x` prend cette valeur ;
3. toutes les cellules dérivées qui dépendent de `x`, directement ou non, sont recalculées **une seule fois chacune**, dans l'**ordre de leur déclaration** (qui est un ordre topologique valide, puisqu'on déclare avant d'utiliser) ;
4. enfin, les observateurs concernés s'exécutent (voir ci-dessous).

Personne ne voit donc d'état intermédiaire : dans un losange `a → b, c → d`, `d` est recalculée une fois, après `b` et `c`. La propagation a lieu **immédiatement après l'affectation**, y compris dans une boucle ou une condition.

### Observateurs : `quand`

`quand y { ... }` déclare un bloc qui s'exécute **chaque fois que la valeur de `y` change** : on compare la valeur de `y` avant l'affectation et après la propagation. Une affectation qui ne change aucune valeur (`a = 2;` quand `a` valait déjà 2) ne déclenche rien.

- `y` doit être une cellule (`soit` ou `lie`) déclarée **au niveau supérieur**, avant le `quand`.
- L'observateur n'est **pas** déclenché à la création de la cellule, seulement par un changement ultérieur.
- Si plusieurs observateurs sont concernés par la même affectation, ils s'exécutent dans l'ordre de leur déclaration, chacun une fois.
- Un observateur peut lire n'importe quelle cellule, déclarer ses propres variables et utiliser `si`, `pour` et `affiche`. Il ne peut **pas affecter** une cellule du niveau supérieur (cela pourrait boucler indéfiniment) : c'est une erreur sémantique.

### Blocs et portées

Un bloc ouvre une portée : un nom déclaré avec `soit` dans un bloc n'existe plus après son `}`. Le corps d'une boucle est un nouveau bloc **à chaque tour** : `soit carre = i * i;` y est donc redéclaré à chaque tour sans erreur. Le nom d'un bloc frère peut être réutilisé. Un nom utilisé hors de sa portée est une erreur sémantique (« nom non déclaré »).

> Python n'a pas de portée de bloc. Comme Butterfly interdit de masquer un nom, le Python généré garde le même sens ; l'analyse sémantique doit seulement refuser les usages hors portée.

### Structures de contrôle

- `si c { ... } sinon si c2 { ... } sinon { ... }` : la condition doit être un booléen (erreur d'exécution sinon). Les blocs peuvent être vides.
- `pour i dans a..b { ... }` : `a` et `b` sont des entiers évalués une fois, avant la boucle. `i` prend les valeurs `a`, `a+1`, …, `b-1` (**borne haute exclue**). Si `a >= b`, le corps ne s'exécute pas. `i` est en lecture seule : lui affecter une valeur est une erreur sémantique.

### Affichage

`affiche e1, e2, ...;` écrit les valeurs séparées par **une espace**, suivies d'un saut de ligne. Un entier s'affiche en décimal, un texte tel quel (sans guillemets), un booléen `vrai` ou `faux`.

### Fonctions prédéfinies

| Appel | Résultat |
|---|---|
| `min(a, b)` | le plus petit de deux entiers |
| `max(a, b)` | le plus grand de deux entiers |
| `abs(n)` | la valeur absolue d'un entier |

Un mauvais nombre d'arguments est une erreur sémantique ; un argument qui n'est pas un entier est une erreur d'exécution. Butterfly n'a pas de fonctions définies par l'utilisateur.

### Erreurs d'exécution

La division ou le modulo par zéro, un opérande du mauvais type, une condition non booléenne, des bornes de `pour` non entières : le programme s'arrête avec un message qui donne la **ligne du programme Butterfly**. Le contenu déjà affiché reste affiché.

## Programmes d'exemple

Cinq programmes, dans `projet/exemples/`, avec leur sortie exacte (même nom, extension `.attendu`).

| Fichier | Ce qu'il montre |
|---|---|
| `01_expressions.fly` | priorités, `non`/`et`/`ou`, division et modulo de négatifs, fonctions prédéfinies, textes |
| `02_cellules.fly` | `soit`, `lie`, affectation et mise à jour d'une cellule dérivée |
| `03_losange.fly` | dépendances en losange sans état intermédiaire, `quand`, affectation sans changement |
| `04_boucle.fly` | `pour` (dont zéro tour), `si`/`sinon`, `soit` dans un bloc, observateur sur un seuil |
| `05_budget.fly` | programme plus long : plusieurs cellules, `sinon si`, observateur, `abs` |

## Erreurs

Format des messages : `Erreur <genre> (ligne L, colonne C) : <message>`. Pour les erreurs d'exécution, seule la ligne est donnée.

| Genre | Programme | Message attendu |
|---|---|---|
| lexicale | `soit x = 3 @ 2;` | `Erreur lexicale (ligne 1, colonne 12) : caractère inattendu '@'` |
| syntaxe | `soit x = ;` | `Erreur de syntaxe (ligne 1, colonne 10) : expression attendue, ';' trouvé` |
| syntaxe | `affiche 1 < 2 < 3;` | `Erreur de syntaxe (ligne 1, colonne 15) : les comparaisons ne s'enchaînent pas, utilisez 'et'` |
| syntaxe | `si vrai { lie x = 1; }` | `Erreur de syntaxe (ligne 1, colonne 11) : 'lie' n'est permis qu'au niveau supérieur` |
| sémantique | `lie c = a + 1;` | `Erreur sémantique (ligne 1, colonne 9) : nom 'a' non déclaré` |
| sémantique | `soit a = 1;` `lie b = a;` `b = 2;` | `Erreur sémantique (ligne 3, colonne 1) : 'b' est une cellule dérivée (lie), on ne peut pas lui affecter de valeur` |
| exécution | `affiche 1 / 0;` | `Erreur d'exécution (ligne 1) : division par zéro` |

## Limites

Pas de fonctions définies par l'utilisateur, pas de listes, pas de décimaux, pas d'entrées-sorties (ni fichiers, ni clavier, ni réseau) : un programme Butterfly ne peut rien faire d'autre que calculer et afficher, ce qui simplifiera l'exécution en isolation du projet MCP.

## Pistes d'extension

- Autoriser une formule `lie` à citer une cellule déclarée **plus loin**, et détecter les cycles (`lie a = b; lie b = a;`) pendant l'analyse sémantique.
- Autoriser `lie` et `quand` dans des blocs.
- Ajouter des fonctions définies par l'utilisateur.
