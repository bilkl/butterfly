"""Les backends : ce qu'on peut produire à partir d'un programme analysé.

``Backend`` est un ``Protocol`` : tout objet qui a un ``nom`` et une méthode
``produire`` en est un, sans héritage. Ajouter un backend ne modifie ni la CLI, ni
le générateur existant : c'est le principe ouvert/fermé.
"""

from typing import Protocol

from butterfly.formateur import formater
from butterfly.generateur import generer_python
from butterfly.semantique import Analyse


class Backend(Protocol):
    nom: str

    def produire(self, analyse: Analyse, source: str) -> str: ...


class BackendPython:
    """Traduit le programme en Python."""

    nom = "python"

    def produire(self, analyse: Analyse, source: str) -> str:
        return generer_python(analyse)


class BackendFormat:
    """Réécrit le programme en Butterfly canonique."""

    nom = "format"

    def produire(self, analyse: Analyse, source: str) -> str:
        return formater(source)


BACKENDS: dict[str, Backend] = {
    backend.nom: backend for backend in (BackendPython(), BackendFormat())
}
