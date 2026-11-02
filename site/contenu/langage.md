# Le langage en dix minutes

Butterfly est un langage **réactif**. À côté des variables ordinaires, on y déclare des cellules dont la valeur est toujours égale à une formule, comme dans un tableur. Cette page présente le langage pas à pas. Chaque programme est exécuté à la construction du site : ce que vous lisez comme sortie est la vraie sortie.

## Une valeur qui en suit une autre

`soit` crée une **cellule source** : on peut la modifier quand on veut. `lie` crée une **cellule dérivée** : elle vaut toujours le résultat de sa formule.

```fly run
soit prix = 20;
soit quantite = 3;
lie total = prix * quantite;
affiche "total :", total;
quantite = 5;
affiche "total :", total;
prix = prix + 5;
affiche "total :", total;
```

Personne n'a recalculé `total`. Dès qu'une source change, toutes les cellules dérivées qui en dépendent sont mises à jour, une seule fois chacune, et dans le bon ordre. On ne peut pas affecter une valeur à une cellule dérivée : ce serait contradictoire avec sa formule.

## Réagir à un changement

`quand` déclare un **observateur** : un bloc exécuté chaque fois que la valeur d'une cellule change.

```fly run
soit temperature = 18;
lie chaud = temperature > 25;

quand chaud {
    affiche "il fait chaud :", chaud;
}

temperature = 22;
temperature = 27;
temperature = 30;
temperature = 20;
```

L'observateur n'a parlé que deux fois, alors que la température a changé quatre fois. Ce qui compte, c'est la valeur de `chaud` : elle ne change que lorsqu'on franchit les 25 degrés, dans un sens ou dans l'autre. Trois règles à retenir :

- un observateur n'est **pas** déclenché quand la cellule est créée ;
- il n'est déclenché que si la valeur **a vraiment changé** (affecter `a = 2;` quand `a` vaut déjà 2 ne fait rien) ;
- il peut lire n'importe quelle cellule, mais **pas en modifier** une du niveau supérieur, ce qui évite les boucles infinies.

## Pas d'état intermédiaire

Quand plusieurs cellules dépendent de la même source, un observateur ne voit jamais un état à moitié mis à jour. Ici, `d` dépend de `b` et de `c`, qui dépendent tous deux de `a` :

```fly run
soit a = 1;
lie b = a + 1;
lie c = a * 10;
lie d = b + c;

quand d {
    affiche "d vaut maintenant", d;
}

a = 2;
a = 5;
```

Pour `a = 2;`, `d` est recalculée une fois, **après** `b` et `c`. L'observateur reçoit donc 23, jamais 13 (la valeur qu'on obtiendrait avec `b` à jour mais pas encore `c`).

## Valeurs et opérateurs

Butterfly a trois sortes de valeurs : les **entiers** (de taille illimitée), les **booléens** (`vrai`, `faux`) et les **textes**. Les variables n'ont pas de type déclaré : c'est la valeur qui en porte un, et les erreurs de type sont signalées à l'exécution.

```fly run
affiche 2 + 3 * 4, (2 + 3) * 4;
affiche 17 / 5, 17 % 5, -17 / 5, -17 % 5;
affiche 1 < 2, non (1 < 2) ou 5 >= 5;
affiche "but" + "terfly", "a" < "b";
affiche 99999999999 * 99999999999;
```

`/` est la division entière arrondie vers le bas, et `%` le reste de même signe que le diviseur (comme `//` et `%` de Python). Voici les priorités, du moins prioritaire au plus prioritaire :

| Niveau | Opérateurs | Associativité |
|---|---|---|
| 1 | `ou` | gauche |
| 2 | `et` | gauche |
| 3 | `non` | préfixe |
| 4 | `==` `!=` `<` `<=` `>` `>=` | aucune |
| 5 | `+` `-` | gauche |
| 6 | `*` `/` `%` | gauche |
| 7 | `-` unaire | préfixe |

Les comparaisons **ne s'enchaînent pas** : `1 < 2 < 3` est une erreur, qui dit comment l'écrire.

```fly erreur
affiche 1 < 2 < 3;
```

`et` et `ou` **court-circuitent** : `faux et (1 / 0 == 0)` vaut `faux` sans jamais diviser par zéro. Et `==` compare aussi les types : `vrai == 1` vaut `faux`.

## Conditions et boucles

```fly run
soit note = 14;
si note >= 16 {
    affiche "très bien";
} sinon si note >= 12 {
    affiche "bien";
} sinon {
    affiche "à revoir";
}

pour i dans 1..4 {
    affiche i, i * i;
}
```

La borne haute d'un `pour` est **exclue** : `1..4` donne 1, 2, 3. Les bornes sont évaluées une seule fois, avant la boucle. La variable de boucle est en lecture seule.

## Blocs et portées

Un nom déclaré dans un bloc n'existe plus après lui. Surtout, un nom **ne peut jamais en masquer un autre** : c'est plus strict que Python, et c'est ce qui permet au code Python généré de garder exactement le même sens.

```fly erreur
soit a = 1;
si vrai {
    soit a = 2;
}
```

## Fonctions prédéfinies

Il y en a trois, qui travaillent sur des entiers : `min`, `max` et `abs`.

```fly run
affiche min(4, 9), max(4, 9), abs(-7);
```

## Les erreurs

Une erreur donne son genre, sa position, un message qui dit quoi faire, et la ligne fautive soulignée. Butterfly signale **toutes** les erreurs d'un coup plutôt qu'une par une.

```fly erreur
soit a = ;
soit b = 2
affiche c;
```

Il y a quatre genres d'erreurs : lexicale (un caractère que le langage ne connaît pas), de syntaxe, sémantique (le programme est bien écrit mais n'a pas de sens) et d'exécution.

```fly erreur
soit x = 3 @ 2;
```

```fly erreur
soit a = 1;
lie b = a;
b = 2;
```

Une erreur d'exécution donne la ligne **du programme Butterfly** (pas celle du Python généré), et ce qui a déjà été affiché est conservé :

```fly run
affiche "début";
affiche 1 / 0;
affiche "fin";
```

## Ce que Butterfly ne fait pas

Pas de fonctions définies par l'utilisateur, pas de listes, pas de nombres décimaux, pas d'entrées-sorties (ni fichiers, ni clavier, ni réseau). Un programme ne peut que calculer et afficher. C'est un choix : cela rend le langage petit et, surtout, sûr à exécuter pour une IA (voir la page sur le [serveur MCP](mcp.html)).
