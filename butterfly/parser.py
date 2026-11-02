"""Le parser : transforme les tokens en arbre syntaxique.

- Les **instructions** sont analysées par descente récursive : une méthode par
  règle de la grammaire.
- Les **expressions** sont analysées par un parser de Pratt : une table donne la
  priorité de chaque opérateur, et ajouter un opérateur revient à ajouter une
  ligne dans la table.
- Le parser **ne s'arrête pas à la première erreur** : il la note, se
  resynchronise sur l'instruction suivante, et signale toutes les erreurs en une
  seule fois.
"""

from collections.abc import Callable

from butterfly.erreurs import (
    ErreurButterfly,
    ErreurCompilation,
    ErreurLexicale,
    ErreurSyntaxe,
    Position,
)
from butterfly.lexer import tokenize
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
from butterfly.tokens import Token, TypeToken

T = TypeToken

#: Priorité de chaque opérateur binaire (plus grand = plus prioritaire).
PRIORITES: dict[TypeToken, tuple[int, str]] = {
    T.OU: (10, "ou"),
    T.ET: (20, "et"),
    T.EGAL_EGAL: (40, "=="),
    T.DIFFERENT: (40, "!="),
    T.INF: (40, "<"),
    T.INF_EGAL: (40, "<="),
    T.SUP: (40, ">"),
    T.SUP_EGAL: (40, ">="),
    T.PLUS: (50, "+"),
    T.MOINS: (50, "-"),
    T.ETOILE: (60, "*"),
    T.SLASH: (60, "/"),
    T.POURCENT: (60, "%"),
}
PRIORITE_NON = 30
PRIORITE_COMPARAISON = 40
PRIORITE_MOINS_UNAIRE = 70
COMPARATEURS = frozenset(t for t, (p, _) in PRIORITES.items() if p == 40)

#: Les mots-clés qui commencent une instruction : points de resynchronisation.
DEBUTS_INSTRUCTION = frozenset({T.SOIT, T.LIE, T.QUAND, T.SI, T.POUR, T.AFFICHE})


class Parseur:
    """Un parser sur une liste de tokens (les commentaires sont ignorés)."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = [t for t in tokens if t.type is not T.COMMENTAIRE]
        self.i = 0
        self.erreurs: list[ErreurButterfly] = []

    # --- Outils -------------------------------------------------------------

    def courant(self) -> Token:
        return self.tokens[self.i]

    def avancer(self) -> Token:
        token = self.tokens[self.i]
        if token.type is not T.FIN:
            self.i += 1
        return token

    def verifier(self, *types: TypeToken) -> bool:
        return self.courant().type in types

    @staticmethod
    def decrire(token: Token) -> str:
        return "fin de programme" if token.type is T.FIN else f"'{token.lexeme}'"

    def erreur(self, message: str, position: Position | None = None) -> ErreurSyntaxe:
        return ErreurSyntaxe(message, position or self.courant().position)

    def consommer(self, type_attendu: TypeToken, attendu: str) -> Token:
        if self.verifier(type_attendu):
            return self.avancer()
        raise self.erreur(f"{attendu} attendu, {self.decrire(self.courant())} trouvé")

    def point_virgule(self) -> None:
        """Consomme le ``;`` final. S'il manque, l'erreur est signalée **juste
        après** le dernier token de l'instruction, là où il aurait dû être."""
        if self.verifier(T.POINT_VIRGULE):
            self.avancer()
            return
        precedent = self.tokens[self.i - 1]
        fin = Position(
            precedent.position.ligne,
            precedent.position.colonne + len(precedent.lexeme),
        )
        raise self.erreur(
            "';' attendu à la fin de l'instruction, "
            f"{self.decrire(self.courant())} trouvé",
            fin,
        )

    # --- Récupération d'erreurs ---------------------------------------------

    def _avec_recuperation[R](self, analyse: Callable[[], R]) -> R | None:
        """Lance ``analyse`` ; en cas d'erreur, la note et se resynchronise."""
        debut = self.i
        try:
            return analyse()
        except ErreurSyntaxe as erreur:
            self.erreurs.append(erreur)
            self._resynchroniser(debut)
            return None

    def _resynchroniser(self, debut: int) -> None:
        """Saute les tokens jusqu'au début de l'instruction suivante."""
        if self.i == debut:  # garantit qu'on avance toujours
            self.avancer()
        while not self.verifier(T.FIN):
            type_courant = self.courant().type
            if type_courant is T.POINT_VIRGULE:
                self.avancer()
                return
            if type_courant is T.ACC_D or type_courant in DEBUTS_INSTRUCTION:
                return
            self.avancer()

    # --- Programme et instructions ------------------------------------------

    def programme(self) -> Programme:
        instructions: list[InstructionHaute] = []
        while not self.verifier(T.FIN):
            instruction = self._avec_recuperation(self.instruction_haute)
            if instruction is not None:
                instructions.append(instruction)
        if self.erreurs:
            raise ErreurCompilation(tuple(self.erreurs))
        return Programme(tuple(instructions))

    def instruction_haute(self) -> InstructionHaute:
        """Au niveau supérieur, ``lie`` et ``quand`` sont permis."""
        if self.verifier(T.LIE):
            return self.liaison()
        if self.verifier(T.QUAND):
            return self.observation()
        return self.instruction()

    def instruction(self) -> Instruction:
        token = self.courant()
        match token.type:
            case T.SOIT:
                return self.declaration()
            case T.SI:
                return self.si()
            case T.POUR:
                return self.pour()
            case T.AFFICHE:
                return self.affiche()
            case T.IDENT:
                return self.affectation()
            case T.LIE | T.QUAND:
                raise self.erreur(
                    f"'{token.lexeme}' n'est permis qu'au niveau supérieur"
                )
            case _:
                raise self.erreur(f"instruction attendue, {self.decrire(token)} trouvé")

    def declaration(self) -> Declaration:
        mot = self.avancer()
        nom = self.consommer(T.IDENT, "nom")
        self.consommer(T.EGAL, "'='")
        valeur = self.expression()
        self.point_virgule()
        return Declaration(nom.lexeme, valeur, mot.position, nom.position)

    def liaison(self) -> Liaison:
        mot = self.avancer()
        nom = self.consommer(T.IDENT, "nom")
        self.consommer(T.EGAL, "'='")
        valeur = self.expression()
        self.point_virgule()
        return Liaison(nom.lexeme, valeur, mot.position, nom.position)

    def observation(self) -> Observation:
        mot = self.avancer()
        cible = self.consommer(T.IDENT, "nom de cellule")
        corps = self.bloc()
        return Observation(cible.lexeme, corps, mot.position, cible.position)

    def affectation(self) -> Affectation:
        nom = self.avancer()
        if not self.verifier(T.EGAL):
            raise self.erreur(
                f"'=' attendu après {self.decrire(nom)}, "
                f"{self.decrire(self.courant())} trouvé"
            )
        self.avancer()
        valeur = self.expression()
        self.point_virgule()
        return Affectation(nom.lexeme, valeur, nom.position)

    def si(self) -> Si:
        mot = self.avancer()
        condition = self.expression()
        alors = self.bloc()
        sinon: Si | Bloc | None = None
        if self.verifier(T.SINON):
            self.avancer()
            sinon = self.si() if self.verifier(T.SI) else self.bloc()
        return Si(condition, alors, sinon, mot.position)

    def pour(self) -> Pour:
        mot = self.avancer()
        variable = self.consommer(T.IDENT, "nom de variable")
        self.consommer(T.DANS, "'dans'")
        debut = self.expression()
        self.consommer(T.POINT_POINT, "'..'")
        fin = self.expression()
        corps = self.bloc()
        return Pour(variable.lexeme, debut, fin, corps, mot.position, variable.position)

    def affiche(self) -> Affiche:
        mot = self.avancer()
        valeurs = [self.expression()]
        while self.verifier(T.VIRGULE):
            self.avancer()
            valeurs.append(self.expression())
        self.point_virgule()
        return Affiche(tuple(valeurs), mot.position)

    def bloc(self) -> Bloc:
        ouvrant = self.consommer(T.ACC_G, "'{'")
        instructions: list[Instruction] = []
        while not self.verifier(T.ACC_D, T.FIN):
            instruction = self._avec_recuperation(self.instruction)
            if instruction is not None:
                instructions.append(instruction)
        fermant = self.consommer(T.ACC_D, "'}'")
        return Bloc(tuple(instructions), ouvrant.position, fermant.position)

    # --- Expressions (parser de Pratt) --------------------------------------

    def expression(self, priorite_min: int = 0) -> Expression:
        """Analyse une expression, en ne consommant que les opérateurs dont la
        priorité est au moins ``priorite_min``."""
        gauche = self.prefixe(priorite_min)
        while True:
            operateur = self.courant()
            infos = PRIORITES.get(operateur.type)
            if infos is None or infos[0] < priorite_min:
                return gauche
            priorite, symbole = infos
            self.avancer()
            # Associativité à gauche : l'opérande de droite ne peut contenir que
            # des opérateurs *strictement* plus prioritaires.
            droite = self.expression(priorite + 1)
            gauche = Binaire(symbole, gauche, droite, operateur.position)
            if priorite == PRIORITE_COMPARAISON and self.verifier(*COMPARATEURS):
                raise self.erreur("les comparaisons ne s'enchaînent pas, utilisez 'et'")

    def prefixe(self, priorite_min: int) -> Expression:
        token = self.courant()
        if token.type is T.MOINS:
            self.avancer()
            operande = self.expression(PRIORITE_MOINS_UNAIRE)
            return Unaire("-", operande, token.position)
        if token.type is T.NON:
            if priorite_min > PRIORITE_NON:
                raise self.erreur("'non' doit être entre parenthèses à cet endroit")
            self.avancer()
            return Unaire("non", self.expression(PRIORITE_NON), token.position)
        return self.primaire()

    def primaire(self) -> Expression:
        token = self.courant()
        match token.type:
            case T.ENTIER:
                self.avancer()
                assert isinstance(token.valeur, int)
                return Entier(token.valeur, token.position)
            case T.TEXTE:
                self.avancer()
                assert isinstance(token.valeur, str)
                return Texte(token.valeur, token.position)
            case T.VRAI | T.FAUX:
                self.avancer()
                return Booleen(token.type is T.VRAI, token.position)
            case T.IDENT:
                self.avancer()
                if self.verifier(T.PAREN_G):
                    return self.appel(token)
                return Nom(token.lexeme, token.position)
            case T.PAREN_G:
                self.avancer()
                interieur = self.expression()
                self.consommer(T.PAREN_D, "')'")
                return interieur
            case _:
                raise self.erreur(f"expression attendue, {self.decrire(token)} trouvé")

    def appel(self, nom: Token) -> Appel:
        self.avancer()  # la parenthèse ouvrante
        arguments: list[Expression] = []
        if not self.verifier(T.PAREN_D):
            arguments.append(self.expression())
            while self.verifier(T.VIRGULE):
                self.avancer()
                arguments.append(self.expression())
        self.consommer(T.PAREN_D, "')'")
        return Appel(nom.lexeme, tuple(arguments), nom.position)


def lister_tokens(source: str, *, commentaires: bool = False) -> list[Token]:
    """Tous les tokens de ``source`` ; une erreur lexicale devient une
    ``ErreurCompilation``."""
    try:
        return list(tokenize(source, commentaires=commentaires))
    except ErreurLexicale as erreur:
        raise ErreurCompilation((erreur,)) from erreur


def analyser_syntaxe(source: str) -> Programme:
    """Le texte source devient un arbre, ou lève ``ErreurCompilation``."""
    return Parseur(lister_tokens(source)).programme()
