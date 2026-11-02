"""Le formateur : réécrit un programme Butterfly dans une présentation canonique.

C'est un second « backend » : au lieu de produire du Python, il reproduit du
Butterfly, avec quatre espaces d'indentation, un espace autour des opérateurs et
seulement les parenthèses nécessaires. Il conserve les commentaires et une ligne
vide entre deux blocs d'instructions, et il est **idempotent** : formater un
programme déjà formaté ne change rien.
"""

from collections import deque

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
    InstructionHaute,
    Liaison,
    Nom,
    Observation,
    Pour,
    Programme,
    Si,
    Texte,
    Unaire,
)
from butterfly.parser import Parseur, lister_tokens
from butterfly.tokens import Token, TypeToken

INDENTATION = "    "

#: Priorité de chaque opérateur, pour savoir quand une parenthèse est nécessaire.
PRIORITE = {
    "ou": 1,
    "et": 2,
    "non": 3,
    "==": 4, "!=": 4, "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5,
    "*": 6, "/": 6, "%": 6,
}  # fmt: skip
PRIORITE_UNAIRE = 7
PRIORITE_PRIMAIRE = 8


def priorite(expression: Expression) -> int:
    match expression:
        case Binaire(operateur=operateur):
            return PRIORITE[operateur]
        case Unaire(operateur="non"):
            return PRIORITE["non"]
        case Unaire():
            return PRIORITE_UNAIRE
        case _:
            return PRIORITE_PRIMAIRE


def texte_butterfly(texte: str) -> str:
    echappe = texte.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{echappe}"'


def rendre_expression(expression: Expression) -> str:
    """L'expression en texte, avec les parenthèses strictement nécessaires."""
    match expression:
        case Entier(valeur=valeur):
            return str(valeur)
        case Texte(valeur=valeur):
            return texte_butterfly(valeur)
        case Booleen(valeur=valeur):
            return "vrai" if valeur else "faux"
        case Nom(nom=nom):
            return nom
        case Appel(nom=nom, arguments=arguments):
            return f"{nom}({', '.join(rendre_expression(a) for a in arguments)})"
        case Unaire(operateur="non", operande=operande):
            interieur = rendre_expression(operande)
            # `non a == b` serait correct, mais `non (a == b)` se lit sans effort :
            # on garde les parenthèses autour de tout opérande binaire.
            if isinstance(operande, Binaire):
                interieur = f"({interieur})"
            return f"non {interieur}"
        case Unaire(operande=operande):
            interieur = rendre_expression(operande)
            if priorite(operande) < PRIORITE_PRIMAIRE:
                interieur = f"({interieur})"
            return f"-{interieur}"
        case Binaire(operateur=operateur, gauche=gauche, droite=droite):
            p = PRIORITE[operateur]
            comparaison = p == 4
            texte_gauche = rendre_expression(gauche)
            texte_droite = rendre_expression(droite)
            # À gauche : les opérateurs de même priorité s'enchaînent (associativité
            # à gauche), sauf les comparaisons qui ne s'enchaînent jamais.
            if priorite(gauche) < p or (comparaison and priorite(gauche) == p):
                texte_gauche = f"({texte_gauche})"
            # À droite : même priorité = parenthèses (a - (b - c)).
            if priorite(droite) <= p:
                texte_droite = f"({texte_droite})"
            # `non` ne peut pas être l'opérande direct d'un opérateur plus fort.
            return f"{texte_gauche} {operateur} {texte_droite}"
    raise AssertionError(f"expression inconnue : {expression!r}")


class Formateur:
    """Écrit un programme ligne par ligne, en replaçant les commentaires."""

    def __init__(self, source: str, programme: Programme, commentaires: list[Token]):
        self.lignes_source = source.splitlines()
        self.programme = programme
        self.commentaires: deque[Token] = deque(
            sorted(commentaires, key=lambda t: t.position.ligne)
        )
        self.sortie: list[str] = []
        self.premier = True  # premier élément du bloc courant ?

    # --- Lignes, commentaires et lignes vides -------------------------------

    def _en_fin_de_ligne(self, commentaire: Token) -> bool:
        """Le commentaire suit-il du code sur sa ligne ?"""
        ligne = self.lignes_source[commentaire.position.ligne - 1]
        return ligne[: commentaire.position.colonne - 1].strip() != ""

    def _blanc_avant(self, ligne: int) -> None:
        """Conserve (une seule) ligne vide si le source en avait une avant."""
        if (
            not self.premier
            and ligne >= 2
            and self.lignes_source[ligne - 2].strip() == ""
        ):
            self.sortie.append("")

    def _commentaire_seul(self, indentation: int) -> None:
        commentaire = self.commentaires.popleft()
        self._blanc_avant(commentaire.position.ligne)
        self.sortie.append(INDENTATION * indentation + commentaire.lexeme.rstrip())
        self.premier = False

    def _commentaires_avant(self, ligne: int, indentation: int) -> None:
        while self.commentaires and self.commentaires[0].position.ligne < ligne:
            self._commentaire_seul(indentation)

    def _debut(self, ligne: int, indentation: int) -> None:
        """À appeler avant chaque instruction : commentaires et ligne vide."""
        self._commentaires_avant(ligne, indentation)
        self._blanc_avant(ligne)

    def _ligne(self, indentation: int, texte: str, ligne_source: int) -> None:
        suffixe = ""
        if (
            self.commentaires
            and self.commentaires[0].position.ligne == ligne_source
            and self._en_fin_de_ligne(self.commentaires[0])
        ):
            suffixe = "  " + self.commentaires.popleft().lexeme.rstrip()
        self.sortie.append(INDENTATION * indentation + texte + suffixe)
        self.premier = False

    # --- Programme et instructions ------------------------------------------

    def rendre(self) -> str:
        for instruction in self.programme.instructions:
            self.instruction(instruction, 0)
        while self.commentaires:
            self._commentaire_seul(0)
        return "\n".join(self.sortie) + "\n" if self.sortie else ""

    def corps(self, bloc: Bloc, indentation: int) -> None:
        """Les instructions d'un bloc, et les commentaires avant son ``}``."""
        self.premier = True
        for instruction in bloc.instructions:
            self.instruction(instruction, indentation)
        self._commentaires_avant(bloc.fin.ligne, indentation)

    def instruction(
        self, instruction: Instruction | InstructionHaute, indentation: int
    ) -> None:
        ligne = instruction.position.ligne
        self._debut(ligne, indentation)
        match instruction:
            case Declaration(nom=nom, valeur=valeur):
                self._ligne(
                    indentation, f"soit {nom} = {rendre_expression(valeur)};", ligne
                )
            case Liaison(nom=nom, valeur=valeur):
                self._ligne(
                    indentation, f"lie {nom} = {rendre_expression(valeur)};", ligne
                )
            case Affectation(nom=nom, valeur=valeur):
                self._ligne(indentation, f"{nom} = {rendre_expression(valeur)};", ligne)
            case Affiche(valeurs=valeurs):
                liste = ", ".join(rendre_expression(v) for v in valeurs)
                self._ligne(indentation, f"affiche {liste};", ligne)
            case Observation(cible=cible, corps=corps):
                self._ligne(indentation, f"quand {cible} {{", ligne)
                self.corps(corps, indentation + 1)
                self._ligne(indentation, "}", corps.fin.ligne)
            case Pour() as pour:
                debut = rendre_expression(pour.debut)
                fin = rendre_expression(pour.fin)
                self._ligne(
                    indentation, f"pour {pour.variable} dans {debut}..{fin} {{", ligne
                )
                self.corps(pour.corps, indentation + 1)
                self._ligne(indentation, "}", pour.corps.fin.ligne)
            case Si() as si:
                self.si(si, indentation, "si")

    def si(self, si: Si, indentation: int, mot: str) -> None:
        condition = rendre_expression(si.condition)
        self._ligne(indentation, f"{mot} {condition} {{", si.position.ligne)
        self.corps(si.alors, indentation + 1)
        suite = si.sinon
        ligne_fermeture = si.alors.fin.ligne
        if isinstance(suite, Si):
            # Le « } » fermant est fusionné avec le « sinon si » suivant.
            self.si(suite, indentation, "} sinon si")
        elif isinstance(suite, Bloc):
            self._ligne(indentation, "} sinon {", ligne_fermeture)
            self.corps(suite, indentation + 1)
            self._ligne(indentation, "}", suite.fin.ligne)
        else:
            self._ligne(indentation, "}", ligne_fermeture)


def formater_programme(
    source: str, programme: Programme, commentaires: list[Token]
) -> str:
    return Formateur(source, programme, commentaires).rendre()


def formater(source: str) -> str:
    """Le programme ``source``, réécrit dans sa présentation canonique.

    Lève ``ErreurCompilation`` si le programme a des erreurs de syntaxe : on ne
    formate pas un programme qu'on ne comprend pas. (L'analyse sémantique n'est
    pas nécessaire.)
    """
    tokens = lister_tokens(source, commentaires=True)
    programme = Parseur(tokens).programme()
    commentaires = [t for t in tokens if t.type is TypeToken.COMMENTAIRE]
    return formater_programme(source, programme, commentaires)
