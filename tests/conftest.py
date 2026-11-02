"""Configuration commune des tests.

- rend le paquet ``butterfly`` importable même sans installation ;
- choisit asyncio pour les tests asynchrones du serveur MCP (greffon d'anyio,
  installé avec le SDK).
"""

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from mcp import Client

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    """Un client MCP connecté au serveur Butterfly **dans le même processus**."""
    from serveur_butterfly.serveur import mcp

    async with Client(mcp) as connecte:
        yield connecte
