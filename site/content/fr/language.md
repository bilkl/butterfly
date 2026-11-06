# Le langage en dix minutes

Butterfly est un langage **réactif**. À côté des variables ordinaires, on y déclare des cellules dont la valeur est toujours égale à une formule, comme dans un tableur. Cette page présente le langage pas à pas. Chaque programme est exécuté à la construction du site : ce que vous lisez comme sortie est la vraie sortie.

## Une valeur qui en suit une autre

`let` crée une **cellule source** : on peut la modifier quand on veut. `bind` crée une **cellule dérivée** : elle vaut toujours le résultat de sa formule. `print` affiche ses valeurs séparées par une espace.

```fly run
let price = 20;
let quantity = 3;
bind total = price * quantity;
print "total :", total;
quantity = 5;
print "total :", total;
price = price + 5;
print "total :", total;
```

Personne n'a recalculé `total`. Dès qu'une source change, toutes les cellules dérivées qui en dépendent sont mises à jour, une seule fois chacune, et dans le bon ordre. On ne peut pas affecter une valeur à une cellule dérivée : ce serait contradictoire avec sa formule.

## Réagir à un changement

`when` déclare un **observateur** : un bloc exécuté chaque fois que la valeur d'une cellule change.

```fly run
let temperature = 18;
bind hot = temperature > 25;

when hot {
    print "il fait chaud :", hot;
}

temperature = 22;
temperature = 27;
temperature = 30;
temperature = 20;
```

L'observateur n'a parlé que deux fois, alors que la température a changé quatre fois. Ce qui compte, c'est la valeur de `hot` : elle ne change que lorsqu'on franchit les 25 degrés, dans un sens ou dans l'autre. Trois règles à retenir :

- un observateur n'est **pas** déclenché quand la cellule est créée ;
- il n'est déclenché que si la valeur **a vraiment changé** (affecter `a = 2;` quand `a` vaut déjà 2 ne fait rien) ;
- il peut lire n'importe quelle cellule, mais **pas en modifier** une du niveau supérieur, ce qui évite les boucles infinies.

## Pas d'état intermédiaire

Quand plusieurs cellules dépendent de la même source, un observateur ne voit jamais un état à moitié mis à jour. Ici, `d` dépend de `b` et de `c`, qui dépendent tous deux de `a` :

```fly run
let a = 1;
bind b = a + 1;
bind c = a * 10;
bind d = b + c;

when d {
    print "d vaut maintenant", d;
}

a = 2;
a = 5;
```

Pour `a = 2;`, `d` est recalculée une fois, **après** `b` et `c`. L'observateur reçoit donc 23, jamais 13 (la valeur qu'on obtiendrait avec `b` à jour mais pas encore `c`).

## Valeurs et opérateurs

Butterfly a trois sortes de valeurs : les **entiers** (de taille illimitée), les **booléens** (`true`, `false`) et les **textes**. Les variables n'ont pas de type déclaré : c'est la valeur qui en porte un, et les erreurs de type sont signalées à l'exécution. Les opérateurs logiques sont `and` (et), `or` (ou) et `not` (non).

```fly run
print 2 + 3 * 4, (2 + 3) * 4;
print 17 / 5, 17 % 5, -17 / 5, -17 % 5;
print 1 < 2, not (1 < 2) or 5 >= 5;
print "but" + "terfly", "a" < "b";
print 99999999999 * 99999999999;
```

`/` est la division entière arrondie vers le bas, et `%` le reste de même signe que le diviseur (comme `//` et `%` de Python). Voici les priorités, du moins prioritaire au plus prioritaire :

| Niveau | Opérateurs | Associativité |
|---|---|---|
| 1 | `or` | gauche |
| 2 | `and` | gauche |
| 3 | `not` | préfixe |
| 4 | `==` `!=` `<` `<=` `>` `>=` | aucune |
| 5 | `+` `-` | gauche |
| 6 | `*` `/` `%` | gauche |
| 7 | `-` unaire | préfixe |

Les comparaisons **ne s'enchaînent pas** : `1 < 2 < 3` est une erreur, et le message dit comment l'écrire.

```fly error
print 1 < 2 < 3;
```

`and` et `or` **court-circuitent** : `false and (1 / 0 == 0)` vaut `false` sans jamais diviser par zéro. Et `==` compare aussi les types : `true == 1` vaut `false`.

## Conditions et boucles

```fly run
let grade = 14;
if grade >= 16 {
    print "très bien";
} else if grade >= 12 {
    print "bien";
} else {
    print "à revoir";
}

for i in 1..4 {
    print i, i * i;
}
```

La borne haute d'un `for` est **exclue** : `1..4` donne 1, 2, 3. Les bornes sont évaluées une seule fois, avant la boucle. La variable de boucle est en lecture seule.

## Blocs et portées

Un nom déclaré dans un bloc n'existe plus après lui. Surtout, un nom **ne peut jamais en masquer un autre** : c'est plus strict que Python, et c'est ce qui permet au code Python généré de garder exactement le même sens.

```fly error
let a = 1;
if true {
    let a = 2;
}
```

## Fonctions prédéfinies

Il y en a trois, qui travaillent sur des entiers : `min`, `max` et `abs`.

```fly run
print min(4, 9), max(4, 9), abs(-7);
```

## Les erreurs

Une erreur donne son genre, sa position, un message qui dit quoi faire, et la ligne fautive soulignée. Butterfly signale **toutes** les erreurs d'un coup plutôt qu'une par une. Les messages sont en anglais, comme le langage.

```fly error
let a = ;
let b = 2
print c;
```

Il y a quatre genres d'erreurs : lexicale (un caractère que le langage ne connaît pas), de syntaxe, sémantique (le programme est bien écrit mais n'a pas de sens) et d'exécution.

```fly error
let x = 3 @ 2;
```

```fly error
let a = 1;
bind b = a;
b = 2;
```

Une erreur d'exécution donne la ligne **du programme Butterfly** (pas celle du Python généré), et ce qui a déjà été affiché est conservé :

```fly run
print "début";
print 1 / 0;
print "fin";
```

## Ce que Butterfly ne fait pas

Pas de fonctions définies par l'utilisateur, pas de listes, pas de nombres décimaux, pas d'entrées-sorties (ni fichiers, ni clavier, ni réseau). Un programme ne peut que calculer et afficher. C'est un choix : cela rend le langage petit et, surtout, sûr à exécuter pour une IA (voir la page sur le [serveur MCP](mcp.html)).
