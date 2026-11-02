"""Le générateur : traduit l'arbre vérifié en texte Python.

Le point clé est la **propagation**. Butterfly n'embarque aucun moteur réactif à
l'exécution : le compilateur calcule, pour chaque affectation d'une cellule
source, la liste ordonnée des cellules dérivées à recalculer et des
observateurs à prévenir, puis écrit le code qui le fait.

Pour ``quantite = 5;`` dans le programme

    soit prix = 20;  soit quantite = 3;
    lie total = prix * quantite;
    quand total { affiche total; }

le code généré est :

    _av_total = v_total          # on retient la valeur avant
    v_quantite = 5
    v_total = _calc_total()      # on recalcule ce qui dépend de quantite
    if _change(_av_total, v_total):
        _obs_0()                 # on prévient l'observateur si la valeur a changé

Les cellules dérivées sont recalculées dans l'ordre de leur déclaration, qui est
un ordre topologique valide puisqu'on déclare avant d'utiliser : chaque cellule
est recalculée une seule fois, après toutes celles dont elle dépend.
"""

from butterfly.noeuds import (
    Affectation,
    Affiche,
    Appel,
    Binaire,
    Bloc,
    Booleen,
    Declaration,
    Entier,
    Expression,
    Instruction,
    Liaison,
    Nom,
    Observation,
    Pour,
    Si,
    Texte,
    Unaire,
)
from butterfly.semantique import Analyse, GenreSymbole

#: Fonction du runtime associée à chaque opérateur binaire « simple ».
OPERATEURS = {
    "+": "_plus",
    "-": "_moins",
    "*": "_fois",
    "/": "_divise",
    "%": "_reste",
    "<": "_inf",
    "<=": "_inf_egal",
    ">": "_sup",
    ">=": "_sup_egal",
}

INDENTATION = "    "


def nom_python(nom: str) -> str:
    """Le nom Python d'une variable Butterfly : toujours préfixé par ``v_``."""
    return f"v_{nom}"


class GenerateurPython:
    """Génère le texte Python d'un programme analysé."""

    def __init__(self, analyse: Analyse) -> None:
        self.analyse = analyse
        self.lignes: list[str] = []
        self.utilises: set[str] = set()
        # Ce qu'on a rencontré *jusqu'ici* dans le programme, dans l'ordre :
        # une affectation ne concerne que ce qui est déjà déclaré à cet endroit.
        self.liees: list[str] = []
        self.observateurs: list[tuple[int, str]] = []

    # --- Sortie -------------------------------------------------------------

    def generer(self) -> str:
        for instruction in self.analyse.programme.instructions:
            self.instruction(instruction, 0)
        entete = ["# Généré par Butterfly (butterfly transpile) : ne pas modifier."]
        if self.utilises:
            noms = ", ".join(sorted(self.utilises))
            entete.append(f"from butterfly.runtime import {noms}")
        return "\n".join([*entete, "", *self.lignes]) + "\n"

    def ecrire(self, indentation: int, texte: str) -> None:
        self.lignes.append(INDENTATION * indentation + texte)

    def utiliser(self, fonction: str) -> str:
        self.utilises.add(fonction)
        return fonction

    # --- Instructions -------------------------------------------------------

    def bloc(self, bloc: Bloc, indentation: int) -> None:
        if not bloc.instructions:
            self.ecrire(indentation, "pass")
        for instruction in bloc.instructions:
            self.instruction(instruction, indentation)

    def instruction(
        self, instruction: Instruction | Liaison | Observation, indentation: int
    ) -> None:
        match instruction:
            case Declaration(nom=nom, valeur=valeur):
                self.ecrire(indentation, f"{nom_python(nom)} = {self.expr(valeur)}")
            case Liaison(nom=nom, valeur=valeur):
                self.liaison(nom, valeur)
            case Affectation(nom=nom, valeur=valeur):
                self.affectation(nom, valeur, indentation)
            case Si() as si:
                self.si(si, indentation)
            case Pour() as pour:
                self.pour(pour, indentation)
            case Affiche(valeurs=valeurs):
                arguments = ", ".join(self.expr(valeur) for valeur in valeurs)
                self.ecrire(indentation, f"{self.utiliser('_affiche')}({arguments})")
            case Observation() as observation:
                self.observation(observation)

    def liaison(self, nom: str, valeur: Expression) -> None:
        # Une fonction par cellule dérivée : on la rappelle à chaque recalcul.
        self.ecrire(0, f"def _calc_{nom}():")
        self.ecrire(1, f"return {self.expr(valeur)}")
        self.ecrire(0, f"{nom_python(nom)} = _calc_{nom}()")
        self.liees.append(nom)

    def observation(self, observation: Observation) -> None:
        numero = len(self.observateurs)
        self.ecrire(0, f"def _obs_{numero}():")
        self.bloc(observation.corps, 1)
        self.observateurs.append((numero, observation.cible))

    def affectation(self, nom: str, valeur: Expression, indentation: int) -> None:
        genre = self.analyse.genres.get(nom)
        if genre is not GenreSymbole.SOURCE:  # une variable locale : rien à propager
            self.ecrire(indentation, f"{nom_python(nom)} = {self.expr(valeur)}")
            return
        # 1. Quelles cellules dérivées dépendent (même de loin) de `nom` ?
        touchees = {nom}
        a_recalculer: list[str] = []
        for cellule in self.liees:
            if self.analyse.dependances[cellule] & touchees:
                touchees.add(cellule)
                a_recalculer.append(cellule)
        # 2. Lesquelles sont observées ?
        observees = {cible for _, cible in self.observateurs}
        surveillees = [c for c in [nom, *a_recalculer] if c in observees]
        # 3. On retient les valeurs d'avant, on affecte, on recalcule, on notifie.
        for cellule in surveillees:
            self.ecrire(indentation, f"_av_{cellule} = {nom_python(cellule)}")
        self.ecrire(indentation, f"{nom_python(nom)} = {self.expr(valeur)}")
        for cellule in a_recalculer:
            self.ecrire(indentation, f"{nom_python(cellule)} = _calc_{cellule}()")
        for numero, cible in self.observateurs:
            if cible in surveillees:
                change = self.utiliser("_change")
                self.ecrire(
                    indentation,
                    f"if {change}(_av_{cible}, {nom_python(cible)}):",
                )
                self.ecrire(indentation + 1, f"_obs_{numero}()")

    def si(self, si: Si, indentation: int) -> None:
        condition = self.utiliser("_condition")
        self.ecrire(
            indentation,
            f"if {condition}({self.expr(si.condition)}, {si.position.ligne}):",
        )
        self.bloc(si.alors, indentation + 1)
        suite = si.sinon
        while isinstance(suite, Si):
            self.ecrire(
                indentation,
                f"elif {condition}({self.expr(suite.condition)}, "
                f"{suite.position.ligne}):",
            )
            self.bloc(suite.alors, indentation + 1)
            suite = suite.sinon
        if isinstance(suite, Bloc):
            self.ecrire(indentation, "else:")
            self.bloc(suite, indentation + 1)

    def pour(self, pour: Pour, indentation: int) -> None:
        borne = self.utiliser("_borne")
        ligne = pour.position.ligne
        debut = f"{borne}({self.expr(pour.debut)}, {ligne})"
        fin = f"{borne}({self.expr(pour.fin)}, {ligne})"
        self.ecrire(
            indentation, f"for {nom_python(pour.variable)} in range({debut}, {fin}):"
        )
        self.bloc(pour.corps, indentation + 1)

    # --- Expressions --------------------------------------------------------

    def expr(self, expression: Expression) -> str:
        match expression:
            case Entier(valeur=valeur):
                return str(valeur)
            case Texte(valeur=valeur):
                return repr(valeur)
            case Booleen(valeur=valeur):
                return "True" if valeur else "False"
            case Nom(nom=nom):
                return nom_python(nom)
            case Unaire(operateur="-", operande=operande, position=position):
                return (
                    f"{self.utiliser('_neg')}({self.expr(operande)}, {position.ligne})"
                )
            case Unaire(operande=operande, position=position):  # non
                booleen = self.utiliser("_booleen")
                return f"(not {booleen}({self.expr(operande)}, {position.ligne}))"
            case Binaire() as binaire:
                return self.binaire(binaire)
            case Appel(nom=nom, arguments=arguments, position=position):
                fonction = self.utiliser(f"_{nom}")
                valeurs = ", ".join(self.expr(argument) for argument in arguments)
                return f"{fonction}({valeurs}, {position.ligne})"
        raise AssertionError(f"expression inconnue : {expression!r}")

    def binaire(self, expression: Binaire) -> str:
        operateur = expression.operateur
        gauche = self.expr(expression.gauche)
        droite = self.expr(expression.droite)
        ligne = expression.position.ligne
        if operateur == "==":
            return f"{self.utiliser('_egal')}({gauche}, {droite})"
        if operateur == "!=":
            return f"(not {self.utiliser('_egal')}({gauche}, {droite}))"
        if operateur in ("et", "ou"):
            booleen = self.utiliser("_booleen")
            mot = "and" if operateur == "et" else "or"
            return f"({booleen}({gauche}, {ligne}) {mot} {booleen}({droite}, {ligne}))"
        fonction = self.utiliser(OPERATEURS[operateur])
        return f"{fonction}({gauche}, {droite}, {ligne})"


def generer_python(analyse: Analyse) -> str:
    """Le texte Python correspondant à un programme analysé."""
    return GenerateurPython(analyse).generer()
