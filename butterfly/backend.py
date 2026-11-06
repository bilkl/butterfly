"""Les backends : ce qu'on peut produire à partir d'un programme analysé.

``Backend`` est un ``Protocol`` : tout objet qui a un ``nom`` et une méthode
``produire`` en est un, sans héritage. Ajouter un backend ne modifie ni la CLI, ni
le générateur existant : c'est le principe ouvert/fermé.
"""

from typing import Protocol

from butterfly.formatter import format_source
from butterfly.generator import generate_python
from butterfly.semantics import Analysis


class Backend(Protocol):
    name: str

    def produce(self, analysis: Analysis, source: str) -> str: ...


class PythonBackend:
    """Traduit le programme en Python."""

    name = "python"

    def produce(self, analysis: Analysis, source: str) -> str:
        return generate_python(analysis)


class FormatBackend:
    """Réécrit le programme en Butterfly canonique."""

    name = "format"

    def produce(self, analysis: Analysis, source: str) -> str:
        return format_source(source)


BACKENDS: dict[str, Backend] = {
    backend.name: backend for backend in (PythonBackend(), FormatBackend())
}
